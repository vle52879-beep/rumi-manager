# Deploy RUMI 6.1 lên Vercel

## 1. Chạy migration

```bash
cd ~/Downloads/RUMI-Manager-Supabase-v6.1-PAYROLL-LOGIC
pbcopy < sql/SUPABASE_RUMI_V6_1_PAYROLL_LOGIC.sql
```

Mở Supabase → SQL Editor → New query → dán → Run.

## 2. Ghi đè mã nguồn và push

```bash
cd ~/Downloads

rsync -av --delete \
  --exclude='.git' \
  --exclude='.env' \
  RUMI-Manager-Supabase-v6.1-PAYROLL-LOGIC/ \
  RUMI-Manager-Supabase-v4.4-Vercel/

cd ~/Downloads/RUMI-Manager-Supabase-v4.4-Vercel

git add -A
git commit -m "Fix RUMI 6.1 payroll and schedule logic"
git push
```

Chờ Vercel báo Ready rồi nhấn `Command + Shift + R`.

Kiểm tra:

```text
https://rumi-manager-test.vercel.app/api/health
```

Kết quả cần có `"version":"6.1.0"` và `"payroll_logic_v2":true`.
