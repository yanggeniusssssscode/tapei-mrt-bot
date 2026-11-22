"""
台北捷運轉乘時間優化 LINE Bot 主程式
- 提供 Flask Webhook 端點 (/callback)
- 整合混合式轉乘優化演算法與 LINE Flex Message / Quick Reply 互動
- 支援文字智慧剖析、全路線車站引導與雙方案乘車推薦
"""

import os
import re
import datetime
import logging
import sqlite3
from typing import Dict, Any, Optional, Tuple
from flask import Flask, request, abort, jsonify
from dotenv import load_dotenv

# LINE Bot SDK v3
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer,
    QuickReply,
    QuickReplyItem,
    MessageAction,
    DatetimePickerAction
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, PostbackEvent

# 核心轉乘推算引擎與 Flex 模板
from mrt_engine import (
    ScheduleOptimizer,
    metro_graph,
    LINE_NAMES,
    is_taiwan_holiday_or_weekend,
    TAIPEI_TZ,
    get_now_taipei
)
from flex_templates import (
    create_transfer_result_flex,
    create_help_card_flex,
    create_line_selection_quick_reply,
    create_line_station_carousel_flex,
    LINE_CAROUSEL_CONFIG
)

# 載入環境變數
load_dotenv()

# 設定日誌
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 初始化 Flask App
app = Flask(__name__)

# 讀取金鑰設定
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "").strip()
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
PORT = int(os.getenv("PORT", 5000))

if not CHANNEL_SECRET or not CHANNEL_ACCESS_TOKEN:
    logger.warning("⚠️ 請確認 .env 中的 LINE_CHANNEL_SECRET 與 LINE_CHANNEL_ACCESS_TOKEN 是否已正確填寫！")

# 初始化 LINE SDK 客戶端
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ==========================================
# SQLite 使用者狀態持久化管理 (解決多進程/重啟狀態遺失)
# ==========================================
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_sessions.db")

def init_db():
    """初始化 SQLite 資料庫與 table"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    user_id TEXT PRIMARY KEY,
                    origin TEXT,
                    destination TEXT,
                    time_str TEXT,
                    updated_at TEXT
                );
            """)
            conn.commit()
    except Exception as e:
        logger.error(f"初始化 SQLite 資料庫失敗: {e}", exc_info=True)

# 啟動時自動初始化資料庫
init_db()

def get_user_session(user_id: str) -> Dict[str, Optional[str]]:
    """從 SQLite 讀取使用者的查詢狀態"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10.0) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT origin, destination, time_str FROM user_sessions WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return {"from": row[0], "to": row[1], "time": row[2]}
    except Exception as e:
        logger.error(f"讀取 SQLite session 失敗 (user_id={user_id}): {e}")
    return {"from": None, "to": None, "time": None}

def save_user_session(user_id: str, data: Dict[str, Optional[str]]):
    """將使用者的查詢狀態持久化寫入 SQLite"""
    try:
        now_str = datetime.datetime.now(TAIPEI_TZ).isoformat()
        with sqlite3.connect(DB_PATH, timeout=10.0) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_sessions (user_id, origin, destination, time_str, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, data.get("from"), data.get("to"), data.get("time"), now_str))
            conn.commit()
    except Exception as e:
        logger.error(f"寫入 SQLite session 失敗 (user_id={user_id}): {e}")

def clear_user_session(user_id: str):
    """清除使用者的查詢狀態"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10.0) as conn:
            conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"清除 SQLite session 失敗 (user_id={user_id}): {e}")

class UserSession:
    """使用者 Session 代理物件，修改屬性時自動同步寫入 SQLite"""
    def __init__(self, user_id: str):
        self.user_id = user_id
        self._data = get_user_session(user_id)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._data.get(key)

    def __setitem__(self, key: str, value: Any):
        self._data[key] = value
        save_user_session(self.user_id, self._data)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"UserSession({self.user_id}: {self._data})"

    def items(self):
        return self._data.items()

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def update(self, **kwargs):
        for k, v in kwargs.items():
            self._data[k] = v
        save_user_session(self.user_id, self._data)

    def clear(self):
        self._data = {"from": None, "to": None, "time": None}
        clear_user_session(self.user_id)

