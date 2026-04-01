import aiosqlite
import logging

import pytz

# Имя файла базы данных
DB_NAME = "database.db"

logger = logging.getLogger(__name__)

async def init_db():
    """Инициализация БД. Создает таблицы, если их нет."""
    async with aiosqlite.connect(DB_NAME) as db:
        # Таблица пользователей для сохранения языка
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                language TEXT
            )
        """)
        
        # Таблица заявок (ДОБАВЛЕНА КОЛОНКА language)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                language TEXT,
                district TEXT,
                budget INTEGER,
                rooms TEXT,
                term TEXT,
                move_in_date TEXT,
                contact TEXT,
                urgency TEXT,
                payment_status TEXT,
                payment_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
        logger.info("Database initialized successfully.")

async def add_request(user_id, username, language, district, budget, rooms, term, move_in_date, contact, urgency, payment_status):
    # Получаем время в Тбилиси для записи в базу
    georgia_tz = pytz.timezone('Asia/Tbilisi')
    
    """Создает новую заявку и возвращает её ID."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            INSERT INTO requests (
                user_id, username, language, district, budget, 
                rooms, term, move_in_date, contact, urgency, payment_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username, language, district, budget, rooms, term, move_in_date, contact, urgency, payment_status))
        await db.commit()
        return cursor.lastrowid

async def get_request_by_id(request_id: int):
    """Получает заявку по ID. Использует Row для доступа по именам колонок."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM requests WHERE id = ?", (request_id,)) as cursor:
            return await cursor.fetchone()

async def get_request_by_payment_id(payment_id: str):
    """Получает заявку по ID платежа TBC."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM requests WHERE payment_id = ?", (payment_id,)) as cursor:
            return await cursor.fetchone()

async def update_payment_status(request_id: int, status: str):
    """Обновляет статус оплаты (например: 'paid', 'waiting_payment')."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE requests SET payment_status = ? WHERE id = ?", (status, request_id))
        await db.commit()

async def update_payment_id(request_id: int, payment_id: str):
    """Записывает payment_id, полученный от TBC."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE requests SET payment_id = ? WHERE id = ?", (payment_id, request_id))
        await db.commit()

async def get_user_language(user_id: int):
    """Возвращает код языка пользователя (ru, en, ka)."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT language FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def set_user_language(user_id: int, lang: str):
    """Сохраняет выбор языка пользователя."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, language) VALUES (?, ?)", (user_id, lang))
        await db.commit()

# --- ФУНКЦИИ ДЛЯ АДМИН-ПАНЕЛИ ---

async def get_all_requests(limit: int = 10):
    """Возвращает список последних N заявок в виде словарей."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM requests ORDER BY id DESC LIMIT ?", (limit,)
        ) as cursor:
            return await cursor.fetchall()

async def get_unpaid_requests():
    """Возвращает все заявки со статусом ожидания оплаты."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM requests WHERE payment_status = 'waiting_payment' ORDER BY id DESC"
        ) as cursor:
            return await cursor.fetchall()

# --- ДОПОЛНИТЕЛЬНЫЕ УТИЛИТЫ (если были) ---

async def delete_request(request_id: int):
    """Удаление заявки (если нужно для админки)."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM requests WHERE id = ?", (request_id,))
        await db.commit()

async def search_requests(query: str):
    """Поиск по ID, юзернейму или номеру телефона."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        # Ищем совпадение в ID, username или contact
        sql = """
            SELECT * FROM requests 
            WHERE id = ? 
            OR username LIKE ? 
            OR contact LIKE ? 
            ORDER BY id DESC LIMIT 10
        """
        # Подготавливаем параметры для LIKE (%текст%)
        q = f"%{query}%"
        async with db.execute(sql, (query, q, q)) as cursor:
            return await cursor.fetchall()