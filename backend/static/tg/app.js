"use strict";

// Мостик Telegram (в обычном браузере его нет — тогда tg === undefined).
const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
// Скрипт telegram-web-app.js грузится и в обычном браузере, но там initData пустой.
// «Реально в Telegram» = есть подписанный initData. Иначе — режим браузерного превью.
const inTelegram = !!(tg && tg.initData);

const state = {
  token: null,
  products: [],
  category: "",        // "", "krossovki", "kedy", "botinki", "sale"
  search: "",
  total: 0,
  product: null,       // открытый товар
  variantIdx: 0,
  imageIdx: 0,
  size: null,
  qty: 1,
  cart: { items: [], total: 0, items_count: 0 },
  view: "catalog",
  // доставка
  deliveryType: "courier",   // courier | pickup
  pickupCity: "Москва",
  pickup: null,              // ПОДТВЕРЖДЁННЫЙ ПВЗ { code, address }
  pvzCandidate: null,        // ПВЗ, на который тыкнули (ещё не подтверждён)
  payMethod: "card",         // sbp | card | cod
};

let pvzMap = null;           // экземпляр Leaflet-карты
let pvzCluster = null;       // группа-кластер маркеров
let pvzSelMarker = null;     // подсвеченный (красный) маркер
// Вертикальные пины Leaflet: синий по умолчанию, красный — выбранный.
const ICON_BLUE = window.L && new L.Icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
});
const ICON_RED = window.L && new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
});
function highlightMarker(mk) {
  if (pvzSelMarker) pvzSelMarker.setIcon(ICON_BLUE);
  mk.setIcon(ICON_RED);
  pvzSelMarker = mk;
}

const TABS = [
  { key: "", label: "Все" },
  { key: "krossovki", label: "Кроссовки" },
  { key: "kedy", label: "Кеды" },
  { key: "botinki", label: "Ботинки" },
  { key: "sale", label: "Скидки", sale: true },
];

const fmt = (n) => n.toLocaleString("ru-RU") + " ₽";
const $ = (id) => document.getElementById(id);

// Достаёт читаемый текст ошибки из ответа API (detail бывает строкой ИЛИ
// списком ошибок валидации Pydantic — тогда берём первое сообщение).
function errText(e, fallback = "Что-то пошло не так") {
  const d = e && e.body && e.body.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length && d[0].msg) return d[0].msg.replace(/^Value error,?\s*/i, "");
  return fallback;
}

// Валидация телефона на клиенте (та же логика, что на бэкенде):
// 11 цифр, начинается с 7/8, мобильный код 9XX. Возвращает текст ошибки или "".
function phoneError(raw) {
  const digits = raw.replace(/\D/g, "");
  if (!digits) return "Укажите телефон";
  if (digits.length !== 11) return "Телефон должен содержать 11 цифр";
  if (!"78".includes(digits[0]) || digits[1] !== "9") return "Формат: +7 9XX XXX-XX-XX";
  return "";
}

// Живая маска телефона: строго +7 и не более 11 цифр, авто-формат.
function maskPhone(input) {
  const apply = () => {
    let d = input.value.replace(/\D/g, "");
    if (d.startsWith("8")) d = "7" + d.slice(1);
    if (d && !d.startsWith("7")) d = "7" + d;
    d = d.slice(0, 11);
    const a = d.slice(1, 4), b = d.slice(4, 7), c = d.slice(7, 9), e = d.slice(9, 11);
    let s = d ? "+7" : "";
    if (a) s += " " + a;
    if (b) s += " " + b;
    if (c) s += "-" + c;
    if (e) s += "-" + e;
    input.value = s;
  };
  input.addEventListener("input", apply);
  input.addEventListener("keydown", (ev) => {
    if (ev.key === "Backspace" && (input.value === "+7" || input.value === "")) {
      input.value = ""; ev.preventDefault();
    }
  });
}

// Валидация адреса на клиенте (зеркало бэкенда): длина, запятая, номер дома.
function addressError(raw) {
  const v = raw.trim();
  if (v.length < 10) return "Адрес слишком короткий — город, улица и дом";
  if (!v.includes(",")) return "Через запятые: Москва, ул. Тверская, д. 1";
  if (!/\d/.test(v)) return "Укажите номер дома";
  return "";
}

