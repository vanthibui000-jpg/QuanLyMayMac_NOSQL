# Hệ thống quản lý công ty may mặc (bán sỉ) — Đồ án NoSQL

## Phạm vi
- **CSDL duy nhất:** MongoDB 7 (replica set `rs0` để hỗ trợ transaction)
- **Ngôn ngữ:** Python (pymongo)
- **Không triển khai:** Neo4j, Redis, Cassandra (chỉ nêu trong thiết kế và báo cáo)

## Cấu trúc thư mục
- `docker-compose.yml` — MongoDB
- `scripts/` — script khởi tạo schema, nạp dữ liệu mẫu, truy vấn demo
- `docs/` — thiết kế, báo cáo

## Chạy môi trường
```bash
docker compose up -d
docker compose ps
```

| Dịch vụ | Cổng | Ghi chú |
|---|---|---|
| MongoDB | 27017 | replica set `rs0` |

## Cài đặt Python và chạy demo
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/01_schema.py                 # khởi tạo replica set rs0 + schema, validator, index
python scripts/02_seed.py --reset           # nạp dữ liệu mẫu (3000 đơn, 200 khách, 80 sản phẩm)
python scripts/03_queries.py                # truy vấn báo cáo + explain
pytest -q                                   # kiểm thử nghiệp vụ (CSDL riêng maymac_test)
```

### Giao diện web (Flask)

```bash
python run_web.py        # mở http://127.0.0.1:5000
```

| Trang | Chức năng | Hàm nghiệp vụ / truy vấn |
|---|---|---|
| `/don-hang/moi` | Lập đơn đặt hàng theo màu × size | `services.dat_hang` |
| `/don-hang` và `/don-hang/<ma>` | Danh sách đơn, chi tiết đơn, ghi nhận thanh toán | `services.ghi_nhan_thanh_toan` |
| `/kho` | Lập phiếu nhập/xuất kho, xem tồn | `services.lap_phieu_kho` |
| `/bao-cao` | 5 báo cáo aggregation có biểu đồ, xuất CSV qua `/bao-cao/<ten>.csv` | `queries.*` |

Mã đơn, mã thanh toán, mã phiếu được sinh tự động theo số lớn nhất hiện có trong collection.

### Chức năng bổ sung

- **Sản phẩm, khách hàng:** thêm, sửa, tìm kiếm. Không xóa cứng: dùng "Ngừng bán" hoặc "Ngừng hoạt động" để giữ lịch sử đơn. Sản phẩm/khách đã ngừng không chọn được trong form đặt hàng, và nghiệp vụ `dat_hang` cũng từ chối.
- **Đơn hàng:** lọc theo trạng thái, tìm theo mã đơn hoặc mã khách, phân trang 20 dòng. Hủy đơn chưa thanh toán bằng `services.huy_don` (đổi trạng thái sang `DA_HUY`, giữ document). Đơn đã hủy không tính vào báo cáo và công nợ.
- **Kho:** lọc phiếu nhập/xuất, xuất CSV tồn kho.
- **CSV:** `/bao-cao/don-hang.csv`, `/bao-cao/ton-kho.csv` ngoài các báo cáo cũ.

Cấu hình web qua `.env`: `FLASK_SECRET_KEY`, `FLASK_DEBUG` (xem `.env.example`).

### Giao diện và design system

- **Token màu, bo góc, đổ bóng, khoảng cách** nằm ở `:root` trong `app/static/style.css` (primary `#2563EB`, sidebar `#172554`, nền `#F5F7FB`, bo góc 12px). Đổi giao diện chỉ cần sửa token.
- **Sidebar** cố định bên trái, nhóm theo Dashboard, Kinh doanh, Quản lý kho, Phân tích, Database, Hệ thống. Menu khai báo ở `app/nav.py` (dạng dữ liệu): mục nào sáng do route Flask quyết định, mục nào hiện do quyền quyết định. Thu gọn bằng nút cuối sidebar (nhớ trạng thái); trên điện thoại là ngăn kéo có lớp phủ (đóng bằng Esc, bấm lớp phủ hoặc bấm link).
- **Topbar:** breadcrumb, tên trang, ô tìm kiếm, chuông thông báo (dữ liệu thật: nguyên vật liệu sắp hết, đơn chờ thanh toán), menu tài khoản.
- **Toast** thay cho thông báo cũ; **hộp thoại xác nhận** (thẻ `<dialog>`) thay cho `confirm()` ở các form có `data-confirm`.
- "MongoDB Explorer" và "Cài đặt" hiện mờ, nhãn "Sắp có", vì chưa có trang tương ứng.
- Icon: Bootstrap Icons 1.11.3 và font Inter tải từ CDN, cần internet; không có mạng thì chữ vẫn hiện nhưng icon trống.

