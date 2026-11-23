"""Nghiệp vụ ghi dữ liệu bằng MongoDB multi-document transaction (replica set rs0).

Mọi nghiệp vụ ghi quan trọng (đặt hàng trừ tồn kho, hủy đơn hoàn tồn kho,
cập nhật đơn hàng, lập phiếu nhập/xuất kho) đều chạy trong session.with_transaction().
Khi có lỗi nghiệp vụ (NghiepVuError), toàn bộ thay đổi trong transaction bị rollback.
"""
from datetime import datetime, timezone
import re
import uuid

from werkzeug.security import generate_password_hash

from app.auth import kiem_tra_mat_khau

TRANG_THAI_CHO_XN = "CHO_XAC_NHAN"
TRANG_THAI_CHUAN_BI = "DANG_CHUAN_BI"
TRANG_THAI_DANG_GIAO = "DANG_GIAO"
TRANG_THAI_HOAN_THANH = "HOAN_THANH"
TRANG_THAI_DA_HUY = "DA_HUY"

TRANG_THAI_DON = (
    TRANG_THAI_CHO_XN,
    TRANG_THAI_CHUAN_BI,
    TRANG_THAI_DANG_GIAO,
    TRANG_THAI_HOAN_THANH,
    TRANG_THAI_DA_HUY,
)

BUOC_TIEP_THEO = {
    TRANG_THAI_CHO_XN: TRANG_THAI_CHUAN_BI,
    TRANG_THAI_CHUAN_BI: TRANG_THAI_DANG_GIAO,
    TRANG_THAI_DANG_GIAO: TRANG_THAI_HOAN_THANH,
}

TT_CHUA = "CHUA_THANH_TOAN"
TT_DA = "DA_THANH_TOAN"
PHUONG_THUC_TT = ("COD", "CHUYEN_KHOAN")
LOAI_PHIEU = ("NHAP", "XUAT")

NGUONG_FREESHIP = 500_000
PHI_SHIP_MAC_DINH = 30_000


class NghiepVuError(Exception):
    """Lỗi nghiệp vụ: làm transaction bị rollback."""


def _now():
    return datetime.now(timezone.utc)


def tinh_phi_ship(tam_tinh):
    return 0 if tam_tinh >= NGUONG_FREESHIP else PHI_SHIP_MAC_DINH


def ma_tiep_theo(collection, tien_to, do_dai, session=None):
    """Sinh mã tuần tự theo mã lớn nhất hiện có (ví dụ DH000001)."""
    cuoi = collection.find(
        {"_id": {"$regex": f"^{tien_to}[0-9]+$"}},
        {"_id": 1},
        session=session,
    ).sort("_id", -1).limit(1)
    so = 0
    for doc in cuoi:
        so = int(doc["_id"][len(tien_to):])
    return f"{tien_to}{so + 1:0{do_dai}d}"


def dang_ky_khach_hang(db, ten_dang_nhap, mat_khau, ho_ten, sdt, dia_chi="", email=None):
    """Tạo tài khoản khách hàng (nguoidung + khachhang) trong một transaction."""
    ten = (ten_dang_nhap or "").strip().lower()
    ho_ten = (ho_ten or "").strip()
    sdt = (sdt or "").strip()
    dia_chi = (dia_chi or "").strip()
    email = (email or "").strip() or None

    if len(ten) < 3 or " " in ten:
        raise NghiepVuError("Tên đăng nhập tối thiểu 3 ký tự và không chứa khoảng trắng")
    if len(mat_khau or "") < 6:
        raise NghiepVuError("Mật khẩu tối thiểu 6 ký tự")
    if not ho_ten:
        raise NghiepVuError("Vui lòng nhập họ tên")
    if not sdt or len(sdt) < 8:
        raise NghiepVuError("Số điện thoại không hợp lệ")

    pw_hash = generate_password_hash(mat_khau, method="pbkdf2:sha256:60000")

    def _thuc_hien(session):
        if db.nguoidung.find_one({"ten_dang_nhap": ten}, session=session):
            raise NghiepVuError(f"Tên đăng nhập '{ten}' đã được sử dụng")

        ma_kh = ma_tiep_theo(db.khachhang, "KH", 4, session=session)
        ma_nd = f"ND-{ma_kh}"
        nd = {
            "_id": ma_nd,
            "ten_dang_nhap": ten,
            "mat_khau": pw_hash,
            "vai_tro": "KH",
            "ho_ten": ho_ten,
            "email": email,
            "hoat_dong": True,
        }
        kh = {
            "_id": ma_kh,
            "ten_kh": ho_ten,
            "sdt": sdt,
            "dia_chi": dia_chi,
            "email": email,
            "ma_nd": ma_nd,
            "hoat_dong": True,
        }
        db.nguoidung.insert_one(nd, session=session)
        db.khachhang.insert_one(kh, session=session)
        return nd, kh

    with db.client.start_session() as session:
        return session.with_transaction(_thuc_hien)


