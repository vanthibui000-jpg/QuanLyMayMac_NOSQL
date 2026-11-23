"""Định nghĩa 8 collection MongoDB, JSON Schema validator và index cho website bán quần áo thời trang.

Quy ước:
- _id là mã nghiệp vụ dạng chuỗi (DM01, SP0001, KH0001, DH000001, PK0001...).
- Tiền tệ lưu bằng số nguyên VND (không phần thập phân).
- Biến thể Màu × Size và tồn kho thành phẩm được NHÚNG trực tiếp vào `sanpham.bien_the[]`.
- Chi tiết đơn hàng, thông tin giao hàng, lịch sử trạng thái được NHÚNG vào `donhang`.
- Chi tiết phiếu nhập/xuất kho được NHÚNG vào `phieukho`.
"""
from pymongo import ASCENDING, DESCENDING

S = {"bsonType": "string"}
S_NULL = {"bsonType": ["string", "null"]}
D = {"bsonType": "date"}
B = {"bsonType": "bool"}
TIEN = {"bsonType": "number", "minimum": 0}
SO_LUONG = {"bsonType": "number", "minimum": 1}
TON_KHO = {"bsonType": "number", "minimum": 0}
MANG = {"bsonType": "array"}


def _obj(required, properties):
    return {"bsonType": "object", "required": required, "properties": properties}


def _validator(required, properties):
    return {"$jsonSchema": _obj(required, properties)}


VALIDATORS = {
    "nguoidung": _validator(
        ["ten_dang_nhap", "mat_khau", "vai_tro"],
        {
            "ten_dang_nhap": S,
            "mat_khau": S,
            "vai_tro": {"enum": ["ADMIN", "NV", "KH"]},
            "ho_ten": S,
            "email": S_NULL,
            "sdt": S_NULL,
            "hoat_dong": B,
        },
    ),
    "khachhang": _validator(
        ["ten_kh", "sdt"],
        {
            "ten_kh": S,
            "sdt": S,
            "dia_chi": S,
            "email": S_NULL,
            "ma_nd": S,
            "hoat_dong": B,
            "yeu_thich": {"bsonType": "array", "items": S},
            "so_dia_chi": {
                "bsonType": "array",
                "items": _obj(
                    ["id", "ho_ten", "sdt", "dia_chi"],
                    {
                        "id": S,
                        "nhan": S,
                        "ho_ten": S,
                        "sdt": S,
                        "dia_chi": S,
                        "mac_dinh": B,
                    },
                ),
            },
        },
    ),
    "danhmuc": _validator(
        ["ten_dm", "slug"],
        {
            "ten_dm": S,
            "slug": S,
            "mo_ta": S,
            "thu_tu": TIEN,
        },
    ),
    "sanpham": _validator(
        ["ten_sp", "ma_dm", "don_gia", "bien_the"],
        {
            "ten_sp": S,
            "ma_dm": S,
            "don_gia": TIEN,
            "gia_goc": TIEN,
            "bo_suu_tap": S,
            "form_dang": S,
            "chat_lieu": S,
            "mo_ta": S,
            "hinh_anh": MANG,
            "hoat_dong": B,
            "bien_the": {
                "bsonType": "array",
                "minItems": 1,
                "items": _obj(
                    ["mau", "size", "ton_kho"],
                    {"mau": S, "size": S, "ton_kho": TON_KHO},
                ),
            },
        },
    ),
    "giohang": _validator(
        ["items", "cap_nhat"],
        {
            "cap_nhat": D,
            "items": {
                "bsonType": "array",
                "items": _obj(
                    ["ma_sp", "mau", "size", "so_luong"],
                    {"ma_sp": S, "mau": S, "size": S, "so_luong": SO_LUONG},
                ),
            },
        },
    ),
    "donhang": _validator(
        ["ngay_dat", "trang_thai", "trang_thai_tt", "phuong_thuc_tt", "ma_kh", "giao_hang", "chi_tiet", "tong_tien"],
        {
            "ngay_dat": D,
            "trang_thai": {"enum": ["CHO_XAC_NHAN", "DANG_CHUAN_BI", "DANG_GIAO", "HOAN_THANH", "DA_HUY"]},
            "trang_thai_tt": {"enum": ["CHUA_THANH_TOAN", "DA_THANH_TOAN"]},
            "phuong_thuc_tt": {"enum": ["COD", "CHUYEN_KHOAN"]},
            "ma_kh": S,
            "phi_van_chuyen": TIEN,
            "tong_tien": TIEN,
            "giao_hang": _obj(
                ["ho_ten", "sdt", "dia_chi"],
                {"ho_ten": S, "sdt": S, "dia_chi": S, "ghi_chu": S},
            ),
            "chi_tiet": {
                "bsonType": "array",
                "minItems": 1,
                "items": _obj(
                    ["ma_sp", "ten_sp", "mau", "size", "so_luong", "don_gia"],
                    {
                        "ma_sp": S,
                        "ten_sp": S,
                        "mau": S,
                        "size": S,
                        "so_luong": SO_LUONG,
                        "don_gia": TIEN,
                        "hinh_anh": S,
                    },
                ),
            },
            "lich_su": MANG,
        },
    ),
    "hoadon": _validator(
        ["ngay_xuat", "tong_tien", "ma_don", "trang_thai"],
        {"ngay_xuat": D, "tong_tien": TIEN, "ma_don": S, "trang_thai": S},
    ),
    "phieukho": _validator(
        ["loai", "ngay_lap", "chi_tiet"],
        {
            "loai": {"enum": ["NHAP", "XUAT"]},
            "ngay_lap": D,
            "nguoi_lap": S,
            "ghi_chu": S,
            "chi_tiet": {
                "bsonType": "array",
                "minItems": 1,
                "items": _obj(
                    ["ma_sp", "mau", "size", "so_luong"],
                    {"ma_sp": S, "ten_sp": S, "mau": S, "size": S, "so_luong": SO_LUONG},
                ),
            },
        },
    ),
    "danhgia": _validator(
        ["ma_sp", "ma_kh", "ten_kh", "so_sao", "noi_dung", "ngay_tao"],
        {
            "ma_sp": S,
            "ma_kh": S,
            "ten_kh": S,
            "ma_don": S_NULL,
            "so_sao": {"bsonType": "number", "minimum": 1, "maximum": 5},
            "phom_dang": S,
            "noi_dung": S,
            "ngay_tao": D,
        },
    ),
}

