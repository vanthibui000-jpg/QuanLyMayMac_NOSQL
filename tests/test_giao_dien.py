"""Kiểm thử layout dùng chung: sidebar, mục active, breadcrumb, topbar, design system.

Phần đầu kiểm thử module app/nav.py thuần (không cần CSDL). Phần sau kiểm thử HTML thật qua test client.
"""
import re
from pathlib import Path

from app import nav, services
from app.auth import PHAN_QUYEN
from app.web import create_app

GOC = Path(__file__).resolve().parent.parent
THU_MUC_TEMPLATE = GOC / "app" / "templates"


# ---------- Tiện ích ----------

def _tao_url(endpoint, **kwargs):
    neo = kwargs.pop("_anchor", None)
    chuoi = "&".join(f"{k}={v}" for k, v in kwargs.items())
    return f"/{endpoint}" + (f"?{chuoi}" if chuoi else "") + (f"#{neo}" if neo else "")


def _menu(endpoint, args=None, co_quyen=lambda q: True):
    return nav.xay_menu(co_quyen, _tao_url, endpoint, args or {})


def _muc_active(menu):
    return [m["nhan"] for nhom in menu for m in nhom["muc"] if m["active"]]


def _link_menu(html):
    """Các link trong sidebar dưới dạng [(href, active)]."""
    return [(href, bool(act)) for act, href in re.findall(r'<a class="nav-link( active)?" href="([^"]*)"', html)]


def _active_href(html):
    return [href for href, act in _link_menu(html) if act]


# ---------- app/nav.py: xác định mục active theo route ----------

def test_tung_route_chi_sang_dung_mot_muc():
    mong_doi = {
        "trang_chu": "Tổng quan",
        "danh_sach_don": "Quản lý đơn hàng",
        "chi_tiet_don": "Quản lý đơn hàng",
        "don_hang_moi": "Tạo đơn hàng",
        "ds_khach_hang": "Khách hàng",
        "khach_moi": "Khách hàng",
        "khach_sua": "Khách hàng",
        "ds_san_pham": "Sản phẩm",
        "san_pham_moi": "Sản phẩm",
        "san_pham_sua": "Sản phẩm",
        "bao_cao": "Báo cáo thống kê",
    }
    for endpoint, nhan in mong_doi.items():
        assert _muc_active(_menu(endpoint)) == [nhan], endpoint


def test_trang_kho_phan_biet_muc_theo_tham_so():
    assert _muc_active(_menu("kho")) == ["Tổng quan kho"]
    assert _muc_active(_menu("kho", {"muc": "nhap"})) == ["Nhập kho"]
    assert _muc_active(_menu("kho", {"muc": "xuat"})) == ["Xuất kho"]
    assert _muc_active(_menu("kho", {"muc": "canh-bao"})) == ["Cảnh báo tồn kho"]
    # tham số lạ hoặc rỗng không làm sáng nhầm mục nào ngoài Tổng quan kho
    assert _muc_active(_menu("kho", {"muc": ""})) == ["Tổng quan kho"]
    assert _muc_active(_menu("kho", {"loai": "NHAP"})) == ["Tổng quan kho"]


def test_muc_theo_neo_khong_tu_sang_o_phia_server():
    menu = _menu("bao_cao")
    neo = {m["nhan"]: m for nhom in menu for m in nhom["muc"] if m["neo"]}
    assert set(neo) == {"Doanh thu", "Sản phẩm bán chạy"}
    assert not any(m["active"] for m in neo.values())  # JavaScript sẽ bật theo #neo
    assert neo["Doanh thu"]["href"].endswith("#doanh-thu")
    assert neo["Sản phẩm bán chạy"]["href"].endswith("#san-pham")


def test_trang_khac_khong_sang_muc_nao_khi_endpoint_la_none():
    assert _muc_active(_menu(None)) == []  # ví dụ trang 404


def test_muc_sap_co_khong_co_link_va_khong_bao_gio_active():
    sap_co = [m for nhom in _menu("trang_chu") for m in nhom["muc"] if m["sap_co"]]
    assert {m["nhan"] for m in sap_co} == {"MongoDB Explorer", "Cài đặt"}
    assert all(m["href"] is None and not m["active"] for m in sap_co)


