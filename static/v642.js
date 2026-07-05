'use strict';

/* RUMI 6.4.2 — bulk admin controls, 56h/week and registered-applicant reassignment. */
(() => {
  const VERSION = '6.4.2';
  const normalize642 = (value) => String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const parseDate642 = (value) => {
    const [y, m, d] = String(value).slice(0, 10).split('-').map(Number);
    return new Date(y, m - 1, d);
  };
  const addDays642 = (value, amount) => {
    const d = new Date(value); d.setDate(d.getDate() + amount); return d;
  };
  const iso642 = (value) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
  const time642 = (value) => String(value || '').slice(0, 5);

  function selectedIds(selector) {
    return [...document.querySelectorAll(selector)].filter((x) => x.checked).map((x) => Number(x.value)).filter(Boolean);
  }

  function updateNotificationSelection() {
    const checked = selectedIds('[data-v642-notification-check]');
    const button = document.querySelector('[data-v642-action="delete-notifications"]');
    const label = document.querySelector('[data-v642-notification-selected]');
    if (button) button.disabled = !checked.length;
    if (label) label.textContent = checked.length ? `${checked.length} đã chọn` : 'Chưa chọn';
    const visible = [...document.querySelectorAll('[data-v642-notification-row]')].filter((row) => !row.classList.contains('hidden'));
    const selectAll = document.querySelector('[data-v642-notification-all]');
    if (selectAll) {
      const visibleChecks = visible.map((row) => row.querySelector('[data-v642-notification-check]')).filter(Boolean);
      selectAll.checked = !!visibleChecks.length && visibleChecks.every((x) => x.checked);
      selectAll.indeterminate = visibleChecks.some((x) => x.checked) && !selectAll.checked;
    }
  }

  renderNotifications = async function renderNotificationsV642() {
    const rows = await api('/api/notifications', { force: true });
    state.cache.notifications = rows;
    const unread = rows.filter((x) => !x.read_at).length;
    const admin = state.user.role === 'admin';
    pageNode().innerHTML = `
      ${intro('TRUNG TÂM THÔNG BÁO', 'Cập nhật mới nhất', 'Hiển thị toàn bộ thông báo, không còn giới hạn 100 mục.', `<div class="actions"><button class="btn secondary" data-action="notifications-read-all">${icons.check} Đánh dấu tất cả đã đọc</button>${admin ? `<button class="btn danger" data-v642-action="delete-notifications" disabled>${icons.trash} Xóa đã chọn</button>` : ''}</div>`)}
      <section class="v5-summary-strip">
        ${summaryItem('Tổng thông báo', rows.length, 'Không giới hạn 100 mục')}
        ${summaryItem('Chưa đọc', unread, unread ? 'Cần kiểm tra' : 'Đã đọc hết')}
        ${summaryItem('Đã đọc', rows.length - unread, 'Lịch sử')}
        ${summaryItem('Mới nhất', rows[0] ? dateTimeVN(rows[0].created_at) : '—', 'Thời điểm cập nhật')}
      </section>
      ${filterToolbar(`<div class="search-box">${icons.search}<input id="v5-notification-search" placeholder="Tìm nội dung thông báo..."></div><select id="v5-notification-status"><option value="">Tất cả</option><option value="unread">Chưa đọc</option><option value="read">Đã đọc</option></select>${admin ? `<label class="v642-select-all"><input type="checkbox" data-v642-notification-all><span>Chọn tất cả đang hiển thị</span></label><span data-v642-notification-selected class="v5-filter-count">Chưa chọn</span>` : ''}<span id="v5-notification-count" class="v5-filter-count">${rows.length} thông báo</span>`)}
      <div class="card"><div class="card-body"><div id="v5-notification-list" class="list v642-selectable-list">
        ${rows.map((x) => `<div class="list-row v642-selectable-row" data-v642-notification-row data-search="${esc(normalize642(`${x.title} ${x.message}`))}" data-read="${x.read_at ? 'read' : 'unread'}">
          ${admin ? `<label class="v642-check"><input type="checkbox" value="${x.id}" data-v642-notification-check aria-label="Chọn thông báo"></label>` : ''}
          <button type="button" class="v642-row-main" data-v642-action="read-notification" data-id="${x.id}">
            <span class="list-icon">${icons.bell}</span><span class="list-copy"><strong>${esc(x.title)}</strong><span>${esc(x.message)}</span></span>
            <span class="list-value">${dateTimeVN(x.created_at)}${!x.read_at ? '<br><span class="badge amber">Mới</span>' : ''}</span>
          </button>
        </div>`).join('') || empty('Không có thông báo', 'Mọi cập nhật quan trọng sẽ xuất hiện ở đây.', 'bell')}
      </div></div></div>`;
    updateNotificationSelection();
  };

  const previousRenderInventory642 = renderInventory;
  renderInventory = async function renderInventoryV642() {
    await previousRenderInventory642();
    if (state.user.role !== 'admin') return;
    const withdrawals = state.cache.withdrawals || [];
    const card = [...document.querySelectorAll('.card')].find((node) => node.querySelector('h3')?.textContent?.includes('Lịch sử lấy nguyên liệu'));
    if (!card) return;
    card.innerHTML = `<div class="card-head"><div><h3>Lịch sử lấy nguyên liệu</h3><p>${withdrawals.length} lượt đang hiển thị</p></div><div class="actions"><label class="v642-select-all"><input type="checkbox" data-v642-withdrawal-all><span>Chọn tất cả</span></label><button class="btn small danger" data-v642-action="delete-withdrawals" disabled>${icons.trash} Xóa lịch sử đã chọn</button>${exportButton('withdrawals', 'Xuất lịch sử')}</div></div>
      <div class="card-body"><div class="v642-history-note">Xóa lịch sử chỉ ẩn bản ghi khỏi giao diện, <strong>không cộng lại tồn kho</strong>. Thao tác vẫn được lưu trong nhật ký quản trị.</div>
      ${withdrawals.length ? `<div class="list v642-selectable-list">${withdrawals.map((x) => `<div class="list-row v642-selectable-row" data-v642-withdrawal-row><label class="v642-check"><input type="checkbox" value="${x.id}" data-v642-withdrawal-check aria-label="Chọn lịch sử lấy hàng"></label><span class="list-icon">${icons.box}</span><div class="list-copy"><strong>${esc(x.item_name)} · ${number(x.quantity, 2)} ${esc(x.unit)}</strong><span>${dateVN(x.taken_at)} · ${esc(x.employee_name || 'Quản lý')} · ${esc(x.note || 'Không ghi chú')}</span></div></div>`).join('')}</div>` : empty('Chưa có lượt lấy hàng', 'Mỗi lần lấy nguyên liệu sẽ được lưu lại.', 'box')}</div>`;
    updateWithdrawalSelection();
  };

  function updateWithdrawalSelection() {
    const checked = selectedIds('[data-v642-withdrawal-check]');
    const button = document.querySelector('[data-v642-action="delete-withdrawals"]');
    if (button) button.disabled = !checked.length;
    const all = document.querySelector('[data-v642-withdrawal-all]');
    const checks = [...document.querySelectorAll('[data-v642-withdrawal-check]')];
    if (all) {
      all.checked = !!checks.length && checks.every((x) => x.checked);
      all.indeterminate = checks.some((x) => x.checked) && !all.checked;
    }
  }

  const previousRenderSchedule642 = renderSchedule;
  renderSchedule = async function renderScheduleV642() {
    await previousRenderSchedule642();
    if (state.user.role !== 'admin') return;
    const data = state.shiftMarket || {};
    const card = [...document.querySelectorAll('.card')].find((node) => node.querySelector('h3')?.textContent?.includes('Lịch chính thức trong tuần'));
    if (!card) return;
    const start = state.shiftMarketWeekStart;
    const openings = new Map((data.openings || []).map((x) => [Number(x.id), x]));
    const days = Array.from({ length: 7 }, (_, index) => addDays642(parseDate642(start), index));
    const board = `<div class="v64-official-board v642-official-board">${days.map((day) => {
      const date = iso642(day);
      const rows = (data.shifts || []).filter((x) => x.shift_date === date);
      return `<section class="v64-official-day"><header><strong>${day.toLocaleDateString('vi-VN', { weekday: 'short' })}</strong><span>${day.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })}</span></header><div>${rows.length ? rows.map((row) => {
        const opening = openings.get(Number(row.opening_id));
        const candidates = (opening?.applications || []).filter((app) => ['Chờ duyệt', 'Danh sách chờ', 'Từ chối'].includes(app.status) && Number(app.employee_id) !== Number(row.employee_id));
        return `<article class="v642-official-shift"><b>${time642(row.start_time)}–${time642(row.end_time)}</b><span>${esc(row.employee_name || 'Chưa xếp')}</span><small>${esc(row.employee_role || '')} · ${esc(row.location_name || '')}</small>${row.opening_id ? `<button class="btn tiny secondary" data-v642-action="open-reassign" data-id="${row.id}" ${candidates.length ? '' : 'disabled'}>${icons.users || icons.user} ${candidates.length ? `Đổi nhân viên (${candidates.length})` : 'Không có người đăng ký khác'}</button>` : ''}</article>`;
      }).join('') : '<em>Chưa có lịch chính thức</em>'}</div></section>`;
    }).join('')}</div>`;
    const body = card.querySelector('.card-body');
    if (body) body.innerHTML = board;
  };

  function reassignForm(payload) {
    const shift = payload.shift || {};
    const candidates = payload.candidates || [];
    return `<form class="form-grid" data-form="v642-reassign-shift"><input type="hidden" name="shift_id" value="${shift.id}"><div class="field span-2"><div class="v642-current-shift"><small>Ca hiện tại</small><strong>${dateVN(shift.shift_date)} · ${time642(shift.start_time)}–${time642(shift.end_time)}</strong><span>${esc(shift.employee_name || '')} · ${esc(shift.location_name || '')}</span></div></div><div class="field span-2"><label>Chọn nhân viên đã đăng ký đúng ca</label><div class="v642-candidate-list">${candidates.map((x) => `<label class="v642-candidate ${x.allowed ? '' : 'disabled'}"><input type="radio" name="application_id" value="${x.id}" ${x.allowed ? 'required' : 'disabled'}><span>${person(x.employee_name, `${x.employee_code || ''} · ${x.employee_role || ''}`)}<small>${badge(x.status)} · ${number(x.projected_week_hours, 1)} giờ sau khi xếp · ${esc(x.reason || 'Phù hợp')}</small></span></label>`).join('') || '<div class="v5-empty-small">Không còn nhân viên nào đang chờ duyệt hoặc trong danh sách chờ cho ca này.</div>'}</div></div><div class="field span-2"><label>Ghi chú thay đổi</label><textarea name="note" placeholder="Ví dụ: đổi theo đề nghị của quản lý"></textarea></div><div class="form-actions"><button type="button" class="btn secondary" data-action="close-modal">Hủy</button><button class="btn" type="submit" ${candidates.some((x) => x.allowed) ? '' : 'disabled'}>Xác nhận đổi nhân viên</button></div></form>`;
  }

  const previousHandleForm642 = handleForm;
  handleForm = async function handleFormV642(form) {
    if (form.dataset.form !== 'v642-reassign-shift') return previousHandleForm642(form);
    const fd = new FormData(form);
    const applicationId = Number(fd.get('application_id'));
    if (!applicationId) return toast('Hãy chọn một nhân viên đủ điều kiện', 'error');
    const submit = form.querySelector('button[type="submit"]');
    if (submit) submit.disabled = true;
    try {
      await api('/api/shifts/reassign', { method: 'POST', body: { shift_id: Number(fd.get('shift_id')), application_id: applicationId, note: fd.get('note') || '' } });
      closeModal();
      toast('Đã đổi nhân viên và cập nhật kết quả đăng ký');
      return renderSchedule();
    } catch (error) {
      toast(error.message, 'error');
    } finally {
      if (submit) submit.disabled = false;
    }
  };

  document.addEventListener('change', (event) => {
    if (event.target.matches('[data-v642-notification-all]')) {
      const checked = event.target.checked;
      document.querySelectorAll('[data-v642-notification-row]:not(.hidden) [data-v642-notification-check]').forEach((x) => { x.checked = checked; });
      updateNotificationSelection();
    }
    if (event.target.matches('[data-v642-notification-check]')) updateNotificationSelection();
    if (event.target.matches('[data-v642-withdrawal-all]')) {
      document.querySelectorAll('[data-v642-withdrawal-check]').forEach((x) => { x.checked = event.target.checked; });
      updateWithdrawalSelection();
    }
    if (event.target.matches('[data-v642-withdrawal-check]')) updateWithdrawalSelection();
    if (event.target.matches('#v5-notification-status')) window.setTimeout(updateNotificationSelection, 0);
  });

  document.addEventListener('input', (event) => {
    if (event.target.matches('#v5-notification-search')) window.setTimeout(updateNotificationSelection, 0);
  });

  document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-v642-action]');
    if (!button) return;
    const action = button.dataset.v642Action;
    try {
      if (action === 'read-notification') {
        await api('/api/notifications/read', { method: 'POST', body: { id: Number(button.dataset.id) } });
        return renderNotifications();
      }
      if (action === 'delete-notifications') {
        const ids = selectedIds('[data-v642-notification-check]');
        if (!ids.length) return;
        if (!confirm(`Xóa vĩnh viễn ${ids.length} thông báo đã chọn?`)) return;
        const result = await api('/api/notifications/delete', { method: 'POST', body: { ids } });
        toast(`Đã xóa ${result.deleted_count || ids.length} thông báo`);
        return renderNotifications();
      }
      if (action === 'delete-withdrawals') {
        const ids = selectedIds('[data-v642-withdrawal-check]');
        if (!ids.length) return;
        const reason = prompt('Nhập lý do xóa lịch sử (tồn kho sẽ không thay đổi):', 'Dọn lịch sử hiển thị');
        if (reason === null) return;
        const result = await api('/api/withdrawals/archive', { method: 'POST', body: { ids, reason } });
        toast(`Đã xóa ${result.deleted_count || ids.length} mục khỏi lịch sử`);
        return renderInventory();
      }
      if (action === 'open-reassign') {
        const payload = await api(`/api/shifts/reassign-candidates?shift_id=${Number(button.dataset.id)}`, { force: true });
        return openModal('Đổi nhân viên cho ca đã xếp', 'Chỉ hiển thị người đã đăng ký đúng ngày và đúng ca này.', reassignForm(payload), true);
      }
    } catch (error) {
      toast(error.message, 'error');
    }
  });

  window.RumiV642 = { version: VERSION, maxWeeklyHours: 56, bulkNotificationDelete: true, inventoryHistoryArchive: true, registeredApplicantReassignment: true };
})();
