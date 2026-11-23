# Báo cáo triển khai code — Đồ án NoSQL (Quản lý công ty may mặc, bán sỉ)

Tài liệu này ghi lại những gì đã được viết, vì sao viết như vậy, đã kiểm chứng thế nào và còn thiếu gì.

## 1. Tổng quan

- **Đầu vào:** `README.md`, `docker-compose.yml` (MongoDB 7, replica set `rs0`) và tài liệu phân tích thiết kế HTTT (13 bảng quan hệ 3NF, kiến trúc 3 lớp, đặt hàng sỉ theo Màu × Size).
- **Hiện trạng ban đầu:** thư mục `scripts/` trống, chưa có mã Python.
- **Đã làm:** viết ~860 dòng Python gồm lớp truy cập CSDL, nghiệp vụ có transaction, báo cáo aggregation, script khởi tạo/nạp dữ liệu/truy vấn demo và bộ test.
- **Công nghệ:** Python 3 + pymongo 4.10, Faker (dữ liệu mẫu), pytest; chạy trên MongoDB 7 trong Docker.

## 2. Danh sách file đã tạo

| File | Dòng | Vai trò |
|---|---:|---|
| `requirements.txt` | 4 | Khóa phiên bản thư viện (pymongo, python-dotenv, Faker, pytest) |
| `.env.example` | 3 | Mẫu cấu hình `MONGO_URI`, `MONGO_DB` |
| `app/db.py` | 54 | Kết nối MongoDB; `ensure_replica_set()` tự khởi tạo `rs0` |
| `app/schema.py` | 126 | 11 collection, JSON Schema validator, index; `apply_schema()` chạy lại được nhiều lần |
| `app/services.py` | 166 | 3 nghiệp vụ ghi dữ liệu, mỗi nghiệp vụ trong một transaction |
| `app/queries.py` | 84 | 5 truy vấn báo cáo (aggregation) |
| `scripts/01_schema.py` | 28 | Khởi tạo replica set + schema |
| `scripts/02_seed.py` | 211 | Nạp dữ liệu mẫu quy mô lớn |
| `scripts/03_queries.py` | 66 | Chạy báo cáo + in kế hoạch thực thi (explain) |
| `tests/test_nghiep_vu.py` | 127 | 9 test nghiệp vụ và transaction |
| `docs/BAO_CAO_TRIEN_KHAI.md` | — | Báo cáo này |

`README.md` được bổ sung hướng dẫn cài đặt, chạy demo, cấu trúc mã và ghi chú thiết kế. Không sửa `docker-compose.yml`.

## 3. Thiết kế dữ liệu: từ 13 bảng SQL sang MongoDB

| Bảng SQL (thiết kế) | Collection MongoDB | Cách chuyển đổi |
|---|---|---|
| NGUOIDUNG | `nguoidung` | Giữ nguyên, `ten_dang_nhap` unique |
| KHACHHANG, NHANVIEN | `khachhang`, `nhanvien` | Tham chiếu `ma_nd` tới `nguoidung` |
| SANPHAM | `sanpham` | Thêm mảng `mau`, `size` để phục vụ bảng đặt hàng Màu × Size |
| NGUYENVATLIEU | `nguyenvatlieu` | Giữ nguyên, `so_luong_ton >= 0` do validator đảm bảo |
| DONDATHANG + CHITIETDONDATHANG | `donhang` | **Nhúng** `chi_tiet[]` (ma_sp, mau, size, so_luong, don_gia) và `tong_tien` |
| HOADON | `hoadon` | Tách riêng, `ma_don` unique (1 đơn – 1 hóa đơn) |
| THANHTOAN | `thanhtoan` | Tách riêng vì một đơn có nhiều lượt thanh toán |
| XACTHUC | `xacthuc` | Tạo collection theo thiết kế, **chưa có nghiệp vụ dùng tới** |
| PHIEUKHO + CHITIETPHIEUKHO | `phieukho` | **Nhúng** `chi_tiet[]` (ma_nvl, so_luong), thêm trường `loai` NHAP/XUAT |
| BIENBANSUCO | `bienbansuco` | Giữ nguyên, tham chiếu `ma_don` |

