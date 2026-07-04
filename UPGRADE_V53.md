# Nâng từ RUMI 5.2 lên 5.3

## 1. Chạy migration Supabase

Mở Supabase → SQL Editor → New query, dán toàn bộ nội dung:

```text
sql/SUPABASE_RUMI_V5_3_OPERATIONS.sql
```

Nhấn **Run** một lần.

## 2. Ghi đè mã nguồn repository đang deploy

```bash
cd ~/Downloads
unzip -o RUMI-Manager-Supabase-v5.3-OPERATIONS.zip

rsync -av --delete \
  --exclude='.git' \
  --exclude='.env' \
  RUMI-Manager-Supabase-v5.3-OPERATIONS/ \
  RUMI-Manager-Supabase-v4.4-Vercel/

cd ~/Downloads/RUMI-Manager-Supabase-v4.4-Vercel
git add -A
git commit -m "Upgrade RUMI 5.3 scheduling attendance payroll"
git push
```

## 3. Kiểm tra

Chờ Vercel **Ready**, sau đó mở `/api/health` và tải lại trang bằng `Command + Shift + R`.
