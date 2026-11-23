"""Kiểm thử đăng nhập và phân quyền theo vai trò (KD, KHO, KT, NV; KH bị chặn)."""
from app import services

from conftest import MAT_KHAU_CU, MAT_KHAU_TEST


def _du_lieu_don(ma_kh="KH0001"):
    return {"ma_kh": ma_kh, "ma_sp": ["SP0001"], "mau": ["Trắng"], "size": ["M"], "so_luong": ["5"]}


def _tao_don(db, ma="DH0001"):
    services.dat_hang(db, ma, "KH0001", [{"ma_sp": "SP0001", "so_luong": 2, "mau": None, "size": None}])


# ---------- Đăng nhập ----------

def test_chua_dang_nhap_bi_chuyen_ve_trang_dang_nhap(tao_client):
    client = tao_client()
    for url in ["/", "/don-hang", "/san-pham", "/bao-cao", "/kho"]:
        r = client.get(url)
        assert r.status_code == 302, url
        assert "/dang-nhap" in r.headers["Location"], url


def test_post_khi_chua_dang_nhap_khong_ghi_du_lieu(tao_client, db):
    client = tao_client()
    r = client.post("/don-hang/moi", data=_du_lieu_don())
    assert r.status_code == 302 and "/dang-nhap" in r.headers["Location"]
    assert db.donhang.count_documents({}) == 0


def test_trang_dang_nhap_mo_duoc_khi_chua_dang_nhap(tao_client):
    assert tao_client().get("/dang-nhap").status_code == 200


def test_dang_nhap_dung_mat_khau(tao_client):
    client = tao_client()
    r = client.post("/dang-nhap", data={"ten_dang_nhap": "kd1", "mat_khau": MAT_KHAU_TEST})
    assert r.status_code == 302
    assert client.get("/").status_code == 200


def test_ten_dang_nhap_khong_phan_biet_hoa_thuong(tao_client):
    client = tao_client()
    r = client.post("/dang-nhap", data={"ten_dang_nhap": " KD1 ", "mat_khau": MAT_KHAU_TEST})
    assert r.status_code == 302


def test_sai_mat_khau_hoac_khong_co_tai_khoan(tao_client):
    client = tao_client()
    for ten, mk in [("kd1", "sai"), ("khong-ton-tai", MAT_KHAU_TEST), ("", ""), ("kd1", "")]:
        r = client.post("/dang-nhap", data={"ten_dang_nhap": ten, "mat_khau": mk})
        assert r.status_code == 200, (ten, mk)
        assert "Sai tên đăng nhập" in r.get_data(as_text=True)
    assert client.get("/").status_code == 302  # vẫn chưa đăng nhập


def test_tai_khoan_khach_hang_khong_vao_duoc(tao_client):
    client = tao_client()
    r = client.post("/dang-nhap", data={"ten_dang_nhap": "khach1", "mat_khau": MAT_KHAU_TEST})
    assert r.status_code == 200
    assert client.get("/").status_code == 302


def test_mat_khau_dinh_dang_cu_van_dang_nhap_duoc(tao_client):
    client = tao_client()
    r = client.post("/dang-nhap", data={"ten_dang_nhap": "cu1", "mat_khau": MAT_KHAU_CU})
    assert r.status_code == 302


def test_dang_xuat_xoa_phien(tao_client):
    client = tao_client("kd1")
    assert client.get("/don-hang").status_code == 200
    client.post("/dang-xuat")
    assert client.get("/don-hang").status_code == 302


def test_khong_dang_xuat_bang_get(tao_client):
    client = tao_client("kd1")
    assert client.get("/dang-xuat").status_code == 405
    assert client.get("/don-hang").status_code == 200


def test_next_noi_bo_duoc_dung_con_ben_ngoai_bi_bo_qua(tao_client):
    client = tao_client()
    r = client.post("/dang-nhap?next=/san-pham", data={"ten_dang_nhap": "kd1", "mat_khau": MAT_KHAU_TEST})
    assert r.headers["Location"].endswith("/san-pham")

    client = tao_client()
    for xau in ["//evil.example.com", "https://evil.example.com", "/\\evil.example.com"]:
        r = client.post("/dang-nhap", query_string={"next": xau},
                        data={"ten_dang_nhap": "kd1", "mat_khau": MAT_KHAU_TEST})
        assert "evil" not in r.headers["Location"], xau
        client.post("/dang-xuat")


# ---------- Phân quyền ----------

def test_nhan_vien_chi_xem_khong_tao_duoc_don(tao_client, db):
    client = tao_client("nv1")
    assert client.get("/don-hang").status_code == 200
    assert client.get("/san-pham").status_code == 200
    assert client.get("/don-hang/moi").status_code == 403
    assert client.post("/don-hang/moi", data=_du_lieu_don()).status_code == 403
    assert db.donhang.count_documents({}) == 0


def test_nhan_vien_khong_sua_duoc_san_pham_va_khach(tao_client, db):
    client = tao_client("nv1")
    assert client.get("/san-pham/moi").status_code == 403
    assert client.post("/san-pham/SP0001/trang-thai").status_code == 403
    assert client.post("/khach-hang/KH0001/trang-thai").status_code == 403
    assert "hoat_dong" not in db.sanpham.find_one({"_id": "SP0001"})
    assert "hoat_dong" not in db.khachhang.find_one({"_id": "KH0001"})


