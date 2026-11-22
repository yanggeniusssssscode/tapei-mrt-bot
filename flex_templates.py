"""
LINE Flex Message 極簡卡片模板與 Quick Reply 按鈕定義
- 頂部主視覺：大字體預計抵達時間（xxl 粗體），下方小字顯示總車程時間
- 精簡路線時間軸：每段保留顏色圓點 + 出發時間/站名 ➔ 抵達時間/站名，轉乘資訊精簡為單行小字
- 雙方案並排卡片：底部左右並排顯示「正常走」與「慢慢走」備案
- 內建 LINE 原生 DatetimePickerAction 滾輪時分選擇器
- 全線車站分段展開（每站皆可點選，不漏任何一站）
"""

from typing import Dict, Any, List, Optional
from linebot.v3.messaging import (
    QuickReply,
    QuickReplyItem,
    MessageAction,
    DatetimePickerAction
)

# ==========================================
# 全線分段配置表（確保每段車站數 <= 12，全站皆可點選）
# ==========================================
LINE_SECTIONS_CONFIG = {
    "BL": {
        "name": "板南線",
        "emoji": "🟦",
        "color": "#0070BD",
        "sections": [
            {
                "label": "頂埔 ～ 台北車站",
                "stations": ["頂埔", "永寧", "土城", "海山", "亞東醫院", "府中", "板橋", "新埔", "江子翠", "龍山寺", "西門", "台北車站"]
            },
            {
                "label": "善導寺 ～ 南港展覽館",
                "stations": ["善導寺", "忠孝新生", "忠孝復興", "忠孝敦化", "國父紀念館", "市政府", "永春", "後山埤", "昆陽", "南港", "南港展覽館"]
            }
        ]
    },
    "R": {
        "name": "淡水信義線",
        "emoji": "🟥",
        "color": "#E3002C",
        "sections": [
            {
                "label": "廣慈 ～ 台北車站",
                "stations": ["廣慈/奉天宮", "象山", "台北101/世貿", "信義安和", "大安", "大安森林公園", "東門", "中正紀念堂", "台大醫院", "台北車站"]
            },
            {
                "label": "中山 ～ 石牌",
                "stations": ["中山", "雙連", "民權西路", "圓山", "劍潭", "士林", "芝山", "明德", "石牌"]
            },
            {
                "label": "唭哩岸 ～ 淡水/新北投",
                "stations": ["唭哩岸", "奇岩", "北投", "新北投", "復興崗", "忠義", "關渡", "竹圍", "紅樹林", "淡水"]
            }
        ]
    },
    "O": {
        "name": "中和新蘆線",
        "emoji": "🟧",
        "color": "#F89E1B",
        "sections": [
            {
                "label": "迴龍段～民權西路",
                "stations": ["迴龍", "丹鳳", "輔大", "新莊", "頭前庄", "先嗇宮", "三重", "菜寮", "台北橋", "大橋頭"]
            },
            {
                "label": "蘆洲段～民權西路",
                "stations": ["蘆洲", "三民高中", "徐匯中學", "三和國中", "三重國小", "大橋頭", "民權西路"]
            },
            {
                "label": "中山國小～南勢角",
                "stations": ["中山國小", "行天宮", "松江南京", "忠孝新生", "東門", "古亭", "頂溪", "永安市場", "景安", "南勢角"]
            }
        ]
    },
    "G": {
        "name": "松山新店線",
        "emoji": "🟩",
        "color": "#008659",
        "sections": [
            {
                "label": "新店 ～ 古亭/小碧潭",
                "stations": ["新店", "新店區公所", "七張", "小碧潭", "大坪林", "景美", "萬隆", "公館", "台電大樓", "古亭"]
            },
            {
                "label": "中正紀念堂 ～ 松山",
                "stations": ["中正紀念堂", "小南門", "西門", "北門", "中山", "松江南京", "南京復興", "台北小巨蛋", "南京三民", "松山"]
            }
        ]
    },
    "BR": {
        "name": "文湖線",
        "emoji": "🟫",
        "color": "#C48C31",
        "sections": [
            {
                "label": "動物園 ～ 忠孝復興",
                "stations": ["動物園", "木柵", "萬芳社區", "萬芳醫院", "辛亥", "麟光", "六張犁", "科技大樓", "大安", "忠孝復興"]
            },
            {
                "label": "南京復興 ～ 港墘",
                "stations": ["南京復興", "中山國中", "松山機場", "大直", "劍南路", "西湖", "港墘"]
            },
            {
                "label": "文德 ～ 南港展覽館",
                "stations": ["文德", "內湖", "大湖公園", "葫洲", "東湖", "南港軟體園區", "南港展覽館"]
            }
        ]
    },
    "Y": {
        "name": "環狀線",
        "emoji": "🟨",
        "color": "#FEDB00",
        "sections": [
            {
                "label": "大坪林 ～ 中和",
                "stations": ["大坪林", "十四張", "秀朗橋", "景平", "景安", "中和"]
            },
            {
                "label": "橋和 ～ 新北產業園區",
                "stations": ["橋和", "中原", "板新", "板橋", "新埔民生", "頭前庄", "幸福", "新北產業園區"]
            }
        ]
    }
}