Các quyết định chính:

1. **`_id` là mã nghiệp vụ** (`KH0001`, `SP0001`, `DH000001`...) thay cho khóa chính `MaKH`, `MaSP`... Không dùng ObjectId để dữ liệu dễ đọc khi demo.
2. **Nhúng thay vì bảng trung gian** cho chi tiết đơn hàng và chi tiết phiếu kho, vì chúng luôn được đọc cùng document cha. Cách này loại bỏ JOIN so với mô hình 3NF.
3. **Tiền lưu bằng số nguyên VND** thay cho `Decimal(18,2)`, vì VND không có phần thập phân và tránh sai số số thực khi cộng dồn.
4. **Đơn giá được chụp lại** vào từng dòng đơn tại thời điểm đặt (đúng ý nghĩa trường `DonGia` của CHITIETDONDATHANG), nên đổi giá sản phẩm sau này không làm sai đơn cũ.
5. **Validator `$jsonSchema`** đặt ở mức collection để chặn dữ liệu sai ngay tại CSDL (thiếu trường, số lượng < 1, loại phiếu ngoài NHAP/XUAT...). `mau` và `size` trong dòng đơn cho phép `null` vì không phải đơn nào cũng phân theo màu × size.

### Index đã tạo

| Collection | Index | Mục đích |
|---|---|---|
| `nguoidung` | `ten_dang_nhap` (unique) | Đăng nhập |
| `sanpham`, `nguyenvatlieu` | `barcode` (unique, sparse) | Tra cứu mã vạch |
| `nguyenvatlieu` | `so_luong_ton` | Lọc nguyên vật liệu sắp hết |
| `donhang` | `(ma_kh, ngay_dat desc)`, `ngay_dat desc` | Đơn theo khách, báo cáo theo thời gian |
| `hoadon` | `ma_don` (unique) | 1 đơn – 1 hóa đơn |
| `thanhtoan`, `bienbansuco` | `ma_don` | `$lookup` công nợ, tra biên bản theo đơn |
| `phieukho` | `(loai, ngay_lap desc)` | Lọc phiếu nhập/xuất |

## 4. Nghiệp vụ có transaction (`app/services.py`)

Cả ba hàm chạy trong `session.with_transaction(...)`, yêu cầu replica set. Khi có lỗi nghiệp vụ (`NghiepVuError`) toàn bộ thay đổi bị hủy.

| Hàm | Làm gì | Ràng buộc kiểm tra |
|---|---|---|
| `dat_hang(db, ma_don, ma_kh, dong_hang)` | Tạo `donhang` và `hoadon` cùng lúc, tự tính `tong_tien` từ đơn giá sản phẩm | Khách và sản phẩm phải tồn tại; số lượng > 0; màu/size phải thuộc sản phẩm |
| `ghi_nhan_thanh_toan(db, ma_tt, ma_don, so_tien, phuong_thuc)` | Ghi lượt thanh toán, cập nhật trạng thái đơn `CHO_THANH_TOAN` → `THANH_TOAN_MOT_PHAN` → `DA_THANH_TOAN` | Không cho thanh toán vượt số còn nợ |
| `lap_phieu_kho(db, ma_phieu, loai, dong_hang)` | Lập phiếu nhập/xuất, cập nhật `so_luong_ton` | Xuất kho kiểm tra tồn ngay trong điều kiện `update_one` (`so_luong_ton >= số lượng`); thiếu hàng ở **bất kỳ dòng nào** thì rollback cả phiếu |

## 5. Báo cáo / truy vấn (`app/queries.py`)

