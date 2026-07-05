# Nâng cấp RUMI 6.4.1

## 1. Chạy SQL

```bash
cd ~/Downloads/RUMI-Manager-Supabase-v6.4.1-DOUBLE-SHIFT
pbcopy < sql/SUPABASE_RUMI_V6_4_1_DOUBLE_SHIFT.sql
```

Vào **Supabase → SQL Editor → New query**, dán và bấm **Run**.

Migration này:

- Cho phép một đơn tuần có tối đa 2 ca trong cùng ngày.
- Bổ sung số ca đã chọn/duyệt/chờ/từ chối.
- Sửa kiểm tra Full-time dựa trên số ngày làm thay vì số ca.
- Cho phép duyệt đúng cặp ca đôi 09–17 và 17–23 từ cùng đơn tuần.

## 2. Đẩy mã nguồn

```bash
cd ~/Downloads

rsync -av --delete \
  --exclude='.git' \
  --exclude='.env' \
  RUMI-Manager-Supabase-v6.4.1-DOUBLE-SHIFT/ \
  RUMI-Manager-Supabase-v4.4-Vercel/

cd ~/Downloads/RUMI-Manager-Supabase-v4.4-Vercel

git add -A
git commit -m "Upgrade RUMI 6.4.1 double shift and next week registration"
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
  "version": "6.4.1",
  "weekly_double_shift": true,
  "next_week_registration": true
}
```

Sau đó nhấn `Command + Shift + R`.
