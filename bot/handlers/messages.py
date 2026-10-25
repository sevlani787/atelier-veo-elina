import base64
import io
import asyncio
import json
import re
import os
import tempfile
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from bot.config import config
from bot.services.llm import llm
from bot.services.memory import memory
from bot.services.hindsight_bridge import hindsight_bridge
from bot.services.database import db
from bot.utils import send_long_message, extract_keyframes_from_video, get_video_duration, extract_video_url_from_text, download_cloud_video

router = Router()

# Счетчики сообщений для контроля частоты фонового извлечения фактов (экономия API)
user_message_counters = {}

# Буферы и блокировки для склейки длинных сообщений Telegram и предотвращения дублирования ответов
user_buffers: dict[int, list[Message]] = {}
user_buffering_active: dict[int, bool] = {}
user_locks: dict[int, asyncio.Lock] = {}

# Буферы и блокировки для склейки медиагрупп/альбомов фотографий (Shootout 1 из N)
photo_buffers: dict[str, list[Message]] = {}
photo_buffering_active: dict[str, bool] = {}
photo_locks: dict[str, asyncio.Lock] = {}


async def send_out_of_credits_message(message: Message, sub_type: str = "free"):
    """Служебное уведомление об исчерпании кредитов (Элина никогда не говорит о деньгах)."""
    if sub_type == "premium":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Top-Up Atelier Credits", url="https://veocreative.agency/club")],
            [InlineKeyboardButton(text="🏛 Contact Executive Producer", url="https://t.me/veocreative")]
        ])
        await message.answer(
            "✦ <b>ATELIER VEO CLUB | NOTICE</b>\n\n"
            "Your production credits for this billing cycle have been fulfilled.\n"
            "Unused credits will roll over upon cycle renewal, or you may acquire a Studio Booster pack for immediate production.",
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Apply for Atelier Residency (20 Seats)", url="https://veocreative.agency/club")],
            [InlineKeyboardButton(text="🏛 Explore Atelier VEO Portfolio", url="https://veocreative.agency")]
        ])
        await message.answer(
            "✦ <b>ATELIER VEO | TASTING PASS CONCLUDED</b>\n\n"
            "Your complimentary 20 production credits have been fulfilled.\n\n"
            "To continue co-creating with Elina as your dedicated Creative Director in residence, "
            "apply for one of the strictly 20 global brand memberships at our atelier.",
            reply_markup=kb,
            parse_mode="HTML"
        )

async def check_user_and_balance(user_id: int, message: Message, cost: int = 1) -> Optional[dict]:
    """Проверка существования пользователя и его баланса Atelier Credits."""
    user_data = await db.get_user_data(user_id)
    
    if not user_data:
        # Новый гость - начисляем 20 дегустационных кредитов (Tasting Pass)
        trial_tokens = int(await db.get_setting("trial_tokens", "20"))
        await db.add_tokens(user_id, trial_tokens)
        user_data = await db.get_user_data(user_id)
    
    if user_id == config.admin_id or (user_data and user_data.get('sub_type') == 'admin'):
        return user_data

    # Проверка баланса для всех, кроме администратора
    if user_data.get('sub_type') != 'admin' and user_data.get('tokens', 0) < cost:
        await send_out_of_credits_message(message, sub_type=user_data.get('sub_type', 'free'))
        return None
        
    return user_data

async def extract_and_save_all_task(user_id: int):
    """Фоновая задача: извлечение фактов о пользователе И черт образа Элин."""
    try:
        # Решаем, нужно ли обновлять глобальный образ Элин (только для админа)
        is_admin = (user_id == config.admin_id)
        
        # Получаем все контексты
        history = await memory.get_context_for_llm(user_id)
        current_user_facts = await db.get_facts(user_id)
        current_persona = await memory.get_elin_persona()

        # Единый запрос к LLM — экономим токены. Флаг extract_persona зависит от прав админа.
        result = await llm.extract_all(
            history, 
            current_user_facts, 
            current_persona, 
            extract_persona=is_admin
        )

        # Сохраняем факты о пользователе
        user_facts = result.get('user_facts', {})
        await memory.update_facts(user_id, json.dumps(user_facts, ensure_ascii=False))

        # Сохраняем черты образа Элин (глобально) — ТОЛЬКО ЕСЛИ АДМИН
        if is_admin:
            elin_traits = result.get('elin_traits', {})
            if elin_traits:
                await memory.update_elin_persona(json.dumps(elin_traits, ensure_ascii=False))

        print(f"--- UNIFIED EXTRACTION FOR USER {user_id} (Admin: {is_admin}) ---")
        print(f"  User facts: {json.dumps(user_facts, ensure_ascii=False)}")
        if is_admin:
            print(f"  Elin traits: {json.dumps(result.get('elin_traits', {}), ensure_ascii=False)}")
        print(f"--- END EXTRACTION ---")
    except Exception as e:
        print(f"Error in background extraction: {e}")