def tao_tai_khoan(db, ten_dang_nhap, mat_khau, ho_ten, vai_tro, email=None, sdt="", dia_chi=""):
    """Admin tạo tài khoản mới cho bất kỳ vai trò nào (ADMIN, NV, KH) trong một transaction."""
    ten = (ten_dang_nhap or "").strip().lower()
    ho_ten = (ho_ten or "").strip()
    vai_tro = (vai_tro or "").strip().upper()
    email = (email or "").strip() or None
    sdt = (sdt or "").strip()
    dia_chi = (dia_chi or "").strip()

    if vai_tro not in ("ADMIN", "NV", "KH"):
        raise NghiepVuError("Vai trò phải là ADMIN, NV hoặc KH")
    if len(ten) < 3 or " " in ten:
        raise NghiepVuError("Tên đăng nhập tối thiểu 3 ký tự và không chứa khoảng trắng")
    if len(mat_khau or "") < 6:
        raise NghiepVuError("Mật khẩu tối thiểu 6 ký tự")
    if not ho_ten:
        raise NghiepVuError("Vui lòng nhập họ tên")
    if vai_tro == "KH" and len(sdt) < 8:
        raise NghiepVuError("Tài khoản Khách hàng cần số điện thoại hợp lệ (tối thiểu 8 ký tự)")

    pw_hash = generate_password_hash(mat_khau, method="pbkdf2:sha256:60000")

    def _thuc_hien(session):
        if db.nguoidung.find_one({"ten_dang_nhap": ten}, session=session):
            raise NghiepVuError(f"Tên đăng nhập '{ten}' đã tồn tại")

        if vai_tro == "KH":
            ma_kh = ma_tiep_theo(db.khachhang, "KH", 4, session=session)
            ma_nd = f"ND-{ma_kh}"
            nd = {
                "_id": ma_nd,
                "ten_dang_nhap": ten,
                "mat_khau": pw_hash,
                "vai_tro": "KH",
                "ho_ten": ho_ten,
                "email": email,
                "hoat_dong": True,
            }
            kh = {
                "_id": ma_kh,
                "ten_kh": ho_ten,
                "sdt": sdt,
                "dia_chi": dia_chi,
                "email": email,
                "ma_nd": ma_nd,
                "hoat_dong": True,
            }
            db.nguoidung.insert_one(nd, session=session)
            db.khachhang.insert_one(kh, session=session)
            return nd

        tien_to = "ND-AD" if vai_tro == "ADMIN" else "ND-NV"
        ma_nd = ma_tiep_theo(db.nguoidung, tien_to, 3, session=session)
        nd = {
            "_id": ma_nd,
            "ten_dang_nhap": ten,
            "mat_khau": pw_hash,
            "vai_tro": vai_tro,
            "ho_ten": ho_ten,
            "email": email,
            "hoat_dong": True,
        }
        db.nguoidung.insert_one(nd, session=session)
        return nd

    with db.client.start_session() as session:
        return session.with_transaction(_thuc_hien)


def cap_nhat_tai_khoan(db, ma_nd, ho_ten, vai_tro, email=None, mat_khau_moi="", ma_nd_hien_tai=None, sdt="", dia_chi=""):
    """Admin sửa họ tên, email, vai trò và (tùy chọn) đặt lại mật khẩu trong một transaction."""
    ho_ten = (ho_ten or "").strip()
    vai_tro = (vai_tro or "").strip().upper()
    email = (email or "").strip() or None
    mat_khau_moi = mat_khau_moi or ""
    sdt = (sdt or "").strip()
    dia_chi = (dia_chi or "").strip()

    if vai_tro not in ("ADMIN", "NV", "KH"):
        raise NghiepVuError("Vai trò phải là ADMIN, NV hoặc KH")
    if not ho_ten:
        raise NghiepVuError("Họ tên không được để trống")
    if mat_khau_moi and len(mat_khau_moi) < 6:
        raise NghiepVuError("Mật khẩu mới tối thiểu 6 ký tự")
    if ma_nd == ma_nd_hien_tai and vai_tro != "ADMIN":
        raise NghiepVuError("Không thể tự hạ vai trò Quản trị viên của chính mình")

    pw_hash = generate_password_hash(mat_khau_moi, method="pbkdf2:sha256:60000") if mat_khau_moi else None

    def _thuc_hien(session):
        nd = db.nguoidung.find_one({"_id": ma_nd}, session=session)
        if nd is None:
            raise NghiepVuError(f"Tài khoản {ma_nd} không tồn tại")

        if nd["vai_tro"] == "ADMIN" and vai_tro != "ADMIN":
            so_admin_hd = db.nguoidung.count_documents(
                {"vai_tro": "ADMIN", "hoat_dong": {"$ne": False}, "_id": {"$ne": ma_nd}},
                session=session,
            )
            if so_admin_hd == 0:
                raise NghiepVuError("Phải giữ lại ít nhất một tài khoản Quản trị viên đang hoạt động")

        updates = {"ho_ten": ho_ten, "vai_tro": vai_tro, "email": email}
        if pw_hash:
            updates["mat_khau"] = pw_hash
        db.nguoidung.update_one({"_id": ma_nd}, {"$set": updates}, session=session)

        kh = db.khachhang.find_one({"ma_nd": ma_nd}, session=session)
        if vai_tro == "KH":
            if kh:
                kh_up = {"ten_kh": ho_ten, "email": email}
                if sdt:
                    kh_up["sdt"] = sdt
                if dia_chi or "dia_chi" in kh:
                    kh_up["dia_chi"] = dia_chi
                db.khachhang.update_one({"_id": kh["_id"]}, {"$set": kh_up}, session=session)
            else:
                if len(sdt) < 8:
                    raise NghiepVuError("Chuyển sang vai trò Khách hàng cần nhập số điện thoại (tối thiểu 8 ký tự)")
                ma_kh = ma_tiep_theo(db.khachhang, "KH", 4, session=session)
                db.khachhang.insert_one(
                    {
                        "_id": ma_kh,
                        "ten_kh": ho_ten,
                        "sdt": sdt,
                        "dia_chi": dia_chi,
                        "email": email,
                        "ma_nd": ma_nd,
                        "hoat_dong": nd.get("hoat_dong") is not False,
                    },
                    session=session,
                )
        elif kh:
            db.khachhang.update_one({"_id": kh["_id"]}, {"$set": {"ten_kh": ho_ten, "email": email}}, session=session)

        return db.nguoidung.find_one({"_id": ma_nd}, session=session)

    with db.client.start_session() as session:
        return session.with_transaction(_thuc_hien)


