"""Ứng dụng web Flask: Cửa hàng thời trang ATELIER V (chuẩn bố cục Aristino) + Cổng quản trị /admin.

Phân quyền 3 vai trò:
- Khách vãng lai / KH (Khách hàng): xem Trang chủ quảng cáo (/), Tab Sản phẩm (/san-pham),
  Chi tiết sản phẩm, Giỏ hàng (/gio-hang), Thanh toán (/thanh-toan) và Tài khoản (/tai-khoan).
- NV (Nhân viên): quản lý đơn hàng, cập nhật trạng thái/thanh toán, nhập/xuất kho thành phẩm, xem SP & khách trong /admin.
- ADMIN (Quản trị viên): toàn quyền trong /admin (sản phẩm, khách hàng, hủy đơn hoàn kho, báo cáo doanh thu, MongoDB Explorer).
"""
import csv
import io
import json
import math
import os
import re
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, abort, flash, jsonify, redirect, render_template, request, session, url_for

from app import queries, services
from app.auth import (
    VAI_TRO_NHAN,
    cho_phep,
    co_quyen,
    kiem_tra_mat_khau,
    la_khach_hang,
    la_noi_bo,
    ma_khach_hien_tai,
    nguoi_dung_hien_tai,
)
from app.db import get_db
from app.nav import xay_breadcrumb, xay_menu
from app.services import NghiepVuError, ma_tiep_theo

APP_VERSION = "2.0.0"
SO_DONG_KHO = 5
SO_DONG_MOI_TRANG = 12
SO_DONG_ADMIN = 20
NGUONG_TON = 10

TRANG_THAI_NHAN = {
    "CHO_XAC_NHAN": "Chờ xác nhận",
    "DANG_CHUAN_BI": "Đang chuẩn bị",
    "DANG_GIAO": "Đang giao hàng",
    "HOAN_THANH": "Hoàn thành",
    "DA_HUY": "Đã hủy",
}
TRANG_THAI_LOP_STORE = {
    "CHO_XAC_NHAN": "cho",
    "DANG_CHUAN_BI": "chuan-bi",
    "DANG_GIAO": "giao",
    "HOAN_THANH": "xong",
    "DA_HUY": "huy",
}
TRANG_THAI_LOP_ADMIN = {
    "CHO_XAC_NHAN": "cho",
    "DANG_CHUAN_BI": "mot-phan",
    "DANG_GIAO": "mot-phan",
    "HOAN_THANH": "da",
    "DA_HUY": "huy",
}
TT_NHAN = {
    "CHUA_THANH_TOAN": "Chưa thanh toán",
    "DA_THANH_TOAN": "Đã thanh toán",
}
MAU_HEX = {
    "Đen": "#111111",
    "Trắng": "#FFFFFF",
    "Xanh navy": "#1E3A5F",
    "Xám": "#6B7280",
    "Be": "#D6C6B2",
    "Nâu": "#78553A",
    "Xanh rêu": "#4B5E4A",
    "Đỏ đô": "#8B1E24",
    "Cam đất": "#B4654A",
}

THU_MUC_IMG = Path(__file__).resolve().parent / "static" / "img"


def _so_tien(gia_tri):
    return f"{int(gia_tri):,}".replace(",", ".") + " ₫"


def _ngay(gia_tri):
    return gia_tri.strftime("%d/%m/%Y %H:%M") if isinstance(gia_tri, datetime) else (gia_tri or "")


def _tach_danh_sach(chuoi):
    kq = []
    for p in (chuoi or "").split(","):
        gt = p.strip()
        if gt and gt not in kq:
            kq.append(gt)
    return kq


def _so_nguyen_duong(chuoi):
    try:
        so = int(str(chuoi).strip())
    except ValueError:
        return None
    return so if so > 0 else None


def _so_nguyen_khong_am(chuoi, mac_dinh=0):
    s = str(chuoi or "").strip()
    if not s:
        return mac_dinh
    try:
        so = int(s)
    except ValueError:
        return None
    return so if so >= 0 else None


def _tim_theo_ten(truong_ten, q):
    if not q:
        return {}
    mau = {"$regex": re.escape(q), "$options": "i"}
    return {"$or": [{truong_ten: mau}, {"_id": mau}]}


def _json_dep(doc):
    return json.dumps(doc, ensure_ascii=False, indent=2, default=str)


def _ds_anh_san_pham():
    if not THU_MUC_IMG.exists():
        return ["prod_shirt_white.jpg"]
    files = sorted(
        f.name for f in THU_MUC_IMG.iterdir()
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        and not f.name.startswith("hero_")
    )
    return files or ["prod_shirt_white.jpg"]


def _duong_dan_an_toan(duong_dan):
    return bool(duong_dan) and duong_dan.startswith("/") and not duong_dan.startswith("//") and "\\" not in duong_dan


