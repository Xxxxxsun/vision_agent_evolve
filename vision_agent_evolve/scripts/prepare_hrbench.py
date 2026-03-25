"""Normalize local HRBench data into the shared TaskCase schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.structured_data import normalize_hrbench_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize HRBench data into JSONL TaskCase files.")
    parser.add_argument("--raw-data-root", required=True, help="Local root containing raw HRBench files.")
    parser.add_argument("--normalized-data-root", required=True, help="Output root for normalized structured benchmark files.")
    parser.add_argument("--train-size", type=int, default=100)
    parser.add_argument("--val-size", type=int, default=700)
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for quick debugging.")
    args = parser.parse_args()

    manifest = normalize_hrbench_dataset(
        raw_data_root=Path(args.raw_data_root),
        normalized_data_root=Path(args.normalized_data_root),
        train_size=args.train_size,
        val_size=args.val_size,
        limit=args.limit,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
