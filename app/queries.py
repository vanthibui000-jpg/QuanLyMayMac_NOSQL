"""Truy vấn báo cáo và thống kê (aggregation pipeline).

Mọi báo cáo bỏ qua đơn đã hủy (trang_thai = DA_HUY) ở stage $match đầu tiên.
Nếu chưa có đơn hủy nào thì kết quả không đổi so với trước.
"""

KHONG_TINH_DON_HUY = {"$match": {"trang_thai": {"$ne": "DA_HUY"}}}


def doanh_thu_theo_thang(db):
    pipeline = [
        KHONG_TINH_DON_HUY,
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m", "date": "$ngay_dat"}},
            "so_don": {"$sum": 1},
            "doanh_thu": {"$sum": "$tong_tien"},
        }},
        {"$sort": {"_id": 1}},
        {"$project": {"_id": 0, "thang": "$_id", "so_don": 1, "doanh_thu": 1}},
    ]
    return list(db.donhang.aggregate(pipeline))


def top_san_pham(db, n=5):
    pipeline = [
        KHONG_TINH_DON_HUY,
        {"$unwind": "$chi_tiet"},
        {"$group": {
            "_id": "$chi_tiet.ma_sp",
            "so_luong": {"$sum": "$chi_tiet.so_luong"},
            "doanh_thu": {"$sum": {"$multiply": ["$chi_tiet.so_luong", "$chi_tiet.don_gia"]}},
        }},
        {"$sort": {"so_luong": -1}},
        {"$limit": n},
        {"$lookup": {"from": "sanpham", "localField": "_id", "foreignField": "_id", "as": "sp"}},
        {"$project": {
            "_id": 0,
            "ma_sp": "$_id",
            "ten_sp": {"$arrayElemAt": ["$sp.ten_sp", 0]},
            "so_luong": 1,
            "doanh_thu": 1,
        }},
    ]
    return list(db.donhang.aggregate(pipeline))


def ban_chay_theo_mau_size(db):
    """Số lượng bán theo tổ hợp Màu × Size (đúng bảng đặt hàng trong thiết kế)."""
    pipeline = [
        KHONG_TINH_DON_HUY,
        {"$unwind": "$chi_tiet"},
        {"$group": {
            "_id": {"mau": "$chi_tiet.mau", "size": "$chi_tiet.size"},
            "so_luong": {"$sum": "$chi_tiet.so_luong"},
        }},
        {"$sort": {"so_luong": -1}},
        {"$project": {"_id": 0, "mau": "$_id.mau", "size": "$_id.size", "so_luong": 1}},
    ]
    return list(db.donhang.aggregate(pipeline))


def cong_no_khach_hang(db, limit=10):
    """Công nợ = tổng tiền đã mua - tổng tiền đã thanh toán, theo từng khách hàng."""
    pipeline = [
        KHONG_TINH_DON_HUY,
        {"$lookup": {"from": "thanhtoan", "localField": "_id", "foreignField": "ma_don", "as": "tt"}},
        {"$addFields": {"da_tra": {"$sum": "$tt.so_tien"}}},
        {"$group": {
            "_id": "$ma_kh",
            "tong_mua": {"$sum": "$tong_tien"},
            "da_tra": {"$sum": "$da_tra"},
        }},
        {"$project": {
            "_id": 0,
            "ma_kh": "$_id",
            "tong_mua": 1,
            "da_tra": 1,
            "cong_no": {"$subtract": ["$tong_mua", "$da_tra"]},
        }},
        {"$match": {"cong_no": {"$gt": 0}}},
        {"$sort": {"cong_no": -1}},
        {"$limit": limit},
    ]
    return list(db.donhang.aggregate(pipeline))


def nvl_sap_het(db, nguong=500):
    """Nguyên vật liệu có tồn kho dưới ngưỡng, dùng để lập yêu cầu mua vật tư."""
    return list(
        db.nguyenvatlieu.find(
            {"so_luong_ton": {"$lt": nguong}},
            {"_id": 1, "ten_nvl": 1, "so_luong_ton": 1},
        ).sort("so_luong_ton", 1)
    )