def create_app(db=None):
    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "atelier-v-nosql-demo-key")
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_HTTPONLY"] = True

    app.jinja_env.filters["tien"] = _so_tien
    app.jinja_env.filters["ngay"] = _ngay
    app.jinja_env.filters["trang_thai"] = lambda ma: TRANG_THAI_NHAN.get(ma, ma)
    app.jinja_env.filters["trang_thai_tt"] = lambda ma: TT_NHAN.get(ma, ma)

    if db is None:
        db = get_db()
    app.config["DB"] = db

    def _trang_hien_tai():
        try:
            return max(1, int(request.args.get("trang", 1)))
        except ValueError:
            return 1

    def _phan_trang(tong, trang, moi_trang):
        so_trang = max(1, math.ceil(tong / moi_trang))

        def link(n):
            return url_for(request.endpoint, **{**request.view_args, **request.args.to_dict(), "trang": n})

        return {
            "tong": tong,
            "trang": trang,
            "so_trang": so_trang,
            "truoc": link(trang - 1) if trang > 1 else None,
            "sau": link(trang + 1) if trang < so_trang else None,
        }

    # ---------- Giỏ hàng (MongoDB `giohang` cho KH; session cho khách vãng lai) ----------

    def _lay_items_gio_tho():
        if la_khach_hang() and ma_khach_hien_tai():
            return services.lay_gio_hang(db, ma_khach_hien_tai())
        return list(session.get("guest_cart", []))

    def _luu_items_gio_tho(items):
        if la_khach_hang() and ma_khach_hien_tai():
            services.luu_gio_hang(db, ma_khach_hien_tai(), items)
        else:
            session["guest_cart"] = items

    def _gop_gio_vang_lai_vao_kh(ma_kh):
        guest_items = session.pop("guest_cart", [])
        for it in guest_items:
            try:
                services.them_vao_gio(db, ma_kh, it["ma_sp"], it["mau"], it["size"], it["so_luong"])
            except NghiepVuError:
                pass

    def _lay_yeu_thich_hien_tai():
        if la_khach_hang() and ma_khach_hien_tai():
            return services.lay_yeu_thich(db, ma_khach_hien_tai())
        return list(session.get("guest_wish", []))

    def _context_tai_khoan():
        ma_kh = ma_khach_hien_tai()
        khach = db.khachhang.find_one({"_id": ma_kh})
        if khach is None:
            abort(403)
        don_all = list(db.donhang.find({"ma_kh": ma_kh}, {"trang_thai": 1, "tong_tien": 1}))
        tong_chi_ht = sum(d["tong_tien"] for d in don_all if d["trang_thai"] == services.TRANG_THAI_HOAN_THANH)
        return {
            "khach": khach,
            "hang": services.tinh_hang_thanh_vien(tong_chi_ht),
            "so_don_tong": len(don_all),
            "so_dang_xu_ly": sum(1 for d in don_all if d["trang_thai"] in ("CHO_XAC_NHAN", "DANG_CHUAN_BI", "DANG_GIAO")),
            "so_yeu_thich": len(khach.get("yeu_thich") or []),
            "so_dia_chi": len(services.lay_so_dia_chi(khach)),
            "so_danh_gia": db.danhgia.count_documents({"ma_kh": ma_kh}),
        }

    def _xay_gio_day_du():
        raw = _lay_items_gio_tho()
        if not raw:
            return {"ds_hang": [], "so_luong": 0, "tam_tinh": 0, "phi_ship": 0, "tong_tien": 0}
        ids = list({i["ma_sp"] for i in raw})
        sp_map = {s["_id"]: s for s in db.sanpham.find({"_id": {"$in": ids}, "hoat_dong": {"$ne": False}})}
        ds_hang = []
        for it in raw:
            sp = sp_map.get(it["ma_sp"])
            if not sp:
                continue
            bt = next((b for b in sp.get("bien_the", []) if b["mau"] == it["mau"] and b["size"] == it["size"]), None)
            ton = bt["ton_kho"] if bt else 0
            sl = int(it["so_luong"])
            if sl <= 0:
                continue
            anh = (sp.get("hinh_anh") or ["prod_shirt_white.jpg"])[0]
            ds_hang.append({
                "ma_sp": sp["_id"],
                "ten_sp": sp["ten_sp"],
                "mau": it["mau"],
                "size": it["size"],
                "so_luong": sl,
                "don_gia": sp["don_gia"],
                "thanh_tien": sl * sp["don_gia"],
                "hinh_anh": anh,
                "ton_kho": ton,
            })
        tam_tinh = sum(i["thanh_tien"] for i in ds_hang)
        phi_ship = services.tinh_phi_ship(tam_tinh) if ds_hang else 0
        return {
            "ds_hang": ds_hang,
            "so_luong": sum(i["so_luong"] for i in ds_hang),
            "tam_tinh": tam_tinh,
            "phi_ship": phi_ship,
            "tong_tien": tam_tinh + phi_ship,
        }

    # ---------- Trước request & Context chung ----------

    @app.route("/favicon.ico")
    def favicon():
        return Response(status=204)

    @app.before_request
    def bao_ve_route():
        # Tự động dọn phiên đăng nhập cũ có vai trò ngoài 3 role hiện hành (ADMIN, NV, KH)
        if "ma_nd" in session and session.get("vai_tro") not in ("ADMIN", "NV", "KH"):
            session.clear()
        ep = request.endpoint or ""
        if ep.startswith("admin_"):
            if "ma_nd" not in session:
                tham_so = {"next": request.full_path.rstrip("?")} if request.method == "GET" else {}
                return redirect(url_for("dang_nhap", **tham_so))
            if not la_noi_bo():
                abort(403)
        elif ep.startswith("tai_khoan"):
            if "ma_nd" not in session:
                tham_so = {"next": request.full_path.rstrip("?")} if request.method == "GET" else {}
                return redirect(url_for("dang_nhap", **tham_so))
            if not la_khach_hang():
                abort(403)
        return None

    def _thong_bao_admin():
        if not la_noi_bo():
            return []
        ds = []
        so_cho = db.donhang.count_documents({"trang_thai": services.TRANG_THAI_CHO_XN})
        if so_cho:
            ds.append({
                "tieu_de": f"{so_cho} đơn chờ xác nhận",
                "mo_ta": "Cần kiểm tra và xác nhận giao hàng",
                "icon": "hourglass-split",
                "url": url_for("admin_don_hang", trang_thai=services.TRANG_THAI_CHO_XN),
            })
        so_het = len(queries.bien_the_sap_het(db, NGUONG_TON))
        if so_het:
            ds.append({
                "tieu_de": f"{so_het} biến thể sắp hết hàng",
                "mo_ta": f"Tồn kho dưới {NGUONG_TON} sản phẩm",
                "icon": "exclamation-triangle",
                "url": url_for("admin_kho", muc="canh-bao"),
            })
        return ds

    @app.context_processor
    def them_context():
        nd = nguoi_dung_hien_tai()
        ep = request.endpoint or ""
        is_admin_page = ep.startswith("admin_")
        buoc = []
        if is_admin_page:
            buoc = [
                {"nhan": nhan, "url": url_for(target) if target else None}
                for nhan, target in xay_breadcrumb(ep, request.view_args, request.args)
            ]
        return {
            "nguoi_dung": nd,
            "co_quyen": co_quyen,
            "app_version": APP_VERSION,
            "menu": xay_menu(co_quyen, url_for, ep, request.args) if (nd and is_admin_page) else [],
            "breadcrumb": buoc,
            "thong_bao_he_thong": _thong_bao_admin,
            "danh_muc_nav": list(db.danhmuc.find({}).sort("thu_tu", 1)) if not is_admin_page else [],
            "gio_tom_tat": _xay_gio_day_du() if not is_admin_page else {"ds_hang": [], "so_luong": 0, "tam_tinh": 0},
            "yeu_thich_ids": _lay_yeu_thich_hien_tai() if not is_admin_page else [],
        }

    @app.errorhandler(403)
    def khong_co_quyen(_loi):
        return render_template("403.html"), 403

    # =========================================================================
    # 1. MẶT TIỀN CỬA HÀNG CÔNG KHAI (CHUẨN ARISTINO)
    # =========================================================================

    @app.route("/")
    def trang_chu():
        """Trang chủ thuần quảng cáo & chiến dịch thời trang (không nhét lưới sản phẩm bán lẻ)."""
        return render_template("store/trang_chu.html")

    @app.route("/bo-suu-tap")
    def bo_suu_tap():
        """Tab Bộ sưu tập độc lập — Lookbook 4 chương, kể chuyện chất liệu & thiết kế tiêu biểu."""
        sp_noi_bat = list(
            db.sanpham.find({"hoat_dong": {"$ne": False}})
            .sort([("bo_suu_tap", 1), ("_id", 1)])
            .limit(4)
        )
        ten_dm_map = {d["_id"]: d["ten_dm"] for d in db.danhmuc.find({})}
        return render_template("store/bo_suu_tap.html", sp_noi_bat=sp_noi_bat, ten_dm_map=ten_dm_map)

    @app.route("/thuong-hieu")
    def thuong_hieu():
        """Tab Thương hiệu độc lập — Triết lý, chỉ số, quy trình chế tác & hành trình phát triển."""
        return render_template("store/thuong_hieu.html")

    @app.route("/san-pham")
    def cua_hang():
        """Tab Sản phẩm tách riêng — bộ lọc trái + lưới 3 cột phải kiểu Aristino."""
        danh_muc = request.args.get("danh_muc", "").strip()
        bo_suu_tap = request.args.get("bo_suu_tap", "").strip()
        mau = request.args.get("mau", "").strip()
        size = request.args.get("size", "").strip()
        khoang_gia = request.args.get("gia", "").strip()
        q = request.args.get("q", "").strip()
        sap_xep = request.args.get("sap_xep", "moi").strip()

        loc = {"hoat_dong": {"$ne": False}}
        dm_hien_tai = None
        if danh_muc:
            dm_hien_tai = db.danhmuc.find_one({"slug": danh_muc})
            if dm_hien_tai:
                loc["ma_dm"] = dm_hien_tai["_id"]
        if bo_suu_tap == "sale":
            loc["$expr"] = {"$gt": ["$gia_goc", "$don_gia"]}
        elif bo_suu_tap == "moi":
            loc["bo_suu_tap"] = "moi"
        if mau and size:
            loc["bien_the"] = {"$elemMatch": {"mau": mau, "size": size}}
        elif mau:
            loc["bien_the.mau"] = mau
        elif size:
            loc["bien_the.size"] = size
        if khoang_gia == "duoi-1tr":
            loc["don_gia"] = {"$lt": 1_000_000}
        elif khoang_gia == "1tr-2tr":
            loc["don_gia"] = {"$gte": 1_000_000, "$lte": 2_000_000}
        elif khoang_gia == "tren-2tr":
            loc["don_gia"] = {"$gt": 2_000_000}
        if q:
            regex = {"$regex": re.escape(q), "$options": "i"}
            loc["$or"] = [{"ten_sp": regex}, {"_id": regex}, {"mo_ta": regex}]

        sort_spec = [("_id", -1)]
        if sap_xep == "gia-tang":
            sort_spec = [("don_gia", 1)]
        elif sap_xep == "gia-giam":
            sort_spec = [("don_gia", -1)]

        tong = db.sanpham.count_documents(loc)
        trang = _trang_hien_tai()
        ds = list(
            db.sanpham.find(loc)
            .sort(sort_spec)
            .skip((trang - 1) * SO_DONG_MOI_TRANG)
            .limit(SO_DONG_MOI_TRANG)
        )
        for sp in ds:
            sp["ds_mau"] = list(dict.fromkeys(b["mau"] for b in sp.get("bien_the", [])))

        ten_dm_map = {d["_id"]: d["ten_dm"] for d in db.danhmuc.find({})}
        tat_ca_mau = sorted(db.sanpham.distinct("bien_the.mau", {"hoat_dong": {"$ne": False}}))

        if dm_hien_tai:
            tieu_de_trang = dm_hien_tai["ten_dm"]
        elif bo_suu_tap == "sale":
            tieu_de_trang = "Final Sale"
        elif bo_suu_tap == "moi":
            tieu_de_trang = "Hàng mới về"
        else:
            tieu_de_trang = "Tất cả sản phẩm"

        return render_template(
            "store/san_pham.html",
            ds=ds,
            tong=tong,
            tieu_de_trang=tieu_de_trang,
            dm_hien_tai=dm_hien_tai,
            danh_muc=danh_muc,
            bo_suu_tap=bo_suu_tap,
            mau=mau,
            size=size,
            khoang_gia=khoang_gia,
            q=q,
            sap_xep=sap_xep,
            tat_ca_mau=tat_ca_mau,
            ten_dm_map=ten_dm_map,
            mau_hex=MAU_HEX,
            pt=_phan_trang(tong, trang, SO_DONG_MOI_TRANG),
        )

    @app.route("/san-pham/<ma_sp>")
    def chi_tiet_sp(ma_sp):
        sp = db.sanpham.find_one({"_id": ma_sp, "hoat_dong": {"$ne": False}})
        if sp is None:
            abort(404)
        dm = db.danhmuc.find_one({"_id": sp["ma_dm"]})
        ds_mau = list(dict.fromkeys(b["mau"] for b in sp.get("bien_the", [])))
        thu_tu_size = ["S", "M", "L", "XL", "XXL"]
        size_co = list(dict.fromkeys(b["size"] for b in sp.get("bien_the", [])))
        ds_size = sorted(size_co, key=lambda x: thu_tu_size.index(x) if x in thu_tu_size else 99)

        con_hang = next((b for b in sp.get("bien_the", []) if b["ton_kho"] > 0), None)
        mau_mac_dinh = con_hang["mau"] if con_hang else (ds_mau[0] if ds_mau else "")
        size_mac_dinh = con_hang["size"] if con_hang else (ds_size[0] if ds_size else "")

        lien_quan = list(
            db.sanpham.find({"ma_dm": sp["ma_dm"], "_id": {"$ne": ma_sp}, "hoat_dong": {"$ne": False}})
            .limit(4)
        )
        danh_gia = services.lay_danh_gia_san_pham(db, ma_sp)
        co_the_danh_gia = False
        danh_gia_cua_toi = None
        if la_khach_hang() and ma_khach_hien_tai():
            co_the_danh_gia = services.kiem_tra_quyen_danh_gia(db, ma_khach_hien_tai(), ma_sp) is not None
            danh_gia_cua_toi = db.danhgia.find_one({"ma_kh": ma_khach_hien_tai(), "ma_sp": ma_sp})
        return render_template(
            "store/chi_tiet_sp.html",
            sp=sp,
            dm=dm,
            ds_mau=ds_mau,
            ds_size=ds_size,
            mau_mac_dinh=mau_mac_dinh,
            size_mac_dinh=size_mac_dinh,
            lien_quan=lien_quan,
            danh_gia=danh_gia,
            co_the_danh_gia=co_the_danh_gia,
            danh_gia_cua_toi=danh_gia_cua_toi,
            phom_danh_gia=services.PHOM_DANH_GIA,
        )

    @app.route("/san-pham/<ma_sp>/danh-gia", methods=["POST"])
    @cho_phep("mua_hang")
    def gui_danh_gia(ma_sp):
        if db.sanpham.find_one({"_id": ma_sp}, {"_id": 1}) is None:
            abort(404)
        try:
            services.tao_danh_gia(
                db,
                ma_khach_hien_tai(),
                ma_sp,
                so_sao=request.form.get("so_sao", 5),
                noi_dung=request.form.get("noi_dung", ""),
                phom_dang=request.form.get("phom_dang", "Vừa vặn"),
            )
            flash("Cảm ơn bạn đã gửi đánh giá sản phẩm!", "ok")
        except NghiepVuError as loi:
            flash(str(loi), "loi")
        return redirect(url_for("chi_tiet_sp", ma_sp=ma_sp) + "#danh-gia")

    @app.route("/yeu-thich")
    def yeu_thich_cong_khai():
        if la_khach_hang():
            return redirect(url_for("tai_khoan_yeu_thich"))
        ids = list(session.get("guest_wish", []))
        ds_sp = []
        if ids:
            sp_map = {s["_id"]: s for s in db.sanpham.find({"_id": {"$in": ids}, "hoat_dong": {"$ne": False}})}
            for mid in ids:
                if mid in sp_map:
                    sp = sp_map[mid]
                    sp["tong_ton"] = sum(b["ton_kho"] for b in sp.get("bien_the", []))
                    ds_sp.append(sp)
        ten_dm_map = {d["_id"]: d["ten_dm"] for d in db.danhmuc.find({})}
        return render_template("store/yeu_thich_khach.html", ds_sp=ds_sp, ten_dm_map=ten_dm_map)

    @app.route("/api/yeu-thich", methods=["POST"])
    def api_yeu_thich():
        data = request.get_json(silent=True) or request.form
        ma_sp = (data.get("ma_sp") or "").strip()
        if not ma_sp:
            return jsonify({"ok": False, "error": "Thiếu mã sản phẩm"}), 400
        if la_noi_bo():
            return jsonify({"ok": False, "error": "Tài khoản nội bộ không sử dụng danh sách yêu thích"}), 403

        if la_khach_hang() and ma_khach_hien_tai():
            try:
                saved, ds = services.chuyen_yeu_thich(db, ma_khach_hien_tai(), ma_sp)
            except NghiepVuError as loi:
                return jsonify({"ok": False, "error": str(loi)}), 400
            return jsonify({"ok": True, "saved": saved, "count": len(ds)})

        sp = db.sanpham.find_one({"_id": ma_sp, "hoat_dong": {"$ne": False}}, {"_id": 1})
        if sp is None:
            return jsonify({"ok": False, "error": "Sản phẩm không tồn tại"}), 404
        ds = list(session.get("guest_wish", []))
        if ma_sp in ds:
            ds = [x for x in ds if x != ma_sp]
            saved = False
        else:
            ds.append(ma_sp)
            saved = True
        session["guest_wish"] = ds
        return jsonify({"ok": True, "saved": saved, "count": len(ds)})

    # ---------- Giỏ hàng & Thanh toán ----------

    @app.route("/gio-hang")
    def gio_hang():
        return render_template("store/gio_hang.html", gio=_xay_gio_day_du())

    @app.route("/gio-hang/them", methods=["POST"])
    def gio_hang_them():
        ma_sp = request.form.get("ma_sp", "").strip()
        mau = request.form.get("mau", "").strip()
        size = request.form.get("size", "").strip()
        so_luong = _so_nguyen_duong(request.form.get("so_luong", "1"))
        hanh_dong = request.form.get("hanh_dong", "them")

        if not ma_sp or not mau or not size or so_luong is None:
            flash("Vui lòng chọn đầy đủ màu sắc, kích cỡ và số lượng hợp lệ", "loi")
            return redirect(request.referrer or url_for("cua_hang"))

        if la_khach_hang() and ma_khach_hien_tai():
            try:
                services.them_vao_gio(db, ma_khach_hien_tai(), ma_sp, mau, size, so_luong)
            except NghiepVuError as loi:
                flash(str(loi), "loi")
                return redirect(request.referrer or url_for("chi_tiet_sp", ma_sp=ma_sp))
        else:
            sp = db.sanpham.find_one({"_id": ma_sp, "hoat_dong": {"$ne": False}})
            bt = next((b for b in (sp or {}).get("bien_the", []) if b["mau"] == mau and b["size"] == size), None)
            if not sp or not bt:
                flash("Sản phẩm hoặc phiên bản không tồn tại", "loi")
                return redirect(request.referrer or url_for("cua_hang"))
            items = _lay_items_gio_tho()
            found = False
            for it in items:
                if it["ma_sp"] == ma_sp and it["mau"] == mau and it["size"] == size:
                    if it["so_luong"] + so_luong > bt["ton_kho"]:
                        flash(f"Chỉ còn {bt['ton_kho']} sản phẩm cho phiên bản {mau} / {size}", "loi")
                        return redirect(request.referrer or url_for("chi_tiet_sp", ma_sp=ma_sp))
                    it["so_luong"] += so_luong
                    found = True
                    break
            if not found:
                if so_luong > bt["ton_kho"]:
                    flash(f"Chỉ còn {bt['ton_kho']} sản phẩm cho phiên bản {mau} / {size}", "loi")
                    return redirect(request.referrer or url_for("chi_tiet_sp", ma_sp=ma_sp))
                items.append({"ma_sp": ma_sp, "mau": mau, "size": size, "so_luong": so_luong})
            _luu_items_gio_tho(items)

        flash("Đã thêm sản phẩm vào giỏ hàng", "ok")
        if hanh_dong == "mua_ngay":
            return redirect(url_for("thanh_toan"))
        return redirect(request.referrer or url_for("gio_hang"))

    @app.route("/gio-hang/cap-nhat", methods=["POST"])
    def gio_hang_cap_nhat():
        ma_sp = request.form.get("ma_sp", "").strip()
        mau = request.form.get("mau", "").strip()
        size = request.form.get("size", "").strip()
        so_luong = _so_nguyen_khong_am(request.form.get("so_luong", "0"), mac_dinh=0)
        if so_luong is None:
            flash("Số lượng không hợp lệ", "loi")
            return redirect(url_for("gio_hang"))

        items = _lay_items_gio_tho()
        moi = []
        for it in items:
            if it["ma_sp"] == ma_sp and it["mau"] == mau and it["size"] == size:
                if so_luong > 0:
                    sp = db.sanpham.find_one({"_id": ma_sp})
                    bt = next((b for b in (sp or {}).get("bien_the", []) if b["mau"] == mau and b["size"] == size), None)
                    if bt and so_luong > bt["ton_kho"]:
                        flash(f"Chỉ còn {bt['ton_kho']} sản phẩm cho {mau} / {size}", "loi")
                        return redirect(url_for("gio_hang"))
                    moi.append({**it, "so_luong": so_luong})
            else:
                moi.append(it)
        _luu_items_gio_tho(moi)
        flash("Đã cập nhật giỏ hàng", "ok")
        return redirect(url_for("gio_hang"))

    @app.route("/thanh-toan", methods=["GET", "POST"])
    def thanh_toan():
        if "ma_nd" not in session:
            flash("Vui lòng đăng nhập tài khoản Khách hàng để đặt hàng", "loi")
            return redirect(url_for("dang_nhap", next=url_for("thanh_toan")))
        if not la_khach_hang():
            flash("Tài khoản nội bộ không đặt mua trên cửa hàng; vui lòng dùng tài khoản Khách hàng (KH)", "loi")
            return redirect(url_for("cua_hang"))

        gio = _xay_gio_day_du()
        if not gio["ds_hang"]:
            flash("Giỏ hàng của bạn đang trống", "loi")
            return redirect(url_for("cua_hang"))

        khach = db.khachhang.find_one({"_id": ma_khach_hien_tai()}) or {}
        so_dia_chi = services.lay_so_dia_chi(khach)
        dc_mac_dinh = next((d for d in so_dia_chi if d.get("mac_dinh")), so_dia_chi[0] if so_dia_chi else None)
        mac_dinh = {
            "ho_ten": request.form.get("ho_ten", (dc_mac_dinh["ho_ten"] if dc_mac_dinh else khach.get("ten_kh", ""))),
            "sdt": request.form.get("sdt", (dc_mac_dinh["sdt"] if dc_mac_dinh else khach.get("sdt", ""))),
            "dia_chi": request.form.get("dia_chi", (dc_mac_dinh["dia_chi"] if dc_mac_dinh else khach.get("dia_chi", ""))),
            "ghi_chu": request.form.get("ghi_chu", ""),
        }

        if request.method == "POST":
            dong_hang = [
                {"ma_sp": it["ma_sp"], "mau": it["mau"], "size": it["size"], "so_luong": it["so_luong"]}
                for it in gio["ds_hang"]
            ]
            try:
                don = services.dat_hang(
                    db,
                    ma_tiep_theo(db.donhang, "DH", 6),
                    ma_khach_hien_tai(),
                    dong_hang,
                    giao_hang=mac_dinh,
                    phuong_thuc_tt=request.form.get("phuong_thuc_tt", "COD"),
                    xoa_gio=True,
                )
            except NghiepVuError as loi:
                flash(str(loi), "loi")
                return render_template("store/thanh_toan.html", gio=gio, mac_dinh=mac_dinh, so_dia_chi=so_dia_chi)

            flash(f"Đặt hàng thành công! Mã đơn của bạn là {don['_id']}.", "ok")
            return redirect(url_for("tai_khoan_don", ma_don=don["_id"]))

        return render_template("store/thanh_toan.html", gio=gio, mac_dinh=mac_dinh, so_dia_chi=so_dia_chi)

    # =========================================================================
    # 2. ĐĂNG NHẬP, ĐĂNG KÝ, ĐĂNG XUẤT (3 ROLE: ADMIN, NV, KH)
    # =========================================================================

    @app.route("/dang-nhap", methods=["GET", "POST"])
    def dang_nhap():
        if "ma_nd" in session:
            return redirect(url_for("admin_dashboard") if la_noi_bo() else url_for("tai_khoan"))

        if request.method == "POST":
            ten = request.form.get("ten_dang_nhap", "").strip().lower()
            mat_khau = request.form.get("mat_khau", "")
            nd = db.nguoidung.find_one({"ten_dang_nhap": ten}) if ten else None
            hop_le = nd is not None and kiem_tra_mat_khau(nd.get("mat_khau"), mat_khau)

            if hop_le and nd["vai_tro"] in ("ADMIN", "NV", "KH"):
                if nd.get("hoat_dong") is False:
                    flash("Tài khoản đã bị khóa, vui lòng liên hệ Quản trị viên", "loi")
                    return render_template("store/dang_nhap.html", tab="dang_nhap", form={})
                kh_doc = None
                if nd["vai_tro"] == "KH":
                    kh_doc = db.khachhang.find_one({"ma_nd": nd["_id"]})
                    if kh_doc is None or kh_doc.get("hoat_dong") is False:
                        flash("Tài khoản khách hàng đã ngừng hoạt động hoặc chưa hợp lệ", "loi")
                        return render_template("store/dang_nhap.html", tab="dang_nhap", form={})

                guest_cart = session.get("guest_cart", [])
                guest_wish = session.get("guest_wish", [])
                session.clear()
                session["ma_nd"] = nd["_id"]
                session["ten"] = nd["ten_dang_nhap"]
                session["ho_ten"] = nd.get("ho_ten") or (kh_doc["ten_kh"] if kh_doc else nd["ten_dang_nhap"])
                session["vai_tro"] = nd["vai_tro"]
                if kh_doc:
                    session["ma_kh"] = kh_doc["_id"]
                    session["guest_cart"] = guest_cart
                    _gop_gio_vang_lai_vao_kh(kh_doc["_id"])
                    services.gop_yeu_thich(db, kh_doc["_id"], guest_wish)

                chuyen_toi = request.args.get("next", "")
                if _duong_dan_an_toan(chuyen_toi):
                    return redirect(chuyen_toi)
                return redirect(url_for("admin_dashboard") if nd["vai_tro"] in ("ADMIN", "NV") else url_for("tai_khoan"))

            flash("Sai tên đăng nhập hoặc mật khẩu", "loi")
        return render_template("store/dang_nhap.html", tab="dang_nhap", form={})

    @app.route("/dang-ky", methods=["GET", "POST"])
    def dang_ky():
        if "ma_nd" in session:
            return redirect(url_for("admin_dashboard") if la_noi_bo() else url_for("tai_khoan"))

        if request.method == "POST":
            try:
                nd, kh = services.dang_ky_khach_hang(
                    db,
                    request.form.get("ten_dang_nhap", ""),
                    request.form.get("mat_khau", ""),
                    request.form.get("ho_ten", ""),
                    request.form.get("sdt", ""),
                    request.form.get("dia_chi", ""),
                )
            except NghiepVuError as loi:
                flash(str(loi), "loi")
                return render_template("store/dang_nhap.html", tab="dang_ky", form=request.form)

            guest_cart = session.get("guest_cart", [])
            guest_wish = session.get("guest_wish", [])
            session.clear()
            session["ma_nd"] = nd["_id"]
            session["ten"] = nd["ten_dang_nhap"]
            session["ho_ten"] = kh["ten_kh"]
            session["vai_tro"] = "KH"
            session["ma_kh"] = kh["_id"]
            session["guest_cart"] = guest_cart
            _gop_gio_vang_lai_vao_kh(kh["_id"])
            services.gop_yeu_thich(db, kh["_id"], guest_wish)

            flash("Đăng ký tài khoản khách hàng thành công!", "ok")
            chuyen_toi = request.args.get("next", "")
            return redirect(chuyen_toi if _duong_dan_an_toan(chuyen_toi) else url_for("tai_khoan"))

        return render_template("store/dang_nhap.html", tab="dang_ky", form={})

    @app.route("/dang-xuat", methods=["POST"])
    def dang_xuat():
        session.clear()
        flash("Đã đăng xuất tài khoản", "ok")
        return redirect(url_for("trang_chu"))

    @app.route("/ho-so")
    def ho_so_chuyen_huong():
        if "ma_nd" not in session:
            return redirect(url_for("dang_nhap", next=url_for("ho_so_chuyen_huong")))
        if la_noi_bo():
            return redirect(url_for("admin_ho_so"))
        if la_khach_hang():
            return redirect(url_for("tai_khoan_ho_so"))
        return redirect(url_for("dang_nhap"))

    # =========================================================================
    # 3. TÀI KHOẢN KHÁCH HÀNG (/tai-khoan — CHỈ ROLE KH, CÔ LẬP DỮ LIỆU CHẶT)
    # =========================================================================

    @app.route("/tai-khoan")
    @cho_phep("mua_hang")
    def tai_khoan():
        tk = _context_tai_khoan()
        ma_kh = ma_khach_hien_tai()
        don = list(db.donhang.find({"ma_kh": ma_kh}).sort("ngay_dat", -1))
        tong_chi = sum(d["tong_tien"] for d in don if d["trang_thai"] != "DA_HUY")
        so_dc = services.lay_so_dia_chi(tk["khach"])
        dia_chi_mac_dinh = next((d for d in so_dc if d.get("mac_dinh")), so_dc[0] if so_dc else None)
        return render_template(
            "store/tai_khoan.html",
            tk=tk,
            khach=tk["khach"],
            don=don,
            don_gan=don[:3],
            so_dang_xu_ly=tk["so_dang_xu_ly"],
            tong_chi=tong_chi,
            dia_chi_mac_dinh=dia_chi_mac_dinh,
            trang_thai_lop=TRANG_THAI_LOP_STORE,
        )

    @app.route("/tai-khoan/don-hang")
    @cho_phep("mua_hang")
    def tai_khoan_don_hang():
        tk = _context_tai_khoan()
        ma_kh = ma_khach_hien_tai()
        trang_thai = request.args.get("trang_thai", "").strip()
        q = request.args.get("q", "").strip()

        tat_ca = list(db.donhang.find({"ma_kh": ma_kh}, {"trang_thai": 1}))
        dem_tt = {"TAT_CA": len(tat_ca)}
        for d in tat_ca:
            dem_tt[d["trang_thai"]] = dem_tt.get(d["trang_thai"], 0) + 1

        loc = {"ma_kh": ma_kh}
        if trang_thai in TRANG_THAI_NHAN:
            loc["trang_thai"] = trang_thai
        if q:
            mau = {"$regex": re.escape(q), "$options": "i"}
            loc["$or"] = [{"_id": mau}, {"chi_tiet.ten_sp": mau}]

        don = list(db.donhang.find(loc).sort("ngay_dat", -1))
        return render_template(
            "store/tai_khoan_don_ds.html",
            tk=tk,
            don=don,
            trang_thai=trang_thai,
            q=q,
            dem_tt=dem_tt,
            trang_thai_nhan=TRANG_THAI_NHAN,
            trang_thai_lop=TRANG_THAI_LOP_STORE,
        )

    @app.route("/tai-khoan/ho-so", methods=["GET", "POST"])
    @cho_phep("mua_hang")
    def tai_khoan_ho_so():
        tk = _context_tai_khoan()
        ma_nd = session["ma_nd"]
        nd = db.nguoidung.find_one({"_id": ma_nd}, {"mat_khau": 0})
        khach = tk["khach"]
        if nd is None:
            abort(403)

        if request.method == "POST":
            loai_form = request.form.get("form_type", "ho_so")
            if loai_form == "mat_khau":
                try:
                    services.doi_mat_khau_ca_nhan(
                        db,
                        ma_nd,
                        request.form.get("mat_khau_cu", ""),
                        request.form.get("mat_khau_moi", ""),
                        request.form.get("xac_nhan_mat_khau", ""),
                    )
                    flash("Đã đổi mật khẩu thành công", "ok")
                    return redirect(url_for("tai_khoan_ho_so"))
                except NghiepVuError as loi:
                    flash(str(loi), "loi")
            else:
                ho_ten = request.form.get("ho_ten", "")
                email = request.form.get("email", "")
                sdt = request.form.get("sdt", "")
                dia_chi = request.form.get("dia_chi", "")
                try:
                    nd_moi = services.cap_nhat_ho_so_ca_nhan(
                        db,
                        ma_nd,
                        ho_ten=ho_ten,
                        email=email,
                        sdt=sdt,
                        dia_chi=dia_chi,
                    )
                    session["ho_ten"] = nd_moi["ho_ten"]
                    flash("Đã cập nhật thông tin cá nhân", "ok")
                    return redirect(url_for("tai_khoan_ho_so"))
                except NghiepVuError as loi:
                    flash(str(loi), "loi")
                    nd = {**nd, "ho_ten": ho_ten, "email": email, "sdt": sdt}
                    khach = {**khach, "ten_kh": ho_ten, "email": email, "sdt": sdt, "dia_chi": dia_chi}

        return render_template("store/tai_khoan_ho_so.html", tk=tk, nd=nd, khach=khach)

    @app.route("/tai-khoan/dia-chi", methods=["GET", "POST"])
    @cho_phep("mua_hang")
    def tai_khoan_dia_chi():
        tk = _context_tai_khoan()
        ma_kh = ma_khach_hien_tai()
        if request.method == "POST":
            try:
                services.luu_dia_chi(
                    db,
                    ma_kh,
                    ho_ten=request.form.get("ho_ten", ""),
                    sdt=request.form.get("sdt", ""),
                    dia_chi=request.form.get("dia_chi", ""),
                    nhan=request.form.get("nhan", "Nhà riêng"),
                    mac_dinh=request.form.get("mac_dinh") == "1",
                    id_dc=request.form.get("id_dc") or None,
                )
                flash("Đã lưu địa chỉ giao hàng", "ok")
                return redirect(url_for("tai_khoan_dia_chi"))
            except NghiepVuError as loi:
                flash(str(loi), "loi")
                ds_dia_chi = services.lay_so_dia_chi(tk["khach"])
                return render_template(
                    "store/tai_khoan_dia_chi.html",
                    tk=tk,
                    ds_dia_chi=ds_dia_chi,
                    dang_sua=None,
                    form=request.form,
                )

        ds_dia_chi = services.lay_so_dia_chi(tk["khach"])
        sua_id = request.args.get("sua", "").strip()
        dang_sua = next((d for d in ds_dia_chi if d["id"] == sua_id), None) if sua_id else None
        return render_template(
            "store/tai_khoan_dia_chi.html",
            tk=tk,
            ds_dia_chi=ds_dia_chi,
            dang_sua=dang_sua,
            form={},
        )

    @app.route("/tai-khoan/dia-chi/<id_dc>/mac-dinh", methods=["POST"])
    @cho_phep("mua_hang")
    def tai_khoan_dia_chi_mac_dinh(id_dc):
        try:
            services.dat_dia_chi_mac_dinh(db, ma_khach_hien_tai(), id_dc)
            flash("Đã đặt địa chỉ giao hàng mặc định", "ok")
        except NghiepVuError as loi:
            flash(str(loi), "loi")
        return redirect(url_for("tai_khoan_dia_chi"))

    @app.route("/tai-khoan/dia-chi/<id_dc>/xoa", methods=["POST"])
    @cho_phep("mua_hang")
    def tai_khoan_xoa_dia_chi(id_dc):
        try:
            services.xoa_dia_chi(db, ma_khach_hien_tai(), id_dc)
            flash("Đã xóa địa chỉ giao hàng", "ok")
        except NghiepVuError as loi:
            flash(str(loi), "loi")
        return redirect(url_for("tai_khoan_dia_chi"))

    @app.route("/tai-khoan/yeu-thich")
    @cho_phep("mua_hang")
    def tai_khoan_yeu_thich():
        tk = _context_tai_khoan()
        ids = list(tk["khach"].get("yeu_thich") or [])
        ds_sp = []
        if ids:
            sp_map = {s["_id"]: s for s in db.sanpham.find({"_id": {"$in": ids}, "hoat_dong": {"$ne": False}})}
            for mid in ids:
                if mid in sp_map:
                    sp = sp_map[mid]
                    sp["tong_ton"] = sum(b["ton_kho"] for b in sp.get("bien_the", []))
                    ds_sp.append(sp)
        ten_dm_map = {d["_id"]: d["ten_dm"] for d in db.danhmuc.find({})}
        return render_template("store/tai_khoan_yeu_thich.html", tk=tk, ds_sp=ds_sp, ten_dm_map=ten_dm_map)

    @app.route("/tai-khoan/yeu-thich/<ma_sp>/xoa", methods=["POST"])
    @cho_phep("mua_hang")
    def tai_khoan_bo_yeu_thich(ma_sp):
        db.khachhang.update_one({"_id": ma_khach_hien_tai()}, {"$pull": {"yeu_thich": ma_sp}})
        flash("Đã bỏ sản phẩm khỏi danh sách yêu thích", "ok")
        return redirect(url_for("tai_khoan_yeu_thich"))

    @app.route("/tai-khoan/danh-gia")
    @cho_phep("mua_hang")
    def tai_khoan_danh_gia():
        tk = _context_tai_khoan()
        ma_kh = ma_khach_hien_tai()
        ds_danh_gia = list(db.danhgia.find({"ma_kh": ma_kh}).sort("ngay_tao", -1))
        da_dg_ids = {d["ma_sp"] for d in ds_danh_gia}

        cho_danh_gia = []
        thay = set()
        for don in db.donhang.find({"ma_kh": ma_kh, "trang_thai": services.TRANG_THAI_HOAN_THANH}).sort("ngay_dat", -1):
            for ct in don.get("chi_tiet", []):
                mid = ct["ma_sp"]
                if mid not in da_dg_ids and mid not in thay:
                    thay.add(mid)
                    cho_danh_gia.append({
                        "ma_sp": mid,
                        "ten_sp": ct["ten_sp"],
                        "hinh_anh": ct.get("hinh_anh"),
                        "ma_don": don["_id"],
                    })

        sp_ids = list({d["ma_sp"] for d in ds_danh_gia})
        sp_map = {s["_id"]: s for s in db.sanpham.find({"_id": {"$in": sp_ids}}, {"ten_sp": 1})} if sp_ids else {}
        return render_template(
            "store/tai_khoan_danh_gia.html",
            tk=tk,
            ds_danh_gia=ds_danh_gia,
            cho_danh_gia=cho_danh_gia,
            sp_map=sp_map,
        )

    @app.route("/tai-khoan/don-hang/<ma_don>")
    @cho_phep("mua_hang")
    def tai_khoan_don(ma_don):
        tk = _context_tai_khoan()
        don = db.donhang.find_one({"_id": ma_don})
        if don is None:
            abort(404)
        if don["ma_kh"] != ma_khach_hien_tai():
            abort(403)
        sp_ids = [ct["ma_sp"] for ct in don.get("chi_tiet", [])]
        da_danh_gia = {
            d["ma_sp"]
            for d in db.danhgia.find({"ma_kh": ma_khach_hien_tai(), "ma_sp": {"$in": sp_ids}}, {"ma_sp": 1})
        }
        return render_template(
            "store/tai_khoan_don.html",
            tk=tk,
            don=don,
            lop=TRANG_THAI_LOP_STORE.get(don["trang_thai"], ""),
            da_danh_gia=da_danh_gia,
        )

    @app.route("/tai-khoan/don-hang/<ma_don>/huy", methods=["POST"])
    @cho_phep("mua_hang")
    def tai_khoan_huy_don(ma_don):
        don = db.donhang.find_one({"_id": ma_don})
        if don is None:
            abort(404)
        if don["ma_kh"] != ma_khach_hien_tai():
            abort(403)
        ly_do = (request.form.get("ly_do") or "").strip()
        ly_do_khac = (request.form.get("ly_do_khac") or "").strip()
        ly_do_day_du = f"{ly_do} — {ly_do_khac}" if (ly_do and ly_do_khac) else (ly_do_khac or ly_do or "Khách hàng tự hủy đơn")
        try:
            services.huy_don(db, ma_don, nguoi_huy="KH", ly_do=ly_do_day_du)
            flash(f"Đã hủy đơn {ma_don} và hoàn trả tồn kho", "ok")
        except NghiepVuError as loi:
            flash(str(loi), "loi")
        return redirect(url_for("tai_khoan_don", ma_don=ma_don))

    @app.route("/tai-khoan/don-hang/<ma_don>/mua-lai", methods=["POST"])
    @cho_phep("mua_hang")
    def tai_khoan_mua_lai(ma_don):
        don = db.donhang.find_one({"_id": ma_don})
        if don is None:
            abort(404)
        if don["ma_kh"] != ma_khach_hien_tai():
            abort(403)
        try:
            kq = services.mua_lai_don(db, ma_khach_hien_tai(), ma_don)
            tb = f"Đã thêm {kq['da_them']} sản phẩm từ đơn {ma_don} vào giỏ hàng"
            if kq["bo_qua"]:
                tb += f" (bỏ qua {len(kq['bo_qua'])} phiên bản hết hàng)"
            flash(tb, "ok")
            return redirect(url_for("gio_hang"))
        except NghiepVuError as loi:
            flash(str(loi), "loi")
            return redirect(url_for("tai_khoan_don", ma_don=ma_don))

    # =========================================================================
    # 4. CỔNG QUẢN TRỊ NỘI BỘ (/admin — ROLE ADMIN & NV)
    # =========================================================================

    @app.route("/admin")
    @cho_phep("xem_admin")
    def admin_dashboard():
        theo_thang = queries.doanh_thu_theo_thang(db)
        thang_moi = theo_thang[-1] if theo_thang else {"thang": "-", "doanh_thu": 0, "so_don": 0}
        top_sp = queries.top_san_pham(db, 5)
        sap_het = queries.bien_the_sap_het(db, NGUONG_TON)
        don_gan = list(db.donhang.find({}).sort("ngay_dat", -1).limit(6))
        return render_template(
            "trang_chu.html",
            thang_moi=thang_moi,
            so_don=db.donhang.count_documents({"trang_thai": {"$ne": "DA_HUY"}}),
            so_khach=db.khachhang.count_documents({}),
            so_sp=db.sanpham.count_documents({}),
            so_cho_xn=db.donhang.count_documents({"trang_thai": services.TRANG_THAI_CHO_XN}),
            so_sap_het=len(sap_het),
            nguong=NGUONG_TON,
            don_gan=don_gan,
            nhan_thang=[r["thang"] for r in theo_thang],
            gia_tri_thang=[r["doanh_thu"] for r in theo_thang],
            nhan_sp=[r["ten_sp"] or r["ma_sp"] for r in top_sp],
            gia_tri_sp=[r["so_luong"] for r in top_sp],
            trang_thai_lop=TRANG_THAI_LOP_ADMIN,
        )

    # ---------- Admin: Đơn hàng ----------

    @app.route("/admin/don-hang")
    @cho_phep("xem_don")
    def admin_don_hang():
        q = request.args.get("q", "").strip()
        trang_thai = request.args.get("trang_thai", "").strip()
        loc = {}
        if trang_thai in TRANG_THAI_NHAN:
            loc["trang_thai"] = trang_thai
        if q:
            mau = {"$regex": re.escape(q), "$options": "i"}
            loc["$or"] = [{"_id": mau}, {"ma_kh": mau}, {"giao_hang.ho_ten": mau}]

        tong = db.donhang.count_documents(loc)
        trang = _trang_hien_tai()
        don = list(
            db.donhang.find(loc)
            .sort("ngay_dat", -1)
            .skip((trang - 1) * SO_DONG_ADMIN)
            .limit(SO_DONG_ADMIN)
        )
        return render_template(
            "danh_sach_don.html",
            don=don,
            q=q,
            trang_thai=trang_thai,
            trang_thai_nhan=TRANG_THAI_NHAN,
            trang_thai_lop=TRANG_THAI_LOP_ADMIN,
            pt=_phan_trang(tong, trang, SO_DONG_ADMIN),
        )

    @app.route("/admin/don-hang/<ma_don>")
    @cho_phep("xem_don")
    def admin_chi_tiet_don(ma_don):
        don = db.donhang.find_one({"_id": ma_don})
        if don is None:
            abort(404)
        trang_thai_xu_ly = [
            (ma, nhan) for ma, nhan in TRANG_THAI_NHAN.items() if ma != "DA_HUY"
        ]
        return render_template(
            "chi_tiet_don.html",
            don=don,
            lop=TRANG_THAI_LOP_ADMIN.get(don["trang_thai"], ""),
            co_the_huy=don["trang_thai"] not in ("HOAN_THANH", "DA_HUY"),
            trang_thai_xu_ly=trang_thai_xu_ly,
            json_don=_json_dep(don),
        )

    @app.route("/admin/don-hang/<ma_don>/cap-nhat", methods=["POST"])
    @cho_phep("xu_ly_don")
    def admin_cap_nhat_don(ma_don):
        try:
            services.cap_nhat_don_hang(
                db,
                ma_don,
                trang_thai_moi=request.form.get("trang_thai"),
                trang_thai_tt=request.form.get("trang_thai_tt"),
                ghi_chu=request.form.get("ghi_chu", "").strip(),
            )
            flash(f"Đã cập nhật đơn {ma_don}", "ok")
        except NghiepVuError as loi:
            flash(str(loi), "loi")
        return redirect(url_for("admin_chi_tiet_don", ma_don=ma_don))

    @app.route("/admin/don-hang/<ma_don>/huy", methods=["POST"])
    @cho_phep("huy_don")
    def admin_huy_don(ma_don):
        try:
            services.huy_don(db, ma_don, nguoi_huy="ADMIN", ly_do="Quản trị viên hủy đơn và hoàn tồn kho")
            flash(f"Đã hủy đơn {ma_don} và hoàn tồn kho thành công", "ok")
        except NghiepVuError as loi:
            flash(str(loi), "loi")
        return redirect(url_for("admin_chi_tiet_don", ma_don=ma_don))

    # ---------- Admin: Sản phẩm ----------

    @app.route("/admin/san-pham")
    @cho_phep("xem_san_pham_admin")
    def admin_san_pham():
        q = request.args.get("q", "").strip()
        loc = _tim_theo_ten("ten_sp", q)
        tong = db.sanpham.count_documents(loc)
        trang = _trang_hien_tai()
        ds = list(
            db.sanpham.find(loc).sort("_id", 1)
            .skip((trang - 1) * SO_DONG_ADMIN).limit(SO_DONG_ADMIN)
        )
        for sp in ds:
            sp["tong_ton"] = sum(b["ton_kho"] for b in sp.get("bien_the", []))
        ten_dm = {d["_id"]: d["ten_dm"] for d in db.danhmuc.find({})}
        return render_template(
            "san_pham_ds.html", ds=ds, q=q, ten_dm=ten_dm,
            pt=_phan_trang(tong, trang, SO_DONG_ADMIN),
        )

    @app.route("/admin/san-pham/moi", methods=["GET", "POST"])
    @cho_phep("ql_san_pham")
    def admin_san_pham_moi():
        danh_muc = list(db.danhmuc.find({}).sort("thu_tu", 1))
        anh_co_san = _ds_anh_san_pham()
        if request.method == "POST":
            ten = request.form.get("ten_sp", "").strip()
            ma_dm = request.form.get("ma_dm", "").strip()
            gia = _so_nguyen_duong(request.form.get("don_gia", ""))
            gia_goc = _so_nguyen_khong_am(request.form.get("gia_goc", ""), mac_dinh=gia or 0)
            mau_ds = _tach_danh_sach(request.form.get("mau", ""))
            size_ds = _tach_danh_sach(request.form.get("size", ""))
            ton_bd = _so_nguyen_khong_am(request.form.get("ton_mac_dinh", "20"), mac_dinh=20)
            if not ten or not ma_dm or gia is None or gia_goc is None or not mau_ds or not size_ds or ton_bd is None:
                flash("Vui lòng nhập đầy đủ tên, danh mục, giá bán, màu và size hợp lệ", "loi")
                return render_template("san_pham_form.html", sp=request.form, danh_muc=danh_muc, anh_co_san=anh_co_san, la_moi=True)

            bien_the = [{"mau": m, "size": s, "ton_kho": ton_bd} for m in mau_ds for s in size_ds]
            anh = request.form.get("hinh_anh", "").strip() or anh_co_san[0]
            doc = {
                "_id": ma_tiep_theo(db.sanpham, "SP", 4),
                "ten_sp": ten,
                "ma_dm": ma_dm,
                "don_gia": gia,
                "gia_goc": max(gia, gia_goc),
                "bo_suu_tap": request.form.get("bo_suu_tap", "moi"),
                "form_dang": request.form.get("form_dang", "Regular Fit").strip() or "Regular Fit",
                "chat_lieu": request.form.get("chat_lieu", "Cotton tự nhiên").strip() or "Cotton tự nhiên",
                "mo_ta": request.form.get("mo_ta", "").strip(),
                "hinh_anh": [anh],
                "bien_the": bien_the,
                "hoat_dong": True,
            }
            db.sanpham.insert_one(doc)
            flash(f"Đã thêm sản phẩm {doc['_id']}", "ok")
            return redirect(url_for("admin_san_pham"))
        return render_template("san_pham_form.html", sp={}, danh_muc=danh_muc, anh_co_san=anh_co_san, la_moi=True)

    @app.route("/admin/san-pham/<ma_sp>/sua", methods=["GET", "POST"])
    @cho_phep("ql_san_pham")
    def admin_san_pham_sua(ma_sp):
        sp = db.sanpham.find_one({"_id": ma_sp})
        if sp is None:
            abort(404)
        danh_muc = list(db.danhmuc.find({}).sort("thu_tu", 1))
        anh_co_san = _ds_anh_san_pham()
        if request.method == "POST":
            ten = request.form.get("ten_sp", "").strip()
            ma_dm = request.form.get("ma_dm", "").strip()
            gia = _so_nguyen_duong(request.form.get("don_gia", ""))
            gia_goc = _so_nguyen_khong_am(request.form.get("gia_goc", ""), mac_dinh=gia or 0)
            if not ten or not ma_dm or gia is None or gia_goc is None:
                flash("Vui lòng nhập đầy đủ tên, danh mục và đơn giá hợp lệ", "loi")
                return render_template("san_pham_form.html", sp={**sp, **request.form.to_dict()}, danh_muc=danh_muc, anh_co_san=anh_co_san, la_moi=False)

            anh = request.form.get("hinh_anh", "").strip()
            hinh_moi = [anh] + [x for x in sp.get("hinh_anh", []) if x != anh] if anh else sp.get("hinh_anh", [])
            db.sanpham.update_one(
                {"_id": ma_sp},
                {"$set": {
                    "ten_sp": ten,
                    "ma_dm": ma_dm,
                    "don_gia": gia,
                    "gia_goc": max(gia, gia_goc),
                    "bo_suu_tap": request.form.get("bo_suu_tap", sp.get("bo_suu_tap", "thuong")),
                    "form_dang": request.form.get("form_dang", "").strip(),
                    "chat_lieu": request.form.get("chat_lieu", "").strip(),
                    "mo_ta": request.form.get("mo_ta", "").strip(),
                    "hinh_anh": hinh_moi,
                }},
            )
            flash(f"Đã cập nhật sản phẩm {ma_sp}", "ok")
            return redirect(url_for("admin_san_pham"))
        return render_template("san_pham_form.html", sp=sp, danh_muc=danh_muc, anh_co_san=anh_co_san, la_moi=False)

    @app.route("/admin/san-pham/<ma_sp>/trang-thai", methods=["POST"])
    @cho_phep("ql_san_pham")
    def admin_san_pham_trang_thai(ma_sp):
        sp = db.sanpham.find_one({"_id": ma_sp}, {"hoat_dong": 1})
        if sp is None:
            abort(404)
        mo_ban = sp.get("hoat_dong") is False
        db.sanpham.update_one({"_id": ma_sp}, {"$set": {"hoat_dong": mo_ban}})
        flash(f"Sản phẩm {ma_sp} đã {'mở bán lại' if mo_ban else 'ngừng bán'}", "ok")
        return redirect(request.referrer or url_for("admin_san_pham"))

    # ---------- Admin: Khách hàng ----------

    @app.route("/admin/khach-hang")
    @cho_phep("xem_khach")
    def admin_khach_hang():
        q = request.args.get("q", "").strip()
        loc = {}
        if q:
            mau = {"$regex": re.escape(q), "$options": "i"}
            loc = {"$or": [{"ten_kh": mau}, {"_id": mau}, {"sdt": mau}]}
        tong = db.khachhang.count_documents(loc)
        trang = _trang_hien_tai()
        ds = list(
            db.khachhang.find(loc).sort("_id", 1)
            .skip((trang - 1) * SO_DONG_ADMIN).limit(SO_DONG_ADMIN)
        )
        so_don = {}
        if ds:
            gom = db.donhang.aggregate([
                {"$match": {"ma_kh": {"$in": [k["_id"] for k in ds]}, "trang_thai": {"$ne": "DA_HUY"}}},
                {"$group": {"_id": "$ma_kh", "n": {"$sum": 1}}},
            ])
            so_don = {g["_id"]: g["n"] for g in gom}
        return render_template(
            "khach_ds.html", ds=ds, q=q, so_don=so_don,
            pt=_phan_trang(tong, trang, SO_DONG_ADMIN),
        )

    @app.route("/admin/khach-hang/moi", methods=["GET", "POST"])
    @cho_phep("ql_khach")
    def admin_khach_moi():
        if request.method == "POST":
            ten = request.form.get("ten_kh", "").strip()
            sdt = request.form.get("sdt", "").strip()
            dia_chi = request.form.get("dia_chi", "").strip()
            if not ten or not re.fullmatch(r"[0-9+ ]{8,15}", sdt):
                flash("Tên không được trống và SĐT chỉ gồm 8–15 chữ số", "loi")
                return render_template("khach_form.html", kh=request.form, la_moi=True)
            doc = {"_id": ma_tiep_theo(db.khachhang, "KH", 4), "ten_kh": ten, "sdt": sdt, "dia_chi": dia_chi, "hoat_dong": True}
            db.khachhang.insert_one(doc)
            flash(f"Đã thêm khách hàng {doc['_id']}", "ok")
            return redirect(url_for("admin_khach_hang"))
        return render_template("khach_form.html", kh={}, la_moi=True)

    @app.route("/admin/khach-hang/<ma_kh>/sua", methods=["GET", "POST"])
    @cho_phep("ql_khach")
    def admin_khach_sua(ma_kh):
        kh = db.khachhang.find_one({"_id": ma_kh})
        if kh is None:
            abort(404)
        if request.method == "POST":
            ten = request.form.get("ten_kh", "").strip()
            sdt = request.form.get("sdt", "").strip()
            dia_chi = request.form.get("dia_chi", "").strip()
            if not ten or not re.fullmatch(r"[0-9+ ]{8,15}", sdt):
                flash("Tên không được trống và SĐT chỉ gồm 8–15 chữ số", "loi")
                return render_template("khach_form.html", kh={**kh, **request.form.to_dict()}, la_moi=False)
            db.khachhang.update_one({"_id": ma_kh}, {"$set": {"ten_kh": ten, "sdt": sdt, "dia_chi": dia_chi}})
            flash("Đã lưu thông tin khách hàng", "ok")
            return redirect(url_for("admin_khach_hang"))
        return render_template("khach_form.html", kh=kh, la_moi=False)

    @app.route("/admin/khach-hang/<ma_kh>/trang-thai", methods=["POST"])
    @cho_phep("ql_khach")
    def admin_khach_trang_thai(ma_kh):
        kh = db.khachhang.find_one({"_id": ma_kh}, {"hoat_dong": 1})
        if kh is None:
            abort(404)
        mo_lai = kh.get("hoat_dong") is False
        db.khachhang.update_one({"_id": ma_kh}, {"$set": {"hoat_dong": mo_lai}})
        flash(f"Khách hàng {ma_kh} đã {'hoạt động lại' if mo_lai else 'ngừng hoạt động'}", "ok")
        return redirect(request.referrer or url_for("admin_khach_hang"))

    # ---------- Admin: Kho thành phẩm (theo Màu × Size) ----------

    @app.route("/admin/kho", methods=["GET", "POST"])
    @cho_phep("xem_kho")
    def admin_kho():
        if request.method == "POST":
            if not co_quyen("kho_ghi"):
                abort(403)
            loai = request.form.get("loai", "NHAP")
            ghi_chu = request.form.get("ghi_chu", "").strip()
            dong = []
            for key, sl in zip(request.form.getlist("bien_the"), request.form.getlist("so_luong")):
                if key and sl:
                    parts = key.split("||")
                    if len(parts) == 3:
                        dong.append({"ma_sp": parts[0], "mau": parts[1], "size": parts[2], "so_luong": sl})
            try:
                phieu = services.lap_phieu_kho(
                    db,
                    ma_tiep_theo(db.phieukho, "PK", 4),
                    loai,
                    dong,
                    nguoi_lap=session.get("ten", "admin"),
                    ghi_chu=ghi_chu,
                )
                flash(f"Đã lập phiếu {phieu['_id']} ({phieu['loai']})", "ok")
                return redirect(url_for("admin_kho"))
            except NghiepVuError as loi:
                flash(str(loi), "loi")

        ds_bien_the = []
        for sp in db.sanpham.find({"hoat_dong": {"$ne": False}}, {"ten_sp": 1, "bien_the": 1}).sort("_id", 1):
            for bt in sp.get("bien_the", []):
                ds_bien_the.append({
                    "ma_sp": sp["_id"],
                    "ten_sp": sp["ten_sp"],
                    "mau": bt["mau"],
                    "size": bt["size"],
                    "ton_kho": bt["ton_kho"],
                })

        muc = request.args.get("muc", "")
        bang_ton = [b for b in ds_bien_the if b["ton_kho"] < NGUONG_TON] if muc == "canh-bao" else ds_bien_the[:60]
        loc_loai = request.args.get("loai", "")
        loc = {"loai": loc_loai} if loc_loai in ("NHAP", "XUAT") else {}
        phieu = list(db.phieukho.find(loc).sort("ngay_lap", -1).limit(30))

        return render_template(
            "kho.html",
            ds_bien_the=ds_bien_the,
            bang_ton=bang_ton,
            phieu=phieu,
            loc_loai=loc_loai,
            muc=muc,
            loai_mac_dinh="XUAT" if muc == "xuat" else "NHAP",
            so_dong=SO_DONG_KHO,
            nguong=NGUONG_TON,
        )

    # ---------- Admin: Báo cáo thống kê & CSV (CHỈ ADMIN) ----------

    @app.route("/admin/bao-cao")
    @cho_phep("bao_cao")
    def admin_bao_cao():
        theo_thang = queries.doanh_thu_theo_thang(db)
        top_sp = queries.top_san_pham(db, 5)
        mau_size = queries.ban_chay_theo_mau_size(db)[:8]
        theo_dm = queries.doanh_thu_theo_danh_muc(db)
        sap_het = queries.bien_the_sap_het(db, NGUONG_TON)
        return render_template(
            "bao_cao.html",
            theo_thang=theo_thang,
            top_sp=top_sp,
            mau_size=mau_size,
            theo_dm=theo_dm,
            sap_het=sap_het,
            nguong=NGUONG_TON,
            nhan_thang=[r["thang"] for r in theo_thang],
            gia_tri_thang=[r["doanh_thu"] for r in theo_thang],
            nhan_sp=[r["ten_sp"] or r["ma_sp"] for r in top_sp],
            gia_tri_sp=[r["doanh_thu"] for r in top_sp],
            nhan_mau=[f"{r['mau']} · {r['size']}" for r in mau_size],
            gia_tri_mau=[r["so_luong"] for r in mau_size],
        )

    @app.route("/admin/bao-cao/<ten>.csv")
    @cho_phep("bao_cao")
    def admin_xuat_csv(ten):
        bang_map = {
            "doanh-thu-theo-thang": (
                [("Tháng", "thang"), ("Số đơn", "so_don"), ("Doanh thu", "doanh_thu")],
                lambda: queries.doanh_thu_theo_thang(db),
            ),
            "top-san-pham": (
                [("Mã SP", "ma_sp"), ("Tên SP", "ten_sp"), ("Số lượng", "so_luong"), ("Doanh thu", "doanh_thu")],
                lambda: queries.top_san_pham(db, 10),
            ),
            "mau-size": (
                [("Màu", "mau"), ("Size", "size"), ("Số lượng", "so_luong")],
                lambda: queries.ban_chay_theo_mau_size(db),
            ),
            "danh-muc": (
                [("Danh mục", "ten_dm"), ("Số lượng", "so_luong"), ("Doanh thu", "doanh_thu")],
                lambda: queries.doanh_thu_theo_danh_muc(db),
            ),
            "ton-kho": (
                [("Mã SP", "ma_sp"), ("Tên SP", "ten_sp"), ("Màu", "mau"), ("Size", "size"), ("Tồn kho", "ton_kho")],
                lambda: queries.bien_the_sap_het(db, 10**9),
            ),
            "don-hang": (
                [("Mã đơn", "_id"), ("Ngày đặt", "ngay"), ("Mã KH", "ma_kh"), ("Trạng thái", "tt"), ("Tổng tiền", "tong_tien")],
                lambda: [
                    {"_id": d["_id"], "ngay": _ngay(d["ngay_dat"]), "ma_kh": d["ma_kh"],
                     "tt": TRANG_THAI_NHAN.get(d["trang_thai"], d["trang_thai"]), "tong_tien": d["tong_tien"]}
                    for d in db.donhang.find({}).sort("ngay_dat", -1)
                ],
            ),
        }
        bang = bang_map.get(ten)
        if bang is None:
            abort(404)
        cot, lay_du_lieu = bang
        buf = io.StringIO()
        ghi = csv.writer(buf)
        ghi.writerow([tieu_de for tieu_de, _ in cot])
        for dong in lay_du_lieu():
            ghi.writerow([dong.get(khoa, "") for _, khoa in cot])
        return Response(
            "\ufeff" + buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={ten}.csv"},
        )

    # ---------- Admin: Quản lý tài khoản toàn bộ 3 role (CHỈ ADMIN) ----------

    @app.route("/admin/tai-khoan")
    @cho_phep("ql_tai_khoan")
    def admin_tai_khoan():
        q = request.args.get("q", "").strip()
        vai_tro = request.args.get("vai_tro", "").strip().upper()
        trang_thai = request.args.get("trang_thai", "").strip()

        loc = {}
        if vai_tro in ("ADMIN", "NV", "KH"):
            loc["vai_tro"] = vai_tro
        if trang_thai == "khoa":
            loc["hoat_dong"] = False
        elif trang_thai == "hd":
            loc["hoat_dong"] = {"$ne": False}
        if q:
            mau = {"$regex": re.escape(q), "$options": "i"}
            loc["$or"] = [{"ten_dang_nhap": mau}, {"ho_ten": mau}, {"email": mau}, {"_id": mau}]

        tong = db.nguoidung.count_documents(loc)
        trang = _trang_hien_tai()
        ds = list(
            db.nguoidung.find(loc, {"mat_khau": 0})
            .sort([("vai_tro", 1), ("ten_dang_nhap", 1)])
            .skip((trang - 1) * SO_DONG_ADMIN)
            .limit(SO_DONG_ADMIN)
        )
        kh_map = {}
        if ds:
            ma_nds = [d["_id"] for d in ds]
            for kh in db.khachhang.find({"ma_nd": {"$in": ma_nds}}, {"ma_nd": 1, "sdt": 1, "hoat_dong": 1}):
                kh_map[kh["ma_nd"]] = kh

        dem_role = {
            "tong": db.nguoidung.count_documents({}),
            "ADMIN": db.nguoidung.count_documents({"vai_tro": "ADMIN"}),
            "NV": db.nguoidung.count_documents({"vai_tro": "NV"}),
            "KH": db.nguoidung.count_documents({"vai_tro": "KH"}),
        }
        return render_template(
            "tai_khoan_ds.html",
            ds=ds,
            kh_map=kh_map,
            dem_role=dem_role,
            vai_tro_nhan=VAI_TRO_NHAN,
            q=q,
            vai_tro=vai_tro,
            trang_thai=trang_thai,
            ma_nd_toi=session.get("ma_nd"),
            pt=_phan_trang(tong, trang, SO_DONG_ADMIN),
        )

    @app.route("/admin/tai-khoan/moi", methods=["GET", "POST"])
    @cho_phep("ql_tai_khoan")
    def admin_tai_khoan_moi():
        if request.method == "POST":
            try:
                nd = services.tao_tai_khoan(
                    db,
                    request.form.get("ten_dang_nhap", ""),
                    request.form.get("mat_khau", ""),
                    request.form.get("ho_ten", ""),
                    request.form.get("vai_tro", "NV"),
                    email=request.form.get("email", ""),
                    sdt=request.form.get("sdt", ""),
                    dia_chi=request.form.get("dia_chi", ""),
                )
            except NghiepVuError as loi:
                flash(str(loi), "loi")
                return render_template(
                    "tai_khoan_form.html",
                    nd=request.form,
                    kh=request.form,
                    vai_tro_nhan=VAI_TRO_NHAN,
                    la_moi=True,
                )
            flash(f"Đã tạo tài khoản {nd['ten_dang_nhap']} ({VAI_TRO_NHAN.get(nd['vai_tro'], nd['vai_tro'])})", "ok")
            return redirect(url_for("admin_tai_khoan"))

        return render_template(
            "tai_khoan_form.html",
            nd={"vai_tro": "NV"},
            kh={},
            vai_tro_nhan=VAI_TRO_NHAN,
            la_moi=True,
        )

    @app.route("/admin/tai-khoan/<ma_nd>/sua", methods=["GET", "POST"])
    @cho_phep("ql_tai_khoan")
    def admin_tai_khoan_sua(ma_nd):
        nd = db.nguoidung.find_one({"_id": ma_nd}, {"mat_khau": 0})
        if nd is None:
            abort(404)
        kh = db.khachhang.find_one({"ma_nd": ma_nd}) or {}

        if request.method == "POST":
            try:
                services.cap_nhat_tai_khoan(
                    db,
                    ma_nd,
                    ho_ten=request.form.get("ho_ten", ""),
                    vai_tro=request.form.get("vai_tro", nd["vai_tro"]),
                    email=request.form.get("email", ""),
                    mat_khau_moi=request.form.get("mat_khau_moi", ""),
                    ma_nd_hien_tai=session.get("ma_nd"),
                    sdt=request.form.get("sdt", ""),
                    dia_chi=request.form.get("dia_chi", ""),
                )
            except NghiepVuError as loi:
                flash(str(loi), "loi")
                return render_template(
                    "tai_khoan_form.html",
                    nd={**nd, **request.form.to_dict()},
                    kh={**kh, **request.form.to_dict()},
                    vai_tro_nhan=VAI_TRO_NHAN,
                    la_moi=False,
                    la_chinh_minh=(ma_nd == session.get("ma_nd")),
                )
            if ma_nd == session.get("ma_nd"):
                session["ho_ten"] = request.form.get("ho_ten", "").strip() or session.get("ho_ten", "")
            flash(f"Đã cập nhật tài khoản {nd['ten_dang_nhap']}", "ok")
            return redirect(url_for("admin_tai_khoan"))

        return render_template(
            "tai_khoan_form.html",
            nd=nd,
            kh=kh,
            vai_tro_nhan=VAI_TRO_NHAN,
            la_moi=False,
            la_chinh_minh=(ma_nd == session.get("ma_nd")),
        )

    @app.route("/admin/tai-khoan/<ma_nd>/trang-thai", methods=["POST"])
    @cho_phep("ql_tai_khoan")
    def admin_tai_khoan_trang_thai(ma_nd):
        try:
            mo_lai = services.doi_trang_thai_tai_khoan(db, ma_nd, ma_nd_hien_tai=session.get("ma_nd"))
            flash(f"Tài khoản {ma_nd} đã được {'mở khóa' if mo_lai else 'khóa'}", "ok")
        except NghiepVuError as loi:
            flash(str(loi), "loi")
        return redirect(request.referrer or url_for("admin_tai_khoan"))

    # ---------- Admin & Nhân viên: Hồ sơ cá nhân (ADMIN & NV) ----------

    @app.route("/admin/ho-so", methods=["GET", "POST"])
    @cho_phep("xem_admin")
    def admin_ho_so():
        ma_nd = session["ma_nd"]
        nd = db.nguoidung.find_one({"_id": ma_nd}, {"mat_khau": 0})
        if nd is None:
            abort(403)

        if request.method == "POST":
            loai_form = request.form.get("form_type", "ho_so")
            if loai_form == "mat_khau":
                try:
                    services.doi_mat_khau_ca_nhan(
                        db,
                        ma_nd,
                        request.form.get("mat_khau_cu", ""),
                        request.form.get("mat_khau_moi", ""),
                        request.form.get("xac_nhan_mat_khau", ""),
                    )
                    flash("Đã đổi mật khẩu thành công", "ok")
                    return redirect(url_for("admin_ho_so"))
                except NghiepVuError as loi:
                    flash(str(loi), "loi")
            else:
                ho_ten = request.form.get("ho_ten", "")
                email = request.form.get("email", "")
                sdt = request.form.get("sdt", "")
                try:
                    nd_moi = services.cap_nhat_ho_so_ca_nhan(
                        db,
                        ma_nd,
                        ho_ten=ho_ten,
                        email=email,
                        sdt=sdt,
                    )
                    session["ho_ten"] = nd_moi["ho_ten"]
                    flash("Đã cập nhật thông tin cá nhân", "ok")
                    return redirect(url_for("admin_ho_so"))
                except NghiepVuError as loi:
                    flash(str(loi), "loi")
                    nd = {**nd, "ho_ten": ho_ten, "email": email, "sdt": sdt}

        return render_template("ho_so.html", nd=nd, vai_tro_nhan=VAI_TRO_NHAN)

    # ---------- Admin: MongoDB Explorer thật (CHỈ ADMIN) ----------

    @app.route("/admin/mongodb")
    @cho_phep("xem_mongodb")
    def admin_mongodb():
        ten_cols = sorted(db.list_collection_names())
        thong_tin = []
        for ten in ten_cols:
            idx = list(db[ten].index_information().keys())
            thong_tin.append({"ten": ten, "so_doc": db[ten].count_documents({}), "indexes": idx})
        chon = request.args.get("col", ten_cols[0] if ten_cols else "")
        if chon not in ten_cols and ten_cols:
            chon = ten_cols[0]
        mau = db[chon].find_one() if chon else None
        indexes_chon = next((c["indexes"] for c in thong_tin if c["ten"] == chon), [])
        return render_template(
            "mongodb.html",
            db_name=db.name,
            thong_tin=thong_tin,
            tong_doc=sum(c["so_doc"] for c in thong_tin),
            chon=chon,
            indexes_chon=indexes_chon,
            mau_json=_json_dep(mau) if mau else "// Collection hiện đang trống",
        )

    return app
