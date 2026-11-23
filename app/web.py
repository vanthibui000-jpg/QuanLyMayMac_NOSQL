"""Giao diện web Flask cho hệ thống quản lý công ty may mặc (bán sỉ).

Mọi thao tác ghi gọi đúng một hàm nghiệp vụ trong app/services.py (một transaction MongoDB),
hoặc ghi trực tiếp một document đơn giản (sản phẩm, khách hàng) sau khi validate ở đây.
Các trang báo cáo gọi các hàm trong app/queries.py.

Không xóa cứng sản phẩm hay khách hàng: chỉ bật/tắt cờ `hoat_dong`, vì đơn cũ vẫn tham chiếu tới chúng.
"""
import csv
import io
import json
import math
import os
import re
from datetime import datetime

from flask import Flask, Response, abort, flash, redirect, render_template, request, session, url_for
from pymongo.errors import DuplicateKeyError

from app import queries, services
from app.auth import cho_phep, co_quyen, kiem_tra_mat_khau, nguoi_dung_hien_tai
from app.nav import xay_breadcrumb, xay_menu
from app.db import get_db
from app.services import NghiepVuError

APP_VERSION = "1.0.0"
SO_DONG_TOI_DA = 5
SO_DONG_MOI_TRANG = 20
NGUONG_NVL = 500  # nguyên vật liệu dưới mức này được cảnh báo

TRANG_THAI_LOP = {
    "CHO_THANH_TOAN": "cho",
    "THANH_TOAN_MOT_PHAN": "mot-phan",
    "DA_THANH_TOAN": "da",
    "DA_HUY": "huy",
}
TRANG_THAI_NHAN = {
    "CHO_THANH_TOAN": "Chờ thanh toán",
    "THANH_TOAN_MOT_PHAN": "Thanh toán một phần",
    "DA_THANH_TOAN": "Đã thanh toán",
    "DA_HUY": "Đã hủy",
}


def _so_tien(gia_tri):
    return f"{int(gia_tri):,}".replace(",", ".") + " ₫"


def _ngay(gia_tri):
    return gia_tri.strftime("%d/%m/%Y %H:%M") if isinstance(gia_tri, datetime) else gia_tri


def _ma_tiep_theo(collection, tien_to, do_dai):
    """Sinh mã tuần tự dạng TIENTO + số, ví dụ DH000001, dựa trên mã lớn nhất hiện có."""
    cuoi = collection.find({"_id": {"$regex": f"^{tien_to}"}}, {"_id": 1}).sort("_id", -1).limit(1)
    so = 0
    for doc in cuoi:
        so = int(doc["_id"][len(tien_to):])
    return f"{tien_to}{so + 1:0{do_dai}d}"


def _tach_danh_sach(chuoi):
    """'Trắng, Đen,, Trắng' -> ['Trắng', 'Đen'] (bỏ trống, bỏ trùng, giữ thứ tự)."""
    da_thay = []
    for phan in (chuoi or "").split(","):
        gia_tri = phan.strip()
        if gia_tri and gia_tri not in da_thay:
            da_thay.append(gia_tri)
    return da_thay


def _so_nguyen_duong(chuoi):
    try:
        so = int(str(chuoi).strip())
    except ValueError:
        return None
    return so if so > 0 else None


def _tuy_chon_san_pham(san_pham):
    """Dữ liệu sản phẩm cho form đặt hàng động (màu, size, đơn giá)."""
    return [
        {
            "id": sp["_id"],
            "ten": sp["ten_sp"],
            "gia": sp["don_gia"],
            "mau": sp.get("mau", []),
            "size": sp.get("size", []),
        }
        for sp in san_pham
    ]


def _json_don(don):
    """Chuyển document đơn hàng thành JSON dễ đọc để hiển thị trên trang chi tiết."""
    return json.dumps(don, ensure_ascii=False, indent=2, default=str)


def _tim_theo_ten(truong_ten, q):
    """Bộ lọc tìm kiếm không phân biệt hoa thường, an toàn với ký tự đặc biệt."""
    if not q:
        return {}
    mau = {"$regex": re.escape(q), "$options": "i"}
    return {"$or": [{truong_ten: mau}, {"_id": mau}]}


