# RUMI Manager 5.0 — Vercel + Supabase

Bản nâng cấp giao diện và trải nghiệm vận hành cho quán trà sữa RUMI.

## Điểm mới

- Dashboard ưu tiên việc cần xử lý và thao tác nhanh.
- Lịch làm dạng tuần cho admin và nhân viên.
- Tìm kiếm, lọc theo trạng thái/vị trí/nhóm nguyên liệu.
- Xuất CSV: nhân viên, lịch làm, bảng công, bảng lương, tồn kho, lịch sử lấy hàng, cần mua và báo cáo.
- Chấm công GPS có bước kiểm tra độ chính xác trước khi vào/ra ca.
- Giao diện responsive, bảng tự chuyển thành thẻ trên điện thoại.
- Thanh điều hướng dưới màn hình trên mobile.
- Tìm nhanh toàn hệ thống bằng nút kính lúp hoặc phím `/`.
- Không thay đổi cấu trúc dữ liệu; tiếp tục dùng các bảng `rumi_*` trong Supabase của IC3.

## Nâng cấp project đang chạy

Giải nén ZIP, sau đó ghi đè mã nguồn vào repository hiện tại:

```bash
cd ~/Downloads
unzip -o RUMI-Manager-Supabase-v5.0-Vercel.zip

rsync -av --delete \
  --exclude='.git' \
  --exclude='.env' \
  RUMI-Manager-Supabase-v5.0-Vercel/ \
  RUMI-Manager-Supabase-v4.4-Vercel/

cd RUMI-Manager-Supabase-v4.4-Vercel
git add -A
git commit -m "Upgrade RUMI Manager 5.0 UI and features"
git push
```

Vercel sẽ tự deploy commit mới. Các Environment Variables hiện tại được giữ nguyên.

## Kiểm tra sau deploy

- `/login`: màn hình đăng nhập.
- `/api/health`: trạng thái Supabase, phiên bản `5.0`.
- Đăng nhập admin: kiểm tra Dashboard, Nhân viên, Xếp lịch, Kho và Báo cáo.
- Đăng nhập nhân viên: kiểm tra Lịch làm, Đăng ký lịch rảnh và Chấm công GPS.

## Kỹ thuật

- Frontend: HTML/CSS/JavaScript thuần, phục vụ từ thư mục `public/` của Vercel.
- Backend: Flask/Python Function tại `api/index.py`.
- Database: Supabase/PostgreSQL, chỉ dùng bảng/hàm có tiền tố `rumi_`.
- Python: 3.12 qua `.python-version`.
