# 🚇 台北捷運轉乘時間優化 LINE Bot (TRTC Transfer Optimizer)

這是一個專為台北捷運通勤族設計的 LINE 官方帳號機器人，採用 **Python + Flask** 開發，整合 **TDX 運輸資料流通服務 API**、**文湖線專屬班距推算**、**平日尖峰轉乘加權** 與 **極簡直覺 LINE Flex Message**，協助使用者快速掌握最佳抵達時間與從容備案！

---

## ✨ 核心特色

1. **極簡直覺卡片 (LINE Flex Message)**：
   - **頂部主視覺**：以 XXL 粗體醒目展示「預計抵達時間（例如：`09:38 抵達士林`）」，下方輔以總車程時間，一眼看懂！
   - **精簡路線時間軸**：去除多餘贅字，每段僅保留路線代表色圓點與「出發時間/站名 ➔ 抵達時間/站名」，轉乘資訊精簡為單行小字（如：`民權西路站轉乘・步行約 3 分鐘・建議第 5 車廂`）。
   - **雙方案並排卡片**：底部左右並排顯示「正常走（最快銜接班次）」與「慢慢走（預留 2~3 分鐘緩衝的從容備案）」，不附帶任何多餘按鈕。
   - **卡片內建滾輪調時按鈕**：卡片內直接嵌入原生時/分滾輪時間選擇按鈕，一鍵調整時間。
2. **純查詢導向 Quick Reply 快捷按鈕列**：
   - 每次回傳訊息底部固定附帶：`📍 選擇出發站`、`🎯 選擇目的地`、`⏰ 滾輪選擇時間`、`⚡ 立即出發`、`🔄 重新查詢`。
   - **全線車站純按鈕點選（不漏任何一站）**：採用「選路線 ➔ 區段分組（如迴龍段～民權西路、蘆洲段～民權西路、中山國小～南勢角）➔ 該區段所有車站」流程，完整涵蓋北捷六大路線所有站點，包含三重、新莊、先嗇宮等每一站皆可免打字點擊。
   - **LINE 原生時/分滾輪選擇器 (`DatetimePickerAction`)**：支援在手機滑出原生時間滾輪轉動「小時」與「分鐘」，點選確定後立即更新時間並重新計算轉乘卡片。
3. **混合式高精度轉乘優化演算法 (`mrt_engine.py`)**：
   - **消除 1~2 分鐘時刻表誤差**：內建台北捷運官方精準站間行駛時間表（如民權西路至士林 7.0 分鐘、迴龍至民權西路 25.0 分鐘）與真實離站時刻（紅線尖峰 3 分鐘如 09:13、09:16、09:19 等）。
   - **高運量路線（板南、淡水信義、中和新蘆、松山新店、環狀線）**：優先串接 TDX 站別時刻表 (StationTimeTable)；若網路異常或無金鑰，自動切換至官方精確離線時刻表推算 Fallback。
   - **文湖線（棕線）專屬處理**：自動套用官方公告時段班距（平日尖峰 2~2.5 分、離峰/假日 4~5 分、深夜 10~12 分）。
   - **轉乘步行緩衝與尖峰加權**：內建台北各大轉乘站基準步行時間（如台北車站/忠孝復興 4 分鐘、民權西路/忠孝新生 3 分鐘、西門/東門 1 分鐘、板橋站外轉乘 8 分鐘等），於平日上下班尖峰時段自動加權 +1 分鐘，並附上省時車廂推薦。

---

## 📁 專案目錄結構

```text
MRT_Bot/
├── app.py              # Flask 主伺服器與 LINE Webhook 端點 (/callback)
├── mrt_engine.py       # 北捷全路網資料、混合時刻表推算與轉乘優化核心邏輯
├── flex_templates.py   # LINE Flex Message 極簡卡片模板與 Quick Reply 按鈕定義
├── requirements.txt    # 專案依賴套件清單 (Flask, line-bot-sdk, python-dotenv 等)
├── .env                # 實際環境變數設定檔（已內建金鑰，切勿提交至公開 Git）
├── .env.example        # 環境變數範本檔
├── .gitignore          # Git 版本控制排除設定
└── README.md           # 專案完整操作與部署指南
```

