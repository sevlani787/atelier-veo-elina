from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from bot.services.database import db

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
            [InlineKeyboardButton(text="💎 Вступить в Клуб / Оплата (Payoneer)", url="https://veocreative.agency/#pricing")],
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
            [InlineKeyboardButton(text="💎 Apply for Residency / Pay via Payoneer", url="https://veocreative.agency/#pricing")],
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
            "✦ <b>ATELIER VEO | СЕТКА УСЛУГ И КРЕДИТОВ</b> ✦\n\n"
            "Каждое режиссерское действие с Элиной обеспечено выделенными вычислительными мощностями:\n\n"
            "• <b>Двухслойный режиссерский промпт (Veo 2 / Kling):</b> 20 Credits (~$3.8)\n"
            "  <i>Художественный анализ + блок кода 5-компонентной оптики VEO на английском языке.</i>\n\n"
            "• <b>Prompt Doctor & Multimodal Video QA Audit:</b> 25 Credits (~$4.7)\n"
            "  <i>Покадровый аудит дефектов (свет, анатомия, стекло флакона) + готовый скорректированный промпт.</i>\n\n"
            "• <b>Аудит эстетики бренда (Brand DNA Audit):</b> 50 Credits (~$9.5)\n"
            "  <i>Глубокий анализ референсов, палитры и позиционирование в кодах Quiet Luxury.</i>\n\n"
            "• <b>Синтез цифрового амбассадора Дома:</b> 100 Credits (~$19)\n"
            "  <i>Фотометрическая архитектура лица и консистентность виртуальной модели бренда.</i>\n\n"
            "• <b>Режиссерский диалог и брейншторм:</b> 1 Credit (~$0.19)\n"
            "  <i>Креативные консультации, поиск визуальных метафор и итерации.</i>\n\n"
            "<i>✦ 100% Rollover Policy: Все неиспользованные кредиты бессрочно переносятся на следующий месяц.</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Вступить в Клуб / Оплата (Payoneer)", url="https://veocreative.agency/#pricing")],
            [InlineKeyboardButton(text="« Вернуться к условиям резидентуры", callback_data="buy_premium_menu_ru")],
            [InlineKeyboardButton(text="🌐 Switch to English", callback_data="view_rates_menu_en")]
        ])
    else:
        text = (
            "✦ <b>ATELIER VEO | PRODUCTION RATES MENU</b> ✦\n\n"
            "Each creative action with Elina is backed by discrete compute quotas:\n\n"
            "• <b>The Dual-Layer Director Prompt (Veo 2 / Kling):</b> 20 Credits (~$3.8)\n"
            "  <i>Directorial treatment + English 5-component optical formula code block (anamorphic T-stops, Kelvin photometrics).</i>\n\n"
            "• <b>Prompt Doctor & Multimodal Video QA Audit:</b> 25 Credits (~$4.7)\n"
            "  <i>Frame-by-frame diagnostic audit (geometry drift, lighting flaws, anatomical fidelity) + immediate prompt doctoring.</i>\n\n"
            "• <b>Brand Aesthetic Audit:</b> 50 Credits (~$9.5)\n"
            "  <i>Social/web audit + sensory brand archive alignment in Quiet Luxury codes.</i>\n\n"
            "• <b>Virtual Ambassador Blueprint:</b> 100 Credits (~$19)\n"
            "  <i>Photometric prompt architecture for consistent digital brand ambassadors.</i>\n\n"
            "• <b>Directorial Brainstorm & Dialogue:</b> 1 Credit (~$0.19)\n"
            "  <i>Directorial consultations, moodboard analysis, and scene iterations.</i>\n\n"
            "<i>✦ 100% Rollover Privilege: Unused credits never expire upon monthly residency renewal.</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Apply for Residency via Payoneer", url="https://veocreative.agency/#pricing")],
            [InlineKeyboardButton(text="« Return to Residency Menu", callback_data="buy_premium_menu_en")],
            [InlineKeyboardButton(text="🌐 Русский язык", callback_data="view_rates_menu_ru")]
        ])
    
    if isinstance(target, Message):
        await target.answer(text, reply_markup=kb, parse_mode="HTML")
    elif isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
