# Nâng cấp RUMI 5.4 — Đăng ca và duyệt ứng viên

## Luồng mới

1. Admin tạo ca cần người và chọn **Mở đăng ký**.
2. Nhân viên xem ca trống, kiểm tra cảnh báo và gửi đơn.
3. Admin xem điểm phù hợp, giờ đã làm trong tuần rồi chọn **Duyệt**, **Danh sách chờ** hoặc **Từ chối**.
4. Khi duyệt, hệ thống tự tạo ca chính thức. Chỉ ca chính thức mới được chấm công và tính lương.
5. Admin bấm **Chốt ca**; các đơn còn lại được từ chối theo đúng yêu cầu.
6. Nhân viên Full-time đăng ký ngày nghỉ ưu tiên. Admin duyệt ngày nghỉ trước khi bấm **Xếp Full-time tự động**.

## Quy tắc Full-time

- Mặc định mục tiêu 48 giờ/tuần.
- Tối đa 8 giờ/ngày, 48 giờ/tuần.
- Tối đa 6 ngày liên tiếp.
- Bắt buộc ít nhất 1 ngày nghỉ/tuần.
- Cơ sở dữ liệu chặn xếp vượt quy định, không chỉ cảnh báo trên giao diện.

## Chạy migration

Trong Terminal:

```bash
cd ~/Downloads/RUMI-Manager-Supabase-v5.4-SHIFT-MARKET
pbcopy < sql/SUPABASE_RUMI_V5_4_SHIFT_MARKET.sql
```

Vào **Supabase → SQL Editor → New query**, dán và bấm **Run**.

Migration chỉ tạo hoặc sửa bảng có tiền tố `rumi_`.

## Đẩy lên dự án Vercel hiện tại

```bash
cd ~/Downloads
unzip -o RUMI-Manager-Supabase-v5.4-SHIFT-MARKET.zip

rsync -av --delete \
  --exclude='.git' \
  --exclude='.env' \
  RUMI-Manager-Supabase-v5.4-SHIFT-MARKET/ \
  RUMI-Manager-Supabase-v4.4-Vercel/

cd ~/Downloads/RUMI-Manager-Supabase-v4.4-Vercel
git add -A
git commit -m "Upgrade RUMI 5.4 shift registration workflow"
git push
```

Sau khi Vercel báo **Ready**, mở `/api/health`. Kết quả phải có:

```json
{
  "version": "5.4.0",
  "shift_market": true
}
```

Sau đó nhấn `Command + Shift + R` trên trang RUMI.
