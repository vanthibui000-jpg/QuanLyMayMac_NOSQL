"""Kiểm thử nghiệp vụ hủy đơn và chặn thao tác với sản phẩm/khách ngừng hoạt động."""
import pytest

from app import queries, services
from app.services import NghiepVuError


def _tao_don(db, ma_don="DH0001"):
    return services.dat_hang(db, ma_don, "KH0001", [
        {"ma_sp": "SP0001", "so_luong": 10, "mau": "Trắng", "size": "M"},
    ])


def test_huy_don_chua_thanh_toan(db):
    _tao_don(db)
    services.huy_don(db, "DH0001")

    assert db.donhang.find_one({"_id": "DH0001"})["trang_thai"] == "DA_HUY"
    assert db.hoadon.find_one({"ma_don": "DH0001"})["trang_thai"] == "DA_HUY"
    # Document vẫn còn để lưu vết, nhưng không tính vào doanh thu
    assert db.donhang.count_documents({}) == 1
    assert queries.doanh_thu_theo_thang(db) == []


def test_don_huy_khong_vao_cong_no_va_top_san_pham(db):
    _tao_don(db, "DH0001")
    _tao_don(db, "DH0002")
    services.huy_don(db, "DH0002")

    cong_no = queries.cong_no_khach_hang(db)
    assert cong_no[0]["tong_mua"] == 1_000_000  # chỉ tính DH0001 (10 × 100.000)
    top = queries.top_san_pham(db)
    assert top[0]["so_luong"] == 10


def test_huy_don_da_thanh_toan_bi_tu_choi(db):
    _tao_don(db)
    services.ghi_nhan_thanh_toan(db, "TT0001", "DH0001", 100_000)

    with pytest.raises(NghiepVuError, match="đã có thanh toán"):
        services.huy_don(db, "DH0001")
    assert db.donhang.find_one({"_id": "DH0001"})["trang_thai"] == "THANH_TOAN_MOT_PHAN"


def test_huy_lai_bi_tu_choi(db):
    _tao_don(db)
    services.huy_don(db, "DH0001")

    with pytest.raises(NghiepVuError, match="đã bị hủy trước đó"):
        services.huy_don(db, "DH0001")


def test_thanh_toan_don_da_huy_bi_tu_choi(db):
    _tao_don(db)
    services.huy_don(db, "DH0001")

    with pytest.raises(NghiepVuError, match="đã bị hủy"):
        services.ghi_nhan_thanh_toan(db, "TT0001", "DH0001", 100_000)
    assert db.thanhtoan.count_documents({}) == 0


def test_huy_don_khong_ton_tai(db):
    with pytest.raises(NghiepVuError, match="không tồn tại"):
        services.huy_don(db, "DH9999")


def test_dat_hang_san_pham_ngung_ban_bi_tu_choi(db):
    db.sanpham.update_one({"_id": "SP0001"}, {"$set": {"hoat_dong": False}})

    with pytest.raises(NghiepVuError, match="đã ngừng bán"):
        _tao_don(db)
    assert db.donhang.count_documents({}) == 0


def test_dat_hang_khach_ngung_hoat_dong_bi_tu_choi(db):
    db.khachhang.update_one({"_id": "KH0001"}, {"$set": {"hoat_dong": False}})

    with pytest.raises(NghiepVuError, match="đã ngừng hoạt động"):
        _tao_don(db)
    assert db.donhang.count_documents({}) == 0
