# RUMI Manager 6.1 — Payroll Logic Fix

Bản quản lý nhân viên quán trà sữa chạy trên Vercel + Supabase, gồm đăng nhập/phân quyền, đăng ca và duyệt đơn, lịch Full-time/Part-time, chấm công GPS, bảng công, bảng lương tháng, xuất Excel, kho nguyên liệu và bảo mật tài khoản.

## Điểm mới của 6.1

- Ca chính thức được lấy trực tiếp từ bảng lịch làm, không phụ thuộc việc đã chấm công hay chưa.
- Tách rõ **ca theo lịch**, **giờ thực tế** và **giờ tính lương**.
- Ca chưa diễn ra hiển thị `Chưa đến ca`; ca đang diễn ra hiển thị `Đang làm` hoặc `Đến giờ chấm công`.
- Ca đã qua nhưng thiếu dữ liệu hiển thị `Thiếu chấm công` hoặc `Thiếu giờ ra`.
- Không cho chốt bảng lương khi còn ca chưa hoàn tất.
- Không cho đánh dấu `Đã trả` khi bảng lương chưa chốt, số tiền bằng 0 hoặc dữ liệu công chưa đủ.
- Tuần giao tháng hiển thị rõ mỗi ca thuộc **lương tháng nào**.
- Xuất bảng lương bổ sung số ca theo lịch, số ca hoàn thành và tình trạng dữ liệu công.
- Giữ nguyên Premium Motion UI của bản 6.0.

## Nâng cấp Supabase

Chạy file sau trong Supabase SQL Editor:

```text
sql/SUPABASE_RUMI_V6_1_PAYROLL_LOGIC.sql
```

Migration chỉ thêm cột vào bảng `rumi_payroll_items`, không đụng dữ liệu IC3 Smart Class.

## Chạy local

Tạo `.env` theo `.env.example`, sau đó:

```bash
python3 server.py
```

Mở `http://localhost:8000`.

## Deploy Vercel

Xem [UPGRADE_V61.md](UPGRADE_V61.md) và [DEPLOY_VERCEL.md](DEPLOY_VERCEL.md).

## Bảo mật

- Chỉ đặt Secret/service-role key trong Vercel Environment Variables hoặc `.env` phía server.
- Không đưa Secret key vào frontend, GitHub hoặc biến `VITE_*`.