| Hàm | Kỹ thuật | Ý nghĩa |
|---|---|---|
| `doanh_thu_theo_thang` | `$group` + `$dateToString` | Số đơn và doanh thu mỗi tháng |
| `top_san_pham` | `$unwind` + `$group` + `$lookup` | Sản phẩm bán chạy kèm tên |
| `ban_chay_theo_mau_size` | `$unwind` + `$group` theo (mau, size) | Khớp bảng đặt hàng Màu × Size trong thiết kế |
| `cong_no_khach_hang` | `$lookup` thanhtoan + `$addFields` + `$group` | Công nợ = đã mua − đã thanh toán |
| `nvl_sap_het` | `find` có index | Nguyên vật liệu dưới ngưỡng, phục vụ lập yêu cầu mua vật tư |

## 6. Dữ liệu mẫu (`scripts/02_seed.py`)

- Mặc định: 200 khách, 10 nhân viên, 80 sản phẩm, 40 nguyên vật liệu, 3000 đơn trải đều 365 ngày gần nhất. Có thể đổi bằng `--khach --sp --nvl --nhanvien --don --seed`.
- Mỗi đơn có 1–4 dòng, số lượng bội của 10 (đặt sỉ theo lô), kèm hóa đơn. Khoảng 60% đơn thanh toán đủ, 20% một phần, 20% chưa thanh toán; khoảng 2% có biên bản sự cố.
- Dùng `--reset` để xóa CSDL và nạp lại; nếu không có `--reset` mà CSDL đã có dữ liệu, script dừng để tránh nạp trùng.
- Cố định `--seed 42` nên kết quả lặp lại được.
- Mật khẩu người dùng mẫu là hash cố định của chuỗi demo, **chỉ dùng cho demo**.

## 7. Kiểm thử

`tests/test_nghiep_vu.py` dùng CSDL riêng `maymac_test` (tự tạo và xóa sau mỗi test), tự bỏ qua nếu MongoDB không chạy. 9 test:

1. Đặt hàng tính đúng tổng tiền và tạo hóa đơn
2. Đặt hàng sai màu: không ghi gì (rollback cả đơn và hóa đơn)
3. Đặt hàng với khách không tồn tại bị từ chối
4. Thanh toán từng phần rồi đủ: trạng thái đơn đổi đúng
5. Thanh toán vượt nợ bị từ chối, không ghi lượt thanh toán
6. Nhập kho tăng tồn
7. Xuất kho thiếu hàng ở dòng thứ hai: dòng đầu cũng được hoàn lại, không có phiếu
8. Tổng doanh thu theo tháng khớp tổng các đơn
9. Công nợ khách hàng đúng (1.000.000 − 250.000 = 750.000)

## 8. Kết quả chạy thực tế

Đã chạy trên MongoDB 7 trong Docker (container `mm_mongo`, replica set `rs0`):

| Bước | Kết quả |
|---|---|
| `01_schema.py` | Replica set sẵn sàng, tạo/cập nhật 11 collection |
| `02_seed.py --reset` | 3000 đơn, 3000 hóa đơn, 2376 lượt thanh toán, 66 biên bản sự cố, 200 khách, 80 sản phẩm, 40 nguyên vật liệu, 210 người dùng, 10 nhân viên |
| `03_queries.py` | Báo cáo chạy đúng; explain của truy vấn đơn theo khách và tồn kho đều là `FETCH -> IXSCAN` (dùng index) |
| `pytest -q` | **9 passed** |

## 9. Lỗi gặp phải và cách xử lý

Quá trình chạy thử phát hiện 3 lỗi, đã sửa hết:

