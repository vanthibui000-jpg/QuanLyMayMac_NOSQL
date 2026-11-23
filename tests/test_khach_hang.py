"""Kiểm thử nâng cấp toàn diện vai trò Khách hàng (Gói A + Gói B):
Account Hub 2 cột, Hạng thành viên, Lọc & Tìm đơn, Stepper 4 bước, Hủy kèm lý do,
Mua lại 1 click, Sổ địa chỉ, Yêu thích đồng bộ MongoDB, Đánh giá xác thực đã mua & Size Guide.
"""
from app import services

GIAO_HANG = {"ho_ten": "Nguyễn Văn A", "sdt": "0900000001", "dia_chi": "Số 10 Đường Mới"}


def test_hang_thanh_vien_tinh_dung_cac_moc():
    t0 = services.tinh_hang_thanh_vien(0)
    assert t0["ma"] == "THANH_VIEN" and t0["hang_tiep"] == "Hạng Bạc" and t0["con_thieu"] == 5_000_000

    t1 = services.tinh_hang_thanh_vien(10_000_000)
    assert t1["ma"] == "BAC" and t1["hang_tiep"] == "Hạng Vàng" and t1["phan_tram"] == 50

    t2 = services.tinh_hang_thanh_vien(20_000_000)
    assert t2["ma"] == "VANG" and t2["hang_tiep"] == "Kim Cương"

    t3 = services.tinh_hang_thanh_vien(40_000_000)
    assert t3["ma"] == "KIM_CUONG" and t3["hang_tiep"] is None and t3["phan_tram"] == 100


def test_cong_tai_khoan_loc_don_huy_kem_ly_do_va_mua_lai(tao_client, db):
    services.dat_hang(db, "DH000001", "KH0001", [{"ma_sp": "SP0001", "mau": "Trắng", "size": "M", "so_luong": 1}], GIAO_HANG)
    services.dat_hang(db, "DH000002", "KH0001", [{"ma_sp": "SP0002", "mau": "Đen", "size": "M", "so_luong": 2}], GIAO_HANG)
    db.donhang.update_one({"_id": "DH000002"}, {"$set": {"trang_thai": "HOAN_THANH", "trang_thai_tt": "DA_THANH_TOAN"}})

    c_kh = tao_client("khach1")
    html_ov = c_kh.get("/tai-khoan").get_data(as_text=True)
    assert "account-shell" in html_ov and "member-card" in html_ov
    assert "Hạng Bạc" in html_ov  # 2 * 2_500_000 = 5_000_000

    # Lọc trạng thái và tìm kiếm mã đơn
    html_ht = c_kh.get("/tai-khoan/don-hang?trang_thai=HOAN_THANH").get_data(as_text=True)
    assert "DH000002" in html_ht and "DH000001" not in html_ht
    html_q = c_kh.get("/tai-khoan/don-hang?q=DH000001").get_data(as_text=True)
    assert "DH000001" in html_q and "DH000002" not in html_q

    # Chi tiết đơn có stepper 4 bước & hủy kèm lý do
    html_ct = c_kh.get("/tai-khoan/don-hang/DH000001").get_data(as_text=True)
    assert "order-stepper" in html_ct and "cancel-modal" in html_ct
    r_huy = c_kh.post("/tai-khoan/don-hang/DH000001/huy", data={
        "ly_do": "Muốn thay đổi màu sắc hoặc kích cỡ", "ly_do_khac": "Đổi sang size L",
    })
    assert r_huy.status_code == 302
    don1 = db.donhang.find_one({"_id": "DH000001"})
    assert don1["trang_thai"] == "DA_HUY"
    assert "Đổi sang size L" in don1["lich_su"][-1]["ghi_chu"]

    # Mua lại 1 click đẩy vào giỏ hàng MongoDB và chuyển sang /gio-hang
    r_re = c_kh.post("/tai-khoan/don-hang/DH000002/mua-lai")
    assert r_re.status_code == 302 and r_re.headers["Location"].endswith("/gio-hang")
    gio = services.lay_gio_hang(db, "KH0001")
    assert len(gio) == 1 and gio[0]["ma_sp"] == "SP0002" and gio[0]["so_luong"] == 2

    # Cô lập: khách 2 không thể mua lại đơn của khách 1
    assert tao_client("khach2").post("/tai-khoan/don-hang/DH000002/mua-lai").status_code == 403


def test_so_dia_chi_crud_va_chon_nhanh_tai_thanh_toan(tao_client, db):
    c_kh = tao_client("khach1")
    r_add = c_kh.post("/tai-khoan/dia-chi", data={
        "nhan": "Công ty", "ho_ten": "Nguyễn Văn A", "sdt": "0912345678",
        "dia_chi": "Tầng 9, Tòa Nhà Văn Phòng Mới", "mac_dinh": "1",
    })
    assert r_add.status_code == 302
    kh = db.khachhang.find_one({"_id": "KH0001"})
    assert len(kh["so_dia_chi"]) == 2
    assert kh["dia_chi"] == "Tầng 9, Tòa Nhà Văn Phòng Mới"

    id_cty = next(d["id"] for d in kh["so_dia_chi"] if d["nhan"] == "Công ty")
    id_cu = next(d["id"] for d in kh["so_dia_chi"] if d["id"] != id_cty)

    # Đặt địa chỉ cũ làm mặc định lại
    assert c_kh.post(f"/tai-khoan/dia-chi/{id_cu}/mac-dinh").status_code == 302
    kh_after = db.khachhang.find_one({"_id": "KH0001"})
    assert next(d for d in kh_after["so_dia_chi"] if d["id"] == id_cu)["mac_dinh"] is True

    # Thanh toán hiển thị các thẻ chọn nhanh sổ địa chỉ
    services.them_vao_gio(db, "KH0001", "SP0001", "Trắng", "M", 1)
    tt_html = c_kh.get("/thanh-toan").get_data(as_text=True)
    assert "data-pick-addr" in tt_html and "Tầng 9, Tòa Nhà Văn Phòng Mới" in tt_html

    # Xóa địa chỉ công ty
    assert c_kh.post(f"/tai-khoan/dia-chi/{id_cty}/xoa").status_code == 302
    assert len(db.khachhang.find_one({"_id": "KH0001"})["so_dia_chi"]) == 1


