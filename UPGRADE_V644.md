# RUMI v6.4.4 – Attendance risk hotfix

Bản này sửa lỗi duyệt lượt công rủi ro trong trang **Chấm công & bảng công**.

## Đã sửa

- Nút **Xác nhận / Loại công** không còn báo `POST /api/attendance/risk/review 404` khi ca chưa có bản ghi chấm công thật.
- Lượt ca chưa chấm công được gửi kèm `shift_id`; máy chủ tự tạo bản ghi 0 giờ để lưu quyết định của admin và không hiện lại trong danh sách rủi ro chờ duyệt.
- Danh sách **Lượt công rủi ro** chỉ hiển thị lượt còn `Chờ duyệt`, không hiện lại lượt đã xử lý.
- Endpoint `/api/notifications/unread-count` không còn trả 401 ồn ào khi trình duyệt gọi trước khi phiên đăng nhập sẵn sàng.
- Tăng cache-busting lên `v=6.4.4` để Vercel và trình duyệt tải đúng JS mới.

## SQL

Không cần chạy thêm SQL.