### Đăng nhập và phân quyền

Mọi trang đều cần đăng nhập (trừ `/dang-nhap`). Tài khoản lấy từ collection `nguoidung`; vai trò `KH` (khách) không dùng giao diện nội bộ.

| Vai trò | Được làm |
|---|---|
| KD (Kinh doanh) | Đặt, xem, hủy đơn; thanh toán; quản lý sản phẩm và khách hàng; xem báo cáo |
| KHO (Kho) | Lập phiếu nhập/xuất, xem kho; xem sản phẩm; xem báo cáo |
| KT (Kế toán) | Xem đơn, ghi nhận thanh toán, xem kho, xem khách và sản phẩm; xem báo cáo |
| NV (Nhân viên) | Chỉ xem đơn, sản phẩm, khách hàng |

Tài khoản demo từ dữ liệu mẫu (mật khẩu chung `demo-password`, **chỉ dùng demo**): KD `nv001`, KT `nv002`, KHO `nv003`, NV `nv005`.

Bảng quyền nằm ở `app/auth.py` (`PHAN_QUYEN`); route gắn `@cho_phep("<quyền>")`. Route mới mặc định đã yêu cầu đăng nhập.

Kiểm thử: `pytest -q` (82 test: nghiệp vụ, hủy đơn, route web, đăng nhập và phân quyền, giao diện).

Cấu hình kết nối nằm trong `.env` (xem `.env.example`); mặc định là `mongodb://localhost:27017/?replicaSet=rs0`.

### Cấu trúc mã nguồn
- `app/db.py` — kết nối và khởi tạo replica set
- `app/schema.py` — collection, JSON Schema validator, index
- `app/services.py` — nghiệp vụ ghi dữ liệu, mỗi nghiệp vụ là một transaction (đặt hàng + hóa đơn, thanh toán, nhập/xuất kho)
- `app/queries.py` — aggregation báo cáo (doanh thu theo tháng, top sản phẩm, bán theo màu × size, công nợ, tồn kho)

Báo cáo chi tiết những gì đã viết: [docs/BAO_CAO_TRIEN_KHAI.md](docs/BAO_CAO_TRIEN_KHAI.md)

### Ghi chú thiết kế
- Khóa `_id` dùng mã nghiệp vụ (`KH0001`, `SP0001`, ...) thay cho `MaKH`, `MaSP` ở thiết kế SQL.
- Chi tiết đơn hàng và phiếu kho được **nhúng** vào document cha vì luôn được đọc cùng lúc, nên không cần JOIN như bảng trung gian ở 3NF.
- Tiền lưu bằng số nguyên VND thay cho `Decimal(18,2)`, vì VND không có phần thập phân.
- Phiếu xuất kho kiểm tra tồn bằng điều kiện trong `update_one`, và toàn bộ phiếu được rollback nếu một dòng thiếu hàng.

## Phân công
| Thành viên | Vai trò | Ghi chú |
|---|---|---|
| (điền) | Thiết kế CSDL & truy vấn | |
| (điền) | Ứng dụng Python & API | |
| (điền) | Kiểm thử & hiệu năng | |
| (điền) | Báo cáo & slide | |
