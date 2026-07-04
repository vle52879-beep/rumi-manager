# RUMI Manager 5.5 — Security & Smart Attendance

Bản nâng cấp bảo mật tài khoản và chấm công logic cho RUMI Manager. Hệ thống vẫn dùng chung Supabase của IC3 Smart Class nhưng chỉ tạo/sửa bảng và hàm có tiền tố `rumi_`.

## Bảo mật tài khoản

- Mật khẩu PBKDF2-HMAC-SHA256 600.000 vòng, salt riêng và pepper phía backend tùy chọn.
- Nhân viên dùng mật khẩu tạm do admin cấp và bắt buộc đổi ở lần đăng nhập đầu.
- Kiểm tra độ mạnh, chặn mật khẩu phổ biến, tên đăng nhập và 5 mật khẩu gần nhất.
- Khóa đăng nhập 15 phút sau 5 lần sai; 60 phút sau 10 lần sai.
- Phiên đăng nhập ngẫu nhiên lưu dạng hash trong CSDL, cookie `HttpOnly`, `Secure`, `SameSite=Strict`.
- Tự hết phiên sau 2 giờ không hoạt động hoặc 12 giờ tuyệt đối.
- Trang quản lý thiết bị đăng nhập, thu hồi từng thiết bị hoặc đăng xuất tất cả.
- Đổi/reset mật khẩu sẽ thu hồi các phiên cũ.
- CSRF/origin protection, CSP, HSTS và các security header.

## Chấm công thông minh

- Lấy nhiều mẫu GPS và chọn mẫu có sai số tốt nhất.
- GPS phải mới, đủ chính xác, đúng bán kính cửa hàng và đúng khung giờ ca.
- Giờ máy chủ là nguồn thời gian chuẩn; đổi giờ trên điện thoại không ảnh hưởng.
- Phát hiện thiết bị vừa chấm công cho nhiều tài khoản và đánh dấu rủi ro.
- Vào sớm không cộng thêm lương; đi trễ/về sớm tính theo phút thực tế.
- Phút sau giờ kết thúc là tăng ca chờ admin duyệt, chưa duyệt không cộng lương.
- Nhân viên gửi yêu cầu sửa chấm công; admin duyệt hoặc từ chối.
- Bảng công, bảng lương tháng và xuất Excel tiếp tục dùng `payable_hours` đã duyệt.

## Nâng cấp

Đọc [UPGRADE_V55.md](UPGRADE_V55.md).
