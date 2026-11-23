"""Cấu hình menu sidebar và breadcrumb. Dữ liệu thuần, không truy cập CSDL.

Mỗi mục menu:
  nhan        chữ hiển thị
  icon        tên Bootstrap Icons (không kèm tiền tố "bi-")
  endpoint    tên route Flask; link được sinh bằng url_for nên đổi URL không phải sửa ở đây
  quyen       quyền cần có (xem app/auth.py); bỏ trống nghĩa là mọi người dùng đã đăng nhập
  cung_nhom   các endpoint khác cũng làm mục này sáng (ví dụ trang chi tiết thuộc mục danh sách)
  tham_so     tham số query của link, ví dụ {"muc": "nhap"}
  phan_biet   tên tham số query dùng để phân biệt các mục cùng endpoint (ví dụ "muc" của trang kho)
  anchor      đoạn #neo; server không đọc được neo nên phần sáng theo neo do JavaScript xử lý
  sap_co      True nếu chức năng chưa có: hiển thị mờ, không có link
"""

NHOM_MENU = [
    {"tieu_de": "Dashboard", "muc": [
        {"nhan": "Tổng quan", "icon": "speedometer2", "endpoint": "trang_chu", "quyen": "xem_tong_quan"},
    ]},
    {"tieu_de": "Kinh doanh", "muc": [
        {"nhan": "Quản lý đơn hàng", "icon": "receipt", "endpoint": "danh_sach_don",
         "quyen": "xem_don", "cung_nhom": ("chi_tiet_don",)},
        {"nhan": "Tạo đơn hàng", "icon": "plus-circle", "endpoint": "don_hang_moi", "quyen": "tao_don"},
        {"nhan": "Khách hàng", "icon": "people", "endpoint": "ds_khach_hang",
         "quyen": "xem_khach", "cung_nhom": ("khach_moi", "khach_sua")},
        {"nhan": "Sản phẩm", "icon": "box-seam", "endpoint": "ds_san_pham",
         "quyen": "xem_san_pham", "cung_nhom": ("san_pham_moi", "san_pham_sua")},
    ]},
    {"tieu_de": "Quản lý kho", "muc": [
        {"nhan": "Tổng quan kho", "icon": "boxes", "endpoint": "kho", "quyen": "xem_kho", "phan_biet": "muc"},
        {"nhan": "Nhập kho", "icon": "box-arrow-in-down", "endpoint": "kho", "quyen": "kho_ghi",
         "tham_so": {"muc": "nhap"}, "phan_biet": "muc"},
        {"nhan": "Xuất kho", "icon": "box-arrow-up", "endpoint": "kho", "quyen": "kho_ghi",
         "tham_so": {"muc": "xuat"}, "phan_biet": "muc"},
        {"nhan": "Cảnh báo tồn kho", "icon": "exclamation-triangle", "endpoint": "kho", "quyen": "xem_kho",
         "tham_so": {"muc": "canh-bao"}, "phan_biet": "muc"},
    ]},
    {"tieu_de": "Phân tích", "muc": [
        {"nhan": "Báo cáo thống kê", "icon": "bar-chart-line", "endpoint": "bao_cao", "quyen": "bao_cao"},
        {"nhan": "Doanh thu", "icon": "graph-up", "endpoint": "bao_cao", "quyen": "bao_cao",
         "anchor": "doanh-thu", "chi_theo_neo": True},
        {"nhan": "Sản phẩm bán chạy", "icon": "trophy", "endpoint": "bao_cao", "quyen": "bao_cao",
         "anchor": "san-pham", "chi_theo_neo": True},
    ]},
    {"tieu_de": "Database", "muc": [
        {"nhan": "MongoDB Explorer", "icon": "database", "sap_co": True},
    ]},
    {"tieu_de": "Hệ thống", "muc": [
        {"nhan": "Cài đặt", "icon": "gear", "sap_co": True},
    ]},
]


