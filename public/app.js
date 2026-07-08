'use strict';

const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const today = () => new Date().toISOString().slice(0, 10);
const monthNow = () => new Date().toISOString().slice(0, 7);
const APP_VERSION = '6.4.4';
const state = {
  user: null,
  page: 'dashboard',
  month: monthNow(),
  requestTab: 'availability',
  candidates: [],
  candidateQuery: { date: today(), start: '08:00', end: '12:00', location_id: '', required_role: '', employee_count: '1' },
  cache: {},
  prefetchedDashboard: null,
  lastUnreadRefresh: 0,
};

const apiMemory = new Map();
const apiInflight = new Map();

const icons = {
  dashboard: '<svg viewBox="0 0 24 24"><path d="M4 13h6V4H4v9Zm10 7h6V11h-6v9ZM4 20h6v-3H4v3Zm10-13h6V4h-6v3Z"/></svg>',
  users: '<svg viewBox="0 0 24 24"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
  calendar: '<svg viewBox="0 0 24 24"><path d="M6 2v4M18 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2Z"/></svg>',
  request: '<svg viewBox="0 0 24 24"><path d="M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
  clock: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  money: '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 15h.01M17 9h.01M8 12h8"/></svg>',
  box: '<svg viewBox="0 0 24 24"><path d="m21 8-9-5-9 5 9 5 9-5ZM3 8v8l9 5 9-5V8M12 13v8"/></svg>',
  cart: '<svg viewBox="0 0 24 24"><path d="M3 3h2l2.4 11.5a2 2 0 0 0 2 1.5h7.8a2 2 0 0 0 2-1.6L21 7H6M10 21h.01M18 21h.01"/></svg>',
  location: '<svg viewBox="0 0 24 24"><path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></svg>',
  report: '<svg viewBox="0 0 24 24"><path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/></svg>',
  bell: '<svg viewBox="0 0 24 24"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></svg>',
  plus: '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>',
  edit: '<svg viewBox="0 0 24 24"><path d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L8 18l-4 1 1-4L16.5 3.5Z"/></svg>',
  trash: '<svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4h8v2M19 6l-1 15H6L5 6M10 11v5M14 11v5"/></svg>',
  search: '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>',
  check: '<svg viewBox="0 0 24 24"><path d="m5 12 4 4L19 6"/></svg>',
  x: '<svg viewBox="0 0 24 24"><path d="m6 6 12 12M18 6 6 18"/></svg>',
  key: '<svg viewBox="0 0 24 24"><circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M15 4l2 2M18 1l2 2"/></svg>',
  gps: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="8"/><path d="M12 2V0M12 24v-2M2 12H0M24 12h-2"/></svg>',
  info: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>',
  logout: '<svg viewBox="0 0 24 24"><path d="M10 17l5-5-5-5M15 12H3M15 3h5v18h-5"/></svg>',
  settings: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06-2.83 2.83-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21h-4v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06-2.83-2.83.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3v-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06L7.04 4.3l.06.06A1.65 1.65 0 0 0 8.92 4a1.65 1.65 0 0 0 1-1.51V2h4v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06 2.83 2.83-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21v4h-.09a1.65 1.65 0 0 0-1.51 1Z"/></svg>',
  tea: '<svg viewBox="0 0 24 24"><path d="M6 7h12l-1 14H7L6 7ZM4 7h16M9 3h6M13 3l3-3"/><circle cx="10" cy="16" r="1"/><circle cx="14" cy="18" r="1"/></svg>',
};

const navAdmin = [
  ['Quản trị', 'dashboard', 'Tổng quan', 'dashboard'], ['Quản trị', 'employees', 'Nhân viên', 'users'],
  ['Vận hành', 'schedule', 'Xếp lịch làm', 'calendar'], ['Vận hành', 'requests', 'Yêu cầu & duyệt', 'request'],
  ['Vận hành', 'attendance', 'Bảng công', 'clock'], ['Tài chính', 'payroll', 'Bảng lương', 'money'],
  ['Kho hàng', 'inventory', 'Tồn kho', 'box'], ['Kho hàng', 'purchases', 'Cần mua', 'cart'],
  ['Hệ thống', 'locations', 'Vị trí & quy định', 'location'], ['Hệ thống', 'reports', 'Báo cáo', 'report'],
  ['Hệ thống', 'notifications', 'Thông báo', 'bell'],
];
const navEmployee = [
  ['Cá nhân', 'dashboard', 'Tổng quan', 'dashboard'], ['Cá nhân', 'shifts', 'Lịch làm của tôi', 'calendar'],
  ['Cá nhân', 'availability', 'Đăng ký lịch rảnh', 'request'], ['Cá nhân', 'requests', 'Xin nghỉ & thay ca', 'request'],
  ['Công việc', 'attendance', 'Chấm công GPS', 'clock'], ['Công việc', 'payroll', 'Lương của tôi', 'money'],
  ['Kho hàng', 'inventory', 'Lấy nguyên liệu', 'box'], ['Kho hàng', 'purchases', 'Đề xuất cần mua', 'cart'],
  ['Cá nhân', 'notifications', 'Thông báo', 'bell'],
];

