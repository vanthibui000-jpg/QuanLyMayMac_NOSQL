"""Bước 2: nạp dữ liệu mẫu quy mô lớn để demo truy vấn và đo hiệu năng.

Chạy: python scripts/02_seed.py --reset --khach 200 --sp 80 --nvl 40 --don 3000
"""
import argparse
import hashlib
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from faker import Faker  # noqa: E402

from app.db import get_client, get_db  # noqa: E402
from app.schema import apply_schema  # noqa: E402

MAU = ["Trắng", "Đen", "Xanh navy", "Đỏ", "Be", "Xám", "Xanh lá"]
SIZE = ["S", "M", "L", "XL", "XXL"]
LOAI_AO_QUAN = ["Áo thun", "Áo sơ mi", "Áo polo", "Quần jean", "Quần kaki", "Váy", "Áo khoác"]
KIEU = ["basic", "cổ tròn", "form rộng", "slimfit", "oversize", "cao cấp"]
TEN_NVL = ["Vải cotton", "Vải kaki", "Vải jean", "Vải lanh", "Vải thun", "Chỉ may",
           "Cúc áo", "Khóa kéo", "Nhãn mác", "Keo ép", "Túi đựng", "Dây treo"]
VAI_TRO_NV = ["KD", "KHO", "KT", "NV"]
PHUONG_THUC = ["TIEN_MAT", "CHUYEN_KHOAN"]
BATCH = 1000
DEMO_HASH = hashlib.sha256(b"demo-password").hexdigest()  # chỉ dùng cho dữ liệu demo


def _insert(coll, docs):
    for i in range(0, len(docs), BATCH):
        coll.insert_many(docs[i:i + BATCH], ordered=False)
    return len(docs)


def build_khach_hang(fake, n):
    nguoi_dung, khach = [], []
    for i in range(1, n + 1):
        ma = f"KH{i:04d}"
        nguoi_dung.append({
            "_id": f"ND-{ma}",
            "ten_dang_nhap": f"kh{i:04d}",
            "mat_khau": DEMO_HASH,
            "vai_tro": "KH",
        })
        khach.append({
            "_id": ma,
            "ten_kh": fake.name(),
            "sdt": fake.phone_number(),
            "ma_nd": f"ND-{ma}",
        })
    return nguoi_dung, khach


def build_nhan_vien(fake, n):
    nguoi_dung, nhan_vien = [], []
    for i in range(1, n + 1):
        ma = f"NV{i:03d}"
        nguoi_dung.append({
            "_id": f"ND-{ma}",
            "ten_dang_nhap": f"nv{i:03d}",
            "mat_khau": DEMO_HASH,
            "vai_tro": random.choice(VAI_TRO_NV),
        })
        nhan_vien.append({
            "_id": ma,
            "ten_nv": fake.name(),
            "chuc_vu": random.choice(["Nhân viên kinh doanh", "Thủ kho", "Kế toán", "Công nhân may"]),
            "ma_nd": f"ND-{ma}",
        })
    return nguoi_dung, nhan_vien


def build_san_pham(n):
    docs = []
    for i in range(1, n + 1):
        docs.append({
            "_id": f"SP{i:04d}",
            "ten_sp": f"{random.choice(LOAI_AO_QUAN)} {random.choice(KIEU)} {i:03d}",
            "don_gia": random.randrange(80_000, 400_001, 1000),
            "barcode": f"893{i:010d}",
            "mau": random.sample(MAU, k=random.randint(2, 4)),
            "size": SIZE,
        })
    return docs


def build_nvl(n):
    docs = []
    for i in range(1, n + 1):
        docs.append({
            "_id": f"NVL{i:04d}",
            "ten_nvl": TEN_NVL[(i - 1) % len(TEN_NVL)] + f" loại {i}",
            "so_luong_ton": random.randint(200, 5000),
            "barcode": f"894{i:010d}",
        })
    return docs


