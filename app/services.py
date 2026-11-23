"""Nghiệp vụ ghi dữ liệu.

Mỗi hàm chạy trong MỘT transaction multi-document (cần replica set rs0).
Nếu có lỗi nghiệp vụ (NghiepVuError), toàn bộ thay đổi bị hủy: không ghi gì.
"""
from datetime import datetime, timezone

TRANG_THAI_CHO_TT = "CHO_THANH_TOAN"
TRANG_THAI_TT_MOT_PHAN = "THANH_TOAN_MOT_PHAN"
TRANG_THAI_DA_TT = "DA_THANH_TOAN"
TRANG_THAI_DA_HUY = "DA_HUY"  # đơn bị hủy: giữ document để lưu vết, không tính vào báo cáo
LOAI_PHIEU = ("NHAP", "XUAT")


class NghiepVuError(Exception):
    """Lỗi nghiệp vụ: làm transaction bị rollback."""


def _now():
    return datetime.now(timezone.utc)


def dat_hang(db, ma_don, ma_kh, dong_hang, ngay_dat=None):
    """Lập đơn đặt hàng B2B và hóa đơn tương ứng.

    dong_hang: list dict gồm ma_sp, so_luong và tùy chọn mau, size.
    Đơn giá lấy từ sản phẩm tại thời điểm đặt (giống trường DonGia trong thiết kế).
    """
    if not dong_hang:
        raise NghiepVuError("Đơn hàng phải có ít nhất một dòng")
    ngay_dat = ngay_dat or _now()

    def _thuc_hien(session):
        kh = db.khachhang.find_one({"_id": ma_kh}, session=session)
        if kh is None:
            raise NghiepVuError(f"Khách hàng {ma_kh} không tồn tại")
        if kh.get("hoat_dong") is False:
            raise NghiepVuError(f"Khách hàng {ma_kh} đã ngừng hoạt động")

        chi_tiet = []
        for dong in dong_hang:
            sp = db.sanpham.find_one({"_id": dong["ma_sp"]}, session=session)
            if sp is None:
                raise NghiepVuError(f"Sản phẩm {dong['ma_sp']} không tồn tại")
            if sp.get("hoat_dong") is False:
                raise NghiepVuError(f"Sản phẩm {dong['ma_sp']} đã ngừng bán")

            so_luong = int(dong["so_luong"])
            if so_luong <= 0:
                raise NghiepVuError(f"Số lượng của {dong['ma_sp']} phải lớn hơn 0")

            mau, size = dong.get("mau"), dong.get("size")
            if mau is not None and mau not in sp.get("mau", []):
                raise NghiepVuError(f"Sản phẩm {dong['ma_sp']} không có màu {mau}")
            if size is not None and size not in sp.get("size", []):
                raise NghiepVuError(f"Sản phẩm {dong['ma_sp']} không có size {size}")

            chi_tiet.append({
                "ma_sp": dong["ma_sp"],
                "mau": mau,
                "size": size,
                "so_luong": so_luong,
                "don_gia": sp["don_gia"],
            })

        tong = sum(d["so_luong"] * d["don_gia"] for d in chi_tiet)
        don = {
            "_id": ma_don,
            "ngay_dat": ngay_dat,
            "trang_thai": TRANG_THAI_CHO_TT,
            "ma_kh": ma_kh,
            "chi_tiet": chi_tiet,
            "tong_tien": tong,
        }
        db.donhang.insert_one(don, session=session)
        db.hoadon.insert_one(
            {"_id": f"HD{ma_don}", "ngay_xuat": ngay_dat, "tong_tien": tong, "ma_don": ma_don},
            session=session,
        )
        return don

    with db.client.start_session() as session:
        return session.with_transaction(_thuc_hien)


def _tong_da_tra(db, ma_don, session):
    ket_qua = list(db.thanhtoan.aggregate(
        [{"$match": {"ma_don": ma_don}}, {"$group": {"_id": None, "tong": {"$sum": "$so_tien"}}}],
        session=session,
    ))
    return ket_qua[0]["tong"] if ket_qua else 0


