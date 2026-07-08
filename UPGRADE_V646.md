# RUMI v6.4.6 — Hotfix bảng công bị tràn call stack

Bản này sửa lỗi khi mở **Bảng công** báo `Maximum call stack size exceeded`.

## Đã sửa

- Sửa hàm hiển thị giờ vào/ra bị gọi đệ quy vô hạn.
- Bảng công hiển thị lại bình thường cho cả ca có chấm công thật và ca công rủi ro 0 giờ.
- Giữ logic xử lý lượt công rủi ro của v6.4.5.
- Tăng cache key giao diện lên `v=6.4.6`.

## SQL

Không cần chạy thêm SQL.