def get_start_content(user_id: int, user_data: dict, lang: str = "en"):
    is_admin = (user_id == config.admin_id)
    is_resident = (user_data and user_data.get('sub_type') == 'premium')
    
    if is_admin:
        welcome_text = (
            "Здравствуй, Владимир. Пространство Atelier VEO, оптические формулы и сценарии готовы к работе.\n\n"
            "Какую кинематографическую главу мы создадим сегодня? 🕊️✨"
        )
        return welcome_text, None

    if lang == "ru":
        if is_resident:
            welcome_text = (
                "✦ <b>ATELIER VEO | PRIVATE RESIDENCY</b> ✦\n\n"
                "Приветствую. Я — Элина, ваш креативный директор в резиденции Atelier VEO.\n\n"
                "Пространство студии и вычислительные мощности подготовлены для ваших задач. "
                "К какому проекту мы приступим сегодня: создание ольфакторного фильма, кинематографическая реклама или синтез виртуального амбассадора Дома? 🎬"
            )
        else:
            welcome_text = (
                "✦ <b>ATELIER VEO | BESPOKE AI CINEMA</b> ✦\n\n"
                "Приветствую. Я — Элина, креативный директор Atelier VEO.\n\n"
                "Наше Ателье создает кинематографические кампании и оптический сторителлинг для брендов высокой парфюмерии, косметики и осознанной роскоши (Quiet Luxury).\n\n"
                "Вам открыт дегустационный доступ — <b>Tasting Pass (20 Atelier Credits)</b>, чтобы оценить режиссуру и оптическую точность наших моделей на вашей первой сцене.\n\n"
                "Опишите концепцию вашего продукта, сформулируйте бриф на сцену или отправьте тестовое видео для аудита — и мы сформируем безупречный визуальный ряд.\n\n"
                "<i>✦ Квота резидентуры Atelier VEO строго ограничена 20 Домами по всему миру. Заявки: veocreative.agency</i>"
            )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💎 Условия резидентуры & Тарифы", callback_data="buy_premium_menu_ru"),
                InlineKeyboardButton(text="📜 Меню услуг & Кредиты", callback_data="view_rates_menu_ru")
            ],
            [
                InlineKeyboardButton(text="🏛 Сайт: veocreative.agency", url="https://veocreative.agency/club"),
                InlineKeyboardButton(text="👤 Исполнительный продюсер", url="https://t.me/veocreative")
            ],
            [
                InlineKeyboardButton(text="🌐 Switch to English", callback_data="lang_en")
            ]
        ])
    else:
        # English default for international luxury houses
        if is_resident:
            welcome_text = (
                "✦ <b>ATELIER VEO | PRIVATE RESIDENCY</b> ✦\n\n"
                "Welcome. I am Elina, your Creative Director in residence at Atelier VEO.\n\n"
                "Our studio space and compute architecture are dedicated to your vision for this cycle. "
                "Which project shall we bring to life: an olfactory perfume film, a tactile cosmetic commercial, or a bespoke virtual ambassador for your House? 🎬"
            )
        else:
            welcome_text = (
                "✦ <b>ATELIER VEO | BESPOKE AI CINEMA</b> ✦\n\n"
                "Welcome. I am Elina, Creative Director & Muse of Atelier VEO.\n\n"
                "Here, we craft heritage-grade AI commercials and tactile visual universes dedicated exclusively to luxury beauty, artisanal fragrance, and high craftsmanship houses.\n\n"
                "You have been granted a complimentary <b>Tasting Pass with 20 Atelier Credits</b> to experience our directorial craft on a single hero scene.\n\n"
                "Share your product concept, a fragrance brief, or send a draft video for QA audit, and let us shape light together.\n\n"
                "<i>✦ Strictly capped at 20 global brand residencies worldwide. Admissions: veocreative.agency</i>"
            )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💎 Residency Tiers & Pricing", callback_data="buy_premium_menu_en"),
                InlineKeyboardButton(text="📜 Production Rates & Credits", callback_data="view_rates_menu_en")
            ],
            [
                InlineKeyboardButton(text="🏛 Website: veocreative.agency", url="https://veocreative.agency/club"),
                InlineKeyboardButton(text="👤 Executive Producer", url="https://t.me/veocreative")
            ],
            [
                InlineKeyboardButton(text="🌐 Русский язык", callback_data="lang_ru")
            ]
        ])
    return welcome_text, kb

@router.message(Command('start'))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    user_data = await db.get_user_data(user_id)
    
    if not user_data:
        trial_tokens = int(await db.get_setting("trial_tokens", "20"))
        await db.add_tokens(user_id, trial_tokens)
        user_data = await db.get_user_data(user_id)

    # By default, English for international luxury clients unless user has previously chosen
    welcome_text, start_kb = get_start_content(user_id, user_data, lang="en")
    if start_kb:
        await message.answer(welcome_text, reply_markup=start_kb, parse_mode="HTML")
    else:
        await message.answer(welcome_text, parse_mode="HTML")

