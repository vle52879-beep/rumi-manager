# Nâng cấp RUMI 5.5

## 1. Chạy migration Supabase

Chạy file sau trong Supabase SQL Editor, sau các migration v4, v5.3 và v5.4:

```text
sql/SUPABASE_RUMI_V5_5_SECURITY_ATTENDANCE.sql
```

Migration chỉ thao tác đối tượng `rumi_*`.

## 2. Biến môi trường Vercel

Giữ nguyên các biến hiện tại. Có thể thêm pepper ngay từ đầu:

```env
RUMI_PASSWORD_PEPPER=mot-chuoi-ngau-nhien-rat-dai
```

Không đổi hoặc xóa pepper sau khi đã tạo mật khẩu, nếu không toàn bộ mật khẩu cũ sẽ không xác minh được.

Admin hiện có không bị bắt đổi mật khẩu khi migration. Tài khoản nhân viên mới/reset sẽ phải đổi mật khẩu tạm ở lần đăng nhập đầu.

## 3. Kiểm tra

```bash
python3 self_test.py
python3 verify_setup.py
```

API health sau deploy:

```text
/api/health
```

Kết quả cần có `version: 5.5.0`, `security_sessions: true`, `smart_attendance: true`.
