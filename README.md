# RUMI Manager 6.2 — Attendance Alerts & Payroll PDF

Bản quản lý nhân viên quán trà sữa chạy trên Vercel + Supabase, gồm đăng nhập/phân quyền, đăng ca và duyệt đơn, lịch Full-time/Part-time, chấm công GPS, bảng công, bảng lương tháng, xuất Excel/PDF, kho nguyên liệu và bảo mật tài khoản.

## Điểm mới của 6.2

### Cảnh báo chấm công theo thời gian

- `Sắp đến ca`: chưa mở cửa sổ chấm công.
- `Có thể chấm vào`: từ 15 phút trước ca.
- `Đến giờ chấm công`: đã tới giờ bắt đầu nhưng chưa chấm vào.
- `Đi trễ chưa chấm`: quá ngưỡng cảnh báo và hệ thống đếm số phút trễ.
- `Nguy cơ vắng ca`: quá 30 phút chưa chấm vào; admin được cảnh báo.
- `Vắng ca`: ca đã kết thúc mà không có chấm công vào.
- `Đến giờ chấm ra` / `Thiếu giờ ra`: đã chấm vào nhưng chưa hoàn tất ca.

Hệ thống đồng bộ cảnh báo khi admin/nhân viên đang mở web, gửi thông báo, hiển thị tại Dashboard và trang Bảng công. Admin có thể nhắc nhân viên, đóng cảnh báo hoặc xác nhận vắng ca.

### Chấm vào muộn hợp lý

- Sau cửa sổ chấm công thông thường, nhân viên vẫn có thể chấm vào khi ca còn diễn ra.
- Chấm vào muộn được ghi số phút trễ và mức rủi ro.
- Chấm sau ngưỡng nguy cơ vắng được đánh dấu `Cao` và chuyển sang chờ admin duyệt.
- Sau khi ca kết thúc, nhân viên phải gửi yêu cầu sửa công.

### Xuất bảng lương PDF

- Xuất **phiếu lương từng nhân viên** khổ A4 dọc.
- Xuất **bảng lương toàn bộ nhân viên** khổ A4 ngang.
- Hiển thị ca theo lịch, ca hoàn thành, giờ thực tế, giờ tính lương, vắng ca, thiếu chấm công, thưởng/phạt/tạm ứng và thực nhận.
- Bảng chưa chốt có watermark `TẠM TÍNH` / `BẢN NHÁP`.
- Loại bỏ `onclick` nội tuyến, khắc phục lỗi Content Security Policy khi bấm in.
- Khi hộp thoại in mở, chọn **Save as PDF / Lưu dưới dạng PDF**.

## Nâng cấp Supabase

Chạy file sau trong Supabase SQL Editor:

```text
sql/SUPABASE_RUMI_V6_2_ATTENDANCE_ALERTS.sql
```

Migration chỉ tạo/sửa đối tượng `rumi_*`, không đụng dữ liệu IC3 Smart Class.

## Chạy local

Tạo `.env` theo `.env.example`, sau đó:

```bash
python3 server.py
```

Mở `http://localhost:8000`.

## Deploy Vercel

Xem [UPGRADE_V62.md](UPGRADE_V62.md) và [DEPLOY_VERCEL.md](DEPLOY_VERCEL.md).

## Bảo mật

- Chỉ đặt Secret/service-role key trong Vercel Environment Variables hoặc `.env` phía server.
- Không đưa Secret key vào frontend, GitHub hoặc biến `VITE_*`.
