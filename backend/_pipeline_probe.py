import json, time
from pathlib import Path
from PIL import Image
from app.config import get_settings
from app.services.reference_store import ReferenceStore
from app.services.pipeline import analyze_package
settings=get_settings(); store=ReferenceStore(settings.refs_dir)
for case in ["reference/fevra-plus", "tampered/fevra-plus__typo-name", "tampered/fevra-plus__wrong-color"]:
    base=Path("demo_data")/case
    imgs={v: Image.open(base/f"{v}.png").convert("RGB") for v in ("front","back","batch")}
    t=time.time(); result=analyze_package(imgs, settings, store); elapsed=time.time()-t
    print("===",case, f"{elapsed:.1f}s")
    print("verdict",result.verdict,"score",result.risk_score,"conf",result.confidence,result.confidence_reason_key)
    print("ref",result.reference.name if result.reference else None, result.reference_match.matched_by if result.reference_match else None)
    print("fields",result.fields.model_dump())
    for c in result.checks:
        print(" ",c.id,c.status.value,round(c.risk_points,1),c.explanation_en[:90])
    print("visual", {k:(v.ssim,v.color_distance,v.phash_distance,v.sharpness_ratio,v.combined_similarity) for k,v in result.comparisons.items()})
    print("quality",[(k,v.status.value,v.blur_score) for k,v in result.quality.items()])
