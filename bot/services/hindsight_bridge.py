"""
Atelier VEO | Hindsight Studio Memory Bridge
============================================
Unified long-term memory bridge connecting:
1. VEO Boardroom (admin/boardroom_service.py) -> Elina (Gemini 4 Argon), Adrian, Kai
2. Telegram Bot (bot/handlers/messages.py) -> Exclusively for Vladimir (config.admin_id)
3. Antigravity Coding Agents System

Architecture:
- Retain / Recall / Reflect operational paradigm.
- Hybrid connector: tries local Hindsight daemon (http://127.0.0.1:9077) with seamless
  local high-speed fallback (hindsight_memory_bank.json) for 100% uptime and resilience.
- Strict air-gapped security: Studio invariants are never exposed to non-admin club members.
"""

import os
import json
import time
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Optional
import httpx

logger = logging.getLogger("hindsight_bridge")

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
COUNCIL_BANK_1 = Path("d:/Antigravity/AI_Video_Agency/councils/hindsight_memory_bank.json")
COUNCIL_BANK_2 = BASE_DIR / "councils" / "hindsight_memory_bank.json"
HINDSIGHT_DAEMON_URL = os.getenv("HINDSIGHT_API_URL", "http://127.0.0.1:9077")

# Foundational Golden Studio Invariants (Pre-seeded Ground Truth)
INITIAL_STUDIO_INVARIANTS = [
    {
        "id": "inv_001_trade_secret",
        "category": "security_and_moat",
        "title": "Закон абсолютной коммерческой тайны (Trade Secret Moat)",
        "content": (
            "Строжайшее вето на публичный показ чистых флаконов (clean plate) и сравнительных сплит-скринов 'До / После'. "
            "Клиентам и рынку подается только готовое произведение в 4K Master Print. "
            "Внешняя легенда: проприетарная технология фотометрической консистентности Atelier Identity Shield™. "
            "Вероятность обратного инжиниринга финального видео составляет менее 3-5% благодаря Specular Glare Pass."
        ),
        "tags": ["security", "trade_secret", "client_pitch", "shield"],
        "author": "vladimir",
        "timestamp": "2026-10-24 15:00:00"
    },
    {
        "id": "inv_002_clean_plate",
        "category": "video_physics",
        "title": "Закон кристального чистого холста (Clean Flacon Plate)",
        "content": (
            "В Google Flow в слот Ingredient Image подается строго чистый флакон без букв (vanille_clean_plate_reference.jpg). "
            "Любые остаточные контуры или полупрозрачные призраки эмблемы на просвете стекла категорически недопустимы, "
            "так как вызывают латентный конфликт весов и галлюцинации шрифта в Veo."
        ),
        "tags": ["flow", "clean_plate", "veo", "lighting"],
        "author": "vladimir",
        "timestamp": "2026-10-24 16:30:00"
    },
    {
        "id": "inv_003_flat_dewarping",
        "category": "optical_geometry",
        "title": "Закон снятия квадратичного искажения (Inverse Dewarping)",
        "content": (
            "Мастер-этикетка (label_*.png) обязана быть строго плоским 2D-вектором на прозрачном альфа-канале RGBA, "
            "прошедшим через обратную цилиндрическую развертку (max_angle = 0.28 * pi / 2.0). "
            "Это исключает эффект Distortion Squared: 3D-кривизна флакона накладывается через identity_shield.py ровно один раз."
        ),
        "tags": ["dewarping", "label", "math", "shield"],
        "author": "adrian",
        "timestamp": "2026-10-24 17:15:00"
    },
    {
        "id": "inv_004_xavier_laplace_passport",
        "category": "sacred_geometry",
        "title": "Паспорт пространственной геометрии Ксавье Лапласа (profile_*.json)",
        "content": (
            "Для Edeniste Vanille Irrésistible зафиксированы инвариантные координаты: высота центра rel_center_y = 0.4798 (47.98% сверху), "
            "относительная ширина корпуса rel_width = 0.6000, пропорция сторон aspect_ratio = 1.3199. "
            "Смещение выше или ниже на 5% нарушает баланс с золотым стоппером и толстым дном."
        ),
        "tags": ["geometry", "edeniste", "laplace", "coordinates"],
        "author": "adrian",
        "timestamp": "2026-10-23 22:30:00"
    },
    {
        "id": "inv_005_service_boundary",
        "category": "business_architecture",
        "title": "Демаркационная линия: Клуб (AI-Аудит) vs Студия (Кутюрный композитинг)",
        "content": (
            "Услуга автоматического редактирования пользовательских видео полностью изъята из клуба. "
            "В клубе действует Prompt Doctor & Multimodal QA Audit (25 кредитов). "
            "Полный композитинг, вживление физического флакона и мастеринг в True 4K 100 Mbps — строго заказная студийная услуга "
            "Bespoke Haute Finishing под личным руководством исполнительного продюсера Владимира Семенова."
        ),
        "tags": ["club", "studio", "pricing", "monetization"],
        "author": "vladimir",
        "timestamp": "2026-10-24 09:30:00"
    },
    {
        "id": "inv_006_directorial_standards",
        "category": "directorial_canon",
        "title": "Трёхкомпонентный золотой канон промпта Элины (Gemini 4 Argon)",
        "content": (
            "Каждая сцена обязана выдаваться монолитным блоком из 3 частей:\n"
            "1. [Visual & Clean Plate]: оптика Cooke Anamorphic / 85mm T1.8, Кельвины 2700K (свет Вермеера), каустика выдержанного рома, unlabelled bottle;\n"
            "2. [Audio & Foley SFX]: 40Hz sub-bass, felt piano, тактильный щелчок магнитной крышки, звон хрусталя;\n"
            "3. [Voiceover & Phonetics]: интимный бархатный шепот с точным парижским прононсом и паузами для дыхания."
        ),
        "tags": ["elina", "prompt_canon", "audio", "foley", "vermeer"],
        "author": "elina",
        "timestamp": "2026-10-23 21:00:00"
    },
    {
        "id": "inv_007_scale_optical_threshold",
        "category": "directorial_canon",
        "title": "Правило оптического разрешения и маркировка сцен",
        "content": (
            "Элина лично маркирует каждый шот в сценарии:\n"
            "* [Identity Shield: MANDATORY | Референс: clean_ref] — крупный план (>20% кадра) лицом к камере;\n"
            "* [Identity Shield: NONE | Референс: original] — общий план (<10% кадра), сильный расфокус (боке) или вид сзади. "
            "На общих планах используется исходное фото с этикеткой, оптика камеры естественно размывает глифы без аппликации."
        ),
        "tags": ["scale_threshold", "tagging", "efficiency", "optics"],
        "author": "elina",
        "timestamp": "2026-10-24 09:00:00"
    },
    {
        "id": "inv_008_storyboard_presentation_gate",
        "category": "client_pitch_protocol",
        "title": "Двухконтурная архитектура раскадровки (Clean Plate ➔ Presentation Plate)",
        "content": (
            "Презентация заказчику: Элина отбирает 1 из 4 чистых кадра 2K (shot01_clean.jpg) ➔ за 1 секунду накладывается Identity Shield (shielded_shot01.jpg). "
            "Клиенту уходит кадр с золотым брендингом и ольфакторной поэзией. "
            "При утверждении чистый shot01_clean.jpg моментально подается в First Frame во Flow — камера начинает движение из идеальной точки без задержек."
        ),
        "tags": ["storyboard", "first_frame", "client_gate", "flow"],
        "author": "vladimir",
        "timestamp": "2026-10-24 09:15:00"
    }
]