def doi_trang_thai_tai_khoan(db, ma_nd, ma_nd_hien_tai=None):
    """Khóa hoặc mở khóa tài khoản (đồng bộ sang khachhang nếu có). Chống tự khóa và khóa Admin cuối."""
    if ma_nd == ma_nd_hien_tai:
        raise NghiepVuError("Không thể tự khóa tài khoản đang đăng nhập")

    def _thuc_hien(session):
        nd = db.nguoidung.find_one({"_id": ma_nd}, session=session)
        if nd is None:
            raise NghiepVuError(f"Tài khoản {ma_nd} không tồn tại")

        mo_lai = nd.get("hoat_dong") is False
        if not mo_lai and nd["vai_tro"] == "ADMIN":
            so_admin_hd = db.nguoidung.count_documents(
                {"vai_tro": "ADMIN", "hoat_dong": {"$ne": False}, "_id": {"$ne": ma_nd}},
                session=session,
            )
            if so_admin_hd == 0:
                raise NghiepVuError("Không thể khóa tài khoản Quản trị viên duy nhất còn hoạt động")

        db.nguoidung.update_one({"_id": ma_nd}, {"$set": {"hoat_dong": mo_lai}}, session=session)
        db.khachhang.update_one({"ma_nd": ma_nd}, {"$set": {"hoat_dong": mo_lai}}, session=session)
        return mo_lai

    with db.client.start_session() as session:
        return session.with_transaction(_thuc_hien)


def cap_nhat_ho_so_ca_nhan(db, ma_nd, ho_ten, email=None, sdt="", dia_chi=""):
    """Người dùng tự sửa thông tin cá nhân của chính mình (ADMIN, NV, KH). Không đổi vai trò."""
    ho_ten = (ho_ten or "").strip()
    email = (email or "").strip() or None
    sdt = (sdt or "").strip()
    dia_chi = (dia_chi or "").strip()

    if not ho_ten:
        raise NghiepVuError("Họ tên không được để trống")
    if sdt and not re.fullmatch(r"[0-9+ ]{8,15}", sdt):
        raise NghiepVuError("Số điện thoại chỉ gồm chữ số (8 đến 15 ký tự)")

    def _thuc_hien(session):
        nd = db.nguoidung.find_one({"_id": ma_nd}, session=session)
        if nd is None:
            raise NghiepVuError("Tài khoản không tồn tại")
        if nd["vai_tro"] == "KH" and not sdt:
            raise NghiepVuError("Vui lòng nhập số điện thoại nhận hàng")

        db.nguoidung.update_one(
            {"_id": ma_nd},
            {"$set": {"ho_ten": ho_ten, "email": email, "sdt": sdt or None}},
            session=session,
        )
        kh = db.khachhang.find_one({"ma_nd": ma_nd}, session=session)
        if kh:
            kh_up = {"ten_kh": ho_ten, "email": email, "sdt": sdt or kh["sdt"], "dia_chi": dia_chi}
            so_dc = list(kh.get("so_dia_chi") or [])
            if so_dc and dia_chi:
                for d in so_dc:
                    if d.get("mac_dinh"):
                        d["dia_chi"] = dia_chi
                        break
                kh_up["so_dia_chi"] = so_dc
            db.khachhang.update_one(
                {"_id": kh["_id"]},
                {"$set": kh_up},
                session=session,
            )
        return db.nguoidung.find_one({"_id": ma_nd}, {"mat_khau": 0}, session=session)

    with db.client.start_session() as session:
        return session.with_transaction(_thuc_hien)


def doi_mat_khau_ca_nhan(db, ma_nd, mat_khau_cu, mat_khau_moi, xac_nhan):
    """Người dùng tự đổi mật khẩu sau khi xác thực mật khẩu hiện tại."""
    if not mat_khau_cu:
        raise NghiepVuError("Vui lòng nhập mật khẩu hiện tại")
    if len(mat_khau_moi or "") < 6:
        raise NghiepVuError("Mật khẩu mới tối thiểu 6 ký tự")
    if mat_khau_moi != xac_nhan:
        raise NghiepVuError("Mật khẩu xác nhận không khớp")

    nd = db.nguoidung.find_one({"_id": ma_nd})
    if nd is None:
        raise NghiepVuError("Tài khoản không tồn tại")
    if not kiem_tra_mat_khau(nd.get("mat_khau"), mat_khau_cu):
        raise NghiepVuError("Mật khẩu hiện tại không đúng")

    pw_hash = generate_password_hash(mat_khau_moi, method="pbkdf2:sha256:60000")
    db.nguoidung.update_one({"_id": ma_nd}, {"$set": {"mat_khau": pw_hash}})
    return True


