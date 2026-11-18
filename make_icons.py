"""產生 PWA 圖示(需要 Pillow:pip install pillow)。
用法:python tools/make_icons.py"""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "static" / "icons"
OUT.mkdir(parents=True, exist_ok=True)

BG, FG, ACCENT = "#4f46e5", "#ffffff", "#7dd3fc"


def draw_icon(size, rounded=True, content_scale=0.62):
    k = 4  # 超取樣,讓邊緣更平滑
    S = size * k
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if rounded:
        d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=BG)
    else:
        d.rectangle([0, 0, S, S], fill=BG)

    c = S * content_scale
    y0 = (S - c) / 2
    bar_w, gap = c * 0.22, c * 0.09
    total = 3 * bar_w + 2 * gap
    x = (S - total) / 2
    base = y0 + c * 0.88
    for h, color in zip((0.45, 0.78, 0.6), (FG, ACCENT, FG)):
        d.rounded_rectangle([x, base - c * h, x + bar_w, base], radius=bar_w * 0.25, fill=color)
        x += bar_w + gap
    d.rounded_rectangle([(S - total) / 2 - gap, base + c * 0.02, (S + total) / 2 + gap, base + c * 0.07],
                        radius=c * 0.03, fill=FG)
    return img.resize((size, size), Image.LANCZOS)


draw_icon(192).save(OUT / "icon-192.png")
draw_icon(512).save(OUT / "icon-512.png")
draw_icon(512, rounded=False, content_scale=0.5).save(OUT / "icon-maskable-512.png")  # 安全區內縮
draw_icon(180, rounded=False, content_scale=0.6).convert("RGB").save(OUT / "apple-touch-icon.png")
print("icons saved to", OUT)
