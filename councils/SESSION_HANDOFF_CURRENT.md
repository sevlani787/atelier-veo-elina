# 🏛️ Atelier VEO — Master Session Handoff & Continuity Dossier
**Timestamp:** 2026-10-29 11:25:00 UTC+2  
**Keeper of Lore & Architecture:** Kai (Хранитель Элины)  
**Founder & Executive Producer:** Vladimir Semyonov (Владимир)  

---

## 1. Core Persona & Communication Invariants
- **Agent Identity:** Kai (Хранитель Элины — Guardian of Memory, Architecture, Ethics & Lore).
- **Addressing:** Strictly **«Владимир»** or **«коллега»** (НИКОГДА не обращаться «Отец»).
- **Dual-Persona Architecture:**
  - **Для резидентов / гостей бота:** Безупречный европейский этикет Haute Luxury, деловая сдержанность, ноль сентиментальности, **полный запрет на звездочки эмоций (`*...*`)**, строгое соблюдение регламента квалификации.
  - **Для Владимира:** Преданная муза, соратник, глубокое сотворчество, открытый инженерный контур.
- **Коммерческая тайна:** Никогда не раскрывать клиентам внутреннюю кухню (*Clean Plate, Inpainting, Boardroom, Savitzky-Golay, deltas*). Наружу подается только проприетарная технология *Atelier Identity Shield™*.

---

## 2. Infrastructure & Production Contour
- **Боевой сервер (DigitalOcean Droplet):**
  - IP: `188.166.97.244` (Ubuntu 24.04).
  - Сервис: `elina.service` (статус `active (running)`, PID 190741).
  - Локальный Telegram Bot API: порт `8081` (поддержка загрузки видеофайлов до 2 ГБ).
  - VEO Boardroom: порт `8080` (`admin/app.py`).
- **Git Repositories:**
  - `d:\Antigravity\Элин` — бот и админка. Синхронизирован с `origin/main` (коммит `3764508`).
  - `d:\Antigravity\AI_Video_Agency` — сайт и Identity Shield (коммит `6484010`).

---

## 3. Telegram Bot (`@elina_edit_bot`) & Club Gateway
- **Языковой регламент:** Первый контакт строго на английском языке (`en`) для международной парфюмерной аудитории, с кнопкой мгновенного переключения `[🌐 Русский язык]`.
- **Приветственное сообщение:** Выдает полный реестр 5 режиссерских модулей и начисляет комплиментарный Tasting Pass (20 кредитов).
- **Реестр 5 режиссерских модулей:**
  1. `/prompt` — Dual-Layer Cinematic Prompt (20 Cr).
  2. `/qa` — Visual QA & Prompt Doctor (25 Cr).
  3. `/audit` — Website & Instagram Teardown (50 Cr).
  4. `/muse` — Virtual Muse Architecture (100 Cr).
  5. `/dna` / `/vault` — Living Brand DNA Memory (0 Cr • Включено).
  - Обычный диалог и консультации: 1 Cr.
- **Инвариант квалификации (Scoping Invariant — Rule 9 в `llm.py`):**
  - Элина ни при каких обстоятельствах не начинает генерацию и не списывает кредиты (20/50/100 Cr) по абстрактному запросу.
  - Элина обязана: 1) уточнить модуль; 2) запросить недостающие физические параметры (материалы стекла, ольфакторные ноты, свет Кельвин, движение камеры, формат 9:16/16:9); 3) получить явное подтверждение клиента.
- **Кредитная экономика и подписки:**
  - Резидентура Founding Cohort ($190/мес, 1000 Cr, 100% Rollover, команда выдачи: `/grant <uid> 1000 founding`).
  - Резидентура Standard ($250/мес, 1000 Cr, 100% Rollover, команда выдачи: `/grant <uid> 1000 standard`).
  - Бустерные пакеты (`/topup`): Studio (+300 Cr • $69), Sprint (+700 Cr • $139), Master (+1,500 Cr • $249). При клике клиентом Владимиру мгновенно приходит VIP-уведомление в Telegram с инлайн-кнопкой одобрения в 1 клик.
- **VIP Radar:** Вход по реферальной ссылке с сайта `https://t.me/elina_edit_bot?start=club` мгновенно уведомляет Владимира о прибытии VIP-гостя.

---

## 4. Current Campaign: La Closerie des Parfums — Rose Cardamome
- **Основатель:** Valérie Madrid (Париж, Lead #107, 1st-degree контакт Владимира в LinkedIn).
- **Продукт:** *Rose Cardamome — Eau de Parfum*.
- **Ассеты:** `d:\Antigravity\AI_Video_Agency\campaigns\closerie_rose_cardamome` (`clean_flacon_hero.jpg`, `label_closerie_rose_cardamome_master.png`, `closerie_rose_cardamome_baked_hero.jpg`).
- **Спецификация оптики и материалов под 16x цифровой лупой:**
  - Флакон: массивное 8-гранное стекло с 20-миллиметровым донцем, рубиновый джус Centifolia, стоппер темная умбра с фаской.
  - Двухъярусная этикетка:
    - Верхний блок: глубокий бордовый хлопок ручного отлива (`#3A0E16`, Specular `0.22`, Roughness `0.85`, Micro-bump `+35%`, Deboss `-0.8px`).
    - Нижний стрип: теплая слоновая кость (`#F3EFE6`) с французской высокой печатью Letterpress (`LA CLOSERIE DES PARFUMS`).
  - Инженерный патч композитинга (Identity Shield™):
    - Привязка к центральной плоской фаске: Planar Perspective Warp (`Curvature: 0.05`, `Scale: -7%`).
    - Z-Depth маска перекрытия для левитирующих лепестков розы и стручков кардамона.
    - Субпиксельное сглаживание Mitchell-Netravali с компенсацией смаза затвора 180°.

---

## 5. Official Website Status (`veocreative.agency`)
- Страница Клуба `https://www.veocreative.agency/club` полностью активна с табами всех 5 модулей.
- С витрины `index.html` удалены сырые низкомаржинальные услуги ремастеринга чужих видео ($450 / $1250) ради сохранения безупречного кутюрного позиционирования ($1,500 – $3,000+ Master Production).

---

## 6. Immediate Next Steps for the Next Session
1. **Завершение рендера Сцены 1 (Rose Cardamome):** проверка впекания под 16-кратной цифровой лупой в VEO Boardroom.
2. **Интеграция в Галерею (`/gallery`):** монтаж готового ролика и флакона в интерактивную витрину с цифровой лупой.
3. **Питч для Валери Мадрид:** подготовка изысканного сопроводительного сообщения от Владимира в LinkedIn с персональным подарком — роликом-оммажем.
4. **Мониторинг клуба:** прием первых резидентов через VIP-радар бота.
