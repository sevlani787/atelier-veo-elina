from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from bot.services.database import db
from bot.config import config

router = Router()

@router.message(Command("premium", "shop", "club", "membership"))
async def cmd_premium(message: Message, user_id: int = None, lang: str = "en"):
    """Show residency status and Atelier VEO Club terms (English default)."""
    if not user_id:
        user_id = message.from_user.id
    
    user_data = await db.get_user_data(user_id)
    balance = user_data['tokens'] if user_data else 0
    sub_type = user_data.get('sub_type', 'free') if user_data else 'free'
    expiry = user_data.get('sub_expiry') if user_data else None

    if lang == "ru":
        current_status = "Tasting Guest (Дегустационный доступ)"
        if sub_type == 'premium':
            current_status = f"Резидент Ателье (до: {expiry[:10]})" if expiry else "Резидент Ателье"
        elif sub_type == 'admin':
            current_status = "Founder & Executive Producer (Бессрочный безлимит)"

        text = (
            "✦ <b>ATELIER VEO CLUB | РЕЗИДЕНТУРА И ТАРИФЫ</b> ✦\n\n"
            f"• <b>Ваш статус:</b> {current_status}\n"
            f"• <b>Баланс Ателье:</b> <b>{balance:,}</b> Atelier Credits\n\n"
            "Atelier VEO Club — закрытая креативная резидентура, строго ограниченная <b>20 местами для брендов</b> со всего мира. "
            "Прямая 1-on-1 работа с Элиной как вашим AI Creative Director и архитектором визуальной оптики.\n\n"
            "<b>Тарифы резидентуры:</b>\n"
            "• <b>Founding Cohort (Места 01 – 10):</b> $190 / месяц (пожизненная клубная квота)\n"
            "• <b>Standard Residency (Места 11 – 20):</b> $250 / месяц\n"
            "<i>Включает 1,000 Atelier Credits ежемесячно со 100% Rollover (неиспользованные кредиты не сгорают).</i>\n\n"
            "<b>Дополнительные пакеты кредитов для резидентов:</b>\n"
            "• Studio Booster (+300 Credits) — $69\n"
            "• Production Sprint (+700 Credits) — $139\n"
            "• Commercial Master (+1,500 Credits) — $249\n\n"
            "<b>Оплата и активация:</b> Прямой B2B-расчет через <b>Payoneer</b> на официальном сайте."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Вступить в Клуб / Оплата (Payoneer)", url="https://veocreative.agency/club")],
            [InlineKeyboardButton(text="📜 Сетка услуг & Стоимость в кредитах", callback_data="view_rates_menu_ru")],
            [InlineKeyboardButton(text="🏛 Связаться с Исполнительным продюсером", url="https://t.me/veocreative")],
            [InlineKeyboardButton(text="🌐 Switch to English", callback_data="buy_premium_menu_en")]
        ])
    else:
        current_status = "Tasting Guest (Complimentary Pass)"
        if sub_type == 'premium':
            current_status = f"Atelier Resident (Active until: {expiry[:10]})" if expiry else "Atelier Resident"
        elif sub_type == 'admin':
            current_status = "Founder & Executive Producer (Unlimited Access)"

        text = (
            "✦ <b>ATELIER VEO CLUB | PRIVATE RESIDENCY</b> ✦\n\n"
            f"• <b>Current Status:</b> {current_status}\n"
            f"• <b>Production Balance:</b> <b>{balance:,}</b> Atelier Credits\n\n"
            "Atelier VEO Club is a private creative sanctuary dedicated to luxury beauty, artisanal fragrance, and high craftsmanship houses. "
            "Direct 1-on-1 collaboration with Elina as your dedicated AI Creative Director & Optical Architect.\n\n"
            "<b>Residency Quotas & Tiers:</b>\n"
            "• <b>Founding Cohort (Seats 01 – 10):</b> $190 / month (Lifetime Founding Privilege)\n"
            "• <b>Standard Residency (Seats 11 – 20):</b> $250 / month\n"
            "<i>Strict Global Quota: 20 Brand Residencies Worldwide. Includes 1,000 Atelier Credits monthly with 100% Rollover privilege (unused credits never expire).</i>\n\n"
            "<b>Resident Production Top-Up Packs:</b>\n"
            "• Studio Booster (+300 Credits) — $69\n"
            "• Production Sprint (+700 Credits) — $139\n"
            "• Commercial Master (+1,500 Credits) — $249\n\n"
            "<b>Payment & Activation:</b> Direct B2B settlement via <b>Payoneer</b> with instant VIP onboarding."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Apply for Residency / Pay via Payoneer", url="https://veocreative.agency/club")],
            [InlineKeyboardButton(text="📜 Production Rates & Credits Menu", callback_data="view_rates_menu_en")],
            [InlineKeyboardButton(text="🏛 Contact Executive Producer Vladimir", url="https://t.me/veocreative")],
            [InlineKeyboardButton(text="🌐 Русский язык", callback_data="buy_premium_menu_ru")]
        ])
    
    if isinstance(message, Message):
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
    elif isinstance(message, CallbackQuery):
        await message.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.message(Command("services", "rates", "pricing", "cost"))