class SessionStore:
    """全域 Session 存取介面，相容於字典操作並底層對接 SQLite"""
    def __getitem__(self, user_id: str) -> UserSession:
        return UserSession(user_id)

    def __setitem__(self, user_id: str, value: Dict[str, Optional[str]]):
        save_user_session(user_id, value)

    def __contains__(self, user_id: str) -> bool:
        try:
            with sqlite3.connect(DB_PATH, timeout=10.0) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM user_sessions WHERE user_id = ?", (user_id,))
                return cursor.fetchone() is not None
        except Exception:
            return False

user_sessions = SessionStore()



# ==========================================
# 輔助函式：回覆訊息包裝
# ==========================================

def reply_single_message(reply_token: str, message_obj: Any):
    """透過 LINE Messaging API 發送單一訊息（具備錯誤診斷與純文字降級）"""
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[message_obj]
                )
            )
    except Exception as e:
        err_detail = getattr(e, "body", str(e))
        logger.error(f"發送 LINE 訊息失敗: {err_detail}", exc_info=True)
        # 若傳送 Flex 訊息遭 LINE 拒絕，發送降級純文字訊息避免使用者空等
        if isinstance(message_obj, FlexMessage):
            try:
                fallback_text = f"{message_obj.alt_text}\n\n（卡片載入稍有延遲，請點選下方選單繼續查詢）"
                with ApiClient(configuration) as fb_client:
                    api = MessagingApi(fb_client)
                    api.reply_message(
                        ReplyMessageRequest(
                            reply_token=reply_token,
                            messages=[TextMessage(text=fallback_text)]
                        )
                    )
            except Exception as fb_err:
                logger.error(f"發送降級訊息亦失敗: {fb_err}")


def extract_datetime_and_clean_text(text: str) -> Tuple[Optional[str], str]:
    """
    從輸入字串中解析日期（包含特定日期或週一～週日）與時間（HH:MM 或 X點/半/分），
    並將時間字元從字串中移除，返回 (標準化時間字串, 清洗後文字)。
    支援格式：
      - 「週一 08:30 迴龍到士林」-> ("2026-11-23T08:30", "迴龍到士林")
      - 「禮拜六 09:00 板橋到淡水」-> ("2026-11-28T09:00", "板橋到淡水")
      - 「09:00 迴龍 到 士林」-> ("09:00", "迴龍 到 士林")
      - 「2026-11-23 08:30 迴龍到士林」-> ("2026-11-23T08:30", "迴龍到士林")
    """
    now = get_now_taipei()
    clean_text = text.strip()
    target_date = None

    # 1. 匹配特定日期 (如 2026-11-23, 2026/11/23)
    m_full_date = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", clean_text)
    if m_full_date:
        y, m, d = int(m_full_date.group(1)), int(m_full_date.group(2)), int(m_full_date.group(3))
        target_date = datetime.date(y, m, d)
        clean_text = clean_text[:m_full_date.start()] + " " + clean_text[m_full_date.end():]
    else:
        # 月/日 (如 11/23, 11月23日)
        m_short_date = re.search(r"(\d{1,2})[/月](\d{1,2})日?", clean_text)
        if m_short_date:
            m, d = int(m_short_date.group(1)), int(m_short_date.group(2))
            target_date = datetime.date(now.year, m, d)
            clean_text = clean_text[:m_short_date.start()] + " " + clean_text[m_short_date.end():]
        else:
            # 2. 匹配星期/週/禮拜 (如 週一, 星期三, 禮拜天, 禮拜日, 週六)
            m_weekday = re.search(r"(?:下?週|星期|禮拜)([一二三四五六日天1-7])", clean_text)
            if m_weekday:
                wk_char = m_weekday.group(1)
                weekday_map = {"一": 0, "1": 0, "二": 1, "2": 1, "三": 2, "3": 2, "四": 3, "4": 3, "五": 4, "5": 4, "六": 5, "6": 5, "日": 6, "天": 6, "7": 6}
                target_w = weekday_map.get(wk_char)
                if target_w is not None:
                    today_w = now.weekday()
                    days_ahead = (target_w - today_w) % 7
                    if "下" in m_weekday.group(0) and days_ahead == 0:
                        days_ahead = 7
                    target_date = now.date() + datetime.timedelta(days=days_ahead)
                clean_text = clean_text[:m_weekday.start()] + " " + clean_text[m_weekday.end():]

    # 3. 匹配時間格式 (如 9:00, 09:30, 9點, 9點半, 9點30分)
    extracted_time_str = None
    m_colon = re.search(r"(\d{1,2})[:：](\d{2})", clean_text)
    if m_colon:
        h, m = int(m_colon.group(1)), int(m_colon.group(2))
        extracted_time_str = f"{h:02d}:{m:02d}"
        clean_text = clean_text[:m_colon.start()] + " " + clean_text[m_colon.end():]
    else:
        m_cn = re.search(r"(\d{1,2})\s*點\s*(?:半|(\d{1,2})\s*分?)?", clean_text)
        if m_cn:
            h = int(m_cn.group(1))
            if "半" in m_cn.group(0):
                m = 30
            elif m_cn.group(2):
                m = int(m_cn.group(2))
            else:
                m = 0
            extracted_time_str = f"{h:02d}:{m:02d}"
            clean_text = clean_text[:m_cn.start()] + " " + clean_text[m_cn.end():]

    # 組合日期與時間
    final_datetime_str = None
    if target_date and extracted_time_str:
        final_datetime_str = f"{target_date.isoformat()}T{extracted_time_str}"
    elif target_date and not extracted_time_str:
        cur_time = now.strftime("%H:%M")
        final_datetime_str = f"{target_date.isoformat()}T{cur_time}"
    elif extracted_time_str:
        final_datetime_str = extracted_time_str

    clean_text = re.sub(r"\s+", " ", clean_text).strip()
    return final_datetime_str, clean_text


