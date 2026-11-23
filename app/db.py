"""Kết nối MongoDB và khởi tạo replica set."""
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import OperationFailure

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DEFAULT_URI = "mongodb://localhost:27017/?replicaSet=rs0"
DEFAULT_DB = "maymac"
NOT_YET_INITIALIZED = 94  # mã lỗi MongoDB: replica set chưa được khởi tạo


def get_client(uri=None):
    return MongoClient(uri or os.getenv("MONGO_URI", DEFAULT_URI), serverSelectionTimeoutMS=5000)


def get_db(client=None, name=None):
    client = client or get_client()
    return client[name or os.getenv("MONGO_DB", DEFAULT_DB)]


def ensure_replica_set(host="localhost:27017", rs_name="rs0", timeout=30):
    """Khởi tạo replica set một lần (cần cho transaction). Trả về True nếu vừa khởi tạo.

    Dùng directConnection vì replica set chưa khởi tạo thì chưa có primary,
    client thông thường sẽ không chọn được server.
    """
    client = MongoClient(f"mongodb://{host}/?directConnection=true", serverSelectionTimeoutMS=5000)
    try:
        try:
            client.admin.command("replSetGetStatus")
            return False
        except OperationFailure as e:
            if e.code != NOT_YET_INITIALIZED:
                raise

        client.admin.command(
            "replSetInitiate",
            {"_id": rs_name, "members": [{"_id": 0, "host": host}]},
        )
        # Chờ node bầu làm primary để có thể ghi dữ liệu
        deadline = time.time() + timeout
        while time.time() < deadline:
            if client.admin.command("hello").get("isWritablePrimary"):
                return True
            time.sleep(1)
        raise TimeoutError("Replica set chưa bầu được primary sau %d giây" % timeout)
    finally:
        client.close()