async def cmd_services(message: Message):
    """Show rates menu."""
    await view_rates_menu_internal(message, lang="en")

@router.callback_query(F.data.in_(["buy_premium_menu", "buy_premium_menu_en"]))
async def open_premium_menu_en(callback: CallbackQuery):
    await cmd_premium(callback, user_id=callback.from_user.id, lang="en")
    await callback.answer()

@router.callback_query(F.data == "buy_premium_menu_ru")
async def open_premium_menu_ru(callback: CallbackQuery):
    await cmd_premium(callback, user_id=callback.from_user.id, lang="ru")
    await callback.answer()

@router.callback_query(F.data.in_(["view_rates_menu", "view_rates_menu_en"]))
async def view_rates_menu_en(callback: CallbackQuery):
    await view_rates_menu_internal(callback, lang="en")
    await callback.answer()

@router.callback_query(F.data == "view_rates_menu_ru")
async def view_rates_menu_ru(callback: CallbackQuery):
    await view_rates_menu_internal(callback, lang="ru")
    await callback.answer()

async def view_rates_menu_internal(target, lang: str = "en"):
    if lang == "ru":
        text = (
            "✦ <b>ATELIER VEO | 5 МОДУЛЕЙ И СЕТКА КРЕДИТОВ</b> ✦\n\n"
            "Каждое режиссерское действие с Элиной обеспечено выделенными вычислительными мощностями:\n\n"
            "1. <b>Dual-Layer Cinematic Prompt (/prompt):</b> <b>20 Cr</b>\n"
            "   <i>Layer 1: Режиссерский тритмент + Layer 2: 5-компонентный математический промпт на английском (Veo 2 / Kling / Sora).</i>\n\n"
            "2. <b>Visual QA & Prompt Doctor (/qa):</b> <b>25 Cr</b>\n"
            "   <i>Видеоаудит (файл до 2 ГБ / облачная ссылка): оценка /10, диагностика 4 зон + анти-дрейф патч.</i>\n\n"
            "3. <b>Website & Instagram Teardown (/audit):</b> <b>50 Cr</b>\n"
            "   <i>Aesthetic Prestige Score (/10), фотометрия, точки потери статуса + 3 готовых киносценария.</i>\n\n"
            "4. <b>Virtual Muse Architecture (/muse):</b> <b>100 Cr</b>\n"
            "   <i>Паспорт цифрового амбассадора: мульти-ракурсные семена, текстура кожи Hasselblad, палитра гардероба.</i>\n\n"
            "5. <b>Living Brand DNA Memory (/dna /vault):</b> <b>0 Cr</b> (Включено)\n"
            "   <i>Личный суверенный сейф бренда: геометрия, пантоны, материалы упаковки с авто-учетом (Zero-Rebriefing).</i>\n\n"
            "• <b>Режиссерский диалог и консультации:</b> <b>1 Cr</b>\n\n"
            "<i>✦ 100% Rollover Policy: Все неиспользованные кредиты бессрочно переносятся на следующий месяц.</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚡️ Докупить кредиты (/topup)", callback_data="open_topup_menu_ru")],
            [InlineKeyboardButton(text="💎 Вступить в Клуб / Оплата (Payoneer)", url="https://veocreative.agency/club")],
            [InlineKeyboardButton(text="« Условия резидентуры", callback_data="buy_premium_menu_ru")],
            [InlineKeyboardButton(text="🌐 Switch to English", callback_data="view_rates_menu_en")]
        ])
    else:
        text = (
            "✦ <b>ATELIER VEO | 5 DIRECTORIAL MODULES & RATES</b> ✦\n\n"
            "Each creative action with Elina is backed by discrete compute quotas:\n\n"
            "1. <b>Dual-Layer Cinematic Prompt (/prompt):</b> <b>20 Cr</b>\n"
            "   <i>Layer 1: Directorial treatment + Layer 2: English 5-component optical formula code block (Veo 2 / Kling / Sora).</i>\n\n"
            "2. <b>Visual QA & Prompt Doctor (/qa):</b> <b>25 Cr</b>\n"
            "   <i>Video audit (up to 2 GB or Drive link): /10 score, 4-zone diagnostics + prompt doctor patch.</i>\n\n"
            "3. <b>Website & Instagram Teardown (/audit):</b> <b>50 Cr</b>\n"
            "   <i>Aesthetic prestige score (/10), photometry teardown, prestige leaks + 3 bespoke cinematic shot-lists.</i>\n\n"
            "4. <b>Virtual Muse Architecture (/muse):</b> <b>100 Cr</b>\n"
            "   <i>Digital ambassador blueprint: multi-angle seeds, Hasselblad dermal micro-texture, wardrobe palette.</i>\n\n"
            "5. <b>Living Brand DNA Memory (/dna /vault):</b> <b>0 Cr</b> (Included)\n"
            "   <i>Private Sovereign Vault: pantones, materials, sensory archive with Zero-Rebriefing.</i>\n\n"
            "• <b>Directorial Brainstorm & Dialogue:</b> <b>1 Cr</b>\n\n"
            "<i>✦ 100% Rollover Privilege: Unused credits never expire upon monthly residency renewal.</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚡️ Top-Up Booster Packs (/topup)", callback_data="open_topup_menu_en")],
            [InlineKeyboardButton(text="💎 Apply for Residency via Payoneer", url="https://veocreative.agency/club")],
            [InlineKeyboardButton(text="« Residency Tiers", callback_data="buy_premium_menu_en")],
            [InlineKeyboardButton(text="🌐 Русский язык", callback_data="view_rates_menu_ru")]
        ])
    
    if isinstance(target, Message):
        await target.answer(text, reply_markup=kb, parse_mode="HTML")
    elif isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("topup", "boost", "booster"))
