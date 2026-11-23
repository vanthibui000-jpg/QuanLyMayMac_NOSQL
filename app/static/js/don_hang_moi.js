// Form đặt hàng động: thêm/xóa dòng, chọn màu và size bằng chip, tính tổng tạm tính.
// Dữ liệu sản phẩm được đọc từ <script id="du-lieu-sp" type="application/json"> trong template.
(function () {
  var SAN_PHAM = JSON.parse(document.getElementById('du-lieu-sp').textContent);
  var THEO_ID = {};
  SAN_PHAM.forEach(function (s) { THEO_ID[s.id] = s; });

  function dinhDangTien(n) { return Number(n).toLocaleString('vi-VN') + ' ₫'; }

  // Vẽ chip cho màu hoặc size. Bấm chip để chọn, bấm lại chip đang chọn để bỏ chọn.
  function veChip(nhom, cacGiaTri, oAn) {
    nhom.innerHTML = '';
    oAn.value = '';
    if (!cacGiaTri.length) {
      nhom.innerHTML = '<span class="chip-trong">Chọn sản phẩm trước</span>';
      return;
    }
    cacGiaTri.forEach(function (v) {
      var chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'chip';
      chip.textContent = v;
      chip.addEventListener('click', function () {
        var dangChon = chip.classList.contains('chon');
        nhom.querySelectorAll('.chip').forEach(function (c) { c.classList.remove('chon'); });
        if (dangChon) {
          oAn.value = '';
        } else {
          chip.classList.add('chon');
          oAn.value = v;
        }
      });
      nhom.appendChild(chip);
    });
  }

  function capNhatTong() {
    var tong = 0;
    document.querySelectorAll('.dong-hang').forEach(function (d) {
      var sp = THEO_ID[d.querySelector('.chon-sp').value];
      var sl = parseInt(d.querySelector('.so-luong').value, 10) || 0;
      var thanhTien = sp ? sp.gia * sl : 0;
      d.querySelector('.thanh-tien').textContent = dinhDangTien(thanhTien);
      tong += thanhTien;
    });
    document.getElementById('tong-tam').textContent = dinhDangTien(tong);
  }

  function gan(dong) {
    dong.querySelector('.chon-sp').addEventListener('change', function () {
      var sp = THEO_ID[dong.querySelector('.chon-sp').value];
      veChip(dong.querySelector('[data-loai=mau]'), sp ? sp.mau : [], dong.querySelector('input[name=mau]'));
      veChip(dong.querySelector('[data-loai=size]'), sp ? sp.size : [], dong.querySelector('input[name=size]'));
      capNhatTong();
    });
    dong.querySelector('.so-luong').addEventListener('input', capNhatTong);
    dong.querySelector('.nut-xoa').addEventListener('click', function () {
      if (document.querySelectorAll('.dong-hang').length > 1) {
        dong.remove();
      } else {
        dong.querySelector('.chon-sp').value = '';
        dong.querySelector('.so-luong').value = '';
        veChip(dong.querySelector('[data-loai=mau]'), [], dong.querySelector('input[name=mau]'));
        veChip(dong.querySelector('[data-loai=size]'), [], dong.querySelector('input[name=size]'));
      }
      capNhatTong();
    });
  }

  function themDong() {
    var dong = document.getElementById('mau-dong').content.firstElementChild.cloneNode(true);
    document.getElementById('ds-dong').appendChild(dong);
    gan(dong);
    capNhatTong();
  }

  document.getElementById('them-dong').addEventListener('click', themDong);
  for (var i = 0; i < 3; i++) { themDong(); }
})();