def parse_query_text(text: str) -> Optional[Dict[str, str]]:
    """
    解析使用者自然語言輸入，擷取起訖站與出發時間
    支援格式：
      - 「迴龍 到 士林」、「迴龍到士林」
      - 「9:00 迴龍到士林」、「09:00 迴龍 到 士林」
      - 「週一 08:30 迴龍到士林」、「禮拜天 09:00 迴龍到士林」
      - 「迴龍到士林 9:00」、「迴龍到士林 18:30」
      - 「從 迴龍 到 士林」、「迴龍至士林」、「迴龍->士林」
    """
    extracted_datetime, clean_text = extract_datetime_and_clean_text(text)

    # 匹配起訖站 (如 迴龍到士林, 從迴龍到士林, 迴龍至士林, 迴龍->士林)
    route_pattern = r"(?:從\s*)?([^\s到至\->–]+?)\s*(?:到|至|\->|–|-)\s*([^\s0-9:：]+)"
    m_route = re.search(route_pattern, clean_text)
    if m_route:
        orig = m_route.group(1).strip()
        dest = m_route.group(2).strip()
        return {
            "origin": orig,
            "destination": dest,
            "time": extracted_datetime
        }

    return None


# ==========================================
# LINE Webhook 接收端點
# ==========================================

@app.route("/", methods=["GET"])
def index():
    """健康檢查與服務狀態端點"""
    return jsonify({
        "status": "healthy",
        "service": "Taipei Metro Transfer Optimization Bot",
        "version": "1.0.0"
    }), 200


@app.route("/keep-alive", methods=["GET"])
def keep_alive():
    """Render 免費方案防休眠心跳路由（供 UptimeRobot 等服務每 10~14 分鐘定期呼叫）"""
    return jsonify({
        "status": "alive",
        "service": "Taipei Metro Transfer Optimization Bot",
        "timestamp": get_now_taipei().isoformat()
    }), 200


