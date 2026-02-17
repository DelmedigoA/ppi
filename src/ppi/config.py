"""Configuration loading helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_PATH = Path("config/retailers/retailers.yaml")


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML document from disk."""
    with Path(path).open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError("YAML config must be a mapping at the top level")
    return data


def get_retailers(config: dict[str, Any]) -> dict[str, Any]:
    """Support both {retailers: {...}} and direct {retailer_id: {...}} shapes."""
    retailers = config.get("retailers", config)
    if not isinstance(retailers, dict):
        raise ValueError("Retailers config must be a mapping")
    return retailers
