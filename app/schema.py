"""Định nghĩa collection, JSON Schema validator và index.

Quy ước: _id là mã nghiệp vụ (MaKH, MaSP, ...) dạng chuỗi; tên trường dùng snake_case không dấu.
Tiền tệ lưu bằng số nguyên VND (không có phần thập phân), thay cho Decimal(18,2) trong thiết kế SQL.
"""
from pymongo import ASCENDING, DESCENDING

S = {"bsonType": "string"}
S_NULL = {"bsonType": ["string", "null"]}
D = {"bsonType": "date"}
TIEN = {"bsonType": "number", "minimum": 0}
SO_LUONG = {"bsonType": "number", "minimum": 1}
MANG = {"bsonType": "array"}


def _obj(required, properties):
    """Schema thuần cho một object (dùng lồng trong mảng)."""
    return {"bsonType": "object", "required": required, "properties": properties}


def _validator(required, properties):
    """Validator cấp collection: MongoDB chỉ nhận $jsonSchema ở cấp cao nhất."""
    return {"$jsonSchema": _obj(required, properties)}


VALIDATORS = {
    "nguoidung": _validator(
        ["ten_dang_nhap", "mat_khau", "vai_tro"],
        {"ten_dang_nhap": S, "mat_khau": S, "vai_tro": S},
    ),
    "khachhang": _validator(
        ["ten_kh", "sdt"],
        {"ten_kh": S, "sdt": S, "ma_nd": S},
    ),
    "nhanvien": _validator(
        ["ten_nv"],
        {"ten_nv": S, "chuc_vu": S, "ma_nd": S},
    ),
    "sanpham": _validator(
        ["ten_sp", "don_gia"],
        {"ten_sp": S, "don_gia": TIEN, "barcode": S, "mau": MANG, "size": MANG},
    ),
    "nguyenvatlieu": _validator(
        ["ten_nvl", "so_luong_ton"],
        {"ten_nvl": S, "so_luong_ton": TIEN, "barcode": S},
    ),
    "donhang": _validator(
        ["ngay_dat", "trang_thai", "ma_kh", "chi_tiet", "tong_tien"],
        {
            "ngay_dat": D,
            "trang_thai": S,
            "ma_kh": S,
            "tong_tien": TIEN,
            "chi_tiet": {
                "bsonType": "array",
                "minItems": 1,
                "items": _obj(
                    ["ma_sp", "so_luong", "don_gia"],
                    # mau/size có thể null: đơn không phân theo màu × size
                    {"ma_sp": S, "so_luong": SO_LUONG, "don_gia": TIEN, "mau": S_NULL, "size": S_NULL},
                ),
            },
        },
    ),
    "hoadon": _validator(
        ["ngay_xuat", "tong_tien", "ma_don"],
        {"ngay_xuat": D, "tong_tien": TIEN, "ma_don": S},
    ),
    "thanhtoan": _validator(
        ["ngay_thanh_toan", "so_tien", "phuong_thuc", "ma_don"],
        {"ngay_thanh_toan": D, "so_tien": SO_LUONG, "phuong_thuc": S, "ma_don": S},
    ),
    "xacthuc": _validator(
        ["trang_thai"],
        {"trang_thai": S},
    ),
    "phieukho": _validator(
        ["loai", "ngay_lap", "chi_tiet"],
        {
            "loai": {"enum": ["NHAP", "XUAT"]},
            "ngay_lap": D,
            "chi_tiet": {
                "bsonType": "array",
                "minItems": 1,
                "items": _obj(["ma_nvl", "so_luong"], {"ma_nvl": S, "so_luong": SO_LUONG}),
            },
        },
    ),
    "bienbansuco": _validator(
        ["ngay_lap", "ly_do", "ma_don"],
        {"ngay_lap": D, "ly_do": S, "ma_don": S},
    ),
}

COLLECTIONS = list(VALIDATORS.keys())

INDEXES = {
    "nguoidung": [([("ten_dang_nhap", ASCENDING)], {"unique": True})],
    "khachhang": [([("ma_nd", ASCENDING)], {"sparse": True})],
    "sanpham": [([("barcode", ASCENDING)], {"unique": True, "sparse": True})],
    "nguyenvatlieu": [
        ([("barcode", ASCENDING)], {"unique": True, "sparse": True}),
        ([("so_luong_ton", ASCENDING)], {}),
    ],
    "donhang": [
        ([("ma_kh", ASCENDING), ("ngay_dat", DESCENDING)], {}),
        ([("ngay_dat", DESCENDING)], {}),
    ],
    "hoadon": [([("ma_don", ASCENDING)], {"unique": True})],
    "thanhtoan": [([("ma_don", ASCENDING)], {})],
    "phieukho": [([("loai", ASCENDING), ("ngay_lap", DESCENDING)], {})],
    "bienbansuco": [([("ma_don", ASCENDING)], {})],
}


def apply_schema(db):
    """Tạo (hoặc cập nhật) toàn bộ collection, validator và index. An toàn khi chạy lại."""
    existing = set(db.list_collection_names())
    for name in COLLECTIONS:
        if name in existing:
            db.command({"collMod": name, "validator": VALIDATORS[name], "validationLevel": "strict"})
        else:
            db.create_collection(name, validator=VALIDATORS[name])
        for keys, options in INDEXES.get(name, []):
            db[name].create_index(keys, **options)
    return COLLECTIONS