1. **Khởi tạo replica set bị treo** (`ServerSelectionTimeoutError`): client thường cần có primary mới chọn được server, mà replica set chưa khởi tạo thì chưa có primary. Sửa: `ensure_replica_set()` dùng kết nối riêng với `directConnection=true`, rồi chờ node bầu primary.
2. **Validator bị MongoDB từ chối** (`Unknown $jsonSchema keyword`): đã lồng `$jsonSchema` bên trong `items` của mảng. Sửa: tách `_obj()` (schema thuần cho object lồng) và `_validator()` (bọc `$jsonSchema` ở cấp cao nhất).
3. **4 test fail do validator** (đúng chức năng của validator): dòng đơn không có màu/size lưu `null` nhưng schema yêu cầu chuỗi. Sửa: cho phép `["string", "null"]` cho `mau` và `size`.

## 10. Giới hạn và việc chưa làm

- **Giao diện web mới ở mức demo.** Flask (`app/web.py`, `run_web.py`) gọi trực tiếp các hàm nghiệp vụ và báo cáo, chưa có API JSON. Màn hình "Đặt hàng trực tuyến" trong thiết kế mục 3.3 mới là form đặt hàng nội bộ, chưa có cổng cho khách tự đặt.
- **Collection `xacthuc` chưa dùng tới**: có schema nhưng chưa có nghiệp vụ xác thực thanh toán thẻ.
- **Chưa có đăng nhập/phân quyền thật**: `nguoidung` chỉ là dữ liệu; mật khẩu mẫu không an toàn.
- **Chưa có luồng sản xuất** (kế hoạch sản xuất, KCS, chấm công) vì ngoài 13 bảng thiết kế.
- **Chưa đo hiệu năng so sánh** có/không index; mới xác nhận truy vấn dùng index qua explain.
- **Mã sinh thủ công**: người gọi phải truyền `ma_don`, `ma_tt`, `ma_phieu`; chưa có bộ sinh mã tự động.
- **Replica set một node**: đủ cho transaction khi học và demo, không phải cấu hình chịu lỗi.
- Phần "Phân công" trong `README.md` vẫn để trống cho nhóm tự điền.

## 11. Cách chạy lại

```bash
cd may-mac-nosql
docker compose up -d
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/01_schema.py
python scripts/02_seed.py --reset
python scripts/03_queries.py
pytest -q
```


## 12. Nâng cấp giao diện và nghiệp vụ (đợt 2)

- **Nghiệp vụ mới:** `services.huy_don` (hủy đơn chưa thanh toán, trong transaction). `dat_hang` và `ghi_nhan_thanh_toan` từ chối đơn/sản phẩm/khách đã ngừng. Báo cáo bỏ qua đơn `DA_HUY` ở stage `$match` đầu tiên; khi chưa có đơn hủy, kết quả không đổi.
- **Không đổi schema:** trạng thái `DA_HUY` và cờ `hoat_dong` là trường tùy ý, validator hiện có vẫn chấp nhận. Không thêm collection.
- **Giao diện:** CRUD sản phẩm và khách hàng (không xóa cứng), danh sách đơn có lọc và phân trang, hủy đơn có xác nhận, lọc phiếu kho, CSV đơn hàng và tồn kho. JavaScript tách ra `static/js/`.
- **Test:** 31 test (9 nghiệp vụ cũ, 8 hủy đơn và chặn ngừng bán, 14 route web). Fixture dùng chung ở `tests/conftest.py`.
- **Sao lưu:** trước khi sửa, dump toàn bộ `maymac` ra thư mục ngoài repo.

### Chưa làm trong đợt này
- Sinh mã an toàn khi đồng thời: vẫn dựa trên mã lớn nhất hiện có, chưa dùng bộ đếm. Rủi ro này được ghi nhận, chưa khắc phục.
- Chưa dùng Bootstrap 5: giữ CSS tự viết theo yêu cầu không đổi công nghệ.
- Chưa có icon và chế độ tối.


## 13. Đăng nhập và phân quyền (đợt 3)

