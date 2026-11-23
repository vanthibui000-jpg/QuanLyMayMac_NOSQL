"""Kiểm thử đăng nhập, đăng ký và phân quyền chặt chẽ cho 3 vai trò: ADMIN, NV, KH."""
from app import services
from conftest import MAT_KHAU_CU, MAT_KHAU_TEST

GIAO_HANG = {"ho_ten": "Nguyễn Văn A", "sdt": "0900000001", "dia_chi": "128 Phố Huế, Hà Nội"}


def test_cua_hang_cong_khai_khong_can_dang_nhap(tao_client):
    client = tao_client()
    for url in ["/", "/san-pham", "/san-pham/SP0001", "/gio-hang", "/dang-nhap", "/dang-ky"]:
        assert client.get(url).status_code == 200, url


def test_chua_dang_nhap_khong_vao_duoc_admin_va_tai_khoan(tao_client):
    client = tao_client()
    for url in ["/admin", "/admin/don-hang", "/admin/san-pham", "/admin/kho", "/admin/bao-cao", "/tai-khoan", "/thanh-toan"]:
        r = client.get(url)
        assert r.status_code == 302 and "/dang-nhap" in r.headers["Location"], url


def test_dang_nhap_ba_vai_tro_va_mat_khau_cu(tao_client):
    c_admin = tao_client("admin1")
    assert c_admin.get("/admin").status_code == 200
    assert c_admin.get("/admin/bao-cao").status_code == 200
    assert c_admin.get("/admin/mongodb").status_code == 200

    c_nv = tao_client("nv1")
    assert c_nv.get("/admin").status_code == 200

    c_kh = tao_client("khach1")
    assert c_kh.get("/tai-khoan").status_code == 200

    c_cu = tao_client("cu1", mat_khau=MAT_KHAU_CU)
    assert c_cu.get("/admin").status_code == 200


def test_khach_hang_khong_vao_duoc_admin_va_chi_xem_don_cua_minh(tao_client, db):
    services.dat_hang(db, "DH000001", "KH0001", [{"ma_sp": "SP0001", "mau": "Trắng", "size": "M", "so_luong": 1}], GIAO_HANG)
    services.dat_hang(db, "DH000002", "KH0002", [{"ma_sp": "SP0002", "mau": "Đen", "size": "M", "so_luong": 1}], GIAO_HANG)

    kh1 = tao_client("khach1")
    for url in ["/admin", "/admin/don-hang", "/admin/san-pham", "/admin/kho", "/admin/bao-cao", "/admin/mongodb"]:
        assert kh1.get(url).status_code == 403, url

    # Xem được đơn của chính mình, bị chặn 403 khi xem hoặc hủy đơn của KH0002
    assert kh1.get("/tai-khoan/don-hang/DH000001").status_code == 200
    assert kh1.get("/tai-khoan/don-hang/DH000002").status_code == 403
    assert kh1.post("/tai-khoan/don-hang/DH000002/huy").status_code == 403
    assert db.donhang.find_one({"_id": "DH000002"})["trang_thai"] == "CHO_XAC_NHAN"

    # Tự hủy được đơn của mình khi đang CHO_XAC_NHAN
    assert kh1.post("/tai-khoan/don-hang/DH000001/huy").status_code == 302
    assert db.donhang.find_one({"_id": "DH000001"})["trang_thai"] == "DA_HUY"


