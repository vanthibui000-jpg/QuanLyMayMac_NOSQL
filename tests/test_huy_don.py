"""Kiểm thử hủy đơn hoàn tồn kho và chặn sản phẩm/khách ngừng hoạt động."""
import pytest

from app import queries, services
from app.services import NghiepVuError

GIAO_HANG = {"ho_ten": "Nguyễn Văn A", "sdt": "0900000001", "dia_chi": "128 Phố Huế, Hà Nội"}


def _ton(db, ma_sp="SP0001", mau="Trắng", size="M"):
    sp = db.sanpham.find_one({"_id": ma_sp})
    return next(b["ton_kho"] for b in sp["bien_the"] if b["mau"] == mau and b["size"] == size)


def test_huy_don_hoan_ton_kho_va_bo_khoi_bao_cao(db):
    services.dat_hang(db, "DH000001", "KH0001", [{"ma_sp": "SP0001", "mau": "Trắng", "size": "M", "so_luong": 4}], GIAO_HANG)
    assert _ton(db) == 11

    services.huy_don(db, "DH000001", nguoi_huy="ADMIN")
    assert _ton(db) == 15  # đã hoàn đủ 4 chiếc
    assert db.donhang.find_one({"_id": "DH000001"})["trang_thai"] == "DA_HUY"
    assert db.hoadon.find_one({"ma_don": "DH000001"})["trang_thai"] == "DA_HUY"
    assert queries.doanh_thu_theo_thang(db) == []


def test_khach_chi_tu_huy_duoc_khi_cho_xac_nhan(db):
    services.dat_hang(db, "DH000002", "KH0001", [{"ma_sp": "SP0001", "mau": "Trắng", "size": "M", "so_luong": 2}], GIAO_HANG)
    services.cap_nhat_don_hang(db, "DH000002", trang_thai_moi="DANG_GIAO")

    with pytest.raises(NghiepVuError, match="Chờ xác nhận"):
        services.huy_don(db, "DH000002", nguoi_huy="KH")
    assert db.donhang.find_one({"_id": "DH000002"})["trang_thai"] == "DANG_GIAO"

    # Admin vẫn hủy được đơn đang giao và hoàn tồn kho
    services.huy_don(db, "DH000002", nguoi_huy="ADMIN")
    assert _ton(db) == 15


def test_khong_huy_duoc_don_da_hoan_thanh(db):
    services.dat_hang(db, "DH000003", "KH0001", [{"ma_sp": "SP0001", "mau": "Trắng", "size": "M", "so_luong": 1}], GIAO_HANG)
    services.cap_nhat_don_hang(db, "DH000003", trang_thai_moi="HOAN_THANH")

    with pytest.raises(NghiepVuError, match="đã hoàn thành"):
        services.huy_don(db, "DH000003", nguoi_huy="ADMIN")


def test_dat_hang_san_pham_hoac_khach_ngung_hoat_dong_bi_tu_choi(db):
    db.sanpham.update_one({"_id": "SP0001"}, {"$set": {"hoat_dong": False}})
    with pytest.raises(NghiepVuError, match="ngừng kinh doanh"):
        services.dat_hang(db, "DH000004", "KH0001", [{"ma_sp": "SP0001", "mau": "Trắng", "size": "M", "so_luong": 1}], GIAO_HANG)

    db.sanpham.update_one({"_id": "SP0001"}, {"$set": {"hoat_dong": True}})
    db.khachhang.update_one({"_id": "KH0001"}, {"$set": {"hoat_dong": False}})
    with pytest.raises(NghiepVuError, match="ngừng hoạt động"):
        services.dat_hang(db, "DH000005", "KH0001", [{"ma_sp": "SP0001", "mau": "Trắng", "size": "M", "so_luong": 1}], GIAO_HANG)
