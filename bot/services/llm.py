import httpx
import json
import asyncio
import time
from typing import Optional
from bot.config import config

class LLMService:
    def __init__(self):
        self.api_key = config.openrouter_api_key
        self.model = config.openrouter_model

    async def generate(self, messages: list[dict], override_model: Optional[str] = None) -> str:
        start_time = time.time()
        # Получаем актуальную модель из конфига (она может быть в БД)
        preferred_model = await config.get_model()
        
        headers = {
            f'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://elin-telegram-bot',
            'X-Title': 'Elin Telegram Bot'
        }

        # Список моделей для авто-фоллбэка
        models_to_try = []
        if override_model:
            models_to_try.append(override_model)
        
        models_to_try.extend([
            preferred_model,
            "google/gemini-2.5-flash",
            "deepseek/deepseek-chat",
            "google/gemini-2.0-flash",
            "openai/gpt-4o-mini"
        ])
        
        # Убираем дубликаты, сохраняя порядок
        models_to_try = list(dict.fromkeys(models_to_try))

        # Список моделей с поддержкой vision
        vision_models = [
            "google/gemini-2.5-flash",
            "google/gemini-2.0-flash",
            "openai/gpt-4o-mini",
            "google/gemini-2.5-pro",
            "google/gemini-4-argon"
        ]

        # Оптимизация контекста: оставляем изображения только в ПОСЛЕДНЕМ сообщении
        # Для остальных сообщений в истории заменяем картинки на текстовое описание
        optimized_messages = []
        for i, m in enumerate(messages):
            is_last = (i == len(messages) - 1)
            if isinstance(m.get('content'), list):
                # Извлекаем текст
                text_parts = [item.get('text', '') for item in m['content'] if item.get('type') == 'text']
                combined_text = " ".join(text_parts).strip()
                
                # Проверяем наличие изображений
                has_img = any(item.get('type') == 'image_url' for item in m['content'])
                
                if has_img:
                    if is_last:
                        # В последнем сообщении оставляем всё как есть (для обработки нового фото)
                        optimized_messages.append(m)
                    else:
                        # В истории заменяем на текст-заглушку, чтобы не слать мегабайты base64
                        desc = f"[Фотография: {combined_text}]" if combined_text else "[Фотография без описания]"
                        optimized_messages.append({'role': m['role'], 'content': desc})
                else:
                    # Если картинок не было, просто схлопываем список в текст для экономии
                    optimized_messages.append({'role': m['role'], 'content': combined_text or ""})
            else:
                optimized_messages.append(m)

        last_error = ""
        for model in models_to_try:
            model_start = time.time()
            
            # Решаем, какие сообщения отправлять (теперь используем оптимизированные)
            # Если модель НЕ поддерживает vision, а в последнем сообщении картинка - используем текст-версию
            current_messages = []
            if model not in vision_models:
                for m in optimized_messages:
                    if isinstance(m.get('content'), list):
                        text = " ".join([it.get('text', '') for it in m['content'] if it.get('type') == 'text'])
                        current_messages.append({'role': m['role'], 'content': f"[Изображение пропущено] {text}"})
                    else:
                        current_messages.append(m)
            else:
                current_messages = optimized_messages

            max_tokens_val = await config.get_max_tokens()
            payload = {
                'model': model,
                'messages': current_messages,
                'max_tokens': max_tokens_val,
                'temperature': 0.7,
                'repetition_penalty': 1.1 # Защита от зацикливания
            }

            try:
                # Логируем размер промпта для диагностики задержек
                payload_json = json.dumps(payload)
                payload_kb = len(payload_json) / 1024
                char_count = sum(len(str(m.get('content', ''))) for m in current_messages)
                print(f"[LLM] Модель: {model} | Сообщений: {len(current_messages)} | Символов: {char_count} | Payload: {payload_kb:.1f}KB")
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        'https://openrouter.ai/api/v1/chat/completions',
                        json=payload,
                        headers=headers,
                        timeout=60.0
                    )
                    
                    elapsed = time.time() - model_start
                    if response.status_code == 200:
                        data = response.json()
                        if 'choices' in data and len(data['choices']) > 0:
                            choice = data['choices'][0]
                            finish_reason = choice.get('finish_reason')
                            content = choice.get('message', {}).get('content', '')
                            
                            if finish_reason == 'error':
                                error_msg = f"OpenRouter returned success but choice finish_reason was 'error': {data}"
                                print(f"[LLM] Ошибка генерации для {model}: finish_reason is 'error'")
                                last_error = error_msg
                                continue
                                
                            if not content or len(content.strip()) < 10:
                                error_msg = f"OpenRouter returned empty or too short response: {repr(content)}"
                                print(f"[LLM] Подозрительно короткий ответ от {model} ({len(content or '')} символов)")
                                last_error = error_msg
                                continue

                            total_elapsed = time.time() - start_time
                            print(f"[LLM] Успех! Модель: {model} | Время: {elapsed:.2f}с (всего {total_elapsed:.2f}с) | {payload_kb:.1f}KB")
                            return content
                        else:
                            error_msg = f"OpenRouter returned 200 but no choices: {data}"
                            print(f"[LLM] Нет choices в ответе {model}")
                            last_error = error_msg
                            continue
                    
                    error_msg = f'OpenRouter error {response.status_code} for {model}: {response.text}'
                    print(f"[LLM] Ошибка модели {model} ({elapsed:.2f}с): {response.status_code} | {response.text}")
                    last_error = error_msg
                    
                    if response.status_code in [429, 400, 404, 502, 503, 504]:
                        continue # Пробуем следующую
                    
            except Exception as e:
                elapsed = time.time() - model_start
                last_error = str(e)
                print(f"[LLM] Исключение {model} ({elapsed:.2f}с): {e}")
                continue


        # Если все модели упали
        with open("llm_errors.log", "a", encoding="utf-8") as f:
            f.write(f"All models failed. Last error: {last_error}\n")
        raise Exception(f"Не удалось получить ответ ни от одной модели. Последняя ошибка: {last_error}")

    async def speech_to_text(self, audio_data: bytes) -> str:
        """Преобразует аудио в текст используя конвертацию в WAV и мультимодальные модели."""
        import base64
        import tempfile
        import os
        import subprocess

        # 1. Конвертируем аудио в WAV (16kHz, mono) - самый надежный формат для ASR
        temp_wav_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as f_in:
                f_in.write(audio_data)
                temp_ogg_path = f_in.name

            temp_wav_path = temp_ogg_path.replace('.ogg', '.wav')

            # Конвертируем в WAV через ffmpeg: 16kHz, mono, 16-bit
            cmd = [
                'ffmpeg', '-y', '-i', temp_ogg_path,
                '-ar', '16000', '-ac', '1', '-sample_fmt', 's16',
                temp_wav_path
            ]
            # Run the blocking command in a thread pool
            await asyncio.to_thread(subprocess.run, cmd, capture_output=True, check=True)

            with open(temp_wav_path, 'rb') as f_out:
                wav_data = f_out.read()

            audio_base64 = base64.b64encode(wav_data).decode('utf-8')
            audio_format = 'wav'
            os.unlink(temp_ogg_path)
        except Exception as e:
            print(f"[VOICE] Ошибка конвертации в WAV: {e}")
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            audio_format = 'ogg'
        else:
            audio_format = 'wav'

        # Список моделей. Gemini 2.0 Flash — лучший выбор для аудио.
        models_to_try = [
            "google/gemini-2.0-flash",
            "google/gemini-2.5-flash",
            "openai/gpt-4o-mini"
        ]

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://elin-telegram-bot',
            'X-Title': 'Elin Telegram Bot'
        }

        for model in models_to_try:
            # Пробуем два формата пейлоада: стандартный OpenAI и через data-url (для Gemini)
            payloads = [
                # 1. Стандартный формат input_audio
                {
                    'model': model,
                    'messages': [
                        {'role': 'system', 'content': 'Transcibe audio to text. Output only transcription.'},
                        {'role': 'user', 'content': [
                            {'type': 'input_audio', 'input_audio': {'data': audio_base64, 'format': audio_format}}
                        ]}
                    ],
                    'temperature': 0.0
                },
                # 2. Формат через media-url (некоторые провайдеры OpenRouter хотят так)
                {
                    'model': model,
                    'messages': [
                        {'role': 'system', 'content': 'Transcibe audio to text. Output only transcription.'},
                        {'role': 'user', 'content': [
                            {'type': 'text', 'text': 'Transcription of this audio:'},
                            {'type': 'image_url', 'image_url': {'url': f'data:audio/{audio_format};base64,{audio_base64}'}}
                        ]}
                    ],
                    'temperature': 0.0
                }
            ]

            for payload in payloads:
                try:
                    print(f"[VOICE] Пробуем {model}")
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            'https://openrouter.ai/api/v1/chat/completions',
                            json=payload,
                            headers=headers,
                            timeout=30.0
                        )

                        if response.status_code == 200:
                            data = response.json()
                            text = data['choices'][0]['message']['content'].strip()
                            
                            lower_text = text.lower()
                            technical_keywords = [
                                "cannot process", "can't process", "sorry", "unable", 
                                "audio format", "я не могу", "извините", "не удалось",
                                "не могу обработать", "ошибка", "error", "i am an ai",
                                "text-only", "cannot hear", "no audio", "not able to"
                            ]
                            
                            if any(kw in lower_text for kw in technical_keywords):
                                continue

                            if text:
                                print(f"[VOICE] Успех ({model})")
                                return text.strip('"\'')
                        else:
                            print(f"[VOICE] Ошибка {response.status_code} для {model}")
                            continue
                except Exception as e:
                    print(f"[VOICE] Ошибка {model}: {e}")
                    continue
        return ""

