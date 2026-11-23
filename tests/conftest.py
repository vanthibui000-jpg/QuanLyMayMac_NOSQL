"""Fixture dùng chung cho các test: CSDL maymac_test có dữ liệu mẫu nhỏ, tự xóa sau mỗi test."""
import hashlib
import os
import sys
from pathlib import Path

import pytest
from pymongo.errors import PyMongoError
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import get_client  # noqa: E402
from app.schema import apply_schema  # noqa: E402

TEST_DB = os.getenv("MONGO_TEST_DB", "maymac_test")

MAT_KHAU_TEST = "matkhau-test"
MAT_KHAU_CU = "matkhau-cu"
# pbkdf2 với ít vòng lặp để test chạy nhanh; chỉ dùng trong test
_HASH_TEST = generate_password_hash(MAT_KHAU_TEST, method="pbkdf2:sha256:1000")
TAI_KHOAN_TEST = [
    ("kd1", "KD", _HASH_TEST),
    ("kho1", "KHO", _HASH_TEST),
    ("kt1", "KT", _HASH_TEST),
    ("nv1", "NV", _HASH_TEST),
    ("khach1", "KH", _HASH_TEST),
    # định dạng SHA-256 không muối của dữ liệu mẫu cũ
    ("cu1", "KD", hashlib.sha256(MAT_KHAU_CU.encode()).hexdigest()),
]


@pytest.fixture
def db():
    client = get_client()
    try:
        client.admin.command("ping")
    except PyMongoError:
        pytest.skip("MongoDB chưa chạy")

    client.drop_database(TEST_DB)
    database = client[TEST_DB]
    apply_schema(database)

    database.khachhang.insert_one({"_id": "KH0001", "ten_kh": "Cửa hàng A", "sdt": "0900000001"})
    database.sanpham.insert_many([
        {"_id": "SP0001", "ten_sp": "Áo thun", "don_gia": 100_000, "mau": ["Trắng", "Đen"], "size": ["M", "L"]},
        {"_id": "SP0002", "ten_sp": "Quần jean", "don_gia": 150_000, "mau": ["Xanh navy"], "size": ["M", "L"]},
    ])
    database.nguoidung.insert_many([
        {"_id": f"ND-{ten}", "ten_dang_nhap": ten, "mat_khau": mk, "vai_tro": vt}
        for ten, vt, mk in TAI_KHOAN_TEST
    ])
    database.nguyenvatlieu.insert_one({"_id": "NVL0001", "ten_nvl": "Vải cotton", "so_luong_ton": 100})
    database.nguyenvatlieu.insert_one({"_id": "NVL0002", "ten_nvl": "Chỉ may", "so_luong_ton": 5})

    yield database

    client.drop_database(TEST_DB)
    client.close()


@pytest.fixture
def tao_client(db):
    """Trả về hàm tạo test client; truyền tên đăng nhập để đăng nhập sẵn, bỏ trống để chưa đăng nhập."""
    from app.web import create_app

    def _tao(ten=None, mat_khau=MAT_KHAU_TEST):
        app = create_app(db)
        app.config["TESTING"] = True
        client = app.test_client()
        if ten:
            r = client.post("/dang-nhap", data={"ten_dang_nhap": ten, "mat_khau": mat_khau})
            assert r.status_code == 302, f"đăng nhập {ten} thất bại"
        return client

    return _tao
