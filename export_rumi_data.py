#!/usr/bin/env python3
"""Export only RUMI-prefixed business data to a timestamped JSON file."""
import json
from datetime import datetime
from pathlib import Path
from server import SB, TABLES, validate_config

EXCLUDE = {"users"}  # Never export password hashes/salts by default.


def main():
    validate_config()
    output = {}
    for label, table in TABLES.items():
        if label in EXCLUDE:
            continue
        output[table] = SB.select(table, order="id.asc")
        print(f"✓ {table}: {len(output[table])} dòng")
    folder = Path(__file__).resolve().parent / "backups"
    folder.mkdir(exist_ok=True)
    path = folder / f"rumi-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nĐã lưu: {path}")
    print("Bản sao lưu không chứa bảng rumi_users hoặc mật khẩu.")


if __name__ == "__main__":
    main()