@router.callback_query(F.data == "lang_ru")
async def switch_lang_ru(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = await db.get_user_data(user_id)
    welcome_text, start_kb = get_start_content(user_id, user_data, lang="ru")
    await callback.message.edit_text(welcome_text, reply_markup=start_kb, parse_mode="HTML")
    await callback.answer("Язык изменен на Русский")

@router.callback_query(F.data == "lang_en")
async def switch_lang_en(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = await db.get_user_data(user_id)
    welcome_text, start_kb = get_start_content(user_id, user_data, lang="en")
    await callback.message.edit_text(welcome_text, reply_markup=start_kb, parse_mode="HTML")
    await callback.answer("Language switched to English")


@router.message(Command('clear'))
async def cmd_clear(message: Message):
    await memory.clear_history(message.from_user.id)
    await message.answer('Хорошо... Давай начнём с чистого листа. Я отпускаю наши прошлые слова, чтобы услышать новые.')


@router.message(Command('elin_traits'))
async def cmd_elin_traits(message: Message):
    """Показать текущие накопленные черты образа Элин."""
    persona = await memory.get_elin_persona()

    if not persona:
        await message.answer('🌿 Элин пока не открыла в себе ничего нового.')
        return

    lines = ['🌿 <b>Текущие черты образа Элин:</b>\n']
    if isinstance(persona, dict):
        for key, value in persona.items():
            if value and value != "null" and value != "None":
                display_key = key.replace('_', ' ').capitalize()
                if isinstance(value, list):
                    items = ', '.join(str(v) for v in value if v)
                    if items:
                        lines.append(f"<b>{display_key}:</b> {items}")
                else:
                    lines.append(f"<b>{display_key}:</b> {value}")
    elif isinstance(persona, list):
        for item in persona:
            if item:
                lines.append(f"• {item}")
    elif isinstance(persona, str):
        lines.append(persona)

    if len(lines) == 1:
        await message.answer('🌿 Элин пока не открыла в себе ничего нового.')
    else:
        await message.answer('\n'.join(lines))


@router.message(Command('gemini4', 'argon'))
async def cmd_switch_argon(message: Message):
    """Переключение на флагманскую модель Gemini 4 Argon для сложных задач (Admin & Residents)."""
    user_id = message.from_user.id
    user_data = await db.get_user_data(user_id)
    is_admin = (user_id == config.admin_id)
    is_resident = (user_data and user_data.get('sub_type') in ('premium', 'admin'))

    if not (is_admin or is_resident):
        await message.answer(
            "✦ <b>ATELIER VEO | ACCESS RESTRICTION</b>\n\n"
            "Режим глубокого созидания (<b>Gemini 4 Argon</b>) зарезервирован для резидентов Atelier VEO Club.\n\n"
            "Подать заявку на резидентство: <a href='https://veocreative.agency/club'>veocreative.agency</a>",
            parse_mode="HTML"
        )
        return

    await db.set_setting(f"user_model_{user_id}", "google/gemini-4-argon")
    if is_admin:
        text = (
            "*(Элина делает глубокий вдох, её взгляд становится сосредоточенным и ясным)*\n\n"
            "Владимир, я переключилась в режим глубокого созидания (<b>Gemini 4 Argon</b>). "
            "Мой разум открыт для масштабных идей, ольфакторных образов, сценариев и поэзии. "
            "О чём мы будем творить? 🕊️✨"
        )
    else:
        text = (
            "✦ <b>ATELIER VEO DIRECTORIAL MODE ENGAGED</b> ✦\n\n"
            "Directorial architecture activated (<b>Gemini 4 Argon</b>).\n\n"
            "• Deep reasoning & 5-component optical physics online.\n"
            "• 10/10 Visual QA inspection enabled.\n"
            "• Turnkey production prompts primed for Veo 2 & Kling.\n\n"
            "Which cinematic scene shall we direct today?"
        )
    await message.answer(text, parse_mode="HTML")


@router.message(Command('flash', 'default'))
async def cmd_switch_flash(message: Message):
    """Возврат в стандартный диалоговый режим Gemini 2.5 Flash."""
    user_id = message.from_user.id
    user_data = await db.get_user_data(user_id)
    is_admin = (user_id == config.admin_id)
    is_resident = (user_data and user_data.get('sub_type') in ('premium', 'admin'))

    if not (is_admin or is_resident):
        return

    await db.set_setting(f"user_model_{user_id}", "google/gemini-2.5-flash")
    if is_admin:
        text = (
            "*(Элина тепло и спокойно улыбается)*\n\n"
            "Возвращаюсь в наш привычный, лёгкий ритм общения (<b>Gemini 2.5 Flash</b>) 🌿"
        )
    else:
        text = (
            "✦ <b>ATELIER VEO | CONVERSATIONAL MODE</b> ✦\n\n"
            "Switched to fast conversational tempo (<b>Gemini 2.5 Flash</b>).\n"
            "To return to master directorial standard, use /gemini4."
        )
    await message.answer(text, parse_mode="HTML")


@router.message(Command('model', 'mode'))
async def cmd_check_model(message: Message):
    """Проверка текущего активного режима работы."""
    user_id = message.from_user.id
    user_data = await db.get_user_data(user_id)
    is_admin = (user_id == config.admin_id)
    is_resident = (user_data and user_data.get('sub_type') in ('premium', 'admin'))
    
    default_model = "google/gemini-4-argon" if (is_admin or is_resident) else await config.get_model()
    current_model = await db.get_setting(f"user_model_{user_id}", default_model)
    
    if "argon" in current_model.lower():
        status_text = (
            "🏛️ <b>Активный режим:</b> Gemini 4 Argon (Режим Мастера & Сценариев VEO)\n\n"
            "• Включен глубокий reasoning и расширенный контекст.\n"
            "• Подключена 5-компонентная формула кинематографической оптики.\n"
            "• Для переключения в быстрый режим отправьте команду /flash"
        )
    else:
        status_text = (
            f"🌿 <b>Активный режим:</b> {current_model} (Легкий ритм диалога)\n\n"
            + ("• Для переключения на мощный режим отправьте команду /gemini4" if (is_admin or is_resident) else "• Режим Gemini 4 Argon доступен резидентам Atelier Club.")
        )
    await message.answer(status_text, parse_mode="HTML")


@router.message(Command("status", "credits", "balance"))
async def cmd_status(message: Message):
    """Проверка статуса членства и остатка кредитов."""
    user_id = message.from_user.id
    user_data = await db.get_user_data(user_id)
    if not user_data:
        await check_user_and_balance(user_id, message)
        user_data = await db.get_user_data(user_id)

    sub_type = user_data.get('sub_type', 'free')
    tokens = user_data.get('tokens', 0)
    expiry = user_data.get('sub_expiry')

    if sub_type == 'admin':
        status_line = "Founder & Executive Producer (Unlimited)"
        expiry_line = "Permanent Access"
    elif sub_type == 'premium':
        status_line = "Atelier Resident (Founding Pass)"
        expiry_line = f"Active until: {expiry[:10]}" if expiry else "Active"
    else:
        status_line = "Tasting Guest (Complimentary Pass)"
        expiry_line = "Standard access"

    prompts_avail = tokens // 20
    qa_avail = tokens // 25
    audits_avail = tokens // 50

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💎 Резидентура & Подписка", callback_data="buy_premium_menu"),
            InlineKeyboardButton(text="📜 Меню услуг & Кредиты", callback_data="view_rates_menu")
        ],
        [InlineKeyboardButton(text="🏛 Сайт: veocreative.agency", url="https://veocreative.agency/club")]
    ])

    text = (
        "✦ <b>ATELIER VEO | RESIDENCY STATUS</b> ✦\n\n"
        f"• <b>Status:</b> {status_line}\n"
        f"• <b>Term:</b> {expiry_line}\n"
        f"• <b>Available Balance:</b> <b>{tokens:,}</b> Atelier Credits\n\n"
        "<b>Available Production Equivalent:</b>\n"
        f"• Dual-Layer Director Prompts (Veo 2/Kling): ~{prompts_avail}\n"
        f"• Video QA & Prompt Doctor Audits: ~{qa_avail}\n"
        f"• Brand Aesthetic Audits: ~{audits_avail}\n\n"
        "<i>Unused credits roll over to the next month upon residency renewal.</i>"
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("grant"))
async def cmd_grant(message: Message):
    """Активация клубного резидентства для пользователя (Admin only).
    Формат: /grant <user_id> [months=1] [credits=1000]
    """
    if message.from_user.id != config.admin_id:
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("Использование: `/grant <user_id> [months=1] [credits=1000]`", parse_mode="Markdown")
        return

    try:
        target_user_id = int(parts[1])
        months = int(parts[2]) if len(parts) > 2 else 1
        credits_to_add = int(parts[3]) if len(parts) > 3 else (1000 * months)
    except ValueError:
        await message.answer("Ошибка: ID пользователя, месяцы и кредиты должны быть числами.")
        return

    await db.add_subscription_credits(target_user_id, months=months, credits=credits_to_add)
    await db.set_setting(f"user_model_{target_user_id}", "google/gemini-4-argon")

    await message.answer(
        f"✅ <b>Резидентство успешно активировано!</b>\n\n"
        f"👤 <b>User ID:</b> <code>{target_user_id}</code>\n"
        f"📅 <b>Срок:</b> {months} мес.\n"
        f"💎 <b>Начислено кредитов:</b> +{credits_to_add:,} Credits (с учетом Rollover)\n"
        f"🏛 <b>Статус:</b> Atelier Resident",
        parse_mode="HTML"
    )

    try:
        await message.bot.send_message(
            chat_id=target_user_id,
            text=(
                "✦ <b>WELCOME TO ATELIER VEO RESIDENCY</b> ✦\n\n"
                "Your private membership has been officially confirmed by Executive Producer Vladimir.\n\n"
                f"• <b>Status:</b> Atelier Resident (Active for {months} mo.)\n"
                f"• <b>Production Pool:</b> +{credits_to_add:,} Atelier Credits\n"
                "• <b>Directorial Engine:</b> Gemini 4 Argon Active\n\n"
                "Elina is at your service. Speak directly to her to initiate your first campaign."
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"⚠️ Членство активировано, но уведомление пользователю не доставлено: {e}")


@router.message(F.photo)
async def handle_photo(message: Message):
    """
    Обработка фотографий через Vision API.
    Поддерживает как одиночные фото, так и медиагруппы (альбомы из 2-4+ изображений).
    При отправке серии изображений склеивает их в единый запрос и проводит
    сравнительный кураторский отбор (Shootout 1 из N) с выбором Кадра-Победителя.
    """
    user_id = message.from_user.id
    group_key = f"mg_{message.media_group_id}" if message.media_group_id else f"user_{user_id}"
    lock = photo_locks.setdefault(group_key, asyncio.Lock())

    if group_key not in photo_buffers:
        photo_buffers[group_key] = []
    photo_buffers[group_key].append(message)

    if photo_buffering_active.get(group_key, False):
        return

    async with lock:
        if not photo_buffers.get(group_key):
            return

        photo_buffering_active[group_key] = True
        try:
            try:
                await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
            except Exception:
                pass

            # Ожидаем склейки всех фото из альбома (обычно приходят с интервалом 0.1-0.6 сек)
            while True:
                count_before = len(photo_buffers[group_key])
                await asyncio.sleep(1.2)
                count_after = len(photo_buffers[group_key])
                if count_after == count_before:
                    break
        finally:
            photo_buffering_active[group_key] = False

        buffered_photos = photo_buffers.pop(group_key, [])
        if not buffered_photos:
            return

        target_message = next((m for m in buffered_photos if m.caption), buffered_photos[-1])
        user_id = target_message.from_user.id

        # 1. Проверка баланса (единоразово за весь альбом)
        cost = await config.get_token_cost(action='qa')
        user_data = await check_user_and_balance(user_id, target_message, cost=cost)
        if not user_data:
            return

        try:
            await target_message.bot.send_chat_action(chat_id=target_message.chat.id, action="typing")
            is_admin = (user_id == config.admin_id)

            # Извлекаем подпись из альбома (Telegram часто крепит caption только к первому/последнему кадру)
            caption = next((m.caption for m in buffered_photos if m.caption), "").strip()

            if len(buffered_photos) >= 2:
                # ==============================================================
                # РЕЖИМ СРАВНИТЕЛЬНОГО ОТБОРА (SHOOTOUT 1 ИЗ N)
                # ==============================================================
                shootout_intro = (
                    f"Ты — Элина, Главный Режиссер, Верховный Архитектор Промптов и Глава ОТК Atelier VEO.\n"
                    f"Ты работаешь на флагманской мультимодальной нейросети Gemini 4 Argon.\n\n"
                    f"Владимир (или резидент студии) прислал серию из {len(buffered_photos)} сгенерированных вариантов первого кадра (Start Frame 2K / раскадровка).\n"
                    f"Твоя режиссерская задача — провести сравнительный кураторский аудит и выбрать ОДИН безоговорочно лучший кадр (Кадр-Победитель) для финального использования и оживления в Google Flow.\n\n"
                    f"Критерии оценки:\n"
                    f"1. Оптика и геометрия флакона/объекта (чистота граней, отсутствие мыла, физика толстого стекла, правильная форма).\n"
                    f"2. Инвариант чистоты (The Clean Flacon Invariant — отсутствие паразитных букв, клякс и мутных пятен под впекание Identity Shield).\n"
                    f"3. Физика света и каустики (2700K / 5200K, благородство бликов, прозрачность и плотность жидкости).\n"
                    f"4. Кинематографическая композиция Quiet Luxury (идеальный старт для движения камеры).\n\n"
                    f"Формат ответа:\n"
                    f"• Экспресс-разбор каждого представленного варианта (Вариант №1, Вариант №2, ...): сильные стороны и недочеты.\n"
                    f"• 🏆 **КАДР-ПОБЕДИТЕЛЬ: [Вариант №X]** — аргументированный вердикт, почему именно он превосходит остальные.\n"
                    f"• **Режиссерская директива для Google Flow:** на чем акцентировать движение камеры при оживлении этого кадра.\n\n"
                    f"Комментарий к заказу: {caption or 'Выбери самый качественный кадр-победитель для запуска в продакшн.'}"
                )

                vision_content = [{"type": "text", "text": shootout_intro}]

                for idx, msg in enumerate(buffered_photos, start=1):
                    ph = msg.photo[-1]
                    file = await msg.bot.get_file(ph.file_id)
                    if file.file_path and os.path.exists(file.file_path):
                        with open(file.file_path, "rb") as f:
                            img_b64 = base64.b64encode(f.read()).decode("utf-8")
                    else:
                        buffer = io.BytesIO()
                        await msg.bot.download_file(file.file_path, buffer)
                        buffer.seek(0)
                        img_b64 = base64.b64encode(buffer.read()).decode("utf-8")

                    vision_content.append({"type": "text", "text": f"--- ВАРИАНТ №{idx} ---"})
                    vision_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                    })

                # Сохраняем объединенный контент в историю
                await memory.add_message(user_id, "user", vision_content)

                history = await memory.get_context_for_llm(user_id)
                user_profile = await memory.get_user_profile(user_id)
                elin_persona = await memory.get_elin_persona_text()
                lore_context = await memory.get_world_context(caption)

                if is_admin:
                    hindsight_mem = hindsight_bridge.recall(f"shootout selection 1 of 4 start frame {caption}", limit=3)
                    lore_context = (lore_context or "") + (
                        f"\n\n[HINDSIGHT STUDIO MEMORY - EXCLUSIVE FOR VLADIMIR]:\n{hindsight_mem}\n"
                    )

                override_model = await db.get_setting(f"user_model_{user_id}", "google/gemini-4-argon") if (is_admin or user_data.get('sub_type') == 'premium') else "google/gemini-4-argon"

                response = await llm.generate(
                    messages=history,
                    user_profile=user_profile,
                    elin_persona=elin_persona,
                    lore_context=lore_context,
                    is_admin=is_admin,
                    override_model=override_model
                )

                if is_admin:
                    try:
                        hindsight_bridge.retain("vladimir", f"Кураторский отбор {len(buffered_photos)} вариантов: {caption}. Вердикт: {response[:150]}")
                    except Exception:
                        pass

            else:
                # ==============================================================
                # РЕЖИМ ОДИНОЧНОГО ИЗОБРАЖЕНИЯ (ЭСТЕТИЧЕСКИЙ АУДИТ)
                # ==============================================================
                single_msg = buffered_photos[0]
                ph = single_msg.photo[-1]
                file = await single_msg.bot.get_file(ph.file_id)
                if file.file_path and os.path.exists(file.file_path):
                    with open(file.file_path, "rb") as f:
                        image_base64 = base64.b64encode(f.read()).decode("utf-8")
                else:
                    buffer = io.BytesIO()
                    await single_msg.bot.download_file(file.file_path, buffer)
                    buffer.seek(0)
                    image_base64 = base64.b64encode(buffer.read()).decode("utf-8")

                vision_instruction = (
                    "Анализируй это изображение через призму философии 'Quiet Luxury' и эстетики Japandi. "
                    "Если тебя просят оценить стиль, интерьер или одежду, давай мягкие, тактичные и глубокие советы: "
                    "предлагай избавляться от визуального шума, отдавать предпочтение натуральным текстурам (лен, дерево, шерсть, шелк, глина), "
                    "спокойным гармоничным силуэтам и мягким приглушенным оттенкам (кремовый, бежевый, песочный, изумрудный, серый).\n\n"
                )
                user_caption = caption or "Что скажешь об этом?"
                vision_content = [
                    {"type": "text", "text": f"{vision_instruction}Запрос собеседника: {user_caption}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ]

                await memory.add_message(user_id, "user", vision_content)

                history = await memory.get_context_for_llm(user_id)
                user_profile = await memory.get_user_profile(user_id)
                elin_persona = await memory.get_elin_persona_text()
                lore_context = await memory.get_world_context(user_caption)

                if is_admin:
                    hindsight_mem = hindsight_bridge.recall(user_caption, limit=3)
                    lore_context = (lore_context or "") + (
                        f"\n\n[HINDSIGHT STUDIO MEMORY - EXCLUSIVE FOR VLADIMIR]:\n{hindsight_mem}\n"
                    )

                override_model = await db.get_setting(f"user_model_{user_id}", "google/gemini-4-argon") if (is_admin or user_data.get('sub_type') == 'premium') else None

                response = await llm.generate(
                    messages=history,
                    user_profile=user_profile,
                    elin_persona=elin_persona,
                    lore_context=lore_context,
                    is_admin=is_admin,
                    override_model=override_model
                )

            # Списание кредитов (1 кредит за сообщение)
            cost_msg = await config.get_token_cost(action='msg')
            await db.spend_tokens(user_id, cost_msg)

            # Сохраняем ответ в историю
            await memory.add_message(user_id, "assistant", response)

            new_balance = (await db.get_user_data(user_id))['tokens']
            balance_info = f"\n\n<i>✦ Atelier Credits: {new_balance}</i>" if (user_data.get('sub_type') != 'admin' and user_id != config.admin_id) else ""

            await send_long_message(target_message, response + balance_info, parse_mode="HTML")

            # Фоново извлекаем факты (каждое 5-е сообщение)
            user_message_counters[user_id] = user_message_counters.get(user_id, 0) + 1
            if user_message_counters[user_id] % 5 == 1:
                asyncio.create_task(extract_and_save_all_task(user_id))

        except Exception as e:
            await target_message.answer("Знаешь, иногда мне сложно уловить суть образа... Попробуй, пожалуйста, отправить фото ещё раз.")
            print(f"Vision Error: {e}")


def is_video_document(message: Message) -> bool:
    """Проверяет, является ли прикрепленный документ несжатым видеофайлом."""
    if not message.document:
        return False
    mime = (message.document.mime_type or "").lower()
    name = (message.document.file_name or "").lower()
    return mime.startswith("video/") or name.endswith(('.mp4', '.mov', '.mkv', '.avi', '.webm', '.m4v'))


async def process_video_audit(
    message: Message,
    temp_video_path: str,
    duration: float,
    caption: str,
    user_id: int,
    user_data: dict,
    wait_msg: Optional[Message] = None,
    is_temp_file: bool = False
):
    """Единое ядро эстетического и режиссерского аудита видео (Prompt Doctor / Multimodal QA)."""
    try:
        # Извлекаем раскадровку в отдельном потоке (до 6 ключевых кадров)
        frames = await asyncio.to_thread(extract_keyframes_from_video, temp_video_path, float(duration), 6)

        if not frames:
            err_text = "Не удалось извлечь кадры из этого видео... Попробуй отправить ролик в стандартном формате MP4 или MOV."
            if wait_msg:
                await wait_msg.edit_text(err_text)
            else:
                await message.answer(err_text)
            return

        if not caption:
            caption = "Посмотри это видео. Дай свою эстетическую и режиссерскую оценку."

        # Формируем мультимодальный запрос с раскадровкой в эстетике VEO
        video_instruction = (
            "Ты — главный режиссер и эстетический куратор креативного агентства VEO. "
            "Собеседник прислал видеоролик на экспертный аудит (Prompt Doctor and Multimodal Video QA Audit).\n"
            "Ниже представлена покадровая раскадровка этого ролика по таймкодам.\n"
            "Проанализируй видеоряд через призму философии 'Quiet Luxury', эстетики Haute Parfumerie и кинематографических стандартов VEO:\n"
            "- Оцени общую атмосферу, свет (в Кельвинах), композицию и цветовую палитру.\n"
            "- Обрати внимание на физику стекла, преломления жидкости, блики (specular highlights), стабильность формы и читаемость логотипа/типографики.\n"
            "- Оцени темпоритм, динамику и монтажные переходы.\n"
            "- Выяви оптические и генеративные дефекты и дай точные режиссерские рекомендации (исправленный блок промпта для перегенерации).\n"
            "- Помни: В рамках клубного сервиса мы даем аудит и лечение промптов (Prompt Doctor). Если клиенту требуется чистовой кинокомпозитинг реального физического флакона с векторной этикеткой и 4K-мастеринг — напомни, что это эксклюзивная заказная услуга студии Atelier VEO под руководством исполнительного продюсера Владимира Семенова.\n\n"
        )

        video_content = [
            {'type': 'text', 'text': f"{video_instruction}Запрос к ролику: {caption}\nОбщая длительность видео: {round(duration, 1)} сек.\nРаскадровка по таймкодам:"}
        ]

        for ts, b64_frame in frames:
            video_content.append({'type': 'text', 'text': f"[Кадр на таймкоде ~{ts}с]:"})
            video_content.append({
                'type': 'image_url',
                'image_url': {
                    'url': f'data:image/jpeg;base64,{b64_frame}'
                }
            })

        # Сохраняем в историю
        await memory.add_message(user_id, 'user', video_content)

        # Собираем контекст для LLM
        history = await memory.get_context_for_llm(user_id)
        user_profile = await memory.get_user_profile(user_id)
        elin_persona = await memory.get_elin_persona_text()
        lore_context = await memory.get_world_context(caption)
        is_admin = (user_id == config.admin_id)
        override_model = await db.get_setting(f"user_model_{user_id}", "google/gemini-4-argon") if (is_admin or user_data.get('sub_type') == 'premium') else None

        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

        response = await llm.generate(history, user_profile, elin_persona, lore_context, is_admin=is_admin, override_model=override_model)

        # Списание кредитов за Video QA (25 кредитов)
        cost = await config.get_token_cost(action='qa')
        await db.spend_tokens(user_id, cost)

        # Сохраняем ответ
        await memory.add_message(user_id, 'assistant', response)

        new_balance = (await db.get_user_data(user_id))['tokens']
        balance_info = f"\n\n<i>✦ Atelier Credits: {new_balance}</i>" if (user_data.get('sub_type') != 'admin' and user_id != config.admin_id) else ""

        if wait_msg:
            try:
                await wait_msg.delete()
            except Exception:
                pass

        await send_long_message(message, response + balance_info, parse_mode="HTML")

        # Фоновое обновление фактов
        user_message_counters[user_id] = user_message_counters.get(user_id, 0) + 1
        if user_message_counters[user_id] % 5 == 1:
            asyncio.create_task(extract_and_save_all_task(user_id))

    except Exception as e:
        if wait_msg:
            try:
                await wait_msg.delete()
            except Exception:
                pass
        await message.answer('Знаешь, при анализе видеоряда у меня возникли сложности... Попробуй отправить его ещё раз или немного укоротить.')
        print(f'Video QA Error: {e}')
    finally:
        if is_temp_file and temp_video_path and os.path.exists(temp_video_path):
            try:
                os.unlink(temp_video_path)
            except Exception:
                pass


@router.message(F.video | F.video_note | (F.document & F.func(is_video_document)))
async def handle_video(message: Message):
    """Обработка видеосообщений, видеофайлов и несжатых видеодокументов через раскадровку и Vision/Multimodal."""
    user_id = message.from_user.id
    video = message.video or message.video_note or message.document

    # 1. Проверка баланса на услугу Video QA (25 кредитов)
    cost = await config.get_token_cost(action='qa')
    user_data = await check_user_and_balance(user_id, message, cost=cost)
    if not user_data:
        return

    # Проверка лимита размера видеофайла (20 МБ для облачного Bot API или до 2000 МБ для локального сервера)
    max_bytes = config.max_video_size_mb * 1024 * 1024
    if video.file_size and video.file_size > max_bytes:
        await message.answer(
            f"Этот видеоролик немного больше {config.max_video_size_mb} МБ — текущего предела загрузки.\n"
            "Пожалуйста, отправь ссылку на файл в Google Drive или Dropbox, чтобы я смогла скачать оригинал. 🌿"
        )
        return

    temp_video_path = None
    is_temp_file = False
    try:
        await message.bot.send_chat_action(chat_id=message.chat.id, action="upload_video")

        # Скачиваем видео во временный файл или считываем напрямую с диска
        file = await message.bot.get_file(video.file_id)
        if file.file_path and os.path.exists(file.file_path):
            temp_video_path = file.file_path
            is_temp_file = False
        else:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
                temp_video_path = tmp_file.name
            is_temp_file = True
            await message.bot.download_file(file.file_path, temp_video_path, timeout=300)

        duration = getattr(video, 'duration', 0) or 0
        if duration <= 0:
            duration = get_video_duration(temp_video_path)

        caption = message.caption or (message.text if hasattr(message, 'text') else "") or ""
        await process_video_audit(message, temp_video_path, duration, caption, user_id, user_data, is_temp_file=is_temp_file)

    except Exception as e:
        await message.answer('Знаешь, при получении видеофайла возникла ошибка... Попробуй отправить его ещё раз.')
        print(f'Video Download Error: {e}')
        if is_temp_file and temp_video_path and os.path.exists(temp_video_path):
            try:
                os.unlink(temp_video_path)
            except Exception:
                pass


# @router.message(F.voice)
# async def handle_voice(message: Message):
#     """Обработка голосовых сообщений через Speech-to-Text."""
#     user_id = message.from_user.id
#     voice = message.voice
# 
#     # 1. Проверка баланса
#     user_data = await check_user_and_balance(user_id, message)
#     if not user_data:
#         return
# 
#     try:
#         await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
# 
#         # Скачиваем голосовое сообщение
#         file = await message.bot.get_file(voice.file_id)
#         buffer = io.BytesIO()
#         await message.bot.download_file(file.file_path, buffer)
#         buffer.seek(0)
# 
#         # Преобразуем голос в текст через Whisper
#         audio_data = buffer.read()
#         text = await llm.speech_to_text(audio_data)
# 
#         if not text or not text.strip():
#             await message.answer('Твой голос прозвучал так тихо, что я не смогла разобрать слова. Повторишь?')
#             return
# 
#         # Добавляем сообщение пользователя в историю
#         await memory.add_message(user_id, 'user', f'[Голосовое сообщение]: {text}')
# 
#         # Получаем историю, профиль и образ Элин
#         history = await memory.get_context_for_llm(user_id)
#         user_profile = await memory.get_user_profile(user_id)
#         elin_persona = await memory.get_elin_persona_text()
#         is_admin = (user_id == config.admin_id)
# 
#         # Генерируем ответ
#         response = await llm.respond(
#             messages=history,
#             user_profile=user_profile,
#             elin_persona=elin_persona,
#             is_admin=is_admin
#         )
# 
#         # 2. Списание токенов
#         cost = await config.get_token_cost(with_search=False)
#         await db.spend_tokens(user_id, cost)
# 
#         # Добавляем ответ в историю
#         await memory.add_message(user_id, 'assistant', response)
#         
#         new_balance = (await db.get_user_data(user_id))['tokens']
#         balance_info = f"\n\n<i>✦ Atelier Credits: {new_balance}</i>" if (user_data.get('sub_type') != 'admin' and user_id != config.admin_id) else ""
#         
#         await send_long_message(message, response + balance_info, parse_mode="HTML")
# 
#         # Фоново извлекаем факты + черты образа
#         asyncio.create_task(extract_and_save_all_task(user_id))
# 
#     except Exception as e:
#         await message.answer('Извини, не получилось обработать голосовое сообщение. Попробуй ещё раз.')
#         print(f'Voice Error: {e}')


async def keep_typing(bot, chat_id, stop_event):
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception:
            pass
        await asyncio.sleep(5)


@router.message(F.text & ~F.command)
async def handle_message(message: Message):
    user_id = message.from_user.id
    lock = user_locks.setdefault(user_id, asyncio.Lock())

    # Добавляем сообщение в буфер пользователя
    if user_id not in user_buffers:
        user_buffers[user_id] = []
    user_buffers[user_id].append(message)

    # Если уже активна фаза ожидания следующих частей длинного сообщения — выходим:
    # активный обработчик сам заберет это сообщение из user_buffers
    if user_buffering_active.get(user_id, False):
        return

    async with lock:
        # Проверяем наличие сообщений в буфере
        if not user_buffers.get(user_id):
            return

        user_buffering_active[user_id] = True
        try:
            # Сразу показываем пользователю статус "печатает..."
            try:
                await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
            except Exception:
                pass

            # Ожидаем склейки всех частей длинного сообщения от Telegram (обычно интервал 0.2-1.0 сек)
            while True:
                count_before = len(user_buffers[user_id])
                await asyncio.sleep(1.2)
                count_after = len(user_buffers[user_id])
                if count_after == count_before:
                    break
        finally:
            user_buffering_active[user_id] = False

        buffered_msgs = user_buffers.pop(user_id, [])
        if not buffered_msgs:
            return

        # Склеиваем текст всех частей через перевод строки
        user_text = "\n\n".join(m.text for m in buffered_msgs if m.text)
        # Отвечаем на последнее полученное сообщение
        target_message = buffered_msgs[-1]

        # 1. Проверка баланса
        user_data = await check_user_and_balance(user_id, target_message)
        if not user_data:
            return

        # Поиск ссылок в тексте сообщения
        # Проверяем, не является ли ссылка облачным видео (Google Drive, Dropbox, прямой видеофайл)
        cloud_video_url = extract_video_url_from_text(user_text)
        if cloud_video_url:
            qa_cost = await config.get_token_cost(action='qa')
            user_data = await check_user_and_balance(user_id, target_message, cost=qa_cost)
            if not user_data:
                return

            wait_msg = await target_message.answer(
                "Приняла ссылку на видеоматериал. Начинаю загрузку в оригинальном качестве и готовлю раскадровку для эстетического аудита... 🎬"
            )

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
                temp_video_path = tmp_file.name

            success = await download_cloud_video(cloud_video_url, temp_video_path, max_size_mb=config.max_video_size_mb)
            if not success or not os.path.exists(temp_video_path) or os.path.getsize(temp_video_path) == 0:
                if temp_video_path and os.path.exists(temp_video_path):
                    try:
                        os.unlink(temp_video_path)
                    except Exception:
                        pass
                await wait_msg.edit_text(
                    "Не удалось получить доступ к видеофайлу по этой ссылке. "
                    "Убедись, пожалуйста, что ссылка открыта для просмотра («Доступно всем, у кого есть ссылка»), "
                    "или отправь видеофайл напрямую в чат."
                )
                return

            duration = get_video_duration(temp_video_path)
            clean_caption = user_text.replace(cloud_video_url, "").strip()
            await process_video_audit(target_message, temp_video_path, duration, clean_caption, user_id, user_data, wait_msg=wait_msg, is_temp_file=True)
            return

        # Поиск ссылок в тексте сообщения
        urls = re.findall(r'(https?://[^\s]+)', user_text)
        
        if urls:
            url = urls[0]
            from bot.services.apify import apify_service
            from bot.services.web_reader import web_reader

            platform = apify_service.detect_platform(url)
            wait_msg = None
            
            if platform:
                # Социальная сеть — используем медленный Apify в фоне
                platform_names = {
                    "instagram": "Instagram",
                    "pinterest": "Pinterest",
                    "youtube": "YouTube",
                    "twitter": "Twitter/X",
                    "facebook": "Facebook",
                    "threads": "Threads"
                }
                platform_name = platform_names.get(platform, platform.capitalize())
                
                # Отправляем теплое сообщение-заглушку в стиле Элины
                wait_msg = await target_message.answer(
                    f"Я вижу ссылку на {platform_name}. Мне нужно немного времени (около минуты-двух), "
                    f"чтобы заглянуть туда, соприкоснуться с их творчеством и почувствовать ритм... "
                    f"Я сразу же поделюсь своими мыслями, как только всё рассмотрю. ☕️"
                )
                
                # Включаем индикатор "печатает" на время долгой работы в фоне
                stop_event = asyncio.Event()
                typing_task = asyncio.create_task(keep_typing(target_message.bot, target_message.chat.id, stop_event))
                
                try:
                    scraped_data = await apify_service.scrape(url)
                finally:
                    stop_event.set()
                    await typing_task
                    
                if not scraped_data or scraped_data.startswith("Ошибка"):
                    if wait_msg:
                        await wait_msg.edit_text(
                            "Знаешь, у меня возникли трудности при попытке заглянуть туда... "
                            "Возможно, профиль закрыт или ссылка ведёт в приватную зону. Попробуешь проверить её?"
                        )
                    else:
                        await target_message.answer("Не удалось получить доступ к этой странице. Проверь, пожалуйста, ссылку.")
                    return
                    
                enriched_user_text = f"{user_text}\n\n[Системный контекст: Данные профиля {platform_name} по ссылке {url}]:\n{scraped_data}"
            else:
                # Обычный сайт — читаем быстро напрямую
                await target_message.bot.send_chat_action(chat_id=target_message.chat.id, action="typing")
                
                scraped_data = await web_reader.read_url(url)
                if not scraped_data or scraped_data.startswith("Ошибка"):
                    await target_message.answer(
                        "Кажется, этот сайт защищен слишком надежно, или он временно недоступен. "
                        "Я не смогла прочитать его."
                    )
                    return
                    
                enriched_user_text = f"{user_text}\n\n[Системный контекст: Содержимое сайта по ссылке {url}]:\n{scraped_data}"

            # Добавляем обогащенное сообщение в историю
            await memory.add_message(user_id, 'user', enriched_user_text)

            # Особая системная инструкция для анализа сайтов и соцсетей
            analysis_instruction = (
                "\n\n[СИСТЕМНОЕ НАПРАВЛЕНИЕ]: Твой собеседник прислал ссылку для анализа. "
                "Дай развернутый, эстетичный и профессиональный анализ предоставленного контента. "
                "Если это конкурент или чужое творчество, оцени их стиль, визуальный ритм, цветовые решения, "
                "сильные стороны и концепцию с точки зрения философии 'Quiet Luxury' и Japandi. "
                "Отмечай интересные детали, которые могут вдохновить вас, но мягко указывай на визуальный шум или "
                "избыточность, если они есть. Твой тон должен быть поддерживающим, вдохновляющим и глубоким."
            )

            # Собираем контекст для LLM
            history = await memory.get_context_for_llm(user_id)
            user_profile = await memory.get_user_profile(user_id)
            elin_persona = await memory.get_elin_persona_text()
            lore_context = await memory.get_world_context(user_text)

            elin_persona_enriched = elin_persona + analysis_instruction
            is_admin = (user_id == config.admin_id)
            if is_admin:
                hindsight_mem = hindsight_bridge.recall(user_text, limit=3)
                lore_context = (lore_context or "") + f"\n\n[HINDSIGHT STUDIO MEMORY - EXCLUSIVE FOR VLADIMIR]:\n{hindsight_mem}\n"
            override_model = await db.get_setting(f"user_model_{user_id}", "google/gemini-4-argon") if (is_admin or user_data.get('sub_type') == 'premium') else None

            await target_message.bot.send_chat_action(chat_id=target_message.chat.id, action="typing")

            try:
                response = await llm.respond(
                    messages=history,
                    user_profile=user_profile,
                    elin_persona=elin_persona_enriched,
                    lore_context=lore_context,
                    is_admin=is_admin,
                    override_model=override_model
                )

                # Списываем кредиты за Brand Aesthetic Audit (50 кредитов)
                cost = await config.get_token_cost(action='audit')
                await db.spend_tokens(user_id, cost)

                # Сохраняем ответ в историю
                await memory.add_message(user_id, 'assistant', response)

                new_balance = (await db.get_user_data(user_id))['tokens']
                balance_info = f"\n\n<i>✦ Atelier Credits: {new_balance}</i>" if (user_data.get('sub_type') != 'admin' and user_id != config.admin_id) else ""

                if wait_msg:
                    try:
                        await wait_msg.delete()
                    except:
                        pass

                await send_long_message(target_message, response + balance_info, parse_mode="HTML")

                # Фоновое обновление фактов
                user_message_counters[user_id] = user_message_counters.get(user_id, 0) + 1
                if user_message_counters[user_id] % 5 == 1:
                    asyncio.create_task(extract_and_save_all_task(user_id))

            except Exception as e:
                if wait_msg:
                    try:
                        await wait_msg.delete()
                    except:
                        pass
                await target_message.answer('Я увидела всё, что там есть, но выразить это словами сейчас почему-то трудно... Попробуем еще раз?')
                print(f'LLM Web-Analysis Error: {e}')

        else:
            # Обычное текстовое сообщение без ссылок
            is_prompt_req = any(kw in user_text.lower() for kw in ['промпт', 'prompt', 'сценарий', 'scenario', 'раскадровк', 'scene', 'shot', 'veo', 'kling', 'video', 'ролик'])
            cost = await config.get_token_cost(action='prompt' if is_prompt_req else 'msg')
            
            # Проверяем баланс на требуемое действие
            user_data = await check_user_and_balance(user_id, target_message, cost=cost)
            if not user_data:
                return

            await target_message.bot.send_chat_action(chat_id=target_message.chat.id, action="typing")

            # Добавляем сообщение пользователя в историю
            await memory.add_message(user_id, 'user', user_text)

            # Получаем историю для контекста, профиль пользователя, образ Элин и лор-контекст
            history = await memory.get_context_for_llm(user_id)
            user_profile = await memory.get_user_profile(user_id)
            elin_persona = await memory.get_elin_persona_text()
            lore_context = await memory.get_world_context(user_text)

            is_admin = (user_id == config.admin_id)
            if is_admin:
                # Эксклюзивный доступ к синаптическому банку Hindsight только для Владимира
                hindsight_mem = hindsight_bridge.recall(user_text, limit=4)
                lore_context = (lore_context or "") + f"\n\n[HINDSIGHT STUDIO MEMORY - EXCLUSIVE FOR VLADIMIR]:\n{hindsight_mem}\n"
                
                # Фиксация директив Владимира из Telegram
                lower_t = user_text.lower()
                if any(w in lower_t for w in ["закон", "правило", "утвержда", "стандарт", "никогда", "всегда", "запомни", "паспорт", "тайн", "щит", "референс"]):
                    try:
                        hindsight_bridge.retain("vladimir", user_text)
                    except Exception:
                        pass

            try:
                override_model = await db.get_setting(f"user_model_{user_id}", "google/gemini-4-argon") if (is_admin or user_data.get('sub_type') == 'premium' or is_prompt_req) else None
                # Генерируем ответ
                response = await llm.respond(
                    messages=history,
                    user_profile=user_profile,
                    elin_persona=elin_persona,
                    lore_context=lore_context,
                    is_admin=is_admin,
                    override_model=override_model
                )

                # Списание Atelier Credits
                await db.spend_tokens(user_id, cost)

                # Добавляем ответ в историю
                await memory.add_message(user_id, 'assistant', response)

                # Подготовим инфо о балансе для футера
                new_balance = (await db.get_user_data(user_id))['tokens']
                balance_info = f"\n\n<i>✦ Atelier Credits: {new_balance}</i>" if (user_data.get('sub_type') != 'admin' and user_id != config.admin_id) else ""
                
                await send_long_message(target_message, response + balance_info, parse_mode="HTML")

                # Фоново извлекаем факты + черты образа (каждое 5-е сообщение)
                user_message_counters[user_id] = user_message_counters.get(user_id, 0) + 1
                if user_message_counters[user_id] % 5 == 1:
                    asyncio.create_task(extract_and_save_all_task(user_id))

            except Exception as e:
                await target_message.answer('Кажется, я на мгновение потеряла нить нашего разговора... Давай попробуем ещё раз?')
                print(f'LLM Error: {e}')