// ---------- API ----------
async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (state.token) headers["Authorization"] = "Bearer " + state.token;
  const r = await fetch(path, { ...opts, headers });
  const text = await r.text();
  const body = text ? JSON.parse(text) : null;
  if (!r.ok) throw { status: r.status, body };
  return body;
}

// ---------- Авторизация через Telegram ----------
async function authTelegram() {
  if (!tg || !tg.initData) return false;  // открыто не в Telegram
  try {
    const res = await api("/auth/tg-webapp", {
      method: "POST",
      body: JSON.stringify({ init_data: tg.initData }),
    });
    state.token = res.access_token;
    await loadCart();
    return true;
  } catch (e) {
    return false;
  }
}

function requireTelegram() {
  if (!state.token) {
    toast("Откройте магазин через Telegram, чтобы оформить заказ", true);
    return false;
  }
  return true;
}

// ---------- Тост ----------
let toastTimer;
function toast(msg, isError = false) {
  const t = $("toast");
  t.textContent = msg;
  t.className = "tg-toast" + (isError ? " err" : "");
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 2500);
  if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred(isError ? "error" : "success");
}

// ---------- Главная кнопка (Telegram MainButton или фолбэк) ----------
let mainHandler = null;
let fallbackBtn = null;

function setPrimary(text, onClick, { enabled = true, color = null } = {}) {
  if (inTelegram && tg.MainButton) {
    const mb = tg.MainButton;
    mb.setText(text);
    if (color) mb.color = color;
    if (mainHandler) mb.offClick(mainHandler);
    mainHandler = onClick;
    mb.onClick(mainHandler);
    enabled ? mb.enable() : mb.disable();
    mb.show();
  } else {
    if (!fallbackBtn) {
      fallbackBtn = document.createElement("button");
      fallbackBtn.className = "fallback-btn";
      document.body.appendChild(fallbackBtn);
    }
    fallbackBtn.textContent = text;
    fallbackBtn.disabled = !enabled;
    fallbackBtn.onclick = onClick;
    fallbackBtn.style.background = color || "";
    fallbackBtn.hidden = false;
  }
}

function hidePrimary() {
  if (inTelegram && tg.MainButton) tg.MainButton.hide();
  if (fallbackBtn) fallbackBtn.hidden = true;
}

// ---------- Навигация между экранами ----------
function showView(name) {
  state.view = name;
  ["Catalog", "Product", "Cart", "Checkout", "Payment", "Success"].forEach((v) => {
    $("view" + v).hidden = v.toLowerCase() !== name;
  });
  window.scrollTo(0, 0);

  // Кнопка «назад» Telegram
  const backTargets = { product: "catalog", cart: "catalog", checkout: "cart" };
  if (inTelegram && tg.BackButton) {
    backTargets[name] ? tg.BackButton.show() : tg.BackButton.hide();
  }
  $("backBtn").hidden = !backTargets[name] || inTelegram;  // фолбэк-стрелку в шапке показываем только без Telegram
}

function goBack() {
  const map = { product: "catalog", cart: "catalog", checkout: "cart" };
  const dest = map[state.view] || "catalog";
  if (dest === "catalog") openCatalog();
  else if (dest === "cart") openCart();
}

// ---------- Каталог ----------
function renderChips() {
  $("chips").innerHTML = TABS.map(
    (t) =>
      `<button class="tg-chip ${t.sale ? "sale" : ""} ${state.category === t.key ? "active" : ""}" data-cat="${t.key}">${t.label}</button>`
  ).join("");
}

async function loadCatalog() {
  $("grid").innerHTML = '<div class="loader">Загрузка…</div>';
  let q = "?page_size=100";
  if (state.category === "sale") q += "&only_discount=true";
  else if (state.category) q += "&category=" + state.category;
  if (state.search) q += "&q=" + encodeURIComponent(state.search);
  const d = await api("/products" + q);
  state.products = d.items;
  state.total = d.total;
  $("meta").textContent = `Найдено: ${d.total}`;
  renderGrid();
}

