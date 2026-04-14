"""Download the VTOOL/Refocus_Chart dataset snapshot from Hugging Face."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from huggingface_hub import snapshot_download


def main() -> None:
    parser = argparse.ArgumentParser(description="Download VTOOL/Refocus_Chart to a local directory.")
    parser.add_argument("--repo-id", default="VTOOL/Refocus_Chart")
    parser.add_argument("--local-dir", required=True)
    parser.add_argument("--repo-type", default="dataset")
    args = parser.parse_args()

    local_dir = Path(args.local_dir).resolve()
    snapshot_path = snapshot_download(
        repo_id=args.repo_id,
        repo_type=args.repo_type,
        local_dir=str(local_dir),
    )
    payload = {
        "repo_id": args.repo_id,
        "repo_type": args.repo_type,
        "local_dir": str(local_dir),
        "snapshot_path": snapshot_path,
        "files": sorted(path.name for path in local_dir.glob("*") if path.is_file()),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
