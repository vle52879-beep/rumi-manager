'use strict';

/* RUMI 5.5 — account security and smart attendance. */
(() => {
  const VERSION = '6.4.5';

  icons.shield = '<svg viewBox="0 0 24 24"><path d="M12 3 4.5 6v5.2c0 4.7 3.2 8.9 7.5 10.1 4.3-1.2 7.5-5.4 7.5-10.1V6L12 3Z"/><path d="m8.7 12.1 2.1 2.1 4.6-4.8"/></svg>';
  icons.device = '<svg viewBox="0 0 24 24"><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M9 17h6"/></svg>';
  icons.alert = '<svg viewBox="0 0 24 24"><path d="M12 3 2.5 20h19L12 3Z"/><path d="M12 9v5M12 17h.01"/></svg>';

  if (!navAdmin.some((x) => x[1] === 'security')) navAdmin.push(['Hệ thống', 'security', 'Tài khoản & bảo mật', 'shield']);
  if (!navEmployee.some((x) => x[1] === 'security')) navEmployee.push(['Cá nhân', 'security', 'Tài khoản & bảo mật', 'shield']);
  titles.security = 'Tài khoản & bảo mật';

  const oldEnterApp = enterApp;
  enterApp = function enterAppV55(user, dashboard = null, unreadCount = null) {
    oldEnterApp(user, dashboard, unreadCount);
    document.documentElement.dataset.rumiVersion = VERSION;
    if (user?.must_change_password) {
      setTimeout(() => {
        toast('Bạn cần đổi mật khẩu ban đầu trước khi sử dụng hệ thống', 'error');
        navigate('security');
      }, 0);
    }
  };

  const oldNavigate = navigate;
  navigate = async function navigateV55(page) {
    if (page !== 'security') return oldNavigate(page);
    state.page = 'security';
    $('#page-title').textContent = titles.security;
    $('#page-eyebrow').textContent = 'TRUNG TÂM AN TOÀN TÀI KHOẢN';
    buildNav(); closeSidebar(); loading();
    try { await renderSecurityV55(); }
    catch (error) {
      $('#page').innerHTML = `<div class="card">${empty('Không tải được bảo mật tài khoản', error.message, 'shield')}</div>`;
      toast(error.message, 'error');
    }
  };

  function passwordRules(policy) {
    const min = Number(policy?.minimum_length || (state.user.role === 'admin' ? 12 : 10));
    return `<div class="v55-password-rules"><strong>Mật khẩu chuyên nghiệp</strong><span>Ít nhất ${min} ký tự, có tối thiểu 3 nhóm chữ hoa, chữ thường, số và ký tự đặc biệt.</span><span>Không chứa tên đăng nhập, không dùng mật khẩu phổ biến và không lặp lại 5 mật khẩu gần nhất.</span></div>`;
  }

  async function renderSecurityV55() {
    const data = await api('/api/account/security', { force: true, cache: false });
    state.cache.security = data;
    const profile = data.profile || state.user;
    const active = (data.sessions || []).filter((x) => x.active);
    const forced = Boolean(profile.must_change_password);
    $('#page').innerHTML = `
      ${intro('BẢO MẬT TÀI KHOẢN', 'Tài khoản và thiết bị đăng nhập', 'Quản lý mật khẩu, phiên đăng nhập và theo dõi các thao tác bảo mật.', '')}
      ${forced ? `<div class="v55-security-lock">${icons.alert}<div><strong>Bắt buộc đổi mật khẩu ban đầu</strong><span>Tài khoản chỉ được mở các chức năng khác sau khi đặt mật khẩu riêng.</span></div></div>` : ''}
      <section class="v55-security-grid">
        <article class="card v55-security-card">
          <div class="card-head"><div><h3>${icons.shield} Đổi mật khẩu</h3><p>Đổi mật khẩu sẽ thu hồi các phiên đăng nhập khác.</p></div>${badge(forced ? 'Cần đổi ngay' : 'Đang bảo vệ')}</div>
          <div class="card-body">
            <div class="v55-account-summary">${person(profile.name, `${profile.username} · ${profile.role === 'admin' ? 'Quản trị viên' : 'Nhân viên'}`)}<div><span>Lần đổi gần nhất</span><strong>${profile.password_changed_at ? dateTimeVN(profile.password_changed_at) : 'Chưa ghi nhận'}</strong></div></div>
            ${passwordRules(data.policy)}
            <form class="form-grid v55-password-form" data-form="v55-change-password">
              <div class="field span-2"><label>Mật khẩu hiện tại</label><div class="v55-password-input"><input type="password" name="old_password" autocomplete="current-password" required><button type="button" data-v55-action="toggle-password" aria-label="Hiện mật khẩu">${icons.info}</button></div></div>
              <div class="field span-2"><label>Mật khẩu mới</label><div class="v55-password-input"><input id="v55-new-password" type="password" name="new_password" autocomplete="new-password" minlength="${data.policy.minimum_length}" maxlength="128" required><button type="button" data-v55-action="toggle-password" aria-label="Hiện mật khẩu">${icons.info}</button></div><div class="v55-password-meter"><i id="v55-password-meter"></i><span id="v55-password-label">Chưa nhập mật khẩu</span></div></div>
              <div class="field span-2"><label>Nhập lại mật khẩu mới</label><input type="password" name="confirm_password" autocomplete="new-password" minlength="${data.policy.minimum_length}" maxlength="128" required></div>
              <div class="form-actions"><button class="btn" type="submit">${icons.key} Đổi mật khẩu an toàn</button></div>
            </form>
          </div>
        </article>
        <article class="card v55-security-card">
          <div class="card-head"><div><h3>${icons.device} Thiết bị đăng nhập</h3><p>${active.length} phiên đang hoạt động · tự khóa sau ${data.policy.idle_timeout_minutes} phút không dùng.</p></div><button class="btn small danger" data-v55-action="logout-all">Đăng xuất tất cả</button></div>
          <div class="card-body"><div class="v55-session-list">${(data.sessions || []).map((x) => `
            <div class="v55-session ${x.current ? 'current' : ''} ${x.active ? '' : 'revoked'}">
              <span class="v55-session-icon">${icons.device}</span>
              <div><strong>${esc(x.device_label || 'Thiết bị')}</strong><span>${x.current ? 'Thiết bị hiện tại · ' : ''}Hoạt động ${dateTimeVN(x.last_seen_at || x.created_at)}</span><small>${x.revoked_at ? `Đã thu hồi: ${esc(x.revoke_reason || '')}` : `Hết hạn ${dateTimeVN(x.expires_at)}`}</small></div>
              ${x.active ? (x.current ? '<span class="badge green">Hiện tại</span>' : `<button class="btn small secondary" data-v55-action="revoke-session" data-id="${x.id}">Thu hồi</button>`) : '<span class="badge gray">Đã đóng</span>'}
            </div>`).join('') || empty('Chưa có phiên đăng nhập', 'Đăng nhập lại để tạo phiên mới.', 'device')}</div></div>
        </article>
      </section>
      ${profile.role === 'admin' ? adminAccountsPanel(data) : ''}
      <article class="card section-gap">
        <div class="card-head"><div><h3>Nhật ký bảo mật gần đây</h3><p>Đăng nhập, đổi mật khẩu, tạo admin và thu hồi thiết bị được lưu lại.</p></div></div>
        <div class="card-body">${(data.events || []).length ? `<div class="list">${data.events.map((x) => `<div class="list-row"><span class="list-icon">${icons.shield}</span><div class="list-copy"><strong>${securityActionName(x.action)}</strong><span>${dateTimeVN(x.created_at)}</span></div>${badge('Đã ghi nhận')}</div>`).join('')}</div>` : empty('Chưa có sự kiện bảo mật', 'Các thao tác bảo mật sẽ hiển thị ở đây.', 'shield')}</div>
      </article>`;
    updatePasswordMeter();
  }

  function adminAccountsPanel(data) {
    const rows = Array.isArray(data.admin_accounts) ? data.admin_accounts : [];
    return `<article class="card section-gap">
      <div class="card-head"><div><h3>${icons.shield} Quản trị viên hệ thống</h3><p>Tạo thêm tài khoản admin riêng; không dùng chung mật khẩu giữa các quản lý.</p></div><span class="badge brand">${rows.filter((x) => x.active).length} đang hoạt động</span></div>
      <div class="card-body">
        <div class="table-wrap"><table><thead><tr><th>Tài khoản</th><th>Loại</th><th>Lần đăng nhập cuối</th><th>Yêu cầu đổi mật khẩu</th><th>Trạng thái</th></tr></thead><tbody>${rows.map((x) => `<tr>
          <td><span class="cell-main">${esc(x.username || '—')}</span><span class="cell-sub">Tạo ${x.created_at ? dateTimeVN(x.created_at) : '—'}${x.current ? ' · Phiên hiện tại' : ''}</span></td>
          <td>${x.primary ? '<span class="badge brand">Admin chính</span>' : '<span class="badge gray">Admin bổ sung</span>'}</td>
          <td>${x.last_login_at ? dateTimeVN(x.last_login_at) : 'Chưa đăng nhập'}</td>
          <td>${x.must_change_password ? '<span class="badge amber">Bắt buộc</span>' : '<span class="badge green">Đã hoàn tất</span>'}</td>
          <td>${x.active ? '<span class="badge green">Hoạt động</span>' : '<span class="badge gray">Đã khóa</span>'}</td>
        </tr>`).join('') || `<tr><td colspan="5">${empty('Chưa có tài khoản admin', 'Tạo tài khoản quản trị đầu tiên bên dưới.', 'shield')}</td></tr>`}</tbody></table></div>
        <div class="section-gap"><div class="card-head"><div><h3>Tạo admin mới</h3><p>Admin mới có toàn bộ quyền quản trị và phải đổi mật khẩu ở lần đăng nhập đầu tiên.</p></div></div>
          <form class="form-grid" data-form="v643-admin-create">
            <div class="field"><label>Tên đăng nhập</label><input name="username" autocomplete="off" pattern="[a-z0-9._-]{3,40}" minlength="3" maxlength="40" placeholder="Ví dụ: quanly2" required><div class="field-hint">Chữ thường, số, dấu chấm, gạch dưới hoặc gạch ngang.</div></div>
            <div class="field"><label>Mật khẩu tạm thời</label><div class="v55-password-input"><input type="password" name="password" autocomplete="new-password" minlength="12" maxlength="128" required><button type="button" data-v55-action="toggle-password" aria-label="Hiện mật khẩu">${icons.info}</button></div></div>
            <div class="field"><label>Nhập lại mật khẩu</label><input type="password" name="confirm_password" autocomplete="new-password" minlength="12" maxlength="128" required></div>
            <div class="form-actions"><button class="btn" type="submit">${icons.plus} Tạo tài khoản admin</button></div>
          </form>
          ${passwordRules({ minimum_length: 12 })}
        </div>
      </div>
    </article>`;
  }

  function securityActionName(action) {
    return ({login:'Đăng nhập thành công', logout:'Đăng xuất', logout_all:'Đăng xuất mọi thiết bị', change_password:'Đổi mật khẩu', revoke_session:'Thu hồi thiết bị', create_admin:'Tạo tài khoản admin', clock_rejected:'Chấm công bị từ chối'})[action] || String(action || 'Sự kiện bảo mật').replaceAll('_', ' ');
  }

  function passwordScore(value) {
    let score = 0;
    if (value.length >= 10) score++;
    if (value.length >= 14) score++;
    if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score++;
    if (/\d/.test(value)) score++;
    if (/[^A-Za-z0-9]/.test(value)) score++;
    return Math.min(score, 5);
  }

  function updatePasswordMeter() {
    const input = $('#v55-new-password');
    const bar = $('#v55-password-meter');
    const label = $('#v55-password-label');
    if (!input || !bar || !label) return;
    const score = passwordScore(input.value);
    bar.style.width = `${score * 20}%`;
    bar.dataset.score = score;
    label.textContent = ['Chưa nhập mật khẩu','Rất yếu','Yếu','Trung bình','Tốt','Mạnh'][score];
  }

  const oldHandleForm = handleForm;
  handleForm = async function handleFormV55(form) {
    const type = form.dataset.form;
    if (type === 'v643-admin-create') {
      const data = Object.fromEntries(new FormData(form).entries());
      const submit = form.querySelector('button[type="submit"]');
      if (data.password !== data.confirm_password) return toast('Xác nhận mật khẩu admin không khớp', 'error');
      if (submit) submit.disabled = true;
      try {
        await api('/api/admin/accounts', { method:'POST', body:data });
        form.reset();
        toast('Đã tạo admin mới; tài khoản phải đổi mật khẩu ở lần đăng nhập đầu tiên');
        return navigate('security');
      } catch (error) { toast(error.message, 'error'); }
      finally { if (submit) submit.disabled = false; }
      return;
    }
    if (type === 'v55-change-password') {
      const data = Object.fromEntries(new FormData(form).entries());
      const submit = form.querySelector('button[type="submit"]');
      if (submit) submit.disabled = true;
      try {
        await api('/api/auth/change-password', { method:'POST', body:data });
        state.user.must_change_password = false;
        toast('Đã đổi mật khẩu và đóng các phiên đăng nhập khác');
        return navigate('security');
      } catch (error) { toast(error.message, 'error'); }
      finally { if (submit) submit.disabled = false; }
      return;
    }
    if (type === 'v55-correction-create') {
      const data = Object.fromEntries(new FormData(form).entries());
      const submit = form.querySelector('button[type="submit"]');
      if (submit) submit.disabled = true;
      try {
        await api('/api/attendance/corrections', { method:'POST', body:data });
        closeModal(); toast('Đã gửi yêu cầu sửa chấm công'); return navigate('attendance');
      } catch (error) { toast(error.message, 'error'); }
      finally { if (submit) submit.disabled = false; }
      return;
    }
    return oldHandleForm(form);
  };

  function deviceId() {
    const key = 'rumi_attendance_device_v1';
    let value = localStorage.getItem(key);
    if (!value) {
      value = (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`);
      localStorage.setItem(key, value);
    }
    return value;
  }

  function collectBestPosition(button) {
    return new Promise((resolve, reject) => {
      if (!window.isSecureContext) return reject(new Error('Chấm công GPS cần mở bằng HTTPS.'));
      if (!navigator.geolocation) return reject(new Error('Trình duyệt không hỗ trợ vị trí GPS.'));
      const readings = [];
      let watchId = null;
      let finished = false;
      const original = button?.innerHTML;
      const finish = (error) => {
        if (finished) return;
        finished = true;
        if (watchId != null) navigator.geolocation.clearWatch(watchId);
        clearTimeout(timer);
        if (button) button.innerHTML = original;
        if (error) return reject(error);
        readings.sort((a, b) => a.coords.accuracy - b.coords.accuracy);
        resolve(readings[0]);
      };
      const timer = setTimeout(() => finish(readings.length ? null : new Error('Không lấy được GPS trong thời gian cho phép.')), 14000);
      if (button) button.innerHTML = '<span class="loader" style="width:16px;height:16px;border-width:2px"></span> Đang đo GPS 0/3';
      watchId = navigator.geolocation.watchPosition((position) => {
        readings.push(position);
        if (button) button.innerHTML = `<span class="loader" style="width:16px;height:16px;border-width:2px"></span> Đang đo GPS ${Math.min(readings.length,3)}/3 · ±${Math.round(position.coords.accuracy)}m`;
        if (position.coords.accuracy <= 25 || readings.length >= 3) finish();
      }, (error) => finish(new Error(`Không lấy được GPS: ${error.message}`)), {
        enableHighAccuracy:true, maximumAge:0, timeout:12000,
      });
    });
  }

  async function smartClock(button) {
    const shiftId = Number(button.dataset.id || 0);
    const action = button.dataset.clock || 'auto';
    button.disabled = true;
    try {
      const position = await collectBestPosition(button);
      const result = await api('/api/attendance/clock', { method:'POST', body:{
        shift_id:shiftId, action,
        latitude:position.coords.latitude, longitude:position.coords.longitude,
        accuracy:position.coords.accuracy,
        position_timestamp:new Date(position.timestamp).toISOString(),
        device_id:deviceId(),
      }});
      const risk = result.risk_level && result.risk_level !== 'Thấp' ? ` · rủi ro ${result.risk_level}` : '';
      const overtime = result.overtime_status === 'Chờ duyệt' ? ' · tăng ca đang chờ duyệt' : '';
      toast(`${result.action === 'checkin' ? 'Vào ca' : 'Ra ca'} lúc ${result.time} · cách cửa hàng ${number(result.distance_m,1)}m · GPS ±${number(result.accuracy_m,0)}m${risk}${overtime}`);
      await navigate('attendance');
    } catch (error) { toast(error.message, 'error'); }
    finally { button.disabled = false; }
  }

  function correctionForm(data) {
    const history = data.history || [];
    const attendanceByShift = Object.fromEntries(history.map((x) => [String(x.shift_id), x]));
    const shifts = data.correction_shifts || history.map((x) => x.shift).filter(Boolean);
    return `<form class="form-grid" data-form="v55-correction-create">
      <div class="field span-2"><label>Ca cần sửa</label><select name="shift_id" required><option value="">Chọn ca làm</option>${shifts.map((x) => { const a = attendanceByShift[String(x.id)] || {}; return `<option value="${x.id}">${dateVN(x.shift_date)} · ${esc(x.start_time || '')}–${esc(x.end_time || '')} · hiện tại ${esc(a.check_in || '—')}–${esc(a.check_out || '—')}</option>`; }).join('')}</select></div>
      <div class="field"><label>Giờ vào đề nghị</label><input type="time" name="requested_check_in"></div>
      <div class="field"><label>Giờ ra đề nghị</label><input type="time" name="requested_check_out"></div>
      <div class="field span-2"><label>Lý do</label><textarea name="reason" minlength="5" required placeholder="Ví dụ: quên chấm công ra ca, máy hết pin..."></textarea></div>
      <div class="form-actions"><button type="button" class="btn secondary" data-action="close-modal">Hủy</button><button class="btn" type="submit">Gửi quản lý duyệt</button></div>
    </form>`;
  }

  const oldEmployeeFormV55 = employeeForm;
  employeeForm = function employeeFormV55(employee = null) {
    return oldEmployeeFormV55(employee)
      .replaceAll('minlength="8"', 'minlength="10" maxlength="128"')
      .replace('Mật khẩu ban đầu</label>', 'Mật khẩu ban đầu</label><div class="field-hint">Ít nhất 10 ký tự, có tối thiểu 3 nhóm chữ hoa, chữ thường, số hoặc ký tự đặc biệt. Nhân viên phải đổi ở lần đăng nhập đầu.</div>');
  };

  const oldRenderEmployeesV55 = renderEmployees;
  renderEmployees = async function renderEmployeesSecurityV55() {
    await oldRenderEmployeesV55();
    const rows = state.cache.employees || [];
    const tableRows = [...document.querySelectorAll('.table-wrap tbody tr')];
    tableRows.forEach((tr, index) => {
      const item = rows[index];
      if (!item || tr.children.length < 6) return;
      const locked = item.locked_until && new Date(item.locked_until) > new Date();
      tr.children[5].innerHTML = `<span class="cell-main">${esc(item.username || '—')}</span><span class="cell-sub">${locked ? 'Tạm khóa đến ' + dateTimeVN(item.locked_until) : item.must_change_password ? 'Phải đổi mật khẩu' : item.last_login_at ? 'Đăng nhập ' + dateTimeVN(item.last_login_at) : 'Chưa đăng nhập'}</span>${locked ? '<span class="badge red">Đang khóa</span>' : item.must_change_password ? '<span class="badge amber">Mật khẩu tạm</span>' : '<span class="badge green">Bảo mật</span>'}`;
    });
  };

  const oldRenderAttendance = renderAttendance;
  renderAttendance = async function renderAttendanceV55() {
    await oldRenderAttendance();
    const data = await api(`/api/page/attendance?month=${state.month}`);
    if (state.user.role === 'admin') enhanceAdminAttendance(data);
    else enhanceEmployeeAttendance(data);
  };

  function enhanceAdminAttendance(data) {
    const pendingOt = (data.pending_overtime || []).filter((x) => Number(x.overtime_requested_minutes || x.overtime_minutes || 0) > 0 && x.overtime_status === 'Chờ duyệt');
    const corrections = (data.corrections || []).filter((x) => x.status === 'Chờ duyệt');
    const pendingRisk = (data.pending_risk || []).filter((x) => {
      const review = String(x.review_status || '').trim();
      return review === 'Chờ duyệt' || (!review && x.risk_level === 'Cao');
    });
    const page = $('#page');
    const introNode = page.querySelector('.page-intro');
    const panel = document.createElement('section');
    panel.className = 'v55-review-grid section-gap';
    panel.innerHTML = `
      <article class="card"><div class="card-head"><div><h3>Tăng ca chờ duyệt</h3><p>Chỉ phút được duyệt mới cộng vào lương.</p></div><span class="badge amber">${pendingOt.length} yêu cầu</span></div><div class="card-body">${pendingOt.length ? `<div class="list">${pendingOt.map((x) => `<div class="list-row"><span class="list-icon">${icons.clock}</span><div class="list-copy"><strong>${esc(x.employee_name)} · ${dateVN(x.work_date)}</strong><span>Đề nghị ${x.overtime_requested_minutes || x.overtime_minutes} phút · giờ nền ${number((x.base_payable_minutes || 0)/60,2)}</span></div><button class="btn small" data-v55-action="overtime-review" data-id="${x.id}" data-minutes="${x.overtime_requested_minutes || x.overtime_minutes}">Duyệt</button><button class="btn small danger" data-v55-action="overtime-reject" data-id="${x.id}">Từ chối</button></div>`).join('')}</div>` : empty('Không có tăng ca chờ duyệt', 'Tăng ca phát sinh sẽ xuất hiện tại đây.', 'clock')}</div></article>
      <article class="card"><div class="card-head"><div><h3>Yêu cầu sửa chấm công</h3><p>Đối chiếu ca trước khi phê duyệt.</p></div><span class="badge amber">${corrections.length} yêu cầu</span></div><div class="card-body">${corrections.length ? `<div class="list">${corrections.map((x) => `<div class="list-row"><span class="list-icon">${icons.edit}</span><div class="list-copy"><strong>${esc(x.employee_name || 'Nhân viên')}</strong><span>${esc(x.reason)} · đề nghị ${esc(x.requested_check_in || '—')}–${esc(x.requested_check_out || '—')}</span></div><button class="btn small" data-v55-action="correction-review" data-status="Đã duyệt" data-id="${x.id}">Duyệt</button><button class="btn small danger" data-v55-action="correction-review" data-status="Từ chối" data-id="${x.id}">Từ chối</button></div>`).join('')}</div>` : empty('Không có yêu cầu sửa công', 'Đơn nhân viên gửi sẽ xuất hiện tại đây.', 'edit')}</div></article>
      <article class="card"><div class="card-head"><div><h3>Lượt công rủi ro</h3><p>Thiết bị dùng chung hoặc GPS gần ngưỡng cần kiểm tra.</p></div><span class="badge red">${pendingRisk.length} lượt</span></div><div class="card-body">${pendingRisk.length ? `<div class="list">${pendingRisk.map((x) => `<div class="list-row"><span class="list-icon">${icons.alert}</span><div class="list-copy"><strong>${esc(x.employee_name || 'Nhân viên')} · ${dateVN(x.work_date)}</strong><span>${esc(x.risk_level || '')} · ${esc(Array.isArray(x.risk_reasons) ? x.risk_reasons.join(', ') : x.risk_reasons || x.calculation_note || 'Cần xác minh')}</span></div><button class="btn small" data-v55-action="risk-review" data-status="Đã duyệt" data-id="${x.id || ''}" data-shift-id="${x.shift_id || ''}">Xác nhận</button><button class="btn small danger" data-v55-action="risk-review" data-status="Từ chối" data-id="${x.id || ''}" data-shift-id="${x.shift_id || ''}">Loại công</button></div>`).join('')}</div>` : empty('Không có lượt công rủi ro', 'Các lượt nghi ngờ sẽ xuất hiện tại đây.', 'shield')}</div></article>`;
    if (introNode) introNode.insertAdjacentElement('afterend', panel); else page.prepend(panel);

    page.querySelectorAll('#v5-attendance-rows tr').forEach((row, index) => {
      const item = data.history?.[index];
      if (!item) return;
      if (item.risk_level && item.risk_level !== 'Thấp') row.classList.add(item.risk_level === 'Cao' ? 'v55-risk-high' : 'v55-risk-medium');
    });
  }

  function enhanceEmployeeAttendance(data) {
    const page = $('#page');
    const introNode = page.querySelector('.page-intro');
    if (introNode) {
      introNode.querySelector('.page-intro-actions')?.insertAdjacentHTML('beforeend', `<button class="btn secondary" data-v55-action="correction-open">${icons.edit} Yêu cầu sửa công</button>`);
      introNode.insertAdjacentHTML('afterend', `<div class="v55-salary-rule">${icons.info}<div><strong>Cách tính giờ lương</strong><span>Vào sớm không cộng thêm lương. Đi trễ/về sớm trừ theo thời gian thực tế. Phút sau giờ kết thúc được ghi nhận là tăng ca và chỉ cộng sau khi quản lý duyệt.</span></div></div>`);
    }
    if ((data.corrections || []).length) {
      page.insertAdjacentHTML('beforeend', `<article class="card section-gap"><div class="card-head"><div><h3>Yêu cầu sửa công của tôi</h3><p>Theo dõi kết quả xử lý từ quản lý.</p></div></div><div class="card-body"><div class="list">${data.corrections.map((x) => `<div class="list-row"><span class="list-icon">${icons.edit}</span><div class="list-copy"><strong>${esc(x.reason)}</strong><span>Đề nghị ${esc(x.requested_check_in || '—')}–${esc(x.requested_check_out || '—')} · ${dateTimeVN(x.created_at)}</span></div>${badge(x.status)}</div>`).join('')}</div></div></article>`);
    }
  }

  const oldRenderLocations = renderLocations;
  renderLocations = async function renderLocationsV55() {
    if (state.user.role !== 'admin') return navigate('dashboard');
    const data = await api('/api/page/locations', { force:true });
    const locations = data.locations || [], settings = data.settings || {};
    state.cache.locations = locations;
    $('#page').innerHTML = `${intro('CẤU HÌNH CỬA HÀNG','Vị trí GPS và quy định chấm công thông minh','Giờ máy chủ là chuẩn; GPS phải mới, đủ chính xác và nằm trong bán kính cửa hàng.',`<button class="btn" data-action="location-add">${icons.plus} Thêm vị trí</button>`)}
      <div class="v55-location-grid">
        <div class="card"><div class="card-head"><div><h3>Vị trí cửa hàng</h3><p>Dùng để kiểm tra khoảng cách GPS.</p></div></div><div class="card-body">${locations.length ? `<div class="list">${locations.map((x) => `<div class="list-row"><span class="list-icon">${icons.location}</span><div class="list-copy"><strong>${esc(x.name)}</strong><span>${esc(x.address || 'Chưa có địa chỉ')} · ${number(x.latitude,6)}, ${number(x.longitude,6)} · bán kính ${x.radius_m}m</span></div>${badge(x.active ? 'Hoạt động' : 'Đã tắt')}<button class="btn small secondary icon-only" data-action="location-edit" data-id="${x.id}">${icons.edit}</button></div>`).join('')}</div>` : empty('Chưa có vị trí','Thêm cửa hàng để kích hoạt chấm công GPS.','location')}</div></div>
        <div class="card"><div class="card-head"><div><h3>Quy định chấm công</h3><p>Áp dụng cho mọi cửa hàng.</p></div>${badge('Logic v6.2')}</div><div class="card-body"><form class="form-grid" data-form="settings-update">
          <div class="field"><label>Cho vào trước (phút)</label><input type="number" name="checkin_before_minutes" min="0" max="180" value="${settings.checkin_before_minutes ?? 15}"></div>
          <div class="field"><label>Cho vào sau (phút)</label><input type="number" name="checkin_after_minutes" min="0" max="60" value="${settings.checkin_after_minutes ?? 5}"></div>
          <div class="field"><label>Cho ra trước (phút)</label><input type="number" name="checkout_before_minutes" min="0" max="180" value="${settings.checkout_before_minutes ?? 5}"></div>
          <div class="field"><label>Cho ra sau (phút)</label><input type="number" name="checkout_after_minutes" min="0" max="720" value="${settings.checkout_after_minutes ?? 180}"></div>
          <div class="field"><label>Ân hạn đi trễ (phút)</label><input type="number" name="late_grace_minutes" min="0" max="60" value="${settings.late_grace_minutes ?? 5}"></div>
          <div class="field"><label>Ân hạn về sớm (phút)</label><input type="number" name="early_leave_grace_minutes" min="0" max="60" value="${settings.early_leave_grace_minutes ?? 5}"></div>
          <div class="field"><label>Sai số GPS tối đa (m)</label><input type="number" name="max_gps_accuracy_m" min="10" max="500" value="${settings.max_gps_accuracy_m ?? 80}"></div>
          <div class="field"><label>GPS còn mới trong (giây)</label><input type="number" name="location_freshness_seconds" min="15" max="600" value="${settings.location_freshness_seconds ?? 120}"></div>
          <div class="field"><label>Tăng ca tối đa (phút)</label><input type="number" name="max_overtime_minutes" min="0" max="720" value="${settings.max_overtime_minutes ?? 180}"></div>
          <div class="field"><label>Khoảng cách vào/ra tối thiểu</label><input type="number" name="min_clock_gap_minutes" min="0" max="60" value="${settings.min_clock_gap_minutes ?? 1}"></div>
          <div class="field"><label>Cảnh báo đi trễ sau (phút)</label><input type="number" name="attendance_warning_minutes" min="5" max="180" value="${settings.attendance_warning_minutes ?? 15}"></div>
          <div class="field"><label>Nguy cơ vắng sau (phút)</label><input type="number" name="attendance_no_show_minutes" min="5" max="360" value="${settings.attendance_no_show_minutes ?? 30}"></div>
          <div class="field"><label>Tự ghi nhận vắng sau khi hết ca (phút)</label><input type="number" name="attendance_absent_after_end_minutes" min="0" max="240" value="${settings.attendance_absent_after_end_minutes ?? 0}"></div>
          <div class="field"><label>Làm mới cảnh báo (giây)</label><input type="number" name="attendance_alert_refresh_seconds" min="30" max="600" value="${settings.attendance_alert_refresh_seconds ?? 60}"></div>
          <div class="field span-2"><label>Duyệt tăng ca</label><select name="overtime_requires_approval"><option value="true" ${settings.overtime_requires_approval !== false ? 'selected' : ''}>Bắt buộc quản lý duyệt</option><option value="false" ${settings.overtime_requires_approval === false ? 'selected' : ''}>Tự động tính</option></select></div>
          <input type="hidden" name="timezone" value="Asia/Ho_Chi_Minh"><div class="form-actions"><button class="btn" type="submit">${icons.check} Lưu quy định</button></div>
        </form></div></div>
      </div>`;
  };

  document.addEventListener('input', (event) => {
    if (event.target.id === 'v55-new-password') updatePasswordMeter();
  });

  document.addEventListener('click', async (event) => {
    const profile = event.target.closest('[data-action="profile"]');
    if (profile) {
      event.preventDefault(); event.stopImmediatePropagation();
      return navigate('security');
    }
    const clock = event.target.closest('[data-action="clock-shift"]');
    if (clock) {
      event.preventDefault(); event.stopImmediatePropagation();
      return smartClock(clock);
    }
    const reset = event.target.closest('[data-action="employee-reset"]');
    if (reset) {
      event.preventDefault(); event.stopImmediatePropagation();
      const min = 10;
      return openModal('Đặt lại mật khẩu an toàn','Nhân viên bắt buộc đổi mật khẩu sau lần đăng nhập kế tiếp.',`<form class="form-grid" data-form="noop"><div class="field span-2"><label>Mật khẩu tạm thời</label><input id="reset-password" type="password" minlength="${min}" maxlength="128" required><div class="field-hint">Ít nhất ${min} ký tự và có 3 nhóm chữ hoa, chữ thường, số hoặc ký tự đặc biệt.</div></div><div class="form-actions"><button type="button" class="btn secondary" data-action="close-modal">Hủy</button><button type="button" class="btn" data-v55-action="employee-reset-confirm" data-id="${reset.dataset.id}">${icons.key} Đặt lại và khóa phiên cũ</button></div></form>`);
    }

    const button = event.target.closest('[data-v55-action]');
    if (!button) return;
    event.preventDefault();
    const action = button.dataset.v55Action;
    try {
      if (action === 'toggle-password') {
        const input = button.parentElement.querySelector('input');
        input.type = input.type === 'password' ? 'text' : 'password';
        return;
      }
      if (action === 'logout-all') {
        if (!confirm('Đăng xuất tài khoản trên tất cả thiết bị?')) return;
        await api('/api/auth/logout-all',{method:'POST',body:{}}); showLogin(); return toast('Đã đăng xuất tất cả thiết bị');
      }
      if (action === 'revoke-session') {
        await api('/api/auth/session/revoke',{method:'POST',body:{session_id:Number(button.dataset.id)}}); toast('Đã thu hồi thiết bị'); return navigate('security');
      }
      if (action === 'employee-reset-confirm') {
        const password = $('#reset-password')?.value || '';
        await api(`/api/employees/${Number(button.dataset.id)}/reset-password`,{method:'POST',body:{password}}); closeModal(); return toast('Đã đặt lại mật khẩu, thu hồi phiên cũ và yêu cầu nhân viên đổi lại');
      }
      if (action === 'correction-open') {
        const data = await api(`/api/page/attendance?month=${state.month}`);
        return openModal('Yêu cầu sửa chấm công','Quản lý sẽ đối chiếu lịch ca trước khi duyệt.',correctionForm(data),true);
      }
      if (action === 'risk-review') {
        const note = prompt(button.dataset.status === 'Đã duyệt' ? 'Ghi chú xác minh (không bắt buộc):' : 'Lý do loại lượt công:') || '';
        await api('/api/attendance/risk/review',{method:'POST',body:{attendance_id:Number(button.dataset.id || 0),shift_id:Number(button.dataset.shiftId || 0),status:button.dataset.status,note}}); toast('Đã xử lý lượt chấm công rủi ro'); return navigate('attendance');
      }
      if (action === 'correction-review') {
        const note = prompt(button.dataset.status === 'Đã duyệt' ? 'Ghi chú duyệt (không bắt buộc):' : 'Lý do từ chối:') || '';
        await api('/api/attendance/corrections/review',{method:'POST',body:{id:Number(button.dataset.id),status:button.dataset.status,admin_note:note}}); toast('Đã xử lý yêu cầu sửa công'); return navigate('attendance');
      }
      if (action === 'overtime-review') {
        const requested = Number(button.dataset.minutes || 0);
        const value = prompt(`Số phút tăng ca được duyệt (tối đa ${requested}):`, String(requested));
        if (value === null) return;
        await api('/api/attendance/overtime/review',{method:'POST',body:{attendance_id:Number(button.dataset.id),approved_minutes:Number(value),note:'Quản lý duyệt tăng ca'}}); toast('Đã duyệt tăng ca'); return navigate('attendance');
      }
      if (action === 'overtime-reject') {
        if (!confirm('Từ chối toàn bộ thời gian tăng ca này?')) return;
        await api('/api/attendance/overtime/review',{method:'POST',body:{attendance_id:Number(button.dataset.id),approved_minutes:0,note:'Quản lý từ chối tăng ca'}}); toast('Đã từ chối tăng ca'); return navigate('attendance');
      }
    } catch (error) { toast(error.message,'error'); }
  }, true);

  window.RumiV55 = { version: VERSION, collectBestPosition };
})();
