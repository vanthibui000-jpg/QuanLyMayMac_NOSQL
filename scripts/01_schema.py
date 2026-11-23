"""Bước 1: khởi tạo replica set rs0 (nếu cần) và tạo schema, validator, index.

Chạy: python scripts/01_schema.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import ensure_replica_set, get_db  # noqa: E402
from app.schema import apply_schema  # noqa: E402


def main():
    if ensure_replica_set():
        print("Đã khởi tạo replica set rs0")
    else:
        print("Replica set rs0 đã sẵn sàng")

    db = get_db()
    names = apply_schema(db)
    print(f"Đã tạo/cập nhật {len(names)} collection trong CSDL '{db.name}':")
    for name in names:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
