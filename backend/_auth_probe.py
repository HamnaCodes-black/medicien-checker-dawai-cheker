from pathlib import Path
from PIL import Image
from app.config import get_settings
from app.services.reference_store import ReferenceStore
from app.services.pipeline import analyze_package
settings=get_settings(); store=ReferenceStore(settings.refs_dir)
for pid in ["glucobalance","allerfree","cardiosafe"]:
    base=Path("demo_data/reference")/pid
    imgs={v:Image.open(base/f"{v}.png") for v in ("front","back","batch")}
    r=analyze_package(imgs, settings, store)
    print("===",pid,r.verdict.value,r.risk_score)
    print("fields",r.fields.model_dump())
    for c in r.checks:
        if c.status.value!="pass": print(" ",c.id,c.status.value,c.explanation_en,c.metrics)