async def cmd_topup(message: Message, lang: str = "en"):
    """Меню пакетов докупки кредитов (Booster Top-Up Packs)."""
    user_id = message.from_user.id
    user_data = await db.get_user_data(user_id)
    balance = user_data.get('tokens', 0) if user_data else 0
    user_lang = await db.get_setting(f"user_lang_{user_id}", lang)

    if user_lang == "ru":
        text = (
            "✦ <b>ATELIER VEO CLUB | ПАКЕТЫ ДОКУПКИ КРЕДИТОВ</b> ✦\n\n"
            f"• <b>Текущий баланс:</b> <b>{balance:,}</b> Atelier Credits\n\n"
            "Если у вас активный сезон релизов и кредиты подходят к концу, вы можете пополнить баланс без смены тарифного плана:\n\n"
            "• 💎 <b>Studio Booster:</b> +300 Credits — <b>$69</b>\n"
            "• 🚀 <b>Production Sprint:</b> +700 Credits — <b>$139</b>\n"
            "• 👑 <b>Commercial Master:</b> +1,500 Credits — <b>$249</b>\n\n"
            "<i>Все докупленные кредиты защищены 100% Rollover Policy и никогда не сгорают.</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Studio Booster (+300 Cr • $69)", callback_data="buy_topup_300")],
            [InlineKeyboardButton(text="🚀 Production Sprint (+700 Cr • $139)", callback_data="buy_topup_700")],
            [InlineKeyboardButton(text="👑 Commercial Master (+1,500 Cr • $249)", callback_data="buy_topup_1500")],
            [InlineKeyboardButton(text="« Вернуться к сетке услуг", callback_data="view_rates_menu_ru")]
        ])
    else:
        text = (
            "✦ <b>ATELIER VEO CLUB | BOOSTER TOP-UP PACKS</b> ✦\n\n"
            f"• <b>Current Production Balance:</b> <b>{balance:,}</b> Atelier Credits\n\n"
            "For intensive campaign cycles, top up your production compute without altering your residency tier:\n\n"
            "• 💎 <b>Studio Booster:</b> +300 Credits — <b>$69</b>\n"
            "• 🚀 <b>Production Sprint:</b> +700 Credits — <b>$139</b>\n"
            "• 👑 <b>Commercial Master:</b> +1,500 Credits — <b>$249</b>\n\n"
            "<i>All booster credits enjoy 100% Rollover privilege and never expire.</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Studio Booster (+300 Cr • $69)", callback_data="buy_topup_300")],
            [InlineKeyboardButton(text="🚀 Production Sprint (+700 Cr • $139)", callback_data="buy_topup_700")],
            [InlineKeyboardButton(text="👑 Commercial Master (+1,500 Cr • $249)", callback_data="buy_topup_1500")],
            [InlineKeyboardButton(text="« Return to Rates Menu", callback_data="view_rates_menu_en")]
        ])

    if isinstance(message, Message):
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
    elif isinstance(message, CallbackQuery):
        await message.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.in_(["open_topup_menu", "open_topup_menu_en"]))