---

## 🚀 快速上手教學

### 步驟 1：安裝相依套件

請確保系統已安裝 Python 3.9+，並在專案根目錄執行以下指令：

```bash
pip install -r requirements.txt
```

### 步驟 2：確認環境變數檔 (`.env`)

專案根目錄下需有名為 `.env` 的設定檔：

```env
# LINE Messaging API 設定
LINE_CHANNEL_SECRET=a97061d663d8dea382b08925e3dcc6f8
LINE_CHANNEL_ACCESS_TOKEN=3Hcmg3n46aNn9I6ZWWVndT+yCR6SnMck8PAyH7DGMdBqvqzqiYJnAhe7Hz+XfESmsJQ6HHl5m/eRfr8WESoZjin6onZiqYDEW4U8PuUEM2vZPftm06PZQREo2KrPNUySovw+btptHqEPedr0vznDAwdB04t89/1O/w1cDnyilFU=

# TDX 運輸資料流通服務 API 金鑰
TDX_CLIENT_ID=821e2619925bf489eb68cc381cc3c586
TDX_CLIENT_SECRET=e6f9ca98-bf13-4ebf-826c-bd7ba6499608

# Flask 服務埠號
PORT=5000
```

### 步驟 3：啟動本地伺服器

執行主程式啟動 Flask：

```bash
python app.py
```

當終端機顯示以下資訊即代表啟動成功：
```text
 * Running on http://127.0.0.1:5000
 * Running on http://<區域網路IP>:5000
```

可開啟瀏覽器訪問 `http://127.0.0.1:5000/`，若看到 `{"status":"healthy","service":"Taipei Metro Transfer Optimization Bot"}` 表示伺服器運行正常。

---

## 🌐 透過 ngrok 進行外部公開測試

