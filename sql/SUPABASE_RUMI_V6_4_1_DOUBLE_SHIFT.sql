-- RUMI Manager 6.4.1 — cho phép đăng ký 1 hoặc 2 ca/ngày và tuần sau
-- Chạy sau SUPABASE_RUMI_V6_4_WEEKLY_REGISTRATION.sql. Có thể chạy nhiều lần.

begin;

alter table public.rumi_weekly_shift_requests
  add column if not exists selected_shifts integer not null default 0,
  add column if not exists approved_shifts integer not null default 0,
  add column if not exists waitlist_shifts integer not null default 0,
  add column if not exists rejected_shifts integer not null default 0;

alter table public.rumi_weekly_shift_request_items
  drop constraint if exists rumi_weekly_shift_request_items_request_id_work_date_key;

-- Phòng trường hợp tên constraint được PostgreSQL tạo khác với tên mặc định.
do $$
declare r record;
begin
  for r in
    select conname
    from pg_constraint
    where conrelid = 'public.rumi_weekly_shift_request_items'::regclass
      and contype = 'u'
      and pg_get_constraintdef(oid) ilike '%request_id%work_date%'
      and pg_get_constraintdef(oid) not ilike '%opening_id%'
  loop
    execute format('alter table public.rumi_weekly_shift_request_items drop constraint if exists %I', r.conname);
  end loop;
end $$;

create or replace function public.rumi_refresh_weekly_shift_request(p_request_id bigint)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_total integer := 0;
  v_selected_days integer := 0;
  v_approved integer := 0;
  v_approved_days integer := 0;
  v_waitlist integer := 0;
  v_waitlist_days integer := 0;
  v_rejected integer := 0;
  v_rejected_days integer := 0;
  v_withdrawn integer := 0;
  v_status text := 'Chờ duyệt';
  v_employee_id bigint;
  v_week_start date;
  v_employment_type text;
begin
  select employee_id, week_start
    into v_employee_id, v_week_start
  from public.rumi_weekly_shift_requests
  where id = p_request_id;

  if v_employee_id is null then
    return;
  end if;

  select
    count(*),
    count(distinct work_date),
    count(*) filter (where status = 'Đã duyệt'),
    count(distinct work_date) filter (where status = 'Đã duyệt'),
    count(*) filter (where status = 'Danh sách chờ'),
    count(distinct work_date) filter (where status = 'Danh sách chờ'),
    count(*) filter (where status = 'Từ chối'),
    count(distinct work_date) filter (where status = 'Từ chối'),
    count(*) filter (where status = 'Đã rút')
  into v_total, v_selected_days, v_approved, v_approved_days,
       v_waitlist, v_waitlist_days, v_rejected, v_rejected_days, v_withdrawn
  from public.rumi_weekly_shift_request_items
  where request_id = p_request_id;

  if v_total > 0 and v_approved = v_total then
    v_status := 'Đã duyệt';
  elsif v_total > 0 and v_withdrawn = v_total then
    v_status := 'Đã rút';
  elsif v_total > 0 and v_rejected = v_total then
    v_status := 'Từ chối';
  elsif v_approved > 0 or v_waitlist > 0 or v_rejected > 0 then
    v_status := 'Duyệt một phần';
  else
    v_status := 'Chờ duyệt';
  end if;

  update public.rumi_weekly_shift_requests
  set status = v_status,
      selected_days = v_selected_days,
      selected_shifts = v_total,
      approved_days = v_approved_days,
      approved_shifts = v_approved,
      waitlist_days = v_waitlist_days,
      waitlist_shifts = v_waitlist,
      rejected_days = v_rejected_days,
      rejected_shifts = v_rejected,
      reviewed_at = case when v_status <> 'Chờ duyệt' then coalesce(reviewed_at, now()) else reviewed_at end,
      updated_at = now()
  where id = p_request_id;

  select employment_type into v_employment_type
  from public.rumi_employees where id = v_employee_id;

  -- Với ca đôi, đơn có thể được duyệt một phần theo số ca nhưng nhân viên vẫn
  -- đã có đủ 6 ngày làm. Khi đó ngày nghỉ tuần vẫn phải được duyệt đúng logic.
  if v_employment_type = 'Full-time' and v_approved_days = 6 then
    update public.rumi_weekly_day_off_requests
    set status = 'Đã duyệt',
        approved_date = preferred_date,
        reviewed_at = coalesce(reviewed_at, now()),
        admin_note = case when admin_note = '' then 'Duyệt cùng đơn đăng ký ca cả tuần' else admin_note end
    where employee_id = v_employee_id and week_start = v_week_start;
  end if;
