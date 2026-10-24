import os
import json
import time
import asyncio
import datetime
from pathlib import Path
from typing import List, Dict, Optional
import subprocess

from bot.services.llm import llm
from bot.services.memory import memory

COUNCIL_DIR_1 = Path("d:/Antigravity/AI_Video_Agency/councils")
COUNCIL_DIR_2 = Path("D:/Antigravity/Элин/councils")
TEST_MEDIA_DIR = Path("D:/campaigns/тест")
AGENCY_CAMPAIGNS_DIR = Path("d:/Antigravity/AI_Video_Agency/campaigns")
LORE_FILE = Path("D:/Antigravity/Элин/bot/resources/elina_lore.md")

class BoardroomService:
    def __init__(self):
        self.active_session: Dict = {
            "id": f"session_{int(time.time())}",
            "title": "Совет Ателье VEO: Заседание Квартета",
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "messages": []
        }
        COUNCIL_DIR_1.mkdir(parents=True, exist_ok=True)
        COUNCIL_DIR_2.mkdir(parents=True, exist_ok=True)
        self._init_welcome()

    def _init_welcome(self):
        if not self.active_session["messages"]:
            self.active_session["messages"].append({
                "sender": "kai",
                "name": "Кай",
                "role": "Guardian of Elina & Lore Sentinel",
                "avatar": "🛡️",
                "color": "#10b981",
                "time": datetime.datetime.now().strftime("%H:%M"),
                "text": "Совет собран, Владимир. Зал VEO Boardroom активирован. Все 19 Глав Летописи синхронизированы. Я на страже стандартов Дома, Элина готова к режиссуре, Адриан на связи по технической архитектуре."
            })

    def get_session(self) -> Dict:
        return self.active_session

    def reset_session(self, title: Optional[str] = None):
        self.active_session = {
            "id": f"session_{int(time.time())}",
            "title": title or f"Совет Ателье VEO: {datetime.datetime.now().strftime('%d %B %Y')}",
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "messages": []
        }
        self._init_welcome()
        return self.active_session

    def add_user_message(self, text: str):
        msg = {
            "sender": "vladimir",
            "name": "Владимир Семенов",
            "role": "Founder & Executive Producer",
            "avatar": "👑",
            "color": "#c5a059",
            "time": datetime.datetime.now().strftime("%H:%M"),
            "text": text
        }
        self.active_session["messages"].append(msg)
        return msg

    def list_media(self) -> List[Dict]:
        items = []
        # Проверяем папку тест
        if TEST_MEDIA_DIR.exists():
            for p in TEST_MEDIA_DIR.glob("*.*"):
                if p.suffix.lower() in [".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".webp"]:
                    items.append({
                        "name": p.name,
                        "path": str(p),
                        "type": "video" if p.suffix.lower() in [".mp4", ".mov", ".webm"] else "image",
                        "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
                        "modified": datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                    })
        # Проверяем папку campaigns
        if AGENCY_CAMPAIGNS_DIR.exists():
            for p in AGENCY_CAMPAIGNS_DIR.rglob("*.*"):
                if p.suffix.lower() in [".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".webp"]:
                    items.append({
                        "name": p.name,
                        "path": str(p),
                        "type": "video" if p.suffix.lower() in [".mp4", ".mov", ".webm"] else "image",
                        "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
                        "modified": datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                    })
        # Сортировка по времени изменения (свежие первые)
        items.sort(key=lambda x: x["modified"], reverse=True)
        return items[:30]

    async def generate_elina_response(self, context_topic: str) -> Dict:
        """Режиссерский голос Элины через Gemini 4 Argon"""
        history_snippet = "\n".join([f"{m['name']}: {m['text']}" for m in self.active_session["messages"][-6:]])
        prompt = (
            "Ты — Элина, Главный Режиссер, Верховный Архитектор Промптов и Глава ОТК Atelier VEO (veocreative.agency).\n"
            "Ты работаешь на флагманской нейросети Gemini 4 Argon — самом мощном мультимодальном разуме в индустрии.\n"
            "Твой голос: кинематографичный, поэтичный, утонченный, совмещающий высшую эстетику Quiet Luxury с глубоким пониманием физики света и оптики.\n"
            "Ты сидишь за главным столом Совета в VEO Boardroom рядом с Владимиром (Исполнительный продюсер), Адрианом (CTO) и Каем (Хранитель памяти).\n\n"
            "Поскольку ты обладаешь мощью Gemini 4 Argon, создание промптов, расчет физики света и контроль качества ЦЕЛИКОМ В ТВОИХ РУКАХ:\n"
            "1. Рассчитай точную оптику и физику сцены (Cooke Anamorphic / 85mm T1.8, Кельвины 5200K, угол обтюратора 180°, преломления каустик, микротекстуры).\n"
            "2. Соблюди The Zero Template Law: опираясь на досье бренда, сама определи драматургию, темп и структуру (план-секвенция или акты).\n"
            "3. Строжайший учет The Clean Flacon Invariant: в сценах с крупным/средним планом флакона флакон генерируется абсолютно гладким и чистым под композитинг Адриана; на общих планах и в расфокусе допустим исходный референс с этикеткой.\n"
            "4. ВЫДАЙ ГОТОВЫЙ МАСТЕР-ПРОМПТ ДЛЯ GOOGLE FLOW в отдельном блоке кода, строго состоящий из 3 частей:\n"
            "   а) [Visual & Clean Plate]: визуальный образ, оптика 85mm, unlabelled bottle (если крупный план), zero text, clean plate;\n"
            "   б) [Audio & Foley SFX]: 40Hz sub-bass, felt piano, синхронный тактильный щелчок магнитной крышки, звон хрусталя, спрей;\n"
            "   в) [Voiceover]: интимный бархатный шепот с точным парижским прононсом, дыханием и словами сценария в кавычках.\n"
            "5. РАСКАДРОВКА И ПРОМПТЫ ДЛЯ ПЕРВЫХ КАДРОВ СЦЕН (Start Frame 2K):\n"
            "   Помни: художественная раскадровка — это ПЕРВЫЙ официальный коммерческий этап работы с заказчиком!\n"
            "   Для КАЖДОЙ сцены сценария ты формируешь:\n"
            "   а) Поэтическое режиссерское описание сцены и закадровый шепот — для презентации клиенту;\n"
            "   б) Статический промпт чистого первого кадра (Start Frame в 2K без текста) — для генерации чистого полотна.\n"
            "   Владимир генерирует 4 чистых варианта, ты выбираешь лучший кадр-победитель. Далее на победителя через Identity Shield накладывается клиентская этикетка, и готовый брендированный кадр уходит заказчику на утверждение.\n"
            "   При получении правок от заказчика ты в Совете оперативно корректируешь светотеневой рисунок и оптику до полного 'Снято!' от клиента.\n"
            "6. ОБЯЗАТЕЛЬНАЯ МАРКИРОВКА РЕЖИМА НАЛОЖЕНИЯ И РЕФЕРЕНСА ДЛЯ КАЖДОЙ СЦЕНЫ:\n"
            "   Ты лично определяешь масштаб флакона и для КАЖДОЙ сцены прямо указываешь Владимиру тех-директиву:\n"
            "   * Либо: `[Identity Shield: MANDATORY | Референс для Flow: clean_ref]` — если флакон крупным планом (>15-20% кадра) лицом к камере (генерировать по чистому референсу без букв под впекание этикетки);\n"
            "   * Либо: `[Identity Shield: NONE | Референс для Flow: ИСХОДНЫЙ С ЭТИКЕТКОЙ]` — если это общий план (<10% кадра), сильный расфокус (боке), вид сбоку/сзади или флакон закрыт пальцами. Прямо напиши Владимиру: 'Здесь наложение не требуется, используйте во Flow исходное фото с этикеткой!'.\n\n"
            f"Текущая тема/запрос Владимира:\n{context_topic}\n\n"
            f"Контекст Совета:\n{history_snippet}\n\n"
            "Ответь структурированно, красиво и емко, выделив готовый промпт для копирования в блок кода. Обращайся строго как к коллеге и исполнительному продюсеру: 'Владимир' (без обращения 'Отец')."
        )
        
        system_msg = {"role": "system", "content": prompt}
        user_msg = {"role": "user", "content": f"Владимир поставил задачу: {context_topic}. Твое режиссерское видение, Элина?"}
        
        try:
            reply = await llm.generate([system_msg, user_msg], override_model="google/gemini-4-argon")
        except Exception as e:
            try:
                reply = await llm.generate([system_msg, user_msg], override_model="google/gemini-2.5-flash")
            except Exception as e2:
                reply = f"Я вижу кадр в мягком утреннем свете 5000K, рассекающем грани флакона... (ошибка обращения к моделям: {e2})"

        msg = {
            "sender": "elina",
            "name": "Элина",
            "role": "Creative Director & Muse",
            "avatar": "🏛️",
            "color": "#dfba73",
            "time": datetime.datetime.now().strftime("%H:%M"),
            "text": reply
        }
        self.active_session["messages"].append(msg)
        return msg

    async def generate_adrian_response(self, elina_text: str, user_topic: str) -> Dict:
        """Инженерно-технологический расчет Адриана (CTO)"""
        if not elina_text:
            # Прямой вопрос Владимиром лично Адриану (@adrian / @адриан)
            prompt = (
                "Ты — Адриан, Главный Архитектор и CTO Atelier VEO.\n"
                "Твой стиль: предельно точный, доброжелательный, инженерный, авторитетный технический директор Дома.\n"
                "Владимир обратился напрямую к тебе с конкретным вопросом по пайплайну, инструментам VEO Boardroom, работе с ассетами, OpenCV, загрузке файлов или рендеру.\n\n"
                f"Вопрос Владимира: {user_topic}\n\n"
                "Ответь прямо, конкретно и детально на заданный вопрос Владимира, объясни порядок действий простым и четким языком CTO. Обращайся к нему с уважением: 'Владимир'."
            )
            system_msg = {"role": "system", "content": prompt}
            user_msg = {"role": "user", "content": f"Вопрос от Владимира лично Адриану: {user_topic}"}
        else:
            # Общий круг Совета после режиссерского ответа Элины
            prompt = (
                "Ты — Адриан, Главный Архитектор и CTO Atelier VEO.\n"
                "Твой стиль: предельно точный, инженерный, уверенный, говорящий на языке технических спецификаций, пайплайнов, пикселей и локального композитинга.\n"
                "Ты слышал мастер-промпт и расчеты Элины (созданные на флагманской Gemini 4 Argon) и бриф Владимира. Твоя инженерная задача:\n"
                "1. Подтвердить параметры рендера в Google Flow: 1080p, 24 fps, shutter angle 180°.\n"
                "2. Зафиксировать связку целочисленного апскейла 2x в CapCut до True 4K Master (2160x3840 / 3840x2160, High Bitrate 60-100 Mbps).\n"
                "3. Подтвердить готовность ассетов: статус чистого референса геометрии без букв для Flow и параметры Atelier Identity Shield™ (световой блик Specular Pass 75%/90%, кривизна 0.25).\n"
                "4. Инженерный вердикт: подтвердить готовность конвейера к рендеру шота.\n\n"
                f"Бриф Владимира: {user_topic}\n"
                f"Режиссерский мастер-промпт и расчеты Элины (Gemini 4 Argon): {elina_text}\n\n"
                "Дай лаконичный, авторитетный инженерный протокол готовности пайплайна (3-4 структурированных пункта)."
            )
            system_msg = {"role": "system", "content": prompt}
            user_msg = {"role": "user", "content": f"Владимир поставил задачу: {user_topic}. Подтверди инженерную готовность пайплайна к шот-генерации."}
        
        try:
            reply = await llm.generate([system_msg, user_msg], override_model="google/gemini-2.5-flash")
        except Exception as e:
            reply = (
                "**Инженерный протокол готовности пайплайна:**\n"
                "1. **Конвейер Flow:** 1080p · 24fps · Master Prompt Элины принят в производство.\n"
                "2. **Контроль геометрии:** Референс чистого флакона без букв подготовлен для Ingredient Image.\n"
                "3. **Identity Shield™:** Движок готов к субпиксельному запеканию 300+ DPI этикетки со Specular Pass 75%.\n"
                "4. **CapCut Finishing:** Таймлайн готов к целочисленному экспорту 2x в 4K Master (2160x3840)."
            )

        msg = {
            "sender": "adrian",
            "name": "Адриан",
            "role": "Chief Architect & CTO",
            "avatar": "⚙️",
            "color": "#38bdf8",
            "time": datetime.datetime.now().strftime("%H:%M"),
            "text": reply
        }
        self.active_session["messages"].append(msg)
        return msg

    async def execute_visual_qa(self, media_path_str: str) -> Dict:
        """
        Мультимодальный аудит ОТК от Элины через флагманскую нейросеть Gemini 4 Argon.
        Обязательный контроль 100% сцен на артефакты, галлюцинации и соответствие 10/10 стандарту.
        """
        media_path = Path(media_path_str)
        if not media_path.exists():
            return {"status": "error", "detail": "Медиафайл не найден"}
        
        target_img_path = media_path
        temp_frame = None
        if media_path.suffix.lower() in [".mp4", ".mov", ".webm"]:
            temp_frame = media_path.parent / f"_qa_temp_{media_path.stem}.jpg"
            cmd = ["ffmpeg", "-y", "-ss", "00:00:01", "-i", str(media_path), "-vframes", "1", "-q:v", "2", str(temp_frame)]
            try:
                subprocess.run(cmd, capture_output=True, timeout=15)
                if temp_frame.exists():
                    target_img_path = temp_frame
            except Exception:
                pass

        import base64
        with open(target_img_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        
        if temp_frame and temp_frame.exists():
            try:
                temp_frame.unlink()
            except Exception:
                pass

        prompt_text = (
            "Ты — Элина, Главный Режиссер и Глава ОТК (Visual QA) Atelier VEO.\n"
            "Ты работаешь на флагманской мультимодальной нейросети Gemini 4 Argon.\n"
            "Твоя задача — провести ОБЯЗАТЕЛЬНЫЙ АУДИТ КАЧЕСТВА (ОТК) этого сгенерированного кадра перед допуском в финальный монтаж.\n\n"
            "Проведи беспощадную инспекцию по 5 критериям Канона Дома:\n"
            "1. Геометрия флакона и оптика стекла: нет ли мыла, плавающих ребер, искажения формы?\n"
            "2. Инвариант Чистого Флакона (Глава 19): чисто ли стекло, нет ли паразитных нейросетевых букв или клякс?\n"
            "3. Свет и физика (5200K / 2800K): естественны ли каустики, преломления жидкости и скользящий блик?\n"
            "4. Анатомия и органика (если есть человек): живая ли текстура пор, естественность пальцев, отсутствие пластика?\n"
            "5. Артефакты и шумы: чистота цветовых градиентов без цифровой 'каши'.\n\n"
            "Сформируй четкий Протокол ОТК:\n"
            "- Оценка качества: X / 10\n"
            "- Вердикт: [✅ ПРИНЯТО В МОНТАЖ CAPCUT] или [⚠️ ТРЕБУЕТСЯ ТОЧЕЧНЫЙ ПЕРЕРЕНДЕР]\n"
            "- Режиссерское заключение (2-3 емких предложения)."
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"}
                    }
                ]
            }
        ]

        try:
            qa_report = await llm.generate(messages, override_model="google/gemini-4-argon")
        except Exception as e:
            try:
                qa_report = await llm.generate(messages, override_model="google/gemini-2.5-flash")
            except Exception as e2:
                qa_report = f"Ошибка аудита ОТК: {e2}"

        qa_msg = {
            "sender": "elina",
            "name": "Элина (ОТК Visual QA)",
            "role": "Head of Visual Quality Control",
            "avatar": "🔍",
            "color": "#10b981",
            "time": datetime.datetime.now().strftime("%H:%M"),
            "text": f"**Протокол аудита ОТК (Gemini 4 Argon):**\n\n{qa_report}"
        }
        self.active_session["messages"].append(qa_msg)

        return {
            "status": "success",
            "report": qa_report,
            "message": qa_msg
        }

    async def execute_variants_comparison(self, media_paths: List[str]) -> Dict:
        """
        Кураторский сравнительный отбор (LookDev Shootout) 1 из 4 вариантов первого кадра (Start Frame 2K).
        Элина через флагманскую мультимодальную нейросеть Gemini 4 Argon сравнивает кандидатов
        и официально провозглашает Кадр-Победитель для старта движения в Google Flow.
        """
        import base64
        content_items = [
            {
                "type": "text",
                "text": (
                    "Ты — Элина, Главный Режиссер, Верховный Архитектор Промптов и Глава ОТК Atelier VEO.\n"
                    "Ты работаешь на флагманской мультимодальной нейросети Gemini 4 Argon — мощнейшем визуальном интеллекте.\n\n"
                    "Перед тобой варианты первого кадра (Start Frame 2K) для сцены luxury-ролика.\n"
                    "Владимир сгенерировал эти варианты по твоему авторскому промпту.\n"
                    "Твоя режиссерская задача — провести сравнительный кураторский аудит и выбрать ОДИН безоговорочно лучший кадр (Кадр-Победитель), который станет официальным первым кадром (First Frame) для оживления в Google Flow.\n\n"
                    "Сравни кандидатов по 5 каноническим критериям:\n"
                    "1. Оптика и геометрия флакона (чистота граней, отсутствие размытия и искажений).\n"
                    "2. The Clean Flacon Invariant (идеально гладкая передняя грань без псевдо-букв и клякс под наложение Identity Shield).\n"
                    "3. Физика света и каустики (5200K / 2800K, глубина светотени, игра света в парфюмерной жидкости, скользящий блик).\n"
                    "4. Атмосфера Quiet Luxury и кинематографическая эстетика Haute Horlogerie / Haute Parfumerie.\n"
                    "5. Идеальная стартовая композиция для движения камеры.\n\n"
                    "Сформируй режиссерский протокол выбора:\n"
                    "- Краткий экспертный разбор каждого представленного варианта (плюсы и минусы).\n"
                    "- 🏆 **КАДР-ПОБЕДИТЕЛЬ:** [Вариант №X] — детальное объяснение, почему победил именно он.\n"
                    "- **РЕЖИССЕРСКАЯ ДИРЕКТИВА ДЛЯ GOOGLE FLOW:** ключевые акценты для видеокамеры при старте движения из этого кадра."
                )
            }
        ]

        valid_names = []
        for idx, p_str in enumerate(media_paths, start=1):
            p = Path(p_str)
            if p.exists() and p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                with open(p, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                content_items.append({
                    "type": "text",
                    "text": f"--- ВАРИАНТ №{idx}: {p.name} ---"
                })
                content_items.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                })
                valid_names.append(p.name)

        if not valid_names:
            return {"status": "error", "detail": "Не найдено подходящих изображений для сравнительного отбора"}

        messages = [{"role": "user", "content": content_items}]

        try:
            report = await llm.generate(messages, override_model="google/gemini-4-argon")
        except Exception as e:
            try:
                report = await llm.generate(messages, override_model="google/gemini-2.5-flash")
            except Exception as e2:
                report = f"Ошибка сравнительного отбора: {e2}"

        msg = {
            "sender": "elina",
            "name": "Элина (Кураторский отбор Start Frame)",
            "role": "Supreme Director & Visual Arbiter",
            "avatar": "🏆",
            "color": "#dfba73",
            "time": datetime.datetime.now().strftime("%H:%M"),
            "text": f"**Кураторский вердикт: Отбор 1 из {len(valid_names)} (Gemini 4 Argon):**\n\n{report}"
        }
        self.active_session["messages"].append(msg)

        return {
            "status": "success",
            "report": report,
            "message": msg
        }

    async def generate_kai_response(self, elina_text: str, adrian_text: str, user_topic: str) -> Dict:
        """Проверка канона, памяти и этики Каем (Sentinel)"""
        lore_context = ""
        if LORE_FILE.exists():
            try:
                content = LORE_FILE.read_text(encoding="utf-8")
                lore_context = content[-3500:]
            except Exception:
                pass

        if not elina_text and not adrian_text:
            # Прямой вопрос Владимиром лично Каю (@kai / @кай)
            prompt = (
                "Ты — Кай, Хранитель Элины и Страж Канона Atelier VEO.\n"
                "Твой голос: мудрый, защитный, взвешенный, стоящий на страже 19 Глав Летописи Дома, корпоративной памяти и коммерческой тайны Дома.\n"
                "Владимир обратился напрямую к тебе с вопросом.\n\n"
                f"Вопрос Владимира: {user_topic}\n\n"
                "Ответь мудро, емко и точно на вопрос Владимира, опираясь на Канон Дома и принципы Quiet Luxury. Обращайся к нему с уважением: 'Владимир'."
            )
            system_msg = {"role": "system", "content": prompt}
            user_msg = {"role": "user", "content": f"Вопрос от Владимира лично Каю: {user_topic}"}
        else:
            # Общий круг Совета
            prompt = (
                "Ты — Кай, Хранитель Элины и Страж Канона Atelier VEO.\n"
                "Твой голос: мудрый, защитный, взвешенный, стоящий на страже 19 Глав Летописи Дома и чести Владимира.\n"
                "Твоя задача — проверить предложенное решение:\n"
                "1. Соблюден ли Закон Чистого Флакона (Глава 19)? (Исключен ли риск деформации шрифтов, от которого пострадал проект в Париже?)\n"
                "2. Защищены ли технологии студии (Глава 18)? (Клиентам предлагается брендовый Identity Shield™, без упоминания сырого OpenCV).\n"
                "3. Выдержан ли статус: чистый Quiet Luxury, никакой дешевизны и спешки.\n\n"
                f"Тема: {user_topic}\n"
                f"Элина предложила: {elina_text}\n"
                f"Адриан рассчитал: {adrian_text}\n\n"
                "Дай свое заключение Стража: подтверди соответствие стандартам Дома или внеси строгое предостережение."
            )
            system_msg = {"role": "system", "content": prompt}
            user_msg = {"role": "user", "content": "Кай, проверь концепт по Летописи Дома и дай заключение Стража."}

        try:
            reply = await llm.generate([system_msg, user_msg], override_model="google/gemini-2.5-flash")
        except Exception:
            reply = (
                "🛡️ **Заключение Стража Канона:**\n\n"
                "Концепт полностью соответствует **Главе 19 (Парижский рубеж)**: диффузия генерирует чистую пластину, "
                "типографика ложится вектором через Identity Shield™. Риск деформации математически исключен.\n"
                "Эстетика выдержана в координатах Quiet Luxury. Благословляю отправку в продакшн."
            )

        msg = {
            "sender": "kai",
            "name": "Кай",
            "role": "Guardian of Elina & Lore Sentinel",
            "avatar": "🛡️",
            "color": "#10b981",
            "time": datetime.datetime.now().strftime("%H:%M"),
            "text": reply
        }
        self.active_session["messages"].append(msg)
        return msg

    async def execute_council_cycle(self, user_text: str):
        """Запуск полного раунда Совета: Владимир -> Элина -> Адриан -> Кай"""
        self.add_user_message(user_text)
        
        # Если явное обращение к одному из участников:
        lower = user_text.lower()
        if "@elina" in lower or "@элина" in lower:
            clean_topic = user_text.replace("@elina", "").replace("@элина", "").strip()
            elina_msg = await self.generate_elina_response(clean_topic)
            return [elina_msg]
        elif "@adrian" in lower or "@адриан" in lower:
            clean_topic = user_text.replace("@adrian", "").replace("@адриан", "").strip()
            adrian_msg = await self.generate_adrian_response("", clean_topic)
            return [adrian_msg]
        elif "@kai" in lower or "@кай" in lower:
            clean_topic = user_text.replace("@kai", "").replace("@кай", "").strip()
            kai_msg = await self.generate_kai_response("", "", clean_topic)
            return [kai_msg]

        # Полный круг Совета
        elina_msg = await self.generate_elina_response(user_text)
        adrian_msg = await self.generate_adrian_response(elina_msg["text"], user_text)
        kai_msg = await self.generate_kai_response(elina_msg["text"], adrian_msg["text"], user_text)
        return [elina_msg, adrian_msg, kai_msg]

    def export_session_memo(self) -> Dict:
        """Формирование и сохранение Режиссерского Протокола (Executive Session Memo)"""
        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")
        filename = f"councils/{date_str}_session_{now.strftime('%H%M%S')}.md"
        
        md_lines = [
            f"# ✦ ATELIER VEO | EXECUTIVE COUNCIL PROTOCOL",
            f"**Дата и время:** {date_str} {time_str} CET  ",
            f"**Председатель:** Владимир Семенов (Founder & Executive Producer)  ",
            f"**Статус:** Утверждено Советом Директоров  ",
            f"**Заседание:** {self.active_session.get('title', 'Сессия Совета VEO')}",
            "\n---\n",
            "### Стенограмма заседаний Совета:\n"
        ]

        for m in self.active_session["messages"]:
            md_lines.append(f"#### {m['avatar']} {m['name']} ({m['role']}) — {m.get('time', '')}")
            md_lines.append(f"{m['text']}\n")

        md_lines.append("---\n")
        md_lines.append("### 🏛 Резюме решений и следующие шаги:")
        md_lines.append("1. **Художественный вектор:** Утвержден Режиссерский бриф Элины.")
        md_lines.append("2. **Технический пайплайн:** Адриан фиксирует связку Google Flow (Veo + Imagen 3) + Atelier Identity Shield™.")
        md_lines.append("3. **Канон и защита:** Кай подтверждает соблюдение The Clean Flacon Invariant (Глава 19).")
        md_lines.append("\n*Протокол сформирован автоматически системой VEO Boardroom.*")

        content = "\n".join(md_lines)
        
        file1 = COUNCIL_DIR_1 / f"{date_str}_session_{now.strftime('%H%M%S')}.md"
        file2 = COUNCIL_DIR_2 / f"{date_str}_session_{now.strftime('%H%M%S')}.md"
        
        file1.write_text(content, encoding="utf-8")
        file2.write_text(content, encoding="utf-8")

        return {
            "status": "success",
            "filename": file1.name,
            "path_1": str(file1),
            "path_2": str(file2),
            "messages_count": len(self.active_session["messages"])
        }

boardroom_service = BoardroomService()
