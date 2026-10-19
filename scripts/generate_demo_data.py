"""Generate the fictional DawaiCheck demo packaging dataset.

Every product in this dataset is invented. The images are drawn from scratch
with Pillow for software testing only and must never be presented as real
medicine packaging or real DRAP registrations.
"""

from __future__ import annotations

import json
import math
import random
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "demo_data"
REFERENCE_DIR = DEMO_DIR / "reference"
TAMPERED_DIR = DEMO_DIR / "tampered"

EAN_L = [
    "0001101", "0011001", "0010011", "0111101", "0100011",
    "0110001", "0101111", "0111011", "0110111", "0001011",
]
EAN_G = [
    "0100111", "0110011", "0011011", "0100001", "0011101",
    "0111001", "0000101", "0010001", "0001001", "0010111",
]
EAN_R = [
    "1110010", "1100110", "1101100", "1000010", "1011100",
    "1001110", "1010000", "1000100", "1001000", "1110100",
]
EAN_PARITY = {
    0: "LLLLLL", 1: "LLGLGG", 2: "LLGGLG", 3: "LLGGGL", 4: "LGLLGG",
    5: "LGGLLG", 6: "LGGGLL", 7: "LGLGLG", 8: "LGLGGL", 9: "LGGLGL",
}


def _font_path(bold: bool) -> str:
    try:
        prop = font_manager.FontProperties(
            family="DejaVu Sans", weight="bold" if bold else "normal"
        )
        return font_manager.findfont(prop)
    except Exception:
        return "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"


FONT_REGULAR_PATH = _font_path(False)
FONT_BOLD_PATH = _font_path(True)
FONT_CACHE: dict[tuple[int, bool], ImageFont.FreeTypeFont] = {}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key not in FONT_CACHE:
        FONT_CACHE[key] = ImageFont.truetype(
            FONT_BOLD_PATH if bold else FONT_REGULAR_PATH, size
        )
    return FONT_CACHE[key]


def ean13_check_digit(payload12: str) -> str:
    total = 0
    for index, char in enumerate(payload12):
        digit = int(char)
        total += digit if index % 2 == 0 else digit * 3
    return str((10 - total % 10) % 10)


def full_ean13(payload12: str) -> str:
    return payload12 + ean13_check_digit(payload12)


def is_valid_ean13(value: str) -> bool:
    return (
        len(value) == 13
        and value.isdigit()
        and full_ean13(value[:12]) == value
    )