def ghi_nhan_thanh_toan(db, ma_tt, ma_don, so_tien, phuong_thuc="TIEN_MAT"):
    """Ghi một lượt thanh toán và cập nhật trạng thái đơn hàng."""
    if so_tien <= 0:
        raise NghiepVuError("Số tiền thanh toán phải lớn hơn 0")
    ngay = _now()

    def _thuc_hien(session):
        don = db.donhang.find_one({"_id": ma_don}, session=session)
        if don is None:
            raise NghiepVuError(f"Đơn hàng {ma_don} không tồn tại")
        if don["trang_thai"] == TRANG_THAI_DA_HUY:
            raise NghiepVuError("Đơn đã bị hủy, không thể thanh toán")

        da_tra = _tong_da_tra(db, ma_don, session)
        if da_tra + so_tien > don["tong_tien"]:
            raise NghiepVuError(
                f"Thanh toán vượt quá số tiền còn nợ ({don['tong_tien'] - da_tra})"
            )

        db.thanhtoan.insert_one({
            "_id": ma_tt,
            "ngay_thanh_toan": ngay,
            "so_tien": so_tien,
            "phuong_thuc": phuong_thuc,
            "ma_don": ma_don,
        }, session=session)

        da_tra_moi = da_tra + so_tien
        trang_thai = TRANG_THAI_DA_TT if da_tra_moi == don["tong_tien"] else TRANG_THAI_TT_MOT_PHAN
        db.donhang.update_one({"_id": ma_don}, {"$set": {"trang_thai": trang_thai}}, session=session)
        return {"da_tra": da_tra_moi, "con_no": don["tong_tien"] - da_tra_moi, "trang_thai": trang_thai}

    with db.client.start_session() as session:
        return session.with_transaction(_thuc_hien)


def lap_phieu_kho(db, ma_phieu, loai, dong_hang, ngay_lap=None):
    """Lập phiếu nhập hoặc xuất kho nguyên vật liệu và cập nhật tồn kho.

    Phiếu xuất kiểm tra tồn kho bằng điều kiện trong update: nếu thiếu NVL ở bất kỳ dòng nào,
    cả phiếu bị hủy, kể cả các dòng trước đó đã trừ tồn.
    """
    loai = loai.upper()
    if loai not in LOAI_PHIEU:
        raise NghiepVuError("Loại phiếu phải là NHAP hoặc XUAT")
    if not dong_hang:
        raise NghiepVuError("Phiếu kho phải có ít nhất một dòng")
    ngay_lap = ngay_lap or _now()

    def _thuc_hien(session):
        chi_tiet = []
        for dong in dong_hang:
            ma_nvl = dong["ma_nvl"]
            so_luong = int(dong["so_luong"])
            if so_luong <= 0:
                raise NghiepVuError(f"Số lượng của {ma_nvl} phải lớn hơn 0")

            if loai == "NHAP":
                kq = db.nguyenvatlieu.update_one(
                    {"_id": ma_nvl}, {"$inc": {"so_luong_ton": so_luong}}, session=session
                )
            else:
                kq = db.nguyenvatlieu.update_one(
                    {"_id": ma_nvl, "so_luong_ton": {"$gte": so_luong}},
                    {"$inc": {"so_luong_ton": -so_luong}},
                    session=session,
                )

            if kq.matched_count == 0:
                if db.nguyenvatlieu.find_one({"_id": ma_nvl}, session=session) is None:
                    raise NghiepVuError(f"Nguyên vật liệu {ma_nvl} không tồn tại")
                raise NghiepVuError(f"Không đủ tồn kho để xuất {so_luong} của {ma_nvl}")

            chi_tiet.append({"ma_nvl": ma_nvl, "so_luong": so_luong})

        phieu = {"_id": ma_phieu, "loai": loai, "ngay_lap": ngay_lap, "chi_tiet": chi_tiet}
        db.phieukho.insert_one(phieu, session=session)
        return phieu

    with db.client.start_session() as session:
        return session.with_transaction(_thuc_hien)


def huy_don(db, ma_don):
    """Hủy đơn chưa thanh toán. Đổi trạng thái đơn và hóa đơn sang DA_HUY, không xóa document.

    Chỉ hủy được khi đơn chưa có lượt thanh toán nào; đơn đã thanh toán một phần hoặc đủ thì từ chối.
    Đơn chưa từng trừ kho (đặt hàng không đụng tới tồn nguyên vật liệu) nên không cần hoàn kho.
    """
    def _thuc_hien(session):
        don = db.donhang.find_one({"_id": ma_don}, session=session)
        if don is None:
            raise NghiepVuError(f"Đơn hàng {ma_don} không tồn tại")
        if don["trang_thai"] == TRANG_THAI_DA_HUY:
            raise NghiepVuError("Đơn đã bị hủy trước đó")
        if don["trang_thai"] != TRANG_THAI_CHO_TT or _tong_da_tra(db, ma_don, session) > 0:
            raise NghiepVuError("Đơn đã có thanh toán, không thể hủy")

        db.donhang.update_one({"_id": ma_don}, {"$set": {"trang_thai": TRANG_THAI_DA_HUY}}, session=session)
        db.hoadon.update_one({"ma_don": ma_don}, {"$set": {"trang_thai": TRANG_THAI_DA_HUY}}, session=session)
        return {"_id": ma_don, "trang_thai": TRANG_THAI_DA_HUY}

    with db.client.start_session() as session:
        return session.with_transaction(_thuc_hien)
