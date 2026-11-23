"""Bước 2: nạp dữ liệu mẫu cửa hàng thời trang ATELIER V (3 vai trò: ADMIN, NV, KH).

Chạy: python scripts/02_seed.py --reset
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
from app.services import tinh_phi_ship  # noqa: E402

DEMO_HASH = hashlib.sha256(b"demo-password").hexdigest()

DANH_MUC = [
    {"_id": "DM01", "ten_dm": "Áo Sơ Mi", "slug": "ao-so-mi", "mo_ta": "Sơ mi công sở & linen cao cấp chuẩn phom Á Đông", "thu_tu": 1},
    {"_id": "DM02", "ten_dm": "Suits & Blazer", "slug": "suits-blazer", "mo_ta": "Vest và Blazer may đo tinh xảo từ len dạ Ý", "thu_tu": 2},
    {"_id": "DM03", "ten_dm": "Áo Khoác & Măng Tô", "slug": "ao-khoac", "mo_ta": "Măng tô, Overcoat và Bomber kiến trúc Thu Đông", "thu_tu": 3},
    {"_id": "DM04", "ten_dm": "Quần Âu & Kaki", "slug": "quan-au", "mo_ta": "Quần tây xếp ly, Slim Fit & Regular Fit đứng phom", "thu_tu": 4},
    {"_id": "DM05", "ten_dm": "Thời Trang Nữ", "slug": "thoi-trang-nu", "mo_ta": "Đầm xếp ly và thiết kế tối giản thanh lịch", "thu_tu": 5},
]

# 18 sản phẩm thời trang với ảnh thật đã tuyển chọn trong app/static/img/
SAN_PHAM_MAU = [
    ("SP0001", "Áo Blazer Len Kẻ Ô Milano", "DM02", 2_890_000, 3_450_000, "sale", "Tailored Fit", "Len Wool Ý 80%, Viscose 20%",
     "Thiết kế blazer hai nút chuẩn mực với đường vai sắc nét và lót lụa thoáng khí.",
     ["look_blazer.jpg", "look_blazer_detail.jpg"], ["Xanh navy", "Đen", "Xám"]),
    ("SP0002", "Bộ Suit 3 Mảnh Kẻ Caro Xanh", "DM02", 4_650_000, 4_650_000, "moi", "Slim Fit", "Wool Super 120s cao cấp",
     "Bộ suit gồm áo vest, gile và quần âu đồng bộ, lý tưởng cho sự kiện trang trọng.",
     ["prod_suit_navy.jpg", "look_formal_bw.jpg"], ["Xanh navy", "Xám"]),
    ("SP0003", "Áo Khoác Overcoat Đen Tuyền", "DM03", 3_290_000, 3_990_000, "sale", "Regular Fit", "Dạ len ép 2 lớp giữ ấm",
     "Áo khoác dáng dài tối giản với ve cổ chữ V cổ điển, tôn dáng mạnh mẽ mùa Thu Đông.",
     ["look_overcoat.jpg", "look_trouser_detail.jpg"], ["Đen", "Xám"]),
    ("SP0004", "Áo Măng Tô Trench Coat Be Cổ Điển", "DM03", 2_690_000, 3_200_000, "sale", "Regular Fit", "Gabardine Cotton trượt nước",
     "Thiết kế hai hàng khuy kèm đai thắt eo sắc sảo, phù hợp cả công sở lẫn dạo phố.",
     ["prod_trench_beige.jpg", "look_trench.jpg"], ["Be", "Xanh rêu", "Đen"]),
    ("SP0005", "Áo Măng Tô Dạ Olive Kiến Trúc", "DM03", 3_150_000, 3_150_000, "moi", "Relaxed Fit", "Len dạ Merino pha Cashmere",
     "Phom dáng bay bổng, gam xanh olive trầm sang trọng trong BST Fall-Winter 2026.",
     ["look_trench.jpg", "look_trench_detail.jpg"], ["Xanh rêu", "Be"]),
    ("SP0006", "Áo Sơ Mi Trắng Poplin Không Nhăn", "DM01", 890_000, 890_000, "moi", "Slim Fit", "100% Cotton Ai Cập chống nhăn",
     "Cổ áo dựng phom chuẩn mực, bề mặt mịn mượt tự nhiên suốt 12 giờ làm việc.",
     ["prod_shirt_white.jpg", "look_shirt_city.jpg"], ["Trắng", "Xanh navy"]),
    ("SP0007", "Áo Sơ Mi Công Sở Oxford Cao Cấp", "DM01", 750_000, 950_000, "sale", "Regular Fit", "Cotton Oxford dệt thoáng khí",
     "Sơ mi trắng tinh giản kết hợp dễ dàng cùng quần âu đen và đồng hồ dây da.",
     ["look_shirt_city.jpg", "prod_shirt_white.jpg"], ["Trắng", "Be", "Đen"]),
    ("SP0008", "Áo Sơ Mi Linen Tự Nhiên Atelier", "DM01", 980_000, 980_000, "moi", "Relaxed Fit", "100% Linen sợi dài Châu Âu",
     "Chất liệu linen mộc mát nhẹ, thấm hút tối ưu cho những chuyến công tác và nghỉ dưỡng.",
     ["look_linen_rack.jpg", "prod_shirt_white.jpg"], ["Trắng", "Be", "Xám"]),
    ("SP0009", "Quần Âu Xếp Ly Xám Than", "DM04", 1_190_000, 1_450_000, "sale", "Tailored Fit", "Wool Blend co giãn 4 chiều",
     "Đường ly giữa sắc nét, cạp ẩn tinh tế giúp kéo dài tỷ lệ đôi chân lịch lãm.",
     ["prod_trouser_charcoal.jpg", "look_trouser_detail.jpg"], ["Xám", "Đen", "Xanh navy"]),
    ("SP0010", "Quần Tây Đen Dáng Đứng Minimal", "DM04", 1_250_000, 1_250_000, "moi", "Slim Fit", "Poly-Rayon cao cấp giữ ly",
     "Lựa chọn nền tảng trong tủ đồ quý ông, dễ phối cùng áo cổ lọ, sơ mi và blazer.",
     ["look_trouser_detail.jpg", "prod_trouser_charcoal.jpg"], ["Đen", "Xám"]),
    ("SP0011", "Áo Khoác Bomber Tối Giản Cam Đất", "DM03", 1_490_000, 1_890_000, "sale", "Regular Fit", "Polyester Microfiber chống gió",
     "Khóa kéo kim loại nguyên khối cùng bo cổ dệt chắc chắn, trẻ trung và gọn gàng.",
     ["prod_bomber_terra.jpg", "look_camel_coat.jpg"], ["Cam đất", "Đen", "Xanh navy"]),
    ("SP0012", "Áo Khoác Dạ Camel Smart Casual", "DM03", 2_450_000, 2_450_000, "moi", "Regular Fit", "Len dạ chải mịn 600gsm",
     "Tông nâu camel ấm áp dễ phối layer với áo thun trắng và quần sáng màu.",
     ["look_camel_coat.jpg", "prod_trench_beige.jpg"], ["Nâu", "Be", "Đen"]),
    ("SP0013", "Áo Blazer Tối Giản Cổ Điển Đen", "DM02", 2_590_000, 2_590_000, "moi", "Regular Fit", "Wool Gabardine đứng phom",
     "Đường cắt vai tự nhiên, phù hợp từ phòng họp đến những buổi gặp gỡ đối tác.",
     ["look_blazer_detail.jpg", "look_blazer.jpg"], ["Đen", "Xanh navy"]),
    ("SP0014", "Bộ Vest Tuxedo Monochrome", "DM02", 5_200_000, 5_900_000, "sale", "Slim Fit", "Wool pha lụa Satin ve cổ",
     "Dành cho tiệc tối trang trọng với độ rủ hoàn hảo và phom ôm gọn vai.",
     ["look_formal_bw.jpg", "prod_suit_navy.jpg"], ["Đen"]),
    ("SP0015", "Đầm Midi Xếp Ly Lụa Xanh Olive", "DM05", 1_850_000, 1_850_000, "moi", "Regular Fit", "Lụa Satin mờ xếp ly vĩnh viễn",
     "Cổ sơ mi thanh lịch kèm thắt lưng đồng bộ, tạo độ rủ mềm mại theo từng bước đi.",
     ["prod_dress_olive.jpg", "look_evening.jpg"], ["Xanh rêu", "Be"]),
    ("SP0016", "Đầm Dạ Tiệc Cổ Yếm Đen Atelier", "DM05", 2_390_000, 2_790_000, "sale", "Slim Fit", "Nhung lụa cao cấp co giãn nhẹ",
     "Thiết kế cổ yếm tối giản sang trọng, tôn trọn đường nét thanh thoát buổi tiệc tối.",
     ["look_evening.jpg", "prod_dress_olive.jpg"], ["Đen", "Đỏ đô"]),
    ("SP0017", "Quần Kaki Công Sở Chuẩn Phom", "DM04", 890_000, 1_050_000, "sale", "Regular Fit", "98% Cotton Twill, 2% Spandex",
     "Mềm mại, đứng dáng và ít bám bụi, thích hợp mặc hằng ngày cả tuần.",
     ["prod_trouser_charcoal.jpg", "look_blazer.jpg"], ["Be", "Xám", "Xanh navy"]),
    ("SP0018", "Áo Sơ Mi Linen Cổ Trụ Đương Đại", "DM01", 850_000, 850_000, "thuong", "Regular Fit", "Linen pha Cotton thoáng mát",
     "Thiết kế tối giản không cổ gập, dễ mặc trong mọi hoàn cảnh thường nhật.",
     ["look_linen_rack.jpg", "look_shirt_city.jpg"], ["Trắng", "Be"]),
]

SIZES = ["S", "M", "L", "XL"]
DIA_CHI_MAU = [
    "128 Phố Huế, Hai Bà Trưng, Hà Nội",
    "86 Đồng Khởi, Quận 1, TP. Hồ Chí Minh",
    "45 Trần Phú, Hải Châu, Đà Nẵng",
    "210 Cầu Giấy, Quận Cầu Giấy, Hà Nội",
    "15 Nguyễn Huệ, Quận 1, TP. Hồ Chí Minh",
    "72 Lê Lợi, TP. Huế",
]


def build_users_and_customers(fake, n_khach):
    nguoi_dung = [
        {
            "_id": "ND-ADMIN",
            "ten_dang_nhap": "admin",
            "mat_khau": DEMO_HASH,
            "vai_tro": "ADMIN",
            "ho_ten": "Quản trị viên hệ thống",
            "email": "admin@shop.vn",
            "hoat_dong": True,
        },
        {
            "_id": "ND-NV001",
            "ten_dang_nhap": "nv001",
            "mat_khau": DEMO_HASH,
            "vai_tro": "NV",
            "ho_ten": "Nguyễn Minh Anh",
            "email": "nv001@shop.vn",
            "hoat_dong": True,
        },
        {
            "_id": "ND-NV002",
            "ten_dang_nhap": "nv002",
            "mat_khau": DEMO_HASH,
            "vai_tro": "NV",
            "ho_ten": "Trần Quốc Bảo",
            "email": "nv002@shop.vn",
            "hoat_dong": True,
        },
    ]
    khach_hang = []
    for i in range(1, n_khach + 1):
        ma = f"KH{i:04d}"
        ho_ten = fake.name()
        ma_nd = f"ND-{ma}"
        nguoi_dung.append({
            "_id": ma_nd,
            "ten_dang_nhap": f"kh{i:04d}",
            "mat_khau": DEMO_HASH,
            "vai_tro": "KH",
            "ho_ten": ho_ten,
            "email": f"kh{i:04d}@example.vn",
        })
        khach_hang.append({
            "_id": ma,
            "ten_kh": ho_ten,
            "sdt": f"09{random.randint(10000000, 99999999)}",
            "dia_chi": random.choice(DIA_CHI_MAU),
            "email": f"kh{i:04d}@example.vn",
            "ma_nd": ma_nd,
            "hoat_dong": True,
        })
    return nguoi_dung, khach_hang


def build_san_pham():
    docs = []
    for idx, row in enumerate(SAN_PHAM_MAU):
        ma, ten, dm, gia, gia_goc, bst, form, chat_lieu, mo_ta, imgs, maus = row
        bien_the = []
        for m_i, m in enumerate(maus):
            for s_i, s in enumerate(SIZES):
                # Giữ vài biến thể tồn kho thấp (<10) để cảnh báo tồn kho có dữ liệu thật
                ton = random.randint(2, 7) if (idx % 4 == 0 and m_i == 0 and s_i == 0) else random.randint(12, 48)
                bien_the.append({"mau": m, "size": s, "ton_kho": ton})
        docs.append({
            "_id": ma,
            "ten_sp": ten,
            "ma_dm": dm,
            "don_gia": gia,
            "gia_goc": gia_goc,
            "bo_suu_tap": bst,
            "form_dang": form,
            "chat_lieu": chat_lieu,
            "mo_ta": mo_ta,
            "hinh_anh": imgs,
            "bien_the": bien_the,
            "hoat_dong": True,
        })
    return docs


def build_don_hang(n_don, khach_hang, san_pham, start, end):
    don_hang, hoa_don = [], []
    span = int((end - start).total_seconds())
    for j in range(1, n_don + 1):
        ma_don = f"DH{j:06d}"
        ngay = start + timedelta(seconds=random.randrange(span))
        kh = khach_hang[0] if j <= 6 else random.choice(khach_hang)
        chi_tiet = []
        for sp in random.sample(san_pham, k=random.randint(1, 3)):
            bt = random.choice(sp["bien_the"])
            chi_tiet.append({
                "ma_sp": sp["_id"],
                "ten_sp": sp["ten_sp"],
                "mau": bt["mau"],
                "size": bt["size"],
                "so_luong": random.randint(1, 3),
                "don_gia": sp["don_gia"],
                "hinh_anh": sp["hinh_anh"][0],
            })
        tam_tinh = sum(d["so_luong"] * d["don_gia"] for d in chi_tiet)
        phi_ship = tinh_phi_ship(tam_tinh)
        tong = tam_tinh + phi_ship
        pttt = random.choice(["COD", "CHUYEN_KHOAN"])

        r = random.random()
        if j == 1:
            tt = "CHO_XAC_NHAN"
            tt_tt = "CHUA_THANH_TOAN"
        elif r < 0.62:
            tt = "HOAN_THANH"
            tt_tt = "DA_THANH_TOAN"
        elif r < 0.76:
            tt = "DANG_GIAO"
            tt_tt = "DA_THANH_TOAN" if pttt == "CHUYEN_KHOAN" else "CHUA_THANH_TOAN"
        elif r < 0.86:
            tt = "DANG_CHUAN_BI"
            tt_tt = "DA_THANH_TOAN" if pttt == "CHUYEN_KHOAN" else "CHUA_THANH_TOAN"
        elif r < 0.94:
            tt = "CHO_XAC_NHAN"
            tt_tt = "CHUA_THANH_TOAN"
        else:
            tt = "DA_HUY"
            tt_tt = "CHUA_THANH_TOAN"

        lich_su = [{"thoi_gian": ngay, "trang_thai": "CHO_XAC_NHAN", "ghi_chu": "Khách hàng đặt đơn trực tuyến"}]
        if tt != "CHO_XAC_NHAN":
            lich_su.append({"thoi_gian": ngay + timedelta(hours=3), "trang_thai": tt, "ghi_chu": f"Cập nhật trạng thái {tt}"})

        don_hang.append({
            "_id": ma_don,
            "ngay_dat": ngay,
            "trang_thai": tt,
            "trang_thai_tt": tt_tt,
            "phuong_thuc_tt": pttt,
            "ma_kh": kh["_id"],
            "giao_hang": {
                "ho_ten": kh["ten_kh"],
                "sdt": kh["sdt"],
                "dia_chi": kh["dia_chi"],
                "ghi_chu": "",
            },
            "chi_tiet": chi_tiet,
            "phi_van_chuyen": phi_ship,
            "tong_tien": tong,
            "lich_su": lich_su,
        })
        hoa_don.append({
            "_id": f"HD{ma_don}",
            "ngay_xuat": ngay,
            "tong_tien": tong,
            "ma_don": ma_don,
            "trang_thai": tt,
        })
    return don_hang, hoa_don


def build_phieu_kho(n_phieu, san_pham, start, end):
    phieu = []
    span = int((end - start).total_seconds())
    for i in range(1, n_phieu + 1):
        loai = "NHAP" if i % 3 != 0 else "XUAT"
        chi_tiet = []
        for sp in random.sample(san_pham, k=random.randint(1, 3)):
            bt = random.choice(sp["bien_the"])
            chi_tiet.append({
                "ma_sp": sp["_id"],
                "ten_sp": sp["ten_sp"],
                "mau": bt["mau"],
                "size": bt["size"],
                "so_luong": random.randint(5, 25),
            })
        phieu.append({
            "_id": f"PK{i:04d}",
            "loai": loai,
            "ngay_lap": start + timedelta(seconds=random.randrange(span)),
            "nguoi_lap": random.choice(["admin", "nv001", "nv002"]),
            "ghi_chu": "Nhập lô hàng mới từ xưởng" if loai == "NHAP" else "Xuất bổ sung showroom",
            "chi_tiet": chi_tiet,
        })
    return phieu


def build_danh_gia(don_hang, khach_hang):
    """Tạo đánh giá xác thực (đã mua hàng) từ các đơn HOAN_THANH."""
    kh_map = {k["_id"]: k["ten_kh"] for k in khach_hang}
    mau_nhan_xet = [
        (5, "Vừa vặn", "Chất vải mịn thoáng, đường may sắc nét và lên phom rất đứng dáng."),
        (5, "Vừa vặn", "Đóng gói chỉn chu, mặc đi làm cả ngày vẫn giữ nếp gọn gàng, đúng như mô tả."),
        (4, "Vừa vặn", "Màu sắc bên ngoài sang và đúng tông, giao hàng nhanh, sẽ ủng hộ thêm."),
        (5, "Hơi rộng", "Phom thoải mái, chất liệu tự nhiên mát nhẹ, dễ phối nhiều phong cách."),
        (4, "Hơi chật", "Chất vải tốt, vai áo gọn đẹp; ai thích mặc rộng nên tăng thêm 1 size."),
    ]
    da_co = set()
    kq = []
    stt = 1
    for d in don_hang:
        if d["trang_thai"] != "HOAN_THANH":
            continue
        for ct in d["chi_tiet"]:
            key = (d["ma_kh"], ct["ma_sp"])
            if key in da_co:
                continue
            if len(kq) >= 45:
                return kq
            if random.random() > 0.25:
                continue
            da_co.add(key)
            sao, phom, nd = random.choice(mau_nhan_xet)
            kq.append({
                "_id": f"DG{stt:05d}",
                "ma_sp": ct["ma_sp"],
                "ma_kh": d["ma_kh"],
                "ten_kh": kh_map.get(d["ma_kh"], "Khách hàng"),
                "ma_don": d["_id"],
                "so_sao": sao,
                "phom_dang": phom,
                "noi_dung": nd,
                "ngay_tao": d["ngay_dat"] + timedelta(days=random.randint(3, 12)),
            })
            stt += 1
    return kq


def main():
    parser = argparse.ArgumentParser(description="Nạp dữ liệu mẫu shop thời trang ATELIER V")
    parser.add_argument("--khach", type=int, default=50)
    parser.add_argument("--don", type=int, default=600)
    parser.add_argument("--phieu", type=int, default=24)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    random.seed(args.seed)
    fake = Faker("vi_VN")
    Faker.seed(args.seed)

    client = get_client()
    db = get_db(client)

    if args.reset:
        client.drop_database(db.name)
        print(f"Đã xóa CSDL '{db.name}'")
    elif db.sanpham.estimated_document_count() > 0:
        sys.exit("CSDL đã có dữ liệu. Chạy lại với --reset để nạp mới.")

    apply_schema(db)

    nguoi_dung, khach_hang = build_users_and_customers(fake, args.khach)
    san_pham = build_san_pham()

    db.danhmuc.insert_many(DANH_MUC)
    db.nguoidung.insert_many(nguoi_dung)
    db.khachhang.insert_many(khach_hang)
    db.sanpham.insert_many(san_pham)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=330)
    don, hd = build_don_hang(args.don, khach_hang, san_pham, start, end)
    phieu = build_phieu_kho(args.phieu, san_pham, start, end)
    danh_gia = build_danh_gia(don, khach_hang)

    db.donhang.insert_many(don)
    db.hoadon.insert_many(hd)
    db.phieukho.insert_many(phieu)
    if danh_gia:
        db.danhgia.insert_many(danh_gia)

    print("Đã nạp dữ liệu mẫu thành công:")
    for name in ["danhmuc", "nguoidung", "khachhang", "sanpham", "donhang", "hoadon", "phieukho", "giohang", "danhgia"]:
        print(f"  - {name}: {db[name].count_documents({})}")
    print("\nTài khoản demo (mật khẩu chung: demo-password):")
    print("  - ADMIN : admin")
    print("  - NV    : nv001, nv002")
    print("  - KH    : kh0001 .. kh0050")


if __name__ == "__main__":
    main()
