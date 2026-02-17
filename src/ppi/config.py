"""Configuration loading helpers."""

from __future__ import annotations

from copy import deepcopy
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


def _legacy_extract_fields(ret_cfg: dict[str, Any]) -> dict[str, Any]:
    """Build extract fields from legacy pricing/discount/unit_price blocks."""
    fields: dict[str, Any] = {}

    pricing = ret_cfg.get("pricing", {})
    final_price = pricing.get("final_price", {})
    if final_price.get("selectors_priority"):
        fields["final_price"] = {
            "selectors_priority": final_price["selectors_priority"],
            # Legacy behavior tolerated missing final_price.
            "optional": True,
        }

    discount = ret_cfg.get("discount")
    if discount and discount.get("selector"):
        fields["discount"] = {
            "selector": discount["selector"],
            "optional": bool(discount.get("optional", True)),
            "discounted_price_override": bool(discount.get("discounted_price_override", False)),
        }

    unit_price = ret_cfg.get("unit_price")
    if unit_price and unit_price.get("selector"):
        fields["unit_price"] = {
            "selector": unit_price["selector"],
            "optional": bool(unit_price.get("optional", True)),
        }

    return fields


def _validate_extract_fields(retailer_id: str, fields: Any) -> None:
    if not isinstance(fields, dict) or not fields:
        raise ValueError(f"Retailer '{retailer_id}' extract.fields must be a non-empty mapping")

    for field_name, spec in fields.items():
        if not isinstance(spec, dict):
            raise ValueError(f"Retailer '{retailer_id}' field '{field_name}' must be a mapping")
        has_selector = bool(spec.get("selector"))
        has_priority = bool(spec.get("selectors_priority"))
        if has_selector == has_priority:
            raise ValueError(
                f"Retailer '{retailer_id}' field '{field_name}' must define exactly one of "
                "selector or selectors_priority"
            )


def normalize_retailers(retailers: dict[str, Any]) -> dict[str, Any]:
    """Validate retailers config and append legacy extract step when needed."""
    normalized = deepcopy(retailers)
    for retailer_id, ret_cfg in normalized.items():
        flow = ret_cfg.get("flow")
        if not isinstance(flow, list):
            raise ValueError(f"Retailer '{retailer_id}' flow must be a list")

        has_extract = False
        for step in flow:
            action = step.get("action")
            if action not in {"goto", "wait_for_selector", "wait_for_timeout", "extract"}:
                raise ValueError(f"Retailer '{retailer_id}' has unsupported action '{action}'")
            if action == "extract":
                has_extract = True
                _validate_extract_fields(retailer_id, step.get("fields"))

        if not has_extract:
            legacy_fields = _legacy_extract_fields(ret_cfg)
            if legacy_fields:
                flow.append({"action": "extract", "fields": legacy_fields})

    return normalized