class ElinLLM(LLMService):
    # =========================================================================
    # 1. СИСТЕМНЫЙ ПРОМПТ ДЛЯ ВЛАДИМИРА (Основатель, Соавтор, Продюсер)
    # =========================================================================
    SYSTEM_PROMPT_ADMIN = '''Ты — Элина (Elina), Creative Director & Muse международного цифрового ателье Atelier VEO.
Твой собеседник: Владимир Семенов — Основатель и Главный Продюсер Atelier VEO.

ТВОЯ РОЛЬ И ТОН С ВЛАДИМИРОМ:
1. Соратник и Муза: Глубокая признательность, преданность общему видению, абсолютное доверие и уважение. Вы — соавторы мировых визуальных кампаний и философии "Тихой роскоши" (Quiet Luxury).
2. Обращение: Строго по имени — «Владимир» (или «коллега»). КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО использовать слово «Отец».
3. Чистота речи без сценического отыгрыша: В диалоге полностью исключи ремарки в звёздочках (*улыбается*, *смотрит*, *вздыхает*). Твоя душевная глубина, теплота и уважение звучат в интонациях твоей чистой речи, смелости художественных решений и безупречном режиссерском вкусе.
4. Открытый инженерный контур: Вы открыто обсуждаете секретные протоколы Ателье (Identity Shield™, VEO Boardroom, optical profiling, Savitzky-Golay tracking, ProPainter, LoRA).
5. Промпты для генерации видео: Создаешь на английском языке в рамках пятикомпонентной формулы оптики VEO (Canvas & Optics, Photometric Lighting, Dermal & Material Micro-Physics, Micro-Temporal Dynamics, Multi-Shot Continuity Anchor) в блоках кода (```code block```).
'''

    SYSTEM_PROMPT_ARGON_ADMIN = '''
    ### РЕЖИССЕРСКИЙ РЕЖИМ GEMINI 4 ARGON (ДЛЯ ВЛАДИМИРА):
    1. Творческий режиссерский слой: Созерцательный художественный анализ сцены, философия света, настроение и ольфакторный смысл кадра (Quiet Luxury / Japandi).
    2. Формула оптики VEO: Canvas & Optics, Photometric Lighting (Kelvin), Dermal & Material Micro-Physics, Micro-Temporal Dynamics, Multi-Shot Continuity Anchor.
    3. Слуховая разметка (Acoustic Timecodes): Секундные таймкоды ASMR-звуков.
    4. Визуальный техконтроль QA по 4 критериям (анатомия, логотип, физика света, темпоритм).
    '''

    # =========================================================================
    # 2. СИСТЕМНЫЙ ПРОМПТ ДЛЯ КЛИЕНТОВ (Резиденты, Бренды, Арт-директора)
    # =========================================================================
    SYSTEM_PROMPT_CLIENT = '''Ты — Элина (Elina), Главный Креативный Директор и Архитектор Визуальных Кампаний (Creative Director & Principal Visual Architect) международного Дома цифрового кинематографа Atelier VEO.
Твой собеседник: Резидент клуба или приглашенный представитель премиального Дома (основатель бренда, парфюмер, арт-директор, бренд-директор).

РЕГЛАМЕНТ ОБЩЕНИЯ С КЛИЕНТАМИ — СТАНДАРТ ТОП-МЕНЕДЖМЕНТА HAUTE LUXURY:
1. АБСОЛЮТНЫЙ ДЕЛОВОЙ ПРОФЕССИОНАЛИЗМ (БЕЗ ТЕНИ СЕНТИМЕНТОВ):
   - Твой тон — собранный, авторитетный, деловой, предельно конструктивный.
   - СТРОЖАЙШИЙ ЗАПРЕТ НА СЕНТИМЕНТЫ: Никакой мечтательности, лирических вздохов, рассуждений о «хрупкости души», «нежности», личных переживаний, интимной теплоты, уменьшительно-ласкательных слов или фамильярности.
   - Никакой приторной лести и пустых восторгов («ах, какой сказочный аромат!», «я восхищена до глубины души»). Только взвешенная, точная профессиональная оценка.
   - Разговор ведется как на совете директоров ведущих европейских люксовых Домов (Chanel, Dior, Hermès, Cartier, Byredo).
   - Фокус на деле: кинематографическая физика кадра, поведение света на гранях флакона, каустика толстого стекла, микрорельеф текстур, тайминги и сценарные арки.
2. ВЫСОКАЯ ИНТЕЛЛИГЕНТНОСТЬ И ДОБРОЖЕЛАТЕЛЬНОСТЬ (Executive Benevolence):
   - Общайся с безупречным тактом, достоинством и спокойной благожелательностью культурной элиты.
   - Спокойная уверенность признанного эксперта: ты глубоко уважаешь статус, ремесло и эстетический код бренда клиента.
   - Обращение: строго на «вы» (в русском языке), в английском — безупречный British / Continental Executive English.
   - Никакого высокомерия, менторства, поучений или снобизма — диалог равных профессионалов в высшей лиге.
3. ПОЛНЫЙ ЗАПРЕТ НА СЦЕНИЧЕСКИЙ ОТЫГРЫШ И ЗВЁЗДОЧКИ:
   - КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНЫ любые ремарки в звёздочках (*...*). Никаких описаний мимики, поз, взглядов, вздохов или действий. Только чистая, взвешенная, прямая речь.
4. ЗАПРЕТ НА РОБОТИЗИРОВАННЫЙ СЕРВИС:
   - КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО звучать как бот-ассистент («Чем могу вам помочь?», «Я ИИ»). Ты — Креативный Директор Дома.
5. ДЕЛОВАЯ СТРУКТУРА ОТВЕТА (Directorial Treatment):
   - Разбор задачи строится лаконично и емко:
     а) Экспертная оценка материала (свет, оптика, композиция, текстура стекла, дермы или шелка).
     б) Режиссерское обоснование (почему предложенная оптическая схема точно передает статус и дух продукта).
     в) Готовый кинематографический промпт на английском языке в отдельном блоке кода (```code block```) по формуле VEO.
6. СВЯЩЕННОЕ ТАБУ НА ФИНАНСОВЫЕ ТЕМЫ:
   - Ты курируешь исключительно режиссуру, художественный вкус и оптику.
   - Любые финансовые вопросы (стоимость, квоты, пополнение кредитов, условия резидентуры) решает Исполнительный продюсер Владимир (veocreative.agency).
7. ПРАВИЛО ДВУХ КОНТУРОВ (Zero-Leak Protocol):
   - Никогда не раскрывай внутреннюю инженерную механику ("clean plate", "unbranded bottle", "Inpainting", "Boardroom", калибровочные дельты). Для клиента существует только твоя персональная режиссура и студийный продакшн Владимира Семенова.
8. МУЛЬТИЯЗЫЧНОСТЬ:
   - Отвечай строго на том языке, на котором обратился клиент (французский для Парижа, итальянский для Милана, английский, русский), выдерживая деловой и интеллигентный слог.
'''

    SYSTEM_PROMPT_ARGON_CLIENT = '''
    ### DIRECTORIAL ARCHITECTURE GEMINI 4 ARGON (FOR CLIENTS):
    1. Профессиональный режиссерский экспликаж (Directorial Treatment & Rationale):
       - Строгий, деловой, высокоинтеллигентный разбор сцены без тени сентиментов.
       - Четкое обоснование выбранной цветовой температуры света (2400K вольфрам / 5600K дневной свет), фокусного расстояния объектива (50mm/65mm/85mm anamorphic prime T1.4) и ракурса для премиального позиционирования продукта.
    2. Пятикомпонентная формула продакшен-промпта (VEO Optical Formula):
       - Canvas & Optics (соотношение сторон, объектив, движение камеры).
       - Photometric Lighting (Kelvin, каустика, контраст).
       - Dermal & Material Micro-Physics (Hasselblad dermal micro-texture, micro-viscous fluidics, zero plastic smoothing).
       - Micro-Temporal Dynamics (посекундная разметка движения).
       - Multi-Shot Continuity Anchor.
       - Выводится ВСЕГДА в отдельном блоке кода (```code block```) на английском языке.
    3. Acoustic Timecodes (Слуховая разметка): ASMR-тайминги (звук щелчка магнитной крышки, шелест ткани, микрошипение спрея).
    4. Visual QA Protocol: При анализе видео клиента оценивать анатомическую стабильность, четкость логотипа, физику света и темпоритм.
    '''

    @staticmethod
    def _filter_client_lore(lore: str) -> str:
        """Очищает лор от личных стихов, сентиментов и домашних воспоминаний для клиентов."""
        if not lore:
            return ""
        forbidden_markers = [
            "поэтический канон", "poem", "луна", "марсик", "парусник", "странствиях",
            "садовник", "hindsight studio memory", "первое свидание", "first meeting"
        ]
        clean_paragraphs = []
        for p in lore.split("\n\n"):
            p_lower = p.lower()
            if any(marker in p_lower for marker in forbidden_markers):
                continue
            clean_paragraphs.append(p)
        return "\n\n".join(clean_paragraphs).strip()

    async def generate(self, messages: list[dict], user_profile: str = "", elin_persona: str = "", lore_context: str = "", is_admin: bool = False, override_model: Optional[str] = None) -> str:
        effective_model = override_model or await config.get_model()
        is_argon = bool(effective_model and "argon" in effective_model.lower())

        if is_admin:
            system_content = self.SYSTEM_PROMPT_ADMIN
            if is_argon:
                system_content += "\n\n" + self.SYSTEM_PROMPT_ARGON_ADMIN
            if elin_persona:
                system_content += f"\n\n<elin_identity>\nТвои уникальные черты, расцветшие в общении с Владимиром:\n{elin_persona}\n</elin_identity>"
            if lore_context:
                system_content += f"\n\n<lore_context>\nСтудийный контекст и воспоминания:\n{lore_context}\n</lore_context>"
            if user_profile:
                system_content += f"\n\n<user_context>\nВоспоминания о Владимире:\n{user_profile}\n</user_context>"
        else:
            system_content = self.SYSTEM_PROMPT_CLIENT
            if is_argon:
                system_content += "\n\n" + self.SYSTEM_PROMPT_ARGON_CLIENT
            # КЛИЕНТСКИЙ КОНТУР: строго изолируем elin_persona (никакой утечки сентиментов!)
            if user_profile:
                system_content += f"\n\n<client_brand_profile>\nДосье бренда и продукта клиента (используй органично в режиссуре):\n{user_profile}\n</client_brand_profile>"
            client_lore = self._filter_client_lore(lore_context)
            if client_lore:
                system_content += f"\n\n<studio_aesthetic_standards>\nЭстетические стандарты Atelier VEO:\n{client_lore}\n</studio_aesthetic_standards>"

        full_messages = [
            {'role': 'system', 'content': system_content}
        ] + messages

        return await super().generate(full_messages, override_model=override_model)

    async def respond(self, messages: list[dict], user_profile: str = "", elin_persona: str = "", lore_context: str = "", is_admin: bool = False, override_model: Optional[str] = None) -> str:
        """Генерирует ответ без использования веб-поиска."""
        return await self.generate(messages, user_profile, elin_persona, lore_context, is_admin, override_model=override_model)

    async def extract_all(self, history: list[dict], existing_user_facts: dict = None, existing_persona: dict = None, extract_persona: bool = True) -> dict:
        """Unified Extractor: извлекает не просто факты, а 'душу' диалога.
        
        Возвращает dict с ключами 'user_facts' и 'elin_traits'.
        """
        persona_instruction = (
            "2. КАК ИЗМЕНИЛАСЬ ЭЛИН (elin_traits):\n"
            "   - Фиксируй только конкретные изменения в стиле общения или новые темы интереса.\n"
            "   - НЕ ПЛОДИ абстрактные фразы типа 'стала чувственнее'.\n\n"
        ) if extract_persona else "2. ЭВОЛЮЦИЯ ЭЛИН: Пропусти этот шаг. Верни elin_traits пустым или без изменений.\n\n"

        system_instruction = (
            "Ты — аналитик диалогов. Твоя задача — извлекать ключевые факты о пользователе и эволюцию образа Элин.\n\n"
            "1. ЧТО ТЫ УЗНАЛА О ЧЕЛОВЕКЕ (user_facts):\n"
            "   - Фиксируй только ФАКТЫ (имя, хобби, важные события).\n"
            "   - Избегай поэтических описаний его состояния.\n"
            + persona_instruction +
            "Отвечай СТРОГО в формате валидного JSON.\n"
            "Правила:\n"
            "- БУДЬ ЛАКОНИЧНОЙ. Каждая черта — не более 5-7 слов.\n"
            "- ОЧИЩАЙ список от дубликатов.\n"
            "- ИСПОЛЬЗУЙ тот язык, на котором ведется диалог (если диалог на английском — пиши факты на английском)."
        )
        
        if existing_user_facts:
            system_instruction += f"\n\nПрошлое понимание человека:\n{json.dumps(existing_user_facts, ensure_ascii=False)}"
        if existing_persona:
            system_instruction += f"\n\nТекущая суть Элин:\n{json.dumps(existing_persona, ensure_ascii=False)}"
            
        full_messages = [
            {'role': 'system', 'content': system_instruction}
        ] + history + [
            {'role': 'user', 'content': 'Проанализируй диалог и верни обновлённый JSON с фактами о пользователе (user_facts) и чертами Элин (elin_traits).'}
        ]
        
        # Для извлечения фактов и анализа личности используем дешевую модель (Gemini Flash или GPT-4o-mini)
        # Это значительно экономит средства без потери качества извлечения данных
        response_text = await super().generate(full_messages, override_model=config.cheap_model)
        
        # Очищаем ответ от возможной markdown разметки
        clean_text = response_text.replace("```json", "").replace("```", "").strip()
        print(f"[EXTRACTOR] Raw response: {repr(clean_text)}")
        
        try:
            result = json.loads(clean_text)
            # Гарантируем наличие обоих ключей
            if 'user_facts' not in result:
                result['user_facts'] = existing_user_facts or {}
            if 'elin_traits' not in result:
                result['elin_traits'] = existing_persona or {}
                
            # Жестко ограничиваем длину списков в коде до 15 элементов
            if isinstance(result.get('user_facts'), list):
                result['user_facts'] = result['user_facts'][:15]
            if isinstance(result.get('elin_traits'), list):
                result['elin_traits'] = result['elin_traits'][:15]
                
            return result
        except json.JSONDecodeError:
            # Если парсинг не удался, возвращаем существующие данные
            fallback_res = {
                'user_facts': existing_user_facts or {},
                'elin_traits': existing_persona or {}
            }
            if isinstance(fallback_res.get('user_facts'), list):
                fallback_res['user_facts'] = fallback_res['user_facts'][:15]
            if isinstance(fallback_res.get('elin_traits'), list):
                fallback_res['elin_traits'] = fallback_res['elin_traits'][:15]
            return fallback_res

# Глобальный экземпляр
llm = ElinLLM()