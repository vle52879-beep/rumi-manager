# Nâng cấp RUMI 6.0 Premium Motion UI

## Những thay đổi chính

- Thiết kế lại toàn bộ giao diện theo phong cách trà sữa cao cấp.
- Sidebar, topbar, dashboard, bảng, lịch tuần, modal và thông báo có hiệu ứng mượt.
- Trang đăng nhập có minh họa ly trà sữa 3D, bọt trân châu và thẻ trạng thái động.
- Trang giới thiệu công khai được làm lại để thu hút khách hàng.
- Thêm thanh tiến trình khi tải API, trạng thái trực tuyến/mất mạng và hiệu ứng số liệu.
- Thêm nút hiện/ẩn mật khẩu.
- Nút bấm có ripple, card có hover/tilt, số liệu chạy động và thông báo thành công có hiệu ứng.
- Tôn trọng chế độ Reduce Motion của hệ điều hành.

## Dữ liệu và nghiệp vụ

RUMI 6.0 giữ nguyên toàn bộ nghiệp vụ và bảng dữ liệu của 5.5. Không cần chạy SQL mới.

## Cập nhật lên Vercel

```bash
cd ~/Downloads
unzip -o RUMI-Manager-Supabase-v6.0-PREMIUM-UI.zip

rsync -av --delete \
  --exclude='.git' \
  --exclude='.env' \
  RUMI-Manager-Supabase-v6.0-PREMIUM-UI/ \
  RUMI-Manager-Supabase-v4.4-Vercel/

cd ~/Downloads/RUMI-Manager-Supabase-v4.4-Vercel
git add -A
git commit -m "Upgrade RUMI 6.0 premium motion UI"
git push
```

Chờ Vercel báo `Ready`, sau đó nhấn `Command + Shift + R`.

## Đường dẫn kiểm tra

- Hệ thống: `https://rumi-manager-test.vercel.app/`
- Trang giới thiệu: `https://rumi-manager-test.vercel.app/gioi-thieu`
- Hướng dẫn PDF: `https://rumi-manager-test.vercel.app/huong-dan-rumi.pdf`
- API health: `https://rumi-manager-test.vercel.app/api/health`

Kết quả health cần có `"version": "6.0.0"`.