def test_yeu_thich_mongodb_va_gop_tu_vang_lai_va_chan_noi_bo(tao_client, db):
    guest = tao_client()
    r1 = guest.post("/api/yeu-thich", json={"ma_sp": "SP0001"})
    assert r1.status_code == 200 and r1.get_json() == {"ok": True, "saved": True, "count": 1}
    assert "Áo Sơ Mi Trắng Poplin" in guest.get("/yeu-thich").get_data(as_text=True)

    # Đăng nhập KH -> tự gộp SP0001 vào khachhang.yeu_thich trong MongoDB
    assert guest.post("/dang-nhap", data={"ten_dang_nhap": "khach1", "mat_khau": "matkhau-test"}).status_code == 302
    assert "SP0001" in db.khachhang.find_one({"_id": "KH0001"}).get("yeu_thich", [])

    # KH thêm SP0002, xem trang /tai-khoan/yeu-thich, rồi bỏ SP0001
    r2 = guest.post("/api/yeu-thich", json={"ma_sp": "SP0002"})
    assert r2.get_json() == {"ok": True, "saved": True, "count": 2}
    yt_html = guest.get("/tai-khoan/yeu-thich").get_data(as_text=True)
    assert "Áo Sơ Mi Trắng Poplin" in yt_html and "Áo Blazer Len Ý" in yt_html
    assert guest.post("/tai-khoan/yeu-thich/SP0001/xoa").status_code == 302
    assert db.khachhang.find_one({"_id": "KH0001"})["yeu_thich"] == ["SP0002"]

    # Nội bộ (ADMIN & NV) bị chặn 403 toàn bộ các trang tài khoản KH và API yêu thích
    for role in ("admin1", "nv1"):
        c = tao_client(role)
        assert c.post("/api/yeu-thich", json={"ma_sp": "SP0001"}).status_code == 403, role
        for url in ("/tai-khoan/don-hang", "/tai-khoan/dia-chi", "/tai-khoan/yeu-thich", "/tai-khoan/danh-gia"):
            assert c.get(url).status_code == 403, (role, url)


def test_danh_gia_xac_thuc_chi_cho_don_hoan_thanh_va_bang_size(tao_client, db):
    c_kh = tao_client("khach1")

    # Chưa mua SP0001 -> bị từ chối đánh giá
    r_chua = c_kh.post("/san-pham/SP0001/danh-gia", data={"so_sao": "5", "noi_dung": "Rất đẹp và vừa vặn!"})
    assert r_chua.status_code == 302
    assert db.danhgia.count_documents({}) == 0

    # Đặt hàng nhưng mới ở CHO_XAC_NHAN -> vẫn chưa được đánh giá
    services.dat_hang(db, "DH000010", "KH0001", [{"ma_sp": "SP0001", "mau": "Trắng", "size": "M", "so_luong": 1}], GIAO_HANG)
    c_kh.post("/san-pham/SP0001/danh-gia", data={"so_sao": "5", "noi_dung": "Rất đẹp và vừa vặn!"})
    assert db.danhgia.count_documents({}) == 0

    # Hoàn thành đơn -> gửi đánh giá thành công, hiện trên trang chi tiết SP và /tai-khoan/danh-gia
    db.donhang.update_one({"_id": "DH000010"}, {"$set": {"trang_thai": "HOAN_THANH"}})
    assert "DH000010" in c_kh.get("/tai-khoan/danh-gia").get_data(as_text=True)

    r_ok = c_kh.post("/san-pham/SP0001/danh-gia", data={
        "so_sao": "5", "phom_dang": "Vừa vặn", "noi_dung": "Chất vải mát, lên phom chuẩn đẹp!",
    })
    assert r_ok.status_code == 302
    assert db.danhgia.count_documents({"ma_sp": "SP0001", "ma_kh": "KH0001"}) == 1

    # Cập nhật lại đánh giá -> upsert không tạo trùng bản ghi
    c_kh.post("/san-pham/SP0001/danh-gia", data={
        "so_sao": "4", "phom_dang": "Hơi rộng", "noi_dung": "Mặc rất thoải mái, vải đứng dáng.",
    })
    assert db.danhgia.count_documents({"ma_sp": "SP0001", "ma_kh": "KH0001"}) == 1
    assert db.danhgia.find_one({"ma_sp": "SP0001", "ma_kh": "KH0001"})["so_sao"] == 4

    sp_html = c_kh.get("/san-pham/SP0001").get_data(as_text=True)
    assert "Đã mua hàng" in sp_html and "Mặc rất thoải mái, vải đứng dáng." in sp_html
    assert 'id="size-guide-modal"' in sp_html and "Bảng hướng dẫn chọn Size" in sp_html
    assert 'data-wish="SP0001"' in sp_html


def test_header_dropdown_khach_hang_va_gio_hang_nang_cap(tao_client, db):
    services.them_vao_gio(db, "KH0001", "SP0001", "Trắng", "M", 1)
    c_kh = tao_client("khach1")
    html = c_kh.get("/gio-hang").get_data(as_text=True)
    assert 'id="store-acc-dropdown"' in html
    assert 'href="/tai-khoan/yeu-thich"' in html
    assert 'class="cart-stepper"' in html
    assert 'class="freeship-box ok"' in html
