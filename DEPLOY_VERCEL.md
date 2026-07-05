# Deploy RUMI 6.2 lên Vercel

## 1. Chạy migration

```bash
cd ~/Downloads/RUMI-Manager-Supabase-v6.2-ATTENDANCE-PDF
pbcopy < sql/SUPABASE_RUMI_V6_2_ATTENDANCE_ALERTS.sql
```

Mở Supabase → SQL Editor → New query → dán → Run.

## 2. Ghi đè mã nguồn và push

```bash
cd ~/Downloads

rsync -av --delete \
  --exclude='.git' \
  --exclude='.env' \
  RUMI-Manager-Supabase-v6.2-ATTENDANCE-PDF/ \
  RUMI-Manager-Supabase-v4.4-Vercel/

cd ~/Downloads/RUMI-Manager-Supabase-v4.4-Vercel

git add -A
git commit -m "Upgrade RUMI 6.2 attendance alerts and payroll PDF"
git push
```

Chờ Vercel báo **Ready** rồi nhấn `Command + Shift + R`.

## 3. Kiểm tra

```text
https://rumi-manager-test.vercel.app/api/health
```

Kết quả cần có `"version":"6.2.0"`, `"attendance_alerts":true` và `"payroll_pdf":true`.

## 4. Xuất PDF lương

- Admin: **Bảng lương → Xuất PDF bảng lương**.
- Từng nhân viên: **Phiếu lương → Xuất PDF phiếu lương**.
- Trong hộp thoại in của trình duyệt, chọn **Save as PDF / Lưu dưới dạng PDF**.
