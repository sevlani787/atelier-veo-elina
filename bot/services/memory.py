from bot.services.database import db
from bot.config import config

class DialogueMemory:
    def __init__(self, max_messages: int = None):
        self.max_messages = max_messages or config.max_context_messages

    async def get_history(self, user_id: int) -> list[dict]:
        return await db.get_history(user_id, self.max_messages)

    async def add_message(self, user_id: int, role: str, content: str | list):
        await db.save_message(user_id, role, content)

    async def clear_history(self, user_id: int):
        await db.clear_history(user_id)

    async def get_context_for_llm(self, user_id: int) -> list[dict]:
        return await self.get_history(user_id)

    async def update_facts(self, user_id: int, facts_json: str):
        await db.save_facts(user_id, facts_json)

    async def get_user_profile(self, user_id: int) -> str:
        """Возвращает текстовое представление фактов о пользователе."""
        facts = await db.get_facts(user_id)
        if not facts:
            return ""
            
        profile_lines = []
        
        # Безопасная обработка словаря
        if isinstance(facts, dict):
            for key, value in facts.items():
                if value and value != "null" and value != "None":
                    display_key = key.replace('_', ' ').capitalize()
                    if isinstance(value, list):
                        val_str = ", ".join(str(v) for v in value if v)
                        if val_str:
                            profile_lines.append(f"{display_key}: {val_str}")
                    else:
                        profile_lines.append(f"{display_key}: {value}")
        
        # Безопасная обработка списка (на случай сбоя экстрактора)
        elif isinstance(facts, list):
            for item in facts:
                if item:
                    profile_lines.append(str(item))
                
        if not profile_lines:
            return ""
            
        return "\n".join(profile_lines)

    # --- Память образа Элин (глобальная) ---

    async def get_elin_persona(self) -> dict:
        """Возвращает текущие черты образа Элин (dict)."""
        return await db.get_persona()

    async def update_elin_persona(self, traits_json: str):
        """Сохраняет обновлённые черты образа Элин."""
        await db.save_persona(traits_json)

    async def get_elin_persona_text(self) -> str:
        """Возвращает текстовое представление черт образа Элин для промпта."""
        traits = await db.get_persona()
        if not traits:
            return ""

        lines = []
        # Если traits это словарь (ожидаемое поведение)
        if isinstance(traits, dict):
            for key, value in traits.items():
                if value and value != "null" and value != "None":
                    display_key = key.replace('_', ' ').capitalize()
                    if isinstance(value, list):
                        val_str = ", ".join(str(v) for v in value if v)
                        if val_str:
                            lines.append(f"{display_key}: {val_str}")
                    else:
                        lines.append(f"{display_key}: {value}")
        # Если traits это список (бывает при сбоях экстрактора)
        elif isinstance(traits, list):
            for item in traits:
                if item:
                    lines.append(f"• {item}")
        # Если это просто строка
        elif isinstance(traits, str):
            lines.append(traits)

        return "\n".join(lines) if lines else ""

    def _extract_words(self, text: str) -> set[str]:
        import re
        # Находим все слова (русские и английские), приводим к нижнему регистру
        words = re.findall(r'[a-zA-Zа-яА-ЯёЁ0-9]+', text.lower())
        # Исключаем стоп-слова
        stop_words = {
            'что', 'как', 'где', 'когда', 'почему', 'кто', 'это', 'был', 'была', 'было', 'были',
            'мне', 'тебе', 'меня', 'тебя', 'себя', 'свой', 'твоя', 'твое', 'твои', 'наш', 'ваш',
            'этот', 'эта', 'это', 'эти', 'тот', 'та', 'то', 'те', 'для', 'под', 'над', 'при',
            'или', 'если', 'хотя', 'хочет', 'хочу', 'будет', 'будут', 'есть', 'быть',
            'the', 'and', 'you', 'this', 'that', 'for', 'with', 'about', 'from', 'your', 'как', 'так'
        }
        return {w for w in words if len(w) > 2 and w not in stop_words}

    async def get_world_context(self, query: str) -> str:
        """Поиск релевантных разделов в базе знаний (elina_lore.md)."""
        import os
        lore_path = config.base_dir / "bot" / "resources" / "elina_lore.md"
        if not os.path.exists(lore_path):
            return ""

        try:
            with open(lore_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"[LORE] Ошибка чтения elina_lore.md: {e}")
            return ""

        # Разбиваем на секции по заголовкам ## или ###
        import re
        sections = re.split(r'\n(?=#{2,3}\s)', content)
        
        # Первая секция (до первого ## или ###) — введение, игнорируем
        if sections and not sections[0].strip().startswith('#'):
            sections.pop(0)

        query_words = self._extract_words(query)
        if not query_words:
            # Если нет ключевых слов для поиска, вернем приветственный манифест по умолчанию
            for sec in sections:
                if "First Meeting" in sec or "приветственный манифест" in sec.lower():
                    return sec.strip()
            return ""

        scored_sections = []
        for sec in sections:
            sec_words = self._extract_words(sec)
            # Считаем пересечение
            overlap = query_words.intersection(sec_words)
            score = len(overlap)
            if score > 0:
                scored_sections.append((score, sec))

        if not scored_sections:
            # Если ничего не нашли, вернем манифест тихой роскоши или приветственный
            manifests = []
            for sec in sections:
                if "First Meeting" in sec or "Language of Quality" in sec or "манифест" in sec.lower():
                    manifests.append(sec.strip())
            return "\n\n".join(manifests[:2])

        # Сортируем по убыванию очков совпадения
        scored_sections.sort(key=lambda x: x[0], reverse=True)
        
        # Берем топ-2 релевантных раздела
        top_sections = [sec for score, sec in scored_sections[:2]]
        return "\n\n".join(top_sections)


memory = DialogueMemory()