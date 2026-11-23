"""Kiểm thử route Flask bằng test client, trên CSDL maymac_test (không đụng dữ liệu demo)."""
import pytest


@pytest.fixture
def client(tao_client):
    return tao_client("kd1")  # vai trò Kinh doanh: quản lý sản phẩm, khách, đơn


def test_cac_trang_chinh_tra_ve_200(client):
    for url in ["/", "/don-hang", "/don-hang/moi", "/bao-cao",
                "/san-pham", "/san-pham/moi", "/khach-hang", "/khach-hang/moi"]:
        assert client.get(url).status_code == 200, url


def test_them_san_pham_luu_mau_size_va_bo_trung(client, db):
    client.post("/san-pham/moi", data={
        "ten_sp": "Áo sơ mi", "don_gia": "120000",
        "mau": "Trắng, Đen, Trắng", "size": "M, L", "barcode": "",
    })

    sp = db.sanpham.find_one({"_id": "SP0003"})
    assert sp["mau"] == ["Trắng", "Đen"]
    assert sp["size"] == ["M", "L"]
    assert sp["hoat_dong"] is True
    assert "barcode" not in sp  # để trống thì không lưu, tránh vướng index unique


def test_gia_khong_hop_le_khong_luu(client, db):
    client.post("/san-pham/moi", data={"ten_sp": "Áo", "don_gia": "abc", "mau": "", "size": "", "barcode": ""})
    assert db.sanpham.count_documents({}) == 2


def test_trung_ma_vach_bao_loi_khong_500(client, db):
    db.sanpham.update_one({"_id": "SP0001"}, {"$set": {"barcode": "8930001"}})
    r = client.post("/san-pham/moi", data={"ten_sp": "Áo", "don_gia": "1000", "mau": "", "size": "", "barcode": "8930001"})
    assert r.status_code == 200
    assert db.sanpham.count_documents({}) == 2


def test_sua_san_pham_doi_gia(client, db):
    client.post("/san-pham/SP0001/sua", data={
        "ten_sp": "Áo thun basic", "don_gia": "99000", "mau": "Trắng", "size": "M", "barcode": "",
    })
    sp = db.sanpham.find_one({"_id": "SP0001"})
    assert sp["don_gia"] == 99000
    assert sp["ten_sp"] == "Áo thun basic"


def test_ngung_ban_roi_mo_lai_khong_xoa_document(client, db):
    client.post("/san-pham/SP0001/trang-thai")
    assert db.sanpham.find_one({"_id": "SP0001"})["hoat_dong"] is False
    assert db.sanpham.count_documents({}) == 2

    client.post("/san-pham/SP0001/trang-thai")
    assert db.sanpham.find_one({"_id": "SP0001"})["hoat_dong"] is True


def test_tim_san_pham_khong_loi_voi_ky_tu_dac_biet(client):
    assert "Quần jean" in client.get("/san-pham?q=jean").get_data(as_text=True)
    assert client.get("/san-pham?q=(").status_code == 200  # ký tự regex được escape


def test_them_khach_va_kiem_tra_so_dien_thoai(client, db):
    client.post("/khach-hang/moi", data={"ten_kh": "Shop B", "sdt": "0912345678"})
    assert db.khachhang.find_one({"_id": "KH0002"})["sdt"] == "0912345678"

    client.post("/khach-hang/moi", data={"ten_kh": "Shop C", "sdt": "abc"})
    assert db.khachhang.count_documents({}) == 2


def test_khach_ngung_khong_dat_duoc_don_qua_web(client, db):
    client.post("/khach-hang/KH0001/trang-thai")
    r = client.post("/don-hang/moi", data={
        "ma_kh": "KH0001", "ma_sp": ["SP0001"], "mau": ["Trắng"], "size": ["M"], "so_luong": ["5"],
    })
    assert r.status_code == 200
    assert db.donhang.count_documents({}) == 0


def test_huy_don_qua_web_va_loc_theo_trang_thai(client, db):
    client.post("/don-hang/moi", data={
        "ma_kh": "KH0001", "ma_sp": ["SP0001"], "mau": ["Trắng"], "size": ["M"], "so_luong": ["5"],
    })
    ma = db.donhang.find_one({}, sort=[("_id", -1)])["_id"]

    r = client.post(f"/don-hang/{ma}/huy", follow_redirects=True)
    assert r.status_code == 200
    assert db.donhang.find_one({"_id": ma})["trang_thai"] == "DA_HUY"

    loc = client.get("/don-hang?trang_thai=DA_HUY").get_data(as_text=True)
    assert ma in loc


def test_khong_huy_duoc_don_da_thanh_toan_qua_web(client, db):
    from app import services
    services.dat_hang(db, "DH0001", "KH0001", [{"ma_sp": "SP0001", "so_luong": 2, "mau": None, "size": None}])
    services.ghi_nhan_thanh_toan(db, "TT0001", "DH0001", 50_000)

    client.post("/don-hang/DH0001/huy")
    assert db.donhang.find_one({"_id": "DH0001"})["trang_thai"] == "THANH_TOAN_MOT_PHAN"


def test_xuat_csv_don_hang_va_ton_kho(client, db):
    csv_don = client.get("/bao-cao/don-hang.csv")
    assert csv_don.mimetype == "text/csv"
    assert csv_don.get_data(as_text=True).startswith("﻿Mã đơn")

    csv_kho = client.get("/bao-cao/ton-kho.csv").get_data(as_text=True)
    assert "NVL0001" in csv_kho and "1" in csv_kho


def test_csv_ten_khong_co_tra_404(client):
    assert client.get("/bao-cao/khong-co.csv").status_code == 404


def test_loc_phieu_kho_theo_loai(tao_client, db):
    from app import services
    services.lap_phieu_kho(db, "PK0001", "NHAP", [{"ma_nvl": "NVL0001", "so_luong": 5}])
    services.lap_phieu_kho(db, "PK0002", "XUAT", [{"ma_nvl": "NVL0001", "so_luong": 3}])

    xuat = tao_client("kho1").get("/kho?loai=XUAT").get_data(as_text=True)
    assert "PK0002" in xuat and "PK0001" not in xuat
