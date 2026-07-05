'use strict';

/* RUMI 5.4 — ca mở đăng ký, duyệt ứng viên và quản lý Full-time. */
(() => {
  const VERSION = '5.4.0';
  const isoLocal = (value = new Date()) => {
    const d = new Date(value); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  };
  const parseDate = (value) => { const [y,m,d] = String(value).slice(0,10).split('-').map(Number); return new Date(y,m-1,d); };
  const addDays = (value, amount) => { const d = new Date(value); d.setDate(d.getDate()+amount); return d; };
  const monday = (value = new Date()) => { const d = new Date(value); d.setHours(0,0,0,0); const day=d.getDay()||7; d.setDate(d.getDate()-day+1); return d; };
  const weekText = (start) => `${parseDate(start).toLocaleDateString('vi-VN',{day:'2-digit',month:'2-digit'})} – ${addDays(parseDate(start),6).toLocaleDateString('vi-VN',{day:'2-digit',month:'2-digit',year:'numeric'})}`;
  const currentWeekStart = () => isoLocal(monday());
  const normalizeTime = (value) => String(value || '').slice(0,5);
  const payrollMonthLabel = (iso) => { const [y,m] = String(iso).slice(0,7).split('-'); return `Lương T${m}/${y}`; };
  const crossMonthNotice = (start) => {
    const first = parseDate(start), last = addDays(first, 6);
    if (first.getMonth() === last.getMonth()) return '';
    return `<div class="info-banner">${icons.info}<div><strong>Tuần giao tháng</strong><span>Mỗi ca được đưa vào bảng lương theo ngày làm của chính ca đó. Ví dụ ca 05-07 thuộc lương tháng 07, dù tuần bắt đầu từ tháng 06.</span></div></div>`;
  };
  const statusTone = (status) => /Đã chốt|Đã duyệt|Đã xác nhận/.test(status) ? 'green' : /Từ chối|Đã hủy/.test(status) ? 'red' : /Chờ|Mở/.test(status) ? 'amber' : 'gray';
  state.shiftMarketWeekStart = state.shiftMarketWeekStart || state.scheduleWeekStart || currentWeekStart();
  state.shiftMarket = state.shiftMarket || null;

  const employeeNav = navEmployee.find((item) => item[1] === 'availability');
  if (employeeNav) employeeNav[2] = 'Đăng ký ca làm';
  const adminNav = navAdmin.find((item) => item[1] === 'schedule');
  if (adminNav) adminNav[2] = 'Ca đăng ký & lịch';
  titles.schedule = 'Ca đăng ký & lịch tuần';
  titles.availability = 'Đăng ký ca làm';

  function weekRange() {
    const start = state.shiftMarketWeekStart;
    return { start, end: isoLocal(addDays(parseDate(start), 6)) };
  }

  function openingLabel(opening) {
    return `${dateVN(opening.work_date)} · ${normalizeTime(opening.start_time)}–${normalizeTime(opening.end_time)} · ${opening.location_name || 'RUMI'}`;
  }

  function miniMetric(label, value, tone='') {
    return `<span class="v54-mini ${tone}"><small>${esc(label)}</small><strong>${value}</strong></span>`;
  }

  function applicationRow(app, opening) {
    const disabled = opening.status === 'Đã chốt' || opening.status === 'Đã hủy';
    const reason = app.allowed ? `Dự kiến ${number(app.projected_week_hours,2)} giờ · ${app.projected_days} ngày` : app.reason;
    return `<div class="v54-application ${app.status === 'Chờ duyệt' ? 'is-pending' : ''}">
      ${person(app.employee_name, `${app.employee_code || ''} · ${app.employee_role || ''} · ${app.employment_type || 'Part-time'}`)}
      <div class="v54-app-score"><strong>${number(app.score,0)} điểm</strong><span>${esc(reason || '')}</span></div>
      <div>${badge(app.status)}</div>
      <div class="actions">
        <button class="btn small success" data-v54-action="application-status" data-id="${app.id}" data-status="Đã duyệt" ${disabled || !app.allowed ? 'disabled' : ''}>Duyệt</button>
        <button class="btn small secondary" data-v54-action="application-status" data-id="${app.id}" data-status="Danh sách chờ" ${disabled ? 'disabled' : ''}>Chờ</button>
        <button class="btn small danger" data-v54-action="application-status" data-id="${app.id}" data-status="Từ chối" ${disabled ? 'disabled' : ''}>Từ chối</button>
      </div>
    </div>`;
  }

  function openingCard(opening) {
    const apps = opening.applications || [];
    const canEdit = !['Đã chốt','Đã hủy'].includes(opening.status);
    return `<article class="v54-opening" data-opening="${opening.id}">
      <header class="v54-opening-head">
        <div><div class="v54-opening-time">${dateVN(opening.work_date)} · ${normalizeTime(opening.start_time)}–${normalizeTime(opening.end_time)}</div><h3>${esc(opening.location_name || 'RUMI')} · ${esc(opening.required_role || 'Bất kỳ vị trí')}</h3><p>${esc(opening.note || 'Không có ghi chú')} · ${esc(opening.eligible_employment_type || 'Tất cả')}</p></div>
        <div class="v54-opening-status">${badge(opening.status)}</div>
      </header>
      <div class="v54-opening-metrics">
        ${miniMetric('Cần', opening.required_count)}${miniMetric('Đã duyệt', opening.assigned_count, opening.assigned_count >= opening.required_count ? 'ok' : '')}${miniMetric('Chờ duyệt', opening.pending_count, opening.pending_count ? 'warn' : '')}${miniMetric('Còn thiếu', opening.remaining_slots, opening.remaining_slots ? 'danger' : 'ok')}
      </div>
      <div class="v54-opening-actions">
        ${opening.status === 'Nháp' ? `<button class="btn small" data-v54-action="opening-status" data-id="${opening.id}" data-status="Mở đăng ký">Mở đăng ký</button>` : ''}
        ${opening.status === 'Mở đăng ký' ? `<button class="btn small secondary" data-v54-action="opening-status" data-id="${opening.id}" data-status="Đã đóng">Đóng đăng ký</button>` : ''}
        ${opening.status === 'Đã đóng' ? `<button class="btn small secondary" data-v54-action="opening-status" data-id="${opening.id}" data-status="Mở đăng ký">Mở lại</button>` : ''}
        ${canEdit ? `<button class="btn small success" data-v54-action="opening-finalize" data-id="${opening.id}" data-force="${opening.remaining_slots ? '1' : '0'}">Chốt ca${opening.remaining_slots ? ' (đang thiếu)' : ''}</button><button class="btn small danger" data-v54-action="opening-status" data-id="${opening.id}" data-status="Đã hủy">Hủy ca</button>` : ''}
      </div>
      <details class="v54-applications" ${apps.some((x)=>x.status==='Chờ duyệt') ? 'open' : ''}>
        <summary>Ứng viên (${apps.length}) · ${opening.pending_count} đang chờ</summary>
        <div class="v54-application-list">${apps.length ? apps.map((app)=>applicationRow(app, opening)).join('') : empty('Chưa có nhân viên đăng ký','Ca đang mở sẽ xuất hiện trên tài khoản nhân viên.','users')}</div>
      </details>
    </article>`;
  }

  function complianceTable(rows) {
    if (!rows.length) return empty('Chưa có nhân viên Full-time','Chọn loại Full-time trong hồ sơ nhân viên để quản lý lịch 6 ngày/tuần.','users');
    return `<div class="table-wrap"><table><thead><tr><th>Nhân viên</th><th>Giờ tuần</th><th>Ngày làm</th><th>Ngày nghỉ</th><th>Cảnh báo</th></tr></thead><tbody>${rows.map((x)=>`<tr><td>${person(x.name,`${x.code || ''} · ${x.role || ''}`)}</td><td><strong>${number(x.hours,2)}/${number(x.target_hours,2)} giờ</strong></td><td>${x.days_worked}/${x.max_work_days} ngày · liên tiếp ${x.consecutive_days}</td><td>${x.day_off?.approved_date ? dateVN(x.day_off.approved_date) : badge(x.day_off?.status || 'Chưa đăng ký')}</td><td>${x.warnings?.length ? x.warnings.map((w)=>`<span class="v54-warning">${esc(w)}</span>`).join('') : '<span class="v54-ok">Đạt quy định</span>'}</td></tr>`).join('')}</tbody></table></div>`;
  }

  function dayOffAdmin(rows) {
    const pending = rows.filter((x)=>x.status==='Chờ duyệt');
    if (!rows.length) return empty('Chưa có đăng ký ngày nghỉ','Nhân viên Full-time chọn ngày nghỉ ưu tiên theo tuần.','calendar');
    return `<div class="v54-dayoff-list">${rows.map((x)=>`<div class="v54-dayoff"><div>${person(x.employee_name,`${x.employee_code || ''} · tuần ${dateVN(x.week_start)}`)}</div><div><strong>Ưu tiên ${dateVN(x.preferred_date)}</strong><span>Dự phòng ${x.alternate_date ? dateVN(x.alternate_date) : '—'} · ${esc(x.reason || 'Không ghi chú')}</span></div><div>${badge(x.status)}</div><div class="actions">${x.status==='Chờ duyệt'?`<button class="btn small success" data-v54-action="dayoff-status" data-id="${x.id}" data-status="Đã duyệt" data-date="${x.preferred_date}">Duyệt ưu tiên</button>${x.alternate_date?`<button class="btn small secondary" data-v54-action="dayoff-status" data-id="${x.id}" data-status="Đã duyệt" data-date="${x.alternate_date}">Duyệt dự phòng</button>`:''}<button class="btn small danger" data-v54-action="dayoff-status" data-id="${x.id}" data-status="Từ chối">Từ chối</button>`:''}</div></div>`).join('')}</div>${pending.length?`<div class="field-hint">Còn ${pending.length} yêu cầu ngày nghỉ cần xử lý.</div>`:''}`;
  }

  function weekBoard(shifts, start) {
    const days = Array.from({length:7},(_,i)=>addDays(parseDate(start),i));
    return `<div class="v54-week-board">${days.map((day)=>{ const iso=isoLocal(day); const rows=shifts.filter((x)=>x.shift_date===iso); return `<section class="v54-week-day"><header><strong>${day.toLocaleDateString('vi-VN',{weekday:'short'})}</strong><span>${day.toLocaleDateString('vi-VN',{day:'2-digit',month:'2-digit'})}</span></header>${rows.length?rows.map((x)=>`<div class="v54-week-shift"><b>${normalizeTime(x.start_time)}–${normalizeTime(x.end_time)}</b><span>${esc(x.employee_name || 'Chưa xếp')}</span><small>${esc(x.location_name || '')}</small><small class="v61-payroll-month">${payrollMonthLabel(x.shift_date)}</small></div>`).join(''):'<em>Trống</em>'}</section>`; }).join('')}</div>`;
  }

  renderSchedule = async function renderShiftMarketAdmin() {
    if (state.user.role !== 'admin') return navigate('dashboard');
    const range = weekRange();
    const data = await api(`/api/page/shift-market?start=${range.start}&end=${range.end}`, {force:true});
    state.shiftMarket = data; state.cache.locations = data.locations; state.cache.employees = data.employees;
    const openings = data.openings || [], compliance = data.compliance || [], shifts = data.shifts || [];
    const pending = openings.reduce((sum,x)=>sum+Number(x.pending_count||0),0);
    const missing = openings.reduce((sum,x)=>sum+Number(x.remaining_slots||0),0);
    $('#page').innerHTML = `${intro('CA ĐĂNG KÝ & LỊCH TUẦN','Admin đăng ca, nhân viên ứng tuyển, quản lý chốt lịch','Quy trình rõ ràng: đăng nhu cầu → nhận đơn → duyệt đủ người → từ chối đơn còn lại → chốt lịch chính thức.',`<button class="btn" data-v54-action="opening-add">${icons.plus} Đăng ca mới</button><button class="btn secondary" data-v54-action="auto-fulltime">Xếp Full-time tự động</button><button class="btn secondary" data-v5-action="schedule-xlsx" data-scope="schedule">Xuất Excel tuần</button>`)}
      <div class="v54-week-toolbar"><button class="btn small secondary" data-v54-action="week" data-step="-7">‹</button><strong>${weekText(range.start)}</strong><button class="btn small secondary" data-v54-action="week-today">Tuần này</button><button class="btn small secondary" data-v54-action="week" data-step="7">›</button></div>
      <section class="v5-summary-strip">${miniMetric('Ca đã đăng',openings.length)}${miniMetric('Đơn chờ duyệt',pending,pending?'warn':'ok')}${miniMetric('Vị trí còn thiếu',missing,missing?'danger':'ok')}${miniMetric('Full-time cần chú ý',compliance.filter((x)=>x.warnings?.length).length,compliance.some((x)=>x.warnings?.length)?'warn':'ok')}</section>
      <section class="v54-admin-grid"><div><div class="card"><div class="card-head"><div><h3>Ca đang tuyển và kết quả duyệt</h3><p>Mỗi ca chỉ chốt khi đã duyệt đủ số lượng cần.</p></div></div><div class="card-body v54-opening-list">${openings.length?openings.map(openingCard).join(''):empty('Chưa đăng ca nào','Bấm “Đăng ca mới” để nhân viên bắt đầu ứng tuyển.','calendar')}</div></div></div>
      <aside><div class="card"><div class="card-head"><div><h3>Ngày nghỉ Full-time</h3><p>Mỗi tuần phải có ít nhất 1 ngày nghỉ.</p></div></div><div class="card-body">${dayOffAdmin(data.day_offs||[])}</div></div></aside></section>
      <section class="card section-gap"><div class="card-head"><div><h3>Kiểm soát Full-time</h3><p>Cảnh báo thiếu giờ, vượt 6 ngày hoặc chưa duyệt ngày nghỉ.</p></div></div><div class="card-body">${complianceTable(compliance)}</div></section>
      <section class="card section-gap"><div class="card-head"><div><h3>Lịch chính thức trong tuần</h3><p>Chỉ các đơn đã duyệt mới tạo ca làm. Bảng lương lấy theo ngày làm của từng ca.</p></div></div><div class="card-body">${crossMonthNotice(range.start)}${weekBoard(shifts,range.start)}</div></section>`;
  };

  renderAvailability = async function renderOpenShiftsEmployee() {
    const range = weekRange();
    const data = await api(`/api/page/shift-market?start=${range.start}&end=${range.end}`, {force:true});
    state.shiftMarket = data;
    const employee = state.user;
    const rows = (data.openings||[]).filter((x)=>x.status==='Mở đăng ký' || x.my_application);
    const fullTime = employee.employment_type === 'Full-time';
    const dayOff = (data.day_offs||[]).find((x)=>x.week_start===range.start);
    $('#page').innerHTML = `${intro('ĐĂNG KÝ CA LÀM','Chọn ca phù hợp và chờ admin duyệt','Đăng ký không đồng nghĩa đã được xếp. Chỉ ca có trạng thái “Đã duyệt” mới xuất hiện trong lịch chính thức và chấm công.')}
      <div class="v54-week-toolbar"><button class="btn small secondary" data-v54-action="week" data-step="-7">‹</button><strong>${weekText(range.start)}</strong><button class="btn small secondary" data-v54-action="week-today">Tuần này</button><button class="btn small secondary" data-v54-action="week" data-step="7">›</button></div>
      ${fullTime?`<section class="card"><div class="card-head"><div><h3>Ngày nghỉ tuần Full-time</h3><p>Bạn chỉ cần chọn ngày muốn nghỉ; admin sẽ cân đối lịch làm 6 ngày còn lại.</p></div>${dayOff?badge(dayOff.status):''}</div><div class="card-body"><form class="form-grid" data-form="v54-dayoff-create"><input type="hidden" name="week_start" value="${range.start}"><div class="field"><label>Ngày nghỉ ưu tiên</label><input type="date" name="preferred_date" min="${range.start}" max="${range.end}" value="${dayOff?.preferred_date||range.end}" required></div><div class="field"><label>Ngày dự phòng</label><input type="date" name="alternate_date" min="${range.start}" max="${range.end}" value="${dayOff?.alternate_date||''}"></div><div class="field span-2"><label>Lý do / mong muốn</label><input name="reason" value="${esc(dayOff?.reason||'')}" placeholder="Ví dụ: việc gia đình"></div><div class="form-actions"><button class="btn" type="submit">Gửi ngày nghỉ ưu tiên</button></div></form></div></section>`:''}
      <section class="v54-employee-openings section-gap">${rows.length?rows.map((x)=>{const app=x.my_application, rule=x.rule||{}; const canApply=x.status==='Mở đăng ký' && rule.allowed && !app; return `<article class="v54-employee-opening"><header><div><span>${dateVN(x.work_date)}</span><h3>${normalizeTime(x.start_time)}–${normalizeTime(x.end_time)} · ${esc(x.location_name||'RUMI')}</h3><p>${esc(x.required_role||'Bất kỳ vị trí')} · cần ${x.required_count} người · còn ${x.remaining_slots} vị trí</p></div>${badge(app?.status||x.status)}</header><div class="v54-opening-rule ${rule.allowed?'ok':'blocked'}">${rule.allowed?`Phù hợp · dự kiến ${number(rule.projected_week_hours,2)} giờ / ${rule.projected_days} ngày trong tuần`:esc(rule.reason||'Không thể đăng ký')}</div><p>${esc(x.note||'Không có ghi chú')}</p><div class="actions">${canApply?`<button class="btn" data-v54-action="apply" data-id="${x.id}">Đăng ký ca</button>`:''}${app&&['Chờ duyệt','Danh sách chờ'].includes(app.status)?`<button class="btn secondary" data-v54-action="withdraw" data-id="${app.id}">Rút đơn</button>`:''}${app?.status==='Đã duyệt'?'<span class="v54-ok">Bạn đã được xếp vào ca này</span>':''}</div></article>`;}).join(''):empty('Không có ca đang mở','Admin chưa đăng nhu cầu làm việc trong tuần này.','calendar')}</section>`;
  };

  employeeForm = function employeeFormV54(x = null) {
    const type = x?.employment_type || 'Part-time';
    return `<form class="form-grid" data-form="${x?'employee-edit':'employee-create'}" data-id="${x?.id||''}">
      <div class="field"><label>Mã nhân viên</label><input name="code" required value="${esc(x?.code||'')}" placeholder="NV001"></div><div class="field"><label>Họ và tên</label><input name="name" required value="${esc(x?.name||'')}"></div>
      <div class="field"><label>Số điện thoại</label><input name="phone" value="${esc(x?.phone||'')}"></div><div class="field"><label>Email</label><input type="email" name="email" value="${esc(x?.email||'')}"></div>
      <div class="field"><label>Vị trí công việc</label><select name="job_role">${['Pha chế','Thu ngân','Phục vụ','Nhân viên'].map((r)=>`<option ${x?.role===r?'selected':''}>${r}</option>`).join('')}</select></div><div class="field"><label>Loại nhân viên</label><select name="employment_type"><option ${type==='Full-time'?'selected':''}>Full-time</option><option ${type==='Part-time'?'selected':''}>Part-time</option></select></div>
      <div class="field"><label>Lương theo giờ</label><input type="number" name="hourly_wage" min="0" value="${esc(x?.hourly_wage||25000)}"></div><div class="field"><label>Giờ mục tiêu/tuần</label><input type="number" step="0.5" name="weekly_target_hours" min="0" value="${esc(x?.weekly_target_hours ?? (type==='Full-time'?48:24))}"></div>
      <div class="field"><label>Giờ tối đa/tuần</label><input type="number" step="0.5" name="max_weekly_hours" min="1" value="${esc(x?.max_weekly_hours||48)}"></div><div class="field"><label>Giờ tối đa/ngày</label><input type="number" step="0.5" name="max_daily_hours" min="1" value="${esc(x?.max_daily_hours||8)}"></div>
      <div class="field"><label>Ngày làm liên tiếp tối đa</label><input type="number" name="max_consecutive_days" min="1" max="7" value="${esc(x?.max_consecutive_days||6)}"></div><div class="field"><label>Số ngày nghỉ/tuần</label><input type="number" name="weekly_days_off" min="0" max="6" value="${esc(x?.weekly_days_off ?? (type==='Full-time'?1:0))}"></div>
      <div class="field"><label>Ngày bắt đầu</label><input type="date" name="joined_at" value="${esc(x?.joined_at||today())}"></div>${x?`<div class="field"><label>Trạng thái</label><select name="status"><option ${x.status==='Đang làm'?'selected':''}>Đang làm</option><option ${x.status==='Tạm nghỉ'?'selected':''}>Tạm nghỉ</option><option ${x.status==='Đã nghỉ việc'?'selected':''}>Đã nghỉ việc</option></select></div><div class="field span-2"><label>Tên đăng nhập</label><input name="username" required value="${esc(x.username||'')}"></div>`:`<div class="field"><label>Tên đăng nhập</label><input name="username" required></div><div class="field span-2"><label>Mật khẩu ban đầu</label><input type="password" name="password" minlength="8" required></div>`}
      <div class="form-actions"><button type="button" class="btn secondary" data-action="close-modal">Hủy</button><button class="btn" type="submit">${icons.check} Lưu nhân viên</button></div></form>`;
  };

  const legacyRenderEmployees = renderEmployees;
  renderEmployees = async function renderEmployeesV54() {
    if (state.user.role !== 'admin') return navigate('dashboard');
    const rows = await api('/api/employees', {force:true}); state.cache.employees=rows;
    $('#page').innerHTML = `${intro('NHÂN SỰ RUMI','Full-time và Part-time','Thiết lập mục tiêu giờ, giới hạn làm việc và ngày nghỉ để hệ thống xếp lịch đúng quy định.',`<button class="btn" data-action="employee-add">${icons.plus} Thêm nhân viên</button>`)}<div class="table-wrap"><table><thead><tr><th>Nhân viên</th><th>Loại</th><th>Vị trí</th><th>Quy định tuần</th><th>Lương/giờ</th><th>Tài khoản</th><th>Trạng thái</th><th></th></tr></thead><tbody>${rows.map((x)=>`<tr><td>${person(x.name,x.code)}</td><td>${badge(x.employment_type||'Part-time')}</td><td>${esc(x.role)}</td><td><strong>${number(x.weekly_target_hours,1)} giờ mục tiêu</strong><br><small>Tối đa ${number(x.max_weekly_hours,1)} giờ · nghỉ ${x.weekly_days_off||0} ngày</small></td><td>${money(x.hourly_wage)}</td><td>${esc(x.username||'—')}</td><td>${badge(x.status)}</td><td><div class="actions"><button class="btn small secondary" data-action="employee-edit" data-id="${x.id}">${icons.edit}</button><button class="btn small secondary" data-action="employee-reset" data-id="${x.id}">${icons.key}</button><button class="btn small danger" data-action="employee-delete" data-id="${x.id}">${icons.trash}</button></div></td></tr>`).join('')}</tbody></table></div>`;
  };

  function openingForm() {
    const locations = state.shiftMarket?.locations || [];
    const roles = [...new Set((state.shiftMarket?.employees||[]).map((x)=>x.role).filter(Boolean))];
    const tomorrow = isoLocal(addDays(new Date(),1));
    return `<form class="form-grid" data-form="v54-opening-create"><div class="field"><label>Ngày làm</label><input type="date" name="work_date" min="${today()}" value="${tomorrow}" required></div><div class="field"><label>Cửa hàng</label><select name="location_id" required><option value="">Chọn cửa hàng</option>${locations.map((x)=>`<option value="${x.id}">${esc(x.name)}</option>`).join('')}</select></div><div class="field"><label>Bắt đầu</label><input type="time" name="start_time" value="08:00" required></div><div class="field"><label>Kết thúc</label><input type="time" name="end_time" value="16:00" required></div><div class="field"><label>Vị trí cần</label><select name="required_role"><option value="">Bất kỳ</option>${roles.map((r)=>`<option>${esc(r)}</option>`).join('')}</select></div><div class="field"><label>Số người cần</label><input type="number" name="required_count" min="1" max="50" value="1" required></div><div class="field"><label>Loại nhân viên</label><select name="eligible_employment_type"><option>Tất cả</option><option>Full-time</option><option>Part-time</option></select></div><div class="field"><label>Hạn đăng ký</label><input type="datetime-local" name="application_deadline"></div><div class="field"><label>Trạng thái</label><select name="status"><option>Mở đăng ký</option><option>Nháp</option></select></div><div class="field span-2"><label>Ghi chú công việc</label><textarea name="note" placeholder="Ví dụ: ưu tiên biết thu ngân"></textarea></div><div class="form-actions"><button type="button" class="btn secondary" data-action="close-modal">Hủy</button><button class="btn" type="submit">Đăng ca</button></div></form>`;
  }

  const oldHandleForm = handleForm;
  handleForm = async function handleFormV54(form) {
    const type = form.dataset.form;
    if (!type?.startsWith('v54-')) return oldHandleForm(form);
    const data = Object.fromEntries(new FormData(form).entries());
    const submit = form.querySelector('button[type="submit"]'); if (submit) submit.disabled=true;
    try {
      if (type === 'v54-opening-create') { await api('/api/shift-market/openings',{method:'POST',body:data}); closeModal(); toast('Đã đăng ca cho nhân viên đăng ký'); return renderSchedule(); }
      if (type === 'v54-dayoff-create') { await api('/api/shift-market/day-offs',{method:'POST',body:data}); toast('Đã gửi ngày nghỉ ưu tiên'); return renderAvailability(); }
    } catch (error) { toast(error.message,'error'); } finally { if (submit) submit.disabled=false; }
  };

  document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-v54-action]'); if (!button) return;
    const action=button.dataset.v54Action, id=Number(button.dataset.id||0);
    try {
      if (action==='opening-add') return openModal('Đăng ca làm mới','Nhân viên sẽ thấy ca này và gửi đơn đăng ký.',openingForm(),true);
      if (action==='opening-status') { if (button.dataset.status==='Đã hủy'&&!confirm('Hủy ca này và từ chối toàn bộ đơn đăng ký?')) return; await api('/api/shift-market/openings/status',{method:'POST',body:{id,status:button.dataset.status}}); toast('Đã cập nhật ca'); return renderSchedule(); }
      if (action==='opening-finalize') { const force=button.dataset.force==='1'; if (!confirm(force?'Ca đang thiếu người. Vẫn chốt và từ chối các đơn còn lại?':'Chốt ca và từ chối các đơn chưa được duyệt?')) return; await api('/api/shift-market/openings/finalize',{method:'POST',body:{id,force,waitlist_count:0}}); toast('Đã chốt ca chính thức'); return renderSchedule(); }
      if (action==='application-status') { await api('/api/shift-market/applications/status',{method:'POST',body:{id,status:button.dataset.status}}); toast(`Đã chuyển đơn sang ${button.dataset.status}`); return renderSchedule(); }
      if (action==='dayoff-status') { await api('/api/shift-market/day-offs/status',{method:'POST',body:{id,status:button.dataset.status,approved_date:button.dataset.date||''}}); toast('Đã xử lý ngày nghỉ tuần'); return renderSchedule(); }
      if (action==='apply') { await api('/api/shift-market/apply',{method:'POST',body:{opening_id:id}}); toast('Đã đăng ký ca, chờ admin duyệt'); return renderAvailability(); }
      if (action==='withdraw') { if (!confirm('Rút đơn đăng ký ca này?')) return; await api('/api/shift-market/applications/withdraw',{method:'POST',body:{id}}); toast('Đã rút đơn'); return renderAvailability(); }
      if (action==='auto-fulltime') { if (!confirm(`Tự động xếp nhân viên Full-time cho tuần ${weekText(state.shiftMarketWeekStart)}?`)) return; const result=await api('/api/shift-market/auto-fulltime',{method:'POST',body:{week_start:state.shiftMarketWeekStart}}); toast(`Đã xếp ${result.created_count} ca Full-time`); return renderSchedule(); }
      if (action==='week') { state.shiftMarketWeekStart=isoLocal(addDays(parseDate(state.shiftMarketWeekStart),Number(button.dataset.step||0))); state.scheduleWeekStart=state.shiftMarketWeekStart; return (state.user.role==='admin'?renderSchedule():renderAvailability()); }
      if (action==='week-today') { state.shiftMarketWeekStart=currentWeekStart(); state.scheduleWeekStart=state.shiftMarketWeekStart; return (state.user.role==='admin'?renderSchedule():renderAvailability()); }
    } catch (error) { toast(error.message,'error'); }
  });

  window.RumiV54 = {version:VERSION};
})();
