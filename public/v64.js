'use strict';

/* RUMI 6.4.1 — đăng ký tuần sau, cho phép chọn 1 hoặc 2 ca mỗi ngày. */
(() => {
  const VERSION = '6.4.1';
  const SHIFT_SPECS = [
    { code: 'CA_09_17', label: 'Ca ngày', start: '09:00', end: '17:00', hours: 8, tone: 'day' },
    { code: 'CA_17_23', label: 'Ca tối', start: '17:00', end: '23:00', hours: 6, tone: 'night' },
  ];

  const parseDate = (value) => {
    const [y, m, d] = String(value).slice(0, 10).split('-').map(Number);
    return new Date(y, m - 1, d);
  };
  const isoLocal = (value) => {
    const d = new Date(value);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  };
  const addDays64 = (value, amount) => {
    const d = new Date(value);
    d.setDate(d.getDate() + amount);
    return d;
  };
  const monday64 = (value = new Date()) => {
    const d = new Date(value);
    d.setHours(0, 0, 0, 0);
    const day = d.getDay() || 7;
    d.setDate(d.getDate() - day + 1);
    return d;
  };
  const currentWeekStart64 = () => isoLocal(monday64());
  const time5 = (value) => String(value || '').slice(0, 5);
  const weekRange64 = () => {
    const start = state.shiftMarketWeekStart || currentWeekStart64();
    return { start, end: isoLocal(addDays64(parseDate(start), 6)) };
  };
  const weekLabel64 = (start) => {
    const first = parseDate(start);
    const last = addDays64(first, 6);
    return `${first.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })} – ${last.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' })}`;
  };
  const dayLabel = (date) => parseDate(date).toLocaleDateString('vi-VN', { weekday: 'short', day: '2-digit', month: '2-digit' });
  const isStandardOpening = (opening) => SHIFT_SPECS.some((spec) => spec.start === time5(opening.start_time) && spec.end === time5(opening.end_time));
  const specForOpening = (opening) => SHIFT_SPECS.find((spec) => spec.start === time5(opening.start_time) && spec.end === time5(opening.end_time));

  state.shiftMarketWeekStart = state.shiftMarketWeekStart || currentWeekStart64();
  state.v64LocationId = state.v64LocationId || null;

  titles.schedule = 'Lịch tuần & duyệt đăng ký';
  titles.availability = 'Đăng ký lịch cả tuần';
  const employeeNav = navEmployee.find((item) => item[1] === 'availability');
  if (employeeNav) employeeNav[2] = 'Đăng ký lịch tuần';
  const adminNav = navAdmin.find((item) => item[1] === 'schedule');
  if (adminNav) adminNav[2] = 'Lịch tuần & duyệt đơn';

  function weekControls64() {
    const range = weekRange64();
    return `<div class="v64-week-controls">
      <button class="btn small secondary" data-v64-action="week" data-step="-7">‹</button>
      <div><span>Tuần làm việc</span><strong>${weekLabel64(range.start)}</strong></div>
      <button class="btn small secondary" data-v64-action="week-today">Tuần này</button>
      <button class="btn small secondary" data-v64-action="week-next">Tuần sau</button>
      <button class="btn small secondary" data-v64-action="week" data-step="7">›</button>
    </div>`;
  }

  function standardOpenings(data, locationId = null) {
    return (data.openings || []).filter((x) => isStandardOpening(x) && (!locationId || Number(x.location_id) === Number(locationId)));
  }

  function openingsByDay(data, locationId) {
    const grouped = new Map();
    standardOpenings(data, locationId).forEach((opening) => {
      if (!grouped.has(opening.work_date)) grouped.set(opening.work_date, []);
      grouped.get(opening.work_date).push(opening);
    });
    return grouped;
  }

  function statusClass(status) {
    if (/Đã duyệt|Đã chốt|Đã xác nhận/.test(status || '')) return 'ok';
    if (/Từ chối|Đã hủy|Đã rút/.test(status || '')) return 'danger';
    if (/Danh sách chờ|Duyệt một phần/.test(status || '')) return 'wait';
    return 'pending';
  }

  function officialWeekBoard(shifts, start) {
    const days = Array.from({ length: 7 }, (_, index) => addDays64(parseDate(start), index));
    return `<div class="v64-official-board">${days.map((day) => {
      const iso = isoLocal(day);
      const rows = (shifts || []).filter((x) => x.shift_date === iso);
      return `<section class="v64-official-day">
        <header><strong>${day.toLocaleDateString('vi-VN', { weekday: 'short' })}</strong><span>${day.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })}</span></header>
        <div>${rows.length ? rows.map((row) => `<article>
          <b>${time5(row.start_time)}–${time5(row.end_time)}</b>
          <span>${esc(row.employee_name || 'Chưa xếp')}</span>
          <small>${esc(row.employee_role || '')} · ${esc(row.location_name || '')}</small>
        </article>`).join('') : '<em>Chưa có lịch chính thức</em>'}</div>
      </section>`;
    }).join('')}</div>`;
  }

  function publishWeekForm(data) {
    const range = weekRange64();
    const roles = [...new Set((data.employees || []).map((x) => x.role).filter(Boolean))];
    const defaultDeadline = `${range.start}T20:00`;
    return `<form class="form-grid v64-publish-form" data-form="v64-publish-week">
      <input type="hidden" name="week_start" value="${range.start}">
      <div class="field"><label>Cửa hàng</label><select name="location_id" required><option value="">Chọn cửa hàng</option>${(data.locations || []).map((x) => `<option value="${x.id}">${esc(x.name)}</option>`).join('')}</select></div>
      <div class="field"><label>Hạn đăng ký</label><input type="datetime-local" name="application_deadline" value="${defaultDeadline}"></div>
      <div class="field"><label>Số người ca 09:00–17:00</label><input type="number" name="morning_count" min="0" max="50" value="2" required></div>
      <div class="field"><label>Số người ca 17:00–23:00</label><input type="number" name="evening_count" min="0" max="50" value="2" required></div>
      <div class="field"><label>Vị trí cần</label><select name="required_role"><option value="">Bất kỳ vị trí</option>${roles.map((role) => `<option>${esc(role)}</option>`).join('')}</select></div>
      <div class="field"><label>Loại nhân viên</label><select name="eligible_employment_type"><option>Tất cả</option><option>Full-time</option><option>Part-time</option></select></div>
      <div class="field"><label>Trạng thái</label><select name="status"><option>Mở đăng ký</option><option>Nháp</option></select></div>
      <div class="field span-2"><label>Ngày mở ca</label><div class="v64-day-checks">${Array.from({ length: 7 }, (_, index) => {
        const date = isoLocal(addDays64(parseDate(range.start), index));
        return `<label><input type="checkbox" name="days" value="${index}" checked><span>${dayLabel(date)}</span></label>`;
      }).join('')}</div></div>
      <div class="field span-2"><label>Ghi chú</label><textarea name="note" placeholder="Ví dụ: cuối tuần ưu tiên nhân viên có thể hỗ trợ thu ngân"></textarea></div>
      <div class="form-actions"><button type="button" class="btn secondary" data-action="close-modal">Hủy</button><button class="btn" type="submit">Đăng lịch cả tuần</button></div>
    </form>`;
  }

  function capacityBoard(data, locationId) {
    const range = weekRange64();
    const grouped = openingsByDay(data, locationId);
    return `<div class="v64-capacity-board">${Array.from({ length: 7 }, (_, index) => {
      const date = isoLocal(addDays64(parseDate(range.start), index));
      const rows = grouped.get(date) || [];
      return `<section><header><strong>${dayLabel(date)}</strong></header>${SHIFT_SPECS.map((spec) => {
        const opening = rows.find((x) => time5(x.start_time) === spec.start && time5(x.end_time) === spec.end);
        if (!opening) return `<div class="v64-capacity-slot muted"><b>${spec.label}</b><span>${spec.start}–${spec.end}</span><small>Chưa mở</small></div>`;
        return `<div class="v64-capacity-slot ${opening.remaining_slots ? 'needs' : 'full'}"><b>${spec.label}</b><span>${spec.start}–${spec.end}</span><small>${opening.assigned_count || 0}/${opening.required_count} đã duyệt · ${opening.pending_count || 0} chờ</small></div>`;
      }).join('')}</section>`;
    }).join('')}</div>`;
  }

  function requestItemAdmin(item) {
    const canReview = !['Đã duyệt', 'Đã rút'].includes(item.status);
    return `<div class="v64-request-item ${statusClass(item.status)}">
      <div><strong>${dayLabel(item.work_date)}</strong><span>${time5(item.start_time)}–${time5(item.end_time)}</span></div>
      <div>${badge(item.status)}</div>
      <div class="actions">
        ${canReview ? `<button class="btn tiny success" data-v64-action="item-status" data-id="${item.application_id}" data-status="Đã duyệt">Duyệt</button><button class="btn tiny secondary" data-v64-action="item-status" data-id="${item.application_id}" data-status="Danh sách chờ">Chờ</button><button class="btn tiny danger" data-v64-action="item-status" data-id="${item.application_id}" data-status="Từ chối">Từ chối</button>` : ''}
      </div>
    </div>`;
  }

  function weeklyRequestCard(request) {
    const target = Number(request.weekly_target_hours || 0);
    const shortfall = Math.max(target - Number(request.selected_hours || 0), 0);
    return `<article class="v64-request-card">
      <header>
        <div>${person(request.employee_name, `${request.employee_code || ''} · ${request.employee_role || ''} · ${request.employment_type || 'Part-time'}`)}</div>
        <div class="v64-request-state">${badge(request.status)}</div>
      </header>
      <div class="v64-request-metrics">
        <span><small>Đăng ký</small><strong>${request.selected_days || 0} ngày · ${request.selected_shifts || (request.items || []).length} ca · ${number(request.selected_hours || 0, 1)} giờ</strong></span>
        <span><small>Đã duyệt</small><strong>${request.approved_shifts || 0} ca / ${request.approved_days || 0} ngày</strong></span>
        <span><small>Ngày nghỉ</small><strong>${request.requested_day_off ? dateVN(request.requested_day_off) : 'Không cố định'}</strong></span>
        <span class="${shortfall > 0 && request.employment_type === 'Full-time' ? 'warn' : ''}"><small>So với mục tiêu</small><strong>${shortfall > 0 ? `Thiếu ${number(shortfall, 1)} giờ` : 'Đạt / vượt'}</strong></span>
      </div>
      ${request.employee_note ? `<p class="v64-request-note">${esc(request.employee_note)}</p>` : ''}
      <div class="v64-request-items">${(request.items || []).map(requestItemAdmin).join('')}</div>
      <footer>
        <button class="btn small success" data-v64-action="request-review" data-id="${request.id}" data-review="approve_all" ${request.status === 'Đã duyệt' ? 'disabled' : ''}>Duyệt toàn bộ phù hợp</button>
        <button class="btn small danger" data-v64-action="request-review" data-id="${request.id}" data-review="reject_all" ${(request.approved_days || 0) > 0 ? 'disabled' : ''}>Từ chối toàn bộ</button>
      </footer>
    </article>`;
  }

  renderSchedule = async function renderScheduleV64() {
    if (state.user.role !== 'admin') return navigate('dashboard');
    const range = weekRange64();
    const data = await api(`/api/page/shift-market?start=${range.start}&end=${range.end}`, { force: true });
    state.shiftMarket = data;
    state.cache.locations = data.locations;
    state.cache.employees = data.employees;
    const locations = data.locations || [];
    if (!state.v64LocationId || !locations.some((x) => Number(x.id) === Number(state.v64LocationId))) state.v64LocationId = locations[0]?.id || null;
    const requests = data.weekly_requests || [];
    const pendingCount = requests.filter((x) => ['Chờ duyệt', 'Duyệt một phần'].includes(x.status)).length;
    $('#page').innerHTML = `${intro('LỊCH LÀM THEO TUẦN', 'Đăng 2 ca cố định và duyệt một đơn cho cả tuần', 'Admin mở ca 09:00–17:00 và 17:00–23:00. Nhân viên có thể chọn một hoặc cả hai ca trong ngày, kể cả tuần sau.', `<button class="btn" data-v64-action="publish-week">${icons.plus} Đăng lịch tuần</button>`)}
      ${weekControls64()}
      <section class="v64-admin-summary">
        <div><small>Đơn đăng ký tuần</small><strong>${requests.length}</strong></div>
        <div><small>Cần xử lý</small><strong>${pendingCount}</strong></div>
        <div><small>Cửa hàng</small><select data-v64-location-admin>${locations.map((x) => `<option value="${x.id}" ${Number(x.id) === Number(state.v64LocationId) ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select></div>
      </section>
      <section class="card section-gap"><div class="card-head"><div><h3>Công suất 2 ca trong tuần</h3><p>Ca ngày 09:00–17:00 · Ca tối 17:00–23:00.</p></div></div><div class="card-body">${capacityBoard(data, state.v64LocationId)}</div></section>
      <section class="section-gap"><div class="section-title"><div><span>ĐƠN ĐĂNG KÝ CẢ TUẦN</span><h2>Admin duyệt theo nhân viên</h2></div><p>${pendingCount ? `Còn ${pendingCount} đơn cần xử lý.` : 'Không còn đơn chờ duyệt.'}</p></div>${requests.length ? `<div class="v64-request-list">${requests.map(weeklyRequestCard).join('')}</div>` : empty('Chưa có đơn đăng ký tuần', 'Nhân viên sẽ gửi một đơn gồm các ca đã chọn trong cả tuần.', 'calendar')}</section>
      <section class="card section-gap"><div class="card-head"><div><h3>Lịch chính thức trong tuần</h3><p>Chỉ ca đã duyệt mới xuất hiện tại đây và được đưa vào chấm công, tính lương.</p></div></div><div class="card-body">${officialWeekBoard(data.shifts || [], range.start)}</div></section>`;
  };

  function requestSelectionMap(request) {
    const map = new Map();
    (request?.items || []).forEach((item) => {
      if (!map.has(item.work_date)) map.set(item.work_date, new Set());
      map.get(item.work_date).add(String(item.opening_id));
    });
    return map;
  }

  function employeeWeeklyGrid(data, locationId, request) {
    const range = weekRange64();
    const grouped = openingsByDay(data, locationId);
    const selected = requestSelectionMap(request);
    const locked = request && !request.can_edit;
    return `<div class="v64-weekly-grid">${Array.from({ length: 7 }, (_, index) => {
      const date = isoLocal(addDays64(parseDate(range.start), index));
      const openings = grouped.get(date) || [];
      const current = selected.get(date) || new Set();
      const selectedCount = current.size;
      return `<section class="v64-register-day" data-v64-day="${date}">
        <header><strong>${dayLabel(date)}</strong><span data-v64-day-state>${selectedCount ? `Đã chọn ${selectedCount} ca` : 'Ngày nghỉ / không đăng ký'}</span></header>
        <div class="v64-shift-options">
          ${SHIFT_SPECS.map((spec) => {
            const opening = openings.find((x) => time5(x.start_time) === spec.start && time5(x.end_time) === spec.end);
            const disabled = locked || !opening || opening.status !== 'Mở đăng ký' || opening.remaining_slots === 0 && !opening.my_application;
            const checked = opening && current.has(String(opening.id));
            const note = !opening ? 'Chưa mở' : opening.status !== 'Mở đăng ký' ? opening.status : `Cần ${opening.required_count} · còn ${opening.remaining_slots}`;
            return `<label class="v64-shift-option ${spec.tone} ${disabled ? 'disabled' : ''}">
              <input type="checkbox" data-v64-opening data-date="${date}" value="${opening?.id || ''}" data-hours="${spec.hours}" ${checked ? 'checked' : ''} ${disabled ? 'disabled' : ''}>
              <span><b>${spec.label}</b><strong>${spec.start}–${spec.end}</strong><small>${esc(note)}</small></span>
            </label>`;
          }).join('')}
          <button type="button" class="v64-shift-off ${locked ? 'disabled' : ''}" data-v64-action="day-off" data-date="${date}" ${locked ? 'disabled' : ''}>
            <b>Nghỉ ngày này</b><span>Bỏ chọn cả hai ca</span>
          </button>
        </div>
      </section>`;
    }).join('')}</div>`;
  }

  function employeeRequestSummary(request, employmentType) {
    if (!request) return '<div class="info-banner"><div><strong>Chưa gửi đơn tuần</strong><span>Chọn một ca hoặc Nghỉ cho từng ngày rồi gửi một lần.</span></div></div>';
    return `<div class="v64-own-request ${statusClass(request.status)}">
      <div><small>Trạng thái đơn</small>${badge(request.status)}</div>
      <div><small>Đã chọn</small><strong>${request.selected_days} ngày · ${request.selected_shifts || (request.items || []).length} ca · ${number(request.selected_hours, 1)} giờ</strong></div>
      ${employmentType === 'Full-time' ? `<div><small>Ngày nghỉ</small><strong>${request.requested_day_off ? dateVN(request.requested_day_off) : 'Chưa xác định'}</strong></div>` : ''}
      <div><small>Kết quả</small><strong>${request.approved_shifts || 0} duyệt · ${request.waitlist_shifts || 0} chờ · ${request.rejected_shifts || 0} từ chối</strong></div>
    </div>`;
  }

  renderAvailability = async function renderAvailabilityV64() {
    if (state.user.role !== 'employee') return navigate('dashboard');
    const range = weekRange64();
    const data = await api(`/api/page/shift-market?start=${range.start}&end=${range.end}`, { force: true });
    state.shiftMarket = data;
    const request = data.weekly_request || null;
    const locations = data.locations || [];
    const requestLocation = request?.location_id;
    if (requestLocation) state.v64LocationId = requestLocation;
    if (!state.v64LocationId || !locations.some((x) => Number(x.id) === Number(state.v64LocationId))) state.v64LocationId = locations[0]?.id || null;
    const employmentType = state.user.employment_type || 'Part-time';
    const locked = request && !request.can_edit;
    $('#page').innerHTML = `${intro('ĐĂNG KÝ LỊCH CẢ TUẦN', 'Chọn 1 hoặc 2 ca mỗi ngày và gửi một đơn', employmentType === 'Full-time' ? 'Full-time đăng ký đúng 6 ngày làm và 1 ngày nghỉ; mỗi ngày có thể chọn ca ngày, ca tối hoặc cả hai.' : 'Part-time chọn các ca có thể làm; một ngày được chọn một hoặc cả hai ca.', '')}
      ${weekControls64()}
      <section class="v64-employee-toolbar">
        <div class="field"><label>Cửa hàng đăng ký</label><select data-v64-location-employee ${locked ? 'disabled' : ''}>${locations.map((x) => `<option value="${x.id}" ${Number(x.id) === Number(state.v64LocationId) ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select></div>
        ${employeeRequestSummary(request, employmentType)}
      </section>
      <form data-form="v64-submit-week" class="v64-week-form">
        <input type="hidden" name="week_start" value="${range.start}">
        ${employeeWeeklyGrid(data, state.v64LocationId, request)}
        <div class="v64-week-submit">
          <div class="v64-live-summary"><small>Lịch đang chọn</small><strong data-v64-selected-summary>0 ngày · 0 giờ</strong><span data-v64-rule-hint>${employmentType === 'Full-time' ? 'Yêu cầu: đúng 6 ngày làm, 1 ngày nghỉ; mỗi ngày 1 hoặc 2 ca.' : 'Chọn ít nhất một ca.'}</span></div>
          <div class="field"><label>Ghi chú cho quản lý</label><input name="employee_note" value="${esc(request?.employee_note || '')}" placeholder="Ví dụ: ưu tiên ca tối cuối tuần" ${locked ? 'disabled' : ''}></div>
          <div class="actions">
            ${request && request.can_edit ? `<button type="button" class="btn secondary" data-v64-action="withdraw-request" data-id="${request.id}">Rút đơn</button>` : ''}
            <button class="btn" type="submit" ${locked ? 'disabled' : ''}>${request ? 'Cập nhật và gửi lại' : 'Gửi đơn đăng ký cả tuần'}</button>
          </div>
        </div>
      </form>
      <section class="card section-gap"><div class="card-head"><div><h3>Lịch chính thức của tôi</h3><p>Chỉ các ngày được admin duyệt mới xuất hiện trong lịch chấm công.</p></div></div><div class="card-body">${officialWeekBoard(data.shifts || [], range.start)}</div></section>`;
    updateSelectedSummary();
  };

  function updateSelectedSummary() {
    const form = document.querySelector('[data-form="v64-submit-week"]');
    if (!form) return;
    const selected = [...form.querySelectorAll('input[data-v64-opening]:checked')];
    const distinctDays = new Set(selected.map((input) => input.dataset.date));
    const hours = selected.reduce((sum, input) => sum + Number(input.dataset.hours || 0), 0);
    const output = form.querySelector('[data-v64-selected-summary]');
    if (output) output.textContent = `${distinctDays.size} ngày · ${selected.length} ca · ${hours} giờ`;
    form.querySelectorAll('[data-v64-day]').forEach((dayCard) => {
      const count = dayCard.querySelectorAll('input[data-v64-opening]:checked').length;
      const stateEl = dayCard.querySelector('[data-v64-day-state]');
      if (stateEl) stateEl.textContent = count ? `Đã chọn ${count} ca${count === 2 ? ' · ca đôi' : ''}` : 'Ngày nghỉ / không đăng ký';
      dayCard.classList.toggle('double-selected', count === 2);
    });
    const hint = form.querySelector('[data-v64-rule-hint]');
    if (hint && state.user.employment_type === 'Full-time') {
      hint.textContent = distinctDays.size === 6 ? `Đủ 6 ngày làm và 1 ngày nghỉ · ${selected.length} ca.` : `Cần chọn đủ 6 ngày làm (hiện ${distinctDays.size} ngày).`;
      hint.classList.toggle('ok', distinctDays.size === 6);
    }
  }

  const previousHandleForm64 = handleForm;
  handleForm = async function handleFormV64(form) {
    const type = form.dataset.form;
    if (!type?.startsWith('v64-')) return previousHandleForm64(form);
    const submit = form.querySelector('button[type="submit"]');
    if (submit) submit.disabled = true;
    try {
      if (type === 'v64-publish-week') {
        const fd = new FormData(form);
        const body = Object.fromEntries(fd.entries());
        body.days = fd.getAll('days').map(Number);
        await api('/api/shift-market/weekly-openings', { method: 'POST', body });
        closeModal();
        toast('Đã đăng lịch 2 ca cho cả tuần');
        return renderSchedule();
      }
      if (type === 'v64-submit-week') {
        const selectedInputs = [...form.querySelectorAll('input[data-v64-opening]:checked')];
        const selections = selectedInputs.map((input) => Number(input.value)).filter(Boolean);
        const selectedDays = new Set(selectedInputs.map((input) => input.dataset.date));
        if (state.user.employment_type === 'Full-time' && selectedDays.size !== 6) throw new Error('Full-time phải đăng ký đúng 6 ngày làm và nghỉ 1 ngày; mỗi ngày có thể chọn 1 hoặc 2 ca');
        if (!selections.length) throw new Error('Hãy chọn ít nhất một ca trong tuần');
        await api('/api/shift-market/weekly-requests', {
          method: 'POST',
          body: {
            week_start: form.elements.week_start.value,
            opening_ids: selections,
            employee_note: form.elements.employee_note.value,
          },
        });
        toast('Đã gửi một đơn đăng ký cho cả tuần');
        return renderAvailability();
      }
    } catch (error) {
      toast(error.message, 'error');
    } finally {
      if (submit) submit.disabled = false;
    }
  };

  document.addEventListener('change', (event) => {
    if (event.target.matches('[data-v64-location-admin]')) {
      state.v64LocationId = Number(event.target.value);
      renderSchedule().catch((error) => toast(error.message, 'error'));
      return;
    }
    if (event.target.matches('[data-v64-location-employee]')) {
      state.v64LocationId = Number(event.target.value);
      renderAvailability().catch((error) => toast(error.message, 'error'));
      return;
    }
    if (event.target.closest('[data-form="v64-submit-week"]')) updateSelectedSummary();
  });

  document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-v64-action]');
    if (!button) return;
    const action = button.dataset.v64Action;
    try {
      if (action === 'publish-week') return openModal('Đăng lịch làm cho cả tuần', 'Mỗi ngày có 2 ca cố định: 09:00–17:00 và 17:00–23:00.', publishWeekForm(state.shiftMarket || {}), true);
      if (action === 'week') {
        state.shiftMarketWeekStart = isoLocal(addDays64(parseDate(state.shiftMarketWeekStart), Number(button.dataset.step || 0)));
        state.scheduleWeekStart = state.shiftMarketWeekStart;
        return state.user.role === 'admin' ? renderSchedule() : renderAvailability();
      }
      if (action === 'week-today') {
        state.shiftMarketWeekStart = currentWeekStart64();
        state.scheduleWeekStart = state.shiftMarketWeekStart;
        return state.user.role === 'admin' ? renderSchedule() : renderAvailability();
      }
      if (action === 'week-next') {
        state.shiftMarketWeekStart = isoLocal(addDays64(parseDate(currentWeekStart64()), 7));
        state.scheduleWeekStart = state.shiftMarketWeekStart;
        return state.user.role === 'admin' ? renderSchedule() : renderAvailability();
      }
      if (action === 'day-off') {
        const day = button.closest('[data-v64-day]');
        day?.querySelectorAll('input[data-v64-opening]').forEach((input) => { input.checked = false; });
        updateSelectedSummary();
        return;
      }
      if (action === 'item-status') {
        await api('/api/shift-market/applications/status', { method: 'POST', body: { id: Number(button.dataset.id), status: button.dataset.status } });
        toast(`Đã chuyển ngày làm sang ${button.dataset.status}`);
        return renderSchedule();
      }
      if (action === 'request-review') {
        const review = button.dataset.review;
        const message = review === 'approve_all' ? 'Duyệt toàn bộ các ngày còn phù hợp trong đơn này?' : 'Từ chối toàn bộ đơn đăng ký tuần này?';
        if (!confirm(message)) return;
        const result = await api('/api/shift-market/weekly-requests/review', { method: 'POST', body: { id: Number(button.dataset.id), action: review } });
        if (result.errors?.length) toast(`Đã duyệt ${result.approved_count} ngày; ${result.errors.length} ngày chuyển danh sách chờ`, 'warning');
        else toast('Đã xử lý đơn đăng ký cả tuần');
        return renderSchedule();
      }
      if (action === 'withdraw-request') {
        if (!confirm('Rút toàn bộ đơn đăng ký tuần này?')) return;
        await api('/api/shift-market/weekly-requests/withdraw', { method: 'POST', body: { id: Number(button.dataset.id) } });
        toast('Đã rút đơn đăng ký cả tuần');
        return renderAvailability();
      }
    } catch (error) {
      toast(error.message, 'error');
    }
  });

  window.RumiV64 = { version: VERSION, shiftSpecs: SHIFT_SPECS, allowDoubleShift: true, nextWeekRegistration: true };
})();
