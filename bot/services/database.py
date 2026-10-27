import aiosqlite
import json
from typing import Optional


from bot.config import config

class Database:
    def __init__(self, db_path: str = None):
        if db_path is None:
            self.db_path = str(config.base_dir / "elin.db")
        else:
            self.db_path = db_path

    async def init(self):
        """Инициализация таблиц базы данных."""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица пользователей и фактов (профиль)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    facts TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Проверка и добавление новых колонок если их нет
            cursor = await db.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in await cursor.fetchall()]
            
            if 'tokens' not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN tokens INTEGER DEFAULT 0")
            if 'sub_type' not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN sub_type TEXT DEFAULT 'free'")
            if 'sub_expiry' not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN sub_expiry TIMESTAMP NULL")

            # Таблица сообщений (история)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    role TEXT,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            """)

            # Таблица образа Элин (глобальная память персоны)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS persona (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    traits TEXT DEFAULT '{}',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица глобальных настроек
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Гарантируем начальные записи
            await db.execute("INSERT OR IGNORE INTO persona (id, traits) VALUES (1, '{}')")
            
            # Дефолтные настройки
            default_settings = [
                ('trial_tokens', '20'),
                ('token_cost_msg', '100'),
                ('token_cost_search', '500'),
                ('ai_model', 'deepseek/deepseek-chat'),
                ('max_tokens', '4096'),
                ('price_month', '500'),
                ('price_half_year', '2500'),
                ('price_year', '4500'),
                ('tokens_sub_month', '300000'),
                ('tokens_sub_half_year', '2000000'),
                ('tokens_sub_year', '4500000'),
                ('tokens_small', '50000'),
                ('price_tokens_small', '100'),
                ('tokens_medium', '150000'),
                ('price_tokens_medium', '250'),
                ('tokens_large', '500000'),
                ('price_tokens_large', '750')
            ]
            for key, val in default_settings:
                await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

            # Гарантируем дегустационный лимит 20 кредитов (Tasting Pass) для Atelier VEO Club
            await db.execute("UPDATE settings SET value = '20' WHERE key = 'trial_tokens'")

            # Автоматически назначаем админа если он есть в конфиге
            from bot.config import config
            if config.admin_id:
                await db.execute(
                    "UPDATE users SET sub_type = 'admin' WHERE user_id = ?", 
                    (config.admin_id,)
                )

            await db.commit()

    async def save_message(self, user_id: int, role: str, content: str | list):
        """Сохранение сообщения в историю (контент как JSON для поддержки фото)."""
        content_str = json.dumps(content, ensure_ascii=False)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Убедимся, что пользователь есть в таблице users
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, facts) VALUES (?, ?)", 
                (user_id, "{}")
            )
            # Сохраняем сообщение
            await db.execute(
                "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
                (user_id, role, content_str)
            )
            
            # Удаляем старые сообщения (оставляем только N последних для экономии места)
            await db.execute(f"""
                DELETE FROM messages 
                WHERE id NOT IN (
                    SELECT id FROM messages 
                    WHERE user_id = ? 
                    ORDER BY id DESC LIMIT {config.max_context_messages}
                ) AND user_id = ?
            """, (user_id, user_id))
            
            await db.commit()

    async def get_history(self, user_id: int, limit: int = 20) -> list[dict]:
        """Получение последних N сообщений для контекста LLM."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT role, content FROM messages WHERE user_id = ? ORDER BY id ASC", 
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()

        history = []
        for role, content_str in rows:
            try:
                content = json.loads(content_str)
            except json.JSONDecodeError:
                content = content_str
                
            history.append({
                "role": role,
                "content": content
            })
            
        # Возвращаем последние N (история уже отсортирована ASC)
        return history[-limit:]

    async def clear_history(self, user_id: int):
        """Очистка истории сообщений пользователя."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
            await db.commit()

    async def save_facts(self, user_id: int, facts_json: str):
        """Сохранение/обновление извлеченных фактов (профиля) пользователя."""
        async with aiosqlite.connect(self.db_path) as db:
            # Обновляем факты (или вставляем если еще нет)
            await db.execute("""
                INSERT INTO users (user_id, facts, updated_at) 
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET 
                    facts = excluded.facts,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, facts_json))
            await db.commit()

    async def get_facts(self, user_id: int) -> dict:
        """Получение профиля пользователя."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT facts FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                
        if row and row[0]:
            try:
                return json.loads(row[0])
            except json.JSONDecodeError:
                pass
        return {}

    async def save_persona(self, traits_json: str):
        """Сохранение/обновление черт образа Элин (глобальная память)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE persona SET traits = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1
            """, (traits_json,))
            await db.commit()

    async def get_persona(self) -> dict:
        """Получение текущих черт образа Элин."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT traits FROM persona WHERE id = 1") as cursor:
                row = await cursor.fetchone()

        if row and row[0]:
            try:
                return json.loads(row[0])
            except json.JSONDecodeError:
                pass
        return {}

    async def get_setting(self, key: str, default: str = None) -> str:
        """Получение значения настройки из БД."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
                row = await cursor.fetchone()
        return row[0] if row else default

    async def set_setting(self, key: str, value: str):
        """Обновление настройки в БД."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """, (key, str(value)))
            await db.commit()

    async def get_user_data(self, user_id: int) -> Optional[dict]:
        """Получение полных данных пользователя."""
        from bot.config import config
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
            if row:
                data = dict(row)
                if config.admin_id and user_id == config.admin_id and data.get('sub_type') != 'admin':
                    await db.execute("UPDATE users SET sub_type = 'admin' WHERE user_id = ?", (user_id,))
                    await db.commit()
                    data['sub_type'] = 'admin'
                return data
            elif config.admin_id and user_id == config.admin_id:
                await db.execute("INSERT OR IGNORE INTO users (user_id, sub_type, tokens) VALUES (?, 'admin', 999999)", (user_id,))
                await db.commit()
                return {'user_id': user_id, 'sub_type': 'admin', 'tokens': 999999, 'facts': '{}'}
        return None

    async def add_tokens(self, user_id: int, amount: int):
        """Начисление токенов пользователю."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO users (user_id, tokens) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET tokens = tokens + excluded.tokens
            """, (user_id, amount))
            await db.commit()

    async def spend_tokens(self, user_id: int, amount: int) -> bool:
        """Списание токенов. Возвращает True если успешно, False если недостаточно средств."""
        from bot.config import config
        if config.admin_id and user_id == config.admin_id:
            return True
        async with aiosqlite.connect(self.db_path) as db:
            # Сначала проверяем баланс и тип подписки
            async with db.execute("SELECT tokens, sub_type FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
            
            if not row:
                return False
            
            tokens, sub_type = row
            
            # Безлимит только для администраторов
            if sub_type == 'admin':
                return True
                
            if tokens < amount:
                return False
            
            await db.execute("UPDATE users SET tokens = tokens - ? WHERE user_id = ?", (amount, user_id))
            await db.commit()
            return True

    async def add_subscription_credits(self, user_id: int, months: int = 1, credits: int = 1000):
        """Продление или активация членства Atelier VEO Club с начислением Atelier Credits и поддержкой Rollover."""
        from datetime import datetime, timedelta
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, facts, tokens, sub_type) VALUES (?, '{}', 0, 'free')", 
                (user_id,)
            )
            
            async with db.execute("SELECT sub_expiry FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
            
            now = datetime.now()
            current_expiry = None
            if row and row[0]:
                try:
                    current_expiry = datetime.fromisoformat(row[0].replace('Z', '+00:00'))
                except ValueError:
                    current_expiry = None

            # Несгораемый перенос: старый остаток не сгорает, а суммируется!
            start_date = current_expiry if current_expiry and current_expiry > now else now
            new_expiry = start_date + timedelta(days=30 * months)
            
            await db.execute("""
                UPDATE users SET 
                    sub_type = 'premium', 
                    sub_expiry = ?,
                    tokens = tokens + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (new_expiry.isoformat(), credits, user_id))
            await db.commit()

    async def add_subscription(self, user_id: int, months: int):
        """Продление или активация подписки с начислением токенов."""
        from datetime import datetime, timedelta
        
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем текущую дату окончания
            async with db.execute("SELECT sub_expiry FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
            
            now = datetime.now()
            current_expiry = None
            if row and row[0]:
                try:
                    current_expiry = datetime.fromisoformat(row[0].replace('Z', '+00:00'))
                except ValueError:
                    current_expiry = None

            # Если подписка еще действует, продлеваем её
            start_date = current_expiry if current_expiry and current_expiry > now else now
            new_expiry = start_date + timedelta(days=30 * months)
            
            # Определяем количество токенов для начисления на основе тарифа
            if months == 1:
                tokens_to_add = int(await self.get_setting("tokens_sub_month", "300000"))
            elif months == 6:
                tokens_to_add = int(await self.get_setting("tokens_sub_half_year", "2000000"))
            elif months == 12:
                tokens_to_add = int(await self.get_setting("tokens_sub_year", "4500000"))
            else:
                tokens_to_add = 0
            
            await db.execute("""
                UPDATE users SET 
                    sub_type = 'premium', 
                    sub_expiry = ?,
                    tokens = tokens + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (new_expiry.isoformat(), tokens_to_add, user_id))
            await db.commit()

    async def get_payment_settings(self) -> dict:
        """Получение всех цен и настроек оплаты."""
        keys = [
            'price_month', 'price_half_year', 'price_year',
            'tokens_sub_month', 'tokens_sub_half_year', 'tokens_sub_year',
            'tokens_small', 'price_tokens_small',
            'tokens_medium', 'price_tokens_medium',
            'tokens_large', 'price_tokens_large'
        ]
        settings = {}
        for key in keys:
            val = await self.get_setting(key)
            if val:
                settings[key] = val
        return settings

    async def set_sub_type(self, user_id: int, sub_type: str):
        """Обновление статуса подписки пользователя (free / premium / admin)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET sub_type = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (sub_type, user_id)
            )
            await db.commit()


# Глобальный экземпляр
db = Database()