def dat_hang(
    db,
    ma_don,
    ma_kh,
    dong_hang,
    giao_hang,
    phuong_thuc_tt="COD",
    xoa_gio=False,
    ngay_dat=None,
):
    """Đặt hàng bán lẻ thời trang trong MỘT transaction:
    1. Kiểm tra khách hàng & từng biến thể sản phẩm đang bán.
    2. Trừ tồn kho atomic trên `sanpham.bien_the[].ton_kho` (điều kiện `ton_kho >= so_luong`).
    3. Tạo `donhang` + `hoadon` (chụp đơn giá & tên sản phẩm tại thời điểm mua).
    4. Xóa `giohang` của khách nếu `xoa_gio=True`.
    Nếu bất kỳ dòng nào thiếu tồn kho, toàn bộ transaction bị rollback.
    """
    if not dong_hang:
        raise NghiepVuError("Đơn hàng phải có ít nhất một sản phẩm")

    phuong_thuc_tt = (phuong_thuc_tt or "COD").upper()
    if phuong_thuc_tt not in PHUONG_THUC_TT:
        raise NghiepVuError("Phương thức thanh toán không hợp lệ")

    ho_ten = (giao_hang.get("ho_ten") or "").strip()
    sdt = (giao_hang.get("sdt") or "").strip()
    dia_chi = (giao_hang.get("dia_chi") or "").strip()
    ghi_chu = (giao_hang.get("ghi_chu") or "").strip()
    if not ho_ten or not sdt or not dia_chi:
        raise NghiepVuError("Vui lòng điền đầy đủ họ tên, số điện thoại và địa chỉ giao hàng")

    ngay_dat = ngay_dat or _now()

    def _thuc_hien(session):
        kh = db.khachhang.find_one({"_id": ma_kh}, session=session)
        if kh is None:
            raise NghiepVuError(f"Khách hàng {ma_kh} không tồn tại")
        if kh.get("hoat_dong") is False:
            raise NghiepVuError("Tài khoản khách hàng đã ngừng hoạt động")

        chi_tiet = []
        for dong in dong_hang:
            ma_sp = dong["ma_sp"]
            mau = (dong.get("mau") or "").strip()
            size = (dong.get("size") or "").strip()
            try:
                so_luong = int(dong["so_luong"])
            except (TypeError, ValueError) as exc:
                raise NghiepVuError("Số lượng phải là số nguyên dương") from exc
            if so_luong <= 0:
                raise NghiepVuError(f"Số lượng của {ma_sp} phải lớn hơn 0")
            if not mau or not size:
                raise NghiepVuError(f"Vui lòng chọn đủ màu và size cho sản phẩm {ma_sp}")

            sp = db.sanpham.find_one({"_id": ma_sp}, session=session)
            if sp is None:
                raise NghiepVuError(f"Sản phẩm {ma_sp} không tồn tại")
            if sp.get("hoat_dong") is False:
                raise NghiepVuError(f"Sản phẩm {sp['ten_sp']} đã ngừng kinh doanh")

            # Kiểm tra và trừ tồn kho atomic đúng biến thể Màu × Size
            kq = db.sanpham.update_one(
                {
                    "_id": ma_sp,
                    "bien_the": {"$elemMatch": {"mau": mau, "size": size, "ton_kho": {"$gte": so_luong}}},
                },
                {"$inc": {"bien_the.$.ton_kho": -so_luong}},
                session=session,
            )
            if kq.matched_count == 0:
                co_bien_the = any(
                    bt["mau"] == mau and bt["size"] == size for bt in sp.get("bien_the", [])
                )
                if not co_bien_the:
                    raise NghiepVuError(f"Sản phẩm {sp['ten_sp']} không có phiên bản {mau} / {size}")
                raise NghiepVuError(
                    f"Sản phẩm {sp['ten_sp']} ({mau} / {size}) không đủ tồn kho cho số lượng {so_luong}"
                )

            anh = (sp.get("hinh_anh") or [""])[0]
            chi_tiet.append({
                "ma_sp": ma_sp,
                "ten_sp": sp["ten_sp"],
                "mau": mau,
                "size": size,
                "so_luong": so_luong,
                "don_gia": sp["don_gia"],
                "hinh_anh": anh,
            })

        tam_tinh = sum(d["so_luong"] * d["don_gia"] for d in chi_tiet)
        phi_ship = tinh_phi_ship(tam_tinh)
        tong = tam_tinh + phi_ship

        don = {
            "_id": ma_don,
            "ngay_dat": ngay_dat,
            "trang_thai": TRANG_THAI_CHO_XN,
            "trang_thai_tt": TT_CHUA,
            "phuong_thuc_tt": phuong_thuc_tt,
            "ma_kh": ma_kh,
            "giao_hang": {
                "ho_ten": ho_ten,
                "sdt": sdt,
                "dia_chi": dia_chi,
                "ghi_chu": ghi_chu,
            },
            "chi_tiet": chi_tiet,
            "phi_van_chuyen": phi_ship,
            "tong_tien": tong,
            "lich_su": [
                {"thoi_gian": ngay_dat, "trang_thai": TRANG_THAI_CHO_XN, "ghi_chu": "Khách hàng đặt đơn mới"}
            ],
        }
        db.donhang.insert_one(don, session=session)
        db.hoadon.insert_one(
            {
                "_id": f"HD{ma_don}",
                "ngay_xuat": ngay_dat,
                "tong_tien": tong,
                "ma_don": ma_don,
                "trang_thai": TRANG_THAI_CHO_XN,
            },
            session=session,
        )
        if xoa_gio:
            db.giohang.delete_one({"_id": ma_kh}, session=session)
        return don

    with db.client.start_session() as session:
        return session.with_transaction(_thuc_hien)


def huy_don(db, ma_don, nguoi_huy="ADMIN", ly_do="Hủy đơn hàng"):
    """Hủy đơn hàng và HOÀN LẠI tồn kho thành phẩm trong một transaction.

    - Nếu người hủy là khách hàng (`KH`): chỉ cho phép khi đơn đang `CHO_XAC_NHAN`.
    - Nếu người hủy là `ADMIN`: cho hủy mọi đơn chưa `HOAN_THANH` và chưa `DA_HUY`.
    """
    ngay = _now()

    def _thuc_hien(session):
        don = db.donhang.find_one({"_id": ma_don}, session=session)
        if don is None:
            raise NghiepVuError(f"Đơn hàng {ma_don} không tồn tại")
        if don["trang_thai"] == TRANG_THAI_DA_HUY:
            raise NghiepVuError("Đơn hàng đã bị hủy trước đó")
        if don["trang_thai"] == TRANG_THAI_HOAN_THANH:
            raise NghiepVuError("Đơn hàng đã hoàn thành, không thể hủy")
        if nguoi_huy == "KH" and don["trang_thai"] != TRANG_THAI_CHO_XN:
            raise NghiepVuError("Chỉ có thể tự hủy đơn khi đang ở trạng thái Chờ xác nhận")

        # Hoàn lại tồn kho cho từng biến thể đã trừ
        for dong in don["chi_tiet"]:
            db.sanpham.update_one(
                {
                    "_id": dong["ma_sp"],
                    "bien_the": {"$elemMatch": {"mau": dong["mau"], "size": dong["size"]}},
                },
                {"$inc": {"bien_the.$.ton_kho": dong["so_luong"]}},
                session=session,
            )

        db.donhang.update_one(
            {"_id": ma_don},
            {
                "$set": {"trang_thai": TRANG_THAI_DA_HUY},
                "$push": {
                    "lich_su": {
                        "thoi_gian": ngay,
                        "trang_thai": TRANG_THAI_DA_HUY,
                        "ghi_chu": ly_do,
                    }
                },
            },
            session=session,
        )
        db.hoadon.update_one(
            {"ma_don": ma_don},
            {"$set": {"trang_thai": TRANG_THAI_DA_HUY}},
            session=session,
        )
        return {"_id": ma_don, "trang_thai": TRANG_THAI_DA_HUY}

    with db.client.start_session() as session:
        return session.with_transaction(_thuc_hien)