由於 LINE 伺服器必須透過公開的 HTTPS 網址發送 Webhook 請求，本地端測試需使用 [ngrok](https://ngrok.com/) 穿透內網：

1. **啟動 ngrok 轉發**：
   開啟另一個終端機視窗，輸入：
   ```bash
   ngrok http 5000
   ```

2. **複製 HTTPS 轉發網址**：
   終端機會顯示類似如下資訊：
   ```text
   Forwarding   https://xxxx-xx-xx-xx-xx.ngrok-free.app -> http://localhost:5000
   ```
   請複製 `https://xxxx-xx-xx-xx-xx.ngrok-free.app` 這個 HTTPS 網址。

---

## 📲 LINE Developers 後台 Webhook 設定步驟

1. 登入 [LINE Developers Console](https://developers.line.biz/console/)。
2. 進入您的 Provider ➜ 點選剛才建立的 **Messaging API Channel**。
3. 切換至 **Messaging API** 分頁：
   - 滾動至 **Webhook settings**：
   - **Webhook URL**：填入剛才 ngrok 產生的網址加上 `/callback`，例如：
     ```text
     https://xxxx-xx-xx-xx-xx.ngrok-free.app/callback
     ```
   - 點擊 **Update** 儲存。
   - 點擊 **Verify** 按鈕進行驗證，看到綠色 `Success` 即表示連線成功！
   - 開啟 **Use webhook** 開關（轉為綠色開啟狀態）。
4. **關閉官方自動回覆訊息（重要）**：
   - 在同頁面點選「LINE Official Account features」下的「Auto-reply messages (Edit)」。
   - 進入 LINE Official Account Manager 後台：
     - **回應模式**：選擇「聊天室 (Bot)」。
     - **自動回應訊息**：設為「關閉 (Disabled)」。
     - **Webhook**：設為「開啟 (Enabled)」。
   - 這樣可避免官方預設的「感謝加入好友」等訊息與 Bot 自定義訊息重疊干擾。

---

## 💬 測試互動與操作指令範例

加入該 LINE Bot 好友後，可直接在對話框進行測試：

| 查詢情境 | 輸入範例 | Bot 運作說明 |
| :--- | :--- | :--- |
| **即時轉乘查詢** | `迴龍 到 士林` | 立即計算最近一班從迴龍出發的班次，並給出民權西路最佳銜接班次 |
| **指定時間查詢** | `09:00 迴龍 到 士林` | 預設以 09:00 起算發車，平日早尖峰自動加權站內轉乘步速 |
| **直達車查詢** | `板橋 到 台北車站` | 判定為板南線直達，免轉乘，並同時列出正常班次與下一班備案 |
| **文湖線起訖** | `動物園 到 市政府 18:30` | 啟用文湖線專屬班距推算，於忠孝復興轉乘板南線並附上車廂指引 |
| **免打字快捷引導** | 點選 `選擇出發站` | 展開六大路線按鈕，點擊後展開主要轉乘樞紐，免打字點擊即可完成查詢 |
| **重置條件** | 點選 `重新查詢` | 清空當前暫存狀態，恢復至初始查詢引導 |

---

## ☁️ 部署至 Render 雲端平台指南

本專案已內建 `Procfile`、`gunicorn`、`runtime.txt` 與防休眠心跳路由 `/keep-alive`，可極速部署至 Render：

### 1. 推送程式碼至 GitHub
```bash
git init
git add .
git commit -m "feat: complete mrt line bot with timetable and render deployment"
git branch -M main
git remote add origin <您的 GitHub 儲存庫網址>
git push -u origin main
```

### 2. 在 Render 建立 Web Service
1. 登入 [Render Dashboard](https://dashboard.render.com/)，點擊 **New +** ➜ 選擇 **Web Service**。
2. 連結剛才推送的 GitHub Repository。
3. 設定參數：
   - **Name**：`mrt-line-bot`（或自訂）
   - **Region**：`Singapore`（連線台灣延遲最低）
   - **Branch**：`main`
   - **Runtime**：`Python 3`
   - **Build Command**：`pip install -r requirements.txt`
   - **Start Command**：`gunicorn app:app --workers 2 --threads 4 --timeout 120`（亦會自動讀取 Procfile）
   - **Instance Type**：`Free`
4. 設定 **Environment Variables**（環境變數）：
   - `LINE_CHANNEL_SECRET`：填入 LINE 頻道密鑰
   - `LINE_CHANNEL_ACCESS_TOKEN`：填入 LINE 長效 Token
   - `PYTHON_VERSION`：`3.11.9`
5. 點擊 **Create Web Service**，等待建置完成取得專屬網址（例如 `https://mrt-line-bot.onrender.com`）。

### 3. 更新 LINE Developers Webhook URL
將 Webhook URL 更新為：
```text
https://<您的-render-app-名稱>.onrender.com/callback
```
點擊 **Verify**，顯示 `Success` 即完成上線！

### 4. 設定防休眠（防止 Render 免費版 15 分鐘休眠）
前往 [UptimeRobot](https://uptimerobot.com/)（免費）：
- 建立一個 **HTTP(s) Monitor**
- URL 填入：`https://<您的-render-app-名稱>.onrender.com/keep-alive`
- 間隔設為：`10 分鐘` 或 `14 分鐘`
即可確保機器人 24 小時秒回、永不休眠！

---

## 🛡️ 安全注意事項

- 本專案已將 `.env` 列入 `.gitignore`，請勿將包含真實金鑰的 `.env` 上傳至 GitHub 等公開儲存庫。
- 若更換金鑰或部署至雲端伺服器（如 Render, Railway, Fly.io, GCP, AWS），請在該平台環境變數設定後直接啟動。
