"""Kiểm thử nghiệp vụ và transaction. Cần MongoDB replica set đang chạy.

Chạy: pytest -q
Dùng CSDL riêng 'maymac_test' nên không ảnh hưởng dữ liệu demo.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import queries, services  # noqa: E402


def test_dat_hang_tinh_tong_va_tao_hoa_don(db):
    don = services.dat_hang(db, "DH0001", "KH0001", [
        {"ma_sp": "SP0001", "mau": "Trắng", "size": "M", "so_luong": 10},
        {"ma_sp": "SP0002", "mau": "Xanh navy", "size": "L", "so_luong": 5},
    ])

    assert don["tong_tien"] == 10 * 100_000 + 5 * 150_000
    assert db.donhang.count_documents({"_id": "DH0001"}) == 1
    hd = db.hoadon.find_one({"ma_don": "DH0001"})
    assert hd["tong_tien"] == don["tong_tien"]


def test_dat_hang_sai_mau_thi_khong_ghi_gi(db):
    with pytest.raises(services.NghiepVuError):
        services.dat_hang(db, "DH0002", "KH0001", [
            {"ma_sp": "SP0001", "mau": "Trắng", "size": "M", "so_luong": 1},
            {"ma_sp": "SP0002", "mau": "Đen", "size": "M", "so_luong": 1},  # SP0002 không có màu Đen
        ])
    assert db.donhang.count_documents({}) == 0
    assert db.hoadon.count_documents({}) == 0


def test_dat_hang_khach_khong_ton_tai(db):
    with pytest.raises(services.NghiepVuError):
        services.dat_hang(db, "DH0003", "KH9999", [{"ma_sp": "SP0001", "so_luong": 1}])
    assert db.donhang.count_documents({}) == 0


def test_thanh_toan_tung_phan_roi_du(db):
    services.dat_hang(db, "DH0004", "KH0001", [{"ma_sp": "SP0001", "so_luong": 10}])  # 1.000.000

    r1 = services.ghi_nhan_thanh_toan(db, "TT0001", "DH0004", 400_000)
    assert r1["con_no"] == 600_000
    assert db.donhang.find_one({"_id": "DH0004"})["trang_thai"] == services.TRANG_THAI_TT_MOT_PHAN

    r2 = services.ghi_nhan_thanh_toan(db, "TT0002", "DH0004", 600_000)
    assert r2["con_no"] == 0
    assert db.donhang.find_one({"_id": "DH0004"})["trang_thai"] == services.TRANG_THAI_DA_TT


def test_thanh_toan_vuot_no_bi_tu_choi(db):
    services.dat_hang(db, "DH0005", "KH0001", [{"ma_sp": "SP0001", "so_luong": 1}])  # 100.000
    with pytest.raises(services.NghiepVuError):
        services.ghi_nhan_thanh_toan(db, "TT0003", "DH0005", 200_000)
    assert db.thanhtoan.count_documents({}) == 0


def test_nhap_kho_tang_ton(db):
    services.lap_phieu_kho(db, "PK0001", "NHAP", [{"ma_nvl": "NVL0001", "so_luong": 50}])
    assert db.nguyenvatlieu.find_one({"_id": "NVL0001"})["so_luong_ton"] == 150


def test_xuat_kho_vuot_ton_rollback_toan_phieu(db):
    # Dòng đầu hợp lệ (NVL0001), dòng sau thiếu hàng (NVL0002 chỉ còn 5)
    with pytest.raises(services.NghiepVuError):
        services.lap_phieu_kho(db, "PK0002", "XUAT", [
            {"ma_nvl": "NVL0001", "so_luong": 10},
            {"ma_nvl": "NVL0002", "so_luong": 999},
        ])
    assert db.nguyenvatlieu.find_one({"_id": "NVL0001"})["so_luong_ton"] == 100
    assert db.nguyenvatlieu.find_one({"_id": "NVL0002"})["so_luong_ton"] == 5
    assert db.phieukho.count_documents({}) == 0


def test_doanh_thu_theo_thang_khop_tong_don(db):
    services.dat_hang(db, "DH0006", "KH0001", [{"ma_sp": "SP0001", "so_luong": 3}])
    services.dat_hang(db, "DH0007", "KH0001", [{"ma_sp": "SP0002", "so_luong": 2}])

    tong_don = sum(d["tong_tien"] for d in db.donhang.find())
    tong_bao_cao = sum(r["doanh_thu"] for r in queries.doanh_thu_theo_thang(db))
    assert tong_bao_cao == tong_don == 600_000


def test_cong_no_khach_hang(db):
    services.dat_hang(db, "DH0008", "KH0001", [{"ma_sp": "SP0001", "so_luong": 10}])  # 1.000.000
    services.ghi_nhan_thanh_toan(db, "TT0004", "DH0008", 250_000)

    ket_qua = queries.cong_no_khach_hang(db)
    assert ket_qua[0]["ma_kh"] == "KH0001"
    assert ket_qua[0]["cong_no"] == 750_000