def _cac_bang_csv(db):
    """Các file CSV có thể xuất: tên file -> (cột (tiêu đề, khóa), hàm lấy dữ liệu)."""
    def don_hang():
        return [
            {
                "ma_don": d["_id"],
                "ngay_dat": _ngay(d["ngay_dat"]),
                "ma_kh": d["ma_kh"],
                "trang_thai": TRANG_THAI_NHAN.get(d["trang_thai"], d["trang_thai"]),
                "tong_tien": d["tong_tien"],
            }
            for d in db.donhang.find({}).sort("ngay_dat", -1)
        ]

    return {
        "doanh-thu-theo-thang": (
            [("Tháng", "thang"), ("Số đơn", "so_don"), ("Doanh thu", "doanh_thu")],
            lambda: queries.doanh_thu_theo_thang(db),
        ),
        "top-san-pham": (
            [("Mã SP", "ma_sp"), ("Tên SP", "ten_sp"), ("Số lượng", "so_luong"), ("Doanh thu", "doanh_thu")],
            lambda: queries.top_san_pham(db, 5),
        ),
        "mau-size": (
            [("Màu", "mau"), ("Size", "size"), ("Số lượng", "so_luong")],
            lambda: queries.ban_chay_theo_mau_size(db),
        ),
        "cong-no": (
            [("Mã KH", "ma_kh"), ("Đã mua", "tong_mua"), ("Đã trả", "da_tra"), ("Còn nợ", "cong_no")],
            lambda: queries.cong_no_khach_hang(db, 10),
        ),
        "nvl-sap-het": (
            [("Mã NVL", "_id"), ("Tên NVL", "ten_nvl"), ("Tồn kho", "so_luong_ton")],
            lambda: queries.nvl_sap_het(db, NGUONG_NVL),
        ),
        "don-hang": (
            [("Mã đơn", "ma_don"), ("Ngày đặt", "ngay_dat"), ("Mã KH", "ma_kh"),
             ("Trạng thái", "trang_thai"), ("Tổng tiền", "tong_tien")],
            don_hang,
        ),
        "ton-kho": (
            [("Mã NVL", "_id"), ("Tên NVL", "ten_nvl"), ("Tồn kho", "so_luong_ton")],
            lambda: list(db.nguyenvatlieu.find({}, {"ten_nvl": 1, "so_luong_ton": 1}).sort("_id", 1)),
        ),
    }


