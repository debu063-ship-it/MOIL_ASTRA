"""One-off: build preview_imagery.html with base64-embedded JPEGs of the belt images."""
import base64
import io
import os

from PIL import Image

BASE = os.path.join("data", "external", "satellite", "imagery")
PARTS = [
    ("belt_truecolor.png", "1. True color (B4-B3-B2) — Sentinel-2 median composite"),
    ("belt_falsecolor.png", "2. False color (B8-B4-B3) — vegetation / landform contrast"),
    ("belt_hillshade.png", "3. DEM hillshade — Copernicus GLO30 terrain relief"),
]

segments = []
for name, title in PARTS:
    im = Image.open(os.path.join(BASE, name)).convert("RGB")
    w = 900
    im = im.resize((w, int(im.height * w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=70)
    b64 = base64.b64encode(buf.getvalue()).decode()
    segments.append(
        f'<h2>{title}</h2><img src="data:image/jpeg;base64,{b64}" '
        'style="max-width:100%;border-radius:6px">'
    )
    print(name, len(b64) // 1024, "KB b64")

html = (
    '<!DOCTYPE html><html><head><meta charset="utf-8"><title>MOIL Belt Imagery</title>'
    '<style>body{font-family:Segoe UI,Arial;background:#0d1117;color:#e6edf3;margin:16px}'
    'h1{font-size:18px}h2{font-size:14px;color:#8b949e;margin:18px 0 6px}'
    'p{color:#8b949e;font-size:12px}</style></head><body>'
    '<h1>Sentinel-2 &amp; DEM imagery — Balaghat-Bhandara manganese belt</h1>'
    '<p>Cloud-masked dry-season 2024 median via Google Earth Engine. '
    'Full-res: data/external/satellite/imagery/</p>'
    + "<br>".join(segments)
    + "</body></html>"
)
with open("preview_imagery.html", "w") as f:
    f.write(html)
print("preview_imagery.html written,", len(html) // 1024, "KB total")
