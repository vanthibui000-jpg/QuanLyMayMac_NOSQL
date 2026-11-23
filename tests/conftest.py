"""Fixture dùng chung cho bộ test: CSDL maymac_test với 3 vai trò (ADMIN, NV, KH)."""
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
_HASH_TEST = generate_password_hash(MAT_KHAU_TEST, method="pbkdf2:sha256:1000")

TAI_KHOAN_TEST = [
    ("admin1", "ADMIN", _HASH_TEST, "Quản trị viên"),
    ("nv1", "NV", _HASH_TEST, "Nhân viên vận hành"),
    ("khach1", "KH", _HASH_TEST, "Nguyễn Văn A"),
    ("khach2", "KH", _HASH_TEST, "Trần Thị B"),
    ("cu1", "ADMIN", hashlib.sha256(MAT_KHAU_CU.encode()).hexdigest(), "Admin cũ"),
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

    database.danhmuc.insert_many([
        {"_id": "DM01", "ten_dm": "Áo Sơ Mi", "slug": "ao-so-mi", "mo_ta": "Sơ mi", "thu_tu": 1},
        {"_id": "DM02", "ten_dm": "Suits & Blazer", "slug": "suits-blazer", "mo_ta": "Blazer", "thu_tu": 2},
    ])
    database.nguoidung.insert_many([
        {"_id": f"ND-{ten}", "ten_dang_nhap": ten, "mat_khau": mk, "vai_tro": vt, "ho_ten": ht}
        for ten, vt, mk, ht in TAI_KHOAN_TEST
    ])
    database.khachhang.insert_many([
        {
            "_id": "KH0001", "ten_kh": "Nguyễn Văn A", "sdt": "0900000001",
            "dia_chi": "128 Phố Huế, Hà Nội", "ma_nd": "ND-khach1", "hoat_dong": True,
        },
        {
            "_id": "KH0002", "ten_kh": "Trần Thị B", "sdt": "0900000002",
            "dia_chi": "86 Đồng Khởi, TP.HCM", "ma_nd": "ND-khach2", "hoat_dong": True,
        },
    ])
    database.sanpham.insert_many([
        {
            "_id": "SP0001", "ten_sp": "Áo Sơ Mi Trắng Poplin", "ma_dm": "DM01",
            "don_gia": 800_000, "gia_goc": 1_000_000, "bo_suu_tap": "sale",
            "form_dang": "Slim Fit", "chat_lieu": "Cotton", "mo_ta": "Sơ mi cao cấp",
            "hinh_anh": ["prod_shirt_white.jpg"], "hoat_dong": True,
            "bien_the": [
                {"mau": "Trắng", "size": "M", "ton_kho": 15},
                {"mau": "Trắng", "size": "L", "ton_kho": 5},
                {"mau": "Đen", "size": "M", "ton_kho": 10},
            ],
        },
        {
            "_id": "SP0002", "ten_sp": "Áo Blazer Len Ý", "ma_dm": "DM02",
            "don_gia": 2_500_000, "gia_goc": 2_500_000, "bo_suu_tap": "moi",
            "form_dang": "Tailored Fit", "chat_lieu": "Wool", "mo_ta": "Blazer",
            "hinh_anh": ["look_blazer.jpg"], "hoat_dong": True,
            "bien_the": [
                {"mau": "Xanh navy", "size": "L", "ton_kho": 4},
                {"mau": "Đen", "size": "M", "ton_kho": 12},
            ],
        },
    ])

    yield database

    client.drop_database(TEST_DB)
    client.close()


@pytest.fixture
def tao_client(db):
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
