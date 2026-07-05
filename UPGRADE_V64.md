# Nâng cấp RUMI 6.4 — Đăng ký ca cả tuần

## Luồng mới

1. Admin chọn tuần, cửa hàng và đăng lịch với hai ca cố định:
   - Ca ngày: **09:00–17:00**
   - Ca tối: **17:00–23:00**
2. Nhân viên mở **Đăng ký lịch tuần**, chọn tối đa một ca mỗi ngày rồi gửi một đơn duy nhất.
3. Nhân viên Full-time phải chọn đúng **6 ngày làm và 1 ngày nghỉ**.
4. Admin có thể duyệt toàn bộ các ngày phù hợp, duyệt/từ chối từng ngày hoặc đưa ngày đó vào danh sách chờ.
5. Chỉ ngày đã duyệt mới tạo lịch chính thức và được đưa vào chấm công, tính lương.

## Chạy migration

```bash
pbcopy < sql/SUPABASE_RUMI_V6_4_WEEKLY_REGISTRATION.sql
```

Mở **Supabase → SQL Editor → New query**, dán và chọn **Run**.

## Kiểm tra

```bash
python3 self_test.py
python3 verify_setup.py
```

`/api/health` phải trả về:

```json
{
  "version": "6.4.0",
  "weekly_shift_registration": true
}
```