end;
$$;


create or replace function public.rumi_submit_weekly_shift_request(
  p_employee_id bigint,
  p_week_start date,
  p_location_id bigint,
  p_employee_note text,
  p_opening_ids bigint[]
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_employee public.rumi_employees%rowtype;
  v_request_id bigint;
  v_opening public.rumi_shift_openings%rowtype;
  v_application_id bigint;
  v_existing_status text;
  v_selected_shifts integer := coalesce(cardinality(p_opening_ids), 0);
  v_selected_days integer := 0;
  v_selected_hours numeric(8,2) := 0;
  v_seen_dates date[] := array[]::date[];
  v_requested_day_off date;
  v_approved_existing integer := 0;
  v_opening_id bigint;
begin
  if extract(isodow from p_week_start) <> 1 then
    raise exception 'Ngày đầu tuần phải là Thứ Hai';
  end if;

  select * into v_employee
  from public.rumi_employees
  where id = p_employee_id and status = 'Đang làm';

  if not found then
    raise exception 'Nhân viên không tồn tại hoặc đã ngừng hoạt động';
  end if;

  if v_selected_shifts < 1 then
    raise exception 'Hãy chọn ít nhất một ca trong tuần';
  end if;
  if v_selected_shifts > 14 then
    raise exception 'Một tuần chỉ có tối đa 14 ca cố định';
  end if;
  if (select count(distinct x) from unnest(coalesce(p_opening_ids, array[]::bigint[])) as x) <> v_selected_shifts then
    raise exception 'Danh sách ca bị trùng';
  end if;

  select id into v_request_id
  from public.rumi_weekly_shift_requests
  where employee_id = p_employee_id and week_start = p_week_start
  for update;

  if v_request_id is not null then
    select count(*) into v_approved_existing
    from public.rumi_weekly_shift_request_items
    where request_id = v_request_id and status = 'Đã duyệt';
    if v_approved_existing > 0 then
      raise exception 'Đơn tuần đã được duyệt một phần. Hãy liên hệ quản lý để thay đổi lịch';
    end if;

    update public.rumi_shift_applications
    set status = 'Đã rút', reviewed_at = null, reviewed_by = null,
        admin_note = 'Nhân viên gửi lại đơn đăng ký cả tuần'
    where weekly_request_id = v_request_id
      and status in ('Chờ duyệt','Danh sách chờ','Từ chối','Đã rút');

    delete from public.rumi_weekly_shift_request_items where request_id = v_request_id;

    update public.rumi_weekly_shift_requests
    set location_id = p_location_id,
        status = 'Chờ duyệt',
        employee_note = coalesce(p_employee_note, ''),
        admin_note = '',
        approved_days = 0,
        approved_shifts = 0,
        waitlist_days = 0,
        waitlist_shifts = 0,
        rejected_days = 0,
        rejected_shifts = 0,
        submitted_at = now(),
        reviewed_at = null,
        reviewed_by = null,
        updated_at = now()
    where id = v_request_id;
  else
    insert into public.rumi_weekly_shift_requests(
      employee_id, week_start, location_id, employee_note
    ) values (
      p_employee_id, p_week_start, p_location_id, coalesce(p_employee_note, '')
    ) returning id into v_request_id;
  end if;

  foreach v_opening_id in array coalesce(p_opening_ids, array[]::bigint[]) loop
    select * into v_opening
    from public.rumi_shift_openings
    where id = v_opening_id;

    if not found then
      raise exception 'Có ca đăng ký không tồn tại';
    end if;
    if v_opening.location_id <> p_location_id then
      raise exception 'Các ca trong một đơn tuần phải cùng cửa hàng';
    end if;
    if v_opening.work_date not between p_week_start and p_week_start + 6 then
      raise exception 'Ca đăng ký không nằm trong tuần đã chọn';
    end if;
    if v_opening.status <> 'Mở đăng ký' then
      raise exception 'Có ca không còn nhận đăng ký';
    end if;
    if v_opening.application_deadline is not null and v_opening.application_deadline < now() then
      raise exception 'Có ca đã hết hạn đăng ký';
    end if;
    if v_opening.eligible_employment_type <> 'Tất cả'
       and v_opening.eligible_employment_type <> v_employee.employment_type then
      raise exception 'Có ca không dành cho loại nhân viên của bạn';
    end if;
    if (select count(*) from unnest(v_seen_dates) as d where d = v_opening.work_date) >= 2 then
      raise exception 'Mỗi ngày chỉ được đăng ký tối đa 2 ca';
    end if;
    v_seen_dates := array_append(v_seen_dates, v_opening.work_date);

    if v_opening.start_time = time '09:00' and v_opening.end_time = time '17:00' then
      null;
    elsif v_opening.start_time = time '17:00' and v_opening.end_time = time '23:00' then
      null;
    else
      raise exception 'Đơn tuần chỉ hỗ trợ ca 09:00–17:00 và 17:00–23:00';
    end if;

    select status into v_existing_status
    from public.rumi_shift_applications
    where opening_id = v_opening.id and employee_id = p_employee_id;

    if v_existing_status = 'Đã duyệt' then
      raise exception 'Bạn đã được duyệt vào một ca trong tuần này';
    end if;

    insert into public.rumi_shift_applications(
      opening_id, employee_id, weekly_request_id, status,
      employee_note, admin_note, score_snapshot, applied_at,
      reviewed_at, reviewed_by
    ) values (
      v_opening.id, p_employee_id, v_request_id, 'Chờ duyệt',
      coalesce(p_employee_note, ''), '', 0, now(), null, null
    )
    on conflict (opening_id, employee_id) do update
      set weekly_request_id = excluded.weekly_request_id,
          status = 'Chờ duyệt',
          employee_note = excluded.employee_note,
          admin_note = '',
          applied_at = now(),
          reviewed_at = null,
          reviewed_by = null
    returning id into v_application_id;

    insert into public.rumi_weekly_shift_request_items(
      request_id, opening_id, application_id, work_date,
      shift_code, start_time, end_time, status
    ) values (
      v_request_id, v_opening.id, v_application_id, v_opening.work_date,
      case when v_opening.start_time = time '09:00' then 'CA_09_17' else 'CA_17_23' end,
      v_opening.start_time, v_opening.end_time, 'Chờ duyệt'
    );

    v_selected_hours := v_selected_hours + extract(epoch from (v_opening.end_time - v_opening.start_time)) / 3600;
  end loop;

  select count(distinct d) into v_selected_days from unnest(v_seen_dates) as d;

  if v_employee.employment_type = 'Full-time' and v_selected_days <> 6 then
    raise exception 'Nhân viên Full-time phải đăng ký đúng 6 ngày làm và nghỉ 1 ngày; mỗi ngày có thể chọn 1 hoặc 2 ca';
  end if;

  if v_employee.employment_type = 'Full-time' then
    select d::date into v_requested_day_off
    from generate_series(p_week_start, p_week_start + 6, interval '1 day') as d
    where d::date <> all(v_seen_dates)
    order by d
    limit 1;

    insert into public.rumi_weekly_day_off_requests(
      employee_id, week_start, preferred_date, alternate_date,
      approved_date, reason, status, admin_note,
      reviewed_at, reviewed_by, created_at
    ) values (
      p_employee_id, p_week_start, v_requested_day_off, null,
      null, 'Ngày nghỉ theo đơn đăng ký ca cả tuần', 'Chờ duyệt', '',
      null, null, now()
    )
    on conflict (employee_id, week_start) do update
      set preferred_date = excluded.preferred_date,
          alternate_date = null,
          approved_date = null,
          reason = excluded.reason,
          status = 'Chờ duyệt',
          admin_note = '',
          reviewed_at = null,
          reviewed_by = null;
  else
    v_requested_day_off := null;
  end if;

  update public.rumi_weekly_shift_requests
  set requested_day_off = v_requested_day_off,
      selected_days = v_selected_days,
      selected_shifts = v_selected_shifts,
      selected_hours = round(v_selected_hours, 2),
      updated_at = now()
  where id = v_request_id;

  perform public.rumi_refresh_weekly_shift_request(v_request_id);

  return jsonb_build_object(
    'request_id', v_request_id,
    'selected_days', v_selected_days,
    'selected_shifts', v_selected_shifts,
    'selected_hours', round(v_selected_hours, 2),
    'requested_day_off', v_requested_day_off,
    'status', 'Chờ duyệt'
  );
end;
$$;


create or replace function public.rumi_validate_shift_assignment()
returns trigger
language plpgsql
set search_path = public
as $$
declare
  v_employee public.rumi_employees%rowtype;
  v_hours numeric(8,2);
  v_day_hours numeric(8,2);
  v_week_hours numeric(8,2);
  v_week_start date;
  v_distinct_days integer;
  v_capacity integer;
  v_required integer;
  v_day date;
  v_prev date;
  v_run integer := 0;
  v_max_run integer := 0;
  v_allow_weekly_double boolean := false;
begin
  if new.status not in ('Đã xếp','Đã xác nhận') then return new; end if;

  select * into v_employee from public.rumi_employees where id = new.employee_id;
  if not found or v_employee.status <> 'Đang làm' then
    raise exception 'Nhân viên không còn ở trạng thái đang làm';
  end if;

  if exists (
    select 1 from public.rumi_leave_requests l
    where l.employee_id = new.employee_id and l.status = 'Đã duyệt'
      and new.shift_date between l.start_date and l.end_date
  ) then raise exception 'Nhân viên đang nghỉ phép trong ngày này'; end if;

  if exists (
    select 1 from public.rumi_weekly_day_off_requests d
    where d.employee_id = new.employee_id and d.status = 'Đã duyệt'
      and d.approved_date = new.shift_date
  ) then raise exception 'Đây là ngày nghỉ tuần đã được duyệt của nhân viên'; end if;

  if exists (
    select 1 from public.rumi_shifts s
    where s.employee_id = new.employee_id and s.shift_date = new.shift_date
      and s.status in ('Đã xếp','Đã xác nhận')
      and (new.id is null or s.id <> new.id)
      and s.start_time < new.end_time and s.end_time > new.start_time
  ) then raise exception 'Nhân viên bị trùng ca trong khung giờ này'; end if;

  v_hours := round((extract(epoch from (new.end_time - new.start_time))/3600)::numeric,2);
  select coalesce(sum(extract(epoch from (s.end_time-s.start_time))/3600),0)
    into v_day_hours
  from public.rumi_shifts s
  where s.employee_id = new.employee_id and s.shift_date = new.shift_date
    and s.status in ('Đã xếp','Đã xác nhận') and (new.id is null or s.id <> new.id);

  -- Chỉ cho vượt giới hạn ngày khi đây là đúng cặp ca cố định 09–17 + 17–23
  -- và cả hai đơn đều thuộc cùng một đơn đăng ký tuần.
  if v_day_hours + v_hours > v_employee.max_daily_hours then
    select exists (
      select 1
      from public.rumi_shifts s
      join public.rumi_shift_applications old_app on old_app.id = s.application_id
      join public.rumi_shift_applications new_app on new_app.id = new.application_id
      where s.employee_id = new.employee_id
        and s.shift_date = new.shift_date
        and s.status in ('Đã xếp','Đã xác nhận')
        and (new.id is null or s.id <> new.id)
        and old_app.weekly_request_id is not null
        and old_app.weekly_request_id = new_app.weekly_request_id
        and (
          (s.start_time = time '09:00' and s.end_time = time '17:00' and new.start_time = time '17:00' and new.end_time = time '23:00')
          or
          (s.start_time = time '17:00' and s.end_time = time '23:00' and new.start_time = time '09:00' and new.end_time = time '17:00')
        )
    ) into v_allow_weekly_double;

    if not v_allow_weekly_double or v_day_hours + v_hours > 14 then
      raise exception 'Vượt giới hạn % giờ làm trong ngày', v_employee.max_daily_hours;
    end if;
  end if;

  v_week_start := new.shift_date - extract(isodow from new.shift_date)::integer + 1;
  select coalesce(sum(extract(epoch from (s.end_time-s.start_time))/3600),0),
         count(distinct s.shift_date)
    into v_week_hours, v_distinct_days
  from public.rumi_shifts s
  where s.employee_id = new.employee_id
    and s.shift_date between v_week_start and v_week_start + 6
    and s.status in ('Đã xếp','Đã xác nhận') and (new.id is null or s.id <> new.id);
  if v_week_hours + v_hours > v_employee.max_weekly_hours then
    raise exception 'Vượt giới hạn % giờ làm trong tuần', v_employee.max_weekly_hours;
  end if;

  if not exists (
    select 1 from public.rumi_shifts s where s.employee_id = new.employee_id
      and s.shift_date = new.shift_date and s.status in ('Đã xếp','Đã xác nhận')
      and (new.id is null or s.id <> new.id)
  ) then v_distinct_days := v_distinct_days + 1; end if;
  if v_employee.employment_type = 'Full-time'
     and v_distinct_days > 7 - v_employee.weekly_days_off then
    raise exception 'Full-time phải nghỉ ít nhất % ngày trong tuần', v_employee.weekly_days_off;
  end if;

  for v_day in
    select distinct d from (
      select s.shift_date d from public.rumi_shifts s
      where s.employee_id = new.employee_id and s.status in ('Đã xếp','Đã xác nhận')
        and s.shift_date between new.shift_date - 7 and new.shift_date + 7
        and (new.id is null or s.id <> new.id)
      union select new.shift_date
    ) q order by d
  loop
    if v_prev is not null and v_day = v_prev + 1 then v_run := v_run + 1; else v_run := 1; end if;
    v_max_run := greatest(v_max_run, v_run); v_prev := v_day;
  end loop;
  if v_max_run > v_employee.max_consecutive_days then
    raise exception 'Vượt giới hạn % ngày làm liên tiếp', v_employee.max_consecutive_days;
  end if;

  if new.opening_id is not null then
    select required_count into v_required from public.rumi_shift_openings where id = new.opening_id;
    select count(*) into v_capacity from public.rumi_shifts s
      where s.opening_id = new.opening_id and s.status in ('Đã xếp','Đã xác nhận')
        and (new.id is null or s.id <> new.id);
    if v_capacity >= v_required then raise exception 'Ca đã đủ số nhân viên cần'; end if;
  end if;
  return new;
end;
$$;


drop trigger if exists rumi_shifts_validate_assignment on public.rumi_shifts;
create trigger rumi_shifts_validate_assignment
before insert or update of employee_id, shift_date, start_time, end_time, status, opening_id
on public.rumi_shifts
for each row execute function public.rumi_validate_shift_assignment();

commit;
