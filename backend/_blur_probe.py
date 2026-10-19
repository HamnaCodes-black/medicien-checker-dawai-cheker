from pathlib import Path
from PIL import Image
from app.services.image_quality import assess_quality
for pid in ["coughcalm","cardiosafe"]:
    base=Path("demo_data/tampered")/f"{pid}__blurry-text"
    q=assess_quality({v:Image.open(base/f"{v}.png") for v in ("front","back","batch")})
    print(pid, [(v,x.status.value,x.blur_score,x.brightness,x.contrast,x.glare_ratio) for v,x in q.items()])
