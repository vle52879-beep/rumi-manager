# Deploy RUMI 6.4.2 lên Vercel

## Bước 1 — SQL

Chạy file:

```text
sql/SUPABASE_RUMI_V6_4_2_ADMIN_CONTROL.sql
```

trong đúng dự án Supabase của RUMI.

## Bước 2 — Ghi đè dự án Git hiện tại

```bash
cd ~/Downloads
unzip -o RUMI-Manager-Supabase-v6.4.2-ADMIN-CONTROL.zip

rsync -av --delete \
  --exclude='.git' \
  --exclude='.env' \
  RUMI-Manager-Supabase-v6.4.2-ADMIN-CONTROL/ \
  RUMI-Manager-Supabase-v4.4-Vercel/

cd ~/Downloads/RUMI-Manager-Supabase-v4.4-Vercel
git add -A
git commit -m "Upgrade RUMI 6.4.2 admin controls"
git push
```

## Bước 3 — Kiểm tra Vercel

Chờ deployment thành `Ready`, sau đó mở:

```text
https://rumi-manager-test.vercel.app/api/health
```

Không cần thêm biến môi trường mới.
