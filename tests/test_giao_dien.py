"""Kiểm thử giao diện: Trang chủ thuần quảng cáo Aristino, Tab Sản phẩm riêng, Layout Admin & Nav."""
from app import nav
from app.auth import PHAN_QUYEN
from app.web import create_app


def _tao_url(endpoint, **kwargs):
    chuoi = "&".join(f"{k}={v}" for k, v in kwargs.items())
    return f"/{endpoint}" + (f"?{chuoi}" if chuoi else "")


def test_trang_chu_la_quang_cao_khong_nhet_luoi_san_pham(tao_client):
    html = tao_client().get("/").get_data(as_text=True)
    # Các khối chiến dịch Aristino phải có mặt
    for khoi in ["hero-slider", "Tiếp Nối Huyền Thoại", "lookbook-strip", "story-pillars", "policy-strip"]:
        assert khoi in html, khoi
    # Đã xóa tên ATELIER V, khối countdown, 3 từ VUN/ĐAN/RẠNG và địa chỉ showroom theo yêu cầu
    for cam in ["ATELIER V", "flash-countdown", 'class="promo-band"', "VUN", "ĐAN", "RẠNG", "Phố Huế", "Đồng Khởi", "Hà Nội", "TP.HCM"]:
        assert cam not in html, cam
    # Không nhét lưới sản phẩm bán lẻ (product-grid) và nút thêm giỏ trực tiếp vào trang chủ
    assert 'class="product-grid"' not in html
    assert 'action="/gio-hang/them"' not in html
    # Tab Sản phẩm phải dẫn sang /san-pham
    assert 'href="/san-pham"' in html


def test_tab_san_pham_co_bo_loc_trai_va_luoi_san_pham(tao_client):
    html = tao_client().get("/san-pham").get_data(as_text=True)
    assert 'class="filter-sidebar"' in html
    assert 'class="product-grid"' in html
    assert "Áo Sơ Mi Trắng Poplin" in html


def test_menu_admin_khop_phan_quyen_va_route_that(db):
    app = create_app(db)
    routes = {r.endpoint for r in app.url_map.iter_rules()}
    for nhom in nav.NHOM_MENU:
        for muc in nhom["muc"]:
            assert muc["quyen"] in PHAN_QUYEN, muc["nhan"]
            assert muc["endpoint"] in routes, muc["nhan"]


def test_sidebar_admin_khac_nhau_giua_admin_va_nv(tao_client):
    html_admin = tao_client("admin1").get("/admin").get_data(as_text=True)
    assert "/admin/bao-cao" in html_admin
    assert "/admin/tai-khoan" in html_admin
    assert "/admin/ho-so" in html_admin
    assert "/admin/mongodb" in html_admin
    assert "Sắp có" not in html_admin  # đã thay mục chết bằng MongoDB Explorer thật
    assert "Xem mặt tiền shop" not in html_admin

    html_nv = tao_client("nv1").get("/admin").get_data(as_text=True)
    assert "/admin/don-hang" in html_nv
    assert "/admin/kho" in html_nv
    assert "/admin/ho-so" in html_nv
    assert "/admin/bao-cao" not in html_nv
    assert "/admin/tai-khoan" not in html_nv
    assert "/admin/mongodb" not in html_nv
    assert "Doanh thu tháng" not in html_nv
    assert "Xem mặt tiền shop" not in html_nv


def test_giao_dien_ho_so_ca_nhan_ca_ba_vai_tro(tao_client):
    for user in ("admin1", "nv1"):
        r = tao_client(user).get("/admin/ho-so")
        assert r.status_code == 200, user
        html = r.get_data(as_text=True)
        assert "Hồ sơ cá nhân" in html and "Đổi mật khẩu" in html
        assert "Xem mặt tiền shop" not in html
        assert "ATELIER V" not in html

    c_kh = tao_client("khach1")
    tk_html = c_kh.get("/tai-khoan").get_data(as_text=True)
    assert "/tai-khoan/ho-so" in tk_html and "Sửa thông tin cá nhân" in tk_html

    r_hs = c_kh.get("/tai-khoan/ho-so")
    assert r_hs.status_code == 200
    hs_html = r_hs.get_data(as_text=True)
    assert "Thông tin cá nhân" in hs_html and "Đổi mật khẩu" in hs_html
    assert "ATELIER V" not in hs_html


def test_static_store_va_admin_assets_phuc_vu_200(tao_client):
    c = tao_client()
    for url in ["/static/store.css", "/static/js/store.js", "/static/style.css", "/static/js/app.js", "/static/img/hero_01_campaign.jpg"]:
        assert c.get(url).status_code == 200, url


def test_chi_tiet_sp_nap_du_lieu_bien_the_truoc_store_js(tao_client):
    html = tao_client().get("/san-pham/SP0001").get_data(as_text=True)
    idx_data = html.index('id="bien-the-data"')
    idx_js = html.index('/static/js/store.js')
    assert idx_data < idx_js


def test_phien_vai_tro_cu_tu_dong_duoc_don_sach(tao_client):
    c = tao_client()
    with c.session_transaction() as sess:
        sess["ma_nd"] = "ND-OLD"
        sess["ten"] = "nv001"
        sess["vai_tro"] = "KD"
    r = c.get("/dang-nhap")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Đăng nhập" in html
    assert 'data-demo-user="admin"' in html
    assert 'data-demo-user="nv001"' in html
    assert 'data-demo-user="kh0001"' in html


def test_tab_bo_suu_tap_va_thuong_hieu_doc_lap_khong_copy_thuong_hieu_khac(tao_client):
    c = tao_client()
    home = c.get("/").get_data(as_text=True)
    assert 'href="/bo-suu-tap"' in home and 'href="/thuong-hieu"' in home
    assert "/#bo-suu-tap" not in home and "/#thuong-hieu" not in home

    for url, dau_hieu in [
        ("/bo-suu-tap", "Bộ Sưu Tập Mùa Mới"),
        ("/thuong-hieu", "Chuẩn Mực Trong Từng Đường Kim"),
    ]:
        r = c.get(url)
        assert r.status_code == 200, url
        html = r.get_data(as_text=True)
        assert dau_hieu in html
        for cam in ["Aristino", "ARISTINO", "Zara", "Uniqlo", "ATELIER V", "VUN", "ĐAN", "RẠNG", "Phố Huế", "Đồng Khởi", "Hà Nội", "TP.HCM"]:
            assert cam not in html, (url, cam)
    th_html = c.get("/thuong-hieu").get_data(as_text=True)
    assert "Xem Bộ Sưu Tập" not in th_html
    assert "Sang Tab Sản Phẩm" not in th_html



