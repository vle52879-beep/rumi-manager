# Kiểm tra lỗi Vercel

Bản 5.0 đã bỏ `pyproject.toml` lỗi và dùng `requirements.txt` + `.python-version`.

Nếu deployment lỗi:

1. Mở Vercel → Deployments → deployment mới nhất → Logs.
2. Kiểm tra Environment Variables có đủ URL, secret key và mật khẩu admin.
3. Đảm bảo repository có `api/index.py`, `requirements.txt`, `.python-version` và `vercel.json`.
4. Không chọn Build Command hoặc Output Directory tùy chỉnh trong Vercel.
