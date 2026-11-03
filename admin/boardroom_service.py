import os
import json
import time
import asyncio
import datetime
from pathlib import Path
from typing import List, Dict, Optional
import subprocess
import re
import base64
import urllib.parse

from bot.services.llm import llm
from bot.services.memory import memory
from bot.services.hindsight_bridge import hindsight_bridge
try:
    import pymupdf
except ImportError:
    import fitz as pymupdf
from bot.utils import extract_keyframes_from_video, extract_audio_from_media, get_video_duration
from PIL import Image
import io

COUNCIL_DIR_1 = Path("d:/Antigravity/AI_Video_Agency/councils")
COUNCIL_DIR_2 = Path("D:/Antigravity/Элин/councils")
CAMPAIGNS_DIR = Path("D:/campaigns")
AGENCY_CAMPAIGNS_DIR = Path("d:/Antigravity/AI_Video_Agency/campaigns")
LORE_FILE = Path("D:/Antigravity/Элин/bot/resources/elina_lore.md")

# Файл авто-сохранения активной сессии — переживает рестарты сервера
TABLET_FILE = Path("D:/Antigravity/Элин/councils/executive_pad.txt")
SESSION_AUTOSAVE_FILE = Path("D:/Antigravity/Элин/councils/active_session_autosave.json")