def _dang_active(muc, endpoint, args):
    """Mục có đang là trang hiện tại không, chỉ dựa vào endpoint Flask và tham số query."""
    if muc.get("sap_co") or muc.get("chi_theo_neo"):
        return False
    if endpoint != muc["endpoint"] and endpoint not in muc.get("cung_nhom", ()):
        return False
    khoa = muc.get("phan_biet")
    if khoa:
        mong_doi = muc.get("tham_so", {}).get(khoa)
        return (args.get(khoa) or None) == mong_doi
    return True


def xay_menu(co_quyen, tao_url, endpoint, args):
    """Trả về các nhóm menu mà người dùng được xem, kèm href và trạng thái active.

    co_quyen(ten) -> bool; tao_url(endpoint, **kwargs) -> str (thường là flask.url_for).
    Nhóm không còn mục nào sau khi lọc quyền sẽ bị bỏ để không hiện tiêu đề trống.
    """
    ket_qua = []
    for nhom in NHOM_MENU:
        hien = []
        for muc in nhom["muc"]:
            quyen = muc.get("quyen")
            if quyen and not co_quyen(quyen):
                continue
            moi = {"nhan": muc["nhan"], "icon": muc["icon"], "sap_co": bool(muc.get("sap_co")),
                   "active": _dang_active(muc, endpoint, args), "neo": muc.get("anchor"), "href": None}
            if not moi["sap_co"]:
                kwargs = dict(muc.get("tham_so", {}))
                if muc.get("anchor"):
                    kwargs["_anchor"] = muc["anchor"]
                moi["href"] = tao_url(muc["endpoint"], **kwargs)
            hien.append(moi)
        if hien:
            ket_qua.append({"tieu_de": nhom["tieu_de"], "muc": hien})
    return ket_qua


# Tên hiển thị của mục con trong trang kho, theo tham số ?muc=
_MUC_KHO = {"nhap": "Nhập kho", "xuat": "Xuất kho", "canh-bao": "Cảnh báo tồn kho"}


def xay_breadcrumb(endpoint, view_args, args):
    """Danh sách (nhãn, endpoint hoặc None) từ trang chủ tới trang hiện tại; phần tử cuối là trang hiện tại."""
    va = view_args or {}
    if endpoint == "trang_chu":
        return [("Dashboard", None), ("Tổng quan", None)]
    if endpoint == "dang_nhap":
        return [("Đăng nhập", None)]
    if endpoint == "danh_sach_don":
        return [("Kinh doanh", None), ("Quản lý đơn hàng", None)]
    if endpoint == "chi_tiet_don":
        return [("Kinh doanh", None), ("Quản lý đơn hàng", "danh_sach_don"), (f"Đơn {va.get('ma_don', '')}", None)]
    if endpoint == "don_hang_moi":
        return [("Kinh doanh", None), ("Tạo đơn hàng", None)]
    if endpoint == "ds_khach_hang":
        return [("Kinh doanh", None), ("Khách hàng", None)]
    if endpoint == "khach_moi":
        return [("Kinh doanh", None), ("Khách hàng", "ds_khach_hang"), ("Thêm mới", None)]
    if endpoint == "khach_sua":
        return [("Kinh doanh", None), ("Khách hàng", "ds_khach_hang"), (f"Sửa {va.get('ma_kh', '')}", None)]
    if endpoint == "ds_san_pham":
        return [("Kinh doanh", None), ("Sản phẩm", None)]
    if endpoint == "san_pham_moi":
        return [("Kinh doanh", None), ("Sản phẩm", "ds_san_pham"), ("Thêm mới", None)]
    if endpoint == "san_pham_sua":
        return [("Kinh doanh", None), ("Sản phẩm", "ds_san_pham"), (f"Sửa {va.get('ma_sp', '')}", None)]
    if endpoint == "kho":
        con = _MUC_KHO.get(args.get("muc") or "")
        if con:
            return [("Quản lý kho", None), ("Tổng quan kho", "kho"), (con, None)]
        return [("Quản lý kho", None), ("Tổng quan kho", None)]
    if endpoint == "bao_cao":
        return [("Phân tích", None), ("Báo cáo thống kê", None)]
    return [("Hệ thống", None)]
