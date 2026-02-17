"""CLI entrypoint for the ppi scraper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ppi.config import DEFAULT_CONFIG_PATH
from ppi.io import DEFAULT_OUTPUT_PATH
from ppi.runner import run_pipeline
from ppi.targets import DEFAULT_TARGETS_PATH


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Run price pipeline")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to retailers YAML")
    parser.add_argument("--targets", default=str(DEFAULT_TARGETS_PATH), help="Path to targets CSV")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Path to output CSV")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    group.add_argument("--headed", action="store_true", help="Run browser in headed mode")
    parser.set_defaults(headless=False)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    headless = True if args.headless else False
    if args.headed:
        headless = False

    run_pipeline(
        config_path=args.config,
        targets_path=args.targets,
        output_path=args.output,
        headless=headless,
    )


if __name__ == "__main__":
    main()
