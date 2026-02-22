from pathlib import Path

import pytest

from ppi.config import get_retailers, load_yaml, normalize_retailers
from ppi.io import OUTPUT_FIELDS, base_output_row, ensure_output_parent, open_output_writer
from ppi.targets import load_targets


def test_load_yaml_requires_mapping(tmp_path: Path):
    cfg = tmp_path / "bad.yaml"
    cfg.write_text("- just\n- a\n- list\n", encoding="utf-8")

    with pytest.raises(ValueError, match="top level"):
        load_yaml(cfg)


def test_get_retailers_rejects_non_mapping():
    with pytest.raises(ValueError, match="Retailers config must be a mapping"):
        get_retailers({"retailers": ["bad"]})


def test_normalize_retailers_validates_flow_and_actions():
    with pytest.raises(ValueError, match="flow must be a list"):
        normalize_retailers({"x": {"flow": "nope"}})

    with pytest.raises(ValueError, match="unsupported action"):
        normalize_retailers({"x": {"flow": [{"action": "click"}]}})


def test_normalize_retailers_validates_extract_fields_shape():
    with pytest.raises(ValueError, match="non-empty mapping"):
        normalize_retailers({"x": {"flow": [{"action": "extract", "fields": {}}]}})

    with pytest.raises(ValueError, match="must be a mapping"):
        normalize_retailers({"x": {"flow": [{"action": "extract", "fields": {"price": "bad"}}]}})


def test_io_helpers_and_targets_loading(tmp_path: Path):
    out_path = tmp_path / "nested" / "results.csv"
    ensure_output_parent(out_path)
    assert out_path.parent.exists()

    out_file, writer = open_output_writer(out_path)
    with out_file:
        writer.writerow(base_output_row("r1", "p1"))

    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert lines[0].split(",") == OUTPUT_FIELDS
    assert lines[1].startswith("r1,p1,")

    targets_path = tmp_path / "targets.csv"
    targets_path.write_text("retailer_id,product_id\nr1,p1\n", encoding="utf-8")
    loaded = list(load_targets(targets_path))
    assert loaded == [{"retailer_id": "r1", "product_id": "p1"}]
