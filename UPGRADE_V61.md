# RUMI 6.1 — Sửa logic lịch, công và bảng lương

## Vấn đề đã sửa

- Có ca chính thức nhưng bảng lương vẫn hiện `0 ca · 0 giờ`.
- Lịch tuần giao tháng gây hiểu nhầm ca thuộc tháng lương nào.
- Có thể bấm `Đã trả` khi bảng lương chưa chốt hoặc số tiền bằng 0.
- Có thể chốt bảng lương khi còn ca chưa diễn ra, thiếu chấm công hoặc thiếu giờ ra.

## Logic mới

- **Ca theo lịch** lấy trực tiếp từ `rumi_shifts`.
- **Giờ thực tế** lấy từ chấm công vào/ra.
- **Giờ tính lương** chỉ lấy giờ hợp lệ và tăng ca đã duyệt.
- Ca sắp tới hiện `Chưa đến ca`; ca đang diễn ra hiện `Đang làm` hoặc `Đến giờ chấm công`.
- Ca đã qua nhưng không có công hiện `Thiếu chấm công`; có giờ vào nhưng thiếu giờ ra hiện `Thiếu giờ ra`.
- Chỉ được chốt khi toàn bộ ca trong tháng đã hoàn tất.
- Chỉ được đánh dấu `Đã trả` sau khi bảng lương đã chốt, số tiền lớn hơn 0 và phiếu đủ dữ liệu.
- Tuần giao tháng hiển thị nhãn `Lương TMM/YYYY` trên từng ca.
