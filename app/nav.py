"""Cấu hình menu sidebar và breadcrumb cho cổng quản trị /admin (ADMIN & NV)."""

NHOM_MENU = [
    {"tieu_de": "Tổng quan", "muc": [
        {"nhan": "Dashboard", "icon": "speedometer2", "endpoint": "admin_dashboard", "quyen": "xem_admin"},
    ]},
    {"tieu_de": "Bán hàng", "muc": [
        {"nhan": "Quản lý đơn hàng", "icon": "receipt", "endpoint": "admin_don_hang",
         "quyen": "xem_don", "cung_nhom": ("admin_chi_tiet_don",)},
        {"nhan": "Sản phẩm", "icon": "bag", "endpoint": "admin_san_pham",
         "quyen": "xem_san_pham_admin", "cung_nhom": ("admin_san_pham_moi", "admin_san_pham_sua")},
        {"nhan": "Khách hàng", "icon": "people", "endpoint": "admin_khach_hang",
         "quyen": "xem_khach", "cung_nhom": ("admin_khach_moi", "admin_khach_sua")},
    ]},
    {"tieu_de": "Kho thành phẩm", "muc": [
        {"nhan": "Tổng quan kho", "icon": "boxes", "endpoint": "admin_kho", "quyen": "xem_kho", "phan_biet": "muc"},
        {"nhan": "Nhập kho", "icon": "box-arrow-in-down", "endpoint": "admin_kho", "quyen": "kho_ghi",
         "tham_so": {"muc": "nhap"}, "phan_biet": "muc"},
        {"nhan": "Xuất kho", "icon": "box-arrow-up", "endpoint": "admin_kho", "quyen": "kho_ghi",
         "tham_so": {"muc": "xuat"}, "phan_biet": "muc"},
        {"nhan": "Sắp hết hàng", "icon": "exclamation-triangle", "endpoint": "admin_kho", "quyen": "xem_kho",
         "tham_so": {"muc": "canh-bao"}, "phan_biet": "muc"},
    ]},
    {"tieu_de": "Phân tích & Hệ thống", "muc": [
        {"nhan": "Báo cáo thống kê", "icon": "bar-chart-line", "endpoint": "admin_bao_cao", "quyen": "bao_cao"},
        {"nhan": "Quản lý tài khoản", "icon": "person-gear", "endpoint": "admin_tai_khoan",
         "quyen": "ql_tai_khoan", "cung_nhom": ("admin_tai_khoan_moi", "admin_tai_khoan_sua")},
        {"nhan": "MongoDB Explorer", "icon": "database", "endpoint": "admin_mongodb", "quyen": "xem_mongodb"},
        {"nhan": "Hồ sơ cá nhân", "icon": "person-circle", "endpoint": "admin_ho_so", "quyen": "xem_admin"},
    ]},
]


def _dang_active(muc, endpoint, args):
    if endpoint != muc["endpoint"] and endpoint not in muc.get("cung_nhom", ()):
        return False
    khoa = muc.get("phan_biet")
    if khoa:
        mong_doi = muc.get("tham_so", {}).get(khoa)
        return (args.get(khoa) or None) == mong_doi
    return True


def xay_menu(co_quyen, tao_url, endpoint, args):
    ket_qua = []
    for nhom in NHOM_MENU:
        hien = []
        for muc in nhom["muc"]:
            quyen = muc.get("quyen")
            if quyen and not co_quyen(quyen):
                continue
            kwargs = dict(muc.get("tham_so", {}))
            hien.append({
                "nhan": muc["nhan"],
                "icon": muc["icon"],
                "active": _dang_active(muc, endpoint, args),
                "href": tao_url(muc["endpoint"], **kwargs),
            })
        if hien:
            ket_qua.append({"tieu_de": nhom["tieu_de"], "muc": hien})
    return ket_qua


_MUC_KHO = {"nhap": "Nhập kho", "xuat": "Xuất kho", "canh-bao": "Sắp hết hàng"}


def xay_breadcrumb(endpoint, view_args, args):
    va = view_args or {}
    if endpoint == "admin_dashboard":
        return [("Admin", None), ("Dashboard", None)]
    if endpoint == "admin_don_hang":
        return [("Bán hàng", None), ("Quản lý đơn hàng", None)]
    if endpoint == "admin_chi_tiet_don":
        return [("Bán hàng", None), ("Quản lý đơn hàng", "admin_don_hang"), (f"Đơn {va.get('ma_don', '')}", None)]
    if endpoint == "admin_san_pham":
        return [("Bán hàng", None), ("Sản phẩm", None)]
    if endpoint == "admin_san_pham_moi":
        return [("Bán hàng", None), ("Sản phẩm", "admin_san_pham"), ("Thêm mới", None)]
    if endpoint == "admin_san_pham_sua":
        return [("Bán hàng", None), ("Sản phẩm", "admin_san_pham"), (f"Sửa {va.get('ma_sp', '')}", None)]
    if endpoint == "admin_khach_hang":
        return [("Bán hàng", None), ("Khách hàng", None)]
    if endpoint == "admin_khach_moi":
        return [("Bán hàng", None), ("Khách hàng", "admin_khach_hang"), ("Thêm mới", None)]
    if endpoint == "admin_khach_sua":
        return [("Bán hàng", None), ("Khách hàng", "admin_khach_hang"), (f"Sửa {va.get('ma_kh', '')}", None)]
    if endpoint == "admin_kho":
        con = _MUC_KHO.get(args.get("muc") or "")
        if con:
            return [("Kho thành phẩm", None), ("Tổng quan kho", "admin_kho"), (con, None)]
        return [("Kho thành phẩm", None), ("Tổng quan kho", None)]
    if endpoint == "admin_bao_cao":
        return [("Phân tích & Hệ thống", None), ("Báo cáo thống kê", None)]
    if endpoint == "admin_tai_khoan":
        return [("Phân tích & Hệ thống", None), ("Quản lý tài khoản", None)]
    if endpoint == "admin_tai_khoan_moi":
        return [("Phân tích & Hệ thống", None), ("Quản lý tài khoản", "admin_tai_khoan"), ("Thêm tài khoản", None)]
    if endpoint == "admin_tai_khoan_sua":
        return [("Phân tích & Hệ thống", None), ("Quản lý tài khoản", "admin_tai_khoan"), (f"Sửa {va.get('ma_nd', '')}", None)]
    if endpoint == "admin_mongodb":
        return [("Phân tích & Hệ thống", None), ("MongoDB Explorer", None)]
    if endpoint == "admin_ho_so":
        return [("Tài khoản", None), ("Hồ sơ cá nhân", None)]
    return [("Quản trị", None)]
