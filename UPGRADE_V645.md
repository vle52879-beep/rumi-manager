# RUMI v6.4.5 — Hotfix xử lý lượt công rủi ro

Bản này sửa lỗi khi admin bấm **Xác nhận** hoặc **Loại công** cho ca chính thức chưa có lượt chấm công hợp lệ.

## Đã sửa

- Không còn lỗi Supabase `null value in column "check_in" violates not-null constraint`.
- Ca chưa chấm công được ghi nhận thành bản công 0 giờ bằng mốc hệ thống tương thích schema cũ.
- Giao diện bảng công vẫn hiển thị là chưa có chấm công, không gây hiểu nhầm là nhân viên đã vào ca thật.
- Lượt rủi ro sau khi xử lý sẽ được cập nhật trạng thái và không còn nằm trong hàng chờ duyệt.
- Tăng cache key giao diện lên `v=6.4.5`.

## SQL

Không cần chạy thêm SQL.
