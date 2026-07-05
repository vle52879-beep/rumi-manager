# RUMI Manager 6.4.2 — Admin Control

Bản nâng cấp từ 6.4.1, tập trung vào quản trị thông báo, lịch sử kho, giới hạn giờ tuần và đổi nhân viên cho ca đã xếp.

## Tính năng mới

### 1. Quản lý thông báo
- Hiển thị toàn bộ thông báo, không còn giới hạn 100 mục.
- Admin chọn từng thông báo hoặc chọn tất cả thông báo đang hiển thị.
- Xóa nhiều thông báo cùng lúc.
- Đánh dấu tất cả đã đọc vẫn áp dụng cho toàn bộ lịch sử.

### 2. Xóa lịch sử lấy nguyên liệu
- Admin chọn nhiều dòng lịch sử rồi xóa khỏi giao diện.
- Đây là xóa mềm: không cộng lại số lượng tồn kho.
- Lý do xóa và người thực hiện được lưu trong nhật ký quản trị.

### 3. Giới hạn 56 giờ/tuần
- Trần hệ thống là 56 giờ/tuần cho mọi nhân viên.
- Admin có thể đặt giới hạn thấp hơn cho từng người.
- Đơn đăng ký tuần và thao tác duyệt ca đều bị chặn nếu vượt giới hạn.
- Nhân viên cũ đang để mặc định 48 giờ sẽ được nâng lên 56 giờ sau migration.

### 4. Đổi nhân viên cho lịch đã xếp
- Admin bấm **Đổi nhân viên** ngay trên ca chính thức.
- Chỉ chọn được người đã đăng ký đúng ngày, đúng giờ và đúng ca đó.
- Hỗ trợ người đang Chờ duyệt, Danh sách chờ hoặc đã bị Từ chối nhưng chưa rút đơn.
- Hệ thống vẫn kiểm tra trùng lịch, nghỉ phép, ngày nghỉ, giờ ngày và 56 giờ/tuần.
- Không cho đổi nếu ca đã có chấm công.
- Kết quả đơn của người cũ và người mới được cập nhật tự động.
- Lịch sử đổi ca được lưu riêng.

## Cài đặt

1. Chạy `sql/SUPABASE_RUMI_V6_4_2_ADMIN_CONTROL.sql` trong Supabase SQL Editor.
2. Đẩy mã nguồn lên Vercel.
3. Mở `/api/health` và kiểm tra phiên bản `6.4.2`.

Đọc thêm `UPGRADE_V642.md` và `DEPLOY_VERCEL.md`.
