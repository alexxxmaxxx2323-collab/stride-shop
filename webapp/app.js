// ===== Подключение к Telegram =====
// Если страница открыта внутри Telegram — берём объект WebApp.
// Если в обычном браузере (для скриншотов) — tg будет null, и мы это учтём.
const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
if (tg) {
  tg.ready();
  tg.expand(); // развернуть на весь экран
}

// ===== Каталог товаров =====
// Фото — бесплатный сток Unsplash (ссылки проверены, отдают картинку).
const IMG = "https://images.unsplash.com/";
const PRODUCTS = [
  { id: 1,  name: "Aero Runner",      price: 8990,  rating: 4.8, desc: "Лёгкие беговые с дышащей сеткой",        img: IMG + "photo-1542291026-7eec264c27ff?w=600&q=80" },
  { id: 2,  name: "Street Classic",   price: 6490,  rating: 4.6, desc: "Минималистичные кеды на каждый день",     img: IMG + "photo-1460353581641-37baddab0fa2?w=600&q=80" },
  { id: 3,  name: "Trail Boost",      price: 10290, rating: 4.9, desc: "Цепкая подошва для города и трейла",       img: IMG + "photo-1595950653106-6c9ebd614d3a?w=600&q=80" },
  { id: 4,  name: "Retro '84",        price: 9790,  rating: 4.7, desc: "Винтажный силуэт, замша и кожа",           img: IMG + "photo-1606107557195-0e29a4b5b4aa?w=600&q=80" },
  { id: 5,  name: "Mono White",       price: 5990,  rating: 4.5, desc: "Чистый белый — универсальная пара",        img: IMG + "photo-1556906781-9a412961c28c?w=600&q=80" },
  { id: 6,  name: "Night Runner",     price: 11490, rating: 4.9, desc: "Тёмный верх, светоотражающие вставки",     img: IMG + "photo-1608231387042-66d1773070a5?w=600&q=80" },
  { id: 7,  name: "Court Pro",        price: 7290,  rating: 4.6, desc: "Корт-стиль с поддержкой стопы",            img: IMG + "photo-1539185441755-769473a23570?w=600&q=80" },
  { id: 8,  name: "Cloud Knit",       price: 8490,  rating: 4.8, desc: "Бесшовный вязаный верх, сидит как носок",  img: IMG + "photo-1514989940723-e8e51635b782?w=600&q=80" },
  { id: 9,  name: "Bold Red",         price: 9290,  rating: 4.7, desc: "Яркий акцент для смелых образов",          img: IMG + "photo-1525966222134-fcfa99b8ae77?w=600&q=80" },
  { id: 10, name: "Urban Skate",      price: 6990,  rating: 4.5, desc: "Усиленный мыс для скейта",                img: IMG + "photo-1549298916-b41d501d3772?w=600&q=80" },
];

// ===== Состояние корзины: { id товара: количество } =====
const cart = {};

// Удобный помощник: найти товар по id
const findProduct = (id) => PRODUCTS.find((p) => p.id === id);
// Форматирование цены: 8990 -> "8 990 ₽"
const fmt = (n) => n.toLocaleString("ru-RU") + " ₽";

// ===== Отрисовка каталога =====
function renderCatalog() {
  const root = document.getElementById("catalog");
  root.innerHTML = PRODUCTS.map((p) => `
    <article class="card">
      <img src="${p.img}" alt="${p.name}" loading="lazy">
      <div class="card-body">
        <div class="rating">★ ${p.rating}</div>
        <div class="card-name">${p.name}</div>
        <div class="card-desc">${p.desc}</div>
        <div class="card-foot">
          <span class="price">${fmt(p.price)}</span>
          <button class="add-btn" data-add="${p.id}" aria-label="Добавить">+</button>
        </div>
      </div>
    </article>
  `).join("");
}

