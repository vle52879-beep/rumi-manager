-- RUMI Manager 6.1 — Payroll & schedule logic
-- Chỉ bổ sung cột cho bảng rumi_payroll_items. Không chạm dữ liệu IC3 Smart Class.

begin;

alter table public.rumi_payroll_items
  add column if not exists scheduled_shift_count integer not null default 0,
  add column if not exists completed_shift_count integer not null default 0,
  add column if not exists upcoming_shift_count integer not null default 0,
  add column if not exists active_shift_count integer not null default 0,
  add column if not exists pending_checkin_count integer not null default 0,
  add column if not exists missing_attendance_count integer not null default 0,
  add column if not exists incomplete_attendance_count integer not null default 0,
  add column if not exists payroll_state text not null default 'Chưa có dữ liệu',
  add column if not exists eligible_for_payment boolean not null default false;

-- Điền trạng thái hợp lý cho phiếu lương cũ. Khi bấm "Tính lại", backend 6.1
-- sẽ thay bằng số liệu chi tiết lấy trực tiếp từ lịch làm và chấm công.
update public.rumi_payroll_items
set completed_shift_count = greatest(completed_shift_count, attendance_count),
    payroll_state = case
      when payable_hours > 0 then 'Đủ dữ liệu'
      when scheduled_hours > 0 then 'Chưa có công'
      else 'Không có lịch'
    end,
    eligible_for_payment = case
      when total > 0 and payable_hours > 0 then true
      else false
    end
where payroll_state = 'Chưa có dữ liệu'
   or completed_shift_count = 0;

comment on column public.rumi_payroll_items.scheduled_shift_count is 'Số ca chính thức thuộc tháng lương';
comment on column public.rumi_payroll_items.completed_shift_count is 'Số ca đã chấm vào và chấm ra hoàn tất';
comment on column public.rumi_payroll_items.payroll_state is 'Tình trạng dữ liệu công trước khi thanh toán';
comment on column public.rumi_payroll_items.eligible_for_payment is 'Chỉ true khi phiếu lương đã đủ dữ liệu để thanh toán';

commit;