function renderGrid() {
  if (!state.products.length) {
    $("grid").innerHTML = `<div class="tg-empty">Ничего не найдено</div>`;
    return;
  }
  $("grid").innerHTML = state.products
    .map((p) => {
      const img = p.primary_image;
      const badge = p.discount_pct ? `<span class="tg-badge">−${p.discount_pct}%</span>` : "";
      const old = p.price_old ? `<span class="old">${fmt(p.price_old)}</span>` : "";
      return `
        <div class="tg-card" data-pid="${p.id}">
          ${badge}
          <img class="tg-card-img" src="${img}" alt="${p.name}" loading="lazy">
          <div class="tg-card-body">
            <div class="tg-card-brand">${p.brand.name}</div>
            <div class="tg-card-name">${p.name}</div>
            <div class="tg-card-price">${fmt(p.price)}${old}</div>
          </div>
        </div>`;
    })
    .join("");
}

function openCatalog() {
  showView("catalog");
  updateCartIndicator();
}

// ---------- Товар ----------
async function openProduct(id) {
  const p = state.products.find((x) => x.id === id);
  if (!p) return;
  state.product = { ...p };  // копия из списка для мгновенного показа
  state.variantIdx = 0;
  state.imageIdx = 0;
  state.size = null;
  state.qty = 1;
  showView("product");
  renderProduct();
  // догружаем детали (состав, отзывы) — их нет в данных списка
  try {
    const detail = await api(`/products/${id}`);
    if (state.product && state.product.id === id) {
      Object.assign(state.product, detail);
      renderProduct();
    }
  } catch (e) { /* остаёмся на данных из списка */ }
}

function specsBlock(p) {
  if (p.upper === undefined) return "";  // деталь ещё не загрузилась
  const rows = [
    ["Верх", p.upper], ["Подкладка", p.lining], ["Подошва", p.sole],
    ["Сезон", p.season], ["Страна", p.country],
  ].filter(([, v]) => v);
  if (!rows.length) return "";
  return `<div class="pv-label">Состав</div>
    <dl class="pv-specs">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>`;
}

function brandBlock(p) {
  const d = p.brand && p.brand.description;
  if (!d) return "";
  return `<div class="pv-label">О бренде ${p.brand.name}</div><div class="pv-desc">${d}</div>`;
}

function reviewsBlock(p) {
  if (!Array.isArray(p.reviews) || !p.reviews.length) return "";
  const head = `<div class="pv-label">Отзывы · ${p.reviews.length} · ★ ${p.rating.toFixed(1)}</div>`;
  const items = p.reviews
    .map((r) => `
      <div class="pv-rev">
        <div class="pv-rev-top"><span class="pv-rev-author">${r.author}</span>
        <span class="pv-rev-stars">${"★".repeat(r.rating)}${"☆".repeat(5 - r.rating)}</span></div>
        <div class="pv-rev-text">${r.text}</div>
      </div>`)
    .join("");
  return head + items;
}

function currentVariant() {
  return state.product.variants[state.variantIdx];
}

function renderProduct() {
  const p = state.product;
  const v = currentVariant();
  const images = v.images.length ? v.images : [{ url: p.primary_image }];
  const img = images[state.imageIdx] || images[0];
  const allSizes = [39, 40, 41, 42, 43, 44, 45];
  const old = p.price_old ? `<span class="old">${fmt(p.price_old)}</span>` : "";

  $("viewProduct").innerHTML = `
    <div class="pv-wrap">
      <img class="pv-photo" src="${img.url}" alt="${p.name}">
      ${
        images.length > 1
          ? `<div class="pv-thumbs">${images
              .map((im, i) => `<button class="pv-thumb ${i === state.imageIdx ? "active" : ""}" data-img="${i}"><img src="${im.url}"></button>`)
              .join("")}</div>`
          : ""
      }
      <div class="pv-brand">${p.brand.name}</div>
      <div class="pv-name">${p.name}</div>
      <div class="pv-price">${fmt(p.price)}${old}</div>

      <div class="pv-label">Цвет</div>
      <div class="pv-colors">
        ${p.variants
          .map(
            (vr, i) =>
              `<button class="pv-color ${i === state.variantIdx ? "active" : ""}" data-color="${i}"><span style="background:${vr.color_hex}"></span></button>`
          )
          .join("")}
      </div>

      <div class="pv-label">Размер RU</div>
      <div class="pv-sizes">
        ${allSizes
          .map((s) => {
            const avail = v.available_sizes.includes(s);
            return `<button class="pv-size ${state.size === s ? "active" : ""}" data-size="${s}" ${avail ? "" : "disabled"}>${s}</button>`;
          })
          .join("")}
      </div>

      <div class="pv-label">О товаре</div>
      <div class="pv-desc">${p.description || "—"}</div>
      ${specsBlock(p)}
      ${brandBlock(p)}
      ${reviewsBlock(p)}
    </div>`;

  // Главная кнопка
  if (state.size) {
    setPrimary(`В корзину · ${fmt(p.price * state.qty)}`, addToCart, { enabled: true });
  } else {
    setPrimary("Выберите размер", () => {}, { enabled: false });
  }
}

