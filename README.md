# 📊 開放資料 CSV 瀏覽器(PWA + RWD)

以 Gradio 製作的 CSV 瀏覽工具,預設載入台灣證券交易所開放資料,也可輸入任意 CSV 連結。
支援 **PWA**(可安裝到手機/桌面主畫面)與 **RWD**(手機、平板、桌機自適應)。

## 功能

- 輸入 CSV 連結並載入(`utf-8-sig`,繁體中文不亂碼)
- 可選擇是否移除含空值的列(`dropna`)
- 全欄位關鍵字搜尋、自選顯示欄位、統計摘要
- 下載目前結果(CSV,Excel 開啟不亂碼)
- PWA:Web App Manifest、Service Worker、離線提示頁、可安裝
- RWD:手機直向堆疊、觸控按鈕(最小 44px)、安全區域適配、表格可橫向捲動

## 專案結構

```
.
├── app.py                      # FastAPI + Gradio 主程式
├── static/
│   ├── manifest.webmanifest    # PWA 設定
│   ├── sw.js                   # Service Worker
│   ├── offline.html            # 離線頁
│   └── icons/                  # 192 / 512 / maskable / apple-touch
├── tools/make_icons.py         # 重新產生圖示(選用,需 Pillow)
├── requirements.txt
├── render.yaml                 # Render Blueprint(選用)
├── .python-version
└── README.md
```

## 本機執行

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

開啟 http://localhost:7860 (`localhost` 被瀏覽器視為安全來源,可測試 Service Worker)。

## 部署到 Render

1. 推上 GitHub:
   ```bash
   git init && git add . && git commit -m "init"
   git branch -M main
   git remote add origin https://github.com/<帳號>/<repo>.git
   git push -u origin main
   ```
2. Render → **New +** → **Web Service** → 選擇該 repo。
3. 設定:

   | 欄位 | 值 |
   |---|---|
   | Runtime | Python 3 |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `python app.py` |
   | Health Check Path | `/healthz` |
   | Instance Type | Free |

   (或選 **Blueprint**,自動讀取 `render.yaml`。)
4. 部署完成後,Render 提供的 `https://xxx.onrender.com` 即為 PWA 網址(PWA 需要 HTTPS,Render 預設提供)。

## 安裝成 App

- **Android / Chrome**:開啟網址 → 選單 → 「安裝應用程式」。
- **iPhone / Safari**:分享 → 「加入主畫面」。
- **桌機 Chrome / Edge**:網址列右側的安裝圖示。

## 驗證 PWA

Chrome 開發者工具 → **Application** 頁籤,檢查 Manifest 與 Service Worker;或用 **Lighthouse** 的 PWA 項目。

## 注意事項

- 修改 `static/` 內的快取資源後,請調高 `static/sw.js` 的 `VERSION`,使用者端才會更新。
- Service Worker 只快取離線頁與圖示;資料請求一律走網路,所以**離線時無法載入 CSV**,只會顯示離線提示頁。
- 免費方案閒置會休眠,下次開啟需等待約 30–60 秒。
- 為了相容部分政府網站憑證問題使用了 `verify=False`;若來源憑證正常,建議移除。