// ===== Работа с корзиной =====
function addToCart(id) {
  cart[id] = (cart[id] || 0) + 1;
  updateBadge();
  renderCart();
}
function changeQty(id, delta) {
  cart[id] = (cart[id] || 0) + delta;
  if (cart[id] <= 0) delete cart[id];
  updateBadge();
  renderCart();
}
function cartCount() {
  return Object.values(cart).reduce((s, q) => s + q, 0);
}
function cartTotal() {
  return Object.entries(cart).reduce((s, [id, q]) => s + findProduct(+id).price * q, 0);
}

// Счётчик на иконке корзины
function updateBadge() {
  const badge = document.getElementById("cartBadge");
  const n = cartCount();
  badge.textContent = n;
  badge.hidden = n === 0;
}

// Содержимое корзины + форма
function renderCart() {
  const items = document.getElementById("cartItems");
  const empty = document.getElementById("cartEmpty");
  const form = document.getElementById("checkoutForm");
  const ids = Object.keys(cart);

  if (ids.length === 0) {
    items.innerHTML = "";
    empty.hidden = false;
    form.hidden = true;
    return;
  }
  empty.hidden = true;
  form.hidden = false;

  items.innerHTML = ids.map((id) => {
    const p = findProduct(+id);
    const q = cart[id];
    return `
      <div class="cart-row">
        <img src="${p.img}" alt="">
        <div class="cart-info">
          <div class="n">${p.name}</div>
          <div class="p">${fmt(p.price)} × ${q} = ${fmt(p.price * q)}</div>
        </div>
        <div class="stepper">
          <button data-dec="${id}">−</button>
          <span>${q}</span>
          <button data-inc="${id}">+</button>
        </div>
      </div>`;
  }).join("");

  document.getElementById("totalSum").textContent = fmt(cartTotal());
}

// Открыть / закрыть корзину
function openCart() {
  document.getElementById("overlay").hidden = false;
  document.getElementById("cartSheet").hidden = false;
}
function closeCart() {
  document.getElementById("overlay").hidden = true;
  document.getElementById("cartSheet").hidden = true;
}

// Короткое всплывающее уведомление (нужно для демо в браузере)
function showToast(text) {
  const t = document.getElementById("toast");
  t.textContent = text;
  t.hidden = false;
  setTimeout(() => (t.hidden = true), 2500);
}

// ===== Оформление заказа =====
function submitOrder(e) {
  e.preventDefault();
  const name = document.getElementById("name").value.trim();
  const phone = document.getElementById("phone").value.trim();

  // Собираем заказ в аккуратный объект — его получит бот
  const order = {
    customer: { name, phone },
    items: Object.entries(cart).map(([id, q]) => {
      const p = findProduct(+id);
      return { name: p.name, qty: q, sum: p.price * q };
    }),
    total: cartTotal(),
  };

  if (tg && tg.sendData) {
    // Внутри Telegram: отправляем заказ боту и закрываем окно
    tg.sendData(JSON.stringify(order));
    tg.close();
  } else {
    // В браузере: показываем, что всё сработало (для скриншота)
    console.log("Заказ:", order);
    showToast("Заказ оформлен! 🎉");
    for (const k in cart) delete cart[k];
    updateBadge();
    renderCart();
    closeCart();
    e.target.reset();
  }
}

// ===== Навешиваем обработчики =====
document.getElementById("catalog").addEventListener("click", (e) => {
  const id = e.target.dataset.add;
  if (id) addToCart(+id);
});
document.getElementById("cartItems").addEventListener("click", (e) => {
  if (e.target.dataset.inc) changeQty(+e.target.dataset.inc, +1);
  if (e.target.dataset.dec) changeQty(+e.target.dataset.dec, -1);
});
document.getElementById("cartBtn").addEventListener("click", openCart);
document.getElementById("closeCart").addEventListener("click", closeCart);
document.getElementById("overlay").addEventListener("click", closeCart);
document.getElementById("checkoutForm").addEventListener("submit", submitOrder);

// Старт
renderCatalog();
updateBadge();
