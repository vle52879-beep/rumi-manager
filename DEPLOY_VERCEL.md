# Triển khai RUMI 6.4 lên Vercel

## 1. Chạy SQL v6.4

```bash
cd ~/Downloads/RUMI-Manager-Supabase-v6.4-WEEKLY-SHIFT-REGISTRATION
pbcopy < sql/SUPABASE_RUMI_V6_4_WEEKLY_REGISTRATION.sql
```

Dán vào **Supabase SQL Editor** và nhấn **Run**.

## 2. Ghi đè mã nguồn dự án đang kết nối Vercel

```bash
cd ~/Downloads

rsync -av --delete \
  --exclude='.git' \
  --exclude='.env' \
  RUMI-Manager-Supabase-v6.4-WEEKLY-SHIFT-REGISTRATION/ \
  RUMI-Manager-Supabase-v4.4-Vercel/

cd ~/Downloads/RUMI-Manager-Supabase-v4.4-Vercel

git add -A
git commit -m "Upgrade RUMI 6.4 weekly shift registration"
git push
```

## 3. Kiểm tra

Chờ Vercel báo **Ready**, sau đó mở:

```text
https://rumi-manager-test.vercel.app/api/health
```

Sau đó tải lại mạnh bằng **Command + Shift + R**.