@app.route("/callback", methods=["POST"])
def callback():
    """LINE Webhook 驗證與分發端點"""
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    logger.info(f"收到 Webhook 請求: 長度 {len(body)}")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("無效的 LINE 數位簽章 (Invalid Signature)，請檢查 CHANNEL_SECRET")
        abort(400)
    except Exception as e:
        logger.error(f"處理 Webhook 訊息時發生未預期錯誤: {e}", exc_info=True)
        abort(500)

    return "OK", 200


# ==========================================
# 訊息事件監聽與業務邏輯
# ==========================================

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event: MessageEvent):
    user_id = event.source.user_id if event.source else "anonymous"
    user_msg = event.message.text.strip()
    reply_token = event.reply_token

    logger.info(f"使用者 [{user_id}] 輸入: {user_msg}")

    # 確保 session 初始化
    if user_id not in user_sessions:
        user_sessions[user_id] = {"from": None, "to": None, "time": None}
    session = user_sessions[user_id]

    # --------------------------------------------------
    # 1. 重新查詢 / 重置狀態
    # --------------------------------------------------
    if user_msg in ["重新查詢", "重置", "清除", "reset", "clear"]:
        user_sessions[user_id] = {"from": None, "to": None, "time": None}
        reply_msg = TextMessage(
            text="🔄 已重置查詢條件。\n請直接輸入起訖站（例如「迴龍 到 士林」或「09:00 迴龍 到 士林」），或點選下方選單「選擇出發站」開始查詢。"
        )
        reply_single_message(reply_token, reply_msg)
        return

    # --------------------------------------------------
    # 2. 說明首頁 / 查詢轉乘 / 說明
    # --------------------------------------------------
    if user_msg in ["查詢轉乘", "說明", "幫助", "help", "開始", "start"]:
        help_bubble = create_help_card_flex()
        reply_msg = FlexMessage(
            alt_text="🚇 台北捷運轉乘時間優化說明",
            contents=FlexContainer.from_dict(help_bubble)
        )
        reply_single_message(reply_token, reply_msg)
        return

    # --------------------------------------------------
    # 3. Quick Reply 互動選單：選擇出發站 / 選擇目的地
    # --------------------------------------------------
    if user_msg == "選擇出發站":
        # 當使用者點擊「選擇出發站」時，自動清空 SQLite 中原本記錄的目的地與自訂時間
        session.update(to=None, time=None)
        reply_msg = TextMessage(
            text="📍 請選擇「出發站」所屬之捷運路線：",
            quick_reply=create_line_selection_quick_reply("from")
        )
        reply_single_message(reply_token, reply_msg)
        return

    if user_msg == "選擇目的地":
        reply_msg = TextMessage(
            text="🎯 請選擇「目的地」所屬之捷運路線：",
            quick_reply=create_line_selection_quick_reply("to")
        )
        reply_single_message(reply_token, reply_msg)
        return

    if user_msg == "指定出發時間":
        reply_msg = TextMessage(
            text="⏰ 請點選下方按鈕開啟日期與時間滾輪，亦可直接輸入時間（如「09:00」或「週一 08:30」）：",
            quick_reply=QuickReply(items=[
                QuickReplyItem(
                    action=DatetimePickerAction(
                        label="⏰ 選擇日期與時間",
                        data="action=set_datetime",
                        mode="datetime"
                    )
                ),
                QuickReplyItem(
                    action=MessageAction(label="⚡ 立即出發", text="設定時間:現在")
                )
            ])
        )
        reply_single_message(reply_token, reply_msg)
        return

    # --------------------------------------------------
    # 4. 點選路線直接回傳「該路線所有車站」水平輪播卡片 (Carousel)
    # 徹底移除「選擇區段」中間步驟，左右滑動直選車站
    # --------------------------------------------------
    if user_msg.startswith("選線:") or user_msg.startswith("選路線:") or user_msg.startswith("選區段:"):
        parts = user_msg.split(":")
        if len(parts) >= 3:
            target_type = parts[1]  # 'from' 或 'to'
            line_code = parts[2].upper()  # 'BL', 'R', 'O', etc.
            line_cfg = LINE_CAROUSEL_CONFIG.get(line_code, {})
            line_name = line_cfg.get("name", line_code)
            type_name = "出發站" if target_type == "from" else "目的地"

            if target_type == "from":
                session.update(to=None, time=None)

            carousel_bubble = create_line_station_carousel_flex(line_code, target_type)
            reply_msg = FlexMessage(
                alt_text=f"📍 請選擇【{line_name}】{type_name}（向右滑動切換車站）",
                contents=FlexContainer.from_dict(carousel_bubble)
            )
            reply_single_message(reply_token, reply_msg)
            return

    # --------------------------------------------------
    # 6. Quick Reply 點選站點確認
    # --------------------------------------------------
    if user_msg.startswith("選站:"):
        parts = user_msg.split(":")
        if len(parts) >= 3:
            target_type = parts[1]
            station_raw = parts[2]
            norm_st = metro_graph.normalize_station_name(station_raw)
            if not norm_st:
                norm_st = station_raw

            if target_type == "from":
                # 設定新的出發站，並自動清空 SQLite 資料庫中原記錄之「目的地」與「自訂時間」
                session.update(**{"from": norm_st, "to": None, "time": None})
                reply_msg = TextMessage(
                    text=f"✅ 已設定出發站：【{norm_st}】\n🎯 請點選下方路線選擇「目的地」（向右滑動直選車站）：",
                    quick_reply=create_line_selection_quick_reply("to")
                )
                reply_single_message(reply_token, reply_msg)
                return
            else:
                session["to"] = norm_st
                # 若出發站已存在，直接計算結果！
                if session.get("from"):
                    execute_and_reply_plan(reply_token, session["from"], session["to"], session.get("time"))
                    return
                else:
                    reply_msg = TextMessage(
                        text=f"✅ 已設定目的地：【{norm_st}】\n📍 請點選下方路線選擇「出發站」（向右滑動直選車站）：",
                        quick_reply=create_line_selection_quick_reply("from")
                    )
                    reply_single_message(reply_token, reply_msg)
                    return

    # --------------------------------------------------
    # 6. Quick Reply 設定出發時間
    # --------------------------------------------------
    if user_msg.startswith("設定時間:"):
        time_val = user_msg.replace("設定時間:", "").strip()
        if time_val == "現在":
            session["time"] = None
        else:
            session["time"] = time_val

        if session.get("from") and session.get("to"):
            execute_and_reply_plan(reply_token, session["from"], session["to"], session.get("time"))
            return
        elif session.get("from") and not session.get("to"):
            reply_msg = TextMessage(
                text=f"⏰ 已設定出發時間：{time_val}。\n出發站為【{session['from']}】，請繼續選擇「目的地」：",
                quick_reply=create_line_selection_quick_reply("to")
            )
            reply_single_message(reply_token, reply_msg)
            return
        else:
            reply_msg = TextMessage(
                text=f"⏰ 已設定出發時間：{time_val}。\n請選擇「出發站」：",
                quick_reply=create_line_selection_quick_reply("from")
            )
            reply_single_message(reply_token, reply_msg)
            return

    # --------------------------------------------------
    # 7. 純文字時間/日期輸入 (例如使用者直接輸入 09:00, 週一 08:30 或 2026-11-23 08:30)
    # --------------------------------------------------
    standalone_dt, clean_remain = extract_datetime_and_clean_text(user_msg)
    if standalone_dt and not clean_remain:
        session["time"] = standalone_dt
        disp_time = standalone_dt
        if "T" in standalone_dt:
            try:
                dt_obj = datetime.datetime.fromisoformat(standalone_dt)
                if dt_obj.tzinfo is None:
                    dt_obj = dt_obj.replace(tzinfo=TAIPEI_TZ)
                wk_name = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"][dt_obj.weekday()]
                is_h, h_desc = is_taiwan_holiday_or_weekend(dt_obj)
                day_kind = h_desc if is_h else "平日"
                disp_time = f"{dt_obj.strftime('%Y-%m-%d %H:%M')}（{wk_name}，{day_kind}班表）"
            except Exception:
                pass
        if session.get("from") and session.get("to"):
            execute_and_reply_plan(reply_token, session["from"], session["to"], session["time"])
            return
        elif session.get("from") and not session.get("to"):
            reply_msg = TextMessage(
                text=f"⏰ 已將出發時間設定為【{disp_time}】。\n出發站為【{session['from']}】，請繼續選擇「目的地」：",
                quick_reply=create_line_selection_quick_reply("to")
            )
            reply_single_message(reply_token, reply_msg)
            return
        else:
            reply_msg = TextMessage(
                text=f"⏰ 已將出發時間設定為【{disp_time}】。\n請接著點擊下方按鈕選擇「出發站」：",
                quick_reply=create_line_selection_quick_reply("from")
            )
            reply_single_message(reply_token, reply_msg)
            return

    # --------------------------------------------------
    # 8. 智慧自然語言比對（例如「迴龍 到 士林」、「09:00 迴龍 到 士林」）
    # --------------------------------------------------
    parsed = parse_query_text(user_msg)
    if parsed:
        raw_from = parsed["origin"]
        raw_to = parsed["destination"]
        parsed_time = parsed.get("time")

        norm_from = metro_graph.normalize_station_name(raw_from)
        norm_to = metro_graph.normalize_station_name(raw_to)

        if not norm_from:
            reply_msg = TextMessage(
                text=f"❌ 查無捷運站點「{raw_from}」，請確認站名是否正確（例如：台北車站、迴龍、士林等）。"
            )
            reply_single_message(reply_token, reply_msg)
            return

        if not norm_to:
            reply_msg = TextMessage(
                text=f"❌ 查無捷運站點「{raw_to}」，請確認站名是否正確。"
            )
            reply_single_message(reply_token, reply_msg)
            return

        if norm_from == norm_to:
            reply_msg = TextMessage(
                text=f"⚠️ 出發站與目的地相同（{norm_from}），請指定不同的車站。"
            )
            reply_single_message(reply_token, reply_msg)
            return

        # 更新 session
        session["from"] = norm_from
        session["to"] = norm_to
        session["time"] = parsed_time

        execute_and_reply_plan(reply_token, norm_from, norm_to, parsed_time)
        return

    # --------------------------------------------------
    # 9. 單站名輸入智慧輔助（例如使用者僅輸入「迴龍」）
    # --------------------------------------------------
    single_st = metro_graph.normalize_station_name(user_msg)
    if single_st:
        if not session.get("from"):
            session.update(**{"from": single_st, "to": None, "time": None})
            reply_msg = TextMessage(
                text=f"📍 已為您設定出發站：【{single_st}】\n🎯 請接著輸入或選擇「目的地」（例如輸入「士林」或點選下方按鈕）：",
                quick_reply=create_line_selection_quick_reply("to")
            )
            reply_single_message(reply_token, reply_msg)
            return
        elif not session.get("to") and session["from"] != single_st:
            session["to"] = single_st
            execute_and_reply_plan(reply_token, session["from"], session["to"], session.get("time"))
            return
        elif session.get("from") and session.get("to"):
            # 重新設定出發站：自動清空舊目的地與自訂時間
            session.update(**{"from": single_st, "to": None, "time": None})
            reply_msg = TextMessage(
                text=f"📍 已更新出發站為：【{single_st}】\n🎯 請接著選擇或輸入目的地：",
                quick_reply=create_line_selection_quick_reply("to")
            )
            reply_single_message(reply_token, reply_msg)
            return

    # --------------------------------------------------
    # 10. 無法識別時之友善指引
    # --------------------------------------------------
    reply_msg = TextMessage(
        text=(
            "🤔 抱歉，未能理解您的指令。\n\n"
            "💡 請嘗試直接輸入：\n"
            "• 「迴龍 到 士林」\n"
            "• 「09:00 迴龍 到 士林」\n"
            "• 「淡水 至 台北車站」\n\n"
            "或點選下方圖文選單按鈕進行操作。"
        )
    )
    reply_single_message(reply_token, reply_msg)