def cap_nhat_don_hang(db, ma_don, trang_thai_moi=None, trang_thai_tt=None, ghi_chu=""):
    """Cập nhật tiến độ giao hàng và/hoặc xác nhận thanh toán (ADMIN, NV)."""
    ngay = _now()

    def _thuc_hien(session):
        don = db.donhang.find_one({"_id": ma_don}, session=session)
        if don is None:
            raise NghiepVuError(f"Đơn hàng {ma_don} không tồn tại")
        if don["trang_thai"] == TRANG_THAI_DA_HUY:
            raise NghiepVuError("Đơn đã hủy, không thể cập nhật")

        updates = {}
        lich_su_moi = []
        if trang_thai_moi and trang_thai_moi != don["trang_thai"]:
            if trang_thai_moi == TRANG_THAI_DA_HUY:
                raise NghiepVuError("Vui lòng dùng chức năng Hủy đơn để hoàn tồn kho")
            if trang_thai_moi not in TRANG_THAI_DON:
                raise NghiepVuError("Trạng thái đơn không hợp lệ")
            if don["trang_thai"] == TRANG_THAI_HOAN_THANH:
                raise NghiepVuError("Đơn đã hoàn thành, không thể đổi trạng thái")
            updates["trang_thai"] = trang_thai_moi
            # Đơn hoàn thành thì mặc định đã thanh toán (COD đã thu tiền)
            if trang_thai_moi == TRANG_THAI_HOAN_THANH:
                updates["trang_thai_tt"] = TT_DA
            lich_su_moi.append({
                "thoi_gian": ngay,
                "trang_thai": trang_thai_moi,
                "ghi_chu": ghi_chu or f"Cập nhật sang {trang_thai_moi}",
            })

        if trang_thai_tt and trang_thai_tt != don["trang_thai_tt"]:
            if trang_thai_tt not in (TT_CHUA, TT_DA):
                raise NghiepVuError("Trạng thái thanh toán không hợp lệ")
            updates["trang_thai_tt"] = trang_thai_tt
            if not lich_su_moi:
                lich_su_moi.append({
                    "thoi_gian": ngay,
                    "trang_thai": don["trang_thai"],
                    "ghi_chu": ghi_chu or ("Xác nhận đã thanh toán" if trang_thai_tt == TT_DA else "Đánh dấu chưa thanh toán"),
                })

        if not updates:
            return don

        op = {"$set": updates}
        if lich_su_moi:
            op["$push"] = {"lich_su": {"$each": lich_su_moi}}
        db.donhang.update_one({"_id": ma_don}, op, session=session)
        if "trang_thai" in updates:
            db.hoadon.update_one(
                {"ma_don": ma_don},
                {"$set": {"trang_thai": updates["trang_thai"]}},
                session=session,
            )
        return db.donhang.find_one({"_id": ma_don}, session=session)

    with db.client.start_session() as session:
        return session.with_transaction(_thuc_hien)


def lap_phieu_kho(db, ma_phieu, loai, dong_hang, nguoi_lap="admin", ghi_chu="", ngay_lap=None):
    """Lập phiếu nhập/xuất kho THÀNH PHẨM theo từng (ma_sp, mau, size) trong một transaction.

    Phiếu XUAT kiểm tra tồn kho trực tiếp trong update_one (`ton_kho >= so_luong`);
    nếu bất kỳ biến thể nào thiếu hàng, toàn bộ phiếu được rollback.
    """
    loai = (loai or "").upper()
    if loai not in LOAI_PHIEU:
        raise NghiepVuError("Loại phiếu phải là NHAP hoặc XUAT")
    if not dong_hang:
        raise NghiepVuError("Phiếu kho phải có ít nhất một dòng sản phẩm")
    ngay_lap = ngay_lap or _now()

    def _thuc_hien(session):
        chi_tiet = []
        for dong in dong_hang:
            ma_sp = dong["ma_sp"]
            mau = (dong.get("mau") or "").strip()
            size = (dong.get("size") or "").strip()
            try:
                so_luong = int(dong["so_luong"])
            except (TypeError, ValueError) as exc:
                raise NghiepVuError("Số lượng phải là số nguyên dương") from exc
            if so_luong <= 0:
                raise NghiepVuError(f"Số lượng của {ma_sp} phải lớn hơn 0")
            if not mau or not size:
                raise NghiepVuError(f"Vui lòng chọn đủ màu và size cho {ma_sp}")

            sp = db.sanpham.find_one({"_id": ma_sp}, session=session)
            if sp is None:
                raise NghiepVuError(f"Sản phẩm {ma_sp} không tồn tại")

            if loai == "NHAP":
                kq = db.sanpham.update_one(
                    {"_id": ma_sp, "bien_the": {"$elemMatch": {"mau": mau, "size": size}}},
                    {"$inc": {"bien_the.$.ton_kho": so_luong}},
                    session=session,
                )
                if kq.matched_count == 0:
                    # Tự thêm biến thể mới nếu nhập màu/size mới
                    db.sanpham.update_one(
                        {"_id": ma_sp},
                        {"$push": {"bien_the": {"mau": mau, "size": size, "ton_kho": so_luong}}},
                        session=session,
                    )
            else:
                kq = db.sanpham.update_one(
                    {
                        "_id": ma_sp,
                        "bien_the": {"$elemMatch": {"mau": mau, "size": size, "ton_kho": {"$gte": so_luong}}},
                    },
                    {"$inc": {"bien_the.$.ton_kho": -so_luong}},
                    session=session,
                )
                if kq.matched_count == 0:
                    raise NghiepVuError(
                        f"Không đủ tồn kho để xuất {so_luong} sản phẩm {sp['ten_sp']} ({mau} / {size})"
                    )

            chi_tiet.append({
                "ma_sp": ma_sp,
                "ten_sp": sp["ten_sp"],
                "mau": mau,
                "size": size,
                "so_luong": so_luong,
            })

        phieu = {
            "_id": ma_phieu,
            "loai": loai,
            "ngay_lap": ngay_lap,
            "nguoi_lap": nguoi_lap,
            "ghi_chu": (ghi_chu or "").strip(),
            "chi_tiet": chi_tiet,
        }
        db.phieukho.insert_one(phieu, session=session)
        return phieu

    with db.client.start_session() as session:
        return session.with_transaction(_thuc_hien)


