# RUMI Manager 5.3 OPERATIONS

Bản nâng cấp tập trung vào luồng vận hành hoàn chỉnh:

1. Nhân viên đăng ký lịch rảnh.
2. Admin nhập ngày, giờ, cửa hàng, vị trí công việc và số người cần.
3. Hệ thống xếp hạng người phù hợp theo lịch rảnh đã duyệt, trùng ca, nghỉ phép, đúng vị trí và tổng giờ trong tuần.
4. Admin chọn thủ công hoặc **Xếp tự động** nhiều nhân viên.
5. Nhân viên chấm công vào/ra bằng GPS và đúng khung giờ.
6. Hệ thống tự tính giờ theo lịch, giờ thực tế, giờ tính lương, đi trễ, về sớm và tăng ca.
7. Admin tạo bản nháp, kiểm tra, điều chỉnh và chốt bảng lương tháng.
8. Xuất bảng công, bảng lương CSV dùng được với Excel và in phiếu lương từng nhân viên.

## Nâng cấp cơ sở dữ liệu

Dự án mới cài lần đầu:

1. Chạy `sql/SUPABASE_RUMI_V4_FULL.sql`.
2. Chạy `sql/SUPABASE_RUMI_V5_3_OPERATIONS.sql`.

Dự án đang chạy RUMI v5.2 chỉ cần chạy file thứ hai.

Migration chỉ tạo hoặc sửa bảng/hàm có tiền tố `rumi_`, không đọc hay sửa bảng IC3 Smart Class.

## Bảng mới

- `rumi_payroll_runs`: trạng thái bảng lương từng tháng.
- `rumi_payroll_items`: số liệu bảng lương đã lưu/chốt theo nhân viên.

Bảng `rumi_attendance` được bổ sung các cột chi tiết giờ công.

## Kiểm tra

```bash
python3 self_test.py
python3 verify_setup.py
```

## Chạy máy cá nhân

```bash
python3 server.py
```

Mở `http://localhost:8000`.

## Đẩy lên Vercel

Giữ nguyên Environment Variables đang có. Ghi đè mã nguồn vào repository hiện tại, commit và push. Vercel tự triển khai commit mới.

Sau deploy, kiểm tra:

```text
https://TEN-DU-AN.vercel.app/api/health
```

Kết quả cần có `"version": "5.3"` và `"operations_ready": true`.
