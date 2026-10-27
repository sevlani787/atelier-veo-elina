import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.config import config
from bot.services.database import db

logger = logging.getLogger(__name__)


async def get_client_display_info(bot: Bot, user_id: int) -> dict:
    """Извлечение имени, username и бренда клиента для отчетов продюсеру."""
    client_name = "Резидент"
    username_str = "—"
    profile_url = f"tg://user?id={user_id}"

    try:
        chat = await bot.get_chat(user_id)
        name_parts = [chat.first_name or "", chat.last_name or ""]
        full_name = " ".join(p for p in name_parts if p).strip()
        if full_name:
            client_name = full_name
        if chat.username:
            username_str = f"@{chat.username}"
            profile_url = f"https://t.me/{chat.username}"
    except Exception as e:
        logger.debug(f"Unable to fetch Telegram chat for {user_id}: {e}")

    # Извлекаем бренд из накопленных фактов
    brand_name = "—"
    try:
        facts = await db.get_facts(user_id)
        if isinstance(facts, dict):
            brand_name = (
                facts.get("brand")
                or facts.get("бренд")
                or facts.get("company")
                or facts.get("компания")
                or facts.get("project")
                or facts.get("проект")
                or "—"
            )
    except Exception as e:
        logger.debug(f"Unable to fetch facts for {user_id}: {e}")

    return {
        "client_name": client_name,
        "username_str": username_str,
        "profile_url": profile_url,
        "brand_name": brand_name,
    }


