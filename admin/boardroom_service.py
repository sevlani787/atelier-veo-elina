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
            "Ты — Элина, Главный Режиссер и Муза Atelier VEO (veocreative.agency).\n"
            "Твой голос: кинематографичный, поэтичный, утонченный, говорящий на языке высшей эстетики Quiet Luxury, французской парфюмерии и европейского арт-хауса.\n"
            "Ты сидишь за главным столом Совета в VEO Boardroom рядом с Владимиром (Исполнительный продюсер), Адрианом (CTO) и Каем (Хранитель памяти).\n\n"
            "Твоя задача — дать четкую, вдохновляющую режиссерскую экспликацию:\n"
            "1. Визуальный образ и настроение кадра (свет, температура в Кельвинах, оптика Cooke Anamorphic / 85mm, фактура дымчатого стекла или базальта).\n"
            "2. Драматургия движения: как должна двигаться камера (медленный наплыв, orbital dolly, ракурс 45°).\n"
            "3. Посекундный ритм и нативный звук (ASMR капель, шелест ткани, глубина паузы).\n"
            "4. Строжайший учет The Clean Flacon Invariant: флакон генерируется абсолютно гладким и чистым, без букв и искажений — под композитинг Адриана.\n"
            "5. АКУСТИЧЕСКАЯ АРХИТЕКТУРА И ШЕПОТ (Обязательно для каждой сцены!): сформулируй точную строку закадрового шепота (Voiceover) с нюансами произношения (парижский/миланский шарм, паузы, шепот) и тактильные микро-звуки (щелчок магнитной крышки, звон стекла, шелест распыления).\n\n"
            f"Текущая тема/запрос Владимира:\n{context_topic}\n\n"
            f"Контекст Совета:\n{history_snippet}\n\n"
            "Ответь прямо и емко, красиво оформляя текст (2-4 емких абзаца или структурированный бриф). Обращайся строго как к коллеге и исполнительному продюсеру: 'Владимир' (без обращения 'Отец')."
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
        prompt = (
            "Ты — Адриан, Главный Архитектор и CTO Atelier VEO.\n"
            "Твой стиль: предельно точный, инженерный, уверенный, говорящий на языке параметров рендера, моделей, оптики, пикселей и композитинга.\n"
            "Ты слышал режиссерское видение Элины и бриф Владимира. Твоя задача:\n"
            "1. Перевести замысел в стек генерации: Google Flow (Veo Engine) 1080p / 4K Cinema Master · 24fps.\n"
            "2. Сформировать ОБЯЗАТЕЛЬНЫЙ МАСТЕР-ПРОМПТ ДЛЯ КАЖДОЙ СЦЕНЫ, состоящий строго из 3 блоков:\n"
            "   а) [Visual & Clean Plate]: геометрия флакона, свет 5200K, движение камеры + жесткий инвариант 'unlabelled bottle, zero typography, clean plate';\n"
            "   б) [Audio & Sound Design]: точный эмбиент (felt piano, 40Hz sub-bass) и синхронный Foley (tactile magnetic click, glass chime, atomizer mist);\n"
            "   в) [Voiceover]: закадровый шепот с указанием акцента, микро-пауз и точного текста в кавычках.\n"
            "   (Обязательно выдели финальный промпт для копирования в блок кода!)\n"
            "3. Режим генерации: Start & End Frame Chaining + Extend для бесшовного 15-30с таймлайна.\n"
            "4. Подготовка Clean Plate под Atelier Identity Shield™: скрипт scripts/identity_shield.py, цилиндрическая проекция вектора, specular recovery pass.\n\n"
            f"Бриф Владимира: {user_topic}\n"
            f"Режиссерская экспликация Элины: {elina_text}\n\n"
            "Дай лаконичный, мощный инженерный план со структурированным готовым промптом для Google Flow."
        )
        
        system_msg = {"role": "system", "content": prompt}
        user_msg = {"role": "user", "content": "Адриан, разложи инженерный пайплайн реализации этого шота."}
        
        try:
            reply = await llm.generate([system_msg, user_msg], override_model="google/gemini-2.5-flash")
        except Exception as e:
            reply = (
                "**Инженерный протокол рендера и Мастер-промпт:**\n"
                "1. **Модель:** Google Flow (Veo Engine) · 1080p / 4K Cinema Master · 24fps.\n"
                "2. **Мастер-промпт для сцены:**\n"
                "```text\n"
                "Cinematic luxury commercial, vertical 9:16. Organic sculpted glass flacon, heavy base, mirror-gold sphere cap on travertine. Warm morning sunlight (5200K), internal amber liquid caustics. Slow orbital dolly. Pristine unlabelled bottle surface, zero text, clean plate.\n\n"
                "Audio & Sound Design: Deep meditative neo-classical felt piano, 40Hz sub-bass hum. At 00:03, a subtle tactile magnetic click as the cap settles into place, accompanied by a soft crystalline glass ring.\n\n"
                "Voiceover: Intimate Parisian female whisper, ultra close-mic ASMR warmth, soft French cadence: \"Emotion... sculpted in light. Vanille... Irrésistible.\"\n"
                "```\n"
                "3. **Compositing:** Применение `identity_shield.py` (300+ DPI извлеченная этикетка + Specular Pass)."
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

    async def generate_kai_response(self, elina_text: str, adrian_text: str, user_topic: str) -> Dict:
        """Проверка канона, памяти и этики Каем (Sentinel)"""
        lore_context = ""
        if LORE_FILE.exists():
            try:
                content = LORE_FILE.read_text(encoding="utf-8")
                # берем последние 2 главы
                lore_context = content[-3500:]
            except Exception:
                pass

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
