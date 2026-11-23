"""Kiểm thử end-to-end luồng mua sắm cửa hàng & CRUD quản trị qua Flask test client."""


def test_khach_vang_lai_them_gio_dang_ky_va_thanh_toan_tru_ton_kho(tao_client, db):
    client = tao_client()
    # 1. Khách vãng lai thêm 2 áo sơ mi vào giỏ
    r = client.post("/gio-hang/them", data={"ma_sp": "SP0001", "mau": "Trắng", "size": "M", "so_luong": "2"})
    assert r.status_code == 302
    assert "Áo Sơ Mi Trắng Poplin" in client.get("/gio-hang").get_data(as_text=True)

    # 2. Đăng ký tài khoản KH mới — giỏ hàng tự gộp vào MongoDB `giohang`
    r = client.post("/dang-ky?next=/thanh-toan", data={
        "ho_ten": "Lê Minh Hoàng", "ten_dang_nhap": "hoang99",
        "sdt": "0912345678", "dia_chi": "15 Nguyễn Huệ, TP.HCM", "mat_khau": "secret123",
    })
    assert r.status_code == 302 and r.headers["Location"].endswith("/thanh-toan")
    assert db.giohang.count_documents({}) == 1

    # 3. Đặt hàng thành công -> tạo donhang + hoadon, trừ tồn kho, xóa giỏ hàng
    r = client.post("/thanh-toan", data={
        "ho_ten": "Lê Minh Hoàng", "sdt": "0912345678",
        "dia_chi": "15 Nguyễn Huệ, TP.HCM", "phuong_thuc_tt": "COD",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "Đặt hàng thành công" in r.get_data(as_text=True)
    assert db.donhang.count_documents({}) == 1
    assert db.giohang.count_documents({}) == 0
    sp = db.sanpham.find_one({"_id": "SP0001"})
    ton_m = next(b["ton_kho"] for b in sp["bien_the"] if b["mau"] == "Trắng" and b["size"] == "M")
    assert ton_m == 13


def test_loc_san_pham_theo_danh_muc_mau_size_va_tim_kiem(tao_client):
    c = tao_client()
    html_dm = c.get("/san-pham?danh_muc=suits-blazer").get_data(as_text=True)
    assert "Áo Blazer Len Ý" in html_dm and "Áo Sơ Mi Trắng Poplin" not in html_dm

    html_sale = c.get("/san-pham?bo_suu_tap=sale").get_data(as_text=True)
    assert "Áo Sơ Mi Trắng Poplin" in html_sale and "Áo Blazer Len Ý" not in html_sale

    assert c.get("/san-pham?q=(").status_code == 200


def test_admin_crud_san_pham_khach_hang_va_csv(tao_client, db):
    admin = tao_client("admin1")

    # Thêm sản phẩm mới kèm biến thể Màu × Size
    r = admin.post("/admin/san-pham/moi", data={
        "ten_sp": "Quần Âu Xếp Ly Mới", "ma_dm": "DM01",
        "don_gia": "1100000", "gia_goc": "1300000", "bo_suu_tap": "moi",
        "hinh_anh": "prod_trouser_charcoal.jpg", "mau": "Đen, Xám", "size": "M, L", "ton_mac_dinh": "10",
    })
    assert r.status_code == 302
    sp = db.sanpham.find_one({"_id": "SP0003"})
    assert sp is not None and len(sp["bien_the"]) == 4

    # Ngừng bán -> ẩn khỏi cửa hàng công khai
    admin.post("/admin/san-pham/SP0003/trang-thai")
    assert db.sanpham.find_one({"_id": "SP0003"})["hoat_dong"] is False
    assert tao_client().get("/san-pham/SP0003").status_code == 404

    # Xuất CSV báo cáo
    csv_resp = admin.get("/admin/bao-cao/ton-kho.csv")
    assert csv_resp.status_code == 200 and csv_resp.mimetype == "text/csv"
    assert admin.get("/admin/bao-cao/khong-ton-tai.csv").status_code == 404