COLLECTIONS = list(VALIDATORS.keys())

INDEXES = {
    "nguoidung": [([("ten_dang_nhap", ASCENDING)], {"unique": True})],
    "khachhang": [([("ma_nd", ASCENDING)], {"sparse": True})],
    "danhmuc": [([("slug", ASCENDING)], {"unique": True})],
    "sanpham": [
        ([("ma_dm", ASCENDING), ("hoat_dong", ASCENDING)], {}),
        ([("don_gia", ASCENDING)], {}),
        ([("bo_suu_tap", ASCENDING)], {}),
        ([("bien_the.mau", ASCENDING), ("bien_the.size", ASCENDING)], {}),
        ([("bien_the.ton_kho", ASCENDING)], {}),
    ],
    "donhang": [
        ([("ma_kh", ASCENDING), ("ngay_dat", DESCENDING)], {}),
        ([("ngay_dat", DESCENDING)], {}),
        ([("trang_thai", ASCENDING), ("ngay_dat", DESCENDING)], {}),
    ],
    "hoadon": [([("ma_don", ASCENDING)], {"unique": True})],
    "phieukho": [([("loai", ASCENDING), ("ngay_lap", DESCENDING)], {})],
    "danhgia": [
        ([("ma_sp", ASCENDING), ("ngay_tao", DESCENDING)], {}),
        ([("ma_kh", ASCENDING), ("ma_sp", ASCENDING)], {"unique": True}),
    ],
}


def apply_schema(db):
    """Tạo (hoặc cập nhật validator) toàn bộ collection và index. Chạy lại an toàn nhiều lần."""
    existing = set(db.list_collection_names())
    for name, validator in VALIDATORS.items():
        if name not in existing:
            db.create_collection(name, validator=validator)
        else:
            db.command("collMod", name, validator=validator)

    for name, idx_list in INDEXES.items():
        for keys, opts in idx_list:
            db[name].create_index(keys, **opts)

    return COLLECTIONS
