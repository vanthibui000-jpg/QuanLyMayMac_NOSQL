"""Kiểm thử nghiệp vụ bán lẻ thời trang & MongoDB Multi-Document Transaction."""
import pytest

from app import queries, services
from app.services import NghiepVuError

GIAO_HANG = {"ho_ten": "Nguyễn Văn A", "sdt": "0900000001", "dia_chi": "128 Phố Huế, Hà Nội"}


def _ton(db, ma_sp, mau, size):
    sp = db.sanpham.find_one({"_id": ma_sp})
    return next(b["ton_kho"] for b in sp["bien_the"] if b["mau"] == mau and b["size"] == size)


def test_dat_hang_tru_ton_kho_va_tao_hoa_don_freeship(db):
    don = services.dat_hang(
        db, "DH000001", "KH0001",
        [{"ma_sp": "SP0001", "mau": "Trắng", "size": "M", "so_luong": 2}],
        GIAO_HANG,
    )
    assert don["phi_van_chuyen"] == 0
    assert don["tong_tien"] == 1_600_000
    assert _ton(db, "SP0001", "Trắng", "M") == 13
    assert db.hoadon.find_one({"ma_don": "DH000001"})["tong_tien"] == 1_600_000


def test_dat_hang_thieu_ton_o_dong_hai_rollback_toan_bo(db):
    with pytest.raises(NghiepVuError, match="không đủ tồn kho"):
        services.dat_hang(
            db, "DH000002", "KH0001",
            [
                {"ma_sp": "SP0001", "mau": "Trắng", "size": "M", "so_luong": 3},
                {"ma_sp": "SP0002", "mau": "Xanh navy", "size": "L", "so_luong": 99},
            ],
            GIAO_HANG,
        )
    # Dòng đầu phải được rollback, không trừ tồn, không tạo đơn hay hóa đơn
    assert _ton(db, "SP0001", "Trắng", "M") == 15
    assert db.donhang.count_documents({}) == 0
    assert db.hoadon.count_documents({}) == 0


def test_cap_nhat_trang_thai_hoan_thanh_tu_xac_nhan_thanh_toan(db):
    services.dat_hang(db, "DH000003", "KH0001", [{"ma_sp": "SP0001", "mau": "Trắng", "size": "M", "so_luong": 1}], GIAO_HANG)
    don = services.cap_nhat_don_hang(db, "DH000003", trang_thai_moi="HOAN_THANH", ghi_chu="Đã giao thành công")
    assert don["trang_thai"] == "HOAN_THANH"
    assert don["trang_thai_tt"] == "DA_THANH_TOAN"
    assert db.hoadon.find_one({"ma_don": "DH000003"})["trang_thai"] == "HOAN_THANH"


def test_nhap_kho_thanh_pham_tang_ton_va_them_bien_the_moi(db):
    services.lap_phieu_kho(db, "PK0001", "NHAP", [
        {"ma_sp": "SP0001", "mau": "Trắng", "size": "M", "so_luong": 10},
        {"ma_sp": "SP0001", "mau": "Be", "size": "XL", "so_luong": 8},
    ])
    assert _ton(db, "SP0001", "Trắng", "M") == 25
    assert _ton(db, "SP0001", "Be", "XL") == 8
    assert db.phieukho.count_documents({"_id": "PK0001"}) == 1


def test_xuat_kho_thieu_hang_rollback_toan_phieu(db):
    with pytest.raises(NghiepVuError, match="Không đủ tồn kho"):
        services.lap_phieu_kho(db, "PK0002", "XUAT", [
            {"ma_sp": "SP0001", "mau": "Trắng", "size": "M", "so_luong": 5},
            {"ma_sp": "SP0002", "mau": "Xanh navy", "size": "L", "so_luong": 50},
        ])
    assert _ton(db, "SP0001", "Trắng", "M") == 15
    assert db.phieukho.count_documents({}) == 0


def test_aggregation_doanh_thu_va_danh_muc(db):
    services.dat_hang(db, "DH000004", "KH0001", [{"ma_sp": "SP0001", "mau": "Trắng", "size": "M", "so_luong": 1}], GIAO_HANG)
    services.dat_hang(db, "DH000005", "KH0002", [{"ma_sp": "SP0002", "mau": "Đen", "size": "M", "so_luong": 1}], GIAO_HANG)

    thang = queries.doanh_thu_theo_thang(db)
    assert sum(r["doanh_thu"] for r in thang) == 3_300_000
    dm = queries.doanh_thu_theo_danh_muc(db)
    assert dm[0]["ten_dm"] == "Suits & Blazer" and dm[0]["doanh_thu"] == 2_500_000
    sap_het = queries.bien_the_sap_het(db, 10)
    assert any(r["ma_sp"] == "SP0002" and r["mau"] == "Xanh navy" for r in sap_het)
