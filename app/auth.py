"""Đăng nhập và phân quyền theo vai trò (collection nguoidung, trường vai_tro).

Nguyên tắc:
- Mặc định mọi route đều yêu cầu đăng nhập (kiểm tra ở before_request trong web.py).
- Mỗi route cụ thể gắn thêm @cho_phep("<quyền>") để giới hạn theo vai trò.
- Vai trò KH (khách hàng) không dùng giao diện nội bộ này.
"""
import functools
import hashlib
import hmac

from flask import abort, session
from werkzeug.security import check_password_hash

VAI_TRO_NHAN = {
    "KD": "Kinh doanh",
    "KHO": "Kho",
    "KT": "Kế toán",
    "NV": "Nhân viên",
}

# Quyền -> tập vai trò được phép. Thêm quyền mới ở đây, không rải rác trong route.
PHAN_QUYEN = {
    "xem_tong_quan": {"KD", "KHO", "KT", "NV"},
    "xem_don": {"KD", "KT", "NV"},
    "tao_don": {"KD"},
    "huy_don": {"KD"},
    "thanh_toan": {"KD", "KT"},
    "xem_san_pham": {"KD", "KHO", "KT", "NV"},
    "ql_san_pham": {"KD"},
    "xem_khach": {"KD", "KT", "NV"},
    "ql_khach": {"KD"},
    "xem_kho": {"KHO", "KT"},
    "kho_ghi": {"KHO"},
    "bao_cao": {"KD", "KHO", "KT"},
}


def kiem_tra_mat_khau(da_luu, nhap):
    """So khớp mật khẩu nhập vào với giá trị đã lưu.

    Hỗ trợ hai định dạng:
    - hash của Werkzeug (scrypt/pbkdf2), dùng cho tài khoản tạo mới;
    - SHA-256 hex không muối, là định dạng của dữ liệu mẫu cũ (chỉ phù hợp demo).
    """
    if not da_luu or not nhap:
        return False
    if da_luu.startswith(("scrypt:", "pbkdf2:")):
        return check_password_hash(da_luu, nhap)
    sha = hashlib.sha256(nhap.encode("utf-8")).hexdigest()
    return hmac.compare_digest(da_luu, sha)


def vai_tro_hien_tai():
    return session.get("vai_tro")


def co_quyen(quyen):
    return vai_tro_hien_tai() in PHAN_QUYEN.get(quyen, set())


def nguoi_dung_hien_tai():
    """Thông tin người đang đăng nhập cho template, hoặc None nếu chưa đăng nhập."""
    if "ma_nd" not in session:
        return None
    vai_tro = session.get("vai_tro")
    return {
        "ma_nd": session["ma_nd"],
        "ten": session.get("ten", ""),
        "vai_tro": vai_tro,
        "vai_tro_nhan": VAI_TRO_NHAN.get(vai_tro, vai_tro),
    }


def cho_phep(quyen):
    """Decorator: từ chối (403) nếu vai trò hiện tại không có quyền này."""
    def boc(ham):
        @functools.wraps(ham)
        def ben_trong(*args, **kwargs):
            if not co_quyen(quyen):
                abort(403)
            return ham(*args, **kwargs)
        return ben_trong
    return boc
