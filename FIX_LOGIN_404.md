# Sửa lỗi 404 khi tải lại /login hoặc /app

Bản 5.1 không còn phụ thuộc vào rewrite SPA cho màn hình đăng nhập.

- `public/login.html` phục vụ trực tiếp `/login` khi bật `cleanUrls`.
- `public/app.html` phục vụ trực tiếp `/app`.
- Router phía trình duyệt dùng hash ở URL gốc (`/#login`, `/#dashboard`) nên tải lại không còn 404.
- `public/404.html` chuyển các đường dẫn SPA cũ về trang chính.
