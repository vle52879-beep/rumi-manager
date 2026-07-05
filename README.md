# RUMI Manager 6.0 — Premium Motion UI

Bản quản lý nhân viên quán trà sữa chạy trên Vercel + Supabase, gồm đăng nhập/phân quyền, đăng ca và duyệt đơn, lịch Full-time/Part-time, chấm công GPS, bảng công, bảng lương tháng, xuất Excel, kho nguyên liệu và bảo mật tài khoản.

## Điểm mới của 6.0

- Giao diện premium màu caramel – kem sữa – matcha.
- Motion design trên login, dashboard, card, nút, lịch, bảng, modal và toast.
- Trang giới thiệu công khai mới để giới thiệu sản phẩm với khách hàng.
- Loading progress, trạng thái mạng, hiện/ẩn mật khẩu, counter animation và micro-interaction.
- Responsive tốt trên máy tính và điện thoại.
- Không thêm thư viện frontend bên ngoài, không cần `npm install`.
- Giữ nguyên cơ sở dữ liệu 5.5, không cần chạy migration SQL.

## Chạy local

Tạo `.env` theo `.env.example`, sau đó:

```bash
python3 server.py
```

Mở `http://localhost:8000`.

## Deploy Vercel

Xem [UPGRADE_V60.md](UPGRADE_V60.md) hoặc [DEPLOY_VERCEL.md](DEPLOY_VERCEL.md).

## Bảo mật

- Chỉ đặt Secret/service-role key trong Vercel Environment Variables hoặc `.env` phía server.
- Không đưa Secret key vào frontend, GitHub hoặc biến `VITE_*`.
- Không gửi mật khẩu và khóa bí mật qua ảnh chụp màn hình.
