"""開放資料 CSV 瀏覽器 —— Gradio + FastAPI,支援 PWA 與 RWD(單檔版,不需 static 資料夾)"""
import io
import os
import tempfile

import gradio as gr
import pandas as pd
import requests
import urllib3
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, Response
from PIL import Image, ImageDraw

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_URL = "https://mopsfin.twse.com.tw/opendata/t187ap46_L_1.csv"  # 換連結
THEME_COLOR = "#4f46e5"


# ---------- 核心功能 ----------
def to_csv_file(df: pd.DataFrame):
    """把 DataFrame 存成可下載的 CSV(utf-8-sig,Excel 開啟不會亂碼)"""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", prefix="result_")
    tmp.close()
    df.to_csv(tmp.name, index=False, encoding="utf-8-sig")
    return tmp.name


def load_data(url, drop_na):
    try:
        resp = requests.get(url.strip(), verify=False, timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(io.BytesIO(resp.content), encoding="utf-8-sig")
    except Exception as e:
        return None, f"❌ 載入失敗:{e}", pd.DataFrame(), gr.update(choices=[], value=[]), None

    raw_rows = len(df)
    if drop_na:
        df = df.dropna()

    msg = f"✅ 載入成功:原始 {raw_rows:,} 筆 → 目前 {len(df):,} 筆,共 {df.shape[1]} 個欄位"
    cols = list(df.columns)
    return df, msg, df, gr.update(choices=cols, value=cols), to_csv_file(df)


def filter_data(df, keyword, columns):
    if df is None:
        return pd.DataFrame(), "⚠️ 請先載入資料", None

    view = df[columns] if columns else df
    if keyword and keyword.strip():
        kw = keyword.strip()
        mask = view.astype(str).apply(
            lambda col: col.str.contains(kw, case=False, na=False, regex=False)
        ).any(axis=1)
        view = view[mask]

    return view, f"🔍 顯示 {len(view):,} 筆資料", to_csv_file(view)


def describe_data(df):
    if df is None:
        return pd.DataFrame()
    return df.describe(include="all").T.reset_index().rename(columns={"index": "欄位"})


# ---------- PWA:<head> 設定 ----------
HEAD = f"""
<meta name="theme-color" content="{THEME_COLOR}">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="CSV瀏覽器">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" type="image/png" sizes="192x192" href="/pwa/icons/icon-192.png">
<link rel="apple-touch-icon" href="/pwa/icons/apple-touch-icon.png">
<script>
  if ("serviceWorker" in navigator) {{
    window.addEventListener("load", function () {{
      navigator.serviceWorker.register("/sw.js", {{ scope: "/" }})
        .catch(function (err) {{ console.warn("SW 註冊失敗:", err); }});
    }});
  }}
</script>
"""

# ---------- RWD:自訂 CSS ----------
CSS = """
:root { --tap-size: 44px; }

.gradio-container {
  max-width: 1200px !important;
  margin: 0 auto !important;
  padding-left: max(12px, env(safe-area-inset-left)) !important;
  padding-right: max(12px, env(safe-area-inset-right)) !important;
  padding-bottom: max(12px, env(safe-area-inset-bottom)) !important;
}
footer { display: none !important; }

/* 平板與桌機:列內元素可換行 */
.rwd-row { flex-wrap: wrap !important; gap: 12px !important; }
.rwd-row > * { min-width: 200px; }

/* 觸控友善 */
button, input, textarea { min-height: var(--tap-size); }

/* 手機:直向堆疊、元件滿版 */
@media (max-width: 768px) {
  .gradio-container { padding-top: 8px !important; }
  .rwd-row { flex-direction: column !important; }
  .rwd-row > * { width: 100% !important; min-width: 0 !important; flex: 1 1 auto !important; }
  .app-title h1 { font-size: 1.35rem !important; }
  .app-title p  { font-size: 0.9rem !important; }
  table { font-size: 0.85rem; }
}

/* 超小螢幕 */
@media (max-width: 480px) {
  .app-title h1 { font-size: 1.2rem !important; }
}
"""

# ---------- 介面 ----------
theme = gr.themes.Soft(primary_hue="indigo", secondary_hue="sky")

with gr.Blocks(theme=theme, title="CSV 資料瀏覽器", css=CSS, head=HEAD) as demo:
    state = gr.State(None)

    gr.Markdown(
        """
        # 📊 開放資料 CSV 瀏覽器
        輸入 CSV 連結 → 載入 → 搜尋、挑選欄位 → 下載結果
        """,
        elem_classes="app-title",
    )

    with gr.Row(elem_classes="rwd-row"):
        url_in = gr.Textbox(label="CSV 連結", value=DEFAULT_URL, scale=5)
        drop_na = gr.Checkbox(label="移除含空值的列 (dropna)", value=True, scale=1)
        load_btn = gr.Button("🚀 載入資料", variant="primary", scale=1)

    status = gr.Markdown("尚未載入資料")

    with gr.Tabs():
        with gr.Tab("📋 資料表"):
            with gr.Row(elem_classes="rwd-row"):
                keyword = gr.Textbox(
                    label="關鍵字搜尋(全欄位)", placeholder="例如:2330、台積電…", scale=3
                )
                search_btn = gr.Button("🔍 搜尋", scale=1)
            cols_sel = gr.CheckboxGroup(label="顯示欄位", choices=[], value=[])
            table = gr.Dataframe(interactive=False, wrap=True, max_height=500)
            file_out = gr.File(label="⬇️ 下載目前結果 (CSV)")

        with gr.Tab("📈 統計摘要"):
            stat_btn = gr.Button("產生統計摘要")
            stat_table = gr.Dataframe(interactive=False)

    # 事件綁定
    load_btn.click(
        load_data, [url_in, drop_na],
        [state, status, table, cols_sel, file_out],
    )
    search_btn.click(filter_data, [state, keyword, cols_sel], [table, status, file_out])
    keyword.submit(filter_data, [state, keyword, cols_sel], [table, status, file_out])
    cols_sel.change(filter_data, [state, keyword, cols_sel], [table, status, file_out])
    stat_btn.click(describe_data, state, stat_table)


# ---------- PWA 資源(全部內嵌,不需要 static 資料夾)----------
MANIFEST = {
    "id": "/",
    "name": "開放資料 CSV 瀏覽器",
    "short_name": "CSV瀏覽器",
    "description": "載入開放資料 CSV,搜尋、篩選欄位並下載結果",
    "lang": "zh-TW",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "orientation": "any",
    "background_color": "#ffffff",
    "theme_color": THEME_COLOR,
    "icons": [
        {"src": "/pwa/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "/pwa/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": "/pwa/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
}

# 更新快取內容時,請調高 VERSION
SW_JS = """
const VERSION = "v1";
const CACHE = "csv-viewer-" + VERSION;
const OFFLINE_URL = "/pwa/offline.html";
const PRECACHE = [OFFLINE_URL, "/pwa/icons/icon-192.png", "/pwa/icons/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // 頁面導覽:優先走網路,離線時顯示離線頁
  if (req.mode === "navigate") {
    event.respondWith(fetch(req).catch(() => caches.match(OFFLINE_URL)));
    return;
  }
  // /pwa/ 靜態資源:快取優先;Gradio 的 API 與檔案請求不攔截
  if (url.pathname.startsWith("/pwa/")) {
    event.respondWith(
      caches.match(req).then((hit) =>
        hit || fetch(req).then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
          return res;
        })
      )
    );
  }
});
"""

OFFLINE_HTML = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#4f46e5">
  <title>目前離線</title>
  <style>
    :root { color-scheme: light dark; }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 24px;
      font-family: system-ui, -apple-system, "Noto Sans TC", "Microsoft JhengHei", sans-serif;
      background: #f5f5ff; color: #1f2937; text-align: center; }
    @media (prefers-color-scheme: dark) { body { background: #111827; color: #e5e7eb; } }
    .card { max-width: 420px; width: 100%; }
    img { width: 96px; height: 96px; border-radius: 22px; }
    h1 { font-size: clamp(1.25rem, 5vw, 1.6rem); margin: 16px 0 8px; }
    p { margin: 0 0 24px; line-height: 1.6; opacity: .8; }
    button { min-height: 44px; padding: 0 28px; border: 0; border-radius: 10px;
      background: #4f46e5; color: #fff; font-size: 1rem; cursor: pointer; }
  </style>
</head>
<body>
  <div class="card">
    <img src="/pwa/icons/icon-192.png" alt="">
    <h1>目前沒有網路連線</h1>
    <p>CSV 資料需要連線才能載入。請確認網路後再試一次。</p>
    <button onclick="location.reload()">重新連線</button>
  </div>
</body>
</html>
"""


# ---------- 圖示:啟動時以 Pillow 自動產生 ----------
def _make_icon(size, rounded=True, content_scale=0.62):
    bg, fg, accent = THEME_COLOR, "#ffffff", "#7dd3fc"
    k = 4  # 超取樣,邊緣更平滑
    s = size * k
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if rounded:
        d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=bg)
    else:
        d.rectangle([0, 0, s, s], fill=bg)

    c = s * content_scale
    y0 = (s - c) / 2
    bar_w, gap = c * 0.22, c * 0.09
    total = 3 * bar_w + 2 * gap
    x = (s - total) / 2
    base = y0 + c * 0.88
    for h, color in zip((0.45, 0.78, 0.6), (fg, accent, fg)):
        d.rounded_rectangle([x, base - c * h, x + bar_w, base], radius=bar_w * 0.25, fill=color)
        x += bar_w + gap
    d.rounded_rectangle(
        [(s - total) / 2 - gap, base + c * 0.02, (s + total) / 2 + gap, base + c * 0.07],
        radius=c * 0.03, fill=fg,
    )
    return img.resize((size, size), Image.LANCZOS)


def _png(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


ICONS = {
    "icon-192.png": _png(_make_icon(192)),
    "icon-512.png": _png(_make_icon(512)),
    "icon-maskable-512.png": _png(_make_icon(512, rounded=False, content_scale=0.5)),  # 安全區內縮
    "apple-touch-icon.png": _png(_make_icon(180, rounded=False, content_scale=0.6).convert("RGB")),
}


# ---------- FastAPI:PWA 路由 + 掛載 Gradio ----------
app = FastAPI(title="CSV Viewer PWA")


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return JSONResponse(
        MANIFEST,
        media_type="application/manifest+json",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    # Service Worker 必須從根路徑提供,才能控制整個網站範圍
    return Response(
        SW_JS,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


@app.get("/pwa/offline.html", include_in_schema=False)
def offline_page():
    return HTMLResponse(OFFLINE_HTML)


@app.get("/pwa/icons/{name}", include_in_schema=False)
def icon(name: str):
    data = ICONS.get(name)
    if data is None:
        return Response(status_code=404)
    return Response(data, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}


# 必須在所有 PWA 路由註冊之後再掛載 Gradio
app = gr.mount_gradio_app(app, demo, path="/")


if __name__ == "__main__":
    # Render 會提供 PORT 環境變數,且必須綁定 0.0.0.0
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