# ---------- Giỏ hàng khách hàng (lưu MongoDB `giohang`) ----------

def lay_gio_hang(db, ma_kh):
    doc = db.giohang.find_one({"_id": ma_kh})
    return list(doc.get("items", [])) if doc else []


def luu_gio_hang(db, ma_kh, items):
    if not items:
        db.giohang.delete_one({"_id": ma_kh})
        return []
    db.giohang.update_one(
        {"_id": ma_kh},
        {"$set": {"items": items, "cap_nhat": _now()}},
        upsert=True,
    )
    return items


def them_vao_gio(db, ma_kh, ma_sp, mau, size, so_luong=1):
    """Thêm/cộng dồn một biến thể vào giỏ hàng MongoDB của khách."""
    try:
        so_luong = int(so_luong)
    except (TypeError, ValueError) as exc:
        raise NghiepVuError("Số lượng không hợp lệ") from exc
    if so_luong <= 0:
        raise NghiepVuError("Số lượng phải lớn hơn 0")

    sp = db.sanpham.find_one({"_id": ma_sp, "hoat_dong": {"$ne": False}})
    if sp is None:
        raise NghiepVuError("Sản phẩm không tồn tại hoặc đã ngừng bán")
    bt = next((b for b in sp.get("bien_the", []) if b["mau"] == mau and b["size"] == size), None)
    if bt is None:
        raise NghiepVuError("Phiên bản màu/size không hợp lệ")

    items = lay_gio_hang(db, ma_kh)
    tim_thay = False
    for it in items:
        if it["ma_sp"] == ma_sp and it["mau"] == mau and it["size"] == size:
            sl_moi = it["so_luong"] + so_luong
            if sl_moi > bt["ton_kho"]:
                raise NghiepVuError(f"Chỉ còn {bt['ton_kho']} sản phẩm cho phiên bản {mau} / {size}")
            it["so_luong"] = sl_moi
            tim_thay = True
            break
    if not tim_thay:
        if so_luong > bt["ton_kho"]:
            raise NghiepVuError(f"Chỉ còn {bt['ton_kho']} sản phẩm cho phiên bản {mau} / {size}")
        items.append({"ma_sp": ma_sp, "mau": mau, "size": size, "so_luong": so_luong})

    return luu_gio_hang(db, ma_kh, items)


# ---------- Hạng thành viên, Sổ địa chỉ, Yêu thích, Mua lại & Đánh giá (KH) ----------

HANG_THANH_VIEN = (
    ("THANH_VIEN", "Thành viên", 0, "Miễn phí vận chuyển cho đơn từ 500.000 ₫"),
    ("BAC", "Hạng Bạc", 5_000_000, "Ưu tiên xử lý đơn & đổi trả linh hoạt 30 ngày"),
    ("VANG", "Hạng Vàng", 15_000_000, "Miễn phí chỉnh sửa phom dáng 180 ngày & ưu tiên hàng mới"),
    ("KIM_CUONG", "Kim Cương", 35_000_000, "Đặc quyền VIP — ưu tiên bộ sưu tập giới hạn & chăm sóc riêng"),
)

PHOM_DANH_GIA = ("Hơi chật", "Vừa vặn", "Hơi rộng")


def tinh_hang_thanh_vien(tong_chi_hoan_thanh):
    """Tính hạng thành viên và tiến độ lên hạng từ tổng chi tiêu đơn HOAN_THANH."""
    tong = max(0, int(tong_chi_hoan_thanh or 0))
    idx = 0
    for i, (_, _, moc, _) in enumerate(HANG_THANH_VIEN):
        if tong >= moc:
            idx = i
    ma, ten, moc_hien_tai, quyen_loi = HANG_THANH_VIEN[idx]
    if idx + 1 < len(HANG_THANH_VIEN):
        _, hang_tiep, moc_tiep, _ = HANG_THANH_VIEN[idx + 1]
        khoang = max(1, moc_tiep - moc_hien_tai)
        phan_tram = min(100, int(((tong - moc_hien_tai) * 100) / khoang))
        con_thieu = max(0, moc_tiep - tong)
    else:
        hang_tiep, moc_tiep, phan_tram, con_thieu = None, None, 100, 0
    return {
        "ma": ma,
        "ten": ten,
        "quyen_loi": quyen_loi,
        "tong_chi": tong,
        "hang_tiep": hang_tiep,
        "moc_tiep": moc_tiep,
        "con_thieu": con_thieu,
        "phan_tram": phan_tram,
    }


def lay_so_dia_chi(khach):
    """Trả về danh sách sổ địa chỉ của khách; tương thích ngược với trường dia_chi đơn cũ."""
    if not khach:
        return []
    ds = list(khach.get("so_dia_chi") or [])
    if ds:
        ds.sort(key=lambda d: (0 if d.get("mac_dinh") else 1, d.get("id", "")))
        return ds
    if (khach.get("dia_chi") or "").strip():
        return [{
            "id": "DC-MAC-DINH",
            "nhan": "Mặc định",
            "ho_ten": khach.get("ten_kh", ""),
            "sdt": khach.get("sdt", ""),
            "dia_chi": khach["dia_chi"].strip(),
            "mac_dinh": True,
        }]
    return []