def draw_ean13(
    image: Image.Image,
    value: str,
    box: tuple[int, int, int, int],
    module_width: int = 3,
    bar_height: int = 132,
) -> None:
    if len(value) != 13 or not value.isdigit():
        raise ValueError("EAN-13 must be exactly 13 digits")
    draw = ImageDraw.Draw(image)
    x0, y0, x1, y1 = box
    quiet = 18 * module_width
    modules = "101"
    first = int(value[0])
    parity = EAN_PARITY[first]
    for slot, digit_char in enumerate(value[1:7]):
        digit = int(digit_char)
        modules += EAN_L[digit] if parity[slot] == "L" else EAN_G[digit]
    modules += "01010"
    for digit_char in value[7:]:
        modules += EAN_R[int(digit_char)]
    modules += "101"

    total_width = len(modules) * module_width
    if quiet * 2 + total_width > x1 - x0:
        module_width = max(1, (x1 - x0) // (len(modules) + 36))
        total_width = len(modules) * module_width
        quiet = 18 * module_width
    start_x = x0 + max(0, ((x1 - x0) - total_width) // 2)
    bar_top = y0
    bar_bottom = y0 + bar_height
    for index, bit in enumerate(modules):
        if bit == "1":
            bx = start_x + index * module_width
            draw.rectangle(
                [bx, bar_top, bx + module_width - 1, bar_bottom], fill="#111111"
            )
    digits_y = bar_bottom + 10
    draw.text(
        (start_x, digits_y),
        value,
        font=font(max(18, module_width * 8), bold=False),
        fill="#111111",
    )


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def rounded_gradient(
    size: tuple[int, int], top_color: str, bottom_color: str
) -> Image.Image:
    top_color = hex_rgb(top_color)
    bottom_color = hex_rgb(bottom_color)
    width, height = size
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(
            int(top_color[c] * (1 - ratio) + bottom_color[c] * ratio)
            for c in range(3)
        )
        draw.line([(0, y), (width, y)], fill=color)
    return image


def darken(hex_color: str, factor: float = 0.72) -> str:
    value = hex_color.lstrip("#")
    rgb = [int(value[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{max(0, int(c * factor)):02x}" for c in rgb)


def lighten(hex_color: str, factor: float = 0.9) -> str:
    value = hex_color.lstrip("#")
    rgb = [int(value[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{min(255, int(c + (255 - c) * factor)):02x}" for c in rgb)


def fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box_width: int,
    preferred: int,
    bold: bool = True,
    minimum: int = 30,
) -> ImageFont.FreeTypeFont:
    size = preferred
    while size > minimum:
        candidate = font(size, bold=bold)
        if draw.textlength(text, font=candidate) <= box_width:
            return candidate
        size -= 2
    return font(minimum, bold=bold)


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    width: int,
    text_font: ImageFont.FreeTypeFont,
    fill: str,
    line_gap: int = 8,
) -> int:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=text_font) <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    y = xy[1]
    for line in lines:
        draw.text((xy[0], y), line, font=text_font, fill=fill)
        y += text_font.size + line_gap
    return y


def draw_logo(
    image: Image.Image, center: tuple[int, int], radius: int, color: str, mark: str
) -> None:
    draw = ImageDraw.Draw(image)
    cx, cy = center
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        fill="#FFFFFF",
    )
    inner = radius - 10
    draw.ellipse(
        [cx - inner, cy - inner, cx + inner, cy + inner],
        fill=color,
    )
    draw.rounded_rectangle(
        [cx - 7, cy - inner + 16, cx + 7, cy + inner - 16], radius=6, fill="#FFFFFF"
    )
    draw.rounded_rectangle(
        [cx - inner + 16, cy - 7, cx + inner - 16, cy + 7], radius=6, fill="#FFFFFF"
    )
    draw.text(
        (cx, cy + radius + 18),
        mark,
        font=font(18, bold=True),
        fill="#0F172A",
        anchor="ma",
    )


def draw_pill_icon(
    image: Image.Image, center: tuple[int, int], scale: int = 1, color: str = "#0F766E"
) -> None:
    draw = ImageDraw.Draw(image)
    cx, cy = center
    width = 92 * scale
    height = 46 * scale
    box = [cx - width // 2, cy - height // 2, cx + width // 2, cy + height // 2]
    draw.rounded_rectangle(box, radius=height // 2, fill="#FFFFFF", outline=color, width=4)
    draw.rectangle(
        [cx - width // 2, cy - height // 2, cx, cy + height // 2],
        fill=color,
    )
    draw.rounded_rectangle(
        [cx - width // 2, cy - height // 2, cx, cy + height // 2],
        radius=height // 2,
        fill=color,
    )


def make_front(product: dict, display_name: str, primary: str) -> Image.Image:
    width, height = 1000, 1400
    base = rounded_gradient((width, height), primary, darken(primary, 0.6))
    image = base.convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")

    draw.ellipse([640, -180, 1180, 360], fill=lighten(primary, 0.25) + "55")
    draw.ellipse([-220, 860, 360, 1440], fill=lighten(primary, 0.1) + "33")

    draw.rounded_rectangle([60, 70, 940, 1280], radius=36, fill="#FFFFFF")
    draw.rounded_rectangle([60, 70, 940, 1280], radius=36, outline="#FFFFFF", width=2)

    draw.rounded_rectangle([60, 70, 940, 205], radius=32, fill=primary)
    draw.rectangle([60, 155, 940, 205], fill=primary)
    draw_logo(image, (140, 135), 42, "#FFFFFF", "")
    draw.text((205, 96), "DAWAI CHECK DEMO PACK", font=font(23, True), fill="#FFFFFF")
    draw.text(
        (205, 132),
        "FICTIONAL PRODUCT  •  NOT FOR SALE  •  SOFTWARE TEST",
        font=font(16, False),
        fill="#E2F8F4",
    )
    draw.rounded_rectangle([760, 100, 892, 148], radius=24, fill="#FFFFFF")
    draw.text((826, 124), "DEMO", font=font(22, True), fill=primary, anchor="mm")

    draw.text((112, 260), "PHARMACY / PRESCRIPTION", font=font(18, True), fill="#64748B")
    name_font = fit_text(draw, display_name, 740, 92)
    draw.text((112, 300), display_name, font=name_font, fill="#0F172A")
    strength_font = font(64, True)
    draw.text((112, 415), product["strength"], font=strength_font, fill=primary)
    draw.text(
        (112, 500),
        product["form"].upper(),
        font=font(28, True),
        fill="#475569",
    )
    draw.text((112, 542), product["pack"], font=font(28, False), fill="#475569")

    draw.rounded_rectangle([112, 610, 888, 980], radius=26, fill=lighten(primary, 0.92))
    draw.text((146, 640), "DEMO PACKAGING SAMPLE", font=font(20, True), fill=primary)
    draw_pill_icon(image, (740, 785), 1.6, primary)
    draw.rounded_rectangle([160, 690, 380, 760], radius=18, fill="#FFFFFF")
    draw.text((186, 706), "TABLET", font=font(22, True), fill=primary)
    draw.text((186, 730), "SAMPLE ART", font=font(16, False), fill="#64748B")
    draw.rounded_rectangle([160, 800, 500, 870], radius=18, fill="#FFFFFF")
    draw.text((186, 816), "FICTIONAL BRAND", font=font(22, True), fill=primary)
    draw.text((186, 841), "Synthetic demo image", font=font(16, False), fill="#64748B")
    draw.text(
        (146, 905),
        "This carton was generated for DawaiCheck testing.",
        font=font(18, False),
        fill="#475569",
    )

    draw.line([112, 1030, 888, 1030], fill="#E2E8F0", width=2)
    draw.text((112, 1055), "Manufactured by", font=font(18, False), fill="#64748B")
    manufacturer_font = fit_text(draw, product["manufacturer"], 760, 32, bold=True)
    draw.text((112, 1082), product["manufacturer"], font=manufacturer_font, fill="#0F172A")
    draw.text(
        (112, 1130),
        "Plot 00, Demo Industrial Estate, Lahore, Pakistan (fictional address)",
        font=fit_text(draw, "Plot 00, Demo Industrial Estate, Lahore, Pakistan (fictional address)", 760, 21, False),
        fill="#475569",
    )
    draw.rounded_rectangle([112, 1180, 888, 1246], radius=18, fill="#F1F5F9")
    draw.text((134, 1198), "Reg. No.", font=font(20, True), fill="#334155")
    draw.text(
        (228, 1198),
        product["reg_no"] or "— not printed —",
        font=font(20, False),
        fill="#334155",
    )
    draw.text(
        (134, 1222),
        "DEMO DATA — not a real DRAP registration",
        font=font(15, False),
        fill="#64748B",
    )
    return image


def make_back(product: dict, display_name: str, primary: str, barcode: str) -> Image.Image:
    width, height = 1000, 1400
    image = Image.new("RGB", (width, height), "#F8FAFC")
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rounded_rectangle([0, 0, width, 220], radius=0, fill=primary)
    draw.text((64, 48), display_name, font=fit_text(draw, display_name, 500, 52, True), fill="#FFFFFF")
    draw.text((64, 112), f"{product['strength']}  •  {product['form'].upper()}  •  {product['pack']}", font=font(24, False), fill="#E2F8F4")
    draw.rounded_rectangle([780, 60, 936, 112], radius=26, fill="#FFFFFF")
    draw.text((858, 86), "DEMO DATA", font=font(20, True), fill=primary, anchor="mm")
    draw.text((64, 146), "FICTIONAL PACKAGING • FOR SOFTWARE TESTING ONLY", font=font(17, True), fill="#D1FAE5")

    draw.text((64, 260), "PRODUCT INFORMATION", font=font(24, True), fill="#0F172A")
    y = draw_wrapped(
        draw,
        (
            "This is a synthetic sample carton created for the DawaiCheck "
            "packaging-screening prototype. It is not a real medicine and it does "
            "not describe a real product, manufacturer, or registration."
        ),
        (64, 298),
        872,
        font(23, False),
        "#334155",
    )
    y += 26

    draw.text((64, y), "DIRECTIONS", font=font(22, True), fill="#0F172A")
    y = draw_wrapped(
        draw,
        "Demo use only. Store below 30°C in a dry place. Protect from light. Keep out of reach of children.",
        (64, y + 36),
        580,
        font(23, False),
        "#334155",
    )
    y += 26

    panel_top = y
    draw.rounded_rectangle([64, panel_top, 936, panel_top + 330], radius=22, fill="#FFFFFF", outline="#CBD5E1", width=2)
    draw.text((90, panel_top + 22), "BATCH & EXPIRY", font=font(22, True), fill=primary)
    rows = [
        ("Reg. No.", product["reg_no"]),
        ("Batch No.", product["batch"]),
        ("Mfg. Date", product["mfg"]),
        ("Expiry Date", product["exp"]),
    ]
    row_y = panel_top + 68
    for label, value in rows:
        if value is None:
            row_y += 58
            continue
        draw.text((90, row_y), label, font=font(22, True), fill="#475569")
        draw.text((290, row_y - 2), value, font=fit_text(draw, value, 590, 26, True), fill="#0F172A")
        row_y += 58
    draw.text(
        (90, panel_top + 296),
        "DEMO DATA — not a real DRAP registration",
        font=font(16, False),
        fill="#64748B",
    )

    barcode_top = panel_top + 356
    draw.rounded_rectangle([64, barcode_top, 610, barcode_top + 240], radius=20, fill="#FFFFFF", outline="#CBD5E1", width=2)
    draw.text((88, barcode_top + 16), "EAN-13", font=font(18, True), fill="#475569")
    draw_ean13(image, barcode, (88, barcode_top + 46, 586, barcode_top + 196), module_width=4, bar_height=128)

    draw.rounded_rectangle([636, barcode_top, 936, barcode_top + 240], radius=20, fill="#FFFFFF", outline="#CBD5E1", width=2)
    draw.text((662, barcode_top + 20), "MADE IN PAKISTAN", font=font(18, True), fill="#0F172A")
    draw.text((662, barcode_top + 56), "Fictional address", font=font(18, False), fill="#475569")
    draw.text((662, barcode_top + 82), "Plot 00, Demo Estate", font=font(18, False), fill="#475569")
    draw.text((662, barcode_top + 108), "Lahore (DEMO)", font=font(18, False), fill="#475569")
    draw.text((662, barcode_top + 154), f"GTIN: {barcode}", font=font(16, False), fill="#334155")
    draw.text((662, barcode_top + 182), "SAMPLE • NOT FOR SALE", font=font(16, True), fill=primary)

    footer_y = barcode_top + 268
    draw.text(
        (64, footer_y),
        (
            "DawaiCheck checks packaging appearance only. It cannot test tablet "
            "contents. Made-up demo product."
        ),
        font=font(18, False),
        fill="#475569",
    )
    return image


def make_batch_view(product: dict, display_name: str, primary: str) -> Image.Image:
    width, height = 1000, 900
    image = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle([0, 0, width, 130], fill=primary)
    draw.text((54, 30), display_name, font=fit_text(draw, display_name, 500, 44, True), fill="#FFFFFF")
    draw.text((54, 86), f"{product['strength']}  •  {product['form'].upper()}", font=font(22, False), fill="#E2F8F4")
    draw.text((770, 46), "CLOSE-UP", font=font(20, True), fill="#FFFFFF")
    draw.text((770, 76), "batch / expiry area", font=font(16, False), fill="#E2F8F4")

    draw.text((54, 178), "BATCH, DATES & REGISTRATION", font=font(28, True), fill="#0F172A")
    draw.text((54, 220), "Photograph this printed panel clearly.", font=font(20, False), fill="#64748B")

    rows = [
        ("Reg. No.", product["reg_no"], 290),
        ("Batch No.", product["batch"], 382),
        ("Mfg. Date", product["mfg"], 474),
        ("Expiry Date", product["exp"], 566),
    ]
    for label, value, y in rows:
        draw.rounded_rectangle([54, y, 946, y + 72], radius=14, fill="#F1F5F9")
        draw.text((78, y + 22), label, font=font(24, True), fill="#475569")
        if value:
            draw.text((330, y + 18), value, font=fit_text(draw, value, 580, 30, True), fill="#0F172A")
        else:
            draw.text((330, y + 20), "— not printed —", font=font(24, False), fill="#94A3B8")

    draw.rounded_rectangle([54, 676, 946, 782], radius=14, fill="#FEF3C7")
    draw.text((78, 698), "DEMO DATA", font=font(22, True), fill="#92400E")
    draw.text((230, 700), "Fictional product. Not a real DRAP registration.", font=font(19, False), fill="#92400E")

    draw.text((54, 820), "DawaiCheck synthetic demo dataset • software testing only", font=font(17, False), fill="#64748B")
    return image


def apply_blur(image: Image.Image, radius: float = 1.8) -> Image.Image:
    return image.filter(ImageFilter.GaussianBlur(radius=radius))


def draw_front_wrong_color(product: dict, display_name: str) -> Image.Image:
    return make_front(product, display_name, "#6D28D9")


def make_reference_images(product: dict) -> dict[str, Image.Image]:
    barcode = full_ean13(product["barcode12"])
    return {
        "front": make_front(product, product["name"], product["color"]),
        "back": make_back(product, product["name"], product["color"], barcode),
        "batch": make_batch_view(product, product["name"], product["color"]),
    }


PRODUCTS = [
    {
        "id": "fevra-plus",
        "name": "Fevra+",
        "strength": "500 mg",
        "form": "Tablets",
        "pack": "20 tablets",
        "manufacturer": "Northstar Pharma (Pvt) Ltd",
        "reg_no": "DEMO-REG-1001",
        "reg_regex": r"^DEMO-REG-\d{4}$",
        "batch": "DEMO-FV-2025-A17",
        "batch_regex": r"^DEMO-FV-\d{4}-[A-Z]\d{2}$",
        "mfg": "03/2025",
        "exp": "11/2027",
        "color": "#0F766E",
        "barcode12": "200100100001",
        "aliases": ["Fevra Plus"],
    },
    {
        "id": "coughcalm",
        "name": "CoughCalm",
        "strength": "120 ml",
        "form": "Syrup",
        "pack": "100 ml bottle",
        "manufacturer": "Cedar Labs (Pvt) Ltd",
        "reg_no": "DEMO-REG-1002",
        "reg_regex": r"^DEMO-REG-\d{4}$",
        "batch": "DEMO-CC-2025-B04",
        "batch_regex": r"^DEMO-CC-\d{4}-[A-Z]\d{2}$",
        "mfg": "06/2025",
        "exp": "05/2027",
        "color": "#B45309",
        "barcode12": "200200200002",
        "aliases": ["Cough Calm"],
    },
    {
        "id": "glucobalance",
        "name": "GlucoBalance",
        "strength": "850 mg",
        "form": "Tablets",
        "pack": "30 tablets",
        "manufacturer": "Indus Bio Pharma (Pvt) Ltd",
        "reg_no": "DEMO-REG-1003",
        "reg_regex": r"^DEMO-REG-\d{4}$",
        "batch": "DEMO-GB-2026-C11",
        "batch_regex": r"^DEMO-GB-\d{4}-[A-Z]\d{2}$",
        "mfg": "01/2026",
        "exp": "12/2027",
        "color": "#4338CA",
        "barcode12": "200300300003",
        "aliases": ["Gluco Balance"],
    },
    {
        "id": "allerfree",
        "name": "AllerFree",
        "strength": "10 mg",
        "form": "Tablets",
        "pack": "10 tablets",
        "manufacturer": "Meridian Healthcare (Pvt) Ltd",
        "reg_no": "DEMO-REG-1004",
        "reg_regex": r"^DEMO-REG-\d{4}$",
        "batch": "DEMO-AF-2025-D08",
        "batch_regex": r"^DEMO-AF-\d{4}-[A-Z]\d{2}$",
        "mfg": "09/2025",
        "exp": "08/2027",
        "color": "#C2410C",
        "barcode12": "200400400004",
        "aliases": ["Aller Free"],
    },
    {
        "id": "cardiosafe",
        "name": "CardioSafe",
        "strength": "5 mg",
        "form": "Tablets",
        "pack": "28 tablets",
        "manufacturer": "Apex Formulations (Pvt) Ltd",
        "reg_no": "DEMO-REG-1005",
        "reg_regex": r"^DEMO-REG-\d{4}$",
        "batch": "DEMO-CS-2026-E02",
        "batch_regex": r"^DEMO-CS-\d{4}-[A-Z]\d{2}$",
        "mfg": "02/2026",
        "exp": "01/2028",
        "color": "#BE123C",
        "barcode12": "200500500005",
        "aliases": ["Cardio Safe"],
    },
]


VARIANTS = {
    "fevra-plus": [
        ("wrong-color", "wrong_colour", {"color": "#6D28D9"}),
        ("typo-name", "typo_in_brand_name", {"display_name": "Fevrraa+"}),
        ("expired-date", "expired_date", {"exp": "01/2024"}),
    ],
    "coughcalm": [
        ("blurry-text", "blurry_print", {"blur": 1.7}),
        ("wrong-batch-format", "wrong_batch_format", {"batch": "CC/25/B04"}),
        ("invalid-barcode", "invalid_barcode_checksum", {"bad_barcode": True}),
    ],
    "glucobalance": [
        ("typo-name", "typo_in_brand_name", {"display_name": "GlucoBallans"}),
        ("expired-date", "expired_date", {"exp": "06/2024"}),
        ("missing-registration", "missing_registration_number", {"reg_no": None}),
    ],
    "allerfree": [
        ("wrong-color", "wrong_colour", {"color": "#4D7C0F"}),
        ("invalid-barcode", "invalid_barcode_checksum", {"bad_barcode": True}),
        ("wrong-batch-format", "wrong_batch_format", {"batch": "AF2025X08"}),
    ],
    "cardiosafe": [
        ("blurry-text", "blurry_print", {"blur": 1.7}),
        ("missing-registration", "missing_registration_number", {"reg_no": None}),
        ("expired-date", "expired_date", {"exp": "09/2023"}),
    ],
}


def make_variant_images(product: dict, mutation: dict) -> dict[str, Image.Image]:
    working = {**product, **{k: v for k, v in mutation.items() if k in product}}
    display_name = mutation.get("display_name", product["name"])
    color = mutation.get("color", product["color"])
    barcode = full_ean13(product["barcode12"])
    if mutation.get("bad_barcode"):
        last = int(barcode[-1])
        barcode = barcode[:-1] + str((last + 1) % 10)

    images = {
        "front": make_front(working, display_name, color),
        "back": make_back(working, display_name, color, barcode),
        "batch": make_batch_view(working, display_name, color),
    }
    if mutation.get("blur"):
        images = {
            key: apply_blur(image, float(mutation["blur"]))
            for key, image in images.items()
        }
    return images


def save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG", optimize=True)


def main() -> None:
    random.seed(2026)
    if DEMO_DIR.exists():
        for folder in (REFERENCE_DIR, TAMPERED_DIR):
            if folder.exists():
                shutil.rmtree(folder)
    DEMO_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {
        "dataset": "DawaiCheck synthetic demo dataset",
        "notice": (
            "DEMO DATA — all products, manufacturers and registration numbers are "
            "fictional. These images were generated for software testing and are "
            "not real medicine packaging or real DRAP registrations."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "scripts/generate_demo_data.py",
        "references": [],
        "cases": [],
    }

    for product in PRODUCTS:
        images = make_reference_images(product)
        save_png(images["front"], REFERENCE_DIR / product["id"] / "front.png")
        save_png(images["back"], REFERENCE_DIR / product["id"] / "back.png")
        save_png(images["batch"], REFERENCE_DIR / product["id"] / "batch.png")
        manifest["references"].append(
            {
                "id": product["id"],
                "name": product["name"],
                "aliases": product["aliases"],
                "strength": product["strength"],
                "manufacturer": product["manufacturer"],
                "reg_no": product["reg_no"],
                "reg_regex": product["reg_regex"],
                "batch_regex": product["batch_regex"],
                "barcode": full_ean13(product["barcode12"]),
                "barcode_prefix": full_ean13(product["barcode12"])[:7],
                "color_hex": product["color"],
                "demo": True,
                "images": {
                    "front": f"reference/{product['id']}/front.png",
                    "back": f"reference/{product['id']}/back.png",
                    "batch": f"reference/{product['id']}/batch.png",
                },
            }
        )
        manifest["cases"].append(
            {
                "id": f"{product['id']}__authentic",
                "product_id": product["id"],
                "variant": "authentic",
                "tamper_type": None,
                "expected_verdict": "consistent",
                "reference_image": product["id"],
                "images": {
                    view: f"reference/{product['id']}/{view}.png"
                    for view in ("front", "back", "batch")
                },
            }
        )

        for variant_id, tamper_type, mutation in VARIANTS.get(product["id"], []):
            case_id = f"{product['id']}__{variant_id}"
            variant_images = make_variant_images(product, mutation)
            for view, image in variant_images.items():
                save_png(image, TAMPERED_DIR / case_id / f"{view}.png")
            manifest["cases"].append(
                {
                    "id": case_id,
                    "product_id": product["id"],
                    "variant": variant_id,
                    "tamper_type": tamper_type,
                    "expected_verdict": "suspicious",
                    "reference_image": product["id"],
                    "mutation": {
                        key: value for key, value in mutation.items()
                    },
                    "images": {
                        view: f"tampered/{case_id}/{view}.png"
                        for view in ("front", "back", "batch")
                    },
                }
            )

    (DEMO_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    labels_path = DEMO_DIR / "labels.csv"
    with labels_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("case_id,product_id,variant,tamper_type,expected_verdict\n")
        for case in manifest["cases"]:
            handle.write(
                f"{case['id']},{case['product_id']},{case['variant']},"
                f"{case['tamper_type'] or ''},{case['expected_verdict']}\n"
            )

    (DEMO_DIR / "README.md").write_text(
        "# DawaiCheck synthetic demo dataset\n\n"
        "**DEMO DATA — not real registrations.** All product names, manufacturers, "
        "registration numbers, batches and dates are fictional. The packaging images "
        "were generated with PIL specifically for this prototype.\n\n"
        "- `reference/` — 5 fictional authentic reference packages\n"
        "- `tampered/` — 15 intentionally tampered variants\n"
        "- `manifest.json` — metadata and expected labels\n"
        "- `labels.csv` — labels used by the evaluation script\n\n"
        "Regenerate with `python scripts/generate_demo_data.py`.\n"
        "These images must not be used as evidence that any real product is safe "
        "or unsafe.\n",
        encoding="utf-8",
    )

    print(
        f"Generated {len(manifest['references'])} reference packages and "
        f"{len(manifest['cases']) - len(manifest['references'])} tampered cases "
        f"under {DEMO_DIR}"
    )
    print("DEMO DATA — fictional packaging only.")


if __name__ == "__main__":
    main()
