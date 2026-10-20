from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from bot.services.database import db

router = Router()

@router.message(Command("premium", "shop", "club", "membership"))
async def cmd_premium(message: Message, user_id: int = None):
    """Показать статус резидентуры и условия Atelier VEO Club."""
    if not user_id:
        user_id = message.from_user.id
    
    user_data = await db.get_user_data(user_id)
    
    current_status = "Tasting Guest (Дегустационный доступ)"
    expiry_info = ""
    if user_data:
        if user_data.get('sub_type') == 'premium':
            expiry = user_data.get('sub_expiry')
            expiry_info = f" (Активен до: {expiry[:10]})" if expiry else ""
            current_status = f"Резидент Ателье{expiry_info}"
        elif user_data.get('sub_type') == 'admin':
            current_status = "Founder & Executive Producer (Бессрочный безлимит)"
            
    balance = user_data['tokens'] if user_data else 0
    
    text = (
        "✦ <b>ATELIER VEO CLUB | РЕЗИДЕНТУРА И ТАРИФЫ</b> ✦\n\n"
        f"• <b>Ваш статус:</b> {current_status}\n"
        f"• <b>Баланс Ателье:</b> <b>{balance:,}</b> Atelier Credits\n\n"
        "Atelier VEO Club — это закрытая креативная резидентура, строго ограниченная <b>20 местами для брендов</b> со всего мира. "
        "Прямая 1-on-1 работа с Элиной как вашим AI Creative Director и архитектором визуальной оптики.\n\n"
        "<b>Тарифы резидентуры:</b>\n"
        "• <b>Founding Cohort (Места 01 – 10):</b> $190 / месяц (пожизненная клубная квота)\n"
        "• <b>Standard Residency (Места 11 – 20):</b> $250 / месяц\n"
        "<i>Включает 1,000 Atelier Credits ежемесячно со 100% Rollover (неиспользованные кредиты никогда не сгорают при продлении).</i>\n\n"
        "<b>Пакеты дополнительных кредитов для резидентов:</b>\n"
        "• Studio Booster (+300 Credits) — $69\n"
        "• Production Sprint (+700 Credits) — $139\n"
        "• Commercial Master (+1,500 Credits) — $249\n\n"
        "<b>Оплата и активация:</b> Прямой B2B-расчет через <b>Payoneer</b> на официальном сайте студии с мгновенным VIP-онбордингом."
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Вступить в Клуб / Оплата (Payoneer)", url="https://veocreative.agency/#pricing")],
        [InlineKeyboardButton(text="📜 Сетка услуг & Стоимость в кредитах", callback_data="view_rates_menu")],
        [InlineKeyboardButton(text="🏛 Связаться с Исполнительным продюсером", url="https://t.me/veocreative")],
    ])
    
    if isinstance(message, Message):
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
    elif isinstance(message, CallbackQuery):
        await message.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.message(Command("services", "rates", "pricing", "cost"))
async def cmd_services(message: Message):
    """Показать сетку услуг по команде /services."""
    await view_rates_menu_internal(message)

@router.callback_query(F.data == "buy_premium_menu")
async def open_premium_menu(callback: CallbackQuery):
    """Открыть клубное меню через колбэк."""
    await cmd_premium(callback, user_id=callback.from_user.id)
    await callback.answer()

@router.callback_query(F.data == "view_rates_menu")
async def view_rates_menu(callback: CallbackQuery):
    """Показать детальную сетку списания Atelier Credits."""
    await view_rates_menu_internal(callback)
    await callback.answer()

async def view_rates_menu_internal(target):
    text = (
        "✦ <b>ATELIER VEO | СЕТКА УСЛУГ И КРЕДИТОВ</b> ✦\n\n"
        "Каждое режиссерское действие с Элиной обеспечено выделенными вычислительными мощностями:\n\n"
        "• <b>Двухслойный режиссерский промпт (Veo 2 / Kling):</b> 20 Credits (~$3.8)\n"
        "  <i>Художественный режиссерский анализ + блок кода 5-компонентной оптики VEO на английском языке.</i>\n\n"
        "• <b>Prompt Doctor & Multimodal Video QA Audit:</b> 25 Credits (~$4.7)\n"
        "  <i>Покадровый аудит дефектов (свет, анатомия, стекло флакона) + скорректированный промпт.</i>\n\n"
        "• <b>Аудит эстетики бренда (Brand DNA Audit):</b> 50 Credits (~$9.5)\n"
        "  <i>Глубокий анализ референсов, палитры и позиционирование в кодах Quiet Luxury.</i>\n\n"
        "• <b>Синтез цифрового амбассадора Дома:</b> 100 Credits (~$19)\n"
        "  <i>Фотометрическая архитектура лица и консистентность виртуальной модели бренда.</i>\n\n"
        "• <b>Режиссерский диалог и брейншторм:</b> 1 Credit (~$0.19)\n"
        "  <i>Креативные консультации, поиск визуальных метафор и итерации.</i>\n\n"
        "<i>✦ 100% Rollover Policy: Все неиспользованные кредиты бессрочно переносятся на следующий месяц при продлении.</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Вступить в Клуб / Оплата (Payoneer)", url="https://veocreative.agency/#pricing")],
        [InlineKeyboardButton(text="« Вернуться к условиям резидентуры", callback_data="buy_premium_menu")]
    ])
    
    if isinstance(target, Message):
        await target.answer(text, reply_markup=kb, parse_mode="HTML")
    elif isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