def test_nhan_vien_xu_ly_don_va_kho_nhung_khong_huy_don_khong_sua_sp_khong_bao_cao(tao_client, db):
    services.dat_hang(db, "DH000001", "KH0001", [{"ma_sp": "SP0001", "mau": "Trắng", "size": "M", "so_luong": 1}], GIAO_HANG)
    nv = tao_client("nv1")

    # Được phép: xem đơn, cập nhật đơn, nhập/xuất kho, xem SP & khách
    assert nv.get("/admin/don-hang").status_code == 200
    assert nv.post("/admin/don-hang/DH000001/cap-nhat", data={"trang_thai": "DANG_CHUAN_BI", "trang_thai_tt": "DA_THANH_TOAN"}).status_code == 302
    assert db.donhang.find_one({"_id": "DH000001"})["trang_thai"] == "DANG_CHUAN_BI"
    assert nv.get("/admin/kho").status_code == 200
    assert nv.post("/admin/kho", data={"loai": "NHAP", "bien_the": ["SP0001||Trắng||M"], "so_luong": ["5"]}).status_code == 302
    assert nv.get("/admin/san-pham").status_code == 200
    assert nv.get("/admin/khach-hang").status_code == 200

    # Bị chặn 403: hủy đơn, thêm/sửa/ngừng SP, thêm/sửa khách, báo cáo, CSV, MongoDB Explorer
    for url in ["/admin/san-pham/moi", "/admin/khach-hang/moi", "/admin/bao-cao", "/admin/bao-cao/don-hang.csv", "/admin/mongodb"]:
        assert nv.get(url).status_code == 403, url
    assert nv.post("/admin/don-hang/DH000001/huy").status_code == 403
    assert nv.post("/admin/san-pham/SP0001/trang-thai").status_code == 403
    assert nv.post("/admin/khach-hang/KH0001/trang-thai").status_code == 403
    assert nv.get("/tai-khoan").status_code == 403


def test_khach_ngung_hoat_dong_khong_dang_nhap_duoc(tao_client, db):
    db.khachhang.update_one({"_id": "KH0001"}, {"$set": {"hoat_dong": False}})
    client = tao_client()
    r = client.post("/dang-nhap", data={"ten_dang_nhap": "khach1", "mat_khau": MAT_KHAU_TEST})
    assert r.status_code == 200
    assert "ngừng hoạt động" in r.get_data(as_text=True)


def test_next_open_redirect_bi_chan(tao_client):
    client = tao_client()
    r = client.post("/dang-nhap", query_string={"next": "https://evil.example.com"},
                    data={"ten_dang_nhap": "admin1", "mat_khau": MAT_KHAU_TEST})
    assert r.status_code == 302 and "evil" not in r.headers["Location"]


def test_admin_quan_ly_tai_khoan_ca_ba_role_va_chan_nv_kh(tao_client, db):
    # NV và KH bị chặn 403 toàn bộ route quản lý tài khoản
    for role_user in ("nv1", "khach1"):
        c = tao_client(role_user)
        assert c.get("/admin/tai-khoan").status_code == 403, role_user
        assert c.get("/admin/tai-khoan/moi").status_code == 403, role_user
        assert c.post("/admin/tai-khoan/ND-nv1/trang-thai").status_code == 403, role_user

    admin = tao_client("admin1")
    html = admin.get("/admin/tai-khoan").get_data(as_text=True)
    assert "admin1" in html and "nv1" in html and "khach1" in html
    # Lọc theo vai trò NV không hiện khách hàng
    html_nv = admin.get("/admin/tai-khoan?vai_tro=NV").get_data(as_text=True)
    assert "nv1" in html_nv and "khach1" not in html_nv

    # Tạo tài khoản NV mới và KH mới (KH tự tạo đồng bộ document khachhang)
    assert admin.post("/admin/tai-khoan/moi", data={
        "ten_dang_nhap": "nvmoi", "mat_khau": "matkhau123", "ho_ten": "Nhân viên mới", "vai_tro": "NV",
    }).status_code == 302
    assert admin.post("/admin/tai-khoan/moi", data={
        "ten_dang_nhap": "khmoi", "mat_khau": "matkhau123", "ho_ten": "Khách mới",
        "vai_tro": "KH", "sdt": "0988777666", "dia_chi": "Đường mới",
    }).status_code == 302
    nd_kh = db.nguoidung.find_one({"ten_dang_nhap": "khmoi"})
    assert nd_kh is not None and db.khachhang.find_one({"ma_nd": nd_kh["_id"]})["sdt"] == "0988777666"

    # Đổi mật khẩu và nâng vai trò cho nvmoi -> đăng nhập được bằng mật khẩu mới
    nd_nv = db.nguoidung.find_one({"ten_dang_nhap": "nvmoi"})
    assert admin.post(f"/admin/tai-khoan/{nd_nv['_id']}/sua", data={
        "ho_ten": "Admin phụ", "vai_tro": "ADMIN", "mat_khau_moi": "passmoi999",
    }).status_code == 302
    assert tao_client("nvmoi", mat_khau="passmoi999").get("/admin/tai-khoan").status_code == 200

    # Khóa tài khoản nv1 -> không đăng nhập được; mở khóa -> đăng nhập lại bình thường
    admin.post("/admin/tai-khoan/ND-nv1/trang-thai")
    assert db.nguoidung.find_one({"_id": "ND-nv1"})["hoat_dong"] is False
    r_khoa = tao_client().post("/dang-nhap", data={"ten_dang_nhap": "nv1", "mat_khau": MAT_KHAU_TEST})
    assert r_khoa.status_code == 200 and "đã bị khóa" in r_khoa.get_data(as_text=True)

    admin.post("/admin/tai-khoan/ND-nv1/trang-thai")
    assert tao_client("nv1").get("/admin").status_code == 200

    # Chống tự khóa và tự hạ vai trò chính mình
    admin.post("/admin/tai-khoan/ND-admin1/trang-thai")
    assert db.nguoidung.find_one({"_id": "ND-admin1"}).get("hoat_dong") is not False
    r_ha = admin.post("/admin/tai-khoan/ND-admin1/sua", data={"ho_ten": "Admin", "vai_tro": "NV"})
    assert r_ha.status_code == 200 and db.nguoidung.find_one({"_id": "ND-admin1"})["vai_tro"] == "ADMIN"


