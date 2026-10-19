from __future__ import annotations

from datetime import date

from app.services.field_parser import (
    extract_fields_from_text,
    merge_view_fields,
    parse_date,
)
from app.services.barcode import gtin_check_digit, normalize_gtin, validate_gtin


def test_ean13_check_digit_validation():
    assert gtin_check_digit("200100100001") == "1"
    assert validate_gtin("2001001000011")
    assert not validate_gtin("2001001000012")
    assert normalize_gtin("GTIN: 2001001000011") == "2001001000011"


def test_parse_dates_supported_forms():
    assert parse_date("11/2027").isoformat() == "2027-11-01"
    assert parse_date("03/2025").isoformat() == "2025-03-01"
    assert parse_date("Nov 2027").isoformat() == "2027-11-01"
    assert parse_date("25/12/2027").isoformat() == "2027-12-25"
    assert parse_date("not a date") is None


def test_field_parser_extracts_batch_dates_registration_and_barcode():
    text = """Fevra+
500 mg  TABLETS  20 tablets
Reg. No.
DEMO-REG-1001
Batch No. DEM0-FV-2025-A17
Mfg. Date 03/2025
Expiry Date 11/2027
GTIN: 2001001000011
Manufactured by
Northstar Pharma (Pvt) Ltd
"""
    fields = extract_fields_from_text(text)
    assert fields["registration_number"] == "DEMO-REG-1001"
    assert fields["batch_number"] == "DEM0-FV-2025-A17"
    assert fields["manufacturing_date"] == "2025-03"
    assert fields["expiry_date"] == "2027-11"
    assert fields["barcode"] == "2001001000011"
    assert fields["manufacturer"] == "Northstar Pharma (Pvt) Ltd"
    assert fields["strength"] == "500 mg"


def test_merged_view_fields_prefers_batch_closeup_for_regulatory_data():
    merged = merge_view_fields(
        {
            "front": {
                "product_name": "Fevra+",
                "registration_number": "DEMO-REG-1001",
                "batch_number": None,
                "expiry_date": None,
            },
            "back": {
                "registration_number": "DEMO-REG-1001",
                "batch_number": "DEMO-FV-2025-A17",
                "expiry_date": "2027-11",
            },
            "batch": {
                "batch_number": "DEMO-FV-2025-A17",
                "expiry_date": "11/2027",
            },
        }
    )
    assert merged["product_name"] == "Fevra+"
    assert merged["expiry_date"] == "11/2027"
    assert merged["batch_number"] == "DEMO-FV-2025-A17"