@handler.add(PostbackEvent)
def handle_postback(event: PostbackEvent):
    """處理 LINE 原生滾輪 DatetimePicker 等 Postback 互動事件"""
    user_id = event.source.user_id if event.source else "anonymous"
    data = event.postback.data
    params = event.postback.params or {}
    reply_token = event.reply_token

    logger.info(f"使用者 [{user_id}] 觸發 Postback: data={data}, params={params}")

    if user_id not in user_sessions:
        user_sessions[user_id] = {"from": None, "to": None, "time": None}
    session = user_sessions[user_id]

    # 原生滾輪日期/時間選擇器回傳 (mode='datetime' 時 params 為 {'datetime': 'YYYY-MM-DDTHH:MM'}, mode='time' 時為 {'time': 'HH:MM'})
    if "action=set_datetime" in data or "action=set_time" in data:
        chosen_time = params.get("datetime") or params.get("time")
        if chosen_time:
            session["time"] = chosen_time

            # 友善文字呈現
            disp_str = chosen_time
            if "T" in chosen_time:
                try:
                    dt = datetime.datetime.fromisoformat(chosen_time)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=TAIPEI_TZ)
                    wk_name = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"][dt.weekday()]
                    is_h, h_desc = is_taiwan_holiday_or_weekend(dt)
                    day_kind = h_desc if is_h else "平日"
                    disp_str = f"{dt.strftime('%Y-%m-%d %H:%M')}（{wk_name}，{day_kind}班表）"
                except Exception:
                    pass

            # 若已有出發站與目的地，直接重新精算並回傳全新轉乘卡片！
            if session.get("from") and session.get("to"):
                execute_and_reply_plan(reply_token, session["from"], session["to"], chosen_time)
                return
            elif session.get("from") and not session.get("to"):
                reply_msg = TextMessage(
                    text=f"⏰ 已設定出發時間：【{disp_str}】。\n出發站為【{session['from']}】，請繼續選擇「目的地」：",
                    quick_reply=create_line_selection_quick_reply("to")
                )
                reply_single_message(reply_token, reply_msg)
                return
            else:
                reply_msg = TextMessage(
                    text=f"⏰ 已設定出發時間：【{disp_str}】。\n請點選下方按鈕選擇「出發站」：",
                    quick_reply=create_line_selection_quick_reply("from")
                )
                reply_single_message(reply_token, reply_msg)
                return