def test_menu_loc_theo_quyen_va_bo_nhom_trong():
    chi_tong_quan = _menu("trang_chu", co_quyen=lambda q: q == "xem_tong_quan")
    tieu_de = [n["tieu_de"] for n in chi_tong_quan]
    assert "Kinh doanh" not in tieu_de and "Quản lý kho" not in tieu_de and "Phân tích" not in tieu_de
    assert "Dashboard" in tieu_de  # mục không cần quyền cụ thể vẫn hiện

    khong_quyen = _menu("trang_chu", co_quyen=lambda q: False)
    assert [n["tieu_de"] for n in khong_quyen] == ["Database", "Hệ thống"]


def test_moi_quyen_trong_menu_deu_ton_tai_trong_bang_phan_quyen():
    for nhom in nav.NHOM_MENU:
        for muc in nhom["muc"]:
            if muc.get("quyen"):
                assert muc["quyen"] in PHAN_QUYEN, muc["nhan"]


def test_moi_endpoint_trong_menu_la_route_that(db):
    app = create_app(db)
    cac_route = {r.endpoint for r in app.url_map.iter_rules()}
    for nhom in nav.NHOM_MENU:
        for muc in nhom["muc"]:
            if not muc.get("sap_co"):
                assert muc["endpoint"] in cac_route, muc["nhan"]
            for ep in muc.get("cung_nhom", ()):
                assert ep in cac_route, ep


def test_breadcrumb_trang_chi_tiet_va_trang_con():
    ct = nav.xay_breadcrumb("chi_tiet_don", {"ma_don": "DH000042"}, {})
    assert [n for n, _ in ct] == ["Kinh doanh", "Quản lý đơn hàng", "Đơn DH000042"]
    assert ct[1][1] == "danh_sach_don" and ct[-1][1] is None

    sua = nav.xay_breadcrumb("san_pham_sua", {"ma_sp": "SP0007"}, {})
    assert [n for n, _ in sua] == ["Kinh doanh", "Sản phẩm", "Sửa SP0007"]

    kho = nav.xay_breadcrumb("kho", {}, {"muc": "xuat"})
    assert [n for n, _ in kho] == ["Quản lý kho", "Tổng quan kho", "Xuất kho"]
    assert [n for n, _ in nav.xay_breadcrumb("kho", {}, {})] == ["Quản lý kho", "Tổng quan kho"]


# ---------- HTML thật: sidebar, topbar ----------

def test_sidebar_hien_dung_menu_theo_vai_tro(tao_client):
    kd = _link_menu(tao_client("kd1").get("/").get_data(as_text=True))
    href_kd = [h for h, _ in kd]
    for can_co in ["/", "/don-hang", "/don-hang/moi", "/khach-hang", "/san-pham", "/bao-cao"]:
        assert can_co in href_kd, can_co
    assert not any(h.startswith("/kho") for h in href_kd)

    kho = [h for h, _ in _link_menu(tao_client("kho1").get("/").get_data(as_text=True))]
    for can_co in ["/kho", "/kho?muc=nhap", "/kho?muc=xuat", "/kho?muc=canh-bao", "/san-pham", "/bao-cao"]:
        assert can_co in kho, can_co
    assert "/don-hang" not in kho and "/don-hang/moi" not in kho

    kt = [h for h, _ in _link_menu(tao_client("kt1").get("/").get_data(as_text=True))]
    assert "/kho" in kt and "/kho?muc=canh-bao" in kt  # kế toán xem được kho
    assert "/kho?muc=nhap" not in kt and "/kho?muc=xuat" not in kt  # nhưng không lập phiếu


def test_html_chi_mot_muc_active_va_dung_muc(tao_client):
    kd = tao_client("kd1")
    assert _active_href(kd.get("/don-hang").get_data(as_text=True)) == ["/don-hang"]
    assert _active_href(kd.get("/don-hang/moi").get_data(as_text=True)) == ["/don-hang/moi"]
    assert _active_href(kd.get("/san-pham/moi").get_data(as_text=True)) == ["/san-pham"]
    assert _active_href(kd.get("/khach-hang/KH0001/sua").get_data(as_text=True)) == ["/khach-hang"]
    assert _active_href(kd.get("/bao-cao").get_data(as_text=True)) == ["/bao-cao"]

    kho = tao_client("kho1")
    assert _active_href(kho.get("/kho").get_data(as_text=True)) == ["/kho"]
    assert _active_href(kho.get("/kho?muc=nhap").get_data(as_text=True)) == ["/kho?muc=nhap"]
    assert _active_href(kho.get("/kho?muc=canh-bao").get_data(as_text=True)) == ["/kho?muc=canh-bao"]


