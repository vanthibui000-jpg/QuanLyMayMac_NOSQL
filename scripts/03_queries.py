"""Bước 3: chạy 5 báo cáo aggregation và in kế hoạch thực thi (explain) chứng minh dùng index."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import queries  # noqa: E402
from app.db import get_client, get_db  # noqa: E402


def _cac_stage(node, ket=None):
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


def main():
    db = get_db(get_client())
    if db.donhang.estimated_document_count() == 0:
        sys.exit("CSDL chưa có dữ liệu. Chạy scripts/02_seed.py --reset trước.")

    print("\n== Doanh thu theo tháng")
    for row in queries.doanh_thu_theo_thang(db):
        print(f"  {row['thang']}  đơn={row['so_don']:>4}  doanh thu={row['doanh_thu']:>14,} VND")

    print("\n== Top 5 sản phẩm bán chạy")
    for row in queries.top_san_pham(db, 5):
        print(f"  {row['ma_sp']}  {row['ten_sp']:<38} SL={row['so_luong']:>4}  DT={row['doanh_thu']:>14,}")

    print("\n== Doanh thu theo danh mục")
    for row in queries.doanh_thu_theo_danh_muc(db):
        print(f"  {row['ten_dm']:<25} SL={row['so_luong']:>4}  DT={row['doanh_thu']:>14,}")

    print("\n== Top 8 Màu × Size bán chạy")
    for row in queries.ban_chay_theo_mau_size(db)[:8]:
        print(f"  {row['mau']:<12} {row['size']:<4} SL={row['so_luong']}")

    print("\n== Biến thể tồn kho < 10")
    for row in queries.bien_the_sap_het(db, 10)[:10]:
        print(f"  {row['ma_sp']}  {row['ten_sp']:<34} {row['mau']}/{row['size']}  tồn={row['ton_kho']}")

    print("\n== Kế hoạch thực thi (explain)")
    plan1 = db.donhang.find({"ma_kh": "KH0001"}).sort("ngay_dat", -1).explain()
    print("  Đơn của KH0001:", " -> ".join(_cac_stage(plan1["queryPlanner"]["winningPlan"])))
    plan2 = db.sanpham.find({"ma_dm": "DM01", "hoat_dong": True}).explain()
    print("  Lọc SP theo danh mục:", " -> ".join(_cac_stage(plan2["queryPlanner"]["winningPlan"])))


if __name__ == "__main__":
    main()
