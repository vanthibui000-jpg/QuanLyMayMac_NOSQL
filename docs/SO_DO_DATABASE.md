# Sơ đồ cơ sở dữ liệu MongoDB — Hệ thống quản lý công ty may mặc (bán sỉ)

Nguồn: [app/schema.py](../app/schema.py). CSDL `maymac`, 11 collection. Dán khối Mermaid vào bất kỳ trình xem Markdown hỗ trợ Mermaid (GitHub, VS Code + extension, mermaid.live) để xem sơ đồ.

## 1. Sơ đồ quan hệ (ER)

- `PK` là `_id` (mã nghiệp vụ dạng chuỗi), `FK` là tham chiếu bằng mã tới collection khác.
- Hai thực thể có hậu tố `_chi_tiet` **không phải collection riêng**: chúng là mảng được **nhúng** trong document cha.

```mermaid
erDiagram
    nguoidung ||--o| khachhang : "ma_nd"
    nguoidung ||--o| nhanvien : "ma_nd"
    khachhang ||--o{ donhang : "ma_kh"
    donhang ||--|| hoadon : "ma_don"
    donhang ||--o{ thanhtoan : "ma_don"
    donhang ||--o{ bienbansuco : "ma_don"
    donhang ||--|{ donhang_chi_tiet : "nhung"
    sanpham ||--o{ donhang_chi_tiet : "ma_sp"
    phieukho ||--|{ phieukho_chi_tiet : "nhung"
    nguyenvatlieu ||--o{ phieukho_chi_tiet : "ma_nvl"

    nguoidung {
        string _id PK "ND-KH0001, ND-NV001"
        string ten_dang_nhap UK
        string mat_khau
        string vai_tro "KH, KD, KHO, KT, NV"
    }
    khachhang {
        string _id PK "KH0001"
        string ten_kh
        string sdt
        string ma_nd FK
    }
    nhanvien {
        string _id PK "NV001"
        string ten_nv
        string chuc_vu
        string ma_nd FK
    }
    sanpham {
        string _id PK "SP0001"
        string ten_sp
        number don_gia "VND"
        string barcode UK
        array mau
        array size
    }
    nguyenvatlieu {
        string _id PK "NVL0001"
        string ten_nvl
        number so_luong_ton "khong am"
        string barcode UK
    }
    donhang {
        string _id PK "DH000001"
        date ngay_dat
        string trang_thai "CHO_THANH_TOAN, THANH_TOAN_MOT_PHAN, DA_THANH_TOAN"
        string ma_kh FK
        number tong_tien "VND"
        array chi_tiet "nhung"
    }
    donhang_chi_tiet {
        string ma_sp FK
        string mau "co the null"
        string size "co the null"
        number so_luong "min 1"
        number don_gia "chup tai luc dat"
    }
    hoadon {
        string _id PK "HDDH000001"
        date ngay_xuat
        number tong_tien
        string ma_don FK "unique"
    }
    thanhtoan {
        string _id PK "TT0000001"
        date ngay_thanh_toan
        number so_tien "min 1"
        string phuong_thuc "TIEN_MAT, CHUYEN_KHOAN"
        string ma_don FK
    }
    xacthuc {
        string _id PK
        string trang_thai "chua co nghiep vu dung"
    }
    phieukho {
        string _id PK "PK0001"
        string loai "NHAP hoac XUAT"
        date ngay_lap
        array chi_tiet "nhung"
    }
    phieukho_chi_tiet {
        string ma_nvl FK
        number so_luong "min 1"
    }
    bienbansuco {
        string _id PK "BB000001"
        date ngay_lap
        string ly_do
        string ma_don FK
    }
```

## 2. Ví dụ document thực tế

`donhang` (chi tiết nhúng, đơn giá chụp lại tại thời điểm đặt):

```json
{
  "_id": "DH000001",
  "ngay_dat": "2026-05-12T08:30:00Z",
  "trang_thai": "THANH_TOAN_MOT_PHAN",
  "ma_kh": "KH0042",
  "tong_tien": 21500000,
  "chi_tiet": [
    { "ma_sp": "SP0018", "mau": "Đen", "size": "L",  "so_luong": 100, "don_gia": 145000 },
    { "ma_sp": "SP0032", "mau": "Be",  "size": "XL", "so_luong": 50,  "don_gia": 140000 }
  ]
}
```

`phieukho` (xuất kho nguyên vật liệu):

```json
{
  "_id": "PK0001",
  "loai": "XUAT",
  "ngay_lap": "2026-05-13T02:00:00Z",
  "chi_tiet": [
    { "ma_nvl": "NVL0001", "so_luong": 200 },
    { "ma_nvl": "NVL0007", "so_luong": 50 }
  ]
}
```

## 3. Nhúng hay tham chiếu

| Quan hệ | Cách lưu | Lý do |
|---|---|---|
| Đơn hàng – dòng chi tiết | **Nhúng** | Luôn đọc cùng đơn; số dòng nhỏ (1–4 dòng mỗi đơn mẫu); ghi đơn là một thao tác nguyên tử |
| Phiếu kho – dòng chi tiết | **Nhúng** | Giống đơn hàng |
| Đơn hàng – hóa đơn | Tham chiếu (`ma_don` unique) | Hóa đơn là chứng từ độc lập, có vòng đời riêng |
| Đơn hàng – thanh toán | Tham chiếu | Một đơn có nhiều lượt thanh toán, số lượng không giới hạn trước |
| Đơn hàng – biên bản sự cố | Tham chiếu | Chỉ phát sinh ở một số ít đơn |
| Đơn hàng – khách hàng, sản phẩm | Tham chiếu | Dữ liệu dùng chung, thay đổi độc lập |
| Người dùng – khách hàng/nhân viên | Tham chiếu | Tách tài khoản khỏi hồ sơ |

## 4. Chỉ mục

| Collection | Index |
|---|---|
| `nguoidung` | `ten_dang_nhap` (unique) |
| `khachhang` | `ma_nd` (sparse) |
| `sanpham` | `barcode` (unique, sparse) |
| `nguyenvatlieu` | `barcode` (unique, sparse), `so_luong_ton` |
| `donhang` | `(ma_kh, ngay_dat desc)`, `ngay_dat desc` |
| `hoadon` | `ma_don` (unique) |
| `thanhtoan` | `ma_don` |
| `phieukho` | `(loai, ngay_lap desc)` |
| `bienbansuco` | `ma_don` |
