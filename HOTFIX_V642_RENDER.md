# Hotfix RUMI 6.4.2 — lỗi trang Thông báo và Kho nguyên liệu

Bản vá này sửa hai lỗi JavaScript:

- `pageNode is not defined` ở trang **Thông báo**.
- `exportButton is not defined` ở trang **Kho nguyên liệu**.

Nguyên nhân: `pageNode`, `summaryItem`, `filterToolbar` và `exportButton` là helper riêng bên trong module `v5.js`, nhưng `v642.js` gọi trực tiếp như biến toàn cục. Bản vá tạo helper độc lập trong `v642.js`, thêm kiểm tra dependency và kiểm tra phần tử `#page` trước khi render.

Ngoài ra, wrapper `enterApp` đã được sửa để giữ dữ liệu dashboard trả về từ bootstrap, tránh gọi API lần hai; thao tác lưu trang gần nhất cũng có `try/catch` để không làm đứng giao diện khi trình duyệt chặn `sessionStorage`.

Không cần chạy thêm SQL. Sau khi chép mã nguồn và deploy, tải cứng trình duyệt bằng `Command + Shift + R`.