def luu_dia_chi(db, ma_kh, ho_ten, sdt, dia_chi, nhan="Nhà riêng", mac_dinh=False, id_dc=None):
    """Thêm mới hoặc cập nhật một địa chỉ trong mảng nhúng `khachhang.so_dia_chi`."""
    ho_ten = (ho_ten or "").strip()
    sdt = (sdt or "").strip()
    dia_chi = (dia_chi or "").strip()
    nhan = (nhan or "Nhà riêng").strip()[:40] or "Nhà riêng"

    if not ho_ten:
        raise NghiepVuError("Vui lòng nhập họ tên người nhận")
    if not re.fullmatch(r"[0-9+ ]{8,15}", sdt):
        raise NghiepVuError("Số điện thoại người nhận chỉ gồm 8 đến 15 chữ số")
    if not dia_chi:
        raise NghiepVuError("Vui lòng nhập địa chỉ giao hàng chi tiết")

    khach = db.khachhang.find_one({"_id": ma_kh})
    if khach is None:
        raise NghiepVuError("Không tìm thấy hồ sơ khách hàng")

    ds = list(khach.get("so_dia_chi") or [])
    if not ds and (khach.get("dia_chi") or "").strip() and id_dc != "DC-MAC-DINH":
        ds.append({
            "id": "DC-MAC-DINH",
            "nhan": "Mặc định",
            "ho_ten": khach.get("ten_kh", ""),
            "sdt": khach.get("sdt", ""),
            "dia_chi": khach["dia_chi"].strip(),
            "mac_dinh": True,
        })

    if id_dc:
        muc = next((d for d in ds if d["id"] == id_dc), None)
        if muc is None and id_dc == "DC-MAC-DINH":
            muc = {"id": "DC-MAC-DINH", "mac_dinh": True}
            ds.append(muc)
        if muc is None:
            raise NghiepVuError("Địa chỉ cần sửa không tồn tại")
        muc["nhan"] = nhan
        muc["ho_ten"] = ho_ten
        muc["sdt"] = sdt
        muc["dia_chi"] = dia_chi
        if mac_dinh:
            muc["mac_dinh"] = True
        target_id = muc["id"]
    else:
        target_id = f"DC-{uuid.uuid4().hex[:6].upper()}"
        ds.append({
            "id": target_id,
            "nhan": nhan,
            "ho_ten": ho_ten,
            "sdt": sdt,
            "dia_chi": dia_chi,
            "mac_dinh": bool(mac_dinh) or len(ds) == 0,
        })

    if mac_dinh or not any(d.get("mac_dinh") for d in ds):
        for d in ds:
            d["mac_dinh"] = d["id"] == target_id

    mac_dinh_doc = next((d for d in ds if d.get("mac_dinh")), ds[0])
    db.khachhang.update_one(
        {"_id": ma_kh},
        {"$set": {"so_dia_chi": ds, "dia_chi": mac_dinh_doc["dia_chi"]}},
    )
    return mac_dinh_doc


def dat_dia_chi_mac_dinh(db, ma_kh, id_dc):
    """Đặt một địa chỉ trong sổ địa chỉ làm mặc định và đồng bộ sang `khachhang.dia_chi`."""
    khach = db.khachhang.find_one({"_id": ma_kh})
    if khach is None:
        raise NghiepVuError("Không tìm thấy hồ sơ khách hàng")
    ds = lay_so_dia_chi(khach)
    if not any(d["id"] == id_dc for d in ds):
        raise NghiepVuError("Địa chỉ không tồn tại")
    for d in ds:
        d["mac_dinh"] = d["id"] == id_dc
    mac_dinh_doc = next(d for d in ds if d["mac_dinh"])
    db.khachhang.update_one(
        {"_id": ma_kh},
        {"$set": {"so_dia_chi": ds, "dia_chi": mac_dinh_doc["dia_chi"]}},
    )
    return mac_dinh_doc


def xoa_dia_chi(db, ma_kh, id_dc):
    """Xóa một địa chỉ khỏi sổ địa chỉ; tự chọn địa chỉ khác làm mặc định nếu còn."""
    khach = db.khachhang.find_one({"_id": ma_kh})
    if khach is None:
        raise NghiepVuError("Không tìm thấy hồ sơ khách hàng")
    ds = lay_so_dia_chi(khach)
    con_lai = [d for d in ds if d["id"] != id_dc]
    if len(con_lai) == len(ds):
        raise NghiepVuError("Địa chỉ không tồn tại")
    if con_lai and not any(d.get("mac_dinh") for d in con_lai):
        con_lai[0]["mac_dinh"] = True
    dia_chi_chinh = next((d["dia_chi"] for d in con_lai if d.get("mac_dinh")), "")
    db.khachhang.update_one(
        {"_id": ma_kh},
        {"$set": {"so_dia_chi": con_lai, "dia_chi": dia_chi_chinh}},
    )
    return con_lai


def lay_yeu_thich(db, ma_kh):
    """Lấy danh sách mã sản phẩm yêu thích được lưu trong MongoDB cho khách hàng."""
    kh = db.khachhang.find_one({"_id": ma_kh}, {"yeu_thich": 1})
    return list(kh.get("yeu_thich") or []) if kh else []


def chuyen_yeu_thich(db, ma_kh, ma_sp):
    """Thêm hoặc bỏ sản phẩm khỏi danh sách yêu thích của khách hàng trong MongoDB."""
    sp = db.sanpham.find_one({"_id": ma_sp, "hoat_dong": {"$ne": False}}, {"_id": 1})
    if sp is None:
        raise NghiepVuError("Sản phẩm không tồn tại hoặc đã ngừng bán")
    hien_tai = lay_yeu_thich(db, ma_kh)
    if ma_sp in hien_tai:
        db.khachhang.update_one({"_id": ma_kh}, {"$pull": {"yeu_thich": ma_sp}})
        hien_tai = [x for x in hien_tai if x != ma_sp]
        return False, hien_tai
    db.khachhang.update_one({"_id": ma_kh}, {"$addToSet": {"yeu_thich": ma_sp}})
    hien_tai.append(ma_sp)
    return True, hien_tai


