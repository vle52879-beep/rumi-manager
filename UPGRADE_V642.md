# Nâng cấp RUMI 6.4.1 lên 6.4.2

## 1. Chạy migration

```bash
cd ~/Downloads/RUMI-Manager-Supabase-v6.4.2-ADMIN-CONTROL
pbcopy < sql/SUPABASE_RUMI_V6_4_2_ADMIN_CONTROL.sql
```

Vào Supabase → SQL Editor → New query → dán → Run.

Migration này chỉ tạo/sửa đối tượng có tiền tố `rumi_`.

## 2. Đẩy mã nguồn

```bash
cd ~/Downloads
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

## 3. Kiểm tra

Mở:

```text
https://rumi-manager-test.vercel.app/api/health
```

Kết quả cần có:

```json
{
  "version": "6.4.2",
  "notification_bulk_delete": true,
  "inventory_history_archive": true,
  "registered_shift_reassignment": true,
  "max_weekly_hours_cap": 56
}
```

Sau đó nhấn `Command + Shift + R`.
