"""Bước 3: chạy các truy vấn demo và in kế hoạch thực thi (explain) để chứng minh dùng index.

Chạy: python scripts/03_queries.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import queries  # noqa: E402
from app.db import get_client, get_db  # noqa: E402


def _cac_stage(node, ket=None):
    """Thu thập tên các stage trong cây kế hoạch (IXSCAN, COLLSCAN, FETCH, ...)."""
    ket = [] if ket is None else ket
    if isinstance(node, dict):
        if "stage" in node:
            ket.append(node["stage"])
        for v in node.values():
            _cac_stage(v, ket)
    elif isinstance(node, list):
        for v in node:
            _cac_stage(v, ket)
    return ket


def in_tieu_de(tieu_de):
    print(f"\n== {tieu_de}")


def main():
    db = get_db(get_client())
    if db.donhang.estimated_document_count() == 0:
        sys.exit("CSDL chưa có dữ liệu. Chạy scripts/02_seed.py trước.")

    in_tieu_de("Doanh thu theo tháng")
    for row in queries.doanh_thu_theo_thang(db):
        print(f"  {row['thang']}  đơn={row['so_don']:>5}  doanh thu={row['doanh_thu']:>15,} VND")

    in_tieu_de("Top 5 sản phẩm bán chạy")
    for row in queries.top_san_pham(db, 5):
        print(f"  {row['ma_sp']}  {row['ten_sp']:<40} SL={row['so_luong']:>6}  DT={row['doanh_thu']:>15,}")

    in_tieu_de("Top 8 tổ hợp Màu × Size bán chạy")
    for row in queries.ban_chay_theo_mau_size(db)[:8]:
        print(f"  {row['mau']:<12} {row['size']:<4} SL={row['so_luong']}")

    in_tieu_de("Top 10 khách hàng còn nợ")
    for row in queries.cong_no_khach_hang(db, 10):
        print(f"  {row['ma_kh']}  đã mua={row['tong_mua']:>15,}  đã trả={row['da_tra']:>15,}  nợ={row['cong_no']:>15,}")

    in_tieu_de("Nguyên vật liệu dưới 500 đơn vị")
    for row in queries.nvl_sap_het(db, 500):
        print(f"  {row['_id']}  {row['ten_nvl']:<35} tồn={row['so_luong_ton']}")

    in_tieu_de("Kế hoạch thực thi (explain)")
    ma_kh = db.khachhang.find_one()["_id"]
    plan = db.donhang.find({"ma_kh": ma_kh}).sort("ngay_dat", -1).explain()
    print(f"  Đơn của {ma_kh}: {' -> '.join(_cac_stage(plan['queryPlanner']['winningPlan']))}")
    plan = db.nguyenvatlieu.find({"so_luong_ton": {"$lt": 500}}).explain()
    print(f"  Tồn kho < 500: {' -> '.join(_cac_stage(plan['queryPlanner']['winningPlan']))}")


if __name__ == "__main__":
    main()
