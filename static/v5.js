'use strict';

/* RUMI 5.0 enhancement layer. It uses the existing authenticated API and
   keeps all business rules on the Python/PostgreSQL backend. */

window.RumiV5 = (() => {
  const VERSION = '6.5.0';
  const pageNode = () => document.querySelector('#page');
  const localISO = (date) => {
    const d = new Date(date);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  };
  const parseLocalDate = (value) => {
    const [y, m, d] = String(value).slice(0, 10).split('-').map(Number);
    return new Date(y, (m || 1) - 1, d || 1);
  };
  const addDays = (date, amount) => {
    const next = new Date(date);
    next.setDate(next.getDate() + amount);
    return next;
  };
  const mondayOf = (date = new Date()) => {
    const d = new Date(date);
    d.setHours(0, 0, 0, 0);
    const day = d.getDay() || 7;
    d.setDate(d.getDate() - day + 1);
    return d;
  };
  const weekLabel = (start) => {
    const end = addDays(start, 6);
    return `${start.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })} – ${end.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' })}`;
  };
  const dayLabel = (date) => date.toLocaleDateString('vi-VN', { weekday: 'short' }).replace('Th ', 'T');
  const normalize = (value) => String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const byDateTime = (a, b) => `${a.shift_date || a.work_date} ${a.start_time || a.check_in || ''}`.localeCompare(`${b.shift_date || b.work_date} ${b.start_time || b.check_in || ''}`);
  const total = (rows, key) => rows.reduce((sum, row) => sum + Number(row[key] || 0), 0);
  const unique = (rows, key) => new Set(rows.map((row) => row[key]).filter(Boolean)).size;
  const noValidClock = (x) => normalize(`${x?.status || ''} ${x?.calculation_note || ''} ${x?.note || ''}`).includes('khong co cham cong') || normalize(x?.status || '').includes('tu choi cham cong');
  const formatClockValue = (value, fallback = '—') => {
    if (!value) return fallback;
    const text = String(value);
    const match = text.match(/\d{2}:\d{2}/);
    return match ? match[0] : text.slice(0, 5);
  };
  const clockRange = (x) => noValidClock(x) ? '— – —' : `${formatClockValue(x.check_in || x.check_in_at)} – ${formatClockValue(x.check_out || x.check_out_at, 'Chưa ra')}`;
  const compactMoney = (value) => {
    const n = Number(value || 0);
    if (n >= 1_000_000_000) return `${number(n / 1_000_000_000, 1)} tỷ`;
    if (n >= 1_000_000) return `${number(n / 1_000_000, 1)} triệu`;
    if (n >= 1_000) return `${number(n / 1_000, 0)} nghìn`;
    return number(n);
  };

  state.scheduleWeekStart = state.scheduleWeekStart || localISO(mondayOf());
  state.myWeekStart = state.myWeekStart || localISO(mondayOf());
  state.scheduleLocationFilter = state.scheduleLocationFilter || '';
  state.v5Filters = state.v5Filters || {};

  const summaryItem = (label, value, note = '') => `
    <div class="v5-summary-item">
      <span>${esc(label)}</span><strong>${value}</strong><small>${esc(note)}</small>
    </div>`;

  const priorityItem = (tone, icon, title, text, page) => `
    <button class="v5-priority ${tone}" data-nav="${page}">
      <span class="v5-priority-icon">${icons[icon]}</span>
      <span class="v5-priority-copy"><strong>${esc(title)}</strong><span>${esc(text)}</span></span>
      ${icons.chevron || '<svg viewBox="0 0 24 24"><path d="m9 18 6-6-6-6"/></svg>'}
    </button>`;

  const quickAction = (page, icon, title, text) => `
    <button class="v5-action" data-nav="${page}">
      <span>${icons[icon]}</span><span><strong>${esc(title)}</strong><small>${esc(text)}</small></span>
    </button>`;

  const attendanceAlertList = (rows = [], admin = false) => rows.length ? `<div class="v62-alert-list">${rows.map((x) => {
    const shift = x.shift || {};
    const time = `${String(shift.start_time || '').slice(0,5)}–${String(shift.end_time || '').slice(0,5)}`;
    const statusClass = x.severity === 'danger' ? 'danger' : (x.severity === 'warning' ? 'warning' : 'info');
    return `<article class="v62-attendance-alert ${statusClass}">
      <span class="v62-alert-pulse"></span>
      <div class="v62-alert-copy"><strong>${esc(x.status)}</strong><span>${admin ? `${esc(x.employee_name || 'Nhân viên')} · ` : ''}${dateVN(shift.shift_date)} · ${esc(time)} · ${esc(x.location_name || 'RUMI')}</span>${x.minutes_late ? `<small>Đã trễ ${x.minutes_late} phút</small>` : ''}</div>
      <div class="v62-alert-actions">${admin ? `<button class="btn small secondary" data-v5-action="attendance-remind" data-id="${x.id}">Nhắc ngay</button><button class="btn small secondary" data-nav="schedule">Tìm người thay</button>${x.status === 'Vắng ca' ? `<button class="btn small danger" data-v5-action="attendance-resolve" data-mode="absent" data-id="${x.id}">Xác nhận vắng</button>` : `<button class="btn small ghost" data-v5-action="attendance-resolve" data-mode="dismiss" data-id="${x.id}">Đã kiểm tra</button>`}` : `<button class="btn small" data-nav="attendance">Mở chấm công</button>`}</div>
    </article>`;
  }).join('')}</div>` : '';

  const exportButton = (kind, label = 'Xuất CSV') => `<button class="btn secondary" data-v5-action="export" data-export="${kind}">
    <svg viewBox="0 0 24 24"><path d="M12 3v12m0 0 4-4m-4 4-4-4M4 19h16"/></svg>${esc(label)}</button>`;

  const excelWeekButton = (scope = 'schedule', label = 'Xuất Excel tuần') => `<button class="btn secondary" data-v5-action="schedule-xlsx" data-scope="${scope}">
    <svg viewBox="0 0 24 24"><path d="M7 3h7l4 4v14H7zM14 3v5h5M9 12l5 5m0-5-5 5"/></svg>${esc(label)}</button>`;

  const filterToolbar = (content) => `<div class="toolbar"><div class="v5-filter-row">${content}</div></div>`;

  function renderWeekBoard(rows, startDate, admin = false) {
    const sorted = [...rows].sort(byDateTime);
    const todayValue = localISO(new Date());
    const days = Array.from({ length: 7 }, (_, index) => addDays(startDate, index));
    return `<div class="v5-week-scroll"><div class="v5-week-board">${days.map((date) => {
      const iso = localISO(date);
      const dayRows = sorted.filter((row) => row.shift_date === iso);
      return `<section class="v5-day ${iso === todayValue ? 'is-today' : ''}">
        <div class="v5-day-head"><strong>${esc(dayLabel(date))}</strong><span>${date.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })}</span></div>
        ${dayRows.length ? dayRows.map((row) => `
          <article class="v5-shift" data-location="${esc(row.location_id || '')}">
            <div class="v5-shift-time">${esc(row.start_time)} – ${esc(row.end_time)}</div>
            <strong>${esc(admin ? (row.employee_name || 'Chưa có nhân viên') : (row.location_name || 'RUMI'))}</strong>
            <small>${esc(admin ? (row.location_name || 'Chưa gắn cửa hàng') : (row.location_address || 'Chưa có địa chỉ'))}</small>
            <div style="margin-top:7px">${badge(row.attendance?.status || row.status)}</div>
            <div class="v5-shift-actions">
              ${admin ? `<button class="btn secondary" data-action="shift-candidates" data-id="${row.id}">Tìm người thay</button><button class="btn ghost" data-action="shift-delete" data-id="${row.id}">Xóa</button>` : `<button class="btn secondary" data-action="request-shift" data-id="${row.id}">Cần người thay</button>`}
            </div>
          </article>`).join('') : '<div class="v5-day-empty">Không có ca</div>'}
      </section>`;
    }).join('')}</div></div>`;
  }

  function tableLabels() {
    document.querySelectorAll('.table-wrap table').forEach((table) => {
      table.classList.add('responsive-table');
      const labels = [...table.querySelectorAll('thead th')].map((th) => th.textContent.trim());
      table.querySelectorAll('tbody tr').forEach((row) => {
        [...row.children].forEach((cell, index) => {
          if (!cell.getAttribute('data-label')) cell.setAttribute('data-label', labels[index] || 'Thông tin');
        });
      });
    });
  }

  function setupTopbar() {
    const actions = document.querySelector('.topbar-actions');
    if (!actions || document.querySelector('#v5-search-button')) return;
    const search = document.createElement('button');
    search.id = 'v5-search-button';
    search.className = 'icon-button';
    search.type = 'button';
    search.dataset.v5Action = 'command';
    search.title = 'Tìm nhanh (/)' ;
    search.setAttribute('aria-label', 'Tìm nhanh');
    search.innerHTML = `${icons.search}<span class="v5-shortcut" style="position:absolute;right:-8px;bottom:-8px">/</span>`;
    const refresh = document.createElement('button');
    refresh.id = 'v5-refresh-button';
    refresh.className = 'icon-button';
    refresh.type = 'button';
    refresh.dataset.v5Action = 'refresh';
    refresh.title = 'Làm mới dữ liệu';
    refresh.setAttribute('aria-label', 'Làm mới dữ liệu');
    refresh.innerHTML = '<svg viewBox="0 0 24 24"><path d="M20 11a8 8 0 1 0-2.34 5.66M20 4v7h-7"/></svg>';
    const notification = actions.querySelector('.notification-button');
    actions.insertBefore(refresh, notification || actions.firstChild);
    actions.insertBefore(search, refresh);
  }

  function setupVersion() {
    document.querySelectorAll('.v5-version').forEach((node) => node.remove());
    document.title = 'RUMI Manager 6.2 — Cảnh báo công & PDF lương';
  }

  function setupMobileNav() {
    if (!state.user) return;
    let nav = document.querySelector('#v5-mobile-nav');
    if (!nav) {
      nav = document.createElement('nav');
      nav.id = 'v5-mobile-nav';
      nav.className = 'v5-mobile-nav';
      document.body.appendChild(nav);
    }
    const items = state.user.role === 'admin'
      ? [['dashboard','dashboard','Tổng quan'],['schedule','calendar','Xếp ca'],['requests','request','Duyệt'],['inventory','box','Kho'],['employees','users','Nhân sự']]
      : [['dashboard','dashboard','Tổng quan'],['shifts','calendar','Lịch'],['attendance','gps','Chấm công'],['availability','request','Lịch rảnh'],['inventory','box','Kho']];
    nav.innerHTML = items.map(([page, icon, label]) => `<button class="${state.page === page ? 'active' : ''}" data-nav="${page}">${icons[icon]}<span>${esc(label)}</span></button>`).join('');
  }

  function updateCountdowns() {
    document.querySelectorAll('[data-countdown]').forEach((node) => {
      const target = new Date(node.dataset.countdown).getTime();
      if (!Number.isFinite(target)) return;
      const diff = target - Date.now();
      if (diff <= 0) {
        node.textContent = 'Đã đến giờ';
        return;
      }
      const minutes = Math.floor(diff / 60000);
      const days = Math.floor(minutes / 1440);
      const hours = Math.floor((minutes % 1440) / 60);
      const mins = minutes % 60;
      node.textContent = days ? `${days} ngày ${hours} giờ` : `${hours} giờ ${String(mins).padStart(2, '0')} phút`;
    });
  }

  function afterRender() {
    setupTopbar();
    setupVersion();
    setupMobileNav();
    tableLabels();
    updateCountdowns();
    pageNode()?.classList.add('v5-fade');
    window.setTimeout(() => pageNode()?.classList.remove('v5-fade'), 350);
  }

  /* ------------------------------------------------------------------
     Dashboard
  ------------------------------------------------------------------ */
  renderDashboard = async function renderDashboardV5() {
    const d = takeDashboardData() || await api('/api/dashboard');
    applyUnreadCount(d.unread_count, false);
    const s = d.stats;
    if (state.user.role === 'admin') {
      const urgent = [];
      if (s.attendance_alerts) urgent.push(priorityItem(s.attendance_danger ? 'danger' : 'warning', 'clock', `${s.attendance_alerts} cảnh báo chấm công`, s.attendance_danger ? 'Có ca nguy cơ vắng hoặc thiếu giờ ra.' : 'Có nhân viên đến giờ nhưng chưa chấm công.', 'attendance'));
      if (s.pending_schedule) urgent.push(priorityItem('warning', 'calendar', `${s.pending_schedule} lịch rảnh đang chờ`, 'Duyệt để có thể xếp ca đúng nguyện vọng.', 'requests'));
      if (s.pending_requests) urgent.push(priorityItem('danger', 'request', `${s.pending_requests} yêu cầu nghỉ / thay ca`, 'Xử lý sớm để không thiếu người trong ca.', 'requests'));
      if (s.low_stock) urgent.push(priorityItem('danger', 'box', `${s.low_stock} nguyên liệu dưới định mức`, 'Kiểm tra tồn kho và danh sách cần mua.', 'inventory'));
      if (s.pending_purchase) urgent.push(priorityItem('warning', 'cart', `${s.pending_purchase} mặt hàng đang chờ mua`, 'Đánh dấu sau khi đã bổ sung nguyên liệu.', 'purchases'));
      if (!urgent.length) urgent.push(priorityItem('success', 'check', 'Vận hành đang ổn định', 'Không có công việc khẩn cấp cần xử lý.', 'dashboard'));
      pageNode().innerHTML = `
        <section class="hero-card">
          <div class="hero-copy"><span class="v5-kicker">RUMI OPERATIONS</span><h2>Chào quản lý, hôm nay quán đang vận hành thế nào?</h2><p>Mọi thông tin quan trọng về ca làm, nhân viên, chấm công, lương và nguyên liệu được gom lại trong một nơi.</p>
            <div class="v5-hero-meta"><span>${icons.users} ${s.employees} nhân viên</span><span>${icons.calendar} ${s.shifts_today} ca hôm nay</span><span>${icons.clock} ${s.working_now} người đang làm</span></div>
          </div>
          <div class="hero-actions"><button class="btn secondary" data-nav="schedule">${icons.calendar} Xếp lịch</button><button class="btn secondary" data-nav="requests">${icons.request} Duyệt yêu cầu</button></div>
        </section>
        <section class="stats-grid">
          ${stat('Nhân viên hoạt động', s.employees, 'Tài khoản đang sử dụng', 'users')}
          ${stat('Ca làm hôm nay', s.shifts_today, 'Theo lịch đã xếp', 'calendar', 'blue')}
          ${stat('Đang trong ca', s.working_now, 'Đã chấm công vào', 'clock', 'green')}
          ${stat('Lương dự kiến', money(s.payroll_total), 'Tháng hiện tại', 'money', 'green')}
        </section>
        <section class="v5-priority-grid">
          <div class="card"><div class="card-head"><div><h3>Ưu tiên cần xử lý</h3><p>RUMI tự tổng hợp theo dữ liệu mới nhất</p></div></div><div class="card-body"><div class="v5-priority-list">${urgent.join('')}</div></div></div>
          <div class="card"><div class="card-head"><div><h3>Thao tác nhanh</h3><p>Đi thẳng đến công việc thường dùng</p></div></div><div class="card-body"><div class="v5-action-grid">
            ${quickAction('employees','users','Thêm nhân viên','Tạo tài khoản và hồ sơ')}
            ${quickAction('schedule','calendar','Xếp ca mới','Tìm người đang rảnh')}
            ${quickAction('attendance','clock','Kiểm tra công','Đi trễ và thiếu chấm công')}
            ${quickAction('inventory','box','Nhập kho','Cập nhật nguyên liệu')}
          </div></div></div>
        </section>
        ${d.attendance_alerts?.length ? `<section class="card section-gap v62-alert-panel"><div class="card-head"><div><h3>Cảnh báo chấm công theo thời gian thực</h3><p>Hệ thống dùng giờ máy chủ để phát hiện ca chưa chấm vào/ra.</p></div><button class="btn small secondary" data-nav="attendance">Xử lý tất cả</button></div><div class="card-body">${attendanceAlertList(d.attendance_alerts, true)}</div></section>` : ''}
        <section class="grid-2 section-gap">
          <div class="card"><div class="card-head"><div><h3>Ca làm hôm nay</h3><p>Tiến độ theo từng nhân viên</p></div><button class="btn small secondary" data-nav="schedule">Xem lịch tuần</button></div><div class="card-body">${shiftList(d.today_shifts)}</div></div>
          <div class="card"><div class="card-head"><div><h3>Thông báo mới</h3><p>Các thay đổi gần đây</p></div><button class="btn small secondary" data-nav="notifications">Xem tất cả</button></div><div class="card-body">${notificationList(d.notifications)}</div></div>
        </section>`;
    } else {
      const next = [...(d.upcoming_shifts || [])].sort(byDateTime)[0];
      const target = next ? `${next.shift_date}T${next.start_time}:00` : '';
      pageNode().innerHTML = `
        <section class="hero-card">
          <div class="hero-copy"><span class="v5-kicker">CA LÀM CỦA BẠN</span><h2>Chào ${esc(state.user.name)}, sẵn sàng cho một ca thật tốt.</h2><p>Xem lịch, chấm công GPS và theo dõi lương theo giờ ngay trên điện thoại.</p>
          ${next ? `<div class="v5-hero-meta"><span>${icons.calendar} Ca tiếp theo ${dateVN(next.shift_date)}</span><span>${icons.clock} ${esc(next.start_time)}–${esc(next.end_time)}</span><span>${icons.location} ${esc(next.location_name || 'RUMI')}</span></div>` : ''}</div>
          <div class="hero-actions"><button class="btn secondary" data-nav="attendance">${icons.gps} Chấm công</button><button class="btn secondary" data-nav="availability">${icons.calendar} Đăng ký lịch rảnh</button></div>
        </section>
        ${d.attendance_alerts?.length ? `<section class="section-gap">${attendanceAlertList(d.attendance_alerts, false)}</section>` : ''}
        <section class="v5-summary-strip">
          ${summaryItem('Ca sắp tới', s.upcoming_shifts, 'Từ hôm nay')}
          ${summaryItem('Giờ tháng này', `${number(s.month_hours, 2)} giờ`, 'Đã hoàn thành')}
          ${summaryItem('Yêu cầu chờ', s.pending_requests, 'Đang xử lý')}
          ${summaryItem('Lương tạm tính', compactMoney(s.estimated_salary), money(s.estimated_salary))}
        </section>
        ${next ? `<div class="v5-gps-panel"><span class="v5-gps-icon">${icons.clock}</span><div class="v5-gps-copy"><strong>Đếm ngược đến ca tiếp theo</strong><span>${dateVN(next.shift_date)} · ${esc(next.start_time)}–${esc(next.end_time)} · ${esc(next.location_name || '')}</span></div><div class="v5-countdown" data-countdown="${target}">Đang tính…</div></div>` : ''}
        <section class="grid-2">
          <div class="card"><div class="card-head"><div><h3>Lịch làm gần nhất</h3><p>Ca đã được quản lý xác nhận</p></div><button class="btn small secondary" data-nav="shifts">Xem lịch tuần</button></div><div class="card-body">${shiftList(d.upcoming_shifts)}</div></div>
          <div class="card"><div class="card-head"><div><h3>Thông báo của bạn</h3><p>Lịch làm, yêu cầu và lương</p></div><button class="btn small secondary" data-nav="notifications">Xem tất cả</button></div><div class="card-body">${notificationList(d.notifications)}</div></div>
        </section>`;
    }
  };

  /* ------------------------------------------------------------------
     Employees
  ------------------------------------------------------------------ */
  renderEmployees = async function renderEmployeesV5() {
    if (state.user.role !== 'admin') return navigate('dashboard');
    const rows = await api('/api/employees');
    state.cache.employees = rows;
    const active = rows.filter((row) => row.status === 'Đang làm').length;
    const paused = rows.filter((row) => row.status === 'Tạm nghỉ').length;
    const locked = rows.filter((row) => !row.account_active).length;
    const roles = [...new Set(rows.map((row) => row.role).filter(Boolean))].sort();
    pageNode().innerHTML = `
      ${intro('NHÂN SỰ RUMI', 'Quản lý nhân viên', 'Admin tạo, sửa, khóa tài khoản và thiết lập lương theo giờ.', `<button class="btn" data-action="employee-add">${icons.plus} Thêm nhân viên</button>`)}
      <section class="v5-summary-strip">
        ${summaryItem('Tổng hồ sơ', rows.length, 'Toàn bộ nhân viên')}
        ${summaryItem('Đang làm', active, 'Tài khoản hoạt động')}
        ${summaryItem('Tạm nghỉ', paused, 'Chưa xếp ca')}
        ${summaryItem('Tài khoản khóa', locked, 'Không thể đăng nhập')}
      </section>
      ${filterToolbar(`<div class="search-box">${icons.search}<input id="v5-employee-search" placeholder="Tìm tên, mã, số điện thoại, tài khoản..."></div>
        <select id="v5-employee-status"><option value="">Tất cả trạng thái</option><option>Đang làm</option><option>Tạm nghỉ</option><option>Đã nghỉ việc</option></select>
        <select id="v5-employee-role"><option value="">Tất cả vị trí</option>${roles.map((role) => `<option>${esc(role)}</option>`).join('')}</select>
        ${exportButton('employees')}<span id="v5-employee-count" class="v5-filter-count">${rows.length} hồ sơ</span>`)}
      <div class="table-wrap"><table><thead><tr><th>Nhân viên</th><th>Liên hệ</th><th>Vị trí</th><th>Lương/giờ</th><th>Tài khoản</th><th>Trạng thái</th><th>Thao tác</th></tr></thead>
        <tbody id="employee-rows">${rows.map((x) => `<tr data-search="${esc(normalize(`${x.name} ${x.code} ${x.username} ${x.phone} ${x.email}`))}" data-status="${esc(x.status)}" data-role="${esc(x.role)}"><td>${person(x.name, x.code)}</td><td><span class="cell-main">${esc(x.phone || '—')}</span><span class="cell-sub">${esc(x.email || '')}</span></td><td>${esc(x.role)}</td><td class="money">${money(x.hourly_wage)}</td><td><span class="cell-main">${esc(x.username || 'Chưa có')}</span><span class="cell-sub">${x.account_active ? 'Được phép đăng nhập' : 'Đã khóa'}</span></td><td>${badge(x.status)}</td><td><div class="actions"><button class="btn small secondary icon-only" data-action="employee-edit" data-id="${x.id}" title="Sửa">${icons.edit}</button><button class="btn small secondary icon-only" data-action="employee-reset" data-id="${x.id}" title="Đặt lại mật khẩu">${icons.key}</button><button class="btn small danger icon-only" data-action="employee-delete" data-id="${x.id}" title="Xóa">${icons.trash}</button></div></td></tr>`).join('')}</tbody>
      </table></div>`;
  };

  function filterEmployees() {
    const query = normalize(document.querySelector('#v5-employee-search')?.value || '');
    const status = document.querySelector('#v5-employee-status')?.value || '';
    const role = document.querySelector('#v5-employee-role')?.value || '';
    let shown = 0;
    document.querySelectorAll('#employee-rows tr').forEach((row) => {
      const visible = (!query || row.dataset.search.includes(query)) && (!status || row.dataset.status === status) && (!role || row.dataset.role === role);
      row.classList.toggle('hidden', !visible);
      if (visible) shown += 1;
    });
    const count = document.querySelector('#v5-employee-count');
    if (count) count.textContent = `${shown} hồ sơ`;
  }

  /* ------------------------------------------------------------------
     Schedule / personal shifts
  ------------------------------------------------------------------ */
  candidateList = function candidateListV53(rows) {
    if (!rows.length) return empty('Chưa tìm nhân viên', 'Chọn ngày, giờ, vị trí và số người cần để hệ thống xếp hạng.', 'search');
    const labels = { available:'Có thể xếp', busy:'Trùng ca', on_leave:'Nghỉ phép', unregistered:'Chưa đăng ký', role_mismatch:'Sai vị trí' };
    return rows.map((x, index) => `<div class="candidate ${x.state === 'available' ? 'available' : 'disabled'}">
      <span class="v53-rank">${x.state === 'available' ? `#${index + 1}` : '—'}</span>
      <span class="avatar">${initials(x.name)}</span>
      <div class="candidate-copy"><strong>${esc(x.name)} · ${esc(x.role)}</strong><span>${esc(x.code)} · ${esc(x.reason)}</span><small>${number(x.week_hours,2)} giờ / ${x.week_shifts || 0} ca trong tuần · điểm phù hợp ${x.score || 0}</small></div>
      ${x.state === 'available' ? `<button class="btn small success" data-action="schedule-candidate" data-id="${x.employee_id}">${icons.plus} Xếp ca</button>` : badge(labels[x.state] || x.state)}
    </div>`).join('');
  };

  renderSchedule = async function renderScheduleV53() {
    if (state.user.role !== 'admin') return navigate('dashboard');
    const startDate = parseLocalDate(state.scheduleWeekStart);
    const endDate = addDays(startDate, 6);
    const pageData = await api(`/api/page/schedule?start=${localISO(startDate)}&end=${localISO(endDate)}`);
    const shifts = pageData.shifts || [], locations = pageData.locations || [], roles = pageData.roles || [];
    state.cache.shifts = shifts; state.cache.locations = locations; state.cache.roles = roles;
    if (!state.candidateQuery.location_id && locations[0]) state.candidateQuery.location_id = locations[0].id;
    const q = state.candidateQuery;
    const boardRows = state.scheduleLocationFilter ? shifts.filter((row) => String(row.location_id) === String(state.scheduleLocationFilter)) : shifts;
    const availableCount = state.candidates.filter((x) => x.state === 'available').length;
    pageNode().innerHTML = `
      ${intro('XẾP LỊCH LOGIC', 'Lịch làm theo nhu cầu thực tế', 'Chọn số người và vị trí cần. Hệ thống ưu tiên người đúng vị trí, đã đăng ký rảnh, không trùng ca và có ít giờ hơn trong tuần.', excelWeekButton('schedule'))}
      <section class="v5-summary-strip">
        ${summaryItem('Tổng ca tuần', boardRows.length, weekLabel(startDate))}
        ${summaryItem('Nhân viên được xếp', unique(boardRows, 'employee_id'), 'Không tính trùng')}
        ${summaryItem('Ứng viên phù hợp', availableCount, state.candidates.length ? 'Theo lần tìm gần nhất' : 'Chưa tìm')}
        ${summaryItem('Ca hôm nay', boardRows.filter((x) => x.shift_date === today()).length, 'Theo lịch tuần')}
      </section>
      ${!locations.length ? `<div class="info-banner warning-banner">${icons.info}<div><strong>Chưa có vị trí cửa hàng</strong><span>Thêm vị trí trước khi xếp ca để nhân viên chấm công GPS.</span></div></div>` : ''}
      <section class="v5-schedule-layout">
        <div class="card v5-sticky"><div class="card-head"><div><h3>1. Nhập nhu cầu ca</h3><p>Hệ thống sẽ xếp hạng nhân viên phù hợp</p></div></div><div class="card-body">
          <form class="form-grid" data-form="candidate-search" id="v53-schedule-form">
            <div class="field span-2"><label>Ngày làm</label><input type="date" name="date" min="${today()}" value="${esc(q.date)}" required></div>
            <div class="field"><label>Bắt đầu</label><input type="time" name="start" value="${esc(q.start)}" required></div>
            <div class="field"><label>Kết thúc</label><input type="time" name="end" value="${esc(q.end)}" required></div>
            <div class="field span-2"><label>Cửa hàng</label><select name="location_id" required>${locations.map((x) => `<option value="${x.id}" ${String(x.id) === String(q.location_id) ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select></div>
            <div class="field"><label>Vị trí cần</label><select name="required_role"><option value="">Bất kỳ</option>${roles.map((role) => `<option value="${esc(role)}" ${q.required_role === role ? 'selected' : ''}>${esc(role)}</option>`).join('')}</select></div>
            <div class="field"><label>Số nhân viên cần</label><input type="number" name="employee_count" min="1" max="20" value="${esc(q.employee_count || 1)}" required></div>
            <div class="field span-2"><label>Ghi chú ca</label><input name="note" value="${esc(q.note || '')}" placeholder="Ví dụ: ưu tiên người biết thu ngân"></div>
            <div class="form-actions v53-dual-actions"><button class="btn secondary" type="submit" ${!locations.length ? 'disabled' : ''}>${icons.search} Tìm và xếp hạng</button><button class="btn" type="button" data-v5-action="auto-assign" ${!locations.length ? 'disabled' : ''}>${icons.check} Xếp tự động</button></div>
          </form>
          <div class="v53-rule-list"><span>${icons.check} Có lịch rảnh đã duyệt</span><span>${icons.check} Không trùng ca / nghỉ phép</span><span>${icons.check} Đúng vị trí công việc</span><span>${icons.check} Cân bằng giờ làm trong tuần</span></div>
          <div class="v5-divider"></div><div class="card-head compact"><div><h3>2. Danh sách đề xuất</h3><p>${state.candidates.length ? `${availableCount} người có thể xếp` : 'Bấm tìm để xem kết quả'}</p></div></div><div class="candidate-list" id="candidate-list">${candidateList(state.candidates)}</div>
        </div></div>
        <div class="card"><div class="card-head"><div class="v5-week-toolbar"><div class="v5-week-title"><strong>3. Lịch đã xếp · ${weekLabel(startDate)}</strong><span>${boardRows.length} ca</span></div><div class="v5-week-actions"><button class="btn small secondary" data-v5-action="week" data-scope="schedule" data-step="-7">‹</button><button class="btn small secondary" data-v5-action="week-today" data-scope="schedule">Tuần này</button><button class="btn small secondary" data-v5-action="week" data-scope="schedule" data-step="7">›</button></div></div>
          <div class="v5-filter-row"><select id="v5-schedule-location"><option value="">Tất cả cửa hàng</option>${locations.map((x) => `<option value="${x.id}" ${String(state.scheduleLocationFilter) === String(x.id) ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select></div>
        </div><div class="card-body">${renderWeekBoard(boardRows, startDate, true)}</div></div>
      </section>`;
  };

  renderMyShifts = async function renderMyShiftsV5() {
    const startDate = parseLocalDate(state.myWeekStart);
    const endDate = addDays(startDate, 6);
    const rows = await api(`/api/shifts?start=${localISO(startDate)}&end=${localISO(endDate)}`);
    state.cache.myShifts = rows;
    const upcoming = rows.filter((x) => `${x.shift_date} ${x.start_time}` >= `${today()} 00:00`).sort(byDateTime)[0];
    pageNode().innerHTML = `
      ${intro('LỊCH CÁ NHÂN', 'Lịch làm của tôi', 'Xem lịch theo tuần, cửa hàng và trạng thái chấm công.', `<div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" data-nav="attendance">${icons.gps} Chấm công GPS</button>${excelWeekButton('my', 'Xuất Excel')}</div>`)}
      ${upcoming ? `<div class="v5-gps-panel"><span class="v5-gps-icon">${icons.calendar}</span><div class="v5-gps-copy"><strong>Ca gần nhất trong tuần</strong><span>${dateVN(upcoming.shift_date)} · ${esc(upcoming.start_time)}–${esc(upcoming.end_time)} · ${esc(upcoming.location_name || '')}</span></div><div class="v5-countdown" data-countdown="${upcoming.shift_date}T${upcoming.start_time}:00">Đang tính…</div></div>` : ''}
      <div class="card"><div class="card-head"><div class="v5-week-toolbar"><div class="v5-week-title"><strong>${weekLabel(startDate)}</strong><span>${rows.length} ca làm</span></div><div class="v5-week-actions"><button class="btn small secondary" data-v5-action="week" data-scope="my" data-step="-7">‹</button><button class="btn small secondary" data-v5-action="week-today" data-scope="my">Tuần này</button><button class="btn small secondary" data-v5-action="week" data-scope="my" data-step="7">›</button></div></div></div><div class="card-body">${renderWeekBoard(rows, startDate, false)}</div></div>`;
  };

  /* ------------------------------------------------------------------
     Attendance
  ------------------------------------------------------------------ */
  renderAttendance = async function renderAttendanceV53() {
    if (state.user.role === 'employee') return renderEmployeeAttendanceV53();
    const pageData = await api(`/api/page/attendance?month=${state.month}`);
    const rows = pageData.history || [], alerts = pageData.alerts || [];
    state.cache.attendance = rows; state.cache.attendanceAlerts = alerts;
    const done = rows.filter((x) => x.check_out).length;
    const issues = rows.filter((x) => Number(x.late_minutes || 0) || Number(x.early_leave_minutes || 0)).length;
    const overtime = total(rows, 'overtime_minutes');
    pageNode().innerHTML = `
      ${intro('CHẤM CÔNG → TÍNH LƯƠNG', 'Bảng công chi tiết', 'Mỗi lượt công thể hiện ca dự kiến, giờ thực tế, đi trễ, về sớm, tăng ca và số giờ dùng để tính lương.', exportButton('attendance', 'Xuất bảng công'))}
      ${alerts.length ? `<section class="card v62-alert-panel"><div class="card-head"><div><h3>Cảnh báo cần xử lý ngay</h3><p>Nhắc nhân viên, tìm người thay hoặc xác nhận vắng sau khi ca kết thúc.</p></div><span class="v5-filter-count">${alerts.length} cảnh báo</span></div><div class="card-body">${attendanceAlertList(alerts, true)}</div></section>` : ''}
      <section class="v5-summary-strip">
        ${summaryItem('Ca hoàn thành', done, `${rows.length} dòng lịch/công trong tháng`)}
        ${summaryItem('Giờ được trả', `${number(total(rows, 'payable_hours') || total(rows, 'hours'), 2)} giờ`, 'Dùng tính bảng lương')}
        ${summaryItem('Cần chú ý', issues, 'Đi trễ hoặc về sớm')}
        ${summaryItem('Tăng ca', `${number(overtime / 60, 2)} giờ`, `${overtime} phút`)}
      </section>
      ${filterToolbar(`<div class="search-box">${icons.search}<input id="v5-attendance-search" placeholder="Tìm nhân viên hoặc ngày..."></div><input type="month" id="attendance-month" value="${state.month}"><select id="v5-attendance-status"><option value="">Tất cả trạng thái</option>${[...new Set(rows.map((x) => x.status).filter(Boolean))].map((x) => `<option>${esc(x)}</option>`).join('')}</select><span id="v5-attendance-count" class="v5-filter-count">${rows.length} dòng</span>`)}
      <div class="table-wrap"><table><thead><tr><th>Nhân viên</th><th>Ngày / ca</th><th>Vào – ra</th><th>Giờ dự kiến</th><th>Giờ tính lương</th><th>Trễ / sớm / tăng ca</th><th>GPS</th><th>Trạng thái</th><th></th></tr></thead><tbody id="v5-attendance-rows">
        ${rows.map((x) => `<tr data-search="${esc(normalize(`${x.employee_name} ${x.employee_code} ${x.work_date}`))}" data-status="${esc(x.status)}"><td>${person(x.employee_name, x.employee_code)}</td><td><span class="cell-main">${dateVN(x.work_date)}</span><span class="cell-sub">${x.shift ? `${x.shift.start_time}–${x.shift.end_time}` : 'Ngoài lịch'}</span></td><td><span class="cell-main">${clockRange(x)}</span><span class="cell-sub">${number(x.actual_hours || x.hours,2)} giờ thực tế</span></td><td>${number(x.scheduled_hours || 0,2)} giờ</td><td class="money"><strong>${number(x.payable_hours || x.hours,2)} giờ</strong></td><td><span class="v53-metric late">Trễ ${x.late_minutes || 0}p</span><span class="v53-metric early">Sớm ${x.early_leave_minutes || 0}p</span><span class="v53-metric overtime">TC ${x.overtime_minutes || 0}p</span></td><td><span class="cell-main">${x.check_in_distance_m != null ? `${number(x.check_in_distance_m,1)} m` : (x.is_synthetic ? 'Chưa chấm' : 'Thủ công')}</span><span class="cell-sub">${x.check_in_accuracy_m ? `Sai số ${number(x.check_in_accuracy_m,0)} m` : ''}</span></td><td>${badge(x.status)}</td><td><button class="btn small secondary" data-action="attendance-edit" data-id="${x.shift_id || ''}" ${!x.shift_id ? 'disabled' : ''}>${icons.edit}</button></td></tr>`).join('') || `<tr><td colspan="9">${empty('Chưa có dữ liệu công', 'Dữ liệu xuất hiện sau khi nhân viên chấm công.', 'clock')}</td></tr>`}
      </tbody></table></div>`;
  };

  async function renderEmployeeAttendanceV53() {
    const pageData = await api(`/api/page/attendance?month=${state.month}`);
    const todayShifts = pageData.today_shifts || [], history = pageData.history || [], settings = pageData.settings || {}, alerts = pageData.alerts || [];
    state.cache.todayShifts = todayShifts; state.cache.attendance = history; state.cache.attendanceAlerts = alerts;
    pageNode().innerHTML = `
      ${intro('CHẤM CÔNG GPS', 'Vào và ra ca đúng cửa hàng', 'Chấm công hợp lệ sẽ tự chuyển thành giờ tính lương trong bảng lương tháng.')}
      ${alerts.length ? `<section class="section-gap">${attendanceAlertList(alerts, false)}</section>` : ''}
      <div class="v5-gps-panel"><span class="v5-gps-icon">${icons.gps}</span><div class="v5-gps-copy"><strong id="v5-gps-title">Kiểm tra GPS trước khi chấm công</strong><span id="v5-gps-text">Bật vị trí chính xác để kiểm tra sai số và quyền truy cập.</span></div><button class="btn secondary" data-v5-action="gps-test">${icons.gps} Kiểm tra vị trí</button></div>
      <div class="info-banner">${icons.info}<div><strong>Quy định hiện tại</strong><span>Vào ca: được mở trước ${settings.checkin_before_minutes || 15} phút; sau ${settings.checkin_after_minutes || 5} phút hệ thống ghi nhận đi trễ. Quá ${settings.attendance_no_show_minutes || 30} phút sẽ cảnh báo nguy cơ vắng. Ra ca: trước ${settings.checkout_before_minutes || 5} phút đến sau ${settings.checkout_after_minutes || 5} phút.</span></div></div>
      <div class="v5-clock-grid section-gap">${todayShifts.length ? todayShifts.map(clockCardV53).join('') : empty('Hôm nay không có ca', 'Bạn chỉ có thể chấm công cho ca đã được admin xếp.', 'calendar')}</div>
      <div class="section-gap card"><div class="card-head"><div><h3>Lịch sử công tháng ${state.month}</h3><p>${number(total(history, 'payable_hours') || total(history, 'hours'), 2)} giờ được tính lương</p></div><div style="display:flex;gap:8px"><input class="compact-input" type="month" id="attendance-month" value="${state.month}">${exportButton('attendance', 'Xuất công')}</div></div><div class="card-body">${history.length ? `<div class="list">${history.map((x) => `<div class="list-row"><span class="list-icon">${icons.clock}</span><div class="list-copy"><strong>${dateVN(x.work_date)} · ${esc(x.check_in || '—')}–${esc(x.check_out || 'Chưa ra')}</strong><span>${number(x.payable_hours || x.hours,2)} giờ tính lương · Trễ ${x.late_minutes || 0}p · Sớm ${x.early_leave_minutes || 0}p · Tăng ca ${x.overtime_minutes || 0}p</span></div>${badge(x.status)}</div>`).join('')}</div>` : empty('Chưa có giờ công', 'Sau khi chấm công, lịch sử sẽ xuất hiện tại đây.', 'clock')}</div></div>`;
  }

  function clockCardV53(x) {
    const att = x.attendance;
    const live = x.live_attendance_state || {};
    const liveStatus = live.status || 'Chưa chấm công';
    const action = !att ? (liveStatus === 'Vắng ca' ? 'blocked' : 'checkin') : att.check_out_at || att.check_out ? 'done' : 'checkout';
    const target = `${x.shift_date}T${action === 'checkout' ? x.end_time : x.start_time}:00`;
    const danger = ['Đi trễ chưa chấm','Nguy cơ vắng ca','Vắng ca','Thiếu giờ ra'].includes(liveStatus);
    const clockMessage = action === 'done'
      ? `Trễ ${att.late_minutes || 0}p · Sớm ${att.early_leave_minutes || 0}p · Tăng ca ${att.overtime_minutes || 0}p`
      : action === 'blocked'
        ? 'Ca đã kết thúc mà không có chấm công vào. Hãy gửi yêu cầu sửa công.'
        : live.message || `Còn <b class="v5-countdown" data-countdown="${target}">đang tính…</b> đến mốc ca`;
    const button = action === 'done'
      ? `<button class="btn secondary" disabled>${icons.check} Đã hoàn thành</button>`
      : action === 'blocked'
        ? `<button class="btn secondary" data-v55-action="correction-open">${icons.edit} Gửi yêu cầu sửa công</button>`
        : `<button class="btn ${danger ? 'danger' : ''}" data-action="clock-shift" data-id="${x.id}" data-clock="${action}">${icons.gps} ${action === 'checkin' ? (danger ? 'Chấm vào muộn' : 'Chấm công vào') : 'Chấm công ra'}</button>`;
    return `<article class="v5-clock-card ${danger ? 'attendance-danger' : ''}"><span class="v5-kicker">${dateVN(x.shift_date)} · ${esc(x.location_name || 'RUMI')}</span><div class="v5-clock-time">${esc(x.start_time)} – ${esc(x.end_time)}</div><p class="v5-clock-location">${esc(x.location_address || 'Vị trí do quản lý cấu hình')}</p><div class="shift-meta"><div><span>Trạng thái</span><strong>${att ? esc(att.status) : esc(liveStatus)}</strong></div><div><span>Giờ tính lương</span><strong>${number(att?.payable_hours || att?.hours || 0,2)} giờ</strong></div></div><div class="v5-clock-status">${icons.clock}<span>${clockMessage}</span></div>${button}</article>`;
  }

  function filterAttendance() {
    const query = normalize(document.querySelector('#v5-attendance-search')?.value || '');
    const status = document.querySelector('#v5-attendance-status')?.value || '';
    let shown = 0;
    document.querySelectorAll('#v5-attendance-rows tr').forEach((row) => {
      const visible = (!query || row.dataset.search.includes(query)) && (!status || row.dataset.status === status);
      row.classList.toggle('hidden', !visible);
      if (visible) shown += 1;
    });
    const count = document.querySelector('#v5-attendance-count');
    if (count) count.textContent = `${shown} dòng`;
  }

  /* ------------------------------------------------------------------
     Payroll
  ------------------------------------------------------------------ */
  renderPayroll = async function renderPayrollV61() {
    const data = await api(`/api/page/payroll?month=${state.month}`);
    const rows = data.items || [], run = data.run || {status:'Chưa tạo'};
    state.cache.payroll = rows; state.cache.payrollRun = run;
    const admin = state.user.role === 'admin';
    const payrollTotal = total(rows, 'total');
    const paid = rows.filter((x) => x.payment_status === 'Đã thanh toán');
    const runStatus = run.status || 'Chưa tạo';
    const scheduledShifts = rows.reduce((sum, x) => sum + Number(x.scheduled_shift_count || 0), 0);
    const completedShifts = rows.reduce((sum, x) => sum + Number(x.completed_shift_count || x.attendance_count || 0), 0);
    const unresolved = rows.reduce((sum, x) => sum
      + Number(x.upcoming_shift_count || 0)
      + Number(x.active_shift_count || 0)
      + Number(x.pending_checkin_count || 0)
      + Number(x.late_unclocked_count || 0)
      + Number(x.no_show_risk_count || 0)
      + Number(x.missing_attendance_count || 0)
      + Number(x.incomplete_attendance_count || 0), 0);
    const actions = admin
      ? `<div class="v53-payroll-actions">${runStatus === 'Đã chốt'
          ? `<button class="btn secondary" data-v5-action="payroll-unlock">Mở khóa</button>`
          : `<button class="btn secondary" data-v5-action="payroll-generate">Tính lại</button><button class="btn" data-v5-action="payroll-lock" ${unresolved ? 'disabled title="Còn ca chưa hoàn tất"' : ''}>${icons.check} Chốt bảng lương</button>`}${exportButton('payroll', 'Xuất Excel/CSV')}<button class="btn secondary" data-v5-action="payroll-pdf">Xuất PDF bảng lương</button></div>`
      : `<div style="display:flex;gap:8px;flex-wrap:wrap">${exportButton('payroll', 'Xuất CSV')}<button class="btn secondary" data-v5-action="payroll-pdf">Xuất PDF</button></div>`;

    pageNode().innerHTML = `
      ${intro('BẢNG LƯƠNG THÁNG', admin ? `Bảng lương ${state.month}` : 'Phiếu lương của tôi', admin ? 'Lịch làm, chấm công và giờ tính lương được tách riêng để tránh nhầm số liệu.' : 'Lương chỉ tính từ giờ chấm công hợp lệ đã hoàn tất.', actions)}
      <div class="info-banner">${icons.info}<div><strong>Quy tắc theo tháng</strong><span>Bảng lương ${state.month} chỉ lấy ca có ngày làm thuộc tháng này. Tuần giao tháng có thể hiển thị ca của tháng khác trong lịch tuần nhưng không cộng vào tháng đang xem.</span></div></div>
      <div class="v53-payroll-run ${runStatus === 'Đã chốt' ? 'locked' : ''}"><span>${runStatus === 'Đã chốt' ? icons.check : icons.info}</span><div><strong>Trạng thái: ${esc(runStatus)}</strong><small>${run.generated_at ? `Tính lúc ${dateTimeVN(run.generated_at)}` : 'Chưa tạo bản lưu tháng'}${run.locked_at ? ` · Chốt lúc ${dateTimeVN(run.locked_at)}` : ''}${unresolved ? ` · Còn ${unresolved} ca chưa hoàn tất` : ''}</small></div></div>
      <section class="v5-summary-strip">
        ${summaryItem('Ca theo lịch', scheduledShifts, `${number(total(rows, 'scheduled_hours'), 2)} giờ dự kiến`)}
        ${summaryItem('Ca hoàn thành', completedShifts, `${number(total(rows, 'actual_hours'), 2)} giờ thực tế`)}
        ${summaryItem('Giờ tính lương', `${number(total(rows, 'payable_hours') || total(rows, 'hours'), 2)} giờ`, `${number(total(rows, 'overtime_minutes') / 60,2)} giờ tăng ca đã duyệt`)}
        ${summaryItem('Tổng thực nhận', money(payrollTotal), runStatus === 'Đã chốt' ? 'Số liệu đã khóa' : 'Số liệu tạm tính')}
        ${summaryItem('Chưa thanh toán', money(payrollTotal - total(paid, 'total')), `${rows.filter((x)=>x.eligible_for_payment && x.payment_status !== 'Đã thanh toán').length} phiếu đủ điều kiện`)}
      </section>
      ${filterToolbar(`<div class="search-box">${icons.search}<input id="v5-payroll-search" placeholder="Tìm nhân viên..."></div><input type="month" id="payroll-month" value="${state.month}"><select id="v5-payroll-status"><option value="">Tất cả thanh toán</option><option>Đã thanh toán</option><option>Chưa thanh toán</option></select><span id="v5-payroll-count" class="v5-filter-count">${rows.length} phiếu</span>`)}
      <div class="table-wrap"><table><thead><tr>${admin ? '<th>Nhân viên</th>' : ''}<th>Lịch / công</th><th>Tình trạng</th><th>Trễ · sớm · TC</th><th>Lương cơ bản</th><th>Điều chỉnh</th><th>Thực nhận</th><th>Thanh toán</th><th>Thao tác</th></tr></thead><tbody id="v5-payroll-rows">
        ${rows.map((x) => {
          const paidStatus = x.payment_status === 'Đã thanh toán';
          const canPay = runStatus === 'Đã chốt' && Boolean(x.eligible_for_payment) && Number(x.total || 0) > 0;
          const displayPayment = paidStatus ? 'Đã thanh toán' : (canPay ? 'Chưa thanh toán' : 'Chưa đủ điều kiện');
          const payButton = paidStatus
            ? `<button class="btn small secondary" data-action="payroll-pay" data-id="${x.employee_id}" data-status="Chưa thanh toán">Hoàn tác</button>`
            : `<button class="btn small success" data-action="payroll-pay" data-id="${x.employee_id}" data-status="Đã thanh toán" ${canPay ? '' : 'disabled title="Chỉ trả sau khi bảng lương đã chốt và công đã hoàn tất"'}>Đã trả</button>`;
          return `<tr data-search="${esc(normalize(`${x.name} ${x.code}`))}" data-status="${esc(x.payment_status)}">${admin ? `<td>${person(x.name, x.code)}</td>` : ''}<td><span class="cell-main">${x.scheduled_shift_count || 0} ca lịch · ${number(x.scheduled_hours,2)} giờ</span><span class="cell-sub">${x.completed_shift_count || x.attendance_count || 0} ca hoàn tất · ${number(x.actual_hours,2)} giờ thực tế · ${number(x.payable_hours || x.hours,2)} giờ tính lương</span></td><td>${badge(x.payroll_state || 'Chưa có dữ liệu')}${x.absent_shift_count ? `<span class="cell-sub">${x.absent_shift_count} ca vắng</span>` : ''}${x.no_show_risk_count ? `<span class="cell-sub">${x.no_show_risk_count} ca nguy cơ vắng</span>` : ''}${x.late_unclocked_count ? `<span class="cell-sub">${x.late_unclocked_count} ca đi trễ chưa chấm</span>` : ''}${x.missing_attendance_count && !x.absent_shift_count ? `<span class="cell-sub">${x.missing_attendance_count} ca thiếu công</span>` : ''}${x.incomplete_attendance_count ? `<span class="cell-sub">${x.incomplete_attendance_count} ca thiếu giờ ra</span>` : ''}</td><td><span class="v53-metric late">${x.late_minutes || 0}p trễ</span><span class="v53-metric early">${x.early_leave_minutes || 0}p sớm</span><span class="v53-metric overtime">${x.overtime_minutes || 0}p TC</span></td><td class="money"><strong>${money(x.base_salary)}</strong><span class="cell-sub">Dự kiến theo lịch ${money(x.estimated_salary || Number(x.scheduled_hours||0)*Number(x.hourly_wage||0))}</span></td><td><span class="cell-main">+${money(x.bonus)} / -${money(Number(x.penalty||0)+Number(x.advance_pay||0))}</span><span class="cell-sub">Phạt ${money(x.penalty)} · Ứng ${money(x.advance_pay)}</span></td><td class="money"><strong>${money(x.total)}</strong></td><td>${badge(displayPayment)}</td><td><div class="actions">${admin ? `<button class="btn small secondary" data-action="payroll-adjust" data-id="${x.employee_id}" ${runStatus === 'Đã chốt' ? 'disabled title="Mở khóa để sửa"' : ''}>${icons.edit} Điều chỉnh</button>${payButton}` : ''}<button class="btn small secondary" data-v5-action="payroll-slip" data-id="${x.employee_id}">${runStatus === 'Đã chốt' ? 'Xuất PDF phiếu lương' : 'PDF tạm tính'}</button></div></td></tr>`;
        }).join('') || `<tr><td colspan="9">${empty('Chưa có bảng lương', 'Hãy tạo lịch, hoàn tất chấm công rồi bấm Tính lại bảng lương.', 'money')}</td></tr>`}
      </tbody></table></div>`;
  };

  function filterPayroll() {
    const query = normalize(document.querySelector('#v5-payroll-search')?.value || '');
    const status = document.querySelector('#v5-payroll-status')?.value || '';
    let shown = 0;
    document.querySelectorAll('#v5-payroll-rows tr').forEach((row) => {
      const visible = (!query || row.dataset.search.includes(query)) && (!status || row.dataset.status === status);
      row.classList.toggle('hidden', !visible);
      if (visible) shown += 1;
    });
    const count = document.querySelector('#v5-payroll-count');
    if (count) count.textContent = `${shown} phiếu`;
  }

  /* ------------------------------------------------------------------
     Inventory and purchases
  ------------------------------------------------------------------ */
  renderInventory = async function renderInventoryV5() {
    const pageData = await api('/api/page/inventory');
    const items = pageData.items, withdrawals = pageData.withdrawals, employees = pageData.employees;
    state.cache.inventory = items;
    state.cache.withdrawals = withdrawals;
    state.cache.publicEmployees = employees;
    const admin = state.user.role === 'admin';
    const low = items.filter((x) => Number(x.quantity) <= Number(x.min_stock));
    const categories = [...new Set(items.map((x) => x.category).filter(Boolean))].sort();
    pageNode().innerHTML = `
      ${intro('KHO NGUYÊN LIỆU', admin ? 'Quản lý tồn kho' : 'Ghi nhận nguyên liệu đã lấy', 'Tồn kho tự giảm sau mỗi lần lấy và tự đề xuất mua khi xuống thấp.', `${admin ? `<button class="btn secondary" data-action="inventory-add">${icons.plus} Thêm nguyên liệu</button>` : ''}<button class="btn" data-action="inventory-withdraw">${icons.box} Ghi nhận lấy hàng</button>`)}
      <section class="v5-summary-strip">
        ${summaryItem('Mặt hàng', items.length, `${categories.length} nhóm`)}
        ${summaryItem('Dưới định mức', low.length, low.length ? 'Cần bổ sung sớm' : 'Kho đang ổn định')}
        ${summaryItem('Lượt lấy tháng này', withdrawals.filter((x) => String(x.taken_at || '').startsWith(monthNow())).length, 'Đã ghi lịch sử')}
        ${summaryItem('Giá trị tham khảo', money(items.reduce((sum, x) => sum + Number(x.quantity || 0) * Number(x.cost || 0), 0)), 'Tồn kho hiện tại')}
      </section>
      ${filterToolbar(`<div class="search-box">${icons.search}<input id="v5-stock-search" placeholder="Tìm nguyên liệu..."></div><select id="v5-stock-category"><option value="">Tất cả nhóm</option>${categories.map((x) => `<option>${esc(x)}</option>`).join('')}</select><select id="v5-stock-status"><option value="">Tất cả mức tồn</option><option value="low">Sắp hết / đã hết</option><option value="ok">Còn đủ</option></select>${exportButton('inventory')}<span id="v5-stock-count" class="v5-filter-count">${items.length} mặt hàng</span>`)}
      <div id="v5-stock-grid" class="v5-stock-grid">${items.map(stockCard).join('') || empty('Kho đang trống', 'Admin hãy thêm nguyên liệu đầu tiên.', 'box')}</div>
      <div class="section-gap card"><div class="card-head"><div><h3>Lịch sử lấy nguyên liệu</h3><p>${withdrawals.length} lượt gần nhất</p></div>${exportButton('withdrawals', 'Xuất lịch sử')}</div><div class="card-body">${withdrawals.length ? `<div class="list">${withdrawals.slice(0, 50).map((x) => `<div class="list-row"><span class="list-icon">${icons.box}</span><div class="list-copy"><strong>${esc(x.item_name)} · ${number(x.quantity, 2)} ${esc(x.unit)}</strong><span>${dateVN(x.taken_at)} · ${esc(x.employee_name || 'Quản lý')} · ${esc(x.note || 'Không ghi chú')}</span></div></div>`).join('')}</div>` : empty('Chưa có lượt lấy hàng', 'Mỗi lần lấy nguyên liệu sẽ được lưu lại.', 'box')}</div></div>`;
  };

  function stockCard(x) {
    const low = Number(x.quantity) <= Number(x.min_stock);
    const ratio = Math.max(0, Math.min(100, Number(x.quantity) / Math.max(Number(x.min_stock) * 2, 1) * 100));
    return `<article class="v5-stock-card ${low ? 'is-low' : 'is-ok'}" data-search="${esc(normalize(`${x.name} ${x.category} ${x.unit}`))}" data-category="${esc(x.category)}" data-stock="${low ? 'low' : 'ok'}"><div class="v5-stock-head"><div><strong>${esc(x.name)}</strong><small>${esc(x.category)} · Mức tối thiểu ${number(x.min_stock, 2)} ${esc(x.unit)}</small></div>${badge(low ? 'Sắp hết' : 'Còn đủ')}</div><div class="v5-stock-number">${number(x.quantity, 2)} <span>${esc(x.unit)}</span></div><div class="progress ${low ? 'danger' : ''}"><span style="width:${ratio}%"></span></div><div class="v5-stock-foot"><small>${x.cost ? `Giá nhập ${money(x.cost)}/${esc(x.unit)}` : 'Chưa nhập giá tham khảo'}</small>${state.user.role === 'admin' ? `<div class="v5-stock-actions"><button class="btn small secondary icon-only" data-action="inventory-restock" data-id="${x.id}" title="Nhập thêm">${icons.plus}</button><button class="btn small ghost icon-only" data-action="inventory-edit" data-id="${x.id}" title="Sửa">${icons.edit}</button></div>` : ''}</div></article>`;
  }

  function filterInventory() {
    const query = normalize(document.querySelector('#v5-stock-search')?.value || '');
    const category = document.querySelector('#v5-stock-category')?.value || '';
    const stock = document.querySelector('#v5-stock-status')?.value || '';
    let shown = 0;
    document.querySelectorAll('#v5-stock-grid .v5-stock-card').forEach((card) => {
      const visible = (!query || card.dataset.search.includes(query)) && (!category || card.dataset.category === category) && (!stock || card.dataset.stock === stock);
      card.classList.toggle('hidden', !visible);
      if (visible) shown += 1;
    });
    const count = document.querySelector('#v5-stock-count');
    if (count) count.textContent = `${shown} mặt hàng`;
  }

  renderPurchases = async function renderPurchasesV5() {
    const rows = await api('/api/purchase-requests');
    state.cache.purchases = rows;
    const admin = state.user.role === 'admin';
    const pending = rows.filter((x) => x.status === 'Chờ mua');
    const urgent = pending.filter((x) => x.priority === 'Gấp');
    pageNode().innerHTML = `
      ${intro('DANH SÁCH CẦN MUA', admin ? 'Đề xuất nguyên liệu cần mua' : 'Đề xuất mua nguyên liệu', 'Nhân viên gửi đề xuất; chủ cửa hàng cập nhật sau khi đã mua.', `<button class="btn" data-action="purchase-add">${icons.plus} Thêm đề xuất</button>`)}
      <section class="v5-summary-strip">
        ${summaryItem('Tổng đề xuất', rows.length, 'Toàn bộ lịch sử')}
        ${summaryItem('Đang chờ mua', pending.length, 'Cần chủ cửa hàng xử lý')}
        ${summaryItem('Ưu tiên gấp', urgent.length, 'Trong danh sách chờ')}
        ${summaryItem('Đã mua', rows.filter((x) => x.status === 'Đã mua').length, 'Đã hoàn thành')}
      </section>
      ${filterToolbar(`<div class="search-box">${icons.search}<input id="v5-purchase-search" placeholder="Tìm mặt hàng hoặc người đề xuất..."></div><select id="v5-purchase-status"><option value="">Tất cả trạng thái</option><option>Chờ mua</option><option>Đã mua</option></select><select id="v5-purchase-priority"><option value="">Tất cả ưu tiên</option><option>Gấp</option><option>Bình thường</option></select>${exportButton('purchases')}<span id="v5-purchase-count" class="v5-filter-count">${rows.length} đề xuất</span>`)}
      <div class="table-wrap"><table><thead><tr><th>Mặt hàng</th><th>Số lượng</th><th>Người đề xuất</th><th>Lý do</th><th>Ưu tiên</th><th>Ngày</th><th>Trạng thái</th>${admin ? '<th>Thao tác</th>' : ''}</tr></thead><tbody id="v5-purchase-rows">
        ${rows.map((x) => `<tr data-search="${esc(normalize(`${x.item_name} ${x.requester_name} ${x.reason}`))}" data-status="${esc(x.status)}" data-priority="${esc(x.priority)}"><td class="cell-main">${esc(x.item_name)}</td><td>${number(x.quantity, 2)} ${esc(x.unit)}</td><td>${esc(x.requester_name || '—')}</td><td>${esc(x.reason || '—')}</td><td>${badge(x.priority)}</td><td>${dateVN(x.requested_at)}</td><td>${badge(x.status)}</td>${admin ? `<td>${x.status === 'Chờ mua' ? `<button class="btn small success" data-action="purchase-status" data-id="${x.id}" data-status="Đã mua">${icons.check} Đã mua</button>` : `<button class="btn small secondary" data-action="purchase-status" data-id="${x.id}" data-status="Chờ mua">Mở lại</button>`}</td>` : ''}</tr>`).join('') || `<tr><td colspan="8">${empty('Chưa có đề xuất', 'Thêm mặt hàng cửa hàng cần mua.', 'cart')}</td></tr>`}
      </tbody></table></div>`;
  };

  function filterPurchases() {
    const query = normalize(document.querySelector('#v5-purchase-search')?.value || '');
    const status = document.querySelector('#v5-purchase-status')?.value || '';
    const priority = document.querySelector('#v5-purchase-priority')?.value || '';
    let shown = 0;
    document.querySelectorAll('#v5-purchase-rows tr').forEach((row) => {
      const visible = (!query || row.dataset.search.includes(query)) && (!status || row.dataset.status === status) && (!priority || row.dataset.priority === priority);
      row.classList.toggle('hidden', !visible);
      if (visible) shown += 1;
    });
    const count = document.querySelector('#v5-purchase-count');
    if (count) count.textContent = `${shown} đề xuất`;
  }

  /* ------------------------------------------------------------------
     Reports and notifications
  ------------------------------------------------------------------ */
  renderReports = async function renderReportsV5() {
    if (state.user.role !== 'admin') return navigate('dashboard');
    const d = await api(`/api/reports?month=${state.month}`);
    state.cache.report = d;
    const maxPay = Math.max(...d.payroll.map((x) => Number(x.total || 0)), 1);
    const maxHours = Math.max(...d.payroll.map((x) => Number(x.hours || 0)), 1);
    const unpaid = d.total_payroll - d.paid_payroll;
    pageNode().innerHTML = `
      ${intro('PHÂN TÍCH VẬN HÀNH', 'Báo cáo tháng', 'So sánh giờ công, chi phí lương và tiến độ thanh toán.', exportButton('reports', 'Xuất báo cáo'))}
      <section class="v5-summary-strip">
        ${summaryItem('Nhân viên', d.employee_count, 'Đang hoạt động')}
        ${summaryItem('Tổng giờ công', `${number(d.total_hours, 2)} giờ`, state.month)}
        ${summaryItem('Tổng bảng lương', money(d.total_payroll), 'Bao gồm điều chỉnh')}
        ${summaryItem('Chưa thanh toán', money(unpaid), `${d.total_payroll ? number(d.paid_payroll / d.total_payroll * 100, 0) : 0}% đã trả`)}
      </section>
      ${filterToolbar(`<input type="month" id="report-month" value="${state.month}"><span class="v5-filter-count">Dữ liệu cập nhật theo chấm công</span>`)}
      <section class="grid-2">
        <div class="card"><div class="card-head"><div><h3>Thực nhận theo nhân viên</h3><p>So sánh tổng lương trong tháng</p></div></div><div class="card-body"><div class="v5-chart">${d.payroll.sort((a,b) => Number(b.total) - Number(a.total)).map((x) => `<div class="v5-chart-row"><div class="v5-chart-label"><strong>${esc(x.name)}</strong><span>${number(x.hours, 2)} giờ</span></div><div class="v5-chart-track"><div class="v5-chart-fill" style="width:${Number(x.total || 0) / maxPay * 100}%"></div></div><div class="v5-chart-value">${money(x.total)}</div></div>`).join('') || '<div class="v5-empty-small">Chưa có dữ liệu</div>'}</div></div></div>
        <div class="card"><div class="card-head"><div><h3>Giờ công theo nhân viên</h3><p>Phát hiện chênh lệch khối lượng làm việc</p></div></div><div class="card-body"><div class="v5-chart">${d.payroll.sort((a,b) => Number(b.hours) - Number(a.hours)).map((x) => `<div class="v5-chart-row"><div class="v5-chart-label"><strong>${esc(x.name)}</strong><span>${esc(x.code || '')}</span></div><div class="v5-chart-track"><div class="v5-chart-fill matcha" style="width:${Number(x.hours || 0) / maxHours * 100}%"></div></div><div class="v5-chart-value">${number(x.hours, 2)} giờ</div></div>`).join('') || '<div class="v5-empty-small">Chưa có dữ liệu</div>'}</div></div></div>
      </section>`;
  };

  renderNotifications = async function renderNotificationsV5() {
    const rows = await api('/api/notifications');
    state.cache.notifications = rows;
    const unread = rows.filter((x) => !x.read_at).length;
    pageNode().innerHTML = `
      ${intro('TRUNG TÂM THÔNG BÁO', 'Cập nhật mới nhất', 'Lịch làm, kết quả phê duyệt, lương và kho nguyên liệu.', `<button class="btn secondary" data-action="notifications-read-all">${icons.check} Đánh dấu tất cả đã đọc</button>`)}
      <section class="v5-summary-strip">${summaryItem('Tổng thông báo', rows.length, 'Tối đa 100 thông báo')}${summaryItem('Chưa đọc', unread, unread ? 'Cần kiểm tra' : 'Đã đọc hết')}${summaryItem('Đã đọc', rows.length - unread, 'Lịch sử')}${summaryItem('Mới nhất', rows[0] ? dateTimeVN(rows[0].created_at) : '—', 'Thời điểm cập nhật')}</section>
      ${filterToolbar(`<div class="search-box">${icons.search}<input id="v5-notification-search" placeholder="Tìm nội dung thông báo..."></div><select id="v5-notification-status"><option value="">Tất cả</option><option value="unread">Chưa đọc</option><option value="read">Đã đọc</option></select><span id="v5-notification-count" class="v5-filter-count">${rows.length} thông báo</span>`)}
      <div class="card"><div class="card-body"><div id="v5-notification-list" class="list">${rows.map((x) => `<button class="list-row" style="width:100%;border-left:0;border-right:0;border-top:0;background:${x.read_at ? 'transparent' : '#fff8ef'};text-align:left" data-action="notification-read" data-id="${x.id}" data-search="${esc(normalize(`${x.title} ${x.message}`))}" data-read="${x.read_at ? 'read' : 'unread'}"><span class="list-icon">${icons.bell}</span><div class="list-copy"><strong>${esc(x.title)}</strong><span>${esc(x.message)}</span></div><div class="list-value">${dateTimeVN(x.created_at)}${!x.read_at ? '<br><span class="badge amber">Mới</span>' : ''}</div></button>`).join('') || empty('Không có thông báo', 'Mọi cập nhật quan trọng sẽ xuất hiện ở đây.', 'bell')}</div></div></div>`;
  };

  function filterNotifications() {
    const query = normalize(document.querySelector('#v5-notification-search')?.value || '');
    const status = document.querySelector('#v5-notification-status')?.value || '';
    let shown = 0;
    document.querySelectorAll('#v5-notification-list [data-search]').forEach((row) => {
      const visible = (!query || row.dataset.search.includes(query)) && (!status || row.dataset.read === status);
      row.classList.toggle('hidden', !visible);
      if (visible) shown += 1;
    });
    const count = document.querySelector('#v5-notification-count');
    if (count) count.textContent = `${shown} thông báo`;
  }

  async function downloadScheduleWeekXlsx(scope = 'schedule') {
    const startValue = scope === 'my' ? state.myWeekStart : state.scheduleWeekStart;
    const startDate = parseLocalDate(startValue);
    const endValue = localISO(addDays(startDate, 6));
    const params = new URLSearchParams({ start: startValue, end: endValue });
    if (scope === 'schedule' && state.scheduleLocationFilter) params.set('location_id', state.scheduleLocationFilter);
    const response = await fetch(`/api/export/schedule-week.xlsx?${params.toString()}`, {
      method: 'GET', credentials: 'same-origin', headers: { Accept: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' },
    });
    if (!response.ok) {
      let message = 'Không thể xuất lịch Excel';
      try { const payload = await response.json(); message = payload.message || message; } catch (_) {}
      throw new Error(message);
    }
    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const matched = disposition.match(/filename="?([^";]+)"?/i);
    const filename = matched?.[1] || `RUMI_lich_lam_tuan_${startValue}.xlsx`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = filename; document.body.appendChild(link); link.click(); link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1500);
    toast(`Đã xuất lịch tuần ${weekLabel(startDate)}`);
  }

  /* ------------------------------------------------------------------
     CSV exports
  ------------------------------------------------------------------ */
  const csvCell = (value) => `"${String(value ?? '').replace(/"/g, '""')}"`;
  function downloadCSV(filename, headers, rows) {
    const text = '\uFEFF' + [headers, ...rows].map((row) => row.map(csvCell).join(',')).join('\n');
    const blob = new Blob([text], { type: 'text/csv;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    URL.revokeObjectURL(link.href);
    link.remove();
    toast(`Đã tạo file ${filename}`);
  }

  function exportData(kind) {
    const stamp = new Date().toISOString().slice(0, 10);
    if (kind === 'employees') {
      const rows = state.cache.employees || [];
      return downloadCSV(`rumi-nhan-vien-${stamp}.csv`, ['Mã','Họ tên','Điện thoại','Email','Vị trí','Lương giờ','Tài khoản','Trạng thái'], rows.map((x) => [x.code,x.name,x.phone,x.email,x.role,x.hourly_wage,x.username,x.status]));
    }
    if (kind === 'shifts') {
      const rows = state.cache.shifts || state.cache.myShifts || [];
      return downloadCSV(`rumi-lich-lam-${stamp}.csv`, ['Ngày','Bắt đầu','Kết thúc','Nhân viên','Cửa hàng','Trạng thái'], rows.map((x) => [x.shift_date,x.start_time,x.end_time,x.employee_name,x.location_name,x.attendance?.status || x.status]));
    }
    if (kind === 'attendance') {
      const rows = state.cache.attendance || [];
      return downloadCSV(`rumi-bang-cong-${state.month}.csv`, ['Nhân viên','Ngày','Giờ vào','Giờ ra','Số giờ','Khoảng cách GPS','Sai số GPS','Trạng thái'], rows.map((x) => [x.employee_name || state.user.name,x.work_date,noValidClock(x)?'':x.check_in,noValidClock(x)?'':x.check_out,x.hours,x.check_in_distance_m,x.check_in_accuracy_m,x.status]));
    }
    if (kind === 'payroll') {
      const rows = state.cache.payroll || [];
      const body = rows.map((x) => [x.code,x.name,x.role,x.scheduled_shift_count || 0,x.completed_shift_count || x.attendance_count || 0,x.scheduled_hours,x.actual_hours,x.payable_hours || x.hours,x.payroll_state,x.missing_attendance_count || 0,x.incomplete_attendance_count || 0,x.late_minutes,x.early_leave_minutes,x.overtime_minutes,x.hourly_wage,x.estimated_salary || Number(x.scheduled_hours||0)*Number(x.hourly_wage||0),x.base_salary,x.bonus,x.penalty,x.advance_pay,x.total,x.payment_status,x.note]);
      body.push(['','TỔNG','','',total(rows,'completed_shift_count') || total(rows,'attendance_count'),total(rows,'scheduled_hours'),total(rows,'actual_hours'),total(rows,'payable_hours') || total(rows,'hours'),'','','',total(rows,'late_minutes'),total(rows,'early_leave_minutes'),total(rows,'overtime_minutes'),'',rows.reduce((a,x)=>a+Number(x.estimated_salary || Number(x.scheduled_hours||0)*Number(x.hourly_wage||0)),0),'',total(rows,'bonus'),total(rows,'penalty'),total(rows,'advance_pay'),total(rows,'total'),'','']);
      return downloadCSV(`rumi-bang-luong-${state.month}.csv`, ['Mã','Nhân viên','Vị trí','Ca theo lịch','Ca hoàn thành','Giờ theo lịch','Giờ thực tế','Giờ tính lương','Tình trạng công','Ca thiếu chấm công','Ca thiếu giờ ra','Phút đi trễ','Phút về sớm','Phút tăng ca','Lương/giờ','Lương dự kiến theo lịch','Lương cơ bản tính công','Thưởng','Phạt','Tạm ứng','Thực nhận','Thanh toán','Ghi chú'], body);
    }
    if (kind === 'inventory') {
      const rows = state.cache.inventory || [];
      return downloadCSV(`rumi-ton-kho-${stamp}.csv`, ['Nguyên liệu','Nhóm','Số lượng','Đơn vị','Mức tối thiểu','Giá nhập','Tình trạng'], rows.map((x) => [x.name,x.category,x.quantity,x.unit,x.min_stock,x.cost,Number(x.quantity)<=Number(x.min_stock)?'Sắp hết':'Còn đủ']));
    }
    if (kind === 'withdrawals') {
      const rows = state.cache.withdrawals || [];
      return downloadCSV(`rumi-lich-su-lay-hang-${stamp}.csv`, ['Ngày','Nguyên liệu','Số lượng','Đơn vị','Nhân viên','Ghi chú'], rows.map((x) => [x.taken_at,x.item_name,x.quantity,x.unit,x.employee_name,x.note]));
    }
    if (kind === 'purchases') {
      const rows = state.cache.purchases || [];
      return downloadCSV(`rumi-can-mua-${stamp}.csv`, ['Mặt hàng','Số lượng','Đơn vị','Người đề xuất','Lý do','Ưu tiên','Ngày','Trạng thái'], rows.map((x) => [x.item_name,x.quantity,x.unit,x.requester_name,x.reason,x.priority,x.requested_at,x.status]));
    }
    if (kind === 'reports') {
      const d = state.cache.report || { payroll: [] };
      return downloadCSV(`rumi-bao-cao-${state.month}.csv`, ['Mã','Nhân viên','Giờ công','Thực nhận','Thanh toán'], d.payroll.map((x) => [x.code,x.name,x.hours,x.total,x.payment_status]));
    }
    toast('Chưa có dữ liệu để xuất', 'error');
  }

  function openPrintDocument(title, body, {landscape = false, autoPrint = true} = {}) {
    const popup = window.open('', '_blank', landscape ? 'width=1280,height=850' : 'width=920,height=820');
    if (!popup) return toast('Trình duyệt đang chặn cửa sổ xuất PDF', 'error');
    popup.document.open();
    popup.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(title)}</title><style>
      @page{size:A4 ${landscape ? 'landscape' : 'portrait'};margin:12mm}*{box-sizing:border-box}body{font-family:Arial,"Helvetica Neue",sans-serif;color:#2d211b;margin:0;background:#fff;font-size:12px}.sheet{max-width:${landscape ? '1100px' : '820px'};margin:0 auto}.brand{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:3px solid #8b4e34;padding-bottom:14px}.brand h1{margin:0;font-size:25px;letter-spacing:.02em}.brand .meta{text-align:right;color:#78665d;line-height:1.6}.box{border:1px solid #dcc9bc;border-radius:14px;padding:18px;margin-top:18px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:11px 28px}.line{display:flex;justify-content:space-between;gap:24px;border-bottom:1px dashed #ded3cc;padding:9px 0}.line b{text-align:right}.total{font-size:20px;font-weight:800;border-top:2px solid #8b4e34;border-bottom:0;margin-top:4px}.muted{color:#78665d}.state{display:inline-flex;padding:5px 10px;border-radius:999px;background:#f4e8df;color:#7d432c;font-weight:700}.warning{background:#fff1cf;color:#8a5d00}.danger{background:#fde5df;color:#a33f31}.success{background:#e5f3e9;color:#2f704b}.notice{margin-top:14px;padding:12px 14px;border-radius:10px;background:#fff4e8;border-left:4px solid #bd6b3e;line-height:1.5}.foot{margin-top:34px;display:flex;justify-content:space-between;text-align:center}.sign{width:220px;line-height:1.8}table{width:100%;border-collapse:collapse;margin-top:16px;font-size:10px}th{background:#563426;color:#fff;text-align:left;padding:8px 6px}td{border-bottom:1px solid #e4d7ce;padding:7px 6px;vertical-align:top}.right{text-align:right}.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:16px}.summary div{border:1px solid #dfd0c5;border-radius:10px;padding:10px}.summary span{display:block;color:#78665d;font-size:10px}.summary strong{display:block;font-size:16px;margin-top:4px}.watermark{position:fixed;inset:40% 0 auto;text-align:center;font-size:72px;font-weight:900;color:rgba(139,78,52,.07);transform:rotate(-18deg);pointer-events:none}.printbar{position:fixed;right:20px;bottom:20px;display:flex;gap:8px}.printbar button{border:0;border-radius:10px;padding:11px 16px;background:#8b4e34;color:#fff;font-weight:700;cursor:pointer;box-shadow:0 8px 28px rgba(61,40,31,.2)}@media print{.printbar{display:none}.sheet{max-width:none}.watermark{position:fixed}}
    </style></head><body>${body}<div class="printbar"><button id="rumi-print-button" type="button">Lưu / In PDF</button></div></body></html>`);
    popup.document.close();
    const printButton = popup.document.getElementById('rumi-print-button');
    printButton?.addEventListener('click', () => popup.print());
    popup.focus();
    if (autoPrint) window.setTimeout(() => { try { popup.print(); } catch {} }, 450);
    return popup;
  }

  function printPayslip(employeeId) {
    const row = (state.cache.payroll || []).find((x) => Number(x.employee_id) === Number(employeeId));
    if (!row) return toast('Không tìm thấy phiếu lương', 'error');
    const runStatus = state.cache.payrollRun?.status || 'Tạm tính';
    const issueCount = Number(row.pending_checkin_count || 0) + Number(row.late_unclocked_count || 0) + Number(row.no_show_risk_count || 0) + Number(row.absent_shift_count || 0) + Number(row.incomplete_attendance_count || 0) + Number(row.upcoming_shift_count || 0) + Number(row.active_shift_count || 0);
    const stateTone = row.payroll_state === 'Đủ dữ liệu' ? 'success' : (['Vắng ca','Nguy cơ vắng ca','Thiếu giờ ra'].includes(row.payroll_state) ? 'danger' : 'warning');
    const explanation = issueCount
      ? `Phiếu hiện chưa đủ điều kiện thanh toán vì còn ${issueCount} ca chưa hoàn tất hoặc cần quản lý xử lý.`
      : (Number(row.total || 0) <= 0 ? 'Phiếu không phát sinh số tiền phải trả trong tháng này.' : 'Dữ liệu công đã đầy đủ theo trạng thái hiện tại.');
    const watermark = runStatus === 'Đã chốt' ? '' : '<div class="watermark">TẠM TÍNH</div>';
    const body = `<div class="sheet">${watermark}<header class="brand"><div><h1>RUMI · PHIẾU LƯƠNG</h1><div class="muted">Bảng kê lương nhân viên</div></div><div class="meta">Tháng <b>${esc(state.month)}</b><br>Trạng thái bảng: <b>${esc(runStatus)}</b></div></header>
      <section class="box"><div class="grid"><div><b>Nhân viên</b><br>${esc(row.name)}</div><div><b>Mã nhân viên</b><br>${esc(row.code || '')}</div><div><b>Vị trí</b><br>${esc(row.role || '')}</div><div><b>Lương theo giờ</b><br>${money(row.hourly_wage)}</div></div>
      <div class="line"><span>Ca theo lịch / hoàn thành</span><b>${row.scheduled_shift_count || 0} / ${row.completed_shift_count || row.attendance_count || 0} ca</b></div>
      <div class="line"><span>Giờ theo lịch</span><b>${number(row.scheduled_hours,2)} giờ</b></div>
      <div class="line"><span>Giờ thực tế</span><b>${number(row.actual_hours,2)} giờ</b></div>
      <div class="line"><span>Giờ tính lương</span><b>${number(row.payable_hours || row.hours,2)} giờ</b></div>
      <div class="line"><span>Tình trạng công</span><b><span class="state ${stateTone}">${esc(row.payroll_state || 'Chưa có dữ liệu')}</span></b></div>
      <div class="line"><span>Vắng / nguy cơ vắng / thiếu giờ ra</span><b>${row.absent_shift_count || 0} / ${row.no_show_risk_count || 0} / ${row.incomplete_attendance_count || 0} ca</b></div>
      <div class="line"><span>Đi trễ / về sớm / tăng ca duyệt</span><b>${row.late_minutes || 0}p / ${row.early_leave_minutes || 0}p / ${row.overtime_minutes || 0}p</b></div>
      <div class="line"><span>Lương cơ bản</span><b>${money(row.base_salary)}</b></div><div class="line"><span>Thưởng</span><b>+ ${money(row.bonus)}</b></div><div class="line"><span>Phạt</span><b>- ${money(row.penalty)}</b></div><div class="line"><span>Tạm ứng</span><b>- ${money(row.advance_pay)}</b></div><div class="line total"><span>THỰC NHẬN</span><b>${money(row.total)}</b></div>
      <div class="notice"><b>Giải thích:</b> ${esc(explanation)}<br><span class="muted">Thanh toán: ${esc(row.payment_status || 'Chưa thanh toán')} · Ghi chú: ${esc(row.note || 'Không có')}</span></div></section>
      <div class="foot"><div class="sign"><b>Người lập bảng</b><br><br><br>________________</div><div class="sign"><b>Nhân viên xác nhận</b><br><br><br>________________</div></div></div>`;
    openPrintDocument(`RUMI - Phiếu lương ${row.name} - ${state.month}`, body);
  }

  function printPayrollReport() {
    const rows = state.cache.payroll || [];
    if (!rows.length) return toast('Chưa có bảng lương để xuất PDF', 'error');
    const runStatus = state.cache.payrollRun?.status || 'Tạm tính';
    const totalAmount = total(rows, 'total');
    const unresolved = rows.reduce((sum, x) => sum + Number(x.pending_checkin_count||0) + Number(x.late_unclocked_count||0) + Number(x.no_show_risk_count||0) + Number(x.absent_shift_count||0) + Number(x.incomplete_attendance_count||0) + Number(x.upcoming_shift_count||0) + Number(x.active_shift_count||0), 0);
    const bodyRows = rows.map((x, index) => `<tr><td>${index+1}</td><td><b>${esc(x.name)}</b><br><span class="muted">${esc(x.code || '')} · ${esc(x.role || '')}</span></td><td class="right">${x.scheduled_shift_count||0}<br><span class="muted">${number(x.scheduled_hours,2)}h</span></td><td class="right">${x.completed_shift_count||x.attendance_count||0}<br><span class="muted">${number(x.payable_hours||x.hours,2)}h lương</span></td><td>${esc(x.payroll_state||'')}</td><td class="right">${money(x.base_salary)}</td><td class="right">+${money(x.bonus)}<br>-${money(Number(x.penalty||0)+Number(x.advance_pay||0))}</td><td class="right"><b>${money(x.total)}</b></td><td>${esc(x.payment_status||'')}</td></tr>`).join('');
    const watermark = runStatus === 'Đã chốt' ? '' : '<div class="watermark">BẢN NHÁP</div>';
    const body = `<div class="sheet">${watermark}<header class="brand"><div><h1>RUMI · BẢNG LƯƠNG THÁNG</h1><div class="muted">Bảng tổng hợp lương nhân viên</div></div><div class="meta">Tháng <b>${esc(state.month)}</b><br>Trạng thái: <b>${esc(runStatus)}</b><br>Xuất lúc: ${new Date().toLocaleString('vi-VN')}</div></header>
      <section class="summary"><div><span>Nhân viên</span><strong>${rows.length}</strong></div><div><span>Giờ tính lương</span><strong>${number(total(rows,'payable_hours')||total(rows,'hours'),2)}h</strong></div><div><span>Ca chưa hoàn tất</span><strong>${unresolved}</strong></div><div><span>Tổng thực nhận</span><strong>${money(totalAmount)}</strong></div></section>
      ${unresolved ? `<div class="notice"><b>Cảnh báo:</b> Còn ${unresolved} ca chưa hoàn tất. Đây là số liệu ${runStatus === 'Đã chốt' ? 'đã chốt' : 'tạm tính'}; hãy xử lý công trước khi thanh toán.</div>` : ''}
      <table><thead><tr><th>#</th><th>Nhân viên</th><th>Ca lịch</th><th>Ca công</th><th>Tình trạng</th><th class="right">Lương cơ bản</th><th class="right">Điều chỉnh</th><th class="right">Thực nhận</th><th>Thanh toán</th></tr></thead><tbody>${bodyRows}<tr><td colspan="7"><b>TỔNG CỘNG</b></td><td class="right"><b>${money(totalAmount)}</b></td><td></td></tr></tbody></table>
      <div class="foot"><div class="sign"><b>Người lập bảng</b><br><br><br>________________</div><div class="sign"><b>Chủ cửa hàng duyệt</b><br><br><br>________________</div></div></div>`;
    openPrintDocument(`RUMI - Bảng lương ${state.month}`, body, {landscape:true});
  }

  /* ------------------------------------------------------------------
     Global command search
  ------------------------------------------------------------------ */
  async function openCommand() {
    if (document.querySelector('#modal-root .modal-backdrop')) return;
    closeCommand();
    const root = document.createElement('div');
    root.id = 'v5-command-root';
    root.className = 'v5-command-backdrop';
    root.innerHTML = `<section class="v5-command"><div class="v5-command-search">${icons.search}<input id="v5-command-input" placeholder="Tìm trang, nhân viên, nguyên liệu, ca làm..." autocomplete="off"><span class="v5-shortcut">ESC</span></div><div id="v5-command-results" class="v5-command-results"><div class="v5-command-empty">Đang tải dữ liệu tìm kiếm…</div></div></section>`;
    root.addEventListener('click', closeCommand);
    root.querySelector('.v5-command')?.addEventListener('click', (event) => event.stopPropagation());
    document.body.appendChild(root);
    const input = document.querySelector('#v5-command-input');
    input.focus();
    let employeeRows = [];
    let inventoryRows = [];
    let shiftRows = [];
    try {
      const calls = [api('/api/inventory'), api(`/api/shifts?start=${today()}`)];
      if (state.user.role === 'admin') calls.unshift(api('/api/employees'));
      const results = await Promise.all(calls);
      if (state.user.role === 'admin') [employeeRows, inventoryRows, shiftRows] = results;
      else [inventoryRows, shiftRows] = results;
    } catch {}
    const pages = (state.user.role === 'admin' ? navAdmin : navEmployee).map(([, id, label, icon]) => ({ type:'Trang', title:label, sub:'Mở chức năng', page:id, icon }));
    const entries = [
      ...pages,
      ...employeeRows.map((x) => ({ type:'Nhân viên', title:x.name, sub:`${x.code} · ${x.role}`, page:'employees', icon:'users' })),
      ...inventoryRows.map((x) => ({ type:'Kho', title:x.name, sub:`Còn ${number(x.quantity,2)} ${x.unit}`, page:'inventory', icon:'box' })),
      ...shiftRows.slice(0, 40).map((x) => ({ type:'Ca làm', title:state.user.role === 'admin' ? x.employee_name : x.location_name, sub:`${dateVN(x.shift_date)} · ${x.start_time}–${x.end_time}`, page:state.user.role === 'admin' ? 'schedule' : 'shifts', icon:'calendar' })),
    ];
    const draw = () => {
      if (!root.isConnected) return;
      const resultsNode = root.querySelector('#v5-command-results');
      if (!resultsNode) return;
      const q = normalize(input.value);
      const filtered = entries.filter((x) => !q || normalize(`${x.type} ${x.title} ${x.sub}`).includes(q)).slice(0, 18);
      resultsNode.innerHTML = filtered.length ? filtered.map((x) => `<button class="v5-command-item" data-v5-command-page="${x.page}"><span>${icons[x.icon] || icons.search}</span><span><strong>${esc(x.title)}</strong><small>${esc(x.type)} · ${esc(x.sub)}</small></span></button>`).join('') : '<div class="v5-command-empty">Không tìm thấy kết quả phù hợp.</div>';
    };
    if (!root.isConnected) return;
    input.addEventListener('input', draw);
    draw();
  }

  function closeCommand() { document.querySelector('#v5-command-root')?.remove(); }

  /* ------------------------------------------------------------------
     Events and navigation wrapper
  ------------------------------------------------------------------ */
  const legacyNavigate = navigate;
  navigate = async function navigateV5(page) {
    if (state.user) {
      try { sessionStorage.setItem('rumi-last-page', page); } catch (_) {}
      try { history.replaceState(null, '', `/#${page}`); } catch (_) {}
    }
    const result = await legacyNavigate(page);
    afterRender();
    return result;
  };

  const legacyEnterApp = enterApp;
  enterApp = function enterAppV5(user, dashboard = null, unreadCount = null) {
    // Preserve the bootstrap payload. Dropping these arguments forced an
    // unnecessary second dashboard request and temporarily showed stale counts.
    legacyEnterApp(user, dashboard, unreadCount);
    window.setTimeout(() => {
      let remembered = null;
      try { remembered = sessionStorage.getItem('rumi-last-page'); } catch (_) {}
      const allowed = (user.role === 'admin' ? navAdmin : navEmployee).some((item) => item[1] === remembered);
      if (allowed && remembered !== state.page) navigate(remembered);
      afterRender();
    }, 80);
  };

  document.addEventListener('input', (event) => {
    if (event.target.matches('#v5-employee-search')) filterEmployees();
    if (event.target.matches('#v5-attendance-search')) filterAttendance();
    if (event.target.matches('#v5-payroll-search')) filterPayroll();
    if (event.target.matches('#v5-stock-search')) filterInventory();
    if (event.target.matches('#v5-purchase-search')) filterPurchases();
    if (event.target.matches('#v5-notification-search')) filterNotifications();
  });

  document.addEventListener('change', (event) => {
    if (event.target.matches('#v5-employee-status,#v5-employee-role')) filterEmployees();
    if (event.target.matches('#v5-attendance-status')) filterAttendance();
    if (event.target.matches('#v5-payroll-status')) filterPayroll();
    if (event.target.matches('#v5-stock-category,#v5-stock-status')) filterInventory();
    if (event.target.matches('#v5-purchase-status,#v5-purchase-priority')) filterPurchases();
    if (event.target.matches('#v5-notification-status')) filterNotifications();
    if (event.target.matches('#v5-schedule-location')) {
      state.scheduleLocationFilter = event.target.value;
      renderSchedule().then(afterRender).catch((error) => toast(error.message, 'error'));
    }
  });

  document.addEventListener('click', async (event) => {
    const commandPage = event.target.closest('[data-v5-command-page]');
    if (commandPage) {
      closeCommand();
      navigate(commandPage.dataset.v5CommandPage);
      return;
    }
    const button = event.target.closest('[data-v5-action]');
    if (!button) return;
    const action = button.dataset.v5Action;
    try {
      if (action === 'command') return openCommand();
      if (action === 'refresh') return navigate(state.page);
      if (action === 'export') return exportData(button.dataset.export);
      if (action === 'attendance-remind') {
        await api('/api/attendance/alerts/remind', {method:'POST', body:{id:Number(button.dataset.id)}});
        toast('Đã gửi nhắc nhở cho nhân viên');
        return navigate(state.page);
      }
      if (action === 'attendance-resolve') {
        const mode = button.dataset.mode || 'dismiss';
        const label = mode === 'absent' ? 'xác nhận nhân viên vắng ca' : 'đóng cảnh báo này';
        if (!confirm(`Bạn muốn ${label}?`)) return;
        await api('/api/attendance/alerts/resolve', {method:'POST', body:{id:Number(button.dataset.id), action:mode}});
        toast(mode === 'absent' ? 'Đã xác nhận vắng ca' : 'Đã đóng cảnh báo');
        return navigate(state.page);
      }
      if (action === 'schedule-xlsx') {
        button.disabled = true;
        const original = button.innerHTML;
        button.innerHTML = '<span class="loader" style="width:16px;height:16px;border-width:2px"></span> Đang tạo Excel';
        try { await downloadScheduleWeekXlsx(button.dataset.scope || 'schedule'); }
        finally { button.disabled = false; button.innerHTML = original; }
        return;
      }
      if (action === 'auto-assign') {
        const form = document.querySelector('#v53-schedule-form');
        if (!form || !form.reportValidity()) return;
        const data = Object.fromEntries(new FormData(form).entries());
        state.candidateQuery = {...data};
        if (!confirm(`Xếp tự động ${data.employee_count} nhân viên cho ca ${data.date} ${data.start}–${data.end}?`)) return;
        button.disabled = true;
        const result = await api('/api/scheduling/auto-assign', {method:'POST', body:{shift_date:data.date,start_time:data.start,end_time:data.end,location_id:data.location_id,required_role:data.required_role,employee_count:data.employee_count,note:data.note}});
        state.candidates = []; toast(`Đã xếp ${result.length} nhân viên phù hợp`);
        return renderSchedule().then(afterRender);
      }
      if (action === 'payroll-generate') {
        await api('/api/payroll/generate', {method:'POST', body:{month:state.month}}); toast('Đã tính lại bảng lương tháng'); return renderPayroll().then(afterRender);
      }
      if (action === 'payroll-lock') {
        if (!confirm(`Chốt bảng lương tháng ${state.month}? Sau khi chốt, giờ công và điều chỉnh sẽ được giữ ổn định.`)) return;
        await api('/api/payroll/lock', {method:'POST', body:{month:state.month}}); toast('Đã chốt bảng lương'); return renderPayroll().then(afterRender);
      }
      if (action === 'payroll-unlock') {
        if (!confirm(`Mở khóa bảng lương tháng ${state.month} để chỉnh sửa?`)) return;
        await api('/api/payroll/unlock', {method:'POST', body:{month:state.month}}); toast('Đã mở khóa bảng lương'); return renderPayroll().then(afterRender);
      }
      if (action === 'payroll-slip') return printPayslip(button.dataset.id);
      if (action === 'payroll-pdf') {
        if (state.user.role === 'employee') {
          const own = (state.cache.payroll || [])[0];
          return own ? printPayslip(own.employee_id) : toast('Chưa có phiếu lương', 'error');
        }
        return printPayrollReport();
      }
      if (action === 'week') {
        const scope = button.dataset.scope;
        const key = scope === 'schedule' ? 'scheduleWeekStart' : 'myWeekStart';
        state[key] = localISO(addDays(parseLocalDate(state[key]), Number(button.dataset.step || 0)));
        return (scope === 'schedule' ? renderSchedule() : renderMyShifts()).then(afterRender);
      }
      if (action === 'week-today') {
        const scope = button.dataset.scope;
        state[scope === 'schedule' ? 'scheduleWeekStart' : 'myWeekStart'] = localISO(mondayOf());
        return (scope === 'schedule' ? renderSchedule() : renderMyShifts()).then(afterRender);
      }
      if (action === 'gps-test') {
        const title = document.querySelector('#v5-gps-title');
        const text = document.querySelector('#v5-gps-text');
        button.disabled = true;
        button.innerHTML = '<span class="loader" style="width:16px;height:16px;border-width:2px"></span> Đang kiểm tra';
        if (!navigator.geolocation) throw new Error('Trình duyệt không hỗ trợ GPS');
        navigator.geolocation.getCurrentPosition((position) => {
          const accuracy = Math.round(position.coords.accuracy);
          if (title) title.textContent = accuracy <= 100 ? 'GPS đã sẵn sàng' : 'GPS có sai số khá cao';
          if (text) text.textContent = `Sai số hiện tại khoảng ${accuracy} m. Vĩ độ ${position.coords.latitude.toFixed(6)}, kinh độ ${position.coords.longitude.toFixed(6)}.`;
          button.disabled = false;
          button.innerHTML = `${icons.check} Kiểm tra lại`;
          toast(`Đã lấy vị trí với sai số ${accuracy} m`);
        }, (error) => {
          button.disabled = false;
          button.innerHTML = `${icons.gps} Kiểm tra vị trí`;
          if (title) title.textContent = 'Chưa lấy được vị trí';
          if (text) text.textContent = error.message;
          toast(`Không lấy được GPS: ${error.message}`, 'error');
        }, { enableHighAccuracy:true, timeout:15000, maximumAge:0 });
      }
    } catch (error) {
      button.disabled = false;
      toast(error.message, 'error');
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      if (document.querySelector('#modal-root .modal-backdrop')) closeModal();
      else closeCommand();
      return;
    }
    if (event.key === '/' && !document.querySelector('#modal-root .modal-backdrop') && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || '')) {
      event.preventDefault();
      openCommand().catch((error) => toast(error.message || 'Không thể mở tìm kiếm', 'error'));
    }
  });

  let renderTimer;
  const observer = new MutationObserver(() => {
    clearTimeout(renderTimer);
    renderTimer = window.setTimeout(afterRender, 40);
  });
  if (pageNode()) observer.observe(pageNode(), { childList:true, subtree:false });

  window.setInterval(updateCountdowns, 30000);
  window.setTimeout(afterRender, 0);

  return { VERSION, afterRender, exportData, openCommand };
})();