function esc(v) { return String(v ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function money(v) { return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(Number(v || 0)); }
function number(v, d = 0) { return new Intl.NumberFormat('vi-VN', { maximumFractionDigits: d }).format(Number(v || 0)); }
function dateVN(v) { if (!v) return '—'; const [y,m,d] = String(v).slice(0,10).split('-'); return `${d}/${m}/${y}`; }
function dateTimeVN(v) { if (!v) return '—'; return new Intl.DateTimeFormat('vi-VN', { dateStyle:'short', timeStyle:'short' }).format(new Date(v)); }
function initials(name) { return String(name || 'R').trim().split(/\s+/).slice(-2).map(x => x[0]).join('').toUpperCase(); }
function badge(status) {
  const s = String(status || '');
  const cls = /Đã duyệt|Đã xếp|Đã xác nhận|Hoàn thành|Đã thanh toán|Đã mua|Đang làm|Đủ dữ liệu/.test(s) ? 'green' : /Từ chối|Đã hủy|Nghỉ việc|Thiếu chấm công|Thiếu giờ ra/.test(s) ? 'red' : /Chờ|Gấp|Sắp|Đến giờ chấm công|Chưa đủ điều kiện/.test(s) ? 'amber' : /Đang|Chưa đến ca/.test(s) ? 'blue' : 'gray';
  return `<span class="badge ${cls}">${esc(s || 'Không rõ')}</span>`;
}
function empty(title, text, icon = 'tea') { return `<div class="empty"><div>${icons[icon]}<strong>${esc(title)}</strong><p>${esc(text)}</p></div></div>`; }
function stat(label, value, note, icon = 'dashboard', tone = '') { return `<article class="stat-card"><div class="stat-top"><span class="stat-label">${esc(label)}</span><span class="stat-icon ${tone}">${icons[icon]}</span></div><div class="stat-value">${value}</div><div class="stat-note">${esc(note)}</div></article>`; }
function person(name, sub = '') { return `<div class="person-cell"><span class="avatar">${esc(initials(name))}</span><span><span class="cell-main">${esc(name || '—')}</span><span class="cell-sub">${esc(sub)}</span></span></div>`; }
function intro(eyebrow, title, description, actions = '') { return `<div class="page-intro"><div><span class="eyebrow">${esc(eyebrow)}</span><h2>${esc(title)}</h2><p>${esc(description)}</p></div><div class="page-intro-actions">${actions}</div></div>`; }

function apiTtl(path) {
  if (path.includes('/notifications/unread-count')) return 30000;
  if (path.includes('/settings') || path.includes('/locations')) return 30000;
  if (path.includes('/employees')) return 15000;
  return 10000;
}
function clearApiCache() { apiMemory.clear(); apiInflight.clear(); }
async function api(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const cacheable = method === 'GET' && options.cache !== false;
  const now = Date.now();
  if (cacheable && !options.force) {
    const cached = apiMemory.get(path);
    if (cached && cached.expires > now) return cached.data;
    if (apiInflight.has(path)) return apiInflight.get(path);
  }
  const task = (async () => {
    const headers = { Accept: 'application/json', ...(options.headers || {}) };
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    if (method !== 'GET') headers['X-RUMI-Request'] = '1';
    const response = await fetch(path, {
      method, headers, credentials: 'same-origin',
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
    let payload;
    try { payload = await response.json(); } catch { payload = { ok:false, message:'Máy chủ trả về dữ liệu không hợp lệ' }; }
    if (!response.ok || !payload.ok) {
      if (response.status === 401 && !path.includes('/auth/login')) showLogin();
      throw new Error(payload.message || 'Có lỗi xảy ra');
    }
    if (cacheable) apiMemory.set(path, { data: payload.data, expires: Date.now() + apiTtl(path) });
    else clearApiCache();
    return payload.data;
  })();
  if (cacheable) apiInflight.set(path, task);
  try { return await task; } finally { if (cacheable) apiInflight.delete(path); }
}

function toast(message, type = 'success') {
  const root = $('#toast-root');
  const node = document.createElement('div');
  node.className = `toast ${type === 'error' ? 'error' : ''}`;
  node.innerHTML = `<div class="toast-icon">${type === 'error' ? icons.x : icons.check}</div><div><strong>${type === 'error' ? 'Không thể thực hiện' : 'RUMI đã cập nhật'}</strong><span>${esc(message)}</span></div>`;
  root.appendChild(node);
  setTimeout(() => node.remove(), 4200);
}
function loading() { $('#page').innerHTML = '<div class="loading-screen"><span class="loader"></span><p>Đang tải dữ liệu RUMI...</p><div class="loading-hint">Các trang vừa mở sẽ được lưu tạm để chuyển lại nhanh hơn.</div></div>'; }
function openModal(title, subtitle, content, wide = false) {
  const modalRoot = $('#modal-root');
  if (!modalRoot) return toast('Không thể mở hộp thoại. Vui lòng tải lại trang.', 'error');
  if (typeof closeCommand === 'function') closeCommand();
  modalRoot.innerHTML = `<div class="modal-backdrop" data-modal-backdrop><section class="modal ${wide ? 'wide' : ''}" role="dialog" aria-modal="true" aria-label="${esc(title)}"><header class="modal-head"><div><h3>${esc(title)}</h3><p>${esc(subtitle)}</p></div><button type="button" class="modal-close" data-action="close-modal" aria-label="Đóng">${icons.x}</button></header><div class="modal-body">${content}</div></section></div>`;
  const backdrop = modalRoot.querySelector('[data-modal-backdrop]');
  backdrop?.addEventListener('click', (event) => {
    if (event.target === backdrop) closeModal();
  });
  document.body.classList.add('modal-open');
  setTimeout(() => modalRoot.querySelector('input:not([type="hidden"]), select, textarea, button')?.focus(), 50);
}
function closeModal() {
  const modalRoot = $('#modal-root');
  if (modalRoot) modalRoot.innerHTML = '';
  document.body.classList.remove('modal-open');
}

function updateClock() {
  const now = new Date();
  $('#live-time').textContent = now.toLocaleTimeString('vi-VN', { hour:'2-digit', minute:'2-digit' });
  $('#live-date').textContent = now.toLocaleDateString('vi-VN', { weekday:'short', day:'2-digit', month:'2-digit' });
}
setInterval(updateClock, 1000);

function authLayout(card) {
  return `<section class="auth-visual"><div class="auth-brand"><div class="brand-mark">${icons.tea}</div><div><strong>RUMI</strong><span>MILK TEA MANAGER</span></div></div><div class="auth-copy"><span class="eyebrow">VẬN HÀNH THÔNG MINH</span><h1>Nhẹ nhàng quản lý,<br>trọn vị mỗi ca làm.</h1><p>Phân ca theo lịch rảnh, chấm công đúng cửa hàng bằng GPS, tính lương theo giờ và kiểm soát nguyên liệu trong một hệ thống đồng nhất.</p><div class="feature-row"><span class="feature-pill">Phân quyền rõ ràng</span><span class="feature-pill">Chấm công GPS</span><span class="feature-pill">Lương theo giờ</span><span class="feature-pill">Kho tự động</span></div></div><div class="auth-foot">RUMI dùng các bảng riêng <strong>rumi_*</strong>, không đụng dữ liệu IC3 Smart Class.</div></section><section class="auth-panel">${card}</section>`;
}
function showLogin() {
  state.user = null;
  state.prefetchedDashboard = null;
  clearApiCache();
  history.replaceState(null, '', '/#login');
  $('#app-root').classList.add('hidden');
  $('#auth-root').classList.remove('hidden');
  $('#auth-root').innerHTML = authLayout(`<form class="auth-card" data-form="login"><div class="auth-logo-mobile"><div class="brand-mark">${icons.tea}</div><strong>RUMI</strong></div><span class="eyebrow">ĐĂNG NHẬP HỆ THỐNG</span><h2>Chào mừng trở lại</h2><p>Hệ thống sẽ tự đưa bạn đến đúng trang theo vai trò quản trị hoặc nhân viên.</p><div class="field"><label>Tên đăng nhập</label><input name="username" autocomplete="username" required placeholder="Ví dụ: an.nguyen"></div><div class="field" style="margin-top:13px"><label>Mật khẩu</label><input type="password" name="password" autocomplete="current-password" required placeholder="••••••••"></div><button class="btn" type="submit">${icons.key} Đăng nhập</button><div class="auth-hint">Không có chức năng tự đăng ký. Tài khoản admin bổ sung do quản trị viên hiện tại tạo; tài khoản nhân viên chỉ do admin thêm, sửa hoặc xóa.</div></form>`);
}
function buildNav() {
  const items = state.user.role === 'admin' ? navAdmin : navEmployee;
  let lastGroup = '';
  $('#nav').innerHTML = items.map(([group, id, label, icon]) => {
    const heading = group !== lastGroup ? `<div class="nav-group">${esc(group)}</div>` : '';
    lastGroup = group;
    return `${heading}<button class="nav-button ${state.page === id ? 'active' : ''}" data-nav="${id}">${icons[icon]}<span>${esc(label)}</span>${id === 'notifications' && state.cache.unread ? `<span class="nav-badge">${state.cache.unread}</span>` : ''}</button>`;
  }).join('');
}
function enterApp(user, dashboard = null, unreadCount = null) {
  state.user = user;
  state.prefetchedDashboard = dashboard;
  if (unreadCount != null) state.cache.unread = Number(unreadCount || 0);
  history.replaceState(null, '', '/#dashboard');
  $('#auth-root').classList.add('hidden');
  $('#app-root').classList.remove('hidden');
  const name = user.name || user.username;
  $('#sidebar-name').textContent = name;
  $('#top-name').textContent = name;
  $('#sidebar-role').textContent = user.role === 'admin' ? 'Quản trị viên' : `${user.employee_code || ''} · ${user.job_role || 'Nhân viên'}`;
  $('#top-role').textContent = user.role === 'admin' ? 'Admin' : 'Nhân viên';
  $('#role-chip').textContent = user.role === 'admin' ? 'QUYỀN: ADMIN' : 'QUYỀN: NHÂN VIÊN';
  $('#role-chip').className = `role-chip ${user.role === 'admin' ? 'admin' : 'employee'}`;
  $('#sidebar-avatar').textContent = initials(name);
  $('#top-avatar').textContent = initials(name);
  updateClock(); buildNav(); navigate('dashboard');
}

function applyUnreadCount(value, rebuild = true) {
  state.cache.unread = Number(value || 0);
  state.lastUnreadRefresh = Date.now();
  const count = $('#notification-count');
  if (count) {
    count.textContent = state.cache.unread;
    count.classList.toggle('hidden', !state.cache.unread);
  }
  if (rebuild && state.user) buildNav();
}
function takeDashboardData() {
  const data = state.prefetchedDashboard;
  state.prefetchedDashboard = null;
  return data;
}

const titles = { dashboard:'Tổng quan', employees:'Quản lý nhân viên', schedule:'Xếp lịch làm', shifts:'Lịch làm của tôi', availability:'Đăng ký lịch rảnh', requests:'Yêu cầu & phê duyệt', attendance:'Chấm công & bảng công', payroll:'Bảng lương', inventory:'Kho nguyên liệu', purchases:'Danh sách cần mua', locations:'Vị trí & quy định', reports:'Báo cáo', notifications:'Thông báo' };
async function navigate(page) {
  state.page = page;
  $('#page-title').textContent = titles[page] || 'RUMI Manager';
  $('#page-eyebrow').textContent = state.user.role === 'admin' ? 'TRUNG TÂM QUẢN TRỊ' : 'KHÔNG GIAN NHÂN VIÊN';
  buildNav(); closeSidebar(); loading();
  try {
    const fn = { dashboard:renderDashboard, employees:renderEmployees, schedule:renderSchedule, shifts:renderMyShifts, availability:renderAvailability, requests:renderRequests, attendance:renderAttendance, payroll:renderPayroll, inventory:renderInventory, purchases:renderPurchases, locations:renderLocations, reports:renderReports, notifications:renderNotifications }[page];
    if (!fn) return navigate('dashboard');
    await fn();
    if (page !== 'notifications' && Date.now() - state.lastUnreadRefresh > 30000) refreshUnread(false);
  } catch (err) { $('#page').innerHTML = `<div class="card">${empty('Không tải được dữ liệu', err.message, 'info')}</div>`; toast(err.message, 'error'); }
}
async function refreshUnread(rebuild = true) {
  if (!state.user) return;
  try {
    const result = await api('/api/notifications/unread-count');
    applyUnreadCount(result.count, rebuild);
  } catch {}
}

async function renderDashboard() {
  const d = takeDashboardData() || await api('/api/dashboard');
  applyUnreadCount(d.unread_count, false);
  if (state.user.role === 'admin') {
    const s = d.stats;
    $('#page').innerHTML = `<section class="hero-card"><div class="hero-copy"><span class="eyebrow">RUMI HÔM NAY</span><h2>Vận hành gọn gàng, phục vụ thật ngon.</h2><p>Kiểm tra nhân sự, lịch làm, yêu cầu đang chờ và nguyên liệu sắp hết trước khi bắt đầu một ngày mới.</p></div><div class="hero-actions"><button class="btn secondary" data-nav="schedule">${icons.calendar} Xếp ca</button><button class="btn secondary" data-nav="requests">${icons.request} Duyệt yêu cầu</button></div></section><section class="stats-grid">${stat('Nhân viên hoạt động',s.employees,'Tài khoản đang sử dụng','users')}${stat('Ca làm hôm nay',s.shifts_today,'Theo lịch đã xếp','calendar','blue')}${stat('Đang trong ca',s.working_now,'Đã chấm công vào','clock','green')}${stat('Lịch rảnh chờ duyệt',s.pending_schedule,'Cần quản lý xử lý','request','amber')}${stat('Nghỉ / thay ca',s.pending_requests,'Yêu cầu đang chờ','request','red')}${stat('Nguyên liệu sắp hết',s.low_stock,'Bằng hoặc dưới định mức','box','red')}${stat('Mặt hàng cần mua',s.pending_purchase,'Chưa đánh dấu đã mua','cart','amber')}${stat('Lương dự kiến tháng',money(s.payroll_total),'Tính từ giờ công hợp lệ','money','green')}</section><section class="grid-2"><div class="card"><div class="card-head"><div><h3>Ca làm hôm nay</h3><p>Tiến độ chấm công theo từng nhân viên</p></div><button class="btn small secondary" data-nav="schedule">Xem lịch</button></div><div class="card-body">${shiftList(d.today_shifts)}</div></div><div class="card"><div class="card-head"><div><h3>Thông báo mới</h3><p>Các thay đổi cần quản lý chú ý</p></div><button class="btn small secondary" data-nav="notifications">Xem tất cả</button></div><div class="card-body">${notificationList(d.notifications)}</div></div></section>`;
  } else {
    const s = d.stats;
    $('#page').innerHTML = `<section class="hero-card"><div class="hero-copy"><span class="eyebrow">CA LÀM CỦA BẠN</span><h2>Chào ${esc(state.user.name)}, sẵn sàng cho một ca thật tốt.</h2><p>Đăng ký lịch rảnh, xem ca được xếp và chấm công bằng GPS ngay tại vị trí cửa hàng.</p></div><div class="hero-actions"><button class="btn secondary" data-nav="attendance">${icons.gps} Chấm công</button><button class="btn secondary" data-nav="availability">${icons.calendar} Đăng ký lịch</button></div></section><section class="stats-grid">${stat('Ca sắp tới',s.upcoming_shifts,'Từ hôm nay trở đi','calendar','blue')}${stat('Giờ làm tháng này',number(s.month_hours,2),'Giờ công đã hoàn thành','clock','green')}${stat('Yêu cầu đang chờ',s.pending_requests,'Lịch rảnh hoặc thay ca','request','amber')}${stat('Lương tạm tính',money(s.estimated_salary),'Chưa tính thay đổi mới nhất','money','green')}</section><section class="grid-2"><div class="card"><div class="card-head"><div><h3>Lịch làm gần nhất</h3><p>Ca đã được quản lý xác nhận</p></div><button class="btn small secondary" data-nav="shifts">Xem tất cả</button></div><div class="card-body">${shiftList(d.upcoming_shifts)}</div></div><div class="card"><div class="card-head"><div><h3>Thông báo của bạn</h3><p>Lịch làm, yêu cầu và lương</p></div><button class="btn small secondary" data-nav="notifications">Xem tất cả</button></div><div class="card-body">${notificationList(d.notifications)}</div></div></section>`;
  }
}
function shiftList(rows) {
  if (!rows?.length) return empty('Chưa có ca làm', 'Lịch làm sẽ xuất hiện sau khi quản lý xếp ca.', 'calendar');
  return `<div class="list">${rows.map(x => `<div class="list-row"><span class="list-icon">${icons.clock}</span><div class="list-copy"><strong>${esc(x.employee_name || x.location_name || 'Ca làm')}</strong><span>${dateVN(x.shift_date)} · ${esc(x.start_time)}–${esc(x.end_time)} · ${esc(x.location_name || 'Chưa có vị trí')}</span></div><div class="list-value">${x.attendance ? badge(x.attendance.status) : badge(x.status)}</div></div>`).join('')}</div>`;
}
function notificationList(rows) {
  if (!rows?.length) return empty('Chưa có thông báo', 'Các cập nhật mới sẽ hiển thị tại đây.', 'bell');
  return `<div class="list">${rows.map(x => `<div class="list-row"><span class="list-icon">${icons.bell}</span><div class="list-copy"><strong>${esc(x.title)}</strong><span>${esc(x.message)}</span></div><div class="list-value">${dateTimeVN(x.created_at)}</div></div>`).join('')}</div>`;
}

async function renderEmployees() {
  if (state.user.role !== 'admin') return navigate('dashboard');
  const rows = await api('/api/employees'); state.cache.employees = rows;
  $('#page').innerHTML = `${intro('NHÂN SỰ RUMI','Quản lý nhân viên','Chỉ admin được tạo tài khoản, thay đổi thông tin và khóa nhân viên.',`<button class="btn" data-action="employee-add">${icons.plus} Thêm nhân viên</button>`)}<div class="toolbar"><div class="toolbar-left"><div class="search-box">${icons.search}<input id="employee-search" placeholder="Tìm theo tên, mã hoặc tài khoản..."></div></div><div class="toolbar-right"><span class="badge brand">${rows.length} hồ sơ</span></div></div><div class="table-wrap"><table><thead><tr><th>Nhân viên</th><th>Liên hệ</th><th>Vị trí</th><th>Lương/giờ</th><th>Tài khoản</th><th>Trạng thái</th><th></th></tr></thead><tbody id="employee-rows">${employeeRows(rows)}</tbody></table></div>`;
}
function employeeRows(rows) { return rows.map(x => `<tr data-search="${esc(`${x.name} ${x.code} ${x.username}`.toLowerCase())}"><td>${person(x.name,x.code)}</td><td><span class="cell-main">${esc(x.phone || '—')}</span><span class="cell-sub">${esc(x.email || '')}</span></td><td>${esc(x.role)}</td><td class="money">${money(x.hourly_wage)}</td><td><span class="cell-main">${esc(x.username || 'Chưa có')}</span><span class="cell-sub">${x.account_active ? 'Được phép đăng nhập' : 'Đã khóa'}</span></td><td>${badge(x.status)}</td><td><div class="actions"><button class="btn small secondary icon-only" data-action="employee-edit" data-id="${x.id}" title="Sửa">${icons.edit}</button><button class="btn small secondary icon-only" data-action="employee-reset" data-id="${x.id}" title="Đặt lại mật khẩu">${icons.key}</button><button class="btn small danger icon-only" data-action="employee-delete" data-id="${x.id}" title="Xóa nhân viên">${icons.trash}</button></div></td></tr>`).join(''); }
function employeeForm(x = null) { return `<form class="form-grid" data-form="${x ? 'employee-edit' : 'employee-create'}" data-id="${x?.id || ''}"><div class="field"><label>Mã nhân viên</label><input name="code" required value="${esc(x?.code || '')}" placeholder="NV001"></div><div class="field"><label>Họ và tên</label><input name="name" required value="${esc(x?.name || '')}"></div><div class="field"><label>Số điện thoại</label><input name="phone" value="${esc(x?.phone || '')}"></div><div class="field"><label>Email</label><input type="email" name="email" value="${esc(x?.email || '')}"></div><div class="field"><label>Vị trí công việc</label><select name="job_role"><option ${x?.role==='Pha chế'?'selected':''}>Pha chế</option><option ${x?.role==='Thu ngân'?'selected':''}>Thu ngân</option><option ${x?.role==='Phục vụ'?'selected':''}>Phục vụ</option><option ${x?.role==='Nhân viên'?'selected':''}>Nhân viên</option></select></div><div class="field"><label>Lương theo giờ</label><input type="number" name="hourly_wage" min="0" value="${esc(x?.hourly_wage || 25000)}"></div><div class="field"><label>Ngày bắt đầu</label><input type="date" name="joined_at" value="${esc(x?.joined_at || today())}"></div>${x ? `<div class="field"><label>Trạng thái</label><select name="status"><option ${x.status==='Đang làm'?'selected':''}>Đang làm</option><option ${x.status==='Tạm nghỉ'?'selected':''}>Tạm nghỉ</option><option ${x.status==='Đã nghỉ việc'?'selected':''}>Đã nghỉ việc</option></select></div><div class="field"><label>Tên đăng nhập</label><input name="username" required value="${esc(x.username || '')}" placeholder="an.nguyen"></div>` : `<div class="field"><label>Tên đăng nhập</label><input name="username" required placeholder="an.nguyen"></div><div class="field span-2"><label>Mật khẩu ban đầu</label><input type="password" name="password" minlength="8" required placeholder="Ít nhất 8 ký tự"><div class="field-hint">Nhân viên nên đổi mật khẩu sau lần đăng nhập đầu tiên.</div></div>`}<div class="form-actions"><button type="button" class="btn secondary" data-action="close-modal">Hủy</button><button class="btn" type="submit">${icons.check} ${x?'Lưu thay đổi':'Tạo nhân viên'}</button></div></form>`; }

async function renderSchedule() {
  if (state.user.role !== 'admin') return navigate('dashboard');
  const pageData = await api(`/api/page/schedule?start=${today()}&end=2099-12-31`);
  const shifts = pageData.shifts, locations = pageData.locations;
  state.cache.shifts = shifts; state.cache.locations = locations;
  if (!state.candidateQuery.location_id && locations[0]) state.candidateQuery.location_id = locations[0].id;
  const q = state.candidateQuery;
  $('#page').innerHTML = `${intro('PHÂN CA THÔNG MINH','Xếp lịch theo thời gian nhân viên rảnh','Tìm nhân viên đã đăng ký rảnh, tránh trùng ca và nghỉ phép trước khi xếp lịch.')}${!locations.length?`<div class="info-banner warning-banner">${icons.info}<div><strong>Chưa có vị trí cửa hàng</strong><span>Hãy thêm vị trí trước khi xếp ca để hệ thống kiểm tra GPS khi chấm công.</span></div></div>`:''}<div class="schedule-grid"><div class="card"><div class="card-head"><div><h3>Tìm người rảnh</h3><p>Chỉ nhân viên “Rảnh” mới được xếp bình thường</p></div></div><div class="card-body"><form class="form-grid" data-form="candidate-search"><div class="field span-2"><label>Ngày làm</label><input type="date" name="date" min="${today()}" value="${esc(q.date)}" required></div><div class="field"><label>Bắt đầu</label><input type="time" name="start" value="${esc(q.start)}" required></div><div class="field"><label>Kết thúc</label><input type="time" name="end" value="${esc(q.end)}" required></div><div class="field span-2"><label>Cửa hàng</label><select name="location_id" required>${locations.map(x=>`<option value="${x.id}" ${String(x.id)===String(q.location_id)?'selected':''}>${esc(x.name)}</option>`).join('')}</select></div><div class="form-actions"><button class="btn" type="submit" ${!locations.length?'disabled':''}>${icons.search} Tìm nhân viên phù hợp</button></div></form><div class="candidate-list section-gap" id="candidate-list">${candidateList(state.candidates)}</div></div></div><div class="card"><div class="card-head"><div><h3>Lịch đã xếp sắp tới</h3><p>${shifts.length} ca từ hôm nay</p></div></div><div class="card-body">${scheduleCards(shifts)}</div></div></div>`;
}
function candidateList(rows) { if (!rows.length) return empty('Chưa tìm nhân viên', 'Chọn ngày và khung giờ để kiểm tra ai đang rảnh.', 'search'); return rows.map(x=>`<div class="candidate ${x.state==='available'?'available':'disabled'}"><span class="avatar">${initials(x.name)}</span><div class="candidate-copy"><strong>${esc(x.name)} · ${esc(x.role)}</strong><span>${esc(x.code)} · ${esc(x.reason)}</span></div>${x.state==='available'?`<button class="btn small success" data-action="schedule-candidate" data-id="${x.employee_id}">${icons.plus} Xếp ca</button>`:badge(x.state==='busy'?'Trùng ca':x.state==='on_leave'?'Nghỉ phép':'Chưa đăng ký')}</div>`).join(''); }
function scheduleCards(rows) { if (!rows.length) return empty('Chưa có ca sắp tới','Hãy tìm người rảnh và xếp ca đầu tiên.','calendar'); return rows.slice(0,40).map(x=>`<article class="shift-card"><div class="shift-card-head"><div><div class="shift-date">${dateVN(x.shift_date)}</div><div class="shift-time">${esc(x.start_time)} – ${esc(x.end_time)}</div></div>${badge(x.attendance?.status || x.status)}</div><div class="shift-meta"><div><span>Nhân viên</span><strong>${esc(x.employee_name || '—')}</strong></div><div><span>Cửa hàng</span><strong>${esc(x.location_name || 'Chưa gắn vị trí')}</strong></div></div><div class="shift-actions"><button class="btn small secondary" data-action="shift-candidates" data-id="${x.id}">${icons.search} Tìm người thay</button><button class="btn small ghost" data-action="shift-delete" data-id="${x.id}">${icons.trash} Xóa</button></div></article>`).join(''); }

async function renderMyShifts() {
  const rows = await api('/api/shifts?start='+today()); state.cache.myShifts = rows;
  $('#page').innerHTML = `${intro('LỊCH CÁ NHÂN','Lịch làm của tôi','Mỗi ca hiển thị cửa hàng, thời gian và trạng thái chấm công.',`<button class="btn" data-nav="attendance">${icons.gps} Chấm công</button>`)}<div class="grid-3">${rows.length?rows.map(x=>`<article class="shift-card"><div class="shift-card-head"><div><div class="shift-date">${dateVN(x.shift_date)}</div><div class="shift-time">${esc(x.start_time)} – ${esc(x.end_time)}</div></div>${badge(x.attendance?.status || x.status)}</div><div class="shift-meta"><div><span>Cửa hàng</span><strong>${esc(x.location_name || 'Chưa có')}</strong></div><div><span>Địa chỉ</span><strong>${esc(x.location_address || '—')}</strong></div></div><div class="shift-actions"><button class="btn small secondary" data-action="request-shift" data-id="${x.id}">${icons.request} Cần người thay</button></div></article>`).join(''):empty('Chưa có lịch làm','Quản lý sẽ xếp ca dựa trên lịch rảnh bạn đăng ký.','calendar')}</div>`;
}

async function renderAvailability() {
  const rows = await api('/api/availability'); state.cache.availability = rows;
  $('#page').innerHTML = `${intro('ĐĂNG KÝ THỜI GIAN','Ngày và giờ tôi có thể làm','Gửi từng khung giờ rảnh để admin duyệt và xếp ca phù hợp.')}<div class="card"><div class="card-head"><div><h3>Đăng ký lịch rảnh mới</h3><p>Không phải ca làm chính thức cho đến khi admin xếp lịch</p></div></div><div class="card-body"><form class="inline-form" data-form="availability-create"><div class="field"><label>Ngày</label><input type="date" name="work_date" min="${today()}" required></div><div class="field"><label>Từ giờ</label><input type="time" name="start_time" required value="08:00"></div><div class="field"><label>Đến giờ</label><input type="time" name="end_time" required value="17:00"></div><div class="field wide"><label>Ghi chú</label><input name="note" placeholder="Ví dụ: Có thể làm ca sáng"></div><button class="btn" type="submit">${icons.plus} Gửi đăng ký</button></form></div></div><div class="section-gap table-wrap"><table><thead><tr><th>Ngày</th><th>Khung giờ</th><th>Ghi chú</th><th>Phản hồi quản lý</th><th>Trạng thái</th><th></th></tr></thead><tbody>${rows.map(x=>`<tr><td class="cell-main">${dateVN(x.work_date)}</td><td>${esc(x.start_time)}–${esc(x.end_time)}</td><td>${esc(x.note || '—')}</td><td>${esc(x.admin_note || '—')}</td><td>${badge(x.status)}</td><td><div class="actions">${x.status==='Chờ duyệt'?`<button class="btn small ghost" data-action="availability-delete" data-id="${x.id}">${icons.trash} Hủy</button>`:''}</div></td></tr>`).join('')||`<tr><td colspan="6">${empty('Chưa đăng ký lịch','Thêm ngày và giờ bạn có thể làm.','calendar')}</td></tr>`}</tbody></table></div>`;
}

async function renderRequests() {
  const pageData = await api('/api/page/requests');
  if (state.user.role === 'admin') return renderAdminRequests(pageData);
  const leaves = pageData.leaves, changes = pageData.changes, shifts = pageData.upcoming_shifts;
  state.cache.myShifts = shifts;
  $('#page').innerHTML = `${intro('YÊU CẦU CÁ NHÂN','Xin nghỉ và tìm người thay ca','Mọi thay đổi chỉ có hiệu lực sau khi quản lý phê duyệt.')}<section class="grid-2"><div class="card"><div class="card-head"><div><h3>Gửi đơn xin nghỉ</h3><p>Dùng cho một hoặc nhiều ngày</p></div></div><div class="card-body"><form class="form-grid" data-form="leave-create"><div class="field"><label>Từ ngày</label><input type="date" name="start_date" min="${today()}" required></div><div class="field"><label>Đến ngày</label><input type="date" name="end_date" min="${today()}" required></div><div class="field span-2"><label>Lý do</label><textarea name="reason" required placeholder="Nhập lý do xin nghỉ"></textarea></div><div class="form-actions"><button class="btn" type="submit">${icons.request} Gửi đơn</button></div></form></div></div><div class="card"><div class="card-head"><div><h3>Yêu cầu người thay ca</h3><p>Quản lý sẽ tìm nhân viên rảnh phù hợp</p></div></div><div class="card-body"><form class="form-grid" data-form="shift-change-create"><div class="field span-2"><label>Ca cần thay</label><select name="shift_id" required><option value="">Chọn ca làm</option>${shifts.map(x=>`<option value="${x.id}">${dateVN(x.shift_date)} · ${x.start_time}–${x.end_time} · ${esc(x.location_name||'')}</option>`).join('')}</select></div><div class="field"><label>Loại yêu cầu</label><select name="request_type"><option>Tìm người thay</option><option>Đổi ca</option><option>Xin nghỉ ca</option></select></div><div class="field"><label>Lý do</label><input name="reason" required></div><div class="form-actions"><button class="btn" type="submit">${icons.request} Gửi yêu cầu</button></div></form></div></div></section><section class="grid-2 section-gap"><div class="card"><div class="card-head"><h3>Đơn xin nghỉ</h3></div><div class="card-body">${leaves.length?`<div class="list">${leaves.map(x=>`<div class="list-row"><span class="list-icon">${icons.calendar}</span><div class="list-copy"><strong>${dateVN(x.start_date)} – ${dateVN(x.end_date)}</strong><span>${esc(x.reason)}${x.admin_note?` · ${esc(x.admin_note)}`:''}</span></div>${badge(x.status)}</div>`).join('')}</div>`:empty('Chưa có đơn nghỉ','Các đơn đã gửi sẽ xuất hiện tại đây.','request')}</div></div><div class="card"><div class="card-head"><h3>Yêu cầu thay ca</h3></div><div class="card-body">${changes.length?`<div class="list">${changes.map(x=>`<div class="list-row"><span class="list-icon">${icons.request}</span><div class="list-copy"><strong>${dateVN(x.shift?.shift_date)} · ${esc(x.shift?.start_time||'')}–${esc(x.shift?.end_time||'')}</strong><span>${esc(x.reason)}${x.replacement_name?` · Thay bởi ${esc(x.replacement_name)}`:''}</span></div>${badge(x.status)}</div>`).join('')}</div>`:empty('Chưa có yêu cầu thay ca','Chọn một ca sắp tới để gửi yêu cầu.','request')}</div></div></section>`;
}
async function renderAdminRequests(pageData = null) {
  const data = pageData || await api('/api/page/requests');
  const availability = data.availability, leaves = data.leaves, changes = data.changes;
  state.cache.availability=availability; state.cache.leaves=leaves; state.cache.changes=changes;
  const tabs = `<div class="tabs"><button class="tab ${state.requestTab==='availability'?'active':''}" data-action="request-tab" data-tab="availability">Lịch rảnh (${availability.filter(x=>x.status==='Chờ duyệt').length})</button><button class="tab ${state.requestTab==='leaves'?'active':''}" data-action="request-tab" data-tab="leaves">Xin nghỉ (${leaves.filter(x=>x.status==='Chờ duyệt').length})</button><button class="tab ${state.requestTab==='changes'?'active':''}" data-action="request-tab" data-tab="changes">Thay ca (${changes.filter(x=>x.status==='Chờ xử lý').length})</button></div>`;
  $('#page').innerHTML = `${intro('PHÊ DUYỆT','Yêu cầu từ nhân viên','Duyệt thời gian rảnh, đơn nghỉ và tìm nhân viên phù hợp để thay ca.')}${tabs}<div id="request-content">${adminRequestContent()}</div>`;
}
function adminRequestContent() {
  if(state.requestTab==='availability') return requestTable(state.cache.availability,'availability');
  if(state.requestTab==='leaves') return requestTable(state.cache.leaves,'leaves');
  return requestTable(state.cache.changes,'changes');
}
function requestTable(rows,type){
  if(!rows.length) return `<div class="card">${empty('Không có yêu cầu','Hiện chưa có dữ liệu cần xử lý.','request')}</div>`;
  if(type==='availability') return `<div class="table-wrap"><table><thead><tr><th>Nhân viên</th><th>Ngày</th><th>Khung giờ</th><th>Ghi chú</th><th>Trạng thái</th><th></th></tr></thead><tbody>${rows.map(x=>`<tr><td>${person(x.employee_name,x.employee_code)}</td><td>${dateVN(x.work_date)}</td><td>${x.start_time}–${x.end_time}</td><td>${esc(x.note||'—')}</td><td>${badge(x.status)}</td><td><div class="actions">${x.status==='Chờ duyệt'?`<button class="btn small success" data-action="availability-review" data-id="${x.id}" data-status="Đã duyệt">Duyệt</button><button class="btn small danger" data-action="availability-review" data-id="${x.id}" data-status="Từ chối">Từ chối</button>`:''}</div></td></tr>`).join('')}</tbody></table></div>`;
  if(type==='leaves') return `<div class="table-wrap"><table><thead><tr><th>Nhân viên</th><th>Thời gian</th><th>Lý do</th><th>Trạng thái</th><th></th></tr></thead><tbody>${rows.map(x=>`<tr><td>${person(x.employee_name,x.employee_code)}</td><td>${dateVN(x.start_date)}–${dateVN(x.end_date)}</td><td>${esc(x.reason)}</td><td>${badge(x.status)}</td><td><div class="actions">${x.status==='Chờ duyệt'?`<button class="btn small success" data-action="leave-review" data-id="${x.id}" data-status="Đã duyệt">Duyệt</button><button class="btn small danger" data-action="leave-review" data-id="${x.id}" data-status="Từ chối">Từ chối</button>`:''}</div></td></tr>`).join('')}</tbody></table></div>`;
  return `<div class="table-wrap"><table><thead><tr><th>Nhân viên</th><th>Ca cần thay</th><th>Loại</th><th>Lý do</th><th>Trạng thái</th><th></th></tr></thead><tbody>${rows.map(x=>`<tr><td>${person(x.employee_name,'')}</td><td>${dateVN(x.shift?.shift_date)} · ${esc(x.shift?.start_time||'')}–${esc(x.shift?.end_time||'')}</td><td>${esc(x.request_type)}</td><td>${esc(x.reason)}</td><td>${badge(x.status)}</td><td><div class="actions">${x.status==='Chờ xử lý'?`<button class="btn small success" data-action="change-approve" data-id="${x.id}">${icons.search} Tìm người thay</button><button class="btn small danger" data-action="change-reject" data-id="${x.id}">Từ chối</button>`:''}</div></td></tr>`).join('')}</tbody></table></div>`;
}

async function renderAttendance() {
  if(state.user.role==='employee') return renderEmployeeAttendance();
  const rows=await api(`/api/attendance?month=${state.month}`); state.cache.attendance=rows;
  $('#page').innerHTML=`${intro('BẢNG CÔNG','Theo dõi chấm công','Admin xem toàn bộ giờ vào, giờ ra, vị trí và có thể điều chỉnh khi có lý do chính đáng.')}<div class="toolbar"><div class="toolbar-left"><input type="month" id="attendance-month" value="${state.month}"></div></div><div class="table-wrap"><table><thead><tr><th>Nhân viên</th><th>Ngày</th><th>Ca</th><th>Giờ vào</th><th>Giờ ra</th><th>Số giờ</th><th>Vị trí GPS</th><th>Trạng thái</th><th></th></tr></thead><tbody>${rows.map(x=>`<tr><td>${person(x.employee_name,x.employee_code)}</td><td>${dateVN(x.work_date)}</td><td>${x.shift?`${x.shift.start_time}–${x.shift.end_time}`:'Ngoài lịch'}</td><td>${esc(x.check_in)}</td><td>${esc(x.check_out||'—')}</td><td>${number(x.hours,2)} giờ</td><td><span class="cell-main">${x.check_in_distance_m!=null?`${number(x.check_in_distance_m,1)} m`:'Thủ công'}</span><span class="cell-sub">${x.check_in_accuracy_m?`Sai số ${number(x.check_in_accuracy_m,0)} m`:''}</span></td><td>${badge(x.status)}</td><td><button class="btn small secondary" data-action="attendance-edit" data-id="${x.shift_id||''}" ${!x.shift_id?'disabled':''}>${icons.edit}</button></td></tr>`).join('')||`<tr><td colspan="9">${empty('Chưa có dữ liệu công','Dữ liệu xuất hiện sau khi nhân viên chấm công.','clock')}</td></tr>`}</tbody></table></div>`;
}
async function renderEmployeeAttendance(){
  const pageData=await api(`/api/page/attendance?month=${state.month}`);
  const todayShifts=pageData.today_shifts, history=pageData.history, settings=pageData.settings;
  state.cache.todayShifts=todayShifts;
  $('#page').innerHTML=`${intro('CHẤM CÔNG GPS','Vào và ra ca đúng cửa hàng','Trình duyệt sẽ xin quyền vị trí. GPS phải nằm trong bán kính cửa hàng và đúng khung giờ.')}<div class="info-banner">${icons.info}<div><strong>Khung giờ mặc định</strong><span>Vào ca: trước ${settings.checkin_before_minutes} phút đến sau ${settings.checkin_after_minutes} phút. Ra ca: trước ${settings.checkout_before_minutes} phút đến sau ${settings.checkout_after_minutes} phút. Sai số GPS tối đa ${settings.max_gps_accuracy_m} m.</span></div></div><div class="grid-3">${todayShifts.length?todayShifts.map(x=>clockCard(x)):empty('Hôm nay không có ca','Bạn chỉ có thể chấm công cho ca đã được admin xếp.','calendar')}</div><div class="section-gap card"><div class="card-head"><div><h3>Lịch sử công tháng ${state.month}</h3><p>${history.length} lượt chấm công</p></div><input class="compact-input" type="month" id="attendance-month" value="${state.month}"></div><div class="card-body">${history.length?`<div class="list">${history.map(x=>`<div class="list-row"><span class="list-icon">${icons.clock}</span><div class="list-copy"><strong>${dateVN(x.work_date)} · ${esc(x.check_in)}–${esc(x.check_out||'Chưa ra')}</strong><span>${number(x.hours,2)} giờ · ${esc(x.shift?.location_name||'')}</span></div>${badge(x.status)}</div>`).join('')}</div>`:empty('Chưa có giờ công','Sau khi chấm công, lịch sử sẽ xuất hiện tại đây.','clock')}</div></div>`;
}
function clockCard(x){const att=x.attendance;const action=!att?'checkin':att.check_out_at?'done':'checkout';return `<article class="clock-card"><span class="eyebrow">${dateVN(x.shift_date)} · ${esc(x.location_name||'CỬA HÀNG')}</span><h3>${esc(x.start_time)} – ${esc(x.end_time)}</h3><p>${esc(x.location_address||'Vị trí do quản lý cấu hình')}</p><div class="shift-meta"><div><span>Trạng thái</span><strong>${att?esc(att.status):'Chưa chấm công'}</strong></div><div><span>Phạm vi</span><strong>${esc(x.location_radius_m||'—')} m</strong></div></div>${action==='done'?`<div class="gps-status">${icons.check} Đã hoàn thành ${number(att.hours,2)} giờ</div>`:`<button class="btn" data-action="clock-shift" data-id="${x.id}" data-clock="${action}">${icons.gps} ${action==='checkin'?'Chấm công vào':'Chấm công ra'}</button><div class="gps-status">${icons.location} Cần bật quyền vị trí chính xác</div>`}</article>`;}

async function renderPayroll(){
  const rows=await api(`/api/payroll?month=${state.month}`); state.cache.payroll=rows;
  const admin=state.user.role==='admin';
  $('#page').innerHTML=`${intro('LƯƠNG THEO GIỜ',admin?'Bảng lương nhân viên':'Phiếu lương của tôi',admin?'Tự động tính từ giờ công, lương giờ, thưởng, phạt và tạm ứng.':'Bạn chỉ xem được dữ liệu lương của chính mình.')}<div class="toolbar"><div class="toolbar-left"><input type="month" id="payroll-month" value="${state.month}"></div><div class="toolbar-right"><span class="badge brand">Tổng ${money(rows.reduce((a,x)=>a+Number(x.total||0),0))}</span></div></div><div class="table-wrap"><table><thead><tr>${admin?'<th>Nhân viên</th>':''}<th>Giờ công</th><th>Lương/giờ</th><th>Thưởng</th><th>Phạt</th><th>Tạm ứng</th><th>Thực nhận</th><th>Thanh toán</th>${admin?'<th></th>':''}</tr></thead><tbody>${rows.map(x=>`<tr>${admin?`<td>${person(x.name,x.code)}</td>`:''}<td>${number(x.hours,2)} giờ</td><td>${money(x.hourly_wage)}</td><td class="money">${money(x.bonus)}</td><td class="money">${money(x.penalty)}</td><td class="money">${money(x.advance_pay)}</td><td class="money">${money(x.total)}</td><td>${badge(x.payment_status)}</td>${admin?`<td><div class="actions"><button class="btn small secondary" data-action="payroll-adjust" data-id="${x.employee_id}">${icons.edit}</button><button class="btn small ${x.payment_status==='Đã thanh toán'?'secondary':'success'}" data-action="payroll-pay" data-id="${x.employee_id}" data-status="${x.payment_status==='Đã thanh toán'?'Chưa thanh toán':'Đã thanh toán'}">${x.payment_status==='Đã thanh toán'?'Hoàn tác':'Đã trả'}</button></div></td>`:''}</tr>`).join('')||`<tr><td colspan="9">${empty('Chưa có bảng lương','Bảng lương được tính từ chấm công đã hoàn thành.','money')}</td></tr>`}</tbody></table></div>`;
}

async function renderInventory(){
  const pageData=await api('/api/page/inventory');const items=pageData.items,withdrawals=pageData.withdrawals,employees=pageData.employees;
  state.cache.inventory=items;state.cache.withdrawals=withdrawals;state.cache.publicEmployees=employees;
  const admin=state.user.role==='admin';
  $('#page').innerHTML=`${intro('KHO NGUYÊN LIỆU',admin?'Quản lý tồn kho':'Ghi nhận nguyên liệu đã lấy','Sau khi ghi nhận lấy hàng, số lượng tồn tự động giảm và tạo đề xuất mua khi xuống thấp.',`${admin?`<button class="btn secondary" data-action="inventory-add">${icons.plus} Thêm nguyên liệu</button>`:''}<button class="btn" data-action="inventory-withdraw">${icons.box} Ghi nhận lấy hàng</button>`)}<div class="grid-2"><div class="card"><div class="card-head"><div><h3>Tồn kho hiện tại</h3><p>${items.filter(x=>Number(x.quantity)<=Number(x.min_stock)).length} mặt hàng dưới định mức</p></div></div><div class="card-body">${items.length?items.map(x=>{const ratio=Math.min(100,Number(x.quantity)/(Math.max(Number(x.min_stock)*2,1))*100);const low=Number(x.quantity)<=Number(x.min_stock);return `<div class="stock-line"><div><strong>${esc(x.name)}</strong><small>${esc(x.category)} · Tối thiểu ${number(x.min_stock,2)} ${esc(x.unit)}</small></div><div class="progress ${low?'danger':''}"><span style="width:${ratio}%"></span></div><div class="stock-qty">${number(x.quantity,2)} ${esc(x.unit)}</div>${admin?`<div class="actions"><button class="btn small secondary icon-only" data-action="inventory-restock" data-id="${x.id}">${icons.plus}</button><button class="btn small ghost icon-only" data-action="inventory-edit" data-id="${x.id}">${icons.edit}</button></div>`:''}</div>`}).join(''):empty('Kho đang trống','Admin hãy thêm nguyên liệu đầu tiên.','box')}</div></div><div class="card"><div class="card-head"><div><h3>Lịch sử lấy hàng</h3><p>Gần nhất</p></div></div><div class="card-body">${withdrawals.length?`<div class="list">${withdrawals.slice(0,20).map(x=>`<div class="list-row"><span class="list-icon">${icons.box}</span><div class="list-copy"><strong>${esc(x.item_name)} · ${number(x.quantity,2)} ${esc(x.unit)}</strong><span>${dateVN(x.taken_at)} · ${esc(x.employee_name||'Quản lý')} · ${esc(x.note||'Không ghi chú')}</span></div></div>`).join('')}</div>`:empty('Chưa có lượt lấy hàng','Mỗi lần lấy nguyên liệu sẽ được lưu lại.','box')}</div></div></div>`;
}

async function renderPurchases(){
  const rows=await api('/api/purchase-requests');state.cache.purchases=rows;const admin=state.user.role==='admin';
  $('#page').innerHTML=`${intro('DANH SÁCH CẦN MUA',admin?'Đề xuất nguyên liệu cần mua':'Đề xuất mua nguyên liệu','Nhân viên gửi đề xuất; chủ cửa hàng xem và đánh dấu sau khi đã mua.',`<button class="btn" data-action="purchase-add">${icons.plus} Thêm đề xuất</button>`)}<div class="table-wrap"><table><thead><tr><th>Mặt hàng</th><th>Số lượng</th><th>Người đề xuất</th><th>Lý do</th><th>Ưu tiên</th><th>Ngày</th><th>Trạng thái</th>${admin?'<th></th>':''}</tr></thead><tbody>${rows.map(x=>`<tr><td class="cell-main">${esc(x.item_name)}</td><td>${number(x.quantity,2)} ${esc(x.unit)}</td><td>${esc(x.requester_name)}</td><td>${esc(x.reason||'—')}</td><td>${badge(x.priority)}</td><td>${dateVN(x.requested_at)}</td><td>${badge(x.status)}</td>${admin?`<td>${x.status==='Chờ mua'?`<button class="btn small success" data-action="purchase-status" data-id="${x.id}" data-status="Đã mua">Đã mua</button>`:`<button class="btn small secondary" data-action="purchase-status" data-id="${x.id}" data-status="Chờ mua">Mở lại</button>`}</td>`:''}</tr>`).join('')||`<tr><td colspan="8">${empty('Chưa có đề xuất','Thêm mặt hàng cửa hàng cần mua.','cart')}</td></tr>`}</tbody></table></div>`;
}

async function renderLocations(){
  if(state.user.role!=='admin')return navigate('dashboard');
  const pageData=await api('/api/page/locations');const locations=pageData.locations,settings=pageData.settings;state.cache.locations=locations;state.cache.settings=settings;
  $('#page').innerHTML=`${intro('CẤU HÌNH CỬA HÀNG','Vị trí GPS và quy định chấm công','Admin thêm tọa độ từng cửa hàng và điều chỉnh khung giờ chấm công.',`<button class="btn" data-action="location-add">${icons.plus} Thêm vị trí</button>`)}<div class="grid-2"><div class="card"><div class="card-head"><div><h3>Vị trí cửa hàng</h3><p>Dùng để tính khoảng cách GPS</p></div></div><div class="card-body">${locations.length?`<div class="list">${locations.map(x=>`<div class="list-row"><span class="list-icon">${icons.location}</span><div class="list-copy"><strong>${esc(x.name)}</strong><span>${esc(x.address||'Chưa có địa chỉ')} · ${number(x.latitude,6)}, ${number(x.longitude,6)} · Bán kính ${x.radius_m} m</span></div>${badge(x.active?'Hoạt động':'Đã tắt')}<button class="btn small secondary icon-only" data-action="location-edit" data-id="${x.id}">${icons.edit}</button></div>`).join('')}</div>`:empty('Chưa có vị trí','Thêm cửa hàng để kích hoạt chấm công GPS.','location')}</div></div><div class="card"><div class="card-head"><div><h3>Quy định chấm công</h3><p>Áp dụng cho tất cả cửa hàng</p></div></div><div class="card-body"><form class="form-grid" data-form="settings-update"><div class="field"><label>Vào trước (phút)</label><input type="number" name="checkin_before_minutes" min="0" value="${settings.checkin_before_minutes??15}"></div><div class="field"><label>Vào trễ tối đa (phút)</label><input type="number" name="checkin_after_minutes" min="0" value="${settings.checkin_after_minutes??5}"></div><div class="field"><label>Ra trước (phút)</label><input type="number" name="checkout_before_minutes" min="0" value="${settings.checkout_before_minutes??5}"></div><div class="field"><label>Ra sau tối đa (phút)</label><input type="number" name="checkout_after_minutes" min="0" value="${settings.checkout_after_minutes??5}"></div><div class="field span-2"><label>Sai số GPS tối đa (m)</label><input type="number" name="max_gps_accuracy_m" min="10" value="${settings.max_gps_accuracy_m??150}"></div><input type="hidden" name="timezone" value="Asia/Ho_Chi_Minh"><div class="form-actions"><button class="btn" type="submit">${icons.check} Lưu quy định</button></div></form></div></div></div>`;
}

async function renderReports(){
  if(state.user.role!=='admin')return navigate('dashboard');const d=await api(`/api/reports?month=${state.month}`);
  const max=Math.max(...d.payroll.map(x=>Number(x.total||0)),1);
  $('#page').innerHTML=`${intro('PHÂN TÍCH VẬN HÀNH','Báo cáo tháng','Tổng hợp giờ công và chi phí lương theo dữ liệu chấm công.',`<input type="month" id="report-month" value="${state.month}">`)}<section class="stats-grid">${stat('Nhân viên',d.employee_count,'Đang hoạt động','users')}${stat('Tổng giờ công',number(d.total_hours,2),'Trong tháng đã chọn','clock','blue')}${stat('Tổng bảng lương',money(d.total_payroll),'Bao gồm điều chỉnh','money','green')}${stat('Đã thanh toán',money(d.paid_payroll),'Theo trạng thái chi trả','check','green')}</section><div class="card"><div class="card-head"><div><h3>Chi phí theo nhân viên</h3><p>So sánh thực nhận trong tháng</p></div></div><div class="card-body"><div class="bar-list">${d.payroll.map(x=>`<div class="bar-row"><label>${esc(x.name)}</label><div class="bar-track"><div class="bar-fill" style="width:${Number(x.total||0)/max*100}%"></div></div><strong>${money(x.total)}</strong></div>`).join('')||empty('Chưa có dữ liệu','Hãy hoàn tất chấm công để có báo cáo.','report')}</div></div></div>`;
}

async function renderNotifications(){
  const rows=await api('/api/notifications');state.cache.notifications=rows;
  $('#page').innerHTML=`${intro('TRUNG TÂM THÔNG BÁO','Cập nhật mới nhất','Lịch làm, kết quả phê duyệt, lương và kho nguyên liệu.',`<button class="btn secondary" data-action="notifications-read-all">${icons.check} Đánh dấu đã đọc</button>`)}<div class="card"><div class="card-body">${rows.length?`<div class="list">${rows.map(x=>`<button class="list-row" style="width:100%;border-left:0;border-right:0;border-top:0;background:${x.read_at?'transparent':'#fff9f1'};text-align:left" data-action="notification-read" data-id="${x.id}"><span class="list-icon">${icons.bell}</span><div class="list-copy"><strong>${esc(x.title)}</strong><span>${esc(x.message)}</span></div><div class="list-value">${dateTimeVN(x.created_at)}${!x.read_at?'<br><span class="badge amber">Mới</span>':''}</div></button>`).join('')}</div>`:empty('Không có thông báo','Mọi cập nhật quan trọng sẽ xuất hiện ở đây.','bell')}</div></div>`;
}

function profileModal(){openModal('Tài khoản của tôi','Đổi mật khẩu hoặc đăng xuất',`<div class="info-banner">${icons.users}<div><strong>${esc(state.user.name)}</strong><span>${esc(state.user.username)} · ${state.user.role==='admin'?'Quản trị viên':esc(state.user.job_role||'Nhân viên')}</span></div></div><form class="form-grid" data-form="change-password"><div class="field span-2"><label>Mật khẩu hiện tại</label><input type="password" name="old_password" required></div><div class="field span-2"><label>Mật khẩu mới</label><input type="password" name="new_password" minlength="8" required></div><div class="form-actions"><button type="button" class="btn danger" data-action="logout">${icons.logout} Đăng xuất</button><button class="btn" type="submit">${icons.key} Đổi mật khẩu</button></div></form>`);}

function fd(form){return Object.fromEntries(new FormData(form).entries());}
async function handleForm(form){
  const type=form.dataset.form;const data=fd(form);const submit=$('button[type="submit"]',form);if(submit)submit.disabled=true;
  try{
    if(type==='login'){const result=await api('/api/auth/login',{method:'POST',body:data});const user=result.user||result;enterApp(user,result.dashboard||null,result.unread_count);toast('Đăng nhập thành công');return;}
    if(type==='change-password'){await api('/api/auth/change-password',{method:'POST',body:data});closeModal();toast('Đã đổi mật khẩu');return;}
    if(type==='employee-create'){await api('/api/employees',{method:'POST',body:data});closeModal();toast('Đã tạo nhân viên và tài khoản');return navigate('employees');}
    if(type==='employee-edit'){await api(`/api/employees/${form.dataset.id}`,{method:'PUT',body:data});closeModal();toast('Đã cập nhật nhân viên');return navigate('employees');}
    if(type==='candidate-search'){state.candidateQuery={...data};state.candidates=await api(`/api/scheduling/candidates?date=${encodeURIComponent(data.date)}&start=${encodeURIComponent(data.start)}&end=${encodeURIComponent(data.end)}&role=${encodeURIComponent(data.required_role||'')}`);toast(`Tìm thấy ${state.candidates.filter(x=>x.state==='available').length} nhân viên rảnh`);return renderSchedule();}
    if(type==='shift-create'){await api('/api/shifts',{method:'POST',body:{...data,force:data.force==='on'}});closeModal();state.candidates=[];toast('Đã xếp ca và gửi thông báo');return navigate('schedule');}
    if(type==='availability-create'){await api('/api/availability',{method:'POST',body:data});toast('Đã gửi lịch rảnh');form.reset();return navigate('availability');}
    if(type==='leave-create'){await api('/api/leaves',{method:'POST',body:data});toast('Đã gửi đơn xin nghỉ');return navigate('requests');}
    if(type==='shift-change-create'){await api('/api/shift-change-requests',{method:'POST',body:data});toast('Đã gửi yêu cầu thay ca');return navigate('requests');}
    if(type==='attendance-manual'){await api('/api/attendance/manual',{method:'POST',body:data});closeModal();toast('Đã điều chỉnh chấm công');return navigate('attendance');}
    if(type==='payroll-adjust'){await api('/api/payroll/adjustment',{method:'POST',body:{...data,month:state.month}});closeModal();toast('Đã cập nhật bảng lương');return navigate('payroll');}
    if(type==='inventory-add'){await api('/api/inventory',{method:'POST',body:data});closeModal();toast('Đã thêm nguyên liệu');return navigate('inventory');}
    if(type==='inventory-edit'){await api(`/api/inventory/${form.dataset.id}`,{method:'PUT',body:data});closeModal();toast('Đã cập nhật nguyên liệu');return navigate('inventory');}
    if(type==='inventory-restock'){await api('/api/inventory/restock',{method:'POST',body:data});closeModal();toast('Đã nhập thêm hàng');return navigate('inventory');}
    if(type==='inventory-withdraw'){await api('/api/inventory/withdraw',{method:'POST',body:data});closeModal();toast('Đã trừ tồn kho');return navigate('inventory');}
    if(type==='purchase-add'){await api('/api/purchase-requests',{method:'POST',body:data});closeModal();toast('Đã gửi đề xuất mua hàng');return navigate('purchases');}
    if(type==='location-create'){await api('/api/locations',{method:'POST',body:data});closeModal();toast('Đã thêm vị trí cửa hàng');return navigate('locations');}
    if(type==='location-edit'){data.active=data.active==='on';await api(`/api/locations/${form.dataset.id}`,{method:'PUT',body:data});closeModal();toast('Đã cập nhật vị trí');return navigate('locations');}
    if(type==='settings-update'){await api('/api/settings',{method:'PUT',body:data});toast('Đã lưu quy định chấm công');return navigate('locations');}
  }catch(e){toast(e.message,'error');}finally{if(submit)submit.disabled=false;}
}

document.addEventListener('submit',e=>{const f=e.target.closest('form[data-form]');if(!f)return;e.preventDefault();handleForm(f);});
document.addEventListener('input',e=>{if(e.target.id==='employee-search'){const q=e.target.value.toLowerCase();$$('#employee-rows tr').forEach(r=>r.classList.toggle('hidden',!r.dataset.search.includes(q)));}});
document.addEventListener('change',e=>{if(e.target.id==='attendance-month'||e.target.id==='payroll-month'||e.target.id==='report-month'){state.month=e.target.value;navigate(state.page);}});
document.addEventListener('click',async e=>{
  const nav=e.target.closest('[data-nav]');if(nav){navigate(nav.dataset.nav);return;}
  const b=e.target.closest('[data-action]');if(!b)return;const a=b.dataset.action;const id=Number(b.dataset.id||0);
  try{
    if(a==='close-modal'){closeModal();return;}if(a==='profile'){profileModal();return;}if(a==='logout'){await api('/api/auth/logout',{method:'POST',body:{}});closeModal();showLogin();toast('Đã đăng xuất');return;}
    if(a==='employee-add'){openModal('Thêm nhân viên','Tạo hồ sơ và tài khoản đăng nhập',employeeForm());return;}
    if(a==='employee-edit'){const x=state.cache.employees.find(v=>Number(v.id)===id);openModal('Sửa nhân viên','Trạng thái nghỉ việc sẽ khóa đăng nhập',employeeForm(x));return;}
    if(a==='employee-delete'){const x=state.cache.employees.find(v=>Number(v.id)===id);if(!confirm(`Xóa vĩnh viễn nhân viên ${x?.name || ''}? Tài khoản đăng nhập, ca làm và dữ liệu liên quan cũng sẽ bị xóa.`))return;await api(`/api/employees/${id}`,{method:'DELETE'});toast('Đã xóa nhân viên và tài khoản');return navigate('employees');}
    if(a==='employee-reset'){openModal('Đặt lại mật khẩu','Mật khẩu mới có ít nhất 8 ký tự',`<form class="form-grid" data-form="noop"><div class="field span-2"><label>Mật khẩu mới</label><input id="reset-password" type="password" minlength="8" required></div><div class="form-actions"><button type="button" class="btn secondary" data-action="close-modal">Hủy</button><button type="button" class="btn" data-action="employee-reset-confirm" data-id="${id}">${icons.key} Đặt lại</button></div></form>`);return;}
    if(a==='employee-reset-confirm'){const password=$('#reset-password').value;await api(`/api/employees/${id}/reset-password`,{method:'POST',body:{password}});closeModal();toast('Đã đặt lại mật khẩu');return;}
    if(a==='schedule-candidate'){const emp=state.candidates.find(x=>Number(x.employee_id)===id);const q=state.candidateQuery;const loc=state.cache.locations.find(x=>String(x.id)===String(q.location_id));openModal('Xếp ca làm',`${emp.name} · ${dateVN(q.date)} · ${q.start}–${q.end}`,`<form class="form-grid" data-form="shift-create"><input type="hidden" name="employee_id" value="${id}"><input type="hidden" name="location_id" value="${esc(q.location_id)}"><input type="hidden" name="shift_date" value="${esc(q.date)}"><input type="hidden" name="start_time" value="${esc(q.start)}"><input type="hidden" name="end_time" value="${esc(q.end)}"><div class="field span-2"><label>Cửa hàng</label><input readonly value="${esc(loc?.name||'')}"></div><div class="field span-2"><label>Ghi chú</label><textarea name="note" placeholder="Công việc hoặc lưu ý trong ca"></textarea></div><div class="form-actions"><button type="button" class="btn secondary" data-action="close-modal">Hủy</button><button class="btn" type="submit">${icons.check} Xác nhận xếp ca</button></div></form>`);return;}
    if(a==='shift-delete'){if(!confirm('Xóa ca làm này?'))return;await api(`/api/shifts/${id}`,{method:'DELETE'});toast('Đã xóa ca làm');return navigate('schedule');}
    if(a==='shift-candidates'){const shift=state.cache.shifts.find(x=>Number(x.id)===id);const rows=await api(`/api/scheduling/candidates?date=${shift.shift_date}&start=${shift.start_time}&end=${shift.end_time}&exclude_employee_id=${shift.employee_id}&ignore_shift_id=${shift.id}`);openModal('Nhân viên có thể thay ca',`${dateVN(shift.shift_date)} · ${shift.start_time}–${shift.end_time}`,`<div class="candidate-list">${rows.map(x=>`<div class="candidate ${x.state==='available'?'available':'disabled'}"><span class="avatar">${initials(x.name)}</span><div class="candidate-copy"><strong>${esc(x.name)}</strong><span>${esc(x.reason)}</span></div>${badge(x.state==='available'?'Có thể thay':x.state)}</div>`).join('')}</div>`,true);return;}
    if(a==='request-shift'){const x=(state.cache.myShifts||[]).find(v=>Number(v.id)===id);openModal('Yêu cầu người thay ca',`${dateVN(x.shift_date)} · ${x.start_time}–${x.end_time}`,`<form class="form-grid" data-form="shift-change-create"><input type="hidden" name="shift_id" value="${id}"><div class="field"><label>Loại yêu cầu</label><select name="request_type"><option>Tìm người thay</option><option>Đổi ca</option><option>Xin nghỉ ca</option></select></div><div class="field"><label>Lý do</label><input name="reason" required></div><div class="form-actions"><button type="button" class="btn secondary" data-action="close-modal">Hủy</button><button class="btn" type="submit">Gửi yêu cầu</button></div></form>`);return;}
    if(a==='availability-delete'){await api(`/api/availability/${id}`,{method:'DELETE'});toast('Đã hủy đăng ký');return navigate('availability');}
    if(a==='request-tab'){state.requestTab=b.dataset.tab;$('#request-content').innerHTML=adminRequestContent();$$('.tab').forEach(x=>x.classList.toggle('active',x.dataset.tab===state.requestTab));return;}
    if(a==='availability-review'){await api('/api/availability/status',{method:'POST',body:{id,status:b.dataset.status}});toast('Đã xử lý đăng ký lịch');return navigate('requests');}
    if(a==='leave-review'){await api('/api/leaves/status',{method:'POST',body:{id,status:b.dataset.status}});toast('Đã xử lý đơn nghỉ');return navigate('requests');}
    if(a==='change-reject'){const note=prompt('Lý do từ chối (không bắt buộc):')||'';await api('/api/shift-change-requests/status',{method:'POST',body:{id,status:'Từ chối',admin_note:note}});toast('Đã từ chối yêu cầu');return navigate('requests');}
    if(a==='change-approve'){const req=state.cache.changes.find(x=>Number(x.id)===id);const sh=req.shift;const rows=await api(`/api/scheduling/candidates?date=${sh.shift_date}&start=${sh.start_time}&end=${sh.end_time}&exclude_employee_id=${sh.employee_id}&ignore_shift_id=${sh.id}`);openModal('Chọn nhân viên thay ca',`${dateVN(sh.shift_date)} · ${sh.start_time}–${sh.end_time}`,`<div class="candidate-list">${rows.map(x=>`<div class="candidate ${x.state==='available'?'available':'disabled'}"><span class="avatar">${initials(x.name)}</span><div class="candidate-copy"><strong>${esc(x.name)}</strong><span>${esc(x.reason)}</span></div>${x.state==='available'?`<button class="btn small success" data-action="replacement-confirm" data-id="${id}" data-employee="${x.employee_id}">Chọn</button>`:badge(x.state)}</div>`).join('')}</div>`,true);return;}
    if(a==='replacement-confirm'){await api('/api/shift-change-requests/status',{method:'POST',body:{id,status:'Đã duyệt',replacement_employee_id:Number(b.dataset.employee)}});closeModal();toast('Đã xếp nhân viên thay ca');return navigate('requests');}
    if(a==='clock-shift'){await clockShift(id,b.dataset.clock,b);return;}
    if(a==='attendance-edit'){const row=(state.cache.attendance||[]).find(x=>Number(x.shift_id)===id);openModal('Điều chỉnh chấm công','Thao tác được lưu trong nhật ký',`<form class="form-grid" data-form="attendance-manual"><input type="hidden" name="shift_id" value="${id}"><div class="field"><label>Giờ vào</label><input type="time" name="check_in" value="${esc(row?.check_in||'')}" required></div><div class="field"><label>Giờ ra</label><input type="time" name="check_out" value="${esc(row?.check_out||'')}"></div><div class="field span-2"><label>Lý do điều chỉnh</label><input name="note" required value="Điều chỉnh bởi quản lý"></div><div class="form-actions"><button type="button" class="btn secondary" data-action="close-modal">Hủy</button><button class="btn" type="submit">Lưu</button></div></form>`);return;}
    if(a==='payroll-adjust'){const x=state.cache.payroll.find(v=>Number(v.employee_id)===id);openModal('Điều chỉnh bảng lương',`${x.name} · tháng ${state.month}`,`<form class="form-grid" data-form="payroll-adjust"><input type="hidden" name="employee_id" value="${id}"><div class="field"><label>Thưởng</label><input type="number" name="bonus" min="0" value="${x.bonus}"></div><div class="field"><label>Phạt</label><input type="number" name="penalty" min="0" value="${x.penalty}"></div><div class="field"><label>Tạm ứng</label><input type="number" name="advance_pay" min="0" value="${x.advance_pay}"></div><div class="field"><label>Ghi chú</label><input name="note" value="${esc(x.note||'')}"></div><div class="form-actions"><button type="button" class="btn secondary" data-action="close-modal">Hủy</button><button class="btn" type="submit">Lưu</button></div></form>`);return;}
    if(a==='payroll-pay'){await api('/api/payroll/payment',{method:'POST',body:{employee_id:id,month:state.month,status:b.dataset.status}});toast('Đã cập nhật thanh toán');return navigate('payroll');}
    if(a==='inventory-add'){openModal('Thêm nguyên liệu','Thiết lập số lượng và mức cảnh báo',inventoryForm());return;}
    if(a==='inventory-edit'){const x=state.cache.inventory.find(v=>Number(v.id)===id);openModal('Sửa nguyên liệu','Cập nhật thông tin tồn kho',inventoryForm(x));return;}
    if(a==='inventory-restock'){openModal('Nhập thêm hàng','Số lượng sẽ cộng vào tồn kho',`<form class="form-grid" data-form="inventory-restock"><input type="hidden" name="inventory_id" value="${id}"><div class="field span-2"><label>Số lượng nhập thêm</label><input type="number" step="0.001" min="0.001" name="quantity" required></div><div class="form-actions"><button type="button" class="btn secondary" data-action="close-modal">Hủy</button><button class="btn" type="submit">Nhập kho</button></div></form>`);return;}
    if(a==='inventory-withdraw'){openModal('Ghi nhận lấy nguyên liệu','Hệ thống tự trừ hàng tồn',withdrawForm());return;}
    if(a==='purchase-add'){openModal('Đề xuất cần mua','Chủ cửa hàng sẽ nhìn thấy ngay',purchaseForm());return;}
    if(a==='purchase-status'){await api('/api/purchase-requests/status',{method:'POST',body:{id,status:b.dataset.status}});toast('Đã cập nhật trạng thái');return navigate('purchases');}
    if(a==='location-add'){openModal('Thêm vị trí cửa hàng','Có thể lấy tọa độ hiện tại trên thiết bị admin',locationForm());return;}
    if(a==='location-edit'){const x=state.cache.locations.find(v=>Number(v.id)===id);openModal('Sửa vị trí cửa hàng','Thay đổi bán kính ảnh hưởng chấm công',locationForm(x));return;}
    if(a==='get-location'){await fillCurrentLocation();return;}
    if(a==='notifications-read-all'){await api('/api/notifications/read',{method:'POST',body:{}});toast('Đã đánh dấu tất cả là đã đọc');return navigate('notifications');}
    if(a==='notification-read'){await api('/api/notifications/read',{method:'POST',body:{id}});return navigate('notifications');}
  }catch(err){toast(err.message,'error');}
});

function inventoryForm(x=null){return `<form class="form-grid" data-form="${x?'inventory-edit':'inventory-add'}" data-id="${x?.id||''}"><div class="field span-2"><label>Tên nguyên liệu</label><input name="name" required value="${esc(x?.name||'')}"></div><div class="field"><label>Nhóm</label><select name="category"><option>Nguyên liệu</option><option>Bao bì</option><option>Topping</option><option>Vật tư</option></select></div><div class="field"><label>Đơn vị</label><input name="unit" value="${esc(x?.unit||'kg')}" required></div><div class="field"><label>Số lượng hiện có</label><input type="number" step="0.001" min="0" name="quantity" value="${esc(x?.quantity||0)}"></div><div class="field"><label>Mức tối thiểu</label><input type="number" step="0.001" min="0" name="min_stock" value="${esc(x?.min_stock||0)}"></div><div class="field span-2"><label>Giá nhập tham khảo</label><input type="number" min="0" name="cost" value="${esc(x?.cost||0)}"></div><div class="form-actions"><button type="button" class="btn secondary" data-action="close-modal">Hủy</button><button class="btn" type="submit">Lưu nguyên liệu</button></div></form>`;}
function withdrawForm(){const admin=state.user.role==='admin';return `<form class="form-grid" data-form="inventory-withdraw"><div class="field span-2"><label>Nguyên liệu</label><select name="inventory_id" required><option value="">Chọn nguyên liệu</option>${state.cache.inventory.map(x=>`<option value="${x.id}">${esc(x.name)} · còn ${number(x.quantity,2)} ${esc(x.unit)}</option>`).join('')}</select></div>${admin?`<div class="field span-2"><label>Nhân viên lấy</label><select name="employee_id"><option value="">Quản lý / Không xác định</option>${state.cache.publicEmployees.map(x=>`<option value="${x.id}">${esc(x.name)}</option>`).join('')}</select></div>`:''}<div class="field"><label>Số lượng lấy</label><input type="number" step="0.001" min="0.001" name="quantity" required></div><div class="field"><label>Ngày lấy</label><input type="date" name="taken_at" value="${today()}" required></div><div class="field span-2"><label>Ghi chú</label><input name="note" placeholder="Dùng cho ca, pha thử..."></div><div class="form-actions"><button type="button" class="btn secondary" data-action="close-modal">Hủy</button><button class="btn" type="submit">Ghi nhận và trừ kho</button></div></form>`;}
function purchaseForm(){return `<form class="form-grid" data-form="purchase-add"><div class="field span-2"><label>Mặt hàng cần mua</label><input name="item_name" required></div><div class="field"><label>Số lượng</label><input type="number" step="0.001" min="0.001" name="quantity" required></div><div class="field"><label>Đơn vị</label><input name="unit" value="kg" required></div><div class="field"><label>Mức ưu tiên</label><select name="priority"><option>Bình thường</option><option>Gấp</option></select></div><div class="field"><label>Ngày đề xuất</label><input type="date" name="requested_at" value="${today()}"></div><div class="field span-2"><label>Lý do</label><textarea name="reason" placeholder="Sắp hết, cần cho món mới..."></textarea></div><div class="form-actions"><button type="button" class="btn secondary" data-action="close-modal">Hủy</button><button class="btn" type="submit">Gửi đề xuất</button></div></form>`;}
function locationForm(x=null){return `<form class="form-grid" data-form="${x?'location-edit':'location-create'}" data-id="${x?.id||''}"><div class="field span-2"><label>Tên cửa hàng</label><input name="name" required value="${esc(x?.name||'RUMI ')}"></div><div class="field span-2"><label>Địa chỉ</label><input name="address" value="${esc(x?.address||'')}"></div><div class="field"><label>Vĩ độ</label><input id="location-lat" type="number" step="0.0000001" name="latitude" required value="${esc(x?.latitude||'')}"></div><div class="field"><label>Kinh độ</label><input id="location-lng" type="number" step="0.0000001" name="longitude" required value="${esc(x?.longitude||'')}"></div><div class="field"><label>Bán kính cho phép (m)</label><input type="number" min="20" max="2000" name="radius_m" value="${esc(x?.radius_m||100)}"></div>${x?`<div class="field"><label>Hoạt động</label><label style="display:flex;align-items:center;gap:8px;text-transform:none"><input style="width:auto;min-height:0" type="checkbox" name="active" ${x.active?'checked':''}> Cho phép xếp ca</label></div>`:'<div></div>'}<div class="field span-2"><button type="button" class="btn secondary" data-action="get-location">${icons.gps} Lấy vị trí hiện tại</button><div class="field-hint">Đứng tại cửa hàng và bật vị trí chính xác trước khi bấm.</div></div><div class="form-actions"><button type="button" class="btn secondary" data-action="close-modal">Hủy</button><button class="btn" type="submit">Lưu vị trí</button></div></form>`;}
async function fillCurrentLocation(){if(!navigator.geolocation)throw new Error('Trình duyệt không hỗ trợ GPS');navigator.geolocation.getCurrentPosition(p=>{$('#location-lat').value=p.coords.latitude.toFixed(7);$('#location-lng').value=p.coords.longitude.toFixed(7);toast(`Đã lấy vị trí, sai số ${Math.round(p.coords.accuracy)} m`);},e=>toast('Không lấy được vị trí: '+e.message,'error'),{enableHighAccuracy:true,timeout:15000,maximumAge:0});}
async function clockShift(id,action,button){if(!navigator.geolocation){toast('Trình duyệt không hỗ trợ vị trí GPS','error');return;}button.disabled=true;button.innerHTML='<span class="loader" style="width:16px;height:16px;border-width:2px"></span> Đang lấy GPS';navigator.geolocation.getCurrentPosition(async p=>{try{const r=await api('/api/attendance/clock',{method:'POST',body:{shift_id:id,action,latitude:p.coords.latitude,longitude:p.coords.longitude,accuracy:p.coords.accuracy}});toast(`${r.action==='checkin'?'Vào ca':'Ra ca'} lúc ${r.time}, cách cửa hàng ${number(r.distance_m,1)} m`);navigate('attendance');}catch(e){toast(e.message,'error');button.disabled=false;}},e=>{toast('Không lấy được GPS: '+e.message,'error');button.disabled=false;},{enableHighAccuracy:true,timeout:20000,maximumAge:0});}
function openSidebar(){$('#sidebar').classList.add('open');$('#mobile-overlay').classList.add('show');}function closeSidebar(){$('#sidebar').classList.remove('open');$('#mobile-overlay').classList.remove('show');}
$('#menu-button').addEventListener('click',openSidebar);$('#mobile-overlay').addEventListener('click',closeSidebar);

(async function boot(){
  updateClock();
  try {
    const params = new URLSearchParams(location.search);
    if (params.get('logout') === '1') {
      try { await api('/api/auth/logout', {method:'POST', body:{}}); } catch {}
      return showLogin();
    }
    try {
      const result = await api('/api/bootstrap', { cache:false });
      enterApp(result.user, result.dashboard, result.unread_count);
    } catch {
      showLogin();
    }
  } catch(e) {
    $('#app-root').classList.add('hidden');
    $('#auth-root').classList.remove('hidden');
    $('#auth-root').innerHTML=authLayout(`<div class="auth-card"><span class="eyebrow">RUMI v${APP_VERSION} · KHÔNG THỂ KẾT NỐI</span><h2>Chưa thể mở đăng nhập</h2><p>${esc(e.message)}</p><div class="auth-hint">Kiểm tra bạn đang chạy đúng thư mục <strong>RUMI-Manager-Supabase-v4.2</strong>, đã chạy SQL v4 và cấu hình đúng file <strong>.env</strong>.</div></div>`);
  }
})();
