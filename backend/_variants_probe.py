import re
from app.services.checks import _batch_variants
for batch, pattern in [
 ("DEM0-GB-2026-C11", r"^DEMO-GB-\d{4}-[A-Z]\d{2}$"),
 ("DEM0-AF-2025-D08", r"^DEMO-AF-\d{4}-[A-Z]\d{2}$"),
]:
    variants=_batch_variants(batch)
    print(batch,len(variants),[v for v in variants if re.fullmatch(pattern,v,flags=re.IGNORECASE)])
