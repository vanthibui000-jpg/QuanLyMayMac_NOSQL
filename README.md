# Website Bán Quần Áo Thời Trang & Quản Trị (Đồ án NoSQL MongoDB)

## Tổng quan
- **CSDL duy nhất:** MongoDB 7 (replica set `rs0` hỗ trợ multi-document transaction)
- **Backend / Web:** Python 3.12 · Flask 3.1 · PyMongo 4.10
- **Mô hình:** Website bán lẻ thời trang B2C gồm Trang chủ quảng cáo chiến dịch (`/`), Tab Sản phẩm (`/san-pham`), Tab Bộ sưu tập (`/bo-suu-tap`), Tab Thương hiệu (`/thuong-hieu`), Giỏ hàng (`/gio-hang`), Thanh toán trừ tồn kho atomic (`/thanh-toan`), Cổng tài khoản Khách hàng 2 cột (`/tai-khoan/*`) và Cổng quản trị nội bộ (`/admin/*`) phân quyền chặt chẽ **3 vai trò (`ADMIN`, `NV`, `KH`)**.

## Cấu trúc MongoDB (9 Collection)
- `nguoidung` — tài khoản đăng nhập với đúng 3 vai trò (`ADMIN`, `NV`, `KH`), hỗ trợ tự sửa hồ sơ cá nhân & đổi mật khẩu
- `khachhang` — hồ sơ khách hàng liên kết `ma_nd`, **nhúng** `so_dia_chi[]` (sổ nhiều địa chỉ nhận hàng) và `yeu_thich[]` (danh sách sản phẩm yêu thích)
- `danhmuc` — 5 danh mục thời trang (`Áo Sơ Mi`, `Suits & Blazer`, `Áo Khoác & Măng Tô`, `Quần Âu & Kaki`, `Thời Trang Nữ`)
- `sanpham` — sản phẩm kèm ảnh, giá gốc/giá bán và **mảng nhúng `bien_the[]`** (`mau`, `size`, `ton_kho`)
- `giohang` — giỏ hàng lưu trực tiếp trên MongoDB theo từng khách hàng (`items[]`)
- `donhang` — đơn hàng bán lẻ (**nhúng** `chi_tiet[]`, `giao_hang`, `lich_su[]`, trạng thái `CHO_XAC_NHAN` → `DANG_CHUAN_BI` → `DANG_GIAO` → `HOAN_THANH` / `DA_HUY`)
- `hoadon` — hóa đơn tạo đồng bộ trong cùng transaction với `donhang`
- `phieukho` — phiếu nhập/xuất kho thành phẩm (**nhúng** `chi_tiet[]` theo `ma_sp × mau × size`), cập nhật tồn kho atomic trên `sanpham.bien_the[]`
- `danhgia` — đánh giá sản phẩm xác thực (`1–5 sao`, cảm nhận phom dáng, nhận xét), chỉ cho phép khách hàng đã có đơn `HOAN_THANH` chứa sản phẩm đó

## Chạy môi trường
```bash
docker compose up -d
python -m venv .venv
pip install -r requirements.txt

python scripts/01_schema.py          # khởi tạo replica set rs0 + 9 collection, validator, index
python scripts/02_seed.py --reset    # nạp 18 sản phẩm thời trang kèm ảnh, 600 đơn mẫu, 24 phiếu kho, 45 đánh giá
python scripts/03_queries.py         # chạy 5 báo cáo aggregation + explain IXSCAN
pytest -q                            # chạy toàn bộ 37 bài kiểm thử (CSDL riêng maymac_test)
python run_web.py                    # mở http://127.0.0.1:5000
```

## Phân quyền 3 vai trò (Mật khẩu demo: `demo-password`)
| Vai trò | Tài khoản mẫu | Quyền hạn & Phạm vi |
|---|---|---|
| **`ADMIN`** (Quản trị viên) | `admin` | Toàn quyền trong `/admin`: Dashboard doanh thu, quản lý tài khoản cả 3 vai trò (`/admin/tai-khoan`), CRUD sản phẩm & khách hàng, xử lý & hủy đơn (hoàn kho), kho thành phẩm, báo cáo Aggregation + CSV, **MongoDB Explorer** và hồ sơ cá nhân (`/admin/ho-so`) |
| **`NV`** (Nhân viên) | `nv001`, `nv002` | Vận hành hằng ngày trong `/admin`: xử lý đơn hàng, xác nhận thanh toán, nhập/xuất kho thành phẩm theo `Màu × Size`, xem sản phẩm & khách hàng, tự sửa hồ sơ cá nhân (`/admin/ho-so`) *(chặn 403 hủy đơn, sửa SP/khách, quản lý tài khoản, báo cáo doanh thu)* |
| **`KH`** (Khách hàng) | `kh0001`..`kh0050` *(hoặc tự đăng ký tại `/dang-ky`)* | Mua sắm trên cửa hàng (`/` → `/san-pham` → `/gio-hang` → `/thanh-toan`); Cổng tài khoản 2 cột (`/tai-khoan/*`): hạng thành viên, lọc/tìm đơn hàng, tiến trình 4 bước, hủy đơn kèm lý do, mua lại 1 click, sổ địa chỉ, sản phẩm yêu thích, đánh giá sản phẩm đã mua, tự sửa thông tin cá nhân & đổi mật khẩu *(chặn 403 toàn bộ `/admin` và đơn của khách khác)* |