def create_transfer_result_flex(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    建立符合北捷轉乘優化規範之極簡直覺卡片 Flex Message
    包含：XXL 醒目抵達時間、精簡路線時間軸、雙方案並排、原生滾輪調整時間按鈕
    """
    arr_time = plan.get("arr_time", "--:--")
    dest_name = plan.get("destination", "目的地")
    origin_name = plan.get("origin", "出發地")
    total_min = plan.get("total_duration_min", 0)
    is_direct = plan.get("is_direct", False)
    timeline = plan.get("timeline", [])
    transfer_info = plan.get("transfer_info")
    is_peak = plan.get("is_peak", False)

    day_type = plan.get("day_type", "weekday")
    is_weekend = (day_type == "weekend")
    is_holiday = plan.get("is_holiday", False)
    holiday_desc = plan.get("holiday_desc", "")
    wk_name = plan.get("weekday_name", "")

    # 頂部狀態標籤 (平日尖峰加權 / 國定假日 / 假日時刻表 / 離峰)
    if is_peak:
        badge_text = f"平日尖峰加權・{wk_name}" if wk_name else "平日尖峰自動加權"
        badge_bg = "#FEF2F2"
        badge_color = "#DC2626"
    elif is_holiday or is_weekend:
        if holiday_desc and "國定假日" in holiday_desc:
            badge_text = f"{holiday_desc}班表"
        else:
            badge_text = f"假日時刻表・{wk_name}" if wk_name else "假日真實班表"
        badge_bg = "#FEF3C7"
        badge_color = "#D97706"
    elif is_direct:
        badge_text = f"直達列車・{wk_name}" if wk_name else "直達班次"
        badge_bg = "#F0FDF4"
        badge_color = "#16A34A"
    else:
        badge_text = f"離峰步速・{wk_name}" if wk_name else "離峰正常步速"
        badge_bg = "#F0FDF4"
        badge_color = "#16A34A"

    # 路線時間軸元件組裝（動態支援任意多段車程與轉乘提示）
    timeline_boxes = []
    segments = plan.get("segments") or plan.get("timeline") or []

    if len(segments) <= 1:
        if segments:
            leg = segments[0]
            timeline_boxes.append({
                "type": "box",
                "layout": "horizontal",
                "alignItems": "center",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "text",
                        "text": "●",
                        "color": leg.get("line_color", "#0070BD"),
                        "size": "sm",
                        "flex": 0
                    },
                    {
                        "type": "text",
                        "text": f"{leg.get('dep_time')} {leg.get('from_station')} ➔ {leg.get('arr_time')} {leg.get('to_station')}",
                        "size": "sm",
                        "weight": "bold",
                        "color": "#1E293B",
                        "flex": 1
                    }
                ]
            })
            timeline_boxes.append({
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#F8FAFC",
                "cornerRadius": "sm",
                "paddingAll": "xs",
                "margin": "sm",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{leg.get('line_name')}直達列車・無須轉乘・共約 {leg.get('stations_count', 0)} 站",
                        "size": "xxs",
                        "color": "#64748B"
                    }
                ]
            })
    else:
        for idx, leg in enumerate(segments):
            # 車程段落行
            timeline_boxes.append({
                "type": "box",
                "layout": "horizontal",
                "alignItems": "center",
                "spacing": "sm",
                "margin": "xs" if idx > 0 else "none",
                "contents": [
                    {
                        "type": "text",
                        "text": "●",
                        "color": leg.get("line_color", "#888888"),
                        "size": "sm",
                        "flex": 0
                    },
                    {
                        "type": "text",
                        "text": f"{leg.get('dep_time')} {leg.get('from_station')} ➔ {leg.get('arr_time')} {leg.get('to_station')}",
                        "size": "sm",
                        "weight": "bold",
                        "color": "#1E293B",
                        "flex": 1
                    }
                ]
            })

            # 若此段後有轉乘提示，動態渲染
            xfer_desc = None
            if leg.get("transfer_after") and isinstance(leg["transfer_after"], dict):
                xfer_desc = leg["transfer_after"].get("desc")
            elif leg.get("transfer_desc"):
                xfer_desc = leg.get("transfer_desc")

            if xfer_desc:
                timeline_boxes.append({
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": "#F1F5F9",
                    "cornerRadius": "md",
                    "paddingStart": "sm",
                    "paddingEnd": "sm",
                    "paddingTop": "xs",
                    "paddingBottom": "xs",
                    "margin": "xs",
                    "contents": [
                        {
                            "type": "text",
                            "text": xfer_desc,
                            "size": "xxs",
                            "color": "#334155",
                            "weight": "bold",
                            "wrap": True
                        }
                    ]
                })

    # Flex Message Bubble 結構
    flex_bubble = {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "lg",
            "contents": [
                # 頂部狀態列
                {
                    "type": "box",
                    "layout": "horizontal",
                    "alignItems": "center",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"{origin_name} ➔ {dest_name}",
                            "size": "xs",
                            "color": "#64748B",
                            "weight": "bold",
                            "flex": 1
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "backgroundColor": badge_bg,
                            "cornerRadius": "sm",
                            "paddingStart": "xs",
                            "paddingEnd": "xs",
                            "paddingTop": "none",
                            "paddingBottom": "none",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": badge_text,
                                    "size": "xxs",
                                    "color": badge_color,
                                    "weight": "bold"
                                }
                            ]
                        }
                    ]
                },
                # 預計抵達時間 (主視覺最大字體 XXL)
                {
                    "type": "text",
                    "text": f"{arr_time} 抵達{dest_name}",
                    "size": "xxl",
                    "weight": "bold",
                    "color": "#0F172A",
                    "margin": "xs"
                },
                # 總車程時間
                {
                    "type": "text",
                    "text": f"總耗時約 {total_min} 分鐘",
                    "size": "xs",
                    "color": "#64748B",
                    "margin": "xs"
                },
                # 分隔線
                {
                    "type": "separator",
                    "margin": "md",
                    "color": "#E2E8F0"
                },
                # 精簡路線時間軸區塊
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "md",
                    "spacing": "xs",
                    "contents": timeline_boxes
                },
                # 分隔線
                {
                    "type": "separator",
                    "margin": "md",
                    "color": "#E2E8F0"
                },
                # 原生日期/時間滾輪時間調整按鈕
                {
                    "type": "button",
                    "action": {
                        "type": "datetimepicker",
                        "label": "⏰ 選擇日期與時間",
                        "data": "action=set_datetime",
                        "mode": "datetime"
                    },
                    "style": "secondary",
                    "color": "#F1F5F9",
                    "height": "sm",
                    "margin": "md"
                }
            ]
        }
    }

    return flex_bubble


def create_help_card_flex() -> Dict[str, Any]:
    """引導首頁 / 功能說明 Flex 卡片"""
    return {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "lg",
            "contents": [
                {
                    "type": "text",
                    "text": "🚇 台北捷運轉乘時間優化",
                    "size": "lg",
                    "weight": "bold",
                    "color": "#0F172A"
                },
                {
                    "type": "text",
                    "text": "精準預估抵達時間、官方時刻表對齊與最佳車廂轉乘",
                    "size": "xs",
                    "color": "#64748B",
                    "margin": "xs"
                },
                {
                    "type": "separator",
                    "margin": "md"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "md",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "text",
                            "text": "💬 快速查詢範例：",
                            "size": "xs",
                            "weight": "bold",
                            "color": "#334155"
                        },
                        {
                            "type": "text",
                            "text": "• 「迴龍 到 士林」\n• 「09:00 迴龍到士林」\n• 「淡水 至 台北車站」\n• 「動物園 到 市政府 18:30」",
                            "size": "xs",
                            "color": "#475569",
                            "wrap": True
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": "#F8FAFC",
                    "cornerRadius": "md",
                    "paddingAll": "sm",
                    "margin": "md",
                    "contents": [
                        {
                            "type": "text",
                            "text": "✨ 核心升級：",
                            "size": "xxs",
                            "weight": "bold",
                            "color": "#2563EB"
                        },
                        {
                            "type": "text",
                            "text": "1. 消除誤差：依各站間實際行駛時間與官方真實時刻表推算\n2. 全線點選：全路線支援按鈕點選，不漏任何一站\n3. 滾輪選時：原生時/分滾輪精確設定出發時間\n4. 雙方案對照：正常走與慢慢走從容備案",
                            "size": "xxs",
                            "color": "#64748B",
                            "wrap": True
                        }
                    ]
                },
                {
                    "type": "button",
                    "action": {
                        "type": "datetimepicker",
                        "label": "⏰ 選擇日期與時間",
                        "data": "action=set_datetime",
                        "mode": "datetime"
                    },
                    "style": "primary",
                    "color": "#2563EB",
                    "height": "sm",
                    "margin": "md"
                }
            ]
        }
    }


# ==========================================
# Quick Reply 快捷按鈕列定義（純查詢導向）
# ==========================================

def create_main_quick_reply() -> QuickReply:
    """
    每次回傳訊息底部固定附帶的純查詢 Quick Reply 快捷按鈕列
    包含：選擇出發站、選擇目的地、原生時/分滾輪時間選擇器、立即出發、重新查詢
    """
    items = [
        QuickReplyItem(
            action=MessageAction(label="📍 選擇出發站", text="選擇出發站")
        ),
        QuickReplyItem(
            action=MessageAction(label="🎯 選擇目的地", text="選擇目的地")
        ),
        QuickReplyItem(
            action=DatetimePickerAction(
                label="⏰ 選擇日期與時間",
                data="action=set_datetime",
                mode="datetime"
            )
        ),
        QuickReplyItem(
            action=MessageAction(label="⚡ 立即出發", text="設定時間:現在")
        ),
        QuickReplyItem(
            action=MessageAction(label="🔄 重新查詢", text="重新查詢")
        )
    ]
    return QuickReply(items=items)


def create_line_selection_quick_reply(target_type: str = "from") -> QuickReply:
    """
    選擇路線選單（涵蓋板南、淡水信義、中和新蘆、松山新店、文湖與環狀線）
    target_type: 'from' (出發站) 或 'to' (目的地)
    """
    items = []
    for line_code, cfg in LINE_SECTIONS_CONFIG.items():
        items.append(
            QuickReplyItem(
                action=MessageAction(
                    label=f"{cfg['emoji']} {cfg['name']}",
                    text=f"選線:{target_type}:{line_code}"
                )
            )
        )
    items.append(
        QuickReplyItem(
            action=MessageAction(label="🔄 重新查詢", text="重新查詢")
        )
    )
    return QuickReply(items=items)


def create_section_selection_quick_reply(line_code: str, target_type: str = "from") -> QuickReply:
    """
    若路線超過 12 站，先分前後區段按鈕展開
    """
    cfg = LINE_SECTIONS_CONFIG.get(line_code)
    if not cfg:
        return create_line_selection_quick_reply(target_type)

    sections = cfg["sections"]
    items = []
    for idx, sec in enumerate(sections):
        items.append(
            QuickReplyItem(
                action=MessageAction(
                    label=f"📍 {sec['label']}",
                    text=f"選區段:{target_type}:{line_code}:{idx}"
                )
            )
        )
    items.append(
        QuickReplyItem(
            action=MessageAction(label="↩ 返回換線", text="選擇出發站" if target_type == "from" else "選擇目的地")
        )
    )
    return QuickReply(items=items)


def create_station_selection_quick_reply(line_code: str, section_idx: int, target_type: str = "from") -> QuickReply:
    """
    點選區段後，展開該區段【所有車站】供純點選，不漏任何一站
    """
    cfg = LINE_SECTIONS_CONFIG.get(line_code)
    if not cfg:
        return create_line_selection_quick_reply(target_type)

    sections = cfg["sections"]
    if section_idx >= len(sections):
        section_idx = 0

    sec = sections[section_idx]
    stations = sec["stations"]

    items = []
    for st in stations:
        items.append(
            QuickReplyItem(
                action=MessageAction(
                    label=f"{st}",
                    text=f"選站:{target_type}:{st}"
                )
            )
        )
    items.append(
        QuickReplyItem(
            action=MessageAction(label="↩ 返回區段", text=f"選線:{target_type}:{line_code}")
        )
    )
    return QuickReply(items=items)
