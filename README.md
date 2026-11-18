# 開放資料 CSV 瀏覽器(PWA + RWD,單檔版)

只需要 `app.py` 與 `requirements.txt` 兩個檔案即可部署。
PWA 的 manifest、Service Worker、離線頁都內嵌在 `app.py`,圖示於啟動時自動產生。

## Render 部署

- Build Command:`pip install -r requirements.txt`
- Start Command:`python app.py`
- Environment:`PYTHON_VERSION = 3.11.9`
- Health Check Path:`/healthz`(選填)

部署後以 `https://xxx.onrender.com` 開啟,即可在瀏覽器「安裝應用程式」/「加入主畫面」。
