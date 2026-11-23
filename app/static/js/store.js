/* Storefront interactivity: Hero Slider, Countdown, Search, Cart Drawer, Wishlist, Variant Selector */
(function () {
  // 1. Hero Slider
  const slider = document.getElementById("hero-slider");
  if (slider) {
    const slides = Array.from(slider.querySelectorAll(".hero-slide"));
    const dots = Array.from(slider.querySelectorAll(".hero-dot"));
    const counter = document.getElementById("hero-counter");
    let idx = 0;
    let timer = null;

    function show(n) {
      idx = (n + slides.length) % slides.length;
      slides.forEach((s, i) => s.classList.toggle("active", i === idx));
      dots.forEach((d, i) => d.classList.toggle("active", i === idx));
      if (counter) {
        counter.textContent = String(idx + 1).padStart(2, "0") + " / " + String(slides.length).padStart(2, "0");
      }
    }
    function restart() {
      clearInterval(timer);
      timer = setInterval(() => show(idx + 1), 6500);
    }

    const prev = document.getElementById("hero-prev");
    const next = document.getElementById("hero-next");
    if (prev) prev.addEventListener("click", () => { show(idx - 1); restart(); });
    if (next) next.addEventListener("click", () => { show(idx + 1); restart(); });
    dots.forEach((d, i) => d.addEventListener("click", () => { show(i); restart(); }));
    if (slides.length > 1) restart();
  }

  // 2. Flash Sale Countdown Timer
  const cdWrap = document.getElementById("flash-countdown");
  if (cdWrap) {
    let remaining = 2 * 86400 + 14 * 3600 + 38 * 60 + 45;
    const elD = document.getElementById("cd-d");
    const elH = document.getElementById("cd-h");
    const elM = document.getElementById("cd-m");
    const elS = document.getElementById("cd-s");
    function tick() {
      const d = Math.floor(remaining / 86400);
      const h = Math.floor((remaining % 86400) / 3600);
      const m = Math.floor((remaining % 3600) / 60);
      const s = remaining % 60;
      if (elD) elD.textContent = String(d).padStart(2, "0");
      if (elH) elH.textContent = String(h).padStart(2, "0");
      if (elM) elM.textContent = String(m).padStart(2, "0");
      if (elS) elS.textContent = String(s).padStart(2, "0");
      if (remaining > 0) remaining -= 1;
    }
    tick();
    setInterval(tick, 1000);
  }

  // 3. Header Search Drawer Toggle
  const searchBtn = document.getElementById("btn-search-toggle");
  const searchDrawer = document.getElementById("search-drawer");
  if (searchBtn && searchDrawer) {
    searchBtn.addEventListener("click", () => {
      searchDrawer.classList.toggle("open");
      if (searchDrawer.classList.contains("open")) {
        const inp = searchDrawer.querySelector("input");
        if (inp) inp.focus();
      }
    });
  }

  // 4. Slide-out Cart Drawer
  const cartOpen = document.getElementById("btn-cart-open");
  const cartClose = document.getElementById("btn-cart-close");
  const cartDrawer = document.getElementById("cart-drawer");
  const cartBackdrop = document.getElementById("drawer-backdrop");
  function setCart(open) {
    if (!cartDrawer || !cartBackdrop) return;
    cartDrawer.classList.toggle("open", open);
    cartBackdrop.classList.toggle("open", open);
  }
  if (cartOpen) cartOpen.addEventListener("click", () => setCart(true));
  if (cartClose) cartClose.addEventListener("click", () => setCart(false));
  if (cartBackdrop) cartBackdrop.addEventListener("click", () => setCart(false));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") setCart(false);
  });

  // 5. Wishlist (MongoDB for KH, Flask session for Guest via /api/yeu-thich)
  function showStoreToast(msg, loai) {
    let zone = document.querySelector(".store-toasts");
    if (!zone) {
      zone = document.createElement("div");
      zone.className = "store-toasts";
      zone.setAttribute("aria-live", "polite");
      document.body.appendChild(zone);
    }
    const el = document.createElement("div");
    el.className = "store-toast " + (loai || "ok");
    el.innerHTML = '<span></span><button type="button" aria-label="Đóng">&times;</button>';
    el.querySelector("span").textContent = msg;
    el.querySelector("button").addEventListener("click", () => el.remove());
    zone.appendChild(el);
    setTimeout(() => el.remove(), 4000);
  }

  function updateWishButtons(id, saved, count) {
    const badge = document.getElementById("wish-badge");
    if (badge && typeof count === "number") {
      badge.textContent = String(count);
      badge.style.display = count > 0 ? "inline-flex" : "none";
      badge.classList.toggle("sale", count > 0);
    }
    document.querySelectorAll(`[data-wish="${id}"]`).forEach((btn) => {
      btn.classList.toggle("saved", saved);
      const ic = btn.querySelector("i");
      if (ic) ic.className = saved ? "bi bi-heart-fill" : "bi bi-heart";
      if (btn.dataset.wishLabel === "1") {
        const sp = btn.querySelector("span");
        if (sp) sp.textContent = saved ? "Đã yêu thích" : "Yêu thích";
      }
    });
  }

  document.querySelectorAll("[data-wish]").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const id = btn.getAttribute("data-wish");
      if (!id) return;
      try {
        const res = await fetch("/api/yeu-thich", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ma_sp: id }),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          showStoreToast(data.error || "Không thể cập nhật danh sách yêu thích", "loi");
          return;
        }
        updateWishButtons(id, !!data.saved, data.count);
        showStoreToast(data.saved ? "Đã lưu vào danh sách yêu thích" : "Đã bỏ khỏi danh sách yêu thích", "ok");
      } catch {
        showStoreToast("Lỗi kết nối khi cập nhật yêu thích", "loi");
      }
    });
  });

  // 5b. Storefront Customer Account Dropdown
  const accDrop = document.getElementById("store-acc-dropdown");
  const accBtn = document.getElementById("btn-acc-menu");
  if (accDrop && accBtn) {
    accBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = accDrop.classList.toggle("open");
      accBtn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    document.addEventListener("click", (e) => {
      if (!accDrop.contains(e.target)) {
        accDrop.classList.remove("open");
        accBtn.setAttribute("aria-expanded", "false");
      }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        accDrop.classList.remove("open");
        accBtn.setAttribute("aria-expanded", "false");
      }
    });
  }

  // 5c. Storefront Modals (Size Guide & Cancel Order Reason)
  function setModal(id, open) {
    const m = document.getElementById(id);
    if (!m) return;
    m.classList.toggle("open", open);
    m.setAttribute("aria-hidden", open ? "false" : "true");
  }
  const btnCancelModal = document.getElementById("btn-open-cancel-modal");
  if (btnCancelModal) btnCancelModal.addEventListener("click", () => setModal("cancel-modal", true));
  const btnSizeGuide = document.getElementById("btn-open-size-guide");
  if (btnSizeGuide) btnSizeGuide.addEventListener("click", () => setModal("size-guide-modal", true));
  document.querySelectorAll("[data-close-modal]").forEach((btn) => {
    btn.addEventListener("click", () => setModal(btn.dataset.closeModal, false));
  });
  document.querySelectorAll(".store-modal-backdrop").forEach((bd) => {
    bd.addEventListener("click", (e) => {
      if (e.target === bd) setModal(bd.id, false);
    });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      document.querySelectorAll(".store-modal-backdrop.open").forEach((bd) => setModal(bd.id, false));
    }
  });

  // 5d. Checkout Quick Saved-Address Picker
  const addrCards = Array.from(document.querySelectorAll("[data-pick-addr]"));
  if (addrCards.length) {
    const inpName = document.getElementById("ho_ten");
    const inpPhone = document.getElementById("sdt");
    const inpAddr = document.getElementById("dia_chi");
    addrCards.forEach((card) => {
      card.addEventListener("click", () => {
        if (inpName) inpName.value = card.dataset.hoTen || "";
        if (inpPhone) inpPhone.value = card.dataset.sdt || "";
        if (inpAddr) inpAddr.value = card.dataset.diaChi || "";
        addrCards.forEach((c) => c.classList.toggle("active", c === card));
      });
    });
  }

  // 5e. Cart Instant +/- Stepper
  document.querySelectorAll(".cart-qty-form").forEach((form) => {
    const inp = form.querySelector(".cart-qty-input");
    if (!inp) return;
    form.querySelectorAll("[data-cart-step]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const delta = parseInt(btn.dataset.cartStep, 10) || 0;
        const max = parseInt(inp.max, 10) || 99;
        const cur = parseInt(inp.value, 10) || 1;
        const next = Math.max(0, Math.min(max, cur + delta));
        if (next === cur) return;
        inp.value = String(next);
        form.submit();
      });
    });
    inp.addEventListener("change", () => form.submit());
  });

  // 6. Product Detail Variant Selector (Màu × Size -> Real Stock)
  const varDataEl = document.getElementById("bien-the-data");
  if (varDataEl) {
    const variants = JSON.parse(varDataEl.textContent || "[]");
    const mauBtns = Array.from(document.querySelectorAll("[data-pick-mau]"));
    const sizeBtns = Array.from(document.querySelectorAll("[data-pick-size]"));
    const inpMau = document.getElementById("inp-mau");
    const inpSize = document.getElementById("inp-size");
    const inpQty = document.getElementById("inp-qty");
    const stockEl = document.getElementById("stock-status");
    const mauLabel = document.getElementById("mau-selected");
    const sizeLabel = document.getElementById("size-selected");
    const btnAdd = document.getElementById("btn-add-cart");
    const btnBuy = document.getElementById("btn-buy-now");

    let curMau = inpMau ? inpMau.value : "";
    let curSize = inpSize ? inpSize.value : "";

    function stockOf(m, s) {
      const found = variants.find((v) => v.mau === m && v.size === s);
      return found ? Number(found.ton_kho) : 0;
    }

    function renderVariant() {
      mauBtns.forEach((b) => b.classList.toggle("active", b.dataset.pickMau === curMau));
      if (mauLabel) mauLabel.textContent = curMau || "—";

      sizeBtns.forEach((b) => {
        const s = b.dataset.pickSize;
        const st = stockOf(curMau, s);
        b.disabled = st <= 0;
        b.classList.toggle("active", s === curSize && st > 0);
      });

      if (stockOf(curMau, curSize) <= 0) {
        const avail = sizeBtns.find((b) => !b.disabled);
        curSize = avail ? avail.dataset.pickSize : "";
        sizeBtns.forEach((b) => b.classList.toggle("active", b.dataset.pickSize === curSize && !b.disabled));
      }

      if (sizeLabel) sizeLabel.textContent = curSize || "Hết hàng";
      if (inpMau) inpMau.value = curMau;
      if (inpSize) inpSize.value = curSize;

      const st = stockOf(curMau, curSize);
      if (stockEl) {
        if (st > 0) {
          stockEl.textContent = `Còn ${st} sản phẩm sẵn kho (${curMau} · Size ${curSize})`;
          stockEl.className = "stock-line ok";
        } else {
          stockEl.textContent = "Phiên bản này tạm hết hàng";
          stockEl.className = "stock-line out";
        }
      }
      if (inpQty) {
        inpQty.max = Math.max(1, st);
        if (Number(inpQty.value) > st && st > 0) inpQty.value = st;
      }
      if (btnAdd) btnAdd.disabled = st <= 0;
      if (btnBuy) btnBuy.disabled = st <= 0;
    }

    mauBtns.forEach((b) => b.addEventListener("click", () => { curMau = b.dataset.pickMau; renderVariant(); }));
    sizeBtns.forEach((b) => b.addEventListener("click", () => { curSize = b.dataset.pickSize; renderVariant(); }));
    renderVariant();

    // Qty stepper
    const qDec = document.getElementById("qty-dec");
    const qInc = document.getElementById("qty-inc");
    if (qDec && inpQty) qDec.addEventListener("click", () => {
      inpQty.value = Math.max(1, (parseInt(inpQty.value, 10) || 1) - 1);
    });
    if (qInc && inpQty) qInc.addEventListener("click", () => {
      const mx = parseInt(inpQty.max, 10) || 99;
      inpQty.value = Math.min(mx, (parseInt(inpQty.value, 10) || 1) + 1);
    });

    // Gallery thumbnail switch
    const mainImg = document.getElementById("detail-main-img");
    document.querySelectorAll(".detail-thumb").forEach((th) => {
      th.addEventListener("click", () => {
        document.querySelectorAll(".detail-thumb").forEach((x) => x.classList.remove("active"));
        th.classList.add("active");
        if (mainImg) mainImg.src = th.dataset.src;
      });
    });
  }

  // 7. Password visibility toggle & quick-fill demo accounts
  document.querySelectorAll("[data-pw-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const inp = document.getElementById(btn.dataset.pwToggle);
      if (!inp) return;
      const show = inp.type === "password";
      inp.type = show ? "text" : "password";
      const ic = btn.querySelector("i");
      if (ic) ic.className = show ? "bi bi-eye-slash" : "bi bi-eye";
    });
  });

  const demoBtns = Array.from(document.querySelectorAll("[data-demo-user]"));
  if (demoBtns.length) {
    const inpUser = document.getElementById("ten_dang_nhap");
    const inpPass = document.getElementById("mat_khau");
    const submitBtn = document.querySelector('.auth-box button[type="submit"]');
    demoBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        if (inpUser) inpUser.value = btn.dataset.demoUser || "";
        if (inpPass) inpPass.value = btn.dataset.demoPass || "";
        demoBtns.forEach((b) => b.classList.toggle("active", b === btn));
        if (submitBtn) submitBtn.focus();
      });
    });
  }

  // 8. Auto-dismiss toasts
  document.querySelectorAll(".store-toast").forEach((t) => {
    const close = t.querySelector("button");
    if (close) close.addEventListener("click", () => t.remove());
    setTimeout(() => t.remove(), 5000);
  });

  // 9. Back to top
  const btt = document.getElementById("back-top");
  if (btt) {
    window.addEventListener("scroll", () => {
      btt.classList.toggle("show", window.scrollY > 420);
    }, { passive: true });
    btt.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
  }

  // 10. Newsletter demo feedback
  const nlForm = document.getElementById("newsletter-form");
  if (nlForm) {
    nlForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const inp = nlForm.querySelector("input");
      if (inp && inp.value.trim()) {
        inp.value = "";
        inp.placeholder = "Đã đăng ký nhận bản tin!";
      }
    });
  }
})();