def build_don_hang(n_don, khach_ids, san_pham, start, end):
    don_hang, hoa_don, thanh_toan, su_co = [], [], [], []
    span = int((end - start).total_seconds())
    tt_counter = 0
    for j in range(1, n_don + 1):
        ma_don = f"DH{j:06d}"
        ngay = start + timedelta(seconds=random.randrange(span))
        chi_tiet = []
        for sp in random.sample(san_pham, k=random.randint(1, 4)):
            chi_tiet.append({
                "ma_sp": sp["_id"],
                "mau": random.choice(sp["mau"]),
                "size": random.choice(sp["size"]),
                "so_luong": random.randrange(10, 201, 10),  # đặt sỉ theo lô
                "don_gia": sp["don_gia"],
            })
        tong = sum(d["so_luong"] * d["don_gia"] for d in chi_tiet)

        r = random.random()
        if r < 0.6:
            trang_thai = "DA_THANH_TOAN"
            da_tra_list = [tong]
        elif r < 0.8:
            trang_thai = "THANH_TOAN_MOT_PHAN"
            da_tra_list = [int(tong * random.uniform(0.2, 0.8)) // 1000 * 1000]
        else:
            trang_thai = "CHO_THANH_TOAN"
            da_tra_list = []

        don_hang.append({
            "_id": ma_don,
            "ngay_dat": ngay,
            "trang_thai": trang_thai,
            "ma_kh": random.choice(khach_ids),
            "chi_tiet": chi_tiet,
            "tong_tien": tong,
        })
        hoa_don.append({"_id": f"HD{ma_don}", "ngay_xuat": ngay, "tong_tien": tong, "ma_don": ma_don})
        for so_tien in da_tra_list:
            tt_counter += 1
            thanh_toan.append({
                "_id": f"TT{tt_counter:07d}",
                "ngay_thanh_toan": ngay + timedelta(days=random.randint(0, 20)),
                "so_tien": so_tien,
                "phuong_thuc": random.choice(PHUONG_THUC),
                "ma_don": ma_don,
            })
        if random.random() < 0.02:
            su_co.append({
                "_id": f"BB{j:06d}",
                "ngay_lap": ngay,
                "ly_do": random.choice(["Thiếu hàng", "Hàng lỗi đường may", "Sai màu", "Giao trễ"]),
                "ma_don": ma_don,
            })
    return don_hang, hoa_don, thanh_toan, su_co


def main():
    parser = argparse.ArgumentParser(description="Nạp dữ liệu mẫu")
    parser.add_argument("--khach", type=int, default=200)
    parser.add_argument("--sp", type=int, default=80)
    parser.add_argument("--nvl", type=int, default=40)
    parser.add_argument("--nhanvien", type=int, default=10)
    parser.add_argument("--don", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reset", action="store_true", help="Xóa toàn bộ CSDL trước khi nạp")
    args = parser.parse_args()

    random.seed(args.seed)
    fake = Faker("vi_VN")
    Faker.seed(args.seed)

    client = get_client()
    db = get_db(client)

    if args.reset:
        client.drop_database(db.name)
        print(f"Đã xóa CSDL '{db.name}'")
    elif db.khachhang.estimated_document_count() > 0:
        sys.exit("CSDL đã có dữ liệu. Chạy lại với --reset để nạp mới.")

    apply_schema(db)

    nd_kh, khach = build_khach_hang(fake, args.khach)
    nd_nv, nhan_vien = build_nhan_vien(fake, args.nhanvien)
    san_pham = build_san_pham(args.sp)
    nvl = build_nvl(args.nvl)

    _insert(db.nguoidung, nd_kh + nd_nv)
    _insert(db.khachhang, khach)
    _insert(db.nhanvien, nhan_vien)
    _insert(db.sanpham, san_pham)
    _insert(db.nguyenvatlieu, nvl)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365)
    khach_ids = [k["_id"] for k in khach]
    don, hd, tt, bb = build_don_hang(args.don, khach_ids, san_pham, start, end)
    _insert(db.donhang, don)
    _insert(db.hoadon, hd)
    _insert(db.thanhtoan, tt)
    _insert(db.bienbansuco, bb)

    print("Đã nạp dữ liệu mẫu:")
    for name in ["nguoidung", "khachhang", "nhanvien", "sanpham", "nguyenvatlieu",
                 "donhang", "hoadon", "thanhtoan", "bienbansuco"]:
        print(f"  - {name}: {db[name].estimated_document_count()}")


if __name__ == "__main__":
    main()