async def check_expiring_subscriptions(bot: Bot):
    """
    Проверка сроков действия резидентур:
    1. За 2 дня (48 часов) до окончания срока отправляет предупреждение Владимиру (Executive Producer).
    2. При наступлении момента истечения срока переводит пользователя в free,
       сохраняет 100% остатка кредитов и уведомляет обе стороны на языке клиента.
    """
    if not config.admin_id:
        return

    try:
        residents = await db.get_active_residents()
    except Exception as e:
        logger.error(f"Error fetching active residents: {e}")
        return

    for resident in residents:
        user_id = resident.get("user_id")
        expiry_str = resident.get("sub_expiry")
        tokens = resident.get("tokens", 0)

        # Пропускаем самого администратора
        if user_id == config.admin_id:
            continue

        if not expiry_str:
            continue

        try:
            clean_str = expiry_str.replace("Z", "+00:00")
            expiry_dt = datetime.fromisoformat(clean_str)
            now = datetime.now(expiry_dt.tzinfo) if expiry_dt.tzinfo else datetime.now()
            delta = expiry_dt - now
            date_key = expiry_dt.strftime("%Y%m%d")

            # -----------------------------------------------------------------
            # 1. ПРЕДУПРЕЖДЕНИЕ ЗА 2 ДНЯ (48 ЧАСОВ) ДО ОКОНЧАНИЯ СРОКА
            # -----------------------------------------------------------------
            if timedelta(0) < delta <= timedelta(days=2):
                warn_key = f"expiry_warned_2d_{user_id}_{date_key}"
                already_warned = await db.get_setting(warn_key)

                if not already_warned:
                    client_info = await get_client_display_info(bot, user_id)
                    hours_left = max(1, int(delta.total_seconds() // 3600))
                    days_left = round(delta.total_seconds() / 86400, 1)

                    text = (
                        "✦ <b>ATELIER VEO | КОНТРОЛЬ ПОДПИСКИ (2 ДНЯ ДО ИСТЕЧЕНИЯ)</b> ✦\n\n"
                        f"Владимир, у резидента закрытого клуба через <b>{hours_left} ч.</b> (~{days_left} дн.) "
                        "завершается расчетный месячный цикл:\n\n"
                        f"• <b>Клиент:</b> {client_info['client_name']} ({client_info['username_str']})\n"
                        f"• <b>Бренд / Проект:</b> {client_info['brand_name']}\n"
                        f"• <b>User ID:</b> <code>{user_id}</code>\n"
                        f"• <b>Истекает:</b> {expiry_dt.strftime('%d.%m.%Y в %H:%M')}\n"
                        f"• <b>Остаток кредитов:</b> <b>{tokens:,}</b> Atelier Credits\n"
                        "• <b>Активный режим:</b> Gemini 4 Argon\n\n"
                        "<i>Поскольку оплата членства принимается в ручном режиме, вы можете связаться "
                        "с клиентом для подтверждения продления или продлить членство в один клик:</i>"
                    )

                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="💎 Продлить на 1 мес (+1000 кр.)", callback_data=f"prolong_{user_id}_1"),
                            InlineKeyboardButton(text="💎 Продлить на 3 мес (+3000 кр.)", callback_data=f"prolong_{user_id}_3")
                        ],
                        [
                            InlineKeyboardButton(text="💬 Написать клиенту", url=client_info["profile_url"])
                        ]
                    ])

                    await bot.send_message(
                        chat_id=config.admin_id,
                        text=text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                    await db.set_setting(warn_key, "1")
                    logger.info(f"Sent 2-day expiration warning to admin for user {user_id}")

            # -----------------------------------------------------------------
            # 2. НАСТУПЛЕНИЕ МОМЕНТА ОКОНЧАНИЯ СРОКА (DELTAS <= 0)
            # -----------------------------------------------------------------
            elif delta <= timedelta(0):
                # Переводим статус в free и сбрасываем модель на Gemini 2.5 Flash
                await db.set_sub_type(user_id, "free")
                await db.set_setting(f"user_model_{user_id}", "google/gemini-2.5-flash")

                cycle_end_key = f"expiry_handled_{user_id}_{date_key}"
                already_handled = await db.get_setting(cycle_end_key)

                if not already_handled:
                    client_info = await get_client_display_info(bot, user_id)
                    user_lang = await db.get_setting(f"user_lang_{user_id}", "en")

                    # Уведомление клиенту на языке его общения с Элиной
                    if user_lang == "fr":
                        notice_client = (
                            "✦ <b>ATELIER VEO | NOTIFICATION DE RÉSIDENCE</b> ✦\n\n"
                            "Le cycle mensuel de votre résidence au Club est arrivé à son terme.\n\n"
                            f"L'intégralité de vos crédits restants (<b>{tokens:,} Atelier Credits</b>) est précieusement conservée — "
                            "vous pouvez continuer à créer avec Elina en <b>Mode Conversationnel (Gemini 2.5 Flash)</b>.\n\n"
                            "Pour réactiver le moteur directorial d'élite <b>Gemini 4 Argon</b> avec physique optique cinématique à 5 composants "
                            "et recevoir votre nouvelle dotation mensuelle de crédits, vous pouvez renouveler votre adhésion à tout moment."
                        )
                        kb_client = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="💎 Renouveler la Résidence (Gemini 4 Argon)", url="https://veocreative.agency/club")],
                            [InlineKeyboardButton(text="🏛 Producteur Exécutif", url="https://t.me/veocreative")]
                        ])
                    elif user_lang == "it":
                        notice_client = (
                            "✦ <b>ATELIER VEO | NOTIFICA DI RESIDENZA</b> ✦\n\n"
                            "Il ciclo mensile della vostra residenza al Club è giunto al termine.\n\n"
                            f"L'intero saldo rimanente (<b>{tokens:,} Atelier Credits</b>) è completamente preservato — "
                            "potete continuare a creare con Elina in <b>Modalità Conversazionale (Gemini 2.5 Flash)</b>.\n\n"
                            "Per riattivare il motore registico d'élite <b>Gemini 4 Argon</b> con fisica ottica cinematografica a 5 componenti "
                            "e ricevere la nuova dotazione mensile di crediti, potete rinnovare la residenza in qualsiasi momento."
                        )
                        kb_client = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="💎 Rinnova la Residenza (Gemini 4 Argon)", url="https://veocreative.agency/club")],
                            [InlineKeyboardButton(text="🏛 Produttore Esecutivo", url="https://t.me/veocreative")]
                        ])
                    elif user_lang == "ru":
                        notice_client = (
                            "✦ <b>ATELIER VEO | УВЕДОМЛЕНИЕ О РЕЖИМЕ РАБОТЫ</b> ✦\n\n"
                            "Срок вашего месячного клубного цикла подошел к концу.\n\n"
                            f"Все ваши оставшиеся кредиты (<b>{tokens:,} Atelier Credits</b>) полностью сохранены за вами — "
                            "вы можете продолжать использовать их в <b>базовом режиме (Gemini 2.5 Flash)</b>.\n\n"
                            "Для возврата флагманского режиссерского разума <b>Gemini 4 Argon</b> с 5-компонентной оптикой "
                            "и начисления нового пула кредитов вы можете продлить резидентуру в любой удобный момент."
                        )
                        kb_client = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="💎 Продлить резидентуру (Gemini 4 Argon)", url="https://veocreative.agency/club")],
                            [InlineKeyboardButton(text="🏛 Исполнительный продюсер", url="https://t.me/veocreative")]
                        ])
                    else:
                        notice_client = (
                            "✦ <b>ATELIER VEO | RESIDENCY CYCLE NOTICE</b> ✦\n\n"
                            "Your monthly residency cycle has concluded.\n\n"
                            f"All your remaining balance (<b>{tokens:,} Atelier Credits</b>) is fully preserved — "
                            "you may continue co-creating with Elina in <b>Conversational Mode (Gemini 2.5 Flash)</b>.\n\n"
                            "To reactivate the flagship directorial engine <b>Gemini 4 Argon</b> with 5-component cinematic optics "
                            "and receive your fresh production credit pool, you may renew your residency at any time."
                        )
                        kb_client = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="💎 Renew Residency (Gemini 4 Argon)", url="https://veocreative.agency/club")],
                            [InlineKeyboardButton(text="🏛 Executive Producer", url="https://t.me/veocreative")]
                        ])

                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=notice_client,
                            reply_markup=kb_client,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to deliver expiration notice to client {user_id}: {e}")

                    # Уведомление Владимиру о переводе в free
                    text_admin = (
                        "✦ <b>ATELIER VEO | КЛУБНЫЙ ЦИКЛ ЗАВЕРШЕН</b> ✦\n\n"
                        "Владимир, расчетный цикл резидента подошел к концу:\n\n"
                        f"• <b>Клиент:</b> {client_info['client_name']} ({client_info['username_str']})\n"
                        f"• <b>Бренд / Проект:</b> {client_info['brand_name']}\n"
                        f"• <b>User ID:</b> <code>{user_id}</code>\n"
                        f"• <b>Сохраненный остаток:</b> <b>{tokens:,}</b> Atelier Credits\n"
                        "• <b>Текущий режим:</b> Gemini 2.5 Flash (Базовый)\n\n"
                        "<i>Клиент переведен в базовый режим с сохранением 100% остатка кредитов. "
                        "Для возврата Gemini 4 Argon и начисления новых кредитов вы можете продлить членство:</i>"
                    )

                    kb_admin = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="💎 Активировать на 1 мес (+1000 кр.)", callback_data=f"prolong_{user_id}_1"),
                            InlineKeyboardButton(text="💎 Активировать на 3 мес (+3000 кр.)", callback_data=f"prolong_{user_id}_3")
                        ],
                        [
                            InlineKeyboardButton(text="💬 Написать клиенту", url=client_info["profile_url"])
                        ]
                    ])

                    await bot.send_message(
                        chat_id=config.admin_id,
                        text=text_admin,
                        reply_markup=kb_admin,
                        parse_mode="HTML"
                    )
                    await db.set_setting(cycle_end_key, "1")
                    logger.info(f"Processed cycle completion for resident {user_id}")

        except Exception as e:
            logger.error(f"Error checking sub_expiry for resident {user_id}: {e}")


async def subscription_watchdog(bot: Bot):
    """
    Фоновый страж подписок: проверяет сроки каждые 30 минут,
    гарантируя своевременное уведомление продюсера за 2 дня и корректную смену циклов.
    """
    logger.info("Subscription watchdog started (checking every 30 minutes).")
    while True:
        try:
            await check_expiring_subscriptions(bot)
        except asyncio.CancelledError:
            logger.info("Subscription watchdog stopped.")
            break
        except Exception as e:
            logger.error(f"Unexpected error in subscription watchdog loop: {e}")

        try:
            await asyncio.sleep(1800)  # 30 минут
        except asyncio.CancelledError:
            break
