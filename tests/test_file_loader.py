import json
from pathlib import Path

import pytest

import src
from src.util.file_loader import FileLoader

DATA_DIR = Path(src.__file__).parent / "data"


def signature(entries):
    return [(e.date.strftime("%Y-%m-%d"), float(e.weight), e.calories) for e in entries]


def test_all_formats_load_identical_data():
    csv_entries = FileLoader.load_file(str(DATA_DIR / "sample_data.csv"))
    json_entries = FileLoader.load_file(str(DATA_DIR / "sample_data.json"))
    txt_entries = FileLoader.load_file(str(DATA_DIR / "sample_data.txt"))

    assert len(csv_entries) == 20
    assert signature(csv_entries) == signature(json_entries)
    assert signature(csv_entries) == signature(txt_entries)


def test_txt_first_entry_is_parsed_correctly():
    entries = FileLoader.load_file(str(DATA_DIR / "sample_data.txt"))
    first = entries[0]
    assert first.date.strftime("%Y-%m-%d") == "2025-07-01"
    assert first.weight == pytest.approx(200.0)
    assert first.calories == 2200


def test_unsupported_extension_raises():
    with pytest.raises(ValueError):
        FileLoader.load_file("data.xml")


def test_txt_skips_blanks_and_comments(tmp_path):
    p = tmp_path / "log.txt"
    p.write_text(
        "# a comment\n"
        "\n"
        "date, weight, calories\n"
        "2025-07-01, 200, 2200\n"
        "   \n"
        "2025-07-02, 199, 2100\n",
        encoding="utf-8",
    )
    entries = FileLoader.load_file(str(p))
    assert len(entries) == 2


def test_txt_malformed_row_raises_clear_error(tmp_path):
    p = tmp_path / "bad.txt"
    p.write_text("2025-07-01, notanumber, 2200\n", encoding="utf-8")
    with pytest.raises(ValueError):
        FileLoader.load_file(str(p))


def test_txt_too_few_values_raises(tmp_path):
    p = tmp_path / "short.txt"
    p.write_text("2025-07-01, 200\n", encoding="utf-8")
    with pytest.raises(ValueError):
        FileLoader.load_file(str(p))


def test_csv_missing_column_raises(tmp_path):
    p = tmp_path / "missing.csv"
    p.write_text("date,weight\n2025-07-01,200\n", encoding="utf-8")
    with pytest.raises(ValueError):
        FileLoader.load_file(str(p))


def test_json_must_be_a_list(tmp_path):
    p = tmp_path / "obj.json"
    p.write_text('{"date": "2025-07-01", "weight": 200, "calories": 2200}', encoding="utf-8")
    with pytest.raises(ValueError):
        FileLoader.load_file(str(p))


# --- Encoding and headers -------------------------------------------------

def test_csv_with_utf8_bom_loads(tmp_path):
    # Excel's "CSV UTF-8" export starts the file with a byte-order mark.
    p = tmp_path / "excel.csv"
    p.write_bytes(b"\xef\xbb\xbfdate,weight,calories\r\n2025-07-01,200,2200\r\n")
    entries = FileLoader.load_file(str(p))
    assert signature(entries) == [("2025-07-01", 200.0, 2200)]


def test_csv_header_is_case_insensitive(tmp_path):
    p = tmp_path / "caps.csv"
    p.write_text("Date, Weight ,CALORIES\n2025-07-01,200,2200\n", encoding="utf-8")
    assert signature(FileLoader.load_file(str(p))) == [("2025-07-01", 200.0, 2200)]


def test_txt_with_utf8_bom_and_header_loads(tmp_path):
    p = tmp_path / "bom.txt"
    p.write_bytes(b"\xef\xbb\xbfdate, weight, calories\n2025-07-01, 200, 2200\n")
    assert signature(FileLoader.load_file(str(p))) == [("2025-07-01", 200.0, 2200)]


@pytest.mark.parametrize("header", ["Date, Weight, Calories", "DATE WEIGHT CALORIES"])
def test_txt_header_detection_is_case_insensitive(tmp_path, header):
    p = tmp_path / "log.txt"
    p.write_text(f"{header}\n2025-07-01, 200, 2200\n", encoding="utf-8")
    assert len(FileLoader.load_file(str(p))) == 1


