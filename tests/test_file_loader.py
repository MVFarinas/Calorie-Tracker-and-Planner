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