def test_trang_chi_tiet_don_sang_muc_quan_ly_don_hang(tao_client, db):
    services.dat_hang(db, "DH0001", "KH0001", [{"ma_sp": "SP0001", "so_luong": 1, "mau": None, "size": None}])
    html = tao_client("kd1").get("/don-hang/DH0001").get_data(as_text=True)
    assert _active_href(html) == ["/don-hang"]
    assert 'aria-current="page"' in html


def test_muc_sap_co_hien_nhan_va_khong_la_link(tao_client):
    html = tao_client("kd1").get("/").get_data(as_text=True)
    assert "MongoDB Explorer" in html and "Cài đặt" in html
    assert html.count("Sắp có") >= 2
    assert not any("mongodb" in h.lower() for h, _ in _link_menu(html))


def test_cau_truc_layout_co_du_thanh_phan(tao_client):
    html = tao_client("kd1").get("/").get_data(as_text=True)
    for dau_hieu in [
        'class="sidebar"', "ORDER MANAGEMENT SYSTEM", "Phiên bản 1.0.0",
        'id="nut-thu-gon"',                       # nút thu gọn (desktop)
        'for="mo-menu" class="icon-btn topbar-menu"',  # hamburger (mobile)
        'class="sidebar-overlay"',                # lớp phủ khi mở trên mobile
        'class="breadcrumb"', 'class="page-title"',
        'class="topbar-search"', "Thông báo", "Menu tài khoản", "Đăng xuất",
        'id="hop-xac-nhan"', 'id="toast-zone"',
        "/static/style.css",
    ]:
        assert dau_hieu in html, dau_hieu


def test_o_tim_kiem_gui_toi_trang_danh_sach_theo_quyen(tao_client):
    kd = tao_client("kd1").get("/").get_data(as_text=True)
    assert 'action="/don-hang" role="search"' in kd
    kho = tao_client("kho1").get("/").get_data(as_text=True)
    assert 'action="/san-pham" role="search"' in kho  # kho không xem đơn nên tìm sản phẩm


def test_chuong_thong_bao_dung_du_lieu_va_quyen(tao_client, db):
    # fixture có NVL0001 (100) và NVL0002 (5), cả hai dưới ngưỡng 500
    kho = tao_client("kho1").get("/").get_data(as_text=True)
    assert "2 nguyên vật liệu sắp hết" in kho
    assert 'href="/kho?muc=canh-bao"' in kho
    assert "đơn chờ thanh toán" not in kho  # kho không có quyền xem đơn

    services.dat_hang(db, "DH0001", "KH0001", [{"ma_sp": "SP0001", "so_luong": 1, "mau": None, "size": None}])
    kd = tao_client("kd1").get("/").get_data(as_text=True)
    assert "1 đơn chờ thanh toán" in kd
    assert "nguyên vật liệu sắp hết" not in kd

    db.nguyenvatlieu.update_many({}, {"$set": {"so_luong_ton": 9999}})
    assert "Không có thông báo mới" in tao_client("kho1").get("/").get_data(as_text=True)


def test_menu_tai_khoan_hien_ten_va_vai_tro(tao_client):
    html = tao_client("kt1").get("/").get_data(as_text=True)
    assert "kt1" in html and "Kế toán" in html


def test_trang_dang_nhap_khong_co_sidebar_va_topbar_menu(tao_client):
    html = tao_client().get("/dang-nhap").get_data(as_text=True)
    assert 'class="sidebar"' not in html
    assert "topbar-menu" not in html and "topbar-search" not in html
    assert "Đăng nhập hệ thống" in html


# ---------- Toast và modal ----------

def test_thong_bao_flash_hien_thanh_toast(tao_client):
    client = tao_client("kd1")
    loi = client.post("/san-pham/moi", data={"ten_sp": "", "don_gia": "1", "mau": "", "size": "", "barcode": ""})
    assert 'class="toast loi"' in loi.get_data(as_text=True)

    ok = client.post("/khach-hang/moi", data={"ten_kh": "Shop B", "sdt": "0912345678"}, follow_redirects=True)
    html = ok.get_data(as_text=True)
    assert 'class="toast ok"' in html and "Đã thêm khách hàng" in html


def test_thao_tac_nguy_hiem_van_gan_data_confirm_cho_modal(tao_client, db):
    services.dat_hang(db, "DH0001", "KH0001", [{"ma_sp": "SP0001", "so_luong": 1, "mau": None, "size": None}])
    html = tao_client("kd1").get("/don-hang/DH0001").get_data(as_text=True)
    assert 'data-confirm="Hủy đơn DH0001?' in html
    assert 'data-confirm="Ngừng bán' in tao_client("kd1").get("/san-pham").get_data(as_text=True)


