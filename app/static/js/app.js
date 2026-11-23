// Hành vi dùng chung cho mọi trang: sidebar, dropdown, hộp thoại xác nhận, toast.
// Không phụ thuộc thư viện ngoài. Mọi chỗ dùng localStorage đều bọc try/catch
// vì trình duyệt có thể chặn (chế độ riêng tư).
(function () {
  'use strict';

  var goc = document.documentElement;
  var oMenu = document.getElementById('mo-menu');

  /* ---------- Thu gọn sidebar (desktop) ---------- */
  var nutThuGon = document.getElementById('nut-thu-gon');
  function capNhatNutThuGon() {
    if (!nutThuGon) { return; }
    var gon = goc.classList.contains('sidebar-collapsed');
    nutThuGon.setAttribute('aria-pressed', gon ? 'true' : 'false');
    nutThuGon.title = gon ? 'Mở rộng menu' : 'Thu gọn menu';
  }
  if (nutThuGon) {
    capNhatNutThuGon();
    nutThuGon.addEventListener('click', function () {
      goc.classList.toggle('sidebar-collapsed');
      try {
        localStorage.setItem('oms.sidebar', goc.classList.contains('sidebar-collapsed') ? 'collapsed' : 'expanded');
      } catch (e) { /* bỏ qua: chỉ mất ghi nhớ trạng thái */ }
      capNhatNutThuGon();
    });
  }

  /* ---------- Sidebar trên điện thoại: đóng khi bấm link hoặc phím Esc ---------- */
  function dongMenuDienThoai() { if (oMenu) { oMenu.checked = false; } }
  document.querySelectorAll('.sidebar a').forEach(function (a) {
    a.addEventListener('click', dongMenuDienThoai);
  });

  /* ---------- Dropdown (thông báo, tài khoản) ---------- */
  var cacDropdown = Array.prototype.slice.call(document.querySelectorAll('[data-dropdown]'));
  function dongDropdown(ngoaiTru) {
    cacDropdown.forEach(function (dd) {
      if (dd === ngoaiTru) { return; }
      dd.classList.remove('open');
      var nut = dd.querySelector('button[aria-haspopup]');
      if (nut) { nut.setAttribute('aria-expanded', 'false'); }
    });
  }
  cacDropdown.forEach(function (dd) {
    var nut = dd.querySelector('button[aria-haspopup]');
    if (!nut) { return; }
    nut.addEventListener('click', function (e) {
      e.stopPropagation();
      var dangMo = dd.classList.toggle('open');
      nut.setAttribute('aria-expanded', dangMo ? 'true' : 'false');
      dongDropdown(dd);
    });
  });
  document.addEventListener('click', function (e) {
    if (!e.target.closest('[data-dropdown]')) { dongDropdown(null); }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { dongDropdown(null); dongMenuDienThoai(); }
  });

  /* ---------- Hộp thoại xác nhận: form có data-confirm ---------- */
  var hop = document.getElementById('hop-xac-nhan');
  var noiDungHop = document.getElementById('hop-xac-nhan-noi-dung');
  var nutDongY = document.getElementById('hop-xac-nhan-dong-y');
  var nutHuy = document.getElementById('hop-xac-nhan-huy');

  function hoiXacNhan(noiDung, khiDongY) {
    // Trình duyệt quá cũ không có <dialog>: dùng hộp thoại mặc định để thao tác không bị mất.
    if (!hop || typeof hop.showModal !== 'function') {
      if (window.confirm(noiDung)) { khiDongY(); }
      return;
    }
    noiDungHop.textContent = noiDung;
    nutDongY.onclick = function () { hop.close(); khiDongY(); };
    nutHuy.onclick = function () { hop.close(); };
    hop.showModal();
    nutHuy.focus();
  }
  if (hop) {
    // Bấm ra ngoài hộp thoại thì đóng
    hop.addEventListener('click', function (e) { if (e.target === hop) { hop.close(); } });
  }
  document.addEventListener('submit', function (e) {
    var form = e.target;
    var thongBao = form.getAttribute && form.getAttribute('data-confirm');
    if (!thongBao || form.dataset.daXacNhan === '1') { return; }
    e.preventDefault();
    hoiXacNhan(thongBao, function () {
      form.dataset.daXacNhan = '1';
      form.submit(); // submit() không kích hoạt lại sự kiện submit nên không bị lặp
    });
  });

  /* ---------- Toast: tự tắt, bấm × để đóng ---------- */
  function anToast(t) {
    t.classList.add('an-di');
    setTimeout(function () { if (t.parentNode) { t.parentNode.removeChild(t); } }, 220);
  }
  function gaToast(t) {
    var nut = t.querySelector('.toast-close');
    if (nut) { nut.addEventListener('click', function () { anToast(t); }); }
    // Lỗi hiển thị lâu hơn để người dùng kịp đọc
    setTimeout(function () { anToast(t); }, t.classList.contains('loi') ? 8000 : 5000);
  }
  document.querySelectorAll('.toast').forEach(gaToast);

  /* ---------- Menu sáng theo #neo (trang báo cáo) ----------
     Server chỉ xác định được mục theo route, không đọc được phần #neo của URL.
     Mục có data-neo sẽ sáng khi URL có #neo tương ứng; khi đó mục cha (cùng đường dẫn) tắt. */
  var linkNeo = Array.prototype.slice.call(document.querySelectorAll('.sidebar-nav a[data-neo]'));
  if (linkNeo.length) {
    var cacLinkCha = Array.prototype.slice.call(document.querySelectorAll('.sidebar-nav a:not([data-neo])'));
    cacLinkCha.forEach(function (a) { a.dataset.sangTuServer = a.classList.contains('active') ? '1' : '0'; });
    var capNhatTheoNeo = function () {
      var neo = (location.hash || '').replace('#', '');
      var khop = linkNeo.filter(function (a) { return a.dataset.neo === neo && a.pathname === location.pathname; })[0];
      linkNeo.forEach(function (a) { a.classList.toggle('active', a === khop); });
      cacLinkCha.forEach(function (a) {
        if (a.pathname !== location.pathname) { return; }
        a.classList.toggle('active', !khop && a.dataset.sangTuServer === '1');
      });
    };
    window.addEventListener('hashchange', capNhatTheoNeo);
    capNhatTheoNeo();
  }
})();
