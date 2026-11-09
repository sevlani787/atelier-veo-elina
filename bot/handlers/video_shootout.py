"""
Atelier VEO — Video Shootout & Mandatory Re-roll Protocol (Закон пересъемки).
Модуль кураторского отбора серии черновых видео (Video Shootout 1 из N)
для черновых генераций 360p из Google Flow и бескомпромиссного ОТК Elina.
"""

import os
import asyncio
import tempfile
import logging
from typing import Optional

from aiogram.types import Message

from bot.config import config
from bot.services.llm import llm
from bot.services.memory import memory
from bot.services.hindsight_bridge import hindsight_bridge
from bot.services.database import db
from bot.utils import (
    send_long_message,
    extract_keyframes_from_video,
    get_video_duration,
    extract_audio_from_media,
)

logger = logging.getLogger(__name__)


async def process_video_shootout(
    target_message: Message,
    buffered_videos: list[Message],
    user_id: int,
    user_data: dict,
) -> None:
    """
    Кураторский сравнительный отбор серии видеодублей (Video Shootout 1 из N).
    Анализирует серию (обычно 4 варианта из Google Flow в разрешении 360p),
    извлекает раскадровку и звук из каждого дубля, проводит сравнительный аудит
    по критериям Quiet Luxury & Haute Parfumerie.

    Применяет «Закон пересъемки» (Mandatory Re-roll Rule):
    - Если хотя бы один вариант >= 8.5/10 и чист от грубых дефектов:
      объявляет ГРАНД-ПОБЕДИТЕЛЯ и выдает директивы для 4K апскейла.
    - Если ВСЕ варианты < 8.5/10 (или морфинг/мыло/артефакты):
      бракует всю серию [БРАК ВСЕЙ СЕРИИ — ПЕРЕСЪЕМКА] и выдает
      скорректированный 3-частный промпт (Prompt Doctor) для новой генерации.
    """
    from bot.handlers.messages import get_system_error_message, extract_and_save_all_task, user_message_counters

    is_admin = (user_id == config.admin_id)
    num_variants = len(buffered_videos)
    caption = next((m.caption for m in buffered_videos if m.caption), "").strip()

    wait_msg = await target_message.answer(
        f"🎬 <i>Принята серия из {num_variants} видеодублей на кураторский отбор (Video Shootout 1 из {num_variants}).\n"
        f"Анализирую раскадровку, стабильность оптики и звук всех вариантов...</i>",
        parse_mode="HTML"
    )

    temp_files = []
    variants_data = []

    try:
        max_bytes = config.max_video_size_mb * 1024 * 1024
        for idx, msg in enumerate(buffered_videos, start=1):
            vid = msg.video or msg.video_note or msg.document
            if not vid:
                continue

            if vid.file_size and vid.file_size > max_bytes:
                continue

            file = await msg.bot.get_file(vid.file_id)
            if file.file_path and os.path.exists(file.file_path):
                v_path = file.file_path
            else:
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
                    v_path = tmp_file.name
                temp_files.append(v_path)
                await msg.bot.download_file(file.file_path, v_path, timeout=300)

            dur = getattr(vid, "duration", 0) or 0
            if dur <= 0:
                dur = get_video_duration(v_path)

            # Извлекаем 3 ключевых кадра (старт ~10%, середина ~50%, финал ~90%)
            frames = await asyncio.to_thread(extract_keyframes_from_video, v_path, float(dur), 3)

            # Извлекаем аудиодорожку (PCM 16kHz WAV base64)
            audio_b64 = await asyncio.to_thread(extract_audio_from_media, v_path, min(float(dur or 30.0), 30.0))

            variants_data.append({
                "idx": idx,
                "duration": dur,
                "frames": frames,
                "audio_b64": audio_b64,
                "path": v_path,
            })

        if not variants_data:
            await wait_msg.edit_text("Не удалось извлечь кадры из присланных видеофайлов... Попробуйте отправить стандартные MP4 ролики.")
            return

        # Режиссерский бриф для мультимодальной оценки
        if is_admin:
            shootout_intro = (
                f"Ты — Элина, Главный Режиссер, Верховный Архитектор Промптов и Глава ОТК Atelier VEO.\n"
                f"Ты работаешь на флагманской мультимодальной нейросети Gemini 4 Argon.\n\n"
                f"Владимир прислал серию из {len(variants_data)} сгенерированных видеовариантов сцены (Google Flow 360p черновики) для сравнительного отбора (Video Shootout 1 из {len(variants_data)}).\n"
                f"Твоя задача — провести бескомпромиссный режиссерский аудит и выбрать ОДИН лучший дубль для апскейла в 4K Master, "
                f"ЛИБО забраковать всю серию целиком, если ни один вариант не соответствует стандартам Haute Parfumerie & Quiet Luxury.\n\n"
                f"Критерии бескомпромиссного ОТК VEO:\n"
                f"1. Геометрия флакона и физика стекла (Bottle Integrity & Physics) — отсутствие «плывущих» граней, морфинга стекла, деформаций колпачка или дна.\n"
                f"2. Инвариант чистоты оптики и этикетки (The Clean Flacon Invariant) — ровная плоскость под Identity Shield / цифровую шелкографию, отсутствие паразитных мутных пятен, AI-глюков и клякс.\n"
                f"3. Кинематографическая оптика и свет (Lighting & Optics) — благородная глубина резкости, каустика, преломление лучей (2700K / 5200K), органичное размытие движения (180° shutter angle), отсутствие стробоскопа.\n"
                f"4. Плавность динамики и отсутствие AI-галлюцинаций — естественное движение камеры (smooth dolly/orbit), отсутствие внезапных исчезновений или искривлений объектов.\n\n"
                f"🏆 ОБЯЗАТЕЛЬНЫЙ ЗАКОН ПЕРЕСЪЕМКИ (MANDATORY RE-ROLL RULE):\n"
                f"• Если хотя бы один вариант набрал 8.5/10 или выше и не имеет критических визуальных дефектов:\n"
                f"  Объяви: 🏆 **ГРАНД-ПОБЕДИТЕЛЬ: [Вариант №X] (Оценка: Y/10)**.\n"
                f"  Дай аргументированный вердикт, почему именно он превосходит остальные, укажи таймкоды лучших моментов и выдай директиву для 4K апскейла / монтажа.\n"
                f"• Если ВСЕ {len(variants_data)} вариантов имеют оценку ниже 8.5/10 (или страдают от плывущей геометрии, мыла, паразитного морфинга и артефактов):\n"
                f"  Ты ОБЯЗАНА категорически отклонить всю серию:\n"
                f"  ⛔ **[БРАК ВСЕЙ СЕРИИ — ПЕРЕСЪЕМКА]**\n"
                f"  Четко и профессионально укажи, почему каждый вариант (Вариант №1, Вариант №2, ...) провалил ОТК.\n"
                f"  Затем активируй режим **Prompt Doctor** и предоставь обновленный, выверенный 3-частный промпт для Google Flow:\n"
                f"  - 1. Камера и оптика (Camera Motion & Optics: фокусное расстояние, апертура, угол обтюратора 180°, траектория движения)\n"
                f"  - 2. Объект и геометрия (Subject & Bottle Physics: геометрия флакона, стекло, жидкость, каустика)\n"
                f"  - 3. Свет и атмосфера (Lighting & Quiet Luxury Ambiance: 2700K/5200K, chiaroscuro, студийная среда)\n"
                f"  - Отрицательные промпты (Negative Prompts: morphing, melting, floating artifacts, warped typography, unstable glass, strobing, 3D CGI plastic look).\n\n"
                f"Формат ответа:\n"
                f"• Экспресс-разбор каждого варианта (Вариант №1, Вариант №2, ...): оценка по 10-балльной шкале, сильные стороны и дефекты.\n"
                f"• ИТОГОВЫЙ ВЕРДИКТ: Либо 🏆 **ГРАНД-ПОБЕДИТЕЛЬ: [Вариант №X]**, либо ⛔ **[БРАК ВСЕЙ СЕРИИ — ПЕРЕСЪЕМКА]**.\n"
                f"• Директива: Рекомендация для апскейла в 4K (если выбран победитель) ИЛИ Готовый исправленный 3-частный промпт для Google Flow (при браке всей серии).\n\n"
                f"Комментарий Владимира к сцене: {caption or 'Выбери один лучший дубль для 4K апскейла или забракуй серию.'}"
            )
        else:
            shootout_intro = (
                f"Ты — Элина, Главный Креативный Директор и Режиссер Atelier VEO.\n"
                f"Резидент студии прислал серию из {len(variants_data)} вариантов видеосцены для кураторского отбора (Video Shootout 1 из {len(variants_data)}).\n\n"
                f"Твоя задача — по-деловому, высокоинтеллигентно и доброжелательно (в эстетике Quiet Luxury) провести сравнительный аудит раскадровки каждого дубля и выбрать ОДИН лучший вариант для чистового 4K-мастеринга.\n"
                f"Если же ни один из вариантов не соответствует высоким стандартам студии (критические искажения, плывущий логотип/форма), вежливо порекомендуй повторную генерацию и дай рекомендации по корректировке промпта (Prompt Doctor).\n\n"
                f"Критерии оценки:\n"
                f"1. Стабильность формы и геометрии объекта (отсутствие морфинга и размытия граней).\n"
                f"2. Кинематографический свет и цвет (Haute Parfumerie & Quiet Luxury).\n"
                f"3. Плавность динамики камеры и отсутствие артефактов генерации.\n\n"
                f"Формат ответа:\n"
                f"• Разбор каждого варианта (оценка и замечания).\n"
                f"• Итог: 🏆 **ЛУЧШИЙ ВАРИАНТ: [Вариант №X]** либо ⛔ **РЕКОМЕНДАЦИЯ К ПЕРЕСЪЕМКЕ**.\n"
                f"• Рекомендации по оптимизации генерации.\n\n"
                f"Комментарий резидента: {caption or 'Провести сравнительный аудит серии видеодублей.'}"
            )

        video_content = [{"type": "text", "text": shootout_intro}]

        for v in variants_data:
            v_idx = v["idx"]
            v_dur = v["duration"]
            video_content.append({"type": "text", "text": f"\n====================\nДУБЛЬ №{v_idx} (Длительность: {round(v_dur, 1)}с)\n===================="})
            for ts, b64_frame in v["frames"]:
                video_content.append({"type": "text", "text": f"[Дубль №{v_idx} — Кадр ~{ts}с]:"})
                video_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64_frame}"}
                })
            if v["audio_b64"]:
                video_content.append({"type": "text", "text": f"[Дубль №{v_idx} — Аудиодорожка]:"})
                video_content.append({
                    "type": "input_audio",
                    "input_audio": {"data": v["audio_b64"], "format": "wav"}
                })

        # Сохраняем в историю
        await memory.add_message(user_id, "user", video_content)

        # Собираем контекст для LLM
        history = await memory.get_context_for_llm(user_id)
        user_profile = await memory.get_user_profile(user_id)
        elin_persona = (await memory.get_elin_persona_text()) if is_admin else ""
        lore_context = await memory.get_world_context(caption)

        if is_admin:
            hindsight_mem = hindsight_bridge.recall(f"video shootout 1 of 4 flow 360p {caption}", limit=3)
            lore_context = (lore_context or "") + (
                f"\n\n[HINDSIGHT STUDIO MEMORY - EXCLUSIVE FOR VLADIMIR]:\n{hindsight_mem}\n"
            )

        override_model = await db.get_setting(f"user_model_{user_id}", "google/gemini-4-argon") if (is_admin or user_data.get('sub_type') == 'premium') else None

        await target_message.bot.send_chat_action(chat_id=target_message.chat.id, action="typing")

        response = await llm.generate(
            messages=history,
            user_profile=user_profile,
            elin_persona=elin_persona,
            lore_context=lore_context,
            is_admin=is_admin,
            override_model=override_model
        )

        # Списание кредитов (1 раз за всю серию как за Video QA)
        cost = await config.get_token_cost(action='qa')
        await db.spend_tokens(user_id, cost)

        # Сохраняем ответ в память
        await memory.add_message(user_id, "assistant", response)

        if is_admin:
            try:
                hindsight_bridge.retain("vladimir", f"Video Shootout {len(variants_data)} дублей: {caption}. Вердикт: {response[:150]}")
            except Exception:
                pass

        new_balance = (await db.get_user_data(user_id))['tokens']
        balance_info = f"\n\n<i>✦ Atelier Credits: {new_balance}</i>" if (user_data.get('sub_type') != 'admin' and user_id != config.admin_id) else ""

        if wait_msg:
            try:
                await wait_msg.delete()
            except Exception:
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
            except Exception:
                pass
        err_text = await get_system_error_message(user_id, target_message, 'video_analysis')
        await target_message.answer(err_text)
        logger.error(f"Video Shootout Error: {e}", exc_info=True)
    finally:
        for p in temp_files:
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass
