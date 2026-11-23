"""Truy vấn báo cáo và thống kê bằng MongoDB Aggregation Pipeline.

Mọi báo cáo doanh thu / bán chạy bỏ qua đơn đã hủy (`DA_HUY`) ngay ở stage `$match` đầu tiên.
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
            "ten_sp": {"$first": "$chi_tiet.ten_sp"},
            "so_luong": {"$sum": "$chi_tiet.so_luong"},
            "doanh_thu": {"$sum": {"$multiply": ["$chi_tiet.so_luong", "$chi_tiet.don_gia"]}},
        }},
        {"$sort": {"so_luong": -1}},
        {"$limit": n},
        {"$lookup": {"from": "sanpham", "localField": "_id", "foreignField": "_id", "as": "sp"}},
        {"$project": {
            "_id": 0,
            "ma_sp": "$_id",
            "ten_sp": {"$ifNull": [{"$arrayElemAt": ["$sp.ten_sp", 0]}, "$ten_sp"]},
            "so_luong": 1,
            "doanh_thu": 1,
        }},
    ]
    return list(db.donhang.aggregate(pipeline))


def ban_chay_theo_mau_size(db):
    """Số lượng bán theo tổ hợp Màu × Size."""
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


def doanh_thu_theo_danh_muc(db):
    """Doanh thu và số lượng bán gộp theo từng Danh mục thời trang."""
    pipeline = [
        KHONG_TINH_DON_HUY,
        {"$unwind": "$chi_tiet"},
        {"$lookup": {"from": "sanpham", "localField": "chi_tiet.ma_sp", "foreignField": "_id", "as": "sp"}},
        {"$unwind": {"path": "$sp", "preserveNullAndEmptyArrays": True}},
        {"$group": {
            "_id": "$sp.ma_dm",
            "so_luong": {"$sum": "$chi_tiet.so_luong"},
            "doanh_thu": {"$sum": {"$multiply": ["$chi_tiet.so_luong", "$chi_tiet.don_gia"]}},
        }},
        {"$lookup": {"from": "danhmuc", "localField": "_id", "foreignField": "_id", "as": "dm"}},
        {"$project": {
            "_id": 0,
            "ma_dm": "$_id",
            "ten_dm": {"$ifNull": [{"$arrayElemAt": ["$dm.ten_dm", 0]}, "Khác"]},
            "so_luong": 1,
            "doanh_thu": 1,
        }},
        {"$sort": {"doanh_thu": -1}},
    ]
    return list(db.donhang.aggregate(pipeline))


def bien_the_sap_het(db, nguong=10):
    """Danh sách các biến thể (Sản phẩm × Màu × Size) có tồn kho dưới ngưỡng."""
    pipeline = [
        {"$match": {"hoat_dong": {"$ne": False}}},
        {"$unwind": "$bien_the"},
        {"$match": {"bien_the.ton_kho": {"$lt": nguong}}},
        {"$project": {
            "_id": 0,
            "ma_sp": "$_id",
            "ten_sp": 1,
            "mau": "$bien_the.mau",
            "size": "$bien_the.size",
            "ton_kho": "$bien_the.ton_kho",
        }},
        {"$sort": {"ton_kho": 1, "ma_sp": 1}},
    ]
    return list(db.sanpham.aggregate(pipeline))


def thong_ke_trang_thai_don(db):
    pipeline = [
        {"$group": {"_id": "$trang_thai", "so_don": {"$sum": 1}, "tong_tien": {"$sum": "$tong_tien"}}},
    ]
    return {r["_id"]: r for r in db.donhang.aggregate(pipeline)}