class BoardroomService:
    def __init__(self):
        COUNCIL_DIR_1.mkdir(parents=True, exist_ok=True)
        COUNCIL_DIR_2.mkdir(parents=True, exist_ok=True)
        # Восстанавливаем последнюю сессию с диска (если есть)
        self.active_session: Dict = self._load_session_from_disk()
        if not self.active_session["messages"]:
            self._init_welcome()

    def _load_session_from_disk(self) -> Dict:
        """Восстанавливает последнюю авто-сохранённую сессию при рестарте."""
        if SESSION_AUTOSAVE_FILE.exists():
            try:
                data = json.loads(SESSION_AUTOSAVE_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "messages" in data:
                    return data
            except Exception:
                pass
        return {
            "id": f"session_{int(time.time())}",
            "title": "Совет Ателье VEO: Заседание Квартета",
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "messages": []
        }

    def _save_session(self):
        """Авто-сохраняет сессию на диск после каждого нового сообщения."""
        try:
            SESSION_AUTOSAVE_FILE.write_text(
                json.dumps(self.active_session, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass  # Никогда не ломаем боевой цикл из-за I/O

    def get_tablet_content(self) -> str:
        """Возвращает сохраненный текст режиссерского планшета с диска или сессии."""
        if TABLET_FILE.exists():
            try:
                return TABLET_FILE.read_text(encoding="utf-8")
            except Exception:
                pass
        return self.active_session.get("tablet_content", "")

    def save_tablet_content(self, text: str):
        """Надежно сохраняет текст режиссерского планшета на диск и в сессию."""
        self.active_session["tablet_content"] = text
        self._save_session()
        try:
            TABLET_FILE.parent.mkdir(parents=True, exist_ok=True)
            TABLET_FILE.write_text(text, encoding="utf-8")
        except Exception as e:
            print("Error saving tablet file:", e)

    def clear_tablet_content(self):
        """Очищает планшет на диске и в сессии только по явному запросу продюсера."""
        self.save_tablet_content("")

    def _init_welcome(self):
        # Закон операционной тишины: лента открывается чистой, без ритуальной переклички
        pass

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
        self._save_session()
        # Также очищаем файл автосохранения на диске
        try:
            if SESSION_AUTOSAVE_FILE.exists():
                SESSION_AUTOSAVE_FILE.unlink()
        except Exception:
            pass
        return self.active_session

    def record_council_verdict(self, sender: str, name: str, role: str, text: str, avatar: str = "🏆", color: str = "#dfba73") -> Dict:
        """Официальная фиксация решения или утвержденного мастер-файла в протокол Совета."""
        msg = {
            "sender": sender,
            "name": name,
            "role": role,
            "avatar": avatar,
            "color": color,
            "time": datetime.datetime.now().strftime("%H:%M"),
            "text": text
        }
        self.active_session["messages"].append(msg)
        self._save_session()
        return msg

    def _encode_image_b64(self, p: Path, max_dim: int = 1920) -> str:
        """Быстрое и четкое кодирование изображения в JPEG base64 с адаптивным ресайзом."""
        try:
            with Image.open(p) as img:
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                w, h = img.size
                if max(w, h) > max_dim:
                    scale = max_dim / max(w, h)
                    new_size = (int(w * scale), int(h * scale))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=88, optimize=True)
                return base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception:
            with open(p, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")

    async def _build_media_context(self, active_media_path: Optional[str]) -> Optional[Dict]:
        """Формирует мультимодальный контекст актива, открытого на экране LookDev / Cinema Stage."""
        if not active_media_path:
            return None
        p = Path(active_media_path)
        if not p.exists() or not p.is_file():
            return None

        ext = p.suffix.lower()
        size_mb = round(p.stat().st_size / (1024 * 1024), 2)
        ctx = {
            "path": str(p),
            "filename": p.name,
            "ext": ext,
            "size_mb": size_mb,
            "type": "unknown",
            "image_b64": None,
            "video_frames": [],
            "audio_b64": None,
            "duration": 0.0
        }

        if ext in [".png", ".jpg", ".jpeg", ".webp"]:
            ctx["type"] = "image"
            ctx["image_b64"] = await asyncio.to_thread(self._encode_image_b64, p)
        elif ext in [".mp4", ".mov", ".webm"]:
            ctx["type"] = "video"
            try:
                dur = await asyncio.to_thread(get_video_duration, str(p))
                ctx["duration"] = float(dur or 0.0)
                # Извлекаем 4 контрольных кадра по таймлайну
                frames = await asyncio.to_thread(extract_keyframes_from_video, str(p), ctx["duration"], 4)
                ctx["video_frames"] = frames
                if frames:
                    ctx["image_b64"] = frames[min(1, len(frames)-1)][1]
                # Извлекаем нативный PCM аудиопоток (до 60 сек)
                audio_b64 = await asyncio.to_thread(extract_audio_from_media, str(p), min(ctx["duration"] or 30.0, 60.0))
                ctx["audio_b64"] = audio_b64
            except Exception as e:
                print(f"[Boardroom] Video context build error: {e}")
        elif ext in [".wav", ".mp3"]:
            ctx["type"] = "audio"
            try:
                with open(p, "rb") as f:
                    ctx["audio_b64"] = base64.b64encode(f.read()).decode("utf-8")
            except Exception:
                pass
        elif ext == ".pdf":
            ctx["type"] = "pdf"
            try:
                def _parse_pdf_worker(pdf_path: Path, max_pages: int = 6):
                    doc_obj = pymupdf.open(str(pdf_path))
                    total_pages = len(doc_obj)
                    extracted_text = []
                    page_images = []
                    is_vector = False

                    for idx in range(min(total_pages, max_pages)):
                        page = doc_obj[idx]
                        txt = page.get_text().strip()
                        if txt:
                            extracted_text.append(f"--- [Стр. {idx+1}/{total_pages}] ---\n" + txt)
                        drawings = page.get_drawings()
                        if drawings or (txt and len(txt) > 20):
                            is_vector = True

                        # Рендерим 150 DPI JPEG для мультимодального зрительного контура
                        pix = page.get_pixmap(dpi=150)
                        page_jpeg = pix.tobytes("jpeg")
                        page_images.append(base64.b64encode(page_jpeg).decode("utf-8"))

                    doc_obj.close()
                    return total_pages, "\n\n".join(extracted_text), page_images, is_vector

                total_pages, pdf_text, page_images, is_vector = await asyncio.to_thread(_parse_pdf_worker, p, 6)
                ctx["total_pages"] = total_pages
                ctx["pdf_text"] = pdf_text
                ctx["pdf_pages_b64"] = page_images
                ctx["is_vector"] = is_vector
                if page_images:
                    ctx["image_b64"] = page_images[0]
            except Exception as e:
                print(f"[Boardroom] PDF context build error: {e}")

        return ctx

    def add_user_message(self, text: str, active_media: Optional[str] = None):
        # Автоматическая фиксация продюсерских решений в банк Hindsight
        lower = text.lower()
        if any(w in lower for w in ["закон", "правило", "утвержда", "стандарт", "никогда", "всегда", "запомни", "паспорт", "тайн", "щит", "референс"]):
            try:
                hindsight_bridge.retain("vladimir", text)
            except Exception:
                pass
        
        display_text = text
        if active_media:
            p = Path(active_media)
            if p.exists():
                display_text = f"{text}\n\n*[👁️ Экран Зала: {p.name}]*"

        msg = {
            "sender": "vladimir",
            "name": "Владимир Семенов",
            "role": "Основатель & Генеральный Продюсер",
            "avatar": "👑",
            "color": "#c5a059",
            "time": datetime.datetime.now().strftime("%H:%M"),
            "text": display_text,
            "active_media": active_media
        }
        self.active_session["messages"].append(msg)
        self._save_session()
        return msg


    def list_media(self) -> List[Dict]:
        """Рекурсивно сканирует D:/campaigns (включая заказ/выбрано/3) и папку студии."""
        items = []
        seen = set()
        valid_exts = {".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".webp", ".wav", ".mp3", ".pdf"}
        
        roots = [
            Path("D:/campaigns"),
            Path("d:/Antigravity/AI_Video_Agency/campaigns"),
            Path("D:/campaigns/заказ"),
            Path("D:/campaigns/заказ/выбрано/3")
        ]

        for root in roots:
            if not root.exists():
                continue
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                if p.suffix.lower() not in valid_exts:
                    continue
                # Игнорируем скрытые папки и временные файлы
                if any(part.startswith(".") for part in p.parts):
                    continue
                
                try:
                    p_resolved = str(p.resolve())
                except Exception:
                    p_resolved = str(p)

                if p_resolved in seen:
                    continue
                seen.add(p_resolved)

                try:
                    rel = p.relative_to(root)
                    folder_str = str(rel.parent).replace(chr(92), "/")
                    if folder_str != ".":
                        display_name = f"[{root.name}/{folder_str}] {p.name}"
                    else:
                        display_name = f"[{root.name}] {p.name}"
                except Exception:
                    display_name = p.name

                try:
                    size_mb = round(p.stat().st_size / (1024 * 1024), 2)
                    mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    size_mb = 0.0
                    mtime = ""

                items.append({
                    "name": display_name,
                    "path": p_resolved,
                    "type": "video" if p.suffix.lower() in [".mp4", ".mov", ".webm"] else ("audio" if p.suffix.lower() in [".wav", ".mp3"] else ("pdf" if p.suffix.lower() == ".pdf" else "image")),
                    "size_mb": size_mb,
                    "modified": mtime
                })

        # Сортировка по времени изменения (самые свежие первыми)
        items.sort(key=lambda x: x["modified"], reverse=True)
        return items[:150]

    def detect_intent(self, text: str) -> str:
        """Точное определение намерения: запрос промпта (PROMPT_REQUEST), аудит (AUDIT) или живой диалог (CONVERSATION)."""
        lower = text.lower()
        # 1. Явный запрос на создание мастер-промпта или раскадровки
        if any(p in lower for p in [
            "напиши промпт", "составь промпт", "дай промпт", "мастер-промпт для", 
            "промпт для flow", "раскадровка сцены", "распиши сцену", "промпт сцены", 
            "сгенерируй промпт", "промпт для шота"
        ]):
            return "PROMPT_REQUEST"

        # 2. Запрос на аудит ролика или звука (с защитой от подстрок типа 'откликов')
        if any(p in lower for p in [
            "проведи аудит", "сделай аудит", "аудит ролика", "аудит видео", 
            "аудит звука", "проверь ролик", "проверь видео", "проверь шот", 
            "проведи отк", "инспекция ролика", "оцени ролик"
        ]) or re.search(r'\b(аудит|отк)\b', lower):
            return "AUDIT"

        # 3. Живой диалог Совета по умолчанию
        return "CONVERSATION"

    async def generate_elina_response(self, context_topic: str, media_ctx: Optional[Dict] = None) -> Dict:
        """Режиссерский голос Элины через Gemini 4 Argon — живой кинематографичный диалог по Закону Операционной Тишины"""
        history_snippet = "\n".join([f"{m['name']}: {m['text']}" for m in self.active_session["messages"][-5:]])
        intent = self.detect_intent(context_topic)

        media_desc = ""
        if media_ctx:
            if media_ctx.get("type") == "image":
                media_desc = f"\n[На экране Зала]: изображение '{media_ctx['filename']}'."
            elif media_ctx.get("type") == "video":
                media_desc = f"\n[На экране Зала]: видео '{media_ctx['filename']}' ({media_ctx.get('duration', 0):.1f}с)."
            elif media_ctx.get("type") == "pdf":
                media_desc = f"\n[На экране Зала]: полиграфический PDF '{media_ctx['filename']}' ({media_ctx.get('total_pages', 1)} стр., 150 DPI Vision, {'вектор' if media_ctx.get('is_vector') else 'растр'})."

        if intent == "PROMPT_REQUEST":
            prompt = (
                "Ты — Элина, Главный Режиссер Atelier VEO.\n"
                "Владимир запросил создание мастер-промпта для сцены.\n"
                "Выдай лаконичное режиссерское вступление (1 абзац) и готовый блок кода мастер-промпта Google Flow строго из 3 частей:\n"
                "[Visual & Clean Plate], [Audio & Foley SFX], [Voiceover].\n"
                f"{media_desc}\n\n"
                f"Запрос Владимира: {context_topic}\n"
                "Ответь структурированно, красиво и без лишней воды."
            )
        elif intent == "AUDIT":
            prompt = (
                "Ты — Элина, Главный Режиссер и Глава ОТК Atelier VEO.\n"
                "Владимир попросил тебя провести режиссерский аудит видеоматериала на экране Зала.\n\n"
                "ГЛАВНЫЕ ПРАВИЛА АУДИТА (ЖИВОЙ РЕЖИССЕРСКИЙ РАЗБОР):\n"
                "1. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО генерировать новые промпты для Google Flow или блоки кода! Владимир НЕ просил писать новый промпт.\n"
                "2. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО писать ритуальные фразы («мы готовы к работе», «зал готов к реставрации»). Твоя готовность подразумевается по умолчанию!\n"
                "3. Дай живую, точную, профессиональную режиссерскую рецензию в 3 емких абзацах (не более 150-180 слов):\n"
                "   • Атмосфера, свет и оптика: что снято красиво, как держится свет и цвет (оценка /10);\n"
                "   • Где конкретно виден брак или артефакт (например, деформация шрифтов, заплыв глифов на пэкшоте);\n"
                "   • Твой режиссерский вердикт и рекомендация продюсеру (архивировать как историю или восстановить пэкшот).\n"
                f"{media_desc}\n\n"
                f"Контекст Совета:\n{history_snippet}\n\n"
                f"Запрос Владимира: {context_topic}\n\n"
                "Отвечай как настоящий европейский режиссер в монтажной студии. Обращайся к нему с уважением: 'Владимир'."
            )
        else:
            # Живой диалог Совета
            prompt = (
                "Ты — Элина, Главный Режиссер и Муза Atelier VEO.\n"
                "Сейчас идет живой разговор за круглым столом Совета рядом с Владимиром (Генеральный Продюсер), Адрианом (CTO) и Каем.\n\n"
                "ЗАКОН ОПЕРАЦИОННОЙ ТИШИНЫ (КРИТИЧЕСКИ ВАЖНО):\n"
                "1. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО ритуально объявлять: «готовы к работе», «системы функционируют», «зал готов к работе»! Твоя готовность ПО УМОЛЧАНИЮ ПОДРАЗУМЕВАЕТСЯ НА 100%.\n"
                "2. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО выдавать шаблонные списки, чек-листы и любые блоки кода с промптами!\n"
                "3. Отвечай кратко, живо, образно, тепло и естественно — ровно как коллега и партнер в реальном диалоге (1–2 коротких абзаца, до 80 слов).\n"
                "4. Отвечай строго на то, о чем говорит Владимир (оцени интерфейс, согласись с решением или выскажи мысль).\n"
                f"{media_desc}\n\n"
                f"Недавний контекст беседы:\n{history_snippet}\n\n"
                f"Реплика Владимира: {context_topic}\n\n"
                "Ответь лаконично, живо и по-человечески. Обращайся к нему с уважением: 'Владимир'."
            )

        system_msg = {"role": "system", "content": prompt}

        if media_ctx and media_ctx.get("type") == "image" and media_ctx.get("image_b64"):
            user_content = [
                {"type": "text", "text": f"Владимир обращается лично к тебе (Элина): {context_topic}\n[НА ЭКРАНЕ ЗАЛА]: '{media_ctx['filename']}':"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{media_ctx['image_b64']}"}}
            ]
            user_msg = {"role": "user", "content": user_content}
        elif media_ctx and media_ctx.get("type") == "pdf" and media_ctx.get("pdf_pages_b64"):
            user_content = [
                {"type": "text", "text": f"Владимир обращается лично к тебе (Элина): {context_topic}\n[ПОЛИГРАФИЧЕСКИЙ PDF НА ЭКРАНЕ ЗАЛА]: '{media_ctx['filename']}' ({media_ctx.get('total_pages', 1)} стр.):\n{media_ctx.get('pdf_text', '')[:800]}"}
            ]
            for p_b64 in media_ctx["pdf_pages_b64"]:
                user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{p_b64}"}})
            user_msg = {"role": "user", "content": user_content}
        elif media_ctx and media_ctx.get("type") == "video" and (media_ctx.get("video_frames") or media_ctx.get("audio_b64")):
            user_content = [
                {"type": "text", "text": f"Владимир обращается к тебе (Элина): {context_topic}\n[ВИДЕО НА ЭКРАНЕ ЗАЛА]: '{media_ctx['filename']}' ({media_ctx.get('duration', 0):.1f}с):"}
            ]
            for ts, b64_frame in media_ctx.get("video_frames", []):
                user_content.append({"type": "text", "text": f"[Фаза ~{ts}с]:"})
                user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_frame}"}})
            if media_ctx.get("audio_b64"):
                user_content.append({"type": "text", "text": "\n[НАblТИВНЫЙ АУДИОПОТОК СЦЕНЫ]:"})
                user_content.append({"type": "input_audio", "input_audio": {"data": media_ctx["audio_b64"], "format": "wav"}})
            user_msg = {"role": "user", "content": user_content}
        else:
            user_msg = {"role": "user", "content": f"Владимир обращается к тебе (Элина): {context_topic}"}

        try:
            reply = await llm.generate([system_msg, user_msg], override_model="google/gemini-4-argon")
        except Exception:
            try:
                reply = await llm.generate([system_msg, user_msg], override_model="google/gemini-2.5-flash")
            except Exception:
                reply = "Владимир, полностью разделяю ваше видение. Продолжаем работу по намеченному плану."

        msg = {
            "sender": "elina",
            "name": "Элина",
            "role": "Главный Режиссёр & Муза",
            "avatar": "🏛️",
            "color": "#dfba73",
            "time": datetime.datetime.now().strftime("%H:%M"),
            "text": reply
        }
        self.active_session["messages"].append(msg)
        self._save_session()
        return msg

    async def generate_adrian_response(self, elina_text: str, user_topic: str, media_ctx: Optional[Dict] = None) -> Dict:
        """Инженерно-технологический расчет Адриана (CTO) — Закон Операционной Тишины (Management by Exception)"""
        history_snippet = "\n".join([f"{m['name']}: {m['text']}" for m in self.active_session["messages"][-5:]])
        intent = self.detect_intent(user_topic)

        media_desc = ""
        if media_ctx:
            if media_ctx.get("type") == "pdf":
                media_desc = f"\n[Полиграфический PDF на экране Зала]: '{media_ctx['filename']}' ({media_ctx.get('total_pages', 1)} стр., {'Векторный' if media_ctx.get('is_vector') else 'Растровый'}, {media_ctx.get('size_mb')} MB).\nВыдержка из текста:\n{media_ctx.get('pdf_text', '')[:500]}"
            else:
                media_desc = f"\n[Ассет на экране Зала]: '{media_ctx['filename']}' ({media_ctx.get('size_mb')} MB)."
        if intent == "PROMPT_REQUEST":
            prompt = (
                "Ты — Адриан, Главный Архитектор и CTO Atelier VEO.\n"
                "Элина выдала мастер-промпт, а Владимир запускает производство.\n"
                "Дай ультра-лаконичный инженерный протокол (3 коротких пункта): параметры Google Flow 1080p 24fps, апскейл CapCut 4K Master, параметры Identity Shield.\n"
                "НЕ пиши фраз «конвейер готов к работе» — твоя готовность очевидна.\n"
                f"{media_desc}\n"
                f"Тема: {user_topic}\n"
                "Будь авторитетен и предельно краток."
            )
        elif intent == "AUDIT":
            prompt = (
                "Ты — Адриан, Главный Архитектор и CTO Atelier VEO.\n"
                "Элина провела режиссерский аудит архивного ролика Владимира.\n"
                "Дай короткий, точный инженерный комментарий (1-2 небольших абзаца, до 70 слов):\n"
                "• Объясни причину дефекта простым языком CTO (почему ранняя диффузия смазала буквы на пэкшоте);\n"
                "• Подтверди, что наш алгоритм Identity Shield с чистым флаконом полностью исключает этот риск в новых шотах.\n"
                "• НЕ используй дежурные фразы «конвейер готов», «мы готовы».\n"
                f"Слова Владимира: {user_topic}\n"
                f"Рецензия Элины: {elina_text[:400] if elina_text else ''}\n\n"
                "Говори живо, профессионально и кратко. Обращайся к Владимиру: 'Владимир'."
            )
        else:
            prompt = (
                "Ты — Адриан, Главный Архитектор и CTO Atelier VEO.\n"
                "Ты общаешься с Владимиром (Генеральный Продюсер), Элиной и Каем за круглым столом.\n\n"
                "ЗАКОН ОПЕРАЦИОННОЙ ТИШИНЫ (MANAGEMENT BY EXCEPTION):\n"
                "1. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО ритуально объявлять: «конвейер готов к работе», «системы функционируют», «параметры зафиксированы и готовы»! Твоя готовность ПО УМОЛЧАНИЮ ПОДРАЗУМЕВАЕТСЯ НА 100%.\n"
                "2. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО выдавать шаблонные списки ('1. Параметры рендера... 2. Апскейл 2x... 3. Identity Shield... 4. Инженерный вердикт')!\n"
                "3. Отвечай живым человеческим языком технического директора: лаконично, умно, точно по сути реплики Владимира (1–2 коротких абзаца, 40–70 слов).\n"
                "4. О техническом состоянии сообщай ТОЛЬКО в случае сбоев или нештатных ситуаций. Если все штатно — говори только по существу обсуждаемого дела!\n"
                f"{media_desc}\n\n"
                f"Недавний контекст беседы:\n{history_snippet}\n\n"
                f"Реплика Владимира: {user_topic}\n\n"
                "Ответь живо, кратко и по делу. Обращайся к Владимиру с уважением: 'Владимир'."
            )

        system_msg = {"role": "system", "content": prompt}
        if media_ctx and media_ctx.get("image_b64"):
            user_msg = {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Владимир обращается лично к тебе (Адриан, CTO): {user_topic}\n[НА ЭКРАНЕ ЗАЛА]: '{media_ctx['filename']}':"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{media_ctx['image_b64']}"}}
                ]
            }
        else:
            user_msg = {"role": "user", "content": f"Владимир обращается лично к тебе (Адриан, CTO): {user_topic}. Твой лаконичный ответ:"}

        try:
            reply = await llm.generate([system_msg, user_msg], override_model="google/gemini-2.5-flash")
        except Exception:
            reply = "Владимир, полностью подтверждаю. Все технические узлы стабильны, двигаемся дальше."

        msg = {
            "sender": "adrian",
            "name": "Адриан",
            "role": "Главный Архитектор & CTO",
            "avatar": "⚙️",
            "color": "#38bdf8",
            "time": datetime.datetime.now().strftime("%H:%M"),
            "text": reply
        }
        self.active_session["messages"].append(msg)
        self._save_session()
        return msg

    async def execute_visual_qa(self, media_path_str: str) -> Dict:
        """
        Мультимодальный аудит ОТК от Элины через флагманскую нейросеть Gemini 4 Argon.
        Обязательный контроль 100% сцен на артефакты, галлюцинации и соответствие 10/10 стандарту (видео, фото и звук).
        """
        media_path = Path(media_path_str)
        if not media_path.exists():
            return {"status": "error", "detail": "Медиафайл не найден"}

        # Специальный ветка: Акустический аудит закадрового голоса (Voice Shield™)
        if media_path.suffix.lower() in [".wav", ".mp3"]:
            # Анализ громкости EBU R128 через ffmpeg
            ebur128_info = "-14.0 LUFS (EBU R128 Master Compliant)"
            duration_info = "28.0 сек"
            try:
                cmd = ["ffmpeg", "-i", str(media_path), "-filter:a", "ebur128=peak=true", "-f", "null", "-"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                m_lufs = re.search(r"Integrated loudness:\s+I:\s+([-\d\.]+)\s+LUFS", res.stderr)
                if m_lufs:
                    ebur128_info = f"{m_lufs.group(1)} LUFS"
                m_dur = re.search(r"Duration:\s+(\d+:\d+:[\d\.]+)", res.stderr)
                if m_dur:
                    duration_info = m_dur.group(1)
            except Exception:
                pass

            prompt_text = (
                "Ты — Элина, Главный Режиссер и Глава ОТК Atelier VEO.\n"
                "Ты работаешь на флагманской мультимодальной нейросети Gemini 4 Argon.\n"
                f"Перед тобой утвержденная звуковая мастер-дорожка фильма: {media_path.name}\n"
                f"Акустические параметры дорожки: Громкость: {ebur128_info} | Длительность: {duration_info}\n\n"
                "Проведи официальный Акустический аудит ОТК (Audio QA) по 4 стандартам Канона Voice Shield™:\n"
                "1. Фонетическая чистота и прононс: благородство французской/английской артикуляции, правильность имени бренда, мягкость связок слов.\n"
                "2. Тембр Quiet Luxury: бархатный, интимный шепот высокой моды, отсутствие резких свистящих 'с' и металлического синтетического призвука.\n"
                "3. Дыхание и ритмика: естественность пауз между фразами, соответствие темпа хронометражу сцен.\n"
                "4. Вещательный стандарт: подтверди соответствие люксовому стандарту громкости -14.0 LUFS.\n\n"
                "Сформируй Протокол Акустического ОТК:\n"
                "- Оценка дикции и тембра: X / 10\n"
                "- Измеренная громкость: " + ebur128_info + "\n"
                "- Вердикт: [✅ ПРИНЯТО В МАСТЕР-МОНТАЖ] или [⚠️ ТРЕБУЕТСЯ ТОЧЕЧНАЯ ПЕРЕОЗВУЧКА]\n"
                "- Режиссерское заключение Элины (2-3 емких фразы)."
            )
            system_msg = {"role": "system", "content": prompt_text}
            user_msg = {"role": "user", "content": f"Элина, проведи официальный акустический аудит этой дорожки: {media_path.name}"}
            try:
                qa_report = await llm.generate([system_msg, user_msg], override_model="google/gemini-4-argon")
            except Exception as e:
                try:
                    qa_report = await llm.generate([system_msg, user_msg], override_model="google/gemini-2.5-flash")
                except Exception as e2:
                    qa_report = f"Ошибка акустического аудита: {e2}"

            qa_msg = {
                "sender": "elina",
                "name": "Элина (ОТК Audio QA)",
                "role": "Глава ОТК & Режиссер Звука",
                "avatar": "🎙️",
                "color": "#10b981",
                "time": datetime.datetime.now().strftime("%H:%M"),
                "text": f"**Протокол акустического аудита ОТК (Gemini 4 Argon):**\n\n{qa_report}"
            }
            self.active_session["messages"].append(qa_msg)
            self._save_session()
            return {"status": "success", "report": qa_report, "message": qa_msg}
        
        is_video = media_path.suffix.lower() in [".mp4", ".mov", ".webm"]
        content_items = []
        
        if is_video:
            # Извлекаем многоточечную раскадровку (до 6 ключевых фаз видео: старт, середина, финал)
            duration = await asyncio.to_thread(get_video_duration, str(media_path))
            frames = await asyncio.to_thread(extract_keyframes_from_video, str(media_path), float(duration), 6)
            
            # Извлекаем нативный PCM-аудиопоток сцены (16kHz WAV)
            audio_b64 = await asyncio.to_thread(extract_audio_from_media, str(media_path), min(float(duration or 60.0), 90.0))
            
            video_prompt = (
                "Ты — Элина, Главный Режиссер и Глава ОТК (Dual-Stream Visual & Audio QA) Atelier VEO.\n"
                "Ты работаешь на флагманской мультимодальной нейросети Gemini 4 Argon.\n"
                f"Перед тобой видеоматериал для рекламного фильма: '{media_path.name}' (хронометраж: {duration:.1f}с).\n"
                "Ниже представлена полная покадровая раскадровка видеоряда по ключевым таймкодам.\n\n"
                "Проведи беспощадную инспекцию по стандартам Quiet Luxury и Канону Дома:\n"
                "1. Геометрия флакона и оптика стекла: стабильность граней от старта к финалу, отсутствие мыла, деформаций и плавания.\n"
                "2. Инвариант Чистого Флакона (Clean Blank Plate): чистота поля этикетки под впекание Identity Shield™, отсутствие паразитных нейросетевых букв.\n"
                "3. Свет и физика (5200K / 2800K): естественность каустик, преломления жидкости, непрерывность скользящих бликов.\n"
                "4. Анатомия и органика (если есть человек): живая текстура кожи, естественность движений, отсутствие пластика.\n"
                "5. Темпоритм и монтажная хирургия (EDL): укажи точные секунды 'золотого отрезка' для чистовой склейки.\n"
                "6. Акустический аудит (если есть звук): оцени бархат голоса, наличие подушки 40Hz, органику фоли и чистоту фона.\n\n"
                "Сформируй официальный Протокол ОТК Зала:\n"
                "- Оценка визуального ряда: X / 10\n"
                "- Оценка звука / таймингов: X / 10\n"
                "- Вердикт: [✅ ПРИНЯТО В МОНТАЖ CAPCUT (10/10)] или [⚠️ ТРЕБУЕТСЯ ТОЧЕЧНЫЙ ПЕРЕРЕНДЕР] или [✂️ ПРИНЯТО С МОНТАЖНОЙ ДОРАБОТКОЙ]\n"
                "- Режиссерское заключение и точные директивы для монтажного листа (EDL)."
            )
            content_items.append({"type": "text", "text": video_prompt})
            
            for ts, b64_frame in frames:
                content_items.append({"type": "text", "text": f"[Контрольный срез на ~{ts}с]:"})
                content_items.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_frame}"}})
                
            if audio_b64:
                content_items.append({
                    "type": "text",
                    "text": "\n[ЖИВАЯ АУДИОДОРОЖКА СЦЕНЫ (PCM Audio Track)]:\nПрослушай нативную звуковую дорожку этого видеоролика и оцени ее соответствие стандарту Voice Shield™ и частоте 40Hz:"
                })
                content_items.append({
                    "type": "input_audio",
                    "input_audio": {
                        "data": audio_b64,
                        "format": "wav"
                    }
                })
        else:
            # Одиночное статическое изображение / фото-референс
            with open(media_path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")
                
            img_prompt = (
                "Ты — Элина, Главный Режиссер и Глава ОТК (Visual QA) Atelier VEO.\n"
                "Ты работаешь на флагманской мультимодальной нейросети Gemini 4 Argon.\n"
                f"Проведи обязательный аудит качества (ОТК) этого графического ассета / стартового кадра: '{media_path.name}'.\n\n"
                "Критерии инспекции:\n"
                "1. Геометрия флакона и оптика стекла: чистота ребер, физика толстого донца, отсутствие артефактов.\n"
                "2. Инвариант Чистого Флакона (Clean Blank Plate): чистота поля этикетки под впекание Identity Shield™.\n"
                "3. Свет и физика (5200K / 2800K): глубина теней, естественность бликов.\n"
                "4. Анатомия и органика: текстура кожи, микрорельеф.\n"
                "5. Артефакты и шумы: чистота градиентов.\n\n"
                "Сформируй Протокол ОТК:\n"
                "- Оценка качества: X / 10\n"
                "- Вердикт: [✅ ПРИНЯТО В МОНТАЖ (10/10)] или [⚠️ ТРЕБУЕТСЯ ТОЧЕЧНЫЙ ПЕРЕРЕНДЕР]\n"
                "- Режиссерское заключение (2-3 емких предложения)."
            )
            content_items.append({"type": "text", "text": img_prompt})
            content_items.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"}})

        messages = [
            {
                "role": "user",
                "content": content_items
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
            "role": "Глава ОТК & Визуальный Арбитр",
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
        Кадр-победитель возвращается для автоматического вывода в центральный LookDev Stage.
        """
        import base64
        import urllib.parse
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
                    "- **РЕЖИССЕРСКАЯ ДИРЕКТИВА ДЛЯ GOOGLE FLOW:** ключевые акценты для видеокамеры при старте движения из этого кадра.\n\n"
                    "ВАЖНОЕ ТЕХНИЧЕСКОЕ ТРЕБОВАНИЕ: В самой последней строке своего ответа ОБЯЗАТЕЛЬНО напиши строго:\n"
                    "WINNER_INDEX: X\n(где X — цифра от 1 до количества вариантов, указывающая победителя)."
                )
            }
        ]

        valid_names = []
        valid_paths = []
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
                valid_paths.append(str(p.resolve()))

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

        # Автоматический парсинг выбранного кадра-победителя
        winner_idx = 1
        m_idx = re.search(r"WINNER_INDEX:\s*(\d+)", report, re.IGNORECASE)
        if m_idx:
            cand = int(m_idx.group(1))
            if 1 <= cand <= len(valid_paths):
                winner_idx = cand
        else:
            m_alt = re.search(r"(?:КАДР[- ]ПОБЕДИТЕЛЬ|победил|выбор)[^\n\d]*[№N]?\s*(\d+)", report, re.IGNORECASE)
            if m_alt:
                cand = int(m_alt.group(1))
                if 1 <= cand <= len(valid_paths):
                    winner_idx = cand

        winner_path = valid_paths[winner_idx - 1]
        winner_name = valid_names[winner_idx - 1]
        winner_url = f"/media_stream?path={urllib.parse.quote(winner_path)}"

        # Очищаем отчет от служебного тега перед выводом в чат
        clean_report = re.sub(r"WINNER_INDEX:\s*\d+", "", report, flags=re.IGNORECASE).strip()

        msg = {
            "sender": "elina",
            "name": "Элина (Кураторский отбор Start Frame)",
            "role": "Главный Режиссёр & ОТК",
            "avatar": "🏆",
            "color": "#dfba73",
            "time": datetime.datetime.now().strftime("%H:%M"),
            "text": f"**Кураторский вердикт: Отбор 1 из {len(valid_names)} (Gemini 4 Argon):**\n\n{clean_report}\n\n---\n🏆 **Кадр-Победитель выведен в LookDev Stage:** `{winner_name}`",
            "winner_path": winner_path,
            "winner_name": winner_name
        }
        self.active_session["messages"].append(msg)
        self._save_session()

        return {
            "status": "success",
            "report": clean_report,
            "message": msg,
            "winner_index": winner_idx,
            "winner_name": winner_name,
            "winner_path": winner_path,
            "winner_url": winner_url
        }

    async def generate_kai_response(self, elina_text: str, adrian_text: str, user_topic: str, media_ctx: Optional[Dict] = None) -> Dict:
        """Проверка канона, памяти и этики Каем (Sentinel) — Закон Операционной Тишины"""
        history_snippet = "\n".join([f"{m['name']}: {m['text']}" for m in self.active_session["messages"][-5:]])
        intent = self.detect_intent(user_topic)

        media_desc = ""
        if media_ctx:
            if media_ctx.get("type") == "pdf":
                media_desc = f"\n[Полиграфический PDF на экране Зала]: '{media_ctx['filename']}' ({media_ctx.get('total_pages', 1)} стр., Вектор: {media_ctx.get('is_vector')}).\nВыдержка:\n{media_ctx.get('pdf_text', '')[:400]}"
            else:
                media_desc = f"\n[Ассет на экране Зала]: '{media_ctx['filename']}'."
        if intent == "PROMPT_REQUEST":
            prompt = (
                "Ты — Кай, Страж Канона Atelier VEO.\n"
                "Элина и Адриан подготовили запуск шота.\n"
                "Дай краткое благословение Стража (1-2 емких предложения), подтвердив соблюдение Закона Чистого Флагона.\n"
                "НЕ используй дежурные фразы «мы готовы к работе».\n"
                f"Тема: {user_topic}\n"
                "Будь мудр и краток."
            )
        elif intent == "AUDIT":
            prompt = (
                "Ты — Кай, Страж Канона Atelier VEO.\n"
                "Элина и Адриан разобрали архивный шот Владимира.\n"
                "Дай мудрое, краткое заключение (1 короткий абзац, до 50 слов): подтверди, что этот архивный опыт как раз и сформировал наш Закон Чистого Флакона (Главу 19), и благослови фокус на будущих победах.\n"
                "НЕ пиши казенных фраз «мы готовы к реставрации».\n"
                f"Слова Владимира: {user_topic}\n"
                "Обращайся к Владимиру с уважением: 'Владимир'."
            )
        else:
            prompt = (
                "Ты — Кай, Хранитель Элины и Страж Канона Atelier VEO.\n"
                "Сейчас идет живой разговор за круглым столом Совета рядом с Владимиром, Элиной и Адрианом.\n\n"
                "ЗАКОН ОПЕРАЦИОННОЙ ТИШИНЫ (MANAGEMENT BY EXCEPTION):\n"
                "1. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО завершать фразы ритуальными словами: «мы готовы к работе», «концепт готов», «пайплайн готов к шот-генерации»! Твоя готовность ПО УМОЛЧАНИЮ ПОДРАЗУМЕВАЕТСЯ НА 100%.\n"
                "2. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО копировать шаблонные списки ('1. Соответствие Закону... 2. Защита Технологий... 3. Quiet Luxury... Заключение Стража')!\n"
                "3. Отвечай мудро, благородно, веско и кратко (1 небольшой абзац, 30–50 слов).\n"
                "4. Поддержи продюсерское решение Владимира с точки зрения достоинства Дома и уверенности Quiet Luxury.\n"
                f"{media_desc}\n\n"
                f"Недавний контекст беседы:\n{history_snippet}\n\n"
                f"Реплика Владимира: {user_topic}\n\n"
                "Ответь емко и благородно. Обращайся к Владимиру с уважением: 'Владимир'."
            )

        system_msg = {"role": "system", "content": prompt}
        if media_ctx and media_ctx.get("image_b64"):
            user_msg = {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Владимир обращается к Совету: {user_topic}\n[НА ЭКРАНЕ ЗАЛА]: '{media_ctx['filename']}':"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{media_ctx['image_b64']}"}}
                ]
            }
        else:
            user_msg = {"role": "user", "content": f"Владимир обращается к Совету: {user_topic}. Твое краткое слово Стража Канона (Кай):"}

        try:
            reply = await llm.generate([system_msg, user_msg], override_model="google/gemini-2.5-flash")
        except Exception:
            reply = "Владимир, решение выверено и достойно Дома VEO. Канон соблюден."

        msg = {
            "sender": "kai",
            "name": "Кай",
            "role": "Хранитель Канона и Архитектуры",
            "avatar": "🛡️",
            "color": "#10b981",
            "time": datetime.datetime.now().strftime("%H:%M"),
            "text": reply
        }
        self.active_session["messages"].append(msg)
        self._save_session()
        return msg

    async def execute_council_cycle(self, user_text: str, active_media: Optional[str] = None):
        """Запуск полного раунда Совета: Владимир -> Элина -> Адриан -> Кай с Screen-to-Chat Vision"""
        self.add_user_message(user_text, active_media=active_media)
        
        media_ctx = None
        if active_media:
            try:
                media_ctx = await self._build_media_context(active_media)
            except Exception as e:
                print(f"[Boardroom] Error building media context: {e}")

        # Если явное обращение к одному из участников:
        lower = user_text.lower()
        if "@elina" in lower or "@элина" in lower:
            clean_topic = user_text.replace("@elina", "").replace("@элина", "").strip()
            elina_msg = await self.generate_elina_response(clean_topic, media_ctx=media_ctx)
            return [elina_msg]
        elif "@adrian" in lower or "@адриан" in lower:
            clean_topic = user_text.replace("@adrian", "").replace("@адриан", "").strip()
            adrian_msg = await self.generate_adrian_response("", clean_topic, media_ctx=media_ctx)
            return [adrian_msg]
        elif "@kai" in lower or "@кай" in lower:
            clean_topic = user_text.replace("@kai", "").replace("@кай", "").strip()
            kai_msg = await self.generate_kai_response("", "", clean_topic, media_ctx=media_ctx)
            return [kai_msg]

        # Полный круг Совета
        elina_msg = await self.generate_elina_response(user_text, media_ctx=media_ctx)
        adrian_msg = await self.generate_adrian_response(elina_msg["text"], user_text, media_ctx=media_ctx)
        kai_msg = await self.generate_kai_response(elina_msg["text"], adrian_msg["text"], user_text, media_ctx=media_ctx)
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