async function addToCart() {
  if (!requireTelegram()) return;
  const v = currentVariant();
  try {
    state.cart = await api("/cart/items", {
      method: "POST",
      body: JSON.stringify({ variant_id: v.id, size: state.size, quantity: state.qty }),
    });
    updateCartIndicator();
    toast(`Добавлено · ${state.product.name}`);
    openCatalog();
  } catch (e) {
    toast(errText(e, "Не удалось добавить"), true);
  }
}

// ---------- Корзина ----------
async function loadCart() {
  if (!state.token) return;
  state.cart = await api("/cart");
  updateCartIndicator();
}

function updateCartIndicator() {
  const n = state.cart.items_count || 0;
  const badge = $("cartIndN");
  badge.textContent = n;
  badge.hidden = n === 0;
  // На каталоге главная кнопка ведёт в корзину
  if (state.view === "catalog") {
    if (n > 0) setPrimary(`Корзина · ${fmt(state.cart.total)}`, openCart, { enabled: true });
    else hidePrimary();
  }
}

function openCart() {
  showView("cart");
  renderCart();
}

function renderCart() {
  const c = state.cart;
  if (!c.items.length) {
    $("viewCart").innerHTML = `<div class="cart-empty">Корзина пуста</div>`;
    hidePrimary();
    return;
  }
  $("viewCart").innerHTML =
    c.items
      .map(
        (it) => `
      <div class="cart-item">
        <img src="${it.variant.image_url}" alt="">
        <div class="cart-item-info">
          <div class="cart-item-name">${it.product.name}</div>
          <div class="cart-item-sub">${it.variant.color_name} · р. ${it.size}</div>
          <div class="cart-item-price">${fmt(it.subtotal)}</div>
          <div class="cart-qty">
            <button data-dec="${it.id}">−</button>
            <span>${it.quantity}</span>
            <button data-inc="${it.id}">+</button>
          </div>
        </div>
      </div>`
      )
      .join("") + `<div class="cart-total"><span>Итого</span><span>${fmt(c.total)}</span></div>`;

  setPrimary(`Оформить · ${fmt(c.total)}`, openCheckout, { enabled: true });
}

async function changeQty(itemId, delta) {
  const item = state.cart.items.find((i) => i.id === itemId);
  if (!item) return;
  const q = item.quantity + delta;
  try {
    if (q <= 0) state.cart = await api(`/cart/items/${itemId}`, { method: "DELETE" });
    else state.cart = await api(`/cart/items/${itemId}`, { method: "PATCH", body: JSON.stringify({ quantity: q }) });
    updateCartIndicator();
    renderCart();
  } catch (e) {
    toast(errText(e, "Не удалось изменить"), true);
  }
}

// ---------- Оформление ----------
function openCheckout() {
  if (!requireTelegram()) return;
  showView("checkout");
  const name = tg && tg.initDataUnsafe && tg.initDataUnsafe.user
    ? [tg.initDataUnsafe.user.first_name, tg.initDataUnsafe.user.last_name].filter(Boolean).join(" ")
    : "";
  $("viewCheckout").innerHTML = `
    <div class="field"><label>Имя получателя</label><input id="coName" value="${name}" placeholder="Иван Иванов"></div>
    <div class="field"><label>Телефон</label><input id="coPhone" type="tel" inputmode="tel" placeholder="+7 9XX XXX-XX-XX"></div>
    <div class="field">
      <label>Способ получения</label>
      <div class="seg" id="deliverySeg">
        <button type="button" data-dtype="courier" class="${state.deliveryType === "courier" ? "active" : ""}">Курьером</button>
        <button type="button" data-dtype="pickup" class="${state.deliveryType === "pickup" ? "active" : ""}">Пункт выдачи</button>
      </div>
    </div>
    <div id="deliveryBody"></div>
    <div class="field"><div class="err" id="coErr"></div></div>`;
  maskPhone($("coPhone"));
  renderDeliveryBody();
  setPrimary("Оформить заказ", placeOrder, { enabled: true });
}

