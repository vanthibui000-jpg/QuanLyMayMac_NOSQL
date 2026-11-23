"""Đăng nhập và phân quyền 3 vai trò: ADMIN, NV, KH (collection nguoidung, trường vai_tro).

- ADMIN (Quản trị viên): toàn quyền trong /admin (sản phẩm, khách hàng, hủy đơn, kho, báo cáo, MongoDB Explorer).
- NV (Nhân viên): vận hành hằng ngày trong /admin (xử lý đơn hàng, xác nhận thanh toán, nhập/xuất kho, xem SP/khách).
- KH (Khách hàng): mua sắm trên cửa hàng công khai (/), quản lý giỏ hàng, đặt hàng, theo dõi & tự hủy đơn của chính mình.
"""
import functools
import hashlib
import hmac

from flask import abort, session
from werkzeug.security import check_password_hash

VAI_TRO_NHAN = {
    "ADMIN": "Quản trị viên",
    "NV": "Nhân viên",
    "KH": "Khách hàng",
}

PHAN_QUYEN = {
    "xem_admin": {"ADMIN", "NV"},
    "xem_don": {"ADMIN", "NV"},
    "xu_ly_don": {"ADMIN", "NV"},
    "huy_don": {"ADMIN"},
    "xem_san_pham_admin": {"ADMIN", "NV"},
    "ql_san_pham": {"ADMIN"},
    "xem_khach": {"ADMIN", "NV"},
    "ql_khach": {"ADMIN"},
    "xem_kho": {"ADMIN", "NV"},
    "kho_ghi": {"ADMIN", "NV"},
    "bao_cao": {"ADMIN"},
    "xem_mongodb": {"ADMIN"},
    "ql_tai_khoan": {"ADMIN"},
    "mua_hang": {"KH"},
}


def kiem_tra_mat_khau(da_luu, nhap):
    """So khớp mật khẩu (hỗ trợ cả hash Werkzeug mới và SHA-256 hex cho dữ liệu demo)."""
    if not da_luu or not nhap:
        return False
    if da_luu.startswith(("scrypt:", "pbkdf2:")):
        return check_password_hash(da_luu, nhap)
    sha = hashlib.sha256(nhap.encode("utf-8")).hexdigest()
    return hmac.compare_digest(da_luu, sha)


def vai_tro_hien_tai():
    return session.get("vai_tro")


def la_khach_hang():
    return vai_tro_hien_tai() == "KH"


def la_noi_bo():
    return vai_tro_hien_tai() in ("ADMIN", "NV")


def ma_khach_hien_tai():
    return session.get("ma_kh")


def co_quyen(quyen):
    return vai_tro_hien_tai() in PHAN_QUYEN.get(quyen, set())


def nguoi_dung_hien_tai():
    if "ma_nd" not in session:
        return None
    vai_tro = session.get("vai_tro")
    return {
        "ma_nd": session["ma_nd"],
        "ten": session.get("ten", ""),
        "ho_ten": session.get("ho_ten") or session.get("ten", ""),
        "ma_kh": session.get("ma_kh"),
        "vai_tro": vai_tro,
        "vai_tro_nhan": VAI_TRO_NHAN.get(vai_tro, vai_tro),
    }


def cho_phep(quyen):
    """Decorator kiểm tra quyền truy cập: chưa đăng nhập hoặc thiếu quyền trả 403."""
    def boc(ham):
        @functools.wraps(ham)
        def ben_trong(*args, **kwargs):
            if not co_quyen(quyen):
                abort(403)
            return ham(*args, **kwargs)
        return ben_trong
    return boc