- **Cơ chế:** phiên đăng nhập bằng cookie ký của Flask. `before_request` bắt buộc đăng nhập cho mọi route trừ `/dang-nhap` và file tĩnh. Mỗi route gắn thêm `@cho_phep("<quyền>")`; bảng quyền theo vai trò ở `app/auth.py`. Thiếu quyền trả 403 và menu, nút thao tác được ẩn theo quyền.
- **Vai trò:** KD, KHO, KT, NV. Vai trò KH (khách) bị chặn khỏi giao diện nội bộ.
- **Mật khẩu:** nhận cả hash của Werkzeug (tài khoản mới) và SHA-256 không muối (dữ liệu mẫu cũ). Không ghi lại hay đổi mật khẩu trong CSDL.
- **Chuyển hướng sau đăng nhập:** chỉ nhận đường dẫn nội bộ, chặn `//host` và `https://host`.
- **Không đổi schema và không tạo tài khoản mới:** dùng tài khoản có sẵn trong `nguoidung`.
- **Test:** 54 test, trong đó 23 test cho đăng nhập và phân quyền. Một test phát hiện trang tổng quan hiện nút và số liệu cho vai trò không có quyền; đã sửa.

### Hạn chế bảo mật còn lại (chưa làm)
- Form chưa có token CSRF. Hiện chỉ giảm rủi ro bằng cookie `SameSite=Lax`.
- Chưa giới hạn số lần đăng nhập sai.
- Mật khẩu mẫu dùng SHA-256 không muối và chung một chuỗi cho mọi tài khoản. Chỉ chấp nhận được cho demo.
- `FLASK_SECRET_KEY` mặc định là chuỗi cố định; phải đặt khóa riêng nếu chạy ngoài máy demo.
- Chưa có màn hình quản lý tài khoản, đổi mật khẩu, quên mật khẩu.
- Sinh mã vẫn chưa an toàn khi nhiều người ghi đồng thời.


## 14. Giai đoạn 1: design system và sidebar (đợt 4)

- **Chỉ đổi giao diện, không đổi nghiệp vụ:** `services.py`, `queries.py`, `auth.py`, `schema.py`, `db.py` không bị sửa. `web.py` chỉ thêm dữ liệu cho layout (menu, breadcrumb, thông báo, tìm kiếm) và đọc `?muc=` ở trang kho để đổi cách hiển thị.
- **Design system:** viết lại `style.css` trên token CSS. Giữ nguyên tên các class đang dùng nên 10 template trang không phải sửa.
- **Menu theo route:** `app/nav.py` khai báo menu và breadcrumb; mục active do endpoint Flask và tham số `?muc=` quyết định. Mục có `#neo` (Doanh thu, Sản phẩm bán chạy) do JavaScript sáng theo URL vì server không đọc được phần `#`.
- **Lỗi tìm thấy khi kiểm tra trên trình duyệt:** trang Báo cáo tràn ngang trên điện thoại (nội dung 539px trong màn hình 375px) do cột lưới `1fr` không co nhỏ hơn bảng bên trong. Đã sửa bằng `minmax(0, 1fr)` và `min-width: 0`, có test chặn tái phát.
- **Kiểm thử:** 82 test (28 test mới cho giao diện). Đo tràn ngang 40 phép (trang × chiều rộng 1280px và 375px), không có trang nào tràn.

### Chưa làm trong giai đoạn này
- Trang MongoDB Explorer và Cài đặt (menu hiện mờ "Sắp có").
- Tìm kiếm toàn cục thật sự: ô tìm kiếm hiện chuyển tới danh sách đơn hàng (hoặc sản phẩm nếu không có quyền xem đơn) và dùng bộ lọc `?q=` sẵn có.
- Màu chữ phụ `#64748B` trên nền `#F5F7FB` có độ tương phản khoảng 4.4:1, thấp hơn chuẩn WCAG AA (4.5:1) cho chữ nhỏ. Giữ đúng màu bạn chỉ định.
- Chưa có chế độ tối.