function renderDeliveryBody() {
  const body = $("deliveryBody");
  if (state.deliveryType === "courier") {
    body.innerHTML = `<div class="field"><label>Адрес доставки</label>
      <input id="coAddr" placeholder="Москва, ул. Тверская, д. 1, кв. 5" autocomplete="off"></div>`;
  } else {
    const opts = ["Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань", "Нижний Новгород", "Краснодар", "Ростов-на-Дону"];
    body.innerHTML = `
      <div class="field"><label>Город</label>
        <select id="pvzCity">${opts.map((c) => `<option ${c === state.pickupCity ? "selected" : ""}>${c}</option>`).join("")}</select>
      </div>
      <div class="pvz-hint">Нажмите точку на карте или в списке</div>
      <div id="pvzMap" class="pvz-map"></div>
      <div id="pvzDetail" class="pvz-detail" hidden></div>
      <div id="pvzList" class="pvz-list"></div>`;
    initPvzMap();
    loadPvzPoints();
    if (state.pickup) selectPvz(state.pickup);  // вернулись — показать выбранный
  }
}

function initPvzMap() {
  pvzMap = null;
  pvzCluster = null;
  // карта создаётся после отрисовки контейнера
  setTimeout(() => {
    if (!window.L || !$("pvzMap")) return;
    pvzMap = L.map("pvzMap", { attributionControl: false }).setView([55.75, 37.62], 10);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(pvzMap);
  }, 50);
}

async function loadPvzPoints() {
  const city = state.pickupCity;  // фиксируем город запроса
  const listEl = $("pvzList");
  if (listEl) listEl.innerHTML = '<div class="loader">Загрузка пунктов…</div>';
  let points = [];
  try {
    points = await api("/delivery/points?city=" + encodeURIComponent(city));
  } catch (e) { /* пусто */ }

  // если за время запроса пользователь сменил город — этот ответ устарел, игнорируем
  if (state.pickupCity !== city) return;

  // ждём, пока карта проинициализируется
  const waitMap = () => new Promise((res) => {
    const t = setInterval(() => { if (pvzMap) { clearInterval(t); res(); } }, 60);
    setTimeout(() => { clearInterval(t); res(); }, 1500);
  });
  await waitMap();
  if (state.pickupCity !== city) return;

  if (pvzCluster && pvzMap) { pvzMap.removeLayer(pvzCluster); pvzCluster = null; }
  if (!points.length) {
    if (listEl) listEl.innerHTML = '<div class="pvz-empty">Пунктов не найдено</div>';
    return;
  }
  // Кластеризация: близкие точки группируются в кружок с числом (раскрывается при зуме).
  pvzCluster = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 50 });
  pvzSelMarker = null;
  points.forEach((p) => {
    const mk = L.marker([p.lat, p.lon], { icon: ICON_BLUE });
    mk.on("click", () => { selectPvz(p); highlightMarker(mk); });
    pvzCluster.addLayer(mk);
  });
  if (pvzMap) {
    pvzMap.addLayer(pvzCluster);
    const b = pvzCluster.getBounds();
    if (b.isValid()) pvzMap.fitBounds(b, { padding: [30, 30] });
  }
  if (listEl) {
    listEl.innerHTML = points
      .slice(0, 40)
      .map((p) => `<button type="button" class="pvz-item" data-pvz='${encodeURIComponent(JSON.stringify({ code: p.code, address: p.address, work_time: p.work_time, lat: p.lat, lon: p.lon }))}'>📍 ${p.address}</button>`)
      .join("");
  }
}

