from rapidocr_onnxruntime import RapidOCR
from app.services.field_parser import extract_fields_from_text
ocr = RapidOCR()
for p in ["demo_data/reference/fevra-plus/front.png","demo_data/reference/fevra-plus/back.png","demo_data/reference/fevra-plus/batch.png","demo_data/tampered/glucobalance__typo-name/front.png","demo_data/tampered/allerfree__wrong-batch-format/back.png"]:
    result, _ = ocr(p)
    blocks = []
    for points, t, s in (result or []):
        xs=[pt[0] for pt in points]; ys=[pt[1] for pt in points]
        blocks.append({"text": t, "confidence": float(s), "bbox": [min(xs),min(ys),max(xs),max(ys)]})
    text = "\n".join(b["text"] for b in blocks)
    print("---", p)
    print(extract_fields_from_text(text, blocks))
