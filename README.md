# RUMI Manager v4.5 — Vercel + Supabase

Bản này triển khai giống IC3 SmartClass: mã nguồn trên GitHub, tự động deploy lên
Vercel và dùng chung dự án Supabase nhưng chỉ thao tác các bảng có tiền tố
`rumi_`.

## Chạy cục bộ

```bash
cp .env.example .env
python3 server.py
```

## Triển khai Vercel

Xem `DEPLOY_VERCEL.md`.

## Biến môi trường bắt buộc trên Vercel

- `RUMI_SUPABASE_URL`
- `RUMI_SUPABASE_SERVICE_ROLE_KEY`
- `RUMI_ADMIN_PASSWORD` (không dùng `Rumi@2026` khi online)

## Cấu trúc Vercel

- `public/`: giao diện được Vercel CDN phục vụ.
- `app.py`: Flask/WSGI adapter cho toàn bộ API.
- `server.py`: nghiệp vụ, phân quyền và kết nối Supabase.
- `vercel.json`, `pyproject.toml`, `requirements.txt`: cấu hình triển khai.


## Sửa lỗi build Vercel v4.5

Đã bỏ cấu hình `functions.app.py` không hợp lệ. Vercel tự nhận Flask app từ `app.py` và `pyproject.toml`.