def test_kinh_doanh_tao_va_huy_don_nhung_khong_ghi_kho(tao_client, db):
    client = tao_client("kd1")
    assert client.post("/don-hang/moi", data=_du_lieu_don()).status_code == 302
    ma = db.donhang.find_one({})["_id"]
    client.post(f"/don-hang/{ma}/huy")
    assert db.donhang.find_one({"_id": ma})["trang_thai"] == "DA_HUY"

    assert client.get("/kho").status_code == 403
    assert client.post("/kho", data={"loai": "NHAP", "ma_nvl": ["NVL0001"], "so_luong": ["5"]}).status_code == 403
    assert db.nguyenvatlieu.find_one({"_id": "NVL0001"})["so_luong_ton"] == 100


def test_kho_ghi_phieu_nhung_khong_tao_duoc_don(tao_client, db):
    client = tao_client("kho1")
    r = client.post("/kho", data={"loai": "NHAP", "ma_nvl": ["NVL0001"], "so_luong": ["7"]})
    assert r.status_code == 302
    assert db.nguyenvatlieu.find_one({"_id": "NVL0001"})["so_luong_ton"] == 107

    assert client.get("/don-hang/moi").status_code == 403
    assert client.get("/don-hang").status_code == 403  # kho không xem đơn
    assert client.get("/bao-cao").status_code == 200


def test_ke_toan_thanh_toan_nhung_khong_huy_duoc(tao_client, db):
    _tao_don(db)
    client = tao_client("kt1")

    client.post("/don-hang/DH0001/thanh-toan", data={"so_tien": "50000", "phuong_thuc": "TIEN_MAT"})
    assert db.thanhtoan.count_documents({"ma_don": "DH0001"}) == 1

    assert client.post("/don-hang/DH0001/huy").status_code == 403
    assert db.donhang.find_one({"_id": "DH0001"})["trang_thai"] == "THANH_TOAN_MOT_PHAN"
    assert client.get("/kho").status_code == 200  # xem kho được
    assert client.post("/kho", data={"loai": "NHAP", "ma_nvl": ["NVL0001"], "so_luong": ["5"]}).status_code == 403


def test_nhan_vien_khong_thanh_toan_duoc(tao_client, db):
    _tao_don(db)
    r = tao_client("nv1").post("/don-hang/DH0001/thanh-toan", data={"so_tien": "50000"})
    assert r.status_code == 403
    assert db.thanhtoan.count_documents({}) == 0


def test_bao_cao_va_csv_theo_vai_tro(tao_client):
    assert tao_client("kt1").get("/bao-cao/don-hang.csv").status_code == 200
    assert tao_client("nv1").get("/bao-cao").status_code == 403
    assert tao_client("nv1").get("/bao-cao/don-hang.csv").status_code == 403


def test_menu_chi_hien_muc_duoc_phep(tao_client):
    html = tao_client("nv1").get("/").get_data(as_text=True)
    assert 'href="/don-hang"' in html
    assert 'href="/don-hang/moi"' not in html
    assert 'href="/kho"' not in html
    assert 'href="/bao-cao"' not in html


def test_trang_403_hien_thong_bao_than_thien(tao_client):
    r = tao_client("nv1").get("/don-hang/moi")
    assert r.status_code == 403
    assert "không có quyền" in r.get_data(as_text=True)


def test_trang_chu_chi_hien_so_lieu_duoc_phep(tao_client):
    nv = tao_client("nv1").get("/").get_data(as_text=True)
    assert "Doanh thu tháng" not in nv and "Công nợ phải thu" not in nv
    assert 'href="/don-hang/moi"' not in nv

    kho = tao_client("kho1").get("/").get_data(as_text=True)
    assert "NVL dưới" in kho
    assert "Đơn hàng gần nhất" not in kho  # kho không xem đơn nên không thấy link dẫn tới 403

    kd = tao_client("kd1").get("/").get_data(as_text=True)
    assert "Doanh thu tháng" in kd and 'href="/don-hang/moi"' in kd


def test_nut_thao_tac_an_voi_vai_tro_khong_co_quyen(tao_client, db):
    _tao_don(db)

    nv = tao_client("nv1")
    sp = nv.get("/san-pham").get_data(as_text=True)
    assert "+ Thêm sản phẩm" not in sp and "Ngừng bán</button>" not in sp
    kh = nv.get("/khach-hang").get_data(as_text=True)
    assert "+ Thêm khách hàng" not in kh
    ds = nv.get("/don-hang").get_data(as_text=True)
    assert "+ Lập đơn mới" not in ds and "Xuất CSV" not in ds
    ct = nv.get("/don-hang/DH0001").get_data(as_text=True)
    assert "Hủy đơn</button>" not in ct and "Ghi nhận</button>" not in ct

    kt = tao_client("kt1").get("/don-hang/DH0001").get_data(as_text=True)
    assert "Ghi nhận</button>" in kt and "Hủy đơn</button>" not in kt

    kd = tao_client("kd1").get("/don-hang/DH0001").get_data(as_text=True)
    assert "Hủy đơn</button>" in kd and "+ Thêm" in tao_client("kd1").get("/san-pham").get_data(as_text=True)


def test_kho_chi_hien_form_lap_phieu_cho_vai_tro_kho(tao_client):
    assert "Lập phiếu</button>" in tao_client("kho1").get("/kho").get_data(as_text=True)
    assert "Lập phiếu</button>" not in tao_client("kt1").get("/kho").get_data(as_text=True)