def test_ca_ba_role_tu_sua_thong_tin_ca_nhan_va_doi_mat_khau(tao_client, db):
    # Khách vãng lai bị chuyển về đăng nhập
    guest = tao_client()
    for url in ("/ho-so", "/admin/ho-so", "/tai-khoan/ho-so"):
        r = guest.get(url)
        assert r.status_code == 302 and "/dang-nhap" in r.headers["Location"], url

    c_admin = tao_client("admin1")
    c_nv = tao_client("nv1")
    c_kh = tao_client("khach1")

    # /ho-so tự điều hướng đúng cổng theo vai trò
    assert c_admin.get("/ho-so").headers["Location"].endswith("/admin/ho-so")
    assert c_nv.get("/ho-so").headers["Location"].endswith("/admin/ho-so")
    assert c_kh.get("/ho-so").headers["Location"].endswith("/tai-khoan/ho-so")

    # Cô lập cổng chéo: KH không vào được /admin/ho-so; ADMIN & NV không vào được /tai-khoan/ho-so
    assert c_kh.get("/admin/ho-so").status_code == 403
    assert c_kh.post("/admin/ho-so", data={"form_type": "ho_so", "ho_ten": "Hack"}).status_code == 403
    assert c_admin.get("/tai-khoan/ho-so").status_code == 403
    assert c_nv.get("/tai-khoan/ho-so").status_code == 403

    # 1) ADMIN tự cập nhật hồ sơ
    r_ad = c_admin.post("/admin/ho-so", data={
        "form_type": "ho_so", "ho_ten": "Quản trị viên chính", "email": "admin.moi@shop.vn", "sdt": "0901112223",
    })
    assert r_ad.status_code == 302
    nd_ad = db.nguoidung.find_one({"_id": "ND-admin1"})
    assert nd_ad["ho_ten"] == "Quản trị viên chính"
    assert nd_ad["email"] == "admin.moi@shop.vn"
    assert nd_ad["sdt"] == "0901112223"
    assert nd_ad["vai_tro"] == "ADMIN"

    # 2) NV tự cập nhật hồ sơ và cố gửi vai_tro=ADMIN -> không thể tự nâng quyền
    r_nv = c_nv.post("/admin/ho-so", data={
        "form_type": "ho_so", "ho_ten": "Nhân viên kho 01", "email": "nv01.moi@shop.vn",
        "sdt": "0903334445", "vai_tro": "ADMIN",
    })
    assert r_nv.status_code == 302
    nd_nv = db.nguoidung.find_one({"_id": "ND-nv1"})
    assert nd_nv["ho_ten"] == "Nhân viên kho 01"
    assert nd_nv["email"] == "nv01.moi@shop.vn"
    assert nd_nv["sdt"] == "0903334445"
    assert nd_nv["vai_tro"] == "NV"

    # 3) KH tự cập nhật hồ sơ -> đồng bộ cả nguoidung & khachhang, không thể nâng vai trò
    r_kh_loi = c_kh.post("/tai-khoan/ho-so", data={
        "form_type": "ho_so", "ho_ten": "Khách hàng 01", "sdt": "abc", "dia_chi": "Khu A",
    })
    assert r_kh_loi.status_code == 200 and "Số điện thoại" in r_kh_loi.get_data(as_text=True)

    r_kh = c_kh.post("/tai-khoan/ho-so", data={
        "form_type": "ho_so", "ho_ten": "Nguyễn Minh Thư", "email": "minhthu@shop.vn",
        "sdt": "0987654321", "dia_chi": "15 Đường Hoa Mai, Khu Dân Cư Mới", "vai_tro": "ADMIN",
    })
    assert r_kh.status_code == 302
    nd_kh = db.nguoidung.find_one({"_id": "ND-khach1"})
    kh_doc = db.khachhang.find_one({"ma_nd": "ND-khach1"})
    assert nd_kh["ho_ten"] == "Nguyễn Minh Thư" and nd_kh["email"] == "minhthu@shop.vn" and nd_kh["sdt"] == "0987654321"
    assert nd_kh["vai_tro"] == "KH"
    assert kh_doc["ten_kh"] == "Nguyễn Minh Thư" and kh_doc["sdt"] == "0987654321"
    assert kh_doc["dia_chi"] == "15 Đường Hoa Mai, Khu Dân Cư Mới"

    # 4) Cả 3 vai trò tự đổi mật khẩu: từ chối sai mật khẩu cũ / không khớp, chấp nhận khi hợp lệ
    for ten_tk, client, url, mk_moi in [
        ("admin1", c_admin, "/admin/ho-so", "admin-pass-new"),
        ("nv1", c_nv, "/admin/ho-so", "nv-pass-new"),
        ("khach1", c_kh, "/tai-khoan/ho-so", "kh-pass-new"),
    ]:
        r_sai = client.post(url, data={
            "form_type": "mat_khau", "mat_khau_cu": "sai-mat-khau",
            "mat_khau_moi": mk_moi, "xac_nhan_mat_khau": mk_moi,
        })
        assert r_sai.status_code == 200 and "Mật khẩu hiện tại không đúng" in r_sai.get_data(as_text=True), ten_tk

        r_lech = client.post(url, data={
            "form_type": "mat_khau", "mat_khau_cu": MAT_KHAU_TEST,
            "mat_khau_moi": mk_moi, "xac_nhan_mat_khau": "khac-nhau-123",
        })
        assert r_lech.status_code == 200 and "không khớp" in r_lech.get_data(as_text=True), ten_tk

        r_ok = client.post(url, data={
            "form_type": "mat_khau", "mat_khau_cu": MAT_KHAU_TEST,
            "mat_khau_moi": mk_moi, "xac_nhan_mat_khau": mk_moi,
        })
        assert r_ok.status_code == 302, ten_tk

        # Đăng nhập bằng mật khẩu cũ thất bại, bằng mật khẩu mới thành công
        r_cu = tao_client().post("/dang-nhap", data={"ten_dang_nhap": ten_tk, "mat_khau": MAT_KHAU_TEST})
        assert r_cu.status_code == 200 and "Sai tên đăng nhập hoặc mật khẩu" in r_cu.get_data(as_text=True), ten_tk
        c_moi = tao_client(ten_tk, mat_khau=mk_moi)
        assert c_moi.get(url).status_code == 200, ten_tk


