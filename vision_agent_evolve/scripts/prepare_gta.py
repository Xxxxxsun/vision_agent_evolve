"""Normalize local GTA data into the shared TaskCase schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.structured_data import normalize_gta_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize GTA benchmark data into JSONL TaskCase files.")
    parser.add_argument("--raw-data-root", required=True, help="Local root containing GTA dataset.json/toolmeta.json/image.")
    parser.add_argument("--normalized-data-root", required=True, help="Output root for normalized structured benchmark files.")
    parser.add_argument("--train-ratio", type=float, default=0.3, help="Fraction of scorable GTA cases used for train.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for train/val split.")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for quick debugging.")
    args = parser.parse_args()

    manifest = normalize_gta_dataset(
        raw_data_root=Path(args.raw_data_root),
        normalized_data_root=Path(args.normalized_data_root),
        train_ratio=args.train_ratio,
        seed=args.seed,
        limit=args.limit,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