// Тык по точке — показываем карточку ПВЗ (адрес + режим работы + «Подтвердить»).
function selectPvz(p) {
  state.pvzCandidate = p;
  const el = $("pvzDetail");
  if (!el) return;
  const confirmed = state.pickup && state.pickup.code === p.code;
  el.hidden = false;
  el.innerHTML = `
    <div class="pvz-d-name">📍 Пункт выдачи</div>
    <div class="pvz-d-addr">${p.address}</div>
    <div class="pvz-d-work">🕒 ${p.work_time || "часы работы уточняются"}</div>
    <button type="button" class="pvz-confirm ${confirmed ? "done" : ""}" data-confirm-pvz ${confirmed ? "disabled" : ""}>
      ${confirmed ? "✓ Адрес подтверждён" : "Подтвердить адрес"}
    </button>`;
  if (pvzMap && p.lat) pvzMap.setView([p.lat, p.lon], 14);
  if (tg && tg.HapticFeedback && tg.HapticFeedback.selectionChanged) tg.HapticFeedback.selectionChanged();
}

function confirmPvz() {
  const p = state.pvzCandidate;
  if (!p) return;
  state.pickup = { code: p.code, address: p.address, work_time: p.work_time, lat: p.lat, lon: p.lon };
  selectPvz(p);  // перерисовать карточку как подтверждённую
  toast("Пункт выдачи выбран ✓");
}

async function placeOrder() {
  const nameEl = $("coName"), phoneEl = $("coPhone"), addrEl = $("coAddr");
  [nameEl, phoneEl, addrEl].forEach((el) => el && el.classList.remove("input-error"));
  const name = nameEl.value.trim(), phone = phoneEl.value.trim();

  let firstMsg = "";
  const fail = (el, msg) => { if (el) el.classList.add("input-error"); if (!firstMsg) firstMsg = msg; };
  if (name.length < 2) fail(nameEl, "Укажите имя получателя");
  const pe = phoneError(phone);
  if (pe) fail(phoneEl, pe);

  let payload = { delivery_name: name, delivery_phone: phone, delivery_type: state.deliveryType };
  if (state.deliveryType === "courier") {
    const addr = addrEl.value.trim();
    const ae = addressError(addr);
    if (ae) fail(addrEl, ae);
    payload.delivery_address = addr;
  } else if (!state.pickup) {
    if (!firstMsg) firstMsg = "Выберите пункт выдачи на карте";
  } else {
    payload.delivery_address = state.pickup.address;
    payload.pickup_code = state.pickup.code;
  }
  if (firstMsg) { showCoErr(firstMsg); return; }
  showCoErr("");

  try {
    const res = await api("/orders", { method: "POST", body: JSON.stringify(payload) });
    state.cart = { items: [], total: 0, items_count: 0 };
    updateCartIndicator();
    renderPayment(res.order);
  } catch (e) {
    showCoErr(errText(e, "Проверьте данные доставки"));
  }
}

