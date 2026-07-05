# Nâng cấp RUMI 6.2

## 1. Chạy migration Supabase

```bash
cd ~/Downloads/RUMI-Manager-Supabase-v6.2-ATTENDANCE-PDF
pbcopy < sql/SUPABASE_RUMI_V6_2_ATTENDANCE_ALERTS.sql
```

Mở **Supabase → SQL Editor → New query**, dán và nhấn **Run**.

Migration bổ sung:

- Quy định thời gian cảnh báo chấm công.
- Bảng `rumi_shift_attendance_alerts`.
- Các cột thống kê vắng/nguy cơ vắng trong bảng lương.
- Hàm `rumi_clock_shift_v62` cho phép chấm vào muộn có kiểm soát.

## 2. Đẩy mã nguồn

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

## 3. Kiểm tra

Mở:

```text
https://rumi-manager-test.vercel.app/api/health
```

Kết quả cần có:

```json
{
  "version": "6.2.0",
  "attendance_alerts": true,
  "payroll_pdf": true
}
```

Sau đó nhấn `Command + Shift + R`.
