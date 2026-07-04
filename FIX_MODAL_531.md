# RUMI 5.3.1 – Sửa lỗi modal bị khóa

- Bỏ `stopPropagation()` khỏi hộp thoại để các nút Hủy, Đóng, Lấy vị trí và Lưu hoạt động qua event delegation.
- Chỉ đóng modal khi bấm đúng vùng nền tối.
- Sửa race condition của tìm kiếm nhanh khiến `#v5-command-results` bị null.
- Không mở tìm kiếm nhanh khi modal đang hiển thị.
- Phím Escape đóng modal trước, sau đó mới đóng tìm kiếm.
- Tăng cache version lên 5.3.1.