function showCoErr(msg) {
  const el = $("coErr");
  if (el) el.textContent = msg;
  if (msg && tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("error");
}

// ---------- Оплата (тестовая, выбор способа) ----------
const PAY_METHODS = [
  { key: "sbp", label: "СБП (по QR)", icon: "🏦" },
  { key: "card", label: "Карта МИР / банковская", icon: "💳" },
  { key: "cod", label: "При получении", icon: "📦" },
];

function renderPayment(order) {
  state.currentOrder = order;
  showView("payment");
  $("viewPayment").innerHTML = `
    <div class="pay">
      <h2>Заказ №${order.id} создан</h2>
      <div class="hint">Выберите способ оплаты. Оплата тестовая — деньги не списываются.</div>
      <div class="pay-card">
        ${order.items
          .map((it) => `<div class="pay-row"><span>${it.product_name} · р.${it.size} ×${it.quantity}</span><span>${fmt(it.subtotal)}</span></div>`)
          .join("")}
        <div class="pay-row total"><span>К оплате</span><span>${fmt(order.total_amount)}</span></div>
      </div>
      <div class="pay-methods" id="payMethods">
        ${PAY_METHODS.map((m) => `
          <button type="button" class="pay-method ${state.payMethod === m.key ? "active" : ""}" data-method="${m.key}">
            <span>${m.icon} ${m.label}</span><span class="pm-dot"></span>
          </button>`).join("")}
      </div>
      <div class="pay-note">🔒 Демо: реальная интеграция — здесь был бы экран банка/СБП.</div>
    </div>`;
  updatePayButton(order);
}

function updatePayButton(order) {
  const cod = state.payMethod === "cod";
  const text = cod ? "Оформить (оплата при получении)" : `Оплатить ${fmt(order.total_amount)} (тест)`;
  setPrimary(text, () => payMock(order), { enabled: true });
}

async function payMock(order) {
  try {
    await api("/payments/mock", {
      method: "POST",
      body: JSON.stringify({ order_id: order.id, method: state.payMethod }),
    });
    renderSuccess(order, state.payMethod !== "cod", state.payMethod);
  } catch (e) {
    toast(errText(e, "Не удалось провести оплату"), true);
  }
}

// ---------- Успех ----------
function renderSuccess(order, paid = false, method = "card") {
  showView("success");
  const codNote = method === "cod"
    ? "Оплата при получении в пункте выдачи."
    : "Оплата прошла. ";
  $("viewSuccess").innerHTML = `
    <div class="success">
      <div class="ok">${paid ? "✅" : "📦"}</div>
      <h2>Заказ №${order.id} ${paid ? "оплачен" : "оформлен"}</h2>
      <p>Сумма: ${fmt(order.total_amount)}<br>${codNote}Подтверждение придёт в чат.</p>
    </div>`;
  setPrimary("Вернуться в каталог", openCatalog, { enabled: true });
  if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
}

// ---------- Делегирование кликов ----------
document.addEventListener("click", (e) => {
  const card = e.target.closest("[data-pid]");
  if (card) return openProduct(+card.dataset.pid);

  const chip = e.target.closest("[data-cat]");
  if (chip) {
    state.category = chip.dataset.cat;
    renderChips();
    loadCatalog().then(updateCartIndicator);
    return;
  }
  const thumb = e.target.closest("[data-img]");
  if (thumb) { state.imageIdx = +thumb.dataset.img; renderProduct(); return; }

  const color = e.target.closest("[data-color]");
  if (color) {
    state.variantIdx = +color.dataset.color;
    state.imageIdx = 0;
    const nv = currentVariant();
    if (state.size && !nv.available_sizes.includes(state.size)) state.size = null;
    renderProduct();
    return;
  }
  const size = e.target.closest("[data-size]");
  if (size && !size.disabled) { state.size = +size.dataset.size; renderProduct(); return; }

  const inc = e.target.closest("[data-inc]");
  if (inc) return changeQty(+inc.dataset.inc, +1);
  const dec = e.target.closest("[data-dec]");
  if (dec) return changeQty(+dec.dataset.dec, -1);

  // переключатель способа получения
  const dt = e.target.closest("[data-dtype]");
  if (dt) {
    state.deliveryType = dt.dataset.dtype;
    document.querySelectorAll("#deliverySeg button").forEach((b) =>
      b.classList.toggle("active", b.dataset.dtype === state.deliveryType));
    renderDeliveryBody();
    return;
  }
  // выбор ПВЗ из списка
  const pvz = e.target.closest("[data-pvz]");
  if (pvz) { selectPvz(JSON.parse(decodeURIComponent(pvz.dataset.pvz))); return; }
  // подтверждение выбранного ПВЗ
  if (e.target.closest("[data-confirm-pvz]")) { confirmPvz(); return; }

  // выбор способа оплаты
  const pm = e.target.closest("[data-method]");
  if (pm) {
    state.payMethod = pm.dataset.method;
    document.querySelectorAll("#payMethods .pay-method").forEach((b) =>
      b.classList.toggle("active", b.dataset.method === state.payMethod));
    if (state.currentOrder) updatePayButton(state.currentOrder);
    return;
  }
});

// смена города на карте ПВЗ
document.addEventListener("change", (e) => {
  if (e.target.id === "pvzCity") {
    state.pickupCity = e.target.value;
    state.pickup = null;
    loadPvzPoints();
  }
});

$("backBtn").addEventListener("click", goBack);
$("cartBtn").addEventListener("click", openCart);
// убираем красную подсветку поля, как только в нём начали печатать
$("viewCheckout").addEventListener("input", (e) => e.target.classList && e.target.classList.remove("input-error"));

let searchTimer;
$("searchInput").addEventListener("input", (e) => {
  state.search = e.target.value.trim();
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadCatalog().then(updateCartIndicator), 300);
});

// ---------- Старт ----------
async function init() {
  if (tg) {
    tg.ready();
    tg.expand();
    if (inTelegram && tg.BackButton) tg.BackButton.onClick(goBack);
  }
  renderChips();
  await authTelegram();      // не в Telegram — просто каталог без заказа
  await loadCatalog();
  openCatalog();
}

init();
