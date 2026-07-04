# Đưa RUMI lên Vercel

## 1. Chuẩn bị Supabase

Trong Supabase SQL Editor, chạy `sql/SUPABASE_RUMI_V4_FULL.sql` nếu chưa chạy.

## 2. Đưa mã nguồn lên GitHub

```bash
cd ~/Downloads/RUMI-Manager-Supabase-v4.4-Vercel
git init
git add .
git commit -m "Deploy RUMI Manager to Vercel"
git branch -M main
git remote add origin URL_REPOSITORY_GITHUB
git push -u origin main
```

Không commit file `.env`.

## 3. Import vào Vercel

1. Vào Vercel → Add New → Project.
2. Chọn repository RUMI vừa đẩy lên.
3. Framework Preset: Vercel sẽ nhận Python/Flask. Nếu không, chọn **Other**.
4. Root Directory để trống.
5. Thêm Environment Variables cho Production, Preview và Development:

```text
RUMI_SUPABASE_URL=https://qreldfntnznautyzaggc.supabase.co
RUMI_SUPABASE_SERVICE_ROLE_KEY=<SECRET KEY MỚI>
RUMI_ADMIN_USERNAME=admin
RUMI_ADMIN_PASSWORD=<MẬT KHẨU ADMIN MẠNH>
RUMI_ADMIN_NAME=Chủ cửa hàng RUMI
RUMI_ADMIN_RESET_ON_START=0
```

6. Nhấn Deploy.

Sau lần deploy đầu, thêm biến `RUMI_PUBLIC_URL` bằng domain thật, ví dụ
`https://rumi-manager.vercel.app`, rồi Redeploy để sitemap dùng đúng domain.

## 4. Kiểm tra

- `/` — đăng nhập
- `/gioi-thieu` — trang giới thiệu công khai
- `/api/health` — kiểm tra backend và Supabase
- `/robots.txt`
- `/sitemap.xml`

Khóa `sb_secret_...` chỉ đặt trong Vercel Environment Variables, không đặt trong
JavaScript, GitHub hoặc file có tiền tố `VITE_`.