# ---------- Trang kho theo mục con ----------

def test_kho_canh_bao_chi_liet_ke_nguyen_vat_lieu_duoi_nguong(tao_client, db):
    db.nguyenvatlieu.update_one({"_id": "NVL0001"}, {"$set": {"so_luong_ton": 900}})
    html = tao_client("kho1").get("/kho?muc=canh-bao").get_data(as_text=True)
    bang = html.split("Cảnh báo tồn kho</h2>", 1)[1].split("</table>", 1)[0]
    assert "NVL0002" in bang and "NVL0001" not in bang

    tat_ca = tao_client("kho1").get("/kho").get_data(as_text=True)
    bang_tat_ca = tat_ca.split("Tồn kho</h2>", 1)[1].split("</table>", 1)[0]
    assert "NVL0001" in bang_tat_ca and "NVL0002" in bang_tat_ca


def test_kho_muc_xuat_chon_san_tab_xuat_con_mac_dinh_la_nhap(tao_client):
    client = tao_client("kho1")
    xuat = client.get("/kho?muc=xuat").get_data(as_text=True)
    assert re.search(r'id="loai-xuat" value="XUAT"\s+checked', xuat)
    assert not re.search(r'id="loai-nhap" value="NHAP"\s+checked', xuat)

    nhap = client.get("/kho?muc=nhap").get_data(as_text=True)
    assert re.search(r'id="loai-nhap" value="NHAP"\s+checked', nhap)
    assert re.search(r'id="loai-nhap" value="NHAP"\s+checked', client.get("/kho").get_data(as_text=True))


def test_bao_cao_co_neo_cho_menu_doanh_thu_va_san_pham(tao_client):
    html = tao_client("kd1").get("/bao-cao").get_data(as_text=True)
    assert 'id="doanh-thu"' in html and 'id="san-pham"' in html
    assert 'href="/bao-cao#doanh-thu"' in html and 'href="/bao-cao#san-pham"' in html


# ---------- Design system và template ----------

def test_moi_template_trang_deu_ke_thua_base():
    for tep in THU_MUC_TEMPLATE.glob("*.html"):
        if tep.name in ("base.html", "_macros.html"):
            continue
        assert '{% extends "base.html" %}' in tep.read_text(encoding="utf-8"), tep.name


def test_css_co_du_bang_mau_design_system(tao_client):
    css = tao_client("kd1").get("/static/style.css").get_data(as_text=True)
    for token in [
        "--primary: #2563EB", "--primary-hover: #1D4ED8", "--sidebar-bg: #172554",
        "--background: #F5F7FB", "--surface: #FFFFFF", "--border: #E2E8F0",
        "--text-primary: #1E293B", "--text-secondary: #64748B",
        "--success: #16A34A", "--warning: #F59E0B", "--danger: #DC2626", "--info: #0EA5E9",
        "--radius: 12px",
    ]:
        assert token in css, token
    assert "Inter" in css


def test_css_va_js_duoc_phuc_vu(tao_client):
    client = tao_client()
    for url in ["/static/style.css", "/static/js/app.js", "/static/js/don_hang_moi.js"]:
        assert client.get(url).status_code == 200, url


def test_luoi_khong_bi_bang_ben_trong_keo_tran_ngang(tao_client):
    """Lỗi từng gặp: cột 1fr không co nhỏ hơn bảng bên trong nên trang Báo cáo tràn ngang trên điện thoại."""
    css = tao_client().get("/static/style.css").get_data(as_text=True)
    for quy_tac in [
        ".cot-2 { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)",
        ".cot-3 { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr)",
        "min-width: 0; /* cho phép thẻ co lại",
    ]:
        assert quy_tac in css, quy_tac
    # trong khối responsive, lưới một cột cũng phải là minmax(0, 1fr) chứ không phải 1fr trần
    assert ".cot-2 { grid-template-columns: minmax(0, 1fr); }" in css
    assert ".cot-2 { grid-template-columns: 1fr; }" not in css


def test_muc_canh_bao_an_form_lap_phieu_con_cac_muc_khac_van_hien(tao_client):
    client = tao_client("kho1")
    assert "Lập phiếu</button>" not in client.get("/kho?muc=canh-bao").get_data(as_text=True)
    for url in ["/kho", "/kho?muc=nhap", "/kho?muc=xuat"]:
        assert "Lập phiếu</button>" in client.get(url).get_data(as_text=True), url