# --- Value types ----------------------------------------------------------

def write_json(tmp_path, text):
    p = tmp_path / "data.json"
    p.write_text(text, encoding="utf-8")
    return str(p)


@pytest.mark.parametrize("calories", ["2200", "2200.0", "2.2e3"])
def test_json_whole_number_calories_are_accepted(tmp_path, calories):
    path = write_json(tmp_path, f'[{{"date": "2025-07-01", "weight": 200, "calories": {calories}}}]')
    assert FileLoader.load_file(path)[0].calories == 2200


def test_json_quoted_calories_are_accepted(tmp_path):
    path = write_json(tmp_path, '[{"date": "2025-07-01", "weight": "200.5", "calories": "2200"}]')
    entry = FileLoader.load_file(path)[0]
    assert entry.weight == pytest.approx(200.5)
    assert entry.calories == 2200


def test_json_fractional_calories_are_rejected(tmp_path):
    path = write_json(tmp_path, '[{"date": "2025-07-01", "weight": 200, "calories": 2200.9}]')
    with pytest.raises(ValueError, match="whole number"):
        FileLoader.load_file(path)


def test_csv_fractional_calories_are_rejected(tmp_path):
    p = tmp_path / "frac.csv"
    p.write_text("date,weight,calories\n2025-07-01,200,2200.5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="whole number"):
        FileLoader.load_file(str(p))


@pytest.mark.parametrize("field", ["weight", "calories"])
def test_json_boolean_values_are_rejected(tmp_path, field):
    record = {"date": '"2025-07-01"', "weight": "200", "calories": "2200"}
    record[field] = "true"
    body = ", ".join(f'"{key}": {value}' for key, value in record.items())
    path = write_json(tmp_path, f"[{{{body}}}]")
    with pytest.raises(ValueError, match="true/false"):
        FileLoader.load_file(path)


@pytest.mark.parametrize("item", ['"x"', "1", "[1, 2, 3]", "null"])
def test_json_non_object_items_raise_value_error(tmp_path, item):
    path = write_json(tmp_path, f"[{item}]")
    with pytest.raises(ValueError, match="expected an object"):
        FileLoader.load_file(path)


@pytest.mark.parametrize("weight", ["NaN", "Infinity", '"nan"', '"inf"'])
def test_json_non_finite_weight_is_rejected(tmp_path, weight):
    path = write_json(tmp_path, f'[{{"date": "2025-07-01", "weight": {weight}, "calories": 2200}}]')
    with pytest.raises(ValueError, match="finite"):
        FileLoader.load_file(path)


@pytest.mark.parametrize("row", ["2025-07-01,2_0_0,2200", "2025-07-01,200,2_200"])
def test_csv_underscore_digits_are_rejected(tmp_path, row):
    p = tmp_path / "u.csv"
    p.write_text(f"date,weight,calories\n{row}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="plain number"):
        FileLoader.load_file(str(p))


# --- File size ------------------------------------------------------------

def test_oversized_file_is_rejected(tmp_path, monkeypatch):
    from src.util import file_loader
    monkeypatch.setattr(file_loader, "MAX_FILE_BYTES", 10)
    p = tmp_path / "big.csv"
    p.write_text("date,weight,calories\n2025-07-01,200,2200\n", encoding="utf-8")
    with pytest.raises(ValueError, match="too large"):
        FileLoader.load_file(str(p))


def test_default_size_limit_is_10_mb():
    from src.util import file_loader
    assert file_loader.MAX_FILE_BYTES == 10 * 1024 * 1024


# --- Weight units -----------------------------------------------------------

KG_90_5_IN_LBS = 90.5 / 0.45359237


def load_text(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return FileLoader.load_file(str(p))


@pytest.mark.parametrize("header", ["unit", "weight_unit", "Unit"])
def test_csv_unit_column_converts_kg(tmp_path, header):
    entries = load_text(tmp_path, "u.csv",
                        f"date,weight,calories,{header}\n2025-07-01,90.5,2200,kg\n2025-07-02,199,2100,lbs\n")
    assert entries[0].weight == pytest.approx(KG_90_5_IN_LBS)
    assert entries[1].weight == 199


def test_csv_blank_unit_means_lbs(tmp_path):
    entries = load_text(tmp_path, "u.csv", "date,weight,calories,unit\n2025-07-01,200,2200,\n")
    assert entries[0].weight == 200


def test_csv_weight_kg_column(tmp_path):
    entries = load_text(tmp_path, "kg.csv", "date,weight_kg,calories\n2025-07-01,90.5,2200\n")
    assert entries[0].weight == pytest.approx(KG_90_5_IN_LBS)


def test_csv_mixed_weight_and_weight_kg_columns(tmp_path):
    entries = load_text(tmp_path, "mix.csv",
                        "date,weight,weight_kg,calories\n2025-07-01,200,,2200\n2025-07-02,,90.5,2100\n")
    assert entries[0].weight == 200
    assert entries[1].weight == pytest.approx(KG_90_5_IN_LBS)


def test_json_unit_and_weight_kg_fields(tmp_path):
    data = [{"date": "2025-07-01", "weight": 90.5, "unit": "kg", "calories": 2200},
            {"date": "2025-07-02", "weight_kg": 90.5, "calories": 2200},
            {"date": "2025-07-03", "weight": 199, "weight_unit": "LBS", "calories": 2200}]
    entries = load_text(tmp_path, "u.json", json.dumps(data))
    assert [e.weight for e in entries] == pytest.approx([KG_90_5_IN_LBS, KG_90_5_IN_LBS, 199])


@pytest.mark.parametrize("text,match", [
    ("date,weight,calories,unit\n2025-07-01,200,2200,stone\n", "unknown weight unit"),
    ("date,weight,weight_kg,calories\n2025-07-01,200,90,2200\n", "not both"),
    ("date,weight_kg,calories,unit\n2025-07-01,90,2200,lbs\n", "conflicts"),
    ("date,calories,unit\n2025-07-01,2200,kg\n", "missing required field"),
])
def test_csv_unit_errors(tmp_path, text, match):
    with pytest.raises(ValueError, match=match):
        load_text(tmp_path, "bad.csv", text)


def test_json_conflicting_unit_fields_are_rejected(tmp_path):
    data = [{"date": "2025-07-01", "weight": 80, "weight_unit": "kg", "unit": "lbs", "calories": 2200}]
    with pytest.raises(ValueError, match="weight_unit 'kg' conflicts with unit 'lbs'"):
        load_text(tmp_path, "u.json", json.dumps(data))


def test_agreeing_unit_fields_are_accepted(tmp_path):
    entries = load_text(tmp_path, "u.csv", "date,weight,calories,unit,weight_unit\n2025-07-01,90.5,2200,kg,KG\n")
    assert entries[0].weight == pytest.approx(KG_90_5_IN_LBS)


@pytest.mark.parametrize("name,text", [
    ("d.csv", "date,weight,calories,unit\n2025-07-01,90.5,2200,\n2025-07-02,90,2200,lbs\n"),
    ("d.json", json.dumps([{"date": "2025-07-01", "weight": 90.5, "calories": 2200},
                           {"date": "2025-07-02", "weight": 90, "unit": "lbs", "calories": 2200}])),
])
def test_default_unit_applies_only_to_weights_without_a_unit(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    entries, unitless = FileLoader.load_file_with_unit_info(str(p), default_unit="kg")
    assert unitless == 1
    assert [e.weight for e in entries] == pytest.approx([KG_90_5_IN_LBS, 90])
    # Without a default unit, plain weights are lbs.
    assert [e.weight for e in FileLoader.load_file(str(p))] == [90.5, 90]


def test_txt_weights_use_the_default_unit(tmp_path):
    p = tmp_path / "d.txt"
    p.write_text("2025-07-01, 90.5, 2200\n", encoding="utf-8")
    entries, unitless = FileLoader.load_file_with_unit_info(str(p), default_unit="kg")
    assert unitless == 1
    assert entries[0].weight == pytest.approx(KG_90_5_IN_LBS)


def test_unit_info_counts_nothing_when_every_weight_names_its_unit(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text("date,weight_kg,calories\n2025-07-01,90.5,2200\n", encoding="utf-8")
    assert FileLoader.load_file_with_unit_info(str(p))[1] == 0