def gop_yeu_thich(db, ma_kh, ds_ma_sp):
    """Gộp danh sách sản phẩm yêu thích tạm từ phiên khách vãng lai vào tài khoản KH."""
    if not ds_ma_sp:
        return
    hop_le = [
        d["_id"]
        for d in db.sanpham.find({"_id": {"$in": list(set(ds_ma_sp))}, "hoat_dong": {"$ne": False}}, {"_id": 1})
    ]
    if hop_le:
        db.khachhang.update_one({"_id": ma_kh}, {"$addToSet": {"yeu_thich": {"$each": hop_le}}})


def mua_lai_don(db, ma_kh, ma_don):
    """Đẩy lại toàn bộ sản phẩm còn hàng của một đơn cũ vào giỏ hàng MongoDB của khách."""
    don = db.donhang.find_one({"_id": ma_don})
    if don is None:
        raise NghiepVuError("Đơn hàng không tồn tại")
    if don["ma_kh"] != ma_kh:
        raise NghiepVuError("Bạn không có quyền thao tác trên đơn hàng này")

    da_them = 0
    bo_qua = []
    gio_hien_tai = lay_gio_hang(db, ma_kh)

    for ct in don.get("chi_tiet", []):
        sp = db.sanpham.find_one({"_id": ct["ma_sp"], "hoat_dong": {"$ne": False}})
        bt = next(
            (b for b in (sp or {}).get("bien_the", []) if b["mau"] == ct["mau"] and b["size"] == ct["size"]),
            None,
        )
        if not sp or not bt or bt["ton_kho"] <= 0:
            bo_qua.append(f"{ct['ten_sp']} ({ct['mau']} / {ct['size']})")
            continue
        dang_co = next(
            (
                i["so_luong"]
                for i in gio_hien_tai
                if i["ma_sp"] == ct["ma_sp"] and i["mau"] == ct["mau"] and i["size"] == ct["size"]
            ),
            0,
        )
        them_duoc = min(int(ct["so_luong"]), bt["ton_kho"] - dang_co)
        if them_duoc <= 0:
            bo_qua.append(f"{ct['ten_sp']} ({ct['mau']} / {ct['size']} — đã đủ tồn kho trong giỏ)")
            continue
        them_vao_gio(db, ma_kh, ct["ma_sp"], ct["mau"], ct["size"], them_duoc)
        gio_hien_tai = lay_gio_hang(db, ma_kh)
        da_them += them_duoc

    if da_them == 0:
        raise NghiepVuError("Các sản phẩm trong đơn này hiện đã hết hàng hoặc đã có đủ trong giỏ")
    return {"da_them": da_them, "bo_qua": bo_qua}


def kiem_tra_quyen_danh_gia(db, ma_kh, ma_sp):
    """Trả về mã đơn HOAN_THANH gần nhất của khách có chứa ma_sp (hoặc None nếu chưa mua xong)."""
    don = db.donhang.find_one(
        {"ma_kh": ma_kh, "trang_thai": TRANG_THAI_HOAN_THANH, "chi_tiet.ma_sp": ma_sp},
        {"_id": 1},
        sort=[("ngay_dat", -1)],
    )
    return don["_id"] if don else None


def tao_danh_gia(db, ma_kh, ma_sp, so_sao, noi_dung, phom_dang="Vừa vặn"):
    """Khách hàng đã hoàn thành đơn mua sản phẩm tạo hoặc cập nhật đánh giá (1–5 sao)."""
    try:
        so_sao = int(so_sao)
    except (TypeError, ValueError) as exc:
        raise NghiepVuError("Số sao đánh giá phải từ 1 đến 5") from exc
    if so_sao < 1 or so_sao > 5:
        raise NghiepVuError("Số sao đánh giá phải từ 1 đến 5")

    noi_dung = (noi_dung or "").strip()
    if len(noi_dung) < 5:
        raise NghiepVuError("Vui lòng nhập nhận xét tối thiểu 5 ký tự")
    if len(noi_dung) > 1000:
        raise NghiepVuError("Nhận xét tối đa 1000 ký tự")

    if phom_dang not in PHOM_DANH_GIA:
        phom_dang = "Vừa vặn"

    ma_don = kiem_tra_quyen_danh_gia(db, ma_kh, ma_sp)
    if ma_don is None:
        raise NghiepVuError("Chỉ khách hàng đã hoàn thành đơn mua sản phẩm này mới có thể đánh giá")

    khach = db.khachhang.find_one({"_id": ma_kh})
    if khach is None:
        raise NghiepVuError("Không tìm thấy hồ sơ khách hàng")

    da_co = db.danhgia.find_one({"ma_kh": ma_kh, "ma_sp": ma_sp})
    if da_co:
        db.danhgia.update_one(
            {"_id": da_co["_id"]},
            {"$set": {
                "ten_kh": khach["ten_kh"],
                "ma_don": ma_don,
                "so_sao": so_sao,
                "phom_dang": phom_dang,
                "noi_dung": noi_dung,
                "ngay_tao": _now(),
            }},
        )
        return db.danhgia.find_one({"_id": da_co["_id"]})

    doc = {
        "_id": ma_tiep_theo(db.danhgia, "DG", 5),
        "ma_sp": ma_sp,
        "ma_kh": ma_kh,
        "ten_kh": khach["ten_kh"],
        "ma_don": ma_don,
        "so_sao": so_sao,
        "phom_dang": phom_dang,
        "noi_dung": noi_dung,
        "ngay_tao": _now(),
    }
    db.danhgia.insert_one(doc)
    return doc


def lay_danh_gia_san_pham(db, ma_sp):
    """Tổng hợp danh sách đánh giá, điểm trung bình và phân bố sao cho 1 sản phẩm."""
    ds = list(db.danhgia.find({"ma_sp": ma_sp}).sort("ngay_tao", -1))
    tong = len(ds)
    phan_bo = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for d in ds:
        s = int(d.get("so_sao", 5))
        if s in phan_bo:
            phan_bo[s] += 1
    trung_binh = round(sum(d["so_sao"] for d in ds) / tong, 1) if tong else 0.0
    return {"ds": ds, "tong": tong, "trung_binh": trung_binh, "phan_bo": phan_bo}
