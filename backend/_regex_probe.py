import json, re
from pathlib import Path
idx=json.loads(Path('backend/data/references/index.json').read_text(encoding='utf-8'))
for r in idx['references']:
    print(r['id'], repr(r.get('batch_regex')), r.get('reg_regex'))
import sys
sys.path.insert(0,'backend')
from app.services.checks import _batch_variants
b='DEM0-FV-2025-A17'
print(_batch_variants(b))
pattern=r'^DEMO-FV-\d{4}-[A-Z]\d{2}$'
print([(v, bool(re.fullmatch(pattern,v,flags=re.IGNORECASE))) for v in _batch_variants(b)])
