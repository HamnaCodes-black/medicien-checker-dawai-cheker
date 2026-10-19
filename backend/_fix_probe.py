from pathlib import Path
from PIL import Image
from app.config import get_settings
from app.services.reference_store import ReferenceStore
from app.services.pipeline import analyze_package
settings=get_settings(); store=ReferenceStore(settings.refs_dir)
for case in ["tampered/coughcalm__blurry-text","tampered/cardiosafe__blurry-text","reference/glucobalance","reference/allerfree","reference/cardiosafe"]:
    base=Path("demo_data")/case
    imgs={v:Image.open(base/f"{v}.png") for v in ("front","back","batch")}
    r=analyze_package(imgs, settings, store)
    print("===",case,r.verdict.value,r.risk_score,r.confidence.value)
    print(" ", [(c.id,c.status.value,c.risk_points) for c in r.checks if c.status.value!="pass"])
    print("  visual",{k:(x.sharpness_ratio,x.combined_similarity) for k,x in r.comparisons.items()},"quality",[(k,v.status.value,v.blur_score) for k,v in r.quality.items()])
