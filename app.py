"""開放資料 CSV 瀏覽器 —— Gradio + FastAPI,支援 PWA 與 RWD"""
import io
import os
import tempfile
from pathlib import Path

import gradio as gr
import pandas as pd
import requests
import urllib3
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
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


# ---------- FastAPI:PWA 路由 + 掛載 Gradio ----------
app = FastAPI(title="CSV Viewer PWA")


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return FileResponse(
        STATIC_DIR / "manifest.webmanifest",
        media_type="application/manifest+json",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    # Service Worker 必須從根路徑提供,才能控制整個網站範圍
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}


# 靜態資源(圖示、離線頁)—— 需在掛載 Gradio 之前註冊
app.mount("/pwa", StaticFiles(directory=STATIC_DIR), name="pwa")

app = gr.mount_gradio_app(app, demo, path="/")


if __name__ == "__main__":
    # Render 會提供 PORT 環境變數,且必須綁定 0.0.0.0
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
