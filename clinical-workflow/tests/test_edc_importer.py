import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from src.mcp_tools import edc_importer
from src.mcp_tools.edc_importer import (
    SourceParseError,
    parse_registered_edc_source,
    validate_source_metadata_artifact,
    write_source_parse_artifacts,
)
from src.runtime.review_protocol import validate_review_packet_schema


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _fake_sas_metadata(*, with_value_labels: bool = True) -> SimpleNamespace:
    label_mapping = {"AESER": {"0": "No", "1": "Yes"}} if with_value_labels else {}
    return SimpleNamespace(
        column_names=["SUBJID", "AESER"],
        column_labels=["Subject Identifier", "Serious Event?"],
        original_variable_types={"SUBJID": "$12", "AESER": "$1"},
        readstat_variable_types={"SUBJID": "string", "AESER": "string"},
        variable_storage_width={"SUBJID": 12, "AESER": 1},
        variable_to_label={"AESER": "YESNO"} if with_value_labels else {},
        value_labels={"YESNO": {"0": "No", "1": "Yes"}} if with_value_labels else {},
        variable_value_labels=label_mapping,
        file_label="Synthetic AE",
        file_encoding="UTF-8",
        file_format="sas7bdat",
        table_name="AE",
    )


def test_csv_source_metadata_and_local_preview_are_generated(tmp_path: Path) -> None:
    study = tmp_path / "study"
    source = study / "input" / "raw" / "ae.csv"
    source.parent.mkdir(parents=True)
    source.write_text("SUBJID,AETERM\n01,Headache\n02,\n", encoding="utf-8")

    parsed = parse_registered_edc_source(
        "input/raw/ae.csv",
        "csv",
        allowed_root=study,
        expected_sha256=_sha256(source),
        generated_at="2026-07-16T08:00:00+00:00",
    )

    assert parsed.source_metadata["dataset"]["row_count"] == 2
    assert parsed.source_metadata["dataset"]["column_count"] == 2
    assert parsed.source_metadata["variables"][0]["column_label"]["status"] == "unavailable"
    assert parsed.source_metadata["metadata_availability"]["value_labels"]["status"] == (
        "unavailable"
    )
    assert parsed.data_profile["missing_cells"] == 1
    assert validate_source_metadata_artifact(parsed.source_metadata) == []

    paths = write_source_parse_artifacts(
        parsed,
        study_root=study,
        output_dir="work/derived/edc",
        review_queue=".review_queue",
        preview_rows=1,
    )
    assert (study / paths["preview"]).read_text(encoding="utf-8").startswith("SUBJID,AETERM")
    packet = json.loads((study / paths["review_packet"]).read_text(encoding="utf-8"))
    assert packet["review_type"] == "source_intake"
    assert "不确认 SDTM 映射" in packet["agent_summary"]
    assert validate_review_packet_schema(packet) == []


def test_sas7bdat_preserves_labels_formats_widths_and_value_labels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    study = tmp_path / "study"
    source = _write(study / "input" / "edc" / "ae.sas7bdat", b"synthetic-sas-fixture")

    def fake_loader(source_path: Path, source_format: str, catalog_path: Path | None):
        assert source_path == source
        assert source_format == "sas7bdat"
        assert catalog_path is None
        dataframe = pd.DataFrame({"SUBJID": ["01"], "AESER": ["1"]})
        return dataframe, _fake_sas_metadata(), {"pandas": pd.__version__, "pyreadstat": "test"}

    monkeypatch.setattr(edc_importer, "_load_source_dataframe", fake_loader)
    parsed = parse_registered_edc_source(
        "input/edc/ae.sas7bdat",
        "sas7bdat",
        allowed_root=study,
        expected_sha256=_sha256(source),
        generated_at="2026-07-16T08:00:00+00:00",
    )

    aeser = parsed.source_metadata["variables"][1]
    assert aeser["column_label"]["value"] == "Serious Event?"
    assert aeser["source_format"]["value"] == "$1"
    assert aeser["storage_width"] == 1
    assert aeser["source_informat"]["status"] == "unavailable"
    assert aeser["value_labels"] == {
        "status": "available",
        "label_set": "YESNO",
        "mapping": {"0": "No", "1": "Yes"},
        "reason": None,
    }
    assert parsed.source_metadata["metadata_availability"]["value_labels"][
        "available_count"
    ] == 1
    assert validate_source_metadata_artifact(parsed.source_metadata) == []


def test_missing_catalog_is_explicit_and_value_labels_are_not_guessed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    study = tmp_path / "study"
    source = _write(study / "input" / "edc" / "ae.sas7bdat", b"synthetic-sas-fixture")

    def fake_loader(source_path: Path, source_format: str, catalog_path: Path | None):
        assert catalog_path is None
        dataframe = pd.DataFrame({"SUBJID": ["01"], "AESER": ["Y"]})
        return (
            dataframe,
            _fake_sas_metadata(with_value_labels=False),
            {"pandas": pd.__version__, "pyreadstat": "test"},
        )

    monkeypatch.setattr(edc_importer, "_load_source_dataframe", fake_loader)
    parsed = parse_registered_edc_source(
        "input/edc/ae.sas7bdat",
        "sas7bdat",
        allowed_root=study,
        expected_sha256=_sha256(source),
        catalog_file="input/edc/formats.sas7bcat",
    )

    availability = parsed.source_metadata["metadata_availability"]
    assert availability["external_format_catalog"]["status"] == "unavailable"
    assert "missing" in availability["external_format_catalog"]["reason"]
    assert availability["value_labels"]["status"] == "unavailable"
    assert parsed.source_metadata["variables"][1]["value_labels"]["mapping"] == {}
    assert {item["metadata"] for item in parsed.validation_report["gaps"]} >= {
        "external_format_catalog",
        "value_labels",
        "informats",
    }


def test_damaged_sas7bdat_fails_without_derived_artifact(tmp_path: Path) -> None:
    study = tmp_path / "study"
    source = _write(study / "input" / "edc" / "broken.sas7bdat", b"not-a-sas-file")

    with pytest.raises(SourceParseError, match="Unable to parse registered SAS7BDAT source"):
        parse_registered_edc_source(
            "input/edc/broken.sas7bdat",
            "sas7bdat",
            allowed_root=study,
            expected_sha256=_sha256(source),
        )

    assert not (study / "work").exists()


def test_source_hash_mismatch_fails_before_parse(tmp_path: Path) -> None:
    study = tmp_path / "study"
    _write(study / "input" / "edc" / "ae.sas7bdat", b"registered-source")

    with pytest.raises(SourceParseError, match="Source SHA-256 mismatch"):
        parse_registered_edc_source(
            "input/edc/ae.sas7bdat",
            "sas7bdat",
            allowed_root=study,
            expected_sha256="0" * 64,
        )


def test_source_path_cannot_escape_registered_study_root(tmp_path: Path) -> None:
    study = tmp_path / "study"
    study.mkdir()
    outside = _write(tmp_path / "outside.csv", b"SUBJID\n01\n")

    with pytest.raises(SourceParseError, match="outside the registered study root"):
        parse_registered_edc_source(
            outside,
            "csv",
            allowed_root=study,
            expected_sha256=_sha256(outside),
        )


def test_registered_format_must_match_extension(tmp_path: Path) -> None:
    study = tmp_path / "study"
    source = _write(study / "input" / "raw" / "ae.csv", b"SUBJID\n01\n")

    with pytest.raises(SourceParseError, match="does not match"):
        parse_registered_edc_source(
            "input/raw/ae.csv",
            "sas7bdat",
            allowed_root=study,
            expected_sha256=_sha256(source),
        )