def create_app(db=None):
    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "demo-may-mac-nosql")  # ký cookie phiên đăng nhập
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # giảm rủi ro CSRF vì form chưa có token
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.jinja_env.filters["tien"] = _so_tien
    app.jinja_env.filters["ngay"] = _ngay
    app.jinja_env.filters["trang_thai"] = lambda ma: TRANG_THAI_NHAN.get(ma, ma)

    if db is None:
        db = get_db()
    app.config["DB"] = db

    def _trang_hien_tai():
        try:
            return max(1, int(request.args.get("trang", 1)))
        except ValueError:
            return 1

    def _phan_trang(tong, trang):
        """Thông tin phân trang cho template. Link giữ nguyên các tham số lọc đang có."""
        so_trang = max(1, math.ceil(tong / SO_DONG_MOI_TRANG))

        def link(n):
            return url_for(request.endpoint, **{**request.view_args, **request.args.to_dict(), "trang": n})

        return {
            "tong": tong,
            "trang": trang,
            "so_trang": so_trang,
            "truoc": link(trang - 1) if trang > 1 else None,
            "sau": link(trang + 1) if trang < so_trang else None,
        }

    # ---------- Đăng nhập, đăng xuất, phân quyền ----------

    def _duong_dan_an_toan(duong_dan):
        """Chỉ cho chuyển hướng tới đường dẫn nội bộ, tránh open redirect."""
        return bool(duong_dan) and duong_dan.startswith("/") and not duong_dan.startswith("//") \
            and "\\" not in duong_dan

    @app.before_request
    def yeu_cau_dang_nhap():
        # Mặc định mọi route đều cần đăng nhập, trừ trang đăng nhập và file tĩnh.
        if request.endpoint in (None, "dang_nhap", "static"):
            return None
        if "ma_nd" not in session:
            tham_so = {"next": request.full_path.rstrip("?")} if request.method == "GET" else {}
            return redirect(url_for("dang_nhap", **tham_so))
        return None

    def _thong_bao_he_thong():
        """Cảnh báo hiển thị ở chuông thông báo, tính từ dữ liệu thật và chỉ theo quyền của người dùng."""
        if "ma_nd" not in session:
            return []
        ds = []
        if co_quyen("xem_kho"):
            so_nvl = db.nguyenvatlieu.count_documents({"so_luong_ton": {"$lt": NGUONG_NVL}})
            if so_nvl:
                ds.append({"tieu_de": f"{so_nvl} nguyên vật liệu sắp hết", "mo_ta": f"Tồn kho dưới {NGUONG_NVL}",
                           "icon": "exclamation-triangle", "url": url_for("kho", muc="canh-bao")})
        if co_quyen("xem_don"):
            so_cho = db.donhang.count_documents({"trang_thai": services.TRANG_THAI_CHO_TT})
            if so_cho:
                ds.append({"tieu_de": f"{so_cho} đơn chờ thanh toán", "mo_ta": "Chưa có lượt thanh toán nào",
                           "icon": "hourglass-split",
                           "url": url_for("danh_sach_don", trang_thai=services.TRANG_THAI_CHO_TT)})
        return ds

    def _o_tim_kiem():
        """Ô tìm kiếm trên topbar gửi tới trang danh sách phù hợp với quyền (các trang đó đã hỗ trợ ?q=)."""
        if co_quyen("xem_don"):
            return {"url": url_for("danh_sach_don"), "goi_y": "Tìm mã đơn, mã khách…"}
        if co_quyen("xem_san_pham"):
            return {"url": url_for("ds_san_pham"), "goi_y": "Tìm sản phẩm…"}
        return None

    @app.context_processor
    def them_thong_tin_giao_dien():
        nd = nguoi_dung_hien_tai()
        buoc = [{"nhan": nhan, "url": url_for(ep) if ep else None}
                for nhan, ep in xay_breadcrumb(request.endpoint, request.view_args, request.args)]
        return {
            "nguoi_dung": nd,
            "co_quyen": co_quyen,
            "app_version": APP_VERSION,
            "menu": xay_menu(co_quyen, url_for, request.endpoint, request.args) if nd else [],
            "breadcrumb": buoc,
            "o_tim_kiem": _o_tim_kiem() if nd else None,
            "thong_bao_he_thong": _thong_bao_he_thong,
        }

    @app.errorhandler(403)
    def khong_co_quyen(_loi):
        return render_template("403.html"), 403

    @app.route("/dang-nhap", methods=["GET", "POST"])
    def dang_nhap():
        if "ma_nd" in session:
            return redirect(url_for("trang_chu"))
        if request.method == "POST":
            ten = request.form.get("ten_dang_nhap", "").strip().lower()
            mat_khau = request.form.get("mat_khau", "")
            nd = db.nguoidung.find_one({"ten_dang_nhap": ten}) if ten else None
            hop_le = nd is not None and kiem_tra_mat_khau(nd.get("mat_khau"), mat_khau)
            # Khách hàng (KH) không dùng giao diện nội bộ. Thông báo chung để không lộ tài khoản nào tồn tại.
            if hop_le and nd["vai_tro"] != "KH":
                session.clear()
                session["ma_nd"] = nd["_id"]
                session["ten"] = nd["ten_dang_nhap"]
                session["vai_tro"] = nd["vai_tro"]
                chuyen_toi = request.args.get("next", "")
                return redirect(chuyen_toi if _duong_dan_an_toan(chuyen_toi) else url_for("trang_chu"))
            flash("Sai tên đăng nhập hoặc mật khẩu, hoặc tài khoản không được dùng giao diện này", "loi")
        return render_template("dang_nhap.html")

    @app.route("/dang-xuat", methods=["POST"])
    def dang_xuat():
        session.clear()
        flash("Đã đăng xuất", "ok")
        return redirect(url_for("dang_nhap"))

    # ---------- Tổng quan ----------

    @app.route("/")
    @cho_phep("xem_tong_quan")
    def trang_chu():
        theo_thang = queries.doanh_thu_theo_thang(db)
        thang_moi = theo_thang[-1] if theo_thang else {"thang": "-", "doanh_thu": 0, "so_don": 0}
        top_sp = queries.top_san_pham(db, 5)
        tong_no = sum(r["cong_no"] for r in queries.cong_no_khach_hang(db, 100000))
        nvl_het = queries.nvl_sap_het(db, NGUONG_NVL)
        don_gan = list(db.donhang.find({}).sort("ngay_dat", -1).limit(5))
        return render_template(
            "trang_chu.html",
            thang_moi=thang_moi,
            so_don=db.donhang.count_documents({"trang_thai": {"$ne": "DA_HUY"}}),
            so_khach=db.khachhang.count_documents({}),
            so_sp=db.sanpham.count_documents({}),
            tong_no=tong_no,
            so_nvl_het=len(nvl_het),
            nguong=NGUONG_NVL,
            don_gan=don_gan,
            nhan_thang=[r["thang"] for r in theo_thang],
            gia_tri_thang=[r["doanh_thu"] for r in theo_thang],
            nhan_sp=[r["ten_sp"] or r["ma_sp"] for r in top_sp],
            gia_tri_sp=[r["so_luong"] for r in top_sp],
            trang_thai_lop=TRANG_THAI_LOP,
        )

    # ---------- Sản phẩm ----------

    def _doc_san_pham_tu_form(form):
        """Đọc và validate form sản phẩm. Trả về (dict dữ liệu, thông báo lỗi hoặc None)."""
        ten = form.get("ten_sp", "").strip()
        gia = _so_nguyen_duong(form.get("don_gia", ""))
        if not ten:
            return None, "Tên sản phẩm không được để trống"
        if gia is None:
            return None, "Đơn giá phải là số nguyên lớn hơn 0 (VND)"
        du_lieu = {
            "ten_sp": ten,
            "don_gia": gia,
            "mau": _tach_danh_sach(form.get("mau", "")),
            "size": _tach_danh_sach(form.get("size", "")),
            "barcode": form.get("barcode", "").strip(),
        }
        return du_lieu, None

    @app.route("/san-pham")
    @cho_phep("xem_san_pham")
    def ds_san_pham():
        q = request.args.get("q", "").strip()
        loc = _tim_theo_ten("ten_sp", q)
        tong = db.sanpham.count_documents(loc)
        trang = _trang_hien_tai()
        ds = list(db.sanpham.find(loc).sort("_id", 1)
                  .skip((trang - 1) * SO_DONG_MOI_TRANG).limit(SO_DONG_MOI_TRANG))
        return render_template("san_pham_ds.html", ds=ds, q=q, pt=_phan_trang(tong, trang))

    @app.route("/san-pham/moi", methods=["GET", "POST"])
    @cho_phep("ql_san_pham")
    def san_pham_moi():
        if request.method == "POST":
            du_lieu, loi = _doc_san_pham_tu_form(request.form)
            if loi is None:
                doc = {"_id": _ma_tiep_theo(db.sanpham, "SP", 4), **du_lieu, "hoat_dong": True}
                if not doc["barcode"]:
                    doc.pop("barcode")
                try:
                    db.sanpham.insert_one(doc)
                except DuplicateKeyError:
                    loi = "Mã vạch này đã được dùng cho sản phẩm khác"
                else:
                    flash(f"Đã thêm sản phẩm {doc['_id']}", "ok")
                    return redirect(url_for("ds_san_pham"))
            flash(loi, "loi")
            return render_template("san_pham_form.html", sp=request.form, la_moi=True)
        return render_template("san_pham_form.html", sp={}, la_moi=True)

    @app.route("/san-pham/<ma_sp>/sua", methods=["GET", "POST"])
    @cho_phep("ql_san_pham")
    def san_pham_sua(ma_sp):
        sp = db.sanpham.find_one({"_id": ma_sp})
        if sp is None:
            abort(404)
        if request.method == "POST":
            du_lieu, loi = _doc_san_pham_tu_form(request.form)
            if loi is None:
                # Đổi đơn giá chỉ ảnh hưởng đơn lập sau này, vì đơn đã chụp lại giá lúc đặt
                thay_doi = {k: v for k, v in du_lieu.items() if k != "barcode"}
                thao_tac = {"$set": thay_doi}
                if du_lieu["barcode"]:
                    thay_doi["barcode"] = du_lieu["barcode"]
                else:
                    thao_tac["$unset"] = {"barcode": ""}
                try:
                    db.sanpham.update_one({"_id": ma_sp}, thao_tac)
                except DuplicateKeyError:
                    loi = "Mã vạch này đã được dùng cho sản phẩm khác"
                else:
                    flash("Đã lưu thay đổi. Đơn giá mới chỉ áp dụng cho đơn lập sau này.", "ok")
                    return redirect(url_for("ds_san_pham"))
            flash(loi, "loi")
            return render_template("san_pham_form.html", sp={**sp, **request.form.to_dict()}, la_moi=False)
        return render_template("san_pham_form.html", sp=sp, la_moi=False)

    @app.route("/san-pham/<ma_sp>/trang-thai", methods=["POST"])
    @cho_phep("ql_san_pham")
    def san_pham_trang_thai(ma_sp):
        sp = db.sanpham.find_one({"_id": ma_sp}, {"hoat_dong": 1})
        if sp is None:
            abort(404)
        mo_ban = sp.get("hoat_dong") is False
        db.sanpham.update_one({"_id": ma_sp}, {"$set": {"hoat_dong": mo_ban}})
        flash(f"Sản phẩm {ma_sp} đã {'mở bán lại' if mo_ban else 'ngừng bán'}", "ok")
        return redirect(request.referrer or url_for("ds_san_pham"))

    # ---------- Khách hàng ----------

    def _doc_khach_tu_form(form):
        ten = form.get("ten_kh", "").strip()
        sdt = form.get("sdt", "").strip()
        if not ten:
            return None, "Tên khách hàng không được để trống"
        if not re.fullmatch(r"[0-9+ ]{8,15}", sdt):
            return None, "Số điện thoại chỉ gồm chữ số (8 đến 15 ký tự)"
        return {"ten_kh": ten, "sdt": sdt}, None

    @app.route("/khach-hang")
    @cho_phep("xem_khach")
    def ds_khach_hang():
        q = request.args.get("q", "").strip()
        loc = _tim_theo_ten("ten_kh", q)
        tong = db.khachhang.count_documents(loc)
        trang = _trang_hien_tai()
        ds = list(db.khachhang.find(loc).sort("_id", 1)
                  .skip((trang - 1) * SO_DONG_MOI_TRANG).limit(SO_DONG_MOI_TRANG))
        so_don = {}
        if ds:
            gom = db.donhang.aggregate([
                {"$match": {"ma_kh": {"$in": [k["_id"] for k in ds]}, "trang_thai": {"$ne": "DA_HUY"}}},
                {"$group": {"_id": "$ma_kh", "n": {"$sum": 1}}},
            ])
            so_don = {g["_id"]: g["n"] for g in gom}
        return render_template("khach_ds.html", ds=ds, q=q, so_don=so_don,
                               pt=_phan_trang(tong, trang))

    @app.route("/khach-hang/moi", methods=["GET", "POST"])
    @cho_phep("ql_khach")
    def khach_moi():
        if request.method == "POST":
            du_lieu, loi = _doc_khach_tu_form(request.form)
            if loi is None:
                doc = {"_id": _ma_tiep_theo(db.khachhang, "KH", 4), **du_lieu, "hoat_dong": True}
                db.khachhang.insert_one(doc)
                flash(f"Đã thêm khách hàng {doc['_id']}", "ok")
                return redirect(url_for("ds_khach_hang"))
            flash(loi, "loi")
            return render_template("khach_form.html", kh=request.form, la_moi=True)
        return render_template("khach_form.html", kh={}, la_moi=True)

    @app.route("/khach-hang/<ma_kh>/sua", methods=["GET", "POST"])
    @cho_phep("ql_khach")
    def khach_sua(ma_kh):
        kh = db.khachhang.find_one({"_id": ma_kh})
        if kh is None:
            abort(404)
        if request.method == "POST":
            du_lieu, loi = _doc_khach_tu_form(request.form)
            if loi is None:
                db.khachhang.update_one({"_id": ma_kh}, {"$set": du_lieu})
                flash("Đã lưu thay đổi khách hàng", "ok")
                return redirect(url_for("ds_khach_hang"))
            flash(loi, "loi")
            return render_template("khach_form.html", kh={**kh, **request.form.to_dict()}, la_moi=False)
        return render_template("khach_form.html", kh=kh, la_moi=False)

    @app.route("/khach-hang/<ma_kh>/trang-thai", methods=["POST"])
    @cho_phep("ql_khach")
    def khach_trang_thai(ma_kh):
        kh = db.khachhang.find_one({"_id": ma_kh}, {"hoat_dong": 1})
        if kh is None:
            abort(404)
        mo_lai = kh.get("hoat_dong") is False
        db.khachhang.update_one({"_id": ma_kh}, {"$set": {"hoat_dong": mo_lai}})
        flash(f"Khách hàng {ma_kh} đã {'hoạt động lại' if mo_lai else 'ngừng hoạt động'}", "ok")
        return redirect(request.referrer or url_for("ds_khach_hang"))

    # ---------- Đặt hàng ----------

    @app.route("/don-hang/moi", methods=["GET", "POST"])
    @cho_phep("tao_don")
    def don_hang_moi():
        khach = list(db.khachhang.find({"hoat_dong": {"$ne": False}}, {"ten_kh": 1}).sort("_id", 1))
        san_pham = list(db.sanpham.find({"hoat_dong": {"$ne": False}}).sort("_id", 1))

        if request.method == "POST":
            ma_kh = request.form.get("ma_kh", "")
            dong_hang = []
            for ma_sp, mau, size, sl in zip(
                request.form.getlist("ma_sp"),
                request.form.getlist("mau"),
                request.form.getlist("size"),
                request.form.getlist("so_luong"),
            ):
                if not ma_sp or not sl:
                    continue  # dòng trống: bỏ qua
                dong_hang.append({
                    "ma_sp": ma_sp,
                    "mau": mau or None,
                    "size": size or None,
                    "so_luong": sl,
                })
            try:
                don = services.dat_hang(
                    db, _ma_tiep_theo(db.donhang, "DH", 6), ma_kh, dong_hang
                )
            except NghiepVuError as loi:
                flash(str(loi), "loi")
                return render_template("don_hang_moi.html", khach=khach,
                                       tuy_chon_sp=_tuy_chon_san_pham(san_pham))
            flash(f"Đã tạo đơn {don['_id']}, tổng {_so_tien(don['tong_tien'])}", "ok")
            return redirect(url_for("chi_tiet_don", ma_don=don["_id"]))

        return render_template("don_hang_moi.html", khach=khach,
                               tuy_chon_sp=_tuy_chon_san_pham(san_pham))

    # ---------- Đơn hàng ----------

    @app.route("/don-hang")
    @cho_phep("xem_don")
    def danh_sach_don():
        q = request.args.get("q", "").strip()
        trang_thai = request.args.get("trang_thai", "")
        loc = {}
        if trang_thai in TRANG_THAI_NHAN:
            loc["trang_thai"] = trang_thai
        if q:
            mau = {"$regex": re.escape(q), "$options": "i"}
            loc["$or"] = [{"_id": mau}, {"ma_kh": mau}]

        tong = db.donhang.count_documents(loc)
        trang = _trang_hien_tai()
        don = list(db.donhang.find(loc).sort("ngay_dat", -1)
                   .skip((trang - 1) * SO_DONG_MOI_TRANG).limit(SO_DONG_MOI_TRANG))
        ten_kh = {k["_id"]: k["ten_kh"] for k in db.khachhang.find(
            {"_id": {"$in": list({d["ma_kh"] for d in don})}}, {"ten_kh": 1})}
        return render_template(
            "danh_sach_don.html", don=don, ten_kh=ten_kh, q=q, trang_thai=trang_thai,
            trang_thai_nhan=TRANG_THAI_NHAN, trang_thai_lop=TRANG_THAI_LOP,
            pt=_phan_trang(tong, trang),
        )

    @app.route("/don-hang/<ma_don>")
    @cho_phep("xem_don")
    def chi_tiet_don(ma_don):
        don = db.donhang.find_one({"_id": ma_don})
        if don is None:
            abort(404)
        khach = db.khachhang.find_one({"_id": don["ma_kh"]})
        hoa_don = db.hoadon.find_one({"ma_don": ma_don})
        thanh_toan = list(db.thanhtoan.find({"ma_don": ma_don}).sort("ngay_thanh_toan", 1))
        da_tra = sum(t["so_tien"] for t in thanh_toan)
        tong = don["tong_tien"]
        huy = don["trang_thai"] == services.TRANG_THAI_DA_HUY

        moc = [{"thoi_gian": don["ngay_dat"], "tieu_de": "Đặt hàng",
                "mo_ta": f"{len(don['chi_tiet'])} dòng hàng, tổng {_so_tien(tong)}"}]
        if hoa_don:
            moc.append({"thoi_gian": hoa_don["ngay_xuat"], "tieu_de": f"Hóa đơn {hoa_don['_id']}",
                        "mo_ta": _so_tien(hoa_don["tong_tien"])})
        for t in thanh_toan:
            moc.append({"thoi_gian": t["ngay_thanh_toan"], "tieu_de": f"Thanh toán {t['_id']}",
                        "mo_ta": f"{_so_tien(t['so_tien'])} · {t['phuong_thuc']}"})
        if huy:
            moc.append({"thoi_gian": None, "tieu_de": "Đơn đã bị hủy", "mo_ta": "Không tính vào báo cáo"})

        return render_template(
            "chi_tiet_don.html",
            don=don, khach=khach, hoa_don=hoa_don,
            thanh_toan=thanh_toan, da_tra=da_tra, con_no=tong - da_tra,
            phan_tram=round(da_tra * 100 / tong) if tong else 0,
            moc=moc, json_don=_json_don(don),
            lop=TRANG_THAI_LOP.get(don["trang_thai"], ""),
            huy=huy,
            co_the_huy=(don["trang_thai"] == services.TRANG_THAI_CHO_TT and da_tra == 0),
        )

    @app.route("/don-hang/<ma_don>/huy", methods=["POST"])
    @cho_phep("huy_don")
    def huy_don(ma_don):
        try:
            services.huy_don(db, ma_don)
            flash(f"Đã hủy đơn {ma_don}", "ok")
        except NghiepVuError as loi:
            flash(str(loi), "loi")
        return redirect(url_for("chi_tiet_don", ma_don=ma_don))

    # ---------- Thanh toán ----------

    @app.route("/don-hang/<ma_don>/thanh-toan", methods=["POST"])
    @cho_phep("thanh_toan")
    def thanh_toan(ma_don):
        so_tien = _so_nguyen_duong(request.form.get("so_tien", ""))
        if so_tien is None:
            flash("Số tiền thanh toán phải là số nguyên lớn hơn 0", "loi")
            return redirect(url_for("chi_tiet_don", ma_don=ma_don))

        ma_tt = _ma_tiep_theo(db.thanhtoan, "TT", 7)
        try:
            kq = services.ghi_nhan_thanh_toan(
                db, ma_tt, ma_don, so_tien, request.form.get("phuong_thuc", "TIEN_MAT")
            )
            flash(f"Đã ghi thanh toán {ma_tt}. Còn nợ {_so_tien(kq['con_no'])}", "ok")
        except NghiepVuError as loi:
            flash(str(loi), "loi")
        return redirect(url_for("chi_tiet_don", ma_don=ma_don))

    # ---------- Kho ----------

    @app.route("/kho", methods=["GET", "POST"])
    @cho_phep("xem_kho")
    def kho():
        nvl = list(db.nguyenvatlieu.find({}, {"ten_nvl": 1, "so_luong_ton": 1}).sort("_id", 1))

        if request.method == "POST":
            if not co_quyen("kho_ghi"):
                abort(403)
            loai = request.form.get("loai", "NHAP")
            dong = []
            for ma_nvl, sl in zip(request.form.getlist("ma_nvl"), request.form.getlist("so_luong")):
                if ma_nvl and sl:
                    dong.append({"ma_nvl": ma_nvl, "so_luong": sl})
            try:
                phieu = services.lap_phieu_kho(
                    db, _ma_tiep_theo(db.phieukho, "PK", 4), loai, dong
                )
                flash(f"Đã lập phiếu {phieu['_id']} ({phieu['loai']})", "ok")
                return redirect(url_for("kho"))
            except NghiepVuError as loi:
                flash(str(loi), "loi")

        loc_loai = request.args.get("loai", "")
        loc = {"loai": loc_loai} if loc_loai in ("NHAP", "XUAT") else {}
        phieu = list(db.phieukho.find(loc).sort("ngay_lap", -1).limit(30))

        # ?muc= do menu sidebar truyền vào: chỉ đổi cách hiển thị, không đổi nghiệp vụ
        muc = request.args.get("muc", "")
        nvl_bang = [v for v in nvl if v["so_luong_ton"] < NGUONG_NVL] if muc == "canh-bao" else nvl
        return render_template("kho.html", nvl=nvl, nvl_bang=nvl_bang, phieu=phieu, loc_loai=loc_loai,
                               muc=muc, loai_mac_dinh="XUAT" if muc == "xuat" else "NHAP",
                               so_dong=SO_DONG_TOI_DA, nguong=NGUONG_NVL)

    # ---------- Báo cáo ----------

    @app.route("/bao-cao")
    @cho_phep("bao_cao")
    def bao_cao():
        theo_thang = queries.doanh_thu_theo_thang(db)
        top_sp = queries.top_san_pham(db, 5)
        mau_size = queries.ban_chay_theo_mau_size(db)[:8]
        cong_no = queries.cong_no_khach_hang(db, 10)
        nvl_het = queries.nvl_sap_het(db, NGUONG_NVL)
        return render_template(
            "bao_cao.html",
            theo_thang=theo_thang,
            top_sp=top_sp,
            mau_size=mau_size,
            cong_no=cong_no,
            nvl_het=nvl_het,
            nguong=NGUONG_NVL,
            nhan_thang=[r["thang"] for r in theo_thang],
            gia_tri_thang=[r["doanh_thu"] for r in theo_thang],
            nhan_sp=[r["ten_sp"] or r["ma_sp"] for r in top_sp],
            gia_tri_sp=[r["doanh_thu"] for r in top_sp],
            nhan_mau=[f"{r['mau'] or '—'} · {r['size'] or '—'}" for r in mau_size],
            gia_tri_mau=[r["so_luong"] for r in mau_size],
            nhan_no=[r["ma_kh"] for r in cong_no],
            gia_tri_no=[r["cong_no"] for r in cong_no],
        )

    @app.route("/bao-cao/<ten>.csv")
    @cho_phep("bao_cao")
    def xuat_csv(ten):
        bang = _cac_bang_csv(db).get(ten)
        if bang is None:
            abort(404)
        cot, lay_du_lieu = bang
        buf = io.StringIO()
        ghi = csv.writer(buf)
        ghi.writerow([tieu_de for tieu_de, _ in cot])
        for dong in lay_du_lieu():
            ghi.writerow([dong.get(khoa, "") for _, khoa in cot])
        # BOM để Excel mở đúng tiếng Việt
        return Response(
            "﻿" + buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={ten}.csv"},
        )

    return app