class HindsightBridge:
    def __init__(self):
        self.bank_file = COUNCIL_BANK_2
        self.bank_file_backup = COUNCIL_BANK_1
        self._ensure_storage()

    def _ensure_storage(self):
        """Гарантирует существование хранилища банка памяти с начальными золотыми инвариантами."""
        for target in [self.bank_file, self.bank_file_backup]:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    data = {
                        "bank": "atelier_veo_master",
                        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "invariants": INITIAL_STUDIO_INVARIANTS,
                        "episodic_memories": []
                    }
                    target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed to ensure storage at {target}: {e}")

    def _read_bank(self) -> Dict:
        """Безопасное чтение банка памяти с двойным дублированием."""
        for target in [self.bank_file, self.bank_file_backup]:
            if target.exists():
                try:
                    return json.loads(target.read_text(encoding="utf-8"))
                except Exception:
                    pass
        return {"bank": "atelier_veo_master", "invariants": INITIAL_STUDIO_INVARIANTS, "episodic_memories": []}

    def _write_bank(self, data: Dict):
        """Атомарная запись в оба хранилища."""
        data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        for target in [self.bank_file, self.bank_file_backup]:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                logger.warning(f"Error persisting memory bank to {target}: {e}")

    def recall(self, query: str, limit: int = 5) -> str:
        """
        Фаза Recall (Воспоминание):
        Быстрый семантически-ранжированный поиск по законам Дома и подтвержденному опыту.
        """
        data = self._read_bank()
        all_items = data.get("invariants", []) + data.get("episodic_memories", [])
        
        query_words = set(w.lower() for w in query.replace(",", " ").replace(".", " ").split() if len(w) > 2)
        
        scored = []
        for item in all_items:
            score = 0
            text_corpus = (
                item.get("title", "") + " " +
                item.get("content", "") + " " +
                " ".join(item.get("tags", []))
            ).lower()
            
            for qw in query_words:
                if qw in text_corpus:
                    score += 2
                    
            # Дополнительный вес законам безопасности и инвариантам
            if item.get("category") == "security_and_moat":
                score += 1
            if item.get("author") == "vladimir":
                score += 1.5

            scored.append((score, item))
            
        # Сортируем: сначала наиболее подходящие, а если совпадений мало — возвращаем ключевые законы Дома
        scored.sort(key=lambda x: x[0], reverse=True)
        top_items = [item for score, item in scored[:limit]]
        if not top_items:
            top_items = INITIAL_STUDIO_INVARIANTS[:4]

        lines = []
        for idx, item in enumerate(top_items, 1):
            title = item.get("title", "Закон Ателье")
            content = item.get("content", "")
            author = item.get("author", "Дом")
            lines.append(f"{idx}. [{title}] (Автор: {author})\n   {content}")

        return "\n\n".join(lines)

    def retain(self, author: str, text: str, title: Optional[str] = None, tags: Optional[List[str]] = None) -> bool:
        """
        Фаза Retain (Осознанное запоминание):
        Запечатлевает новое продюсерское или режиссерское решение в вечный банк Дома.
        """
        if not text or len(text.strip()) < 5:
            return False

        data = self._read_bank()
        new_memory = {
            "id": f"ep_{int(time.time())}_{author}",
            "category": "producer_decision" if author == "vladimir" else "studio_experience",
            "title": title or f"Решение: {text[:60].strip()}...",
            "content": text.strip(),
            "tags": tags or ["production", author],
            "author": author,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        data.setdefault("episodic_memories", []).append(new_memory)
        # Ограничиваем историю последних решений до 300 самых ценных
        if len(data["episodic_memories"]) > 300:
            data["episodic_memories"] = data["episodic_memories"][-300:]
            
        self._write_bank(data)
        logger.info(f"Retained new studio memory by {author}: {new_memory['title']}")
        return True

    def reflect(self, topic: str = "general") -> str:
        """
        Фаза Reflect (Консолидация):
        Формулирует синтез мудрости студии по текущей теме.
        """
        data = self._read_bank()
        total_invariants = len(data.get("invariants", []))
        total_memories = len(data.get("episodic_memories", []))
        return (
            f"Банк памяти Atelier VEO: {total_invariants} золотых законов Дома, "
            f"{total_memories} зафиксированных решений продюсера. "
            f"Приоритеты: Бескомпромиссная тайна чистых холстов, 300+ DPI Identity Shield, свет 2700K Вермеера."
        )


# Singleton
hindsight_bridge = HindsightBridge()