def execute_and_reply_plan(reply_token: str, origin: str, dest: str, time_str: Optional[str] = None):
    """計算最佳轉乘方案並以 Flex Message 模板回傳"""
    try:
        plan = ScheduleOptimizer.calculate_transfer_plan(origin, dest, time_str)
        if not plan:
            reply_msg = TextMessage(
                text=f"⚠️ 無法為您規劃從【{origin}】至【{dest}】之捷運路線，請確認車站是否有連通。"
            )
            reply_single_message(reply_token, reply_msg)
            return

        flex_bubble = create_transfer_result_flex(plan)
        alt_text = f"🚇 {plan['arr_time']} 抵達{dest}（{origin}➔{dest}）"

        reply_msg = FlexMessage(
            alt_text=alt_text,
            contents=FlexContainer.from_dict(flex_bubble)
        )
        reply_single_message(reply_token, reply_msg)

    except Exception as e:
        logger.error(f"規劃路線失敗: {e}", exc_info=True)
        reply_msg = TextMessage(
            text="⚠️ 系統規劃轉乘時發生異常，請稍候重試或點擊選單「重新查詢」。"
        )
        reply_single_message(reply_token, reply_msg)


# ==========================================
# 程式進入點
# ==========================================

if __name__ == "__main__":
    logger.info(f"🚀 台北捷運轉乘時間優化 LINE Bot 啟動中，監聽連接埠: {PORT}...")
    app.run(host="0.0.0.0", port=PORT, debug=False)
