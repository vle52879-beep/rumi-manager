# Nâng cấp RUMI 5.3.2 — Xuất lịch tuần Excel

## Tính năng

- Admin xuất lịch của tuần đang xem bằng nút **Xuất Excel tuần**.
- Bộ lọc cửa hàng đang chọn được áp dụng vào file.
- Nhân viên có thể xuất lịch cá nhân của tuần đang xem.
- File `.xlsx` có 2 sheet:
  - **Lịch tuần**: ma trận nhân viên × Thứ 2 đến Chủ nhật.
  - **Chi tiết ca**: ngày, giờ, số giờ, nhân viên, vị trí, cửa hàng, trạng thái và ghi chú.
- Có tiêu đề RUMI, tổng số ca, nhân viên đã xếp, tổng giờ, cố định hàng/cột và bộ lọc Excel.
- Không cần chạy SQL và không thêm thư viện npm/Python.

## Đẩy lên Vercel

```bash
cd ~/Downloads
unzip -o RUMI-Manager-Supabase-v5.3.2-EXCEL.zip

rsync -av --delete \
  --exclude='.git' \
  --exclude='.env' \
  RUMI-Manager-Supabase-v5.3.2-EXCEL/ \
  RUMI-Manager-Supabase-v4.4-Vercel/

cd ~/Downloads/RUMI-Manager-Supabase-v4.4-Vercel
git add -A
git commit -m "Add weekly schedule Excel export"
git push
```

Sau khi Vercel báo **Ready**, tải lại bằng `Command + Shift + R`.

Kiểm tra `/api/health` phải có:

```json
{
  "version": "5.3.2",
  "schedule_excel": true
}
```