async def open_topup_menu_en_cb(callback: CallbackQuery):
    await cmd_topup(callback, lang="en")
    await callback.answer()


@router.callback_query(F.data == "open_topup_menu_ru")
async def open_topup_menu_ru_cb(callback: CallbackQuery):
    await cmd_topup(callback, lang="ru")
    await callback.answer()


@router.callback_query(F.data.startswith("buy_topup_"))
async def process_topup_selection(callback: CallbackQuery):
    user_id = callback.from_user.id
    pack_key = callback.data.replace("buy_topup_", "")
    
    pack_info = {
        "300": {"name": "Studio Booster", "credits": 300, "price": "$69"},
        "700": {"name": "Production Sprint", "credits": 700, "price": "$139"},
        "1500": {"name": "Commercial Master", "credits": 1500, "price": "$249"}
    }.get(pack_key, {"name": "Custom Pack", "credits": int(pack_key) if pack_key.isdigit() else 300, "price": "Custom"})

    user_lang = await db.get_setting(f"user_lang_{user_id}", "en")
    
    if user_lang == "ru":
        reply_text = (
            f"✦ <b>ATELIER VEO | ДОКУПКА: {pack_info['name'].upper()}</b> ✦\n\n"
            f"• <b>Выбранный пакет:</b> +{pack_info['credits']:,} Atelier Credits\n"
            f"• <b>Стоимость:</b> <b>{pack_info['price']}</b>\n\n"
            "Для мгновенной активации завершите B2B-расчет через Payoneer на официальном сайте или свяжитесь с Исполнительным продюсером Владимиром (@veocreative).\n\n"
            "<i>Запрос зарегистрирован. Кредиты зачисляются сразу после подтверждения транзакции.</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Оплатить через Payoneer", url="https://veocreative.agency/club")],
            [InlineKeyboardButton(text="👤 Связаться с Продюсером", url="https://t.me/veocreative")],
            [InlineKeyboardButton(text="« Вернуться в меню", callback_data="open_topup_menu_ru")]
        ])
    else:
        reply_text = (
            f"✦ <b>ATELIER VEO | TOP-UP: {pack_info['name'].upper()}</b> ✦\n\n"
            f"• <b>Selected Package:</b> +{pack_info['credits']:,} Atelier Credits\n"
            f"• <b>Settlement:</b> <b>{pack_info['price']}</b>\n\n"
            "To finalize instant activation, complete your B2B settlement via Payoneer or contact Executive Producer Vladimir (@veocreative).\n\n"
            "<i>Your request has been logged. Credits are provisioned immediately upon transaction confirmation.</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Pay via Payoneer", url="https://veocreative.agency/club")],
            [InlineKeyboardButton(text="👤 Contact Producer", url="https://t.me/veocreative")],
            [InlineKeyboardButton(text="« Back to Booster Menu", callback_data="open_topup_menu_en")]
        ])

    await callback.message.edit_text(reply_text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

    # VIP-оповещение Владимиру с кнопкой моментального начисления в 1 клик
    if config.admin_id and user_id != config.admin_id:
        user_name = callback.from_user.full_name or "Резидент"
        username_str = f"@{callback.from_user.username}" if callback.from_user.username else "без username"
        admin_alert = (
            f"💎 <b>ЗАПРОС НА ДОКУПКУ КРЕДИТОВ В КЛУБЕ</b> 💎\n\n"
            f"👤 <b>Резидент:</b> {user_name} ({username_str})\n"
            f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n"
            f"📦 <b>Пакет:</b> {pack_info['name']} (+{pack_info['credits']:,} Cr • {pack_info['price']})\n"
            f"💳 <b>Расчет:</b> Payoneer B2B\n\n"
            f"После получения оплаты нажмите кнопку ниже для мгновенного начисления:"
        )
        admin_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Начислить +{pack_info['credits']} Cr", callback_data=f"grant_booster_{user_id}_{pack_info['credits']}")]
        ])
        try:
            await callback.bot.send_message(config.admin_id, admin_alert, reply_markup=admin_kb, parse_mode="HTML")
        except Exception as e:
            print(f"[TOPUP ALERT] Failed to notify admin: {e}")


