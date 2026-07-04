# RUMI Manager 5.4 SHIFT MARKET

Bản quản lý nhân viên quán trà sữa dùng chung Supabase với IC3 Smart Class nhưng chỉ sử dụng bảng `rumi_*`.

## Tính năng chính

- Admin đăng nhu cầu ca làm theo ngày, giờ, cửa hàng, vị trí và số người cần.
- Nhân viên Full-time/Part-time đăng ký ca đang mở.
- Admin duyệt, đưa vào danh sách chờ hoặc từ chối từng đơn.
- Khi duyệt đơn, hệ thống tự tạo ca chính thức và gửi thông báo.
- Khi chốt ca, hệ thống từ chối các đơn còn lại.
- Full-time đăng ký ngày nghỉ ưu tiên; admin duyệt và xếp tự động các ngày còn lại.
- Chặn trùng ca, nghỉ phép, ngày nghỉ tuần, quá giờ/ngày, quá giờ/tuần và quá số ngày làm liên tiếp.
- Cảnh báo Full-time thiếu giờ, làm quá 6 ngày hoặc chưa có ngày nghỉ.
- Chấm công GPS, bảng công, bảng lương tháng và xuất Excel lịch tuần giữ nguyên.

Xem hướng dẫn triển khai trong [UPGRADE_V54.md](UPGRADE_V54.md).
