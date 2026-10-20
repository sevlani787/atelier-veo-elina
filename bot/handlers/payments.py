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
    
    current_status = "Tasting Guest (Complimentary Pass)"
    expiry_info = ""
    if user_data:
        if user_data.get('sub_type') == 'premium':
            expiry = user_data.get('sub_expiry')
            expiry_info = f" (Active until: {expiry[:10]})" if expiry else ""
            current_status = f"Atelier Resident{expiry_info}"
        elif user_data.get('sub_type') == 'admin':
            current_status = "Founder & Executive Producer (Unlimited)"
            
    balance = user_data['tokens'] if user_data else 0
    
    text = (
        "✦ <b>ATELIER VEO CLUB | PRIVATE RESIDENCY</b> ✦\n\n"
        f"• <b>Current Status:</b> {current_status}\n"
        f"• <b>Production Balance:</b> <b>{balance:,}</b> Atelier Credits\n\n"
        "Atelier VEO Club is a private creative residency limited to strictly <b>20 global brand memberships</b> worldwide. "
        "Direct 1-on-1 collaboration with Elina as your dedicated AI Creative Director & Prompt Architect.\n\n"
        "<b>Residency Tiers:</b>\n"
        "• <b>Founding Cohort (Seats 01 – 10):</b> $190 / month\n"
        "• <b>Standard Residency (Seats 11 – 20):</b> $250 / month\n"
        "<i>Includes 1,000 Atelier Credits monthly with 100% Rollover privilege (unused credits never expire).</i>\n\n"
        "<b>Resident Production Top-Up Packs:</b>\n"
        "• Studio Booster (+300 Credits) — $69\n"
        "• Production Sprint (+700 Credits) — $139\n"
        "• Commercial Master (+1,500 Credits) — $249\n\n"
        "<b>Payment & Activation:</b> Direct B2B settlement via <b>Payoneer</b> with instant VIP onboarding."
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Apply for Residency / Pay via Payoneer", url="https://veocreative.agency/#pricing")],
        [InlineKeyboardButton(text="📜 Production Rates & Credits Menu", callback_data="view_rates_menu")],
        [InlineKeyboardButton(text="🏛 Contact Executive Producer Vladimir", url="https://t.me/veocreative")],
    ])
    
    if isinstance(message, Message):
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
    elif isinstance(message, CallbackQuery):
        await message.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "buy_premium_menu")
async def open_premium_menu(callback: CallbackQuery):
    """Открыть клубное меню через колбэк."""
    await cmd_premium(callback, user_id=callback.from_user.id)
    await callback.answer()

@router.callback_query(F.data == "view_rates_menu")
async def view_rates_menu(callback: CallbackQuery):
    """Показать детальную сетку списания Atelier Credits."""
    text = (
        "✦ <b>ATELIER VEO | PRODUCTION RATES MENU</b> ✦\n\n"
        "Each creative action with Elina is backed by discrete compute quotas:\n\n"
        "• <b>Dual-Layer Director Prompt (Veo 2 / Kling):</b> 20 Credits (~$3.8)\n"
        "  <i>Russian soulful direct commentary + English 5-component optical formula code block.</i>\n\n"
        "• <b>Prompt Doctor & Video QA Audit:</b> 25 Credits (~$4.7)\n"
        "  <i>Keyframe breakdown, 4-point defect inspection, corrected re-generation prompt.</i>\n\n"
        "• <b>Brand Aesthetic Audit:</b> 50 Credits (~$9.5)\n"
        "  <i>Social/web scraping + strategic repositioning in Quiet Luxury & Japandi codes.</i>\n\n"
        "• <b>Virtual Ambassador Blueprint:</b> 100 Credits (~$19)\n"
        "  <i>Photometric prompt architecture for consistent digital brand models.</i>\n\n"
        "• <b>Directorial Brainstorm & Dialogue:</b> 1 Credit (~$0.19)\n"
        "  <i>Creative consultation, moodboards, and scene iterations.</i>\n\n"
        "<i>✦ 100% Rollover Policy: Unused credits never expire upon monthly residency renewal.</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Apply for Residency via Payoneer", url="https://veocreative.agency/#pricing")],
        [InlineKeyboardButton(text="« Return to Residency Menu", callback_data="buy_premium_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()