@router.callback_query(F.data.startswith("grant_booster_"))
async def admin_grant_booster_cb(callback: CallbackQuery):
    if callback.from_user.id != config.admin_id:
        await callback.answer("Только для исполнительного продюсера.", show_alert=True)
        return

    parts = callback.data.split("_")
    if len(parts) >= 4:
        target_uid = int(parts[2])
        credits_to_add = int(parts[3])
        await db.add_tokens(target_uid, credits_to_add)
        new_balance = (await db.get_user_data(target_uid))['tokens']
        
        await callback.message.edit_text(
            f"{callback.message.text}\n\n"
            f"✅ <b>КРЕДИТЫ НАЧИСЛЕНЫ!</b>\n"
            f"Добавлено: +{credits_to_add:,} Cr. Новый баланс: {new_balance:,} Cr.",
            parse_mode="HTML"
        )
        await callback.answer("Кредиты успешно начислены!")

        # Уведомляем резидента
        try:
            user_lang = await db.get_setting(f"user_lang_{target_uid}", "en")
            if user_lang == "ru":
                client_msg = (
                    f"✦ <b>ATELIER VEO | БАЛАНС ПОПОЛНЕН</b> ✦\n\n"
                    f"Вам успешно начислен пакет +{credits_to_add:,} Atelier Credits.\n"
                    f"Текущий баланс студии: <b>{new_balance:,}</b> Credits.\n\n"
                    f"Элина готова к продолжению съемок и разработке сцен."
                )
            else:
                client_msg = (
                    f"✦ <b>ATELIER VEO | PRODUCTION TOP-UP ACTIVATED</b> ✦\n\n"
                    f"+{credits_to_add:,} Atelier Credits have been provisioned to your account.\n"
                    f"Current production balance: <b>{new_balance:,}</b> Credits.\n\n"
                    f"Elina is at your service to continue shaping light."
                )
            await callback.bot.send_message(target_uid, client_msg, parse_mode="HTML")
        except Exception as e:
            print(f"[BOOSTER NOTICE] Failed to notify resident: {e}")

