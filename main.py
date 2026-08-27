import logging
import json
import asyncio
import threading
import os
import re
import html
import random
import time
import datetime
from typing import Optional, Dict, Any, List
from collections import Counter
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaAnimation,
    InputMediaVideo,
) 
from telegram.ext import (
    Application, 
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
from trade_functions import (
    trade_menu,
    select_trade_partner,
    process_partner_selection,
    trade_callback,
    trade_button_callback,
    trade_offer_callback,
    trade_return_callback,
    trade_final_callback,
    _show_trade_card,
    trade_search_callback, 
    search_creatures_for_trade,
)
from telegram.error import NetworkError, TimedOut
from dotenv import load_dotenv
load_dotenv()
# ===== КОНФИГУРАЦИЯ =====

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Токен бота не найден. Проверьте файл .env или переменные окружения.")

INITIAL_ADMIN_ID = (
    "881692999"  # Первый администратор (будет добавлен в список при создании файла)
)
DATA_FILE = "/data/bot_data.json"
ANIMATED_FORMATS = (".mp4", ".gif", ".webm")
AUTO_ANIMATED_RARITIES = ["Highlight"]
SUPER_ADMIN_ID = "881692999"
CLAN_CREATION_COST = 30000
MAX_CLAN_MEMBERS = 7

BASKET_GAME_COST = 800
MAX_BASKET_DAILY_PLAYS = 5
BASKET_HIT_THRESHOLD = 4 

# ===== СОСТОЯНИЯ ДОБАВЛЕНИЯ КАРТЫ =====
ADD_CARD_WAITING_MEDIA = "add_card_waiting_media"
ADD_CARD_WAITING_TITLE = "add_card_waiting_title"
ADD_CARD_WAITING_RARITY = "add_card_waiting_rarity"
ADD_CARD_WAITING_CATCHPHRASE = "add_card_waiting_catchphrase"
ADD_CARD_WAITING_CLASSIC = "add_card_waiting_classic" 

# ===== SUPERMAN BOXES =====
SUPERMAN_HEROES_IMAGE = "https://ibb.co/pBRQHRNC"  # ⭐ ЗАМЕНИТЕ НА URL/FILE_ID КАРТИНКИ БОКСА
SUPERMAN_VILLAIN_IMAGE = "https://ibb.co/zWbrbPBP"  # ⭐ ЗАМЕНИТЕ НА URL/FILE_ID КАРТИНКИ БОКСА

SUPERMAN_HEROES_CARDS = [164, 165, 166, 167, 168, 169, 171]  # ⭐ ЗАПОЛНИТЕ ID КАРТ ГЕРОЕВ
SUPERMAN_VILLAIN_CARDS = [170, 172, 173, 174, 175]  # ⭐ ЗАПОЛНИТЕ ID КАРТ ЗЛОДЕЕВ

# ===== АВАТАРКИ =====
DEFAULT_AVATAR_URL = "https://files.catbox.moe/xtviqr.jpg" 
SEASONAL_AVATAR_URL = "https://files.catbox.moe/502g93.jpg"
SEASON_BOX_AVATAR_URL = "https://files.catbox.moe/24sc2b.jpg"

# ===== АВАТАРКА КЛАНА =====
DEFAULT_CLAN_AVATAR = None  # None означает отсутствие аватарки (используется текст)

MENU_IMAGE = "https://files.catbox.moe/zj1vl8.jpg"
QUESTS_IMAGE = "https://files.catbox.moe/0k82du.jpg"

# ===== НАГРАДЫ ЗА СЖИГАНИЕ =====
BURN_REWARDS = {
    "Common": {"cents": 100, "free_rolls": 0},
    "Rare": {"cents": 200, "free_rolls": 0},
    "Rare Team-up": {"cents": 300, "free_rolls": 0},
    "Epic": {"cents": 0, "free_rolls": 1},
    "Epic Team-up": {"cents": 0, "free_rolls": 3},
    "Legendary": {"cents": 0, "free_rolls": 5},
    "Legendary Team-up": {"cents": 0, "free_rolls": 7},
    "Highlight": {"cents": 0, "free_rolls": 10},
    "Limited": {"cents": 0, "free_rolls": 15},  # бонус для редкой
}

def get_card_media_value(card: Dict) -> str:
    """Возвращает правильный источник медиа для карты (file_id или URL)."""
    media_source = card.get("media_source", "url")
    if media_source == "file_id":
        return card.get("file_id", "")
    return card.get("image_url", "")

# Бонусы по редкостям
RARITY_BONUSES = {
    "Common": {"cents": 100, "points": 200, "probability": 57.93},
    "Rare": {"cents": 250, "points": 300, "probability": 24.3},
    "Rare Team-up": {"cents": 500, "points": 600, "probability": 10},
    "Epic": {"cents": 750, "points": 1000, "probability": 6},
    "Epic Team-up": {"cents": 1000, "points": 1250, "probability": 1},
    "Legendary": {"cents": 1250, "points": 1750, "probability": 0.5},
    "Legendary Team-up": {"cents": 2000, "points": 2500, "probability": 0.2},
    "Highlight": {"cents": 3000, "points": 4000, "probability": 0.07},
    "Limited": {"cents": 0, "points": 0, "probability": 0},
}

# ===== ПРАВИЛА КРАФТА =====
CRAFT_RULES = {
    "Common_to_Rare": {
        "from_rarity": "Common",
        "to_rarity": "Rare",
        "count_needed": 10,
        "button_text": "10 Common → 1 Rare",
    },
    "Rare_to_Epic": {
        "from_rarity": "Rare",
        "to_rarity": "Epic",
        "count_needed": 15,
        "button_text": "15 Rare → 1 Epic",
    },
    "Epic_to_Legendary": {
        "from_rarity": "Epic",
        "to_rarity": "Legendary",
        "count_needed": 20,
        "button_text": "20 Epic → 1 Legendary",
    },
    "Legendary_to_Highlight": {
        "from_rarity": "Legendary",
        "to_rarity": "Highlight",
        "count_needed": 30,
        "button_text": "30 Legendary → 1 Highlight",
    },
    "RareTU_to_EpicTU": {
        "from_rarity": "Rare Team-up",
        "to_rarity": "Epic Team-up",
        "count_needed": 15,
        "button_text": "15 Rare Team-up → 1 Epic Team-up",
    },
    "EpicTU_to_LegendaryTU": {
        "from_rarity": "Epic Team-up",
        "to_rarity": "Legendary Team-up",
        "count_needed": 20,
        "button_text": "20 Epic Team-up → 1 Legendary Team-up",
    },
}

# ===== СЕЗОННЫЕ КВЕСТЫ =====


SEASONAL_QUESTS = {
    1: {
        "id": 1,
        "type": "get_cards",
        "rarity": "Epic",
        "target": 5,
        "reward": {"cents": 2000},
        "desc": "Получить 5 карт редкости Epic через «Получить досье»"
    },
    2: {
        "id": 2,
        "type": "burn_cards",
        "rarity": "Epic",
        "target": 5,
        "reward": {"rep_points": 3000},
        "desc": "Сжечь 5 карт редкости Epic"
    },
    3: {
        "id": 3,
        "type": "get_cards",
        "rarity": "Epic Team-up",
        "target": 2,
        "reward": {"free_rolls": 5},
        "desc": "Получить 2 карты редкости Epic Team-Up через «Получить досье»"
    },
    4: {
        "id": 4,
        "type": "burn_cards",
        "rarity": "Epic Team-up",
        "target": 2,
        "reward": {"cents": 3000},
        "desc": "Сжечь 2 карты редкости Epic Team-Up"
    },
    5: {
        "id": 5,
        "type": "clan",
        "target": 1,
        "reward": {"rep_points": 4000},
        "desc": "Вступить в клан или создать свой клан",
        "check_button": True
    },
    6: {
        "id": 6,
        "type": "get_cards",
        "rarity": "Rare Team-up",
        "target": 30,
        "reward": {"free_rolls": 10},
        "desc": "Получить 30 карт редкости Rare Team-Up через «Получить досье»"
    },
    7: {
        "id": 7,
        "type": "get_cards",
        "rarity": "Legendary",
        "target": 1,
        "reward": {"cents": 4000},
        "desc": "Получить 1 карту редкости Legendary через «Получить досье»"
    },
    8: {
        "id": 8,
        "type": "seasonal_cards",
        "target": 1,
        "reward": {"rep_points": 5000},
        "desc": "Получить все карты из сезонного магазина",
        "check_button": True
    },
    9: {
        "id": 9,
        "type": "burn_cards",
        "rarity": "Legendary",
        "target": 1,
        "reward": {"free_rolls": 15},
        "desc": "Сжечь 1 карту редкости Legendary"
    },
    10: {
        "id": 10,
        "type": "get_cards",
        "rarity": "Highlight",
        "target": 1,
        "reward": {"cents": 5000},
        "desc": "Получить 1 карту редкости Highlight через «Получить досье»"
    },
    11: {
        "id": 11,
        "type": "buy_box",
        "box": "rolls",
        "target": 1,
        "reward": {"rep_points": 6000},
        "desc": "Купить Rolls-Box"
    },
    12: {
        "id": 12,
        "type": "buy_box",
        "box": "classic",
        "target": 1,
        "reward": {"free_rolls": 30, "avatar": SEASONAL_AVATAR_URL},
        "desc": "Купить Classic-Box"
    },
}

CRAFT_ITEMS_PER_PAGE = 5  # Сколько карт показывать на странице

# ===== КОНСТАНТЫ ДАРТСА =====
DARTS_GAME_COST = 1000
MAX_DARTS_DAILY_PLAYS = 5
DARTS_WIN_THRESHOLD = 10

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot_errors.log"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

def load_data() -> Dict[str, Any]:
    """Загружает данные из файла или создает новую структуру."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Инициализируем активные трейды если нет
            if "active_trades" not in data:
                data["active_trades"] = {}

            if "promo_codes" not in data:
                data["promo_codes"] = {}

            if "seasonal_cards" not in data:
                data["seasonal_cards"] = {}  # {card_id: price}

            if "clans" not in data:
                data["clans"] = {}

            for clan in data.get("clans", {}).values():
                if "max_members" not in clan:
                    clan["max_members"] = MAX_CLAN_MEMBERS

            if "user_clan" not in data:
                data["user_clan"] = {}  # {user_id: clan_name}

            for user_id, user_data in data.get("users", {}).items():
                if "clan_invite_pending" not in user_data:
                    user_data["clan_invite_pending"] = None  # Для хранения ожидающего приглашения
                if "weekly_quests" not in user_data:
                    user_data["weekly_quests"] = []
                if "weekly_quests_last_reset_year" not in user_data:
                    user_data["weekly_quests_last_reset_year"] = 0
                if "weekly_quests_last_reset_week" not in user_data:
                    user_data["weekly_quests_last_reset_week"] = 0
                if "daily_quests_streak" not in user_data:
                    user_data["daily_quests_streak"] = 0
                if "last_streak_date" not in user_data:
                    user_data["last_streak_date"] = ""
            
            for user_id, user_data in data.get("users", {}).items():
                if "last_card_time" not in user_data:
                    user_data["last_card_time"] = 0
                if "free_rolls" not in user_data:
                    user_data["free_rolls"] = 0
                if "last_dice_time" not in user_data:
                    user_data["last_dice_time"] = 0
                if "casino_attempts" not in user_data:
                    user_data["casino_attempts"] = 5
                if "basket_plays" not in user_data:
                    user_data["basket_plays"] = 0
                if "darts_plays" not in user_data:
                    user_data["darts_plays"] = 0
                if "darts_last_reset" not in user_data:
                    user_data["darts_last_reset"] = 0
                if "basket_last_reset" not in user_data:
                    user_data["basket_last_reset"] = 0
                if "last_casino_reset" not in user_data:
                    user_data["last_casino_reset"] = 0
                if "used_promo_codes" not in user_data:
                    user_data["used_promo_codes"] = []
                if "referral_invites" not in user_data:
                    user_data["referral_invites"] = []
                if "referral_rewards_claimed" not in user_data:
                    user_data["referral_rewards_claimed"] = []
                if "daily_quests" not in user_data:
                    user_data["daily_quests"] = []
                if "daily_quests_last_reset" not in user_data:
                    user_data["daily_quests_last_reset"] = 0
                if "rolls_box_price" not in user_data:
                    user_data["rolls_box_price"] = 25000
                if "pending_season_boxes" not in user_data:
                    user_data["pending_season_boxes"] = 0
                if "pending_superman_heroes_boxes" not in user_data:
                    user_data["pending_superman_heroes_boxes"] = 0
                if "pending_superman_villain_boxes" not in user_data:
                    user_data["pending_superman_villain_boxes"] = 0
                # ⭐ УДАЛИТЬ СТАРОЕ ПОЛЕ У ВСЕХ ПОЛЬЗОВАТЕЛЕЙ ⭐
                if "pending_supergirl_boxes" in user_data:
                    del user_data["pending_supergirl_boxes"]
                if "has_batpass" not in user_data:
                    user_data["has_batpass"] = False
                if "batpass_expires_at" not in user_data:
                    user_data["batpass_expires_at"] = 0
                if "batpass_privileges" not in user_data:
                    user_data["batpass_privileges"] = {
                        "reduced_cooldown": True,      # 2.5 часа вместо 3 часов
                        "extra_dice_rolls": True,      # 2 броска кубика в неделю
                        "free_clan_creation": True,    # Бесплатное создание клана
                        "extra_casino_attempts": True, # 7 попыток в казино вместо 5
                    }
                # ⭐ НОВОЕ: Счётчик бросков кубика за неделю ⭐
                if "weekly_dice_rolls" not in user_data:
                    user_data["weekly_dice_rolls"] = 1  # 1 бросок по умолчанию
                if "last_dice_week_reset" not in user_data:
                    user_data["last_dice_week_reset"] = 0
                if "last_daily_activity" not in user_data:
                    user_data["last_daily_activity"] = None  # Дата в формате "YYYY-MM-DD" или None
                if "registered_at" not in user_data:
                    user_data["registered_at"] = None  # Дата регистрации в формате "YYYY-MM-DD"
                if "seasonal_quests" not in user_data:
                    user_data["seasonal_quests"] = {"completed": [], "progress": {}}
                # ⭐ НОВОЕ: Миграция аватарок ⭐
                if "avatar_url" not in user_data:
                    user_data["avatar_url"] = DEFAULT_AVATAR_URL
                if "avatars" not in user_data:
                    user_data["avatars"] = [DEFAULT_AVATAR_URL]

                for card in data.get("cards", []):
                    if "is_classic" not in card:
                        card["is_classic"] = False
            return data
            
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {e}")
            return {
                "users": {},
                "cards": [],
                "season": 1,
                "admins": [INITIAL_ADMIN_ID],
                "active_trades": {},
            }
    
    return {
        "users": {},
        "cards": [],
        "season": 1,
        "admins": [INITIAL_ADMIN_ID],
        "active_trades": {},
    }

def check_casino_reset(user_data: Dict) -> None:
    """Проверяет и выполняет сброс попыток казино в 00:00 МСК."""
    from datetime import datetime, timezone, timedelta
    msk_tz = timezone(timedelta(hours=3))
    now = datetime.now(msk_tz)
    
    last_reset = user_data.get("last_casino_reset", 0)
    
    # Определяем начало текущего дня (00:00 МСК)
    current_day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    current_day_start_ts = int(current_day_start.timestamp())
    
    if current_day_start_ts > last_reset:
        # ⭐ НОВОЕ: Проверяем Бэт-пасс ⭐
        max_attempts = 7 if is_batpass_active(user_data) else 5
        
        user_data["casino_attempts"] = max_attempts
        user_data["last_casino_reset"] = current_day_start_ts

def save_data(data: Dict[str, Any]) -> None:
    """Сохраняет данные в файл, компактно оформляя списки."""
    try:
        # 1. Сначала превращаем данные в JSON строку с отступами
        json_str = json.dumps(data, ensure_ascii=False, indent=4)
        
        # 2. Используем регулярное выражение, чтобы найти все списки [...] 
        # и удалить внутри них переносы строк, оставив только пробелы
        # Это сделает вид: "cards": [1, 2, 3, 4, 5] вместо многострочного списка
        
        def replace_newlines_in_lists(match):
            content = match.group(0)
            # Заменяем переносы строк и табуляции на пробелы внутри найденного блока
            cleaned = re.sub(r'[\n\r\t]+', ' ', content)
            # Убираем лишние пробелы
            cleaned = re.sub(r'\s+', ' ', cleaned)
            return cleaned

        # Ищем паттерны списков. Внимание: это упрощенный регекс, он работает для простых списков чисел/строк
        # Для вложенных структур может потребоваться более сложный парсер, но для ID карт подойдет
        json_str_compact = re.sub(r'\[.*?\]', replace_newlines_in_lists, json_str, flags=re.DOTALL)

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            f.write(json_str_compact)
            f.flush()
            os.fsync(f.fileno())
            
    except Exception as e:
        logger.error(f"Ошибка сохранения данных: {e}")


def is_admin(user_id: str, data: Dict[str, Any]) -> bool:
    """Проверяет, является ли пользователь администратором."""
    admins = data.get("admins", [])
    return user_id in admins


def find_card_by_id(card_id: int, cards: List[Dict]) -> Optional[Dict]:
    """Находит карточку по ID."""
    for card in cards:
        if card["id"] == card_id:
            return card
    return None

def create_cards_keyboard(
    current_index: int, total_cards: int
) -> Optional[InlineKeyboardMarkup]:
    """Создает инлайн-клавиатуру для бесконечной навигации."""
    if total_cards <= 0:
        return None
        
    nav_buttons = []

    # Кнопка "<" появляется только если это не первая карта
    if new_index > 0:
        nav_buttons.append(
            InlineKeyboardButton("<", callback_data=f"card_prev_{new_index}")
        )

    # Кнопка с номером карты
    nav_buttons.append(
        InlineKeyboardButton(f"{new_index + 1}/{total_cards}", callback_data="card_info")
    )

    # Кнопка ">" появляется только если это не последняя карта
    if new_index < total_cards - 1:
        nav_buttons.append(
            InlineKeyboardButton(">", callback_data=f"card_next_{new_index}")
        )
    return InlineKeyboardMarkup([nav_buttons])

def determine_media_type(url: str, rarity: str) -> str:
    # Если редкость помечена как анимация
    if rarity in AUTO_ANIMATED_RARITIES:
        return "animation"
    
    # Если ссылка ведёт на видеофайл
    if any(url.lower().endswith(ext) for ext in (".mp4", ".mov", ".webm", ".gif")):
        return "animation"  # В Telegram "animation" = inline-видео без звука, отлично для превью
        
    return "photo"

def generate_card_caption(
    card: Dict,
    user_data: Optional[Dict] = None,
    count: int = 1,
    show_bonus: bool = False,
) -> str:
    """Генерирует описание карточки с количеством дубликатов и цитатой."""
    # ⭐ БАЗОВЫЙ CAPTION ⭐
    if user_data is None:
        caption = f"{card['title']}"
    else:
        caption = f"🔍 У Вас новый\n подозреваемый!\n\n{html.escape(card['title'])}"

    caption += f"\nРедкость: {card['rarity']}"
    
    # ⭐ НОВОЕ: ЦИТАТА ЧЕРЕЗ BLOCKQUOTE (HTML-тег) ⭐
    if card.get("catchphrase"):
        # ⭐ Telegram HTML поддерживает обычные \n для переноса строк ⭐
        escaped_phrase = html.escape(card['catchphrase'])
        caption += f"\n<blockquote><i>{escaped_phrase}</i></blockquote>"
        
    # ⭐ ПОКАЗЫВАЕМ БОНУСЫ ТОЛЬКО ПРИ ПОЛУЧЕНИИ НОВОЙ КАРТЫ ⭐
    if show_bonus and user_data is not None:
        bonus = RARITY_BONUSES.get(card["rarity"], {"cents": 0, "points": 0})
        caption += f"\n\n💰 +{bonus['cents']} бэт-коинов\n💥 +{bonus['points']} очков репутации"
        
    # ⭐ ДОБАВЛЯЕМ КОЛИЧЕСТВО, ЕСЛИ ЕСТЬ ДУБЛИКАТЫ ⭐
    if count > 1:
        caption += f"\n📦 Количество: {count} шт."
        
    # ⭐ ДОБАВЛЯЕМ ОПЫТ ТОЛЬКО ЕСЛИ ЕСТЬ user_data ⭐
    if user_data is not None:
        caption += (
            f"\n\nОчков репутации в этом сезоне: {user_data.get('season_points', 0)}"
            f"\nОчков репутации за все время: {user_data.get('total_points', 0)}"
        )
    return caption

async def send_card(
    update_or_chat_id,
    card: Dict,
    context: ContextTypes.DEFAULT_TYPE,
    caption: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    chat_id: Optional[int] = None
) -> None:
    """Отправляет карту с учётом источника медиа (URL или file_id)."""
    if isinstance(update_or_chat_id, Update):
        chat_id = update_or_chat_id.effective_chat.id
    if chat_id is None:
        return
    
    # ⭐ НОВОЕ: Определяем источник медиа ⭐
    media_source = card.get("media_source", "url")
    
    try:
        if media_source == "file_id":
            # ⭐ ОТПРАВКА ПО FILE_ID ⭐
            file_id = card.get("file_id")
            if not file_id:
                logger.error(f"У карты {card.get('id')} нет file_id!")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ Ошибка: у карты #{card.get('id')} отсутствует файл"
                )
                return
            
            if card.get("media_type") == "animation":
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=file_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                    supports_streaming=True
                )
            else:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=file_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
        else:
            # ⭐ СТАРАЯ ЛОГИКА: ОТПРАВКА ПО URL ⭐
            url = card["image_url"]
            if card.get("media_type") == "animation" or url.lower().endswith((".mp4", ".webm")):
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=url,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                    supports_streaming=True
                )
            else:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=url,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
    except Exception as e:
        logger.error(f"Ошибка отправки карты: {e}")
        logger.error(f"URL/file_id: {card.get('image_url') or card.get('file_id')}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Не удалось загрузить карту #{card.get('id')}"
        )

def is_batpass_active(user_data: Dict) -> bool:
    """Проверяет, активен ли Бэт-пасс у игрока."""
    if not user_data.get("has_batpass", False):
        return False
    
    expires_at = user_data.get("batpass_expires_at", 0)
    if expires_at == 0:
        return False
    
    from datetime import datetime, timezone, timedelta
    msk_tz = timezone(timedelta(hours=3))
    now = int(datetime.now(msk_tz).timestamp())
    
    return now < expires_at
        
async def edit_card_message(query, card: Dict, caption: str, reply_markup: InlineKeyboardMarkup) -> None:
    """Редактирует сообщение с карточкой (поддерживает URL и file_id)."""
    try:
        media_source = card.get("media_source", "url")
        
        if media_source == "file_id":
            # ⭐ РЕДАКТИРОВАНИЕ С FILE_ID ⭐
            file_id = card.get("file_id")
            if card.get("media_type") == "animation":
                media = InputMediaAnimation(
                    media=file_id,
                    caption=caption,
                    parse_mode="HTML"
                )
            else:
                media = InputMediaPhoto(
                    media=file_id,
                    caption=caption,
                    parse_mode="HTML"
                )
        else:
            # ⭐ СТАРАЯ ЛОГИКА: С URL ⭐
            if card.get("media_type") == "animation":
                media = InputMediaAnimation(
                    media=card["image_url"],
                    caption=caption,
                    parse_mode="HTML"
                )
            else:
                media = InputMediaPhoto(
                    media=card["image_url"],
                    caption=caption,
                    parse_mode="HTML"
                )
        
        await query.edit_message_media(media=media, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Ошибка редактирования: {e}")
        # Fallback: удаляем старое и отправляем новое
        try:
            await query.message.delete()
        except:
            pass
        await send_card(
            query, card,
            context=query.get_bot() if hasattr(query, 'get_bot') else None,
            caption=caption,
            reply_markup=reply_markup,
            chat_id=query.message.chat_id
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start с поддержкой реферальной системы."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        
        # Инициализация пользователя, если его нет
        if user_id not in data["users"]:

            from datetime import datetime, timezone, timedelta
            msk_tz = timezone(timedelta(hours=3))
            today_str = datetime.now(msk_tz).strftime("%Y-%m-%d")
            
            data["users"][user_id] = {
                "username": update.effective_user.username or "",
                "first_name": update.effective_user.first_name or "",
                "last_name": update.effective_user.last_name or "",
                "cards": [],
                "total_points": 0,
                "season_points": 0,
                "cents": 0,
                "last_card_time": 0,
                "free_rolls": 0,
                "last_dice_time": 0,
                "referral_invites": [],
                "referral_rewards_claimed": [],
                "avatar_url": DEFAULT_AVATAR_URL,
                "avatars": [DEFAULT_AVATAR_URL], 
                "last_daily_activity": None,
                "registered_at": today_str, 
            }
            save_data(data)

        user_data = data["users"][user_id]

        # ⭐ ОБРАБОТКА РЕФЕРАЛЬНОЙ ССЫЛКИ ⭐
        referrer_id = None
        # ⭐ ИСПРАВЛЕНИЕ: Проверяем, является ли пользователь НОВЫМ ⭐
        is_new_user = user_id not in data["users"]

        # Обработка реферальной ссылки — ТОЛЬКО для новых пользователей
        if is_new_user and context.args and context.args[0].startswith("ref_"):
            referrer_id = context.args[0].replace("ref_", "")
            if referrer_id and referrer_id in data["users"] and referrer_id != user_id:
                referrer_data = data["users"][referrer_id]
        
                # Инициализация полей реферала у приглашающего (на случай старых пользователей)
                if "referral_invites" not in referrer_data:
                    referrer_data["referral_invites"] = []
                if "referral_rewards_claimed" not in referrer_data:
                    referrer_data["referral_rewards_claimed"] = []
        
                # Если пользователь еще не был приглашен этим реферером
                if user_id not in referrer_data["referral_invites"]:
                    referrer_data["referral_invites"].append(user_id)
            
                    new_user_name = update.effective_user.username or update.effective_user.first_name
            
                    # 1. Уведомление рефереру о новом игроке
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 По вашей реферальной ссылке перешёл новый игрок: **@{new_user_name}**!",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.warning(f"Не удалось уведомить реферера {referrer_id}: {e}")
            
                    # 2. Проверка и выдача наград
                    invite_count = len(referrer_data["referral_invites"])
                    claimed = referrer_data["referral_rewards_claimed"]
                    reward_card = None
                    reward_milestone = 0
            
                    if invite_count >= 1 and 1 not in claimed:
                        reward_card = get_random_available_card_by_rarity(data, "Epic")
                        reward_milestone = 1
                    elif invite_count >= 3 and 3 not in claimed:
                        reward_card = get_random_available_card_by_rarity(data, "Epic Team-up")
                        reward_milestone = 3
            
                    if reward_card:
                        claimed.append(reward_milestone)
                        referrer_data["referral_rewards_claimed"] = claimed
                        referrer_data["cards"].append(reward_card["id"])
                        save_data(data)
                
                        try:
                            caption = f"🎁 **Награда за реферала!**\nВы получили случайную карту редкости **{reward_card['rarity']}** за {reward_milestone}-го приглашенного!"
                            # Создаем фиктивный update для send_card, если нужно, или отправляем напрямую
                            await context.bot.send_photo(
                                chat_id=referrer_id,
                                photo=reward_card["image_url"],
                                caption=caption,
                                parse_mode="Markdown"
                            )
                        except Exception as e:
                            logger.error(f"Ошибка отправки реферальной награды: {e}")
                    else:
                        save_data(data)

        # Показываем главное меню
        keyboard = [
            [KeyboardButton("🔍 Получить досье")],
            [KeyboardButton("📁 Мой архив")],
            [KeyboardButton("📋 Меню")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        welcome_text = f"🏠 Главное меню\nДобро пожаловать, {update.effective_user.first_name}! Используйте кнопки ниже:"
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Ошибка в start: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список команд."""
    try:
        user_id = str(update.effective_user.id)
        response = ""
        # Безопасная проверка админа
        try:
            data = load_data()
            admin_list = data.get("admins", [])
            admin = user_id in admin_list
        except Exception as e:
            logger.error(f"Ошибка проверки админа: {e}")
            admin = False
        
        # Админ-команды
        if admin:
            response = "⚙️ Админ-команды:\n"
            response += "/add_card - добавить карточку в систему\n"
            response += "/edit_card - редактировать карту\n"
            response += "/card_info - информация о карте\n"
            response += "/add_card_to_player - добавить карту игроку\n"
            response += "/add_rolls_to_player - добавить попытки игроку\n"
            response += "/reset_season_points [ID] - сбросить поинты за сезон\n"
            response += "/cards - список всех карт\n"
            response += "/disabled_cards - выключенные карты\n"
            response += "/toggle_card [ID] - вкл/выкл карту\n"
            response += "/delete_card [ID] - удалить карту\n"
            response += "/broadcast [текст] - рассылка всем игрокам\n"
            response += "/reset_all_cards - сбросить все карты\n"
            response += "/reset_user [ID] - сбросить карты игрока\n"
            response += "/check_cards - статистика карт\n"
            response += "/list_admins - список админов\n"
            response += "/add_admin [ID] - добавить админа\n"
            response += "/remove_admin [ID] - удалить админа\n"
            response += "/create_promo [КОД] [ID/random] [лимит] - создать промокод\n"
            response += "/delete_promo [КОД] - удалить промокод\n"
            response += "/list_promo - список всех промокодов\n"
            response += "/add_seasonal [ID] [стоимость] - Добавить карту в список сезонных\n"
            response += "/remove_seasonal [ID] - Убрать из списка сезонных\n"
            response += "/give_season_box [@никнейм] - Выдать игроку сезонный бокс\n"
            response += "/add_cents_to_player [ID] [количество] - добавить/списать бэт-коины\n"
            response += "/daily_stats - статистика активности за сегодня\n" 
            response += "/check_probabilities - проверить вероятности выпадения карт\n"
            response += "/give_batpass [@никнейм] [дней] - выдать Бэт-пасс\n"
            response += "/remove_batpass [@никнейм] - отозвать Бэт-пасс\n"
            response += "/give_card_to_batpass [ID_карты] [количество] - выдать карту всем с Бэт-пассом\n"
            response += "/give_superman_box heroes @username\n"
            response += "/give_superman_box villain @username\n"
            
            
        response += "💡 Нужна помощь?\n"
        response += "Напишите администратору бота."
        
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Ошибка в help: {e}")
        await update.message.reply_text("❌ Ошибка при показе помощи")

async def show_user_cards(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню выбора способа просмотра коллекции."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text("У вас пока нет существ!")
            else:
                await update.message.reply_text("У вас пока нет существ!")
            return
        
        user_card_ids = user_data["cards"]
        card_counts = Counter(user_card_ids)
        unique_card_ids = list(card_counts.keys())
        
        # Считаем карты по редкостям
        rarity_cards = {}
        for card_id in unique_card_ids:
            card = find_card_by_id(card_id, data["cards"])
            if card:
                rarity = card.get("rarity", "Classic")
                if rarity not in rarity_cards:
                    rarity_cards[rarity] = []
                rarity_cards[rarity].append((card_id, card_counts[card_id]))
        
        if not rarity_cards:
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text("У вас пока нет существ!")
            else:
                await update.message.reply_text("У вас пока нет существ!")
            return
        
        # ⭐ СОЗДАЁМ МЕНЮ ВЫБОРА СПОСОБА ПРОСМОТРА ⭐
        keyboard = [
            [InlineKeyboardButton("📊 По редкости", callback_data="barracks_rarity")],
            [InlineKeyboardButton("📋 Все карты", callback_data="barracks_all")],
        ]
        
        # ⭐ ПРОВЕРКА: callback или сообщение ⭐
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            try:
                await query.message.delete()
            except:
                pass
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(
                    "📁 Мой архив\n\n"
                    "Выберите способ просмотра:\n"
                    "• 📊 По редкости\n"
                    "• 📋 Все карты"
                ),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    "📁 Мой архив\n\n"
                    "Выберите способ просмотра:\n"
                    "• 📊 По редкости\n"
                    "• 📋 Все карты"
                ),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
    except Exception as e:
        logger.error(f"Ошибка при показе меню существ: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("Произошла ошибка")
            
async def show_cards_by_rarity(update: Update, context: ContextTypes.DEFAULT_TYPE, rarity: str, start_index: int = 0) -> None:
    """Показывает карты конкретной редкости."""
    try:
        query = update.callback_query if hasattr(update, 'callback_query') else None
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            if query:
                await query.edit_message_text("У вас нет существ!")
            else:
                await update.message.reply_text("У вас нет существ!")
            return
        
        user_card_ids = user_data["cards"]
        card_counts = Counter(user_card_ids)
        
        # Фильтруем карты по редкости
        rarity_cards = []
        for card_id, count in card_counts.items():
            card = find_card_by_id(card_id, data["cards"])
            if card and card.get("rarity") == rarity:
                rarity_cards.append((card_id, count))
        
        if not rarity_cards:
            msg = f"У вас нет карт редкости {rarity}!"
            if query:
                await query.edit_message_text(msg)
            else:
                await update.message.reply_text(msg)
            return
        
        # Сортируем по ID
        rarity_cards.sort(key=lambda x: x[0])
        total_cards = len(rarity_cards)
        
        # Корректировка индекса
        start_index = max(0, min(start_index, total_cards - 1))
        current_card_id, count = rarity_cards[start_index]
        card = find_card_by_id(current_card_id, data["cards"])
        
        if not card:
            if query:
                await query.edit_message_text("❌ Ошибка: карта не найдена!")
            else:
                await update.message.reply_text("❌ Ошибка: карта не найдена!")
            return
        
        # ⭐ ИСПРАВЛЕНИЕ: Используем HTML вместо Markdown ⭐
        caption = generate_card_caption(card, user_data, count=count, show_bonus=False)
        
        # ⭐ КЛАВИАТУРА С КНОПКОЙ ПОИСКА ⭐
        nav_buttons = []
        if start_index > 0:
            nav_buttons.append(InlineKeyboardButton("<", callback_data=f"card_prev_{rarity}_{start_index - 1}"))
        
        nav_buttons.append(InlineKeyboardButton(f"{start_index + 1}/{total_cards}", callback_data="card_info"))
        
        if start_index < total_cards - 1:
            nav_buttons.append(InlineKeyboardButton(">", callback_data=f"card_next_{rarity}_{start_index + 1}"))
        
        keyboard = [
            nav_buttons,
            [InlineKeyboardButton("🔍 Поиск", callback_data=f"archive_search_{rarity}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="archive_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            try:
                # ⭐ УНИВЕРСАЛЬНАЯ ЛОГИКА: file_id или URL ⭐
                media_source = card.get("media_source", "url")
                media_value = card.get("file_id") if media_source == "file_id" else card["image_url"]

                if card.get("media_type") == "animation":
                    media = InputMediaAnimation(media=media_value, caption=caption, parse_mode="HTML")
                else:
                    media = InputMediaPhoto(media=media_value, caption=caption, parse_mode="HTML")
                await query.edit_message_media(media=media, reply_markup=reply_markup)
            except Exception as e:
                error_str = str(e)
                if "Message is not modified" in error_str:
                    return
                # ⭐ НОВОЕ: Если не удалось отредактировать (например, это текст), отправляем новое сообщение ⭐
                logger.warning(f"Не удалось отредактировать сообщение: {e}. Отправляю новое.")
                try:
                    await query.message.delete()
                except:
                    pass
                if card.get("media_type") == "animation":
                    await context.bot.send_animation(
                        chat_id=query.message.chat_id,
                        animation=card["image_url"],
                        caption=caption,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                else:
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=card["image_url"],
                        caption=caption,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                await query.edit_message_media(media=media, reply_markup=reply_markup)
            except Exception as e:
                if "Message is not modified" not in str(e):
                    logger.error(f"Ошибка редактирования: {e}")
        else:
            await update.message.reply_photo(
                photo=card["image_url"],
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Ошибка в show_cards_by_rarity: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("Произошла ошибка")

async def show_all_cards(update: Update, context: ContextTypes.DEFAULT_TYPE, start_index: int = 0) -> None:
    """Показывает все карты пользователя."""
    try:
        query = update.callback_query if hasattr(update, 'callback_query') else None
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            if query:
                await query.edit_message_text("У вас нет существ!")
            else:
                await update.message.reply_text("У вас нет существ!")
            return
        
        user_card_ids = user_data["cards"]
        card_counts = Counter(user_card_ids)
        unique_card_ids = list(card_counts.keys())
        
        if not unique_card_ids:
            if query:
                await query.edit_message_text("У вас нет существ!")
            else:
                await update.message.reply_text("У вас нет существ!")
            return
        
        # Сортируем по ID
        unique_card_ids.sort()
        total_cards = len(unique_card_ids)
        
        # Корректировка индекса
        start_index = max(0, min(start_index, total_cards - 1))
        current_card_id = unique_card_ids[start_index]
        card = find_card_by_id(current_card_id, data["cards"])
        
        if not card:
            if query:
                await query.edit_message_text("❌ Ошибка: карта не найдена!")
            else:
                await update.message.reply_text("❌ Ошибка: карта не найдена!")
            return
        
        count = card_counts[current_card_id]
        # ⭐ ИСПРАВЛЕНИЕ: Используем HTML ⭐
        caption = generate_card_caption(card, user_data, count=count, show_bonus=False)
        
        # ⭐ КЛАВИАТУРА С КНОПКОЙ ПОИСКА ⭐
        nav_buttons = []
        if start_index > 0:
            nav_buttons.append(InlineKeyboardButton("<", callback_data=f"card_prev_all_{start_index - 1}"))
        
        nav_buttons.append(InlineKeyboardButton(f"{start_index + 1}/{total_cards}", callback_data="card_info"))
        
        if start_index < total_cards - 1:
            nav_buttons.append(InlineKeyboardButton(">", callback_data=f"card_next_all_{start_index + 1}"))
        
        keyboard = [
            nav_buttons,
            [InlineKeyboardButton("🔍 Поиск", callback_data="archive_search_all")],
            [InlineKeyboardButton("🔙 Назад", callback_data="archive_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            try:
                # ⭐ УНИВЕРСАЛЬНАЯ ЛОГИКА: file_id или URL ⭐
                media_source = card.get("media_source", "url")
                media_value = card.get("file_id") if media_source == "file_id" else card["image_url"]

                if card.get("media_type") == "animation":
                    media = InputMediaAnimation(media=media_value, caption=caption, parse_mode="HTML")
                else:
                    media = InputMediaPhoto(media=media_value, caption=caption, parse_mode="HTML")
                await query.edit_message_media(media=media, reply_markup=reply_markup)
            except Exception as e:
                error_str = str(e)
                if "Message is not modified" in error_str:
                    return
                # ⭐ НОВОЕ: Если не удалось отредактировать (например, это текст), отправляем новое сообщение ⭐
                logger.warning(f"Не удалось отредактировать сообщение: {e}. Отправляю новое.")
                try:
                    await query.message.delete()
                except:
                    pass
                if card.get("media_type") == "animation":
                    await context.bot.send_animation(
                        chat_id=query.message.chat_id,
                        animation=card["image_url"],
                        caption=caption,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                else:
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=card["image_url"],
                        caption=caption,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
    except Exception as e:
        logger.error(f"Ошибка в show_all_cards: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("Произошла ошибка")

async def archive_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начинает процесс поиска карт в архиве."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        
        # ⭐ ИСПРАВЛЕНИЕ: Извлекаем search_type из callback_data ⭐
        # callback_data = "archive_search_all" или "archive_search_Common" и т.д.
        search_type = query.data.replace("archive_search_", "")
        
        # ⭐ Сохраняем состояние поиска ⭐
        context.user_data[user_id] = {
            "step": "archive_search",
            "search_type": search_type  # "all" или конкретная редкость
        }
        
        # ⭐ Определяем текст подсказки ⭐
        if search_type == "all":
            hint = "Среди всех карт"
        else:
            hint = f"Среди карт редкости {search_type}"
        
        await query.message.reply_text(
            f"🔍 **Поиск карт**\n\n"
            f"📂 {hint}\n\n"
            f"Введите часть названия карты:\n"
            f"❌ Для отмены: /cancel",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в archive_search_start: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def archive_search_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выполняет поиск карт по названию."""
    try:
        user_id = str(update.effective_user.id)
        text = update.message.text.strip()
        
        if user_id not in context.user_data:
            await update.message.reply_text("❌ Сессия поиска истекла!")
            return
        
        search_info = context.user_data[user_id]
        if search_info.get("step") != "archive_search":
            return
        
        # ⭐ Обработка отмены ⭐
        if text.lower() == "/cancel":
            del context.user_data[user_id]
            await update.message.reply_text("❌ Поиск отменён.")
            return
        
        search_query = text.lower()
        search_type = search_info.get("search_type", "all")
        
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            del context.user_data[user_id]
            await update.message.reply_text("❌ У вас нет карт!")
            return
        
        user_card_ids = user_data["cards"]
        card_counts = Counter(user_card_ids)
        
        # ⭐ Фильтруем карты ⭐
        filtered_cards = []
        for card_id, count in card_counts.items():
            card = find_card_by_id(card_id, data["cards"])
            if not card:
                continue
            
            # Фильтр по редкости (если не "all")
            if search_type != "all" and card.get("rarity") != search_type:
                continue
            
            # Фильтр по названию
            if search_query in card["title"].lower():
                filtered_cards.append((card_id, count))
        
        if not filtered_cards:
            await update.message.reply_text(
                f"❌ Карт с названием \"{text}\" не найдено!\n"
                "Попробуйте другой запрос или нажмите /cancel для отмены."
            )
            return
        
        # ⭐ Сортируем и показываем первую карту ⭐
        filtered_cards.sort(key=lambda x: x[0])
        
        # ⭐ Сохраняем результаты поиска ⭐
        search_info["step"] = "archive_search_results"
        search_info["filtered_cards"] = filtered_cards
        search_info["current_index"] = 0
        
        current_card_id, count = filtered_cards[0]
        card = find_card_by_id(current_card_id, data["cards"])
        
        caption = generate_card_caption(card, user_data, count=count, show_bonus=False)
        caption += f"\n\n🔍 Найдено карт: {len(filtered_cards)}\nПо запросу: \"{text}\""
        
        # ⭐ Клавиатура для результатов поиска ⭐
        nav_buttons = []
        if len(filtered_cards) > 1:
            nav_buttons.append(InlineKeyboardButton("<", callback_data="archive_search_prev_0"))
            nav_buttons.append(InlineKeyboardButton(f"1/{len(filtered_cards)}", callback_data="archive_search_info"))
            nav_buttons.append(InlineKeyboardButton(">", callback_data="archive_search_next_0"))
        
        keyboard = [
            nav_buttons,
            [InlineKeyboardButton("🔍 Новый поиск", callback_data=f"archive_search_{search_type}")],
            [InlineKeyboardButton("❌ Отмена поиска", callback_data="archive_search_cancel")]
        ]
        
        # ⭐ ИСПРАВЛЕНИЕ: Универсальная логика ⭐
        media_source = card.get("media_source", "url")
        media_value = card.get("file_id") if media_source == "file_id" else card["image_url"]

        if card.get("media_type") == "animation":
            await update.message.reply_animation(
                animation=media_value,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
        else:
            await update.message.reply_photo(
                photo=media_value,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
        
    except Exception as e:
        logger.error(f"Ошибка в archive_search_execute: {e}")
        if user_id in context.user_data:
            del context.user_data[user_id]
        await update.message.reply_text("❌ Ошибка при поиске карт")

async def archive_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок навигации по результатам поиска."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        
        if user_id not in context.user_data:
            await query.edit_message_text("❌ Сессия поиска истекла!")
            return
        
        search_info = context.user_data[user_id]
        if search_info.get("step") != "archive_search_results":
            await query.edit_message_text("❌ Поиск не активен!")
            return
        
        # ⭐ Отмена поиска ⭐
        if query.data == "archive_search_cancel":
            del context.user_data[user_id]
            # ✅ Правильно: либо удаляем сообщение, либо редактируем caption
            try:
                await query.message.delete()
            except:
                # Если не удалось удалить, редактируем caption
                await query.edit_message_caption(
                    caption="❌ Поиск отменён.",
                    reply_markup=None
                )
            return
        
        # ⭐ Информация ⭐
        if query.data == "archive_search_info":
            await query.answer("Используйте < > для навигации", show_alert=False)
            return
        
        # ⭐ Навигация ⭐
        if query.data.startswith("archive_search_prev_") or query.data.startswith("archive_search_next_"):
            action = "prev" if "prev" in query.data else "next"
            current_index = search_info.get("current_index", 0)
            filtered_cards = search_info.get("filtered_cards", [])
    
            if not filtered_cards:
                await query.answer("❌ Карты не найдены!", show_alert=True)
                return
    
            if action == "prev":
                new_index = current_index - 1
            else:
                new_index = current_index + 1
    
            # Проверка границ
            if new_index < 0 or new_index >= len(filtered_cards):
                await query.answer("Нельзя пролистнуть дальше", show_alert=True)
                return
    
            search_info["current_index"] = new_index
    
            current_card_id, count = filtered_cards[new_index]
            data = load_data()
            user_data = data["users"].get(user_id)
            card = find_card_by_id(current_card_id, data["cards"])
    
            if not card:
                await query.edit_message_text("❌ Карта не найдена!")
                return
    
            caption = generate_card_caption(card, user_data, count=count, show_bonus=False)
            caption += f"\n\n🔍 Найдено карт: {len(filtered_cards)}"
    
            # ⭐ Клавиатура ⭐
            nav_buttons = []
            if new_index > 0:
                nav_buttons.append(InlineKeyboardButton("<", callback_data=f"archive_search_prev_{new_index}"))
    
            nav_buttons.append(InlineKeyboardButton(f"{new_index + 1}/{len(filtered_cards)}", callback_data="archive_search_info"))
    
            if new_index < len(filtered_cards) - 1:
                nav_buttons.append(InlineKeyboardButton(">", callback_data=f"archive_search_next_{new_index}"))
    
            keyboard = [
                nav_buttons,
                [InlineKeyboardButton("🔍 Новый поиск", callback_data=f"archive_search_{search_info.get('search_type', 'all')}")],
                [InlineKeyboardButton("❌ Отмена поиска", callback_data="archive_search_cancel")]
            ]
    
            try:
                media_source = card.get("media_source", "url")
                media_value = card.get("file_id") if media_source == "file_id" else card["image_url"]
    
                if card.get("media_type") == "animation":
                    media = InputMediaAnimation(media=media_value, caption=caption, parse_mode="HTML")
                else:
                    media = InputMediaPhoto(media=media_value, caption=caption, parse_mode="HTML")
    
                await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception as edit_error:
            
                if "Message is not modified" in str(edit_error):
                    # Просто обновляем клавиатуру
                    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
                    return
                logger.error(f"Ошибка редактирования: {edit_error}")
                try:
                    await query.message.delete()
                except:
                    pass
                # Отправляем новое сообщение
                if card.get("media_type") == "animation":
                    await context.bot.send_animation(
                        chat_id=query.message.chat_id,
                        animation=media_value,
                        caption=caption,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="HTML"
                    )
                else:
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=media_value,
                        caption=caption,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="HTML"
                    )        
    except Exception as e:
        logger.error(f"Ошибка в archive_search_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)
            
async def show_rarity_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню выбора редкости."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        if not user_data or not user_data.get("cards"):
            await query.edit_message_text("У вас пока нет существ!")
            return

        user_card_ids = user_data["cards"]
        card_counts = Counter(user_card_ids)
        unique_card_ids = list(card_counts.keys())

        rarity_cards = {}
        for card_id in unique_card_ids:
            card = find_card_by_id(card_id, data["cards"])
            if card:
                rarity = card.get("rarity", "Common")
                if rarity not in rarity_cards:
                    rarity_cards[rarity] = []
                rarity_cards[rarity].append((card_id, card_counts[card_id]))

        if not rarity_cards:
            await query.edit_message_text("У вас пока нет существ!")
            return

        keyboard = []
        
        # Обновлённый список редкостей в нужном порядке
        main_rarities = [
            "Common", "Rare", "Epic", "Legendary",  "Highlight", "Limited", "Rare Team-up", "Epic Team-up", 
             "Legendary Team-up"
        ]
        
        for rarity in main_rarities:
            if rarity in rarity_cards:
                keyboard.append([
                    InlineKeyboardButton(f"{rarity}", callback_data=f"barracks_rarity_select_{rarity}")
                ])

        # Проверяем наличие Upgrade редкостей и добавляем их, если они есть
        upgrade_rarities = [r for r in rarity_cards.keys() if r.startswith("Upgrade")]
        if upgrade_rarities:
            keyboard.append([]) # Пустая строка для разделения
            for rarity in sorted(upgrade_rarities):
                keyboard.append([
                    InlineKeyboardButton(f"{rarity}", callback_data=f"barracks_rarity_select_{rarity}")
                ])

        try:
            await query.message.delete()
        except:
            pass

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="📊 Выберите редкость:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Ошибка в show_rarity_menu: {e}")
        await query.answer("Произошла ошибка", show_alert=True)

async def mycards_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок просмотра карт в Казарме."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        # Кнопка "По редкости" → показать меню редкостей
        if query.data == "barracks_rarity":
            await show_rarity_menu(update, context)
            return
        
        elif query.data == "barracks_all":
            if not user_data or not user_data.get("cards"):
                await query.edit_message_text("У вас пока нет существ!")
                return
            user_card_ids = user_data["cards"]
            card_counts = Counter(user_card_ids)
            unique_card_ids = list(card_counts.keys())
            if not unique_card_ids:
                await query.edit_message_text("У вас пока нет существ!")
                return
            # ⭐ СОРТИРУЕМ ДЛЯ СТАБИЛЬНОЙ НАВИГАЦИИ ⭐
            unique_card_ids.sort()
            card = find_card_by_id(unique_card_ids[0], data["cards"])
            if not card:
                await query.edit_message_text("Ошибка: существо не найдено")
                return
    
            count = card_counts[card["id"]]
            caption = generate_card_caption(card, user_data, count=count, show_bonus=False)
    
            # ⭐ ИСПРАВЛЕНИЕ: Правильные callback_data и кнопка поиска ⭐
            nav_buttons = []
            nav_buttons.append(
                InlineKeyboardButton(f"1/{len(unique_card_ids)}", callback_data="card_info")
            )
            if len(unique_card_ids) > 1:
                # ⭐ ИСПРАВЛЕНО: Было card_next_all_0, стало card_next_all_1 ⭐
                nav_buttons.append(
                    InlineKeyboardButton(">", callback_data=f"card_next_all_1")
                )
    
            keyboard = [
                nav_buttons,
                [InlineKeyboardButton("🔍 Поиск", callback_data="archive_search_all")],  # ⭐ ДОБАВЛЕНО
                [InlineKeyboardButton("🔙 Назад", callback_data="archive_menu")]
            ]
    
            # ⭐ Удаляем старое текстовое сообщение и отправляем новое фото ⭐
            try:
                await query.message.delete()
            except:
                pass
    
            if card.get("media_type") == "animation":
                await context.bot.send_animation(
                    chat_id=query.message.chat_id,
                    animation=card["image_url"],
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML"
                )
            else:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=card["image_url"],
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML"
                )
            return
        # Кнопка "Назад в казарму" → вернуться в главное меню
        elif query.data == "barracks_back":
            try:
                await query.message.delete()
            except:
                pass
            await show_user_cards(update, context)
            return
        
        elif query.data.startswith("barracks_rarity_"):
            if query.data.startswith("barracks_rarity_nav_"):
                # Навигация внутри редкости
                parts = query.data.replace("barracks_rarity_nav_", "").split("_")
                rarity = parts[0]
                index = int(parts[1]) if len(parts) > 1 else 0
                await show_cards_by_rarity(update, context, rarity, start_index=index)
            elif query.data.startswith("barracks_rarity_select_"):
                # Выбор редкости
                rarity = query.data.replace("barracks_rarity_select_", "")
                await show_cards_by_rarity(update, context, rarity, start_index=0)
            return
        
        elif query.data.startswith("card_prev_") or query.data.startswith("card_next_"):
            parts = query.data.split("_")
            action = "prev" if "prev" in query.data else "next"
    
            # Определяем тип: "all" или конкретная редкость
            if "all" in query.data:
                # Все карты: card_prev_all_0 или card_next_all_1
                new_index = int(parts[-1])
                await show_all_cards(update, context, start_index=new_index)
            else:
                # По редкости: card_prev_Common_0 или card_next_Epic_1
                rarity = parts[2] if len(parts) > 3 else "Common"
                new_index = int(parts[-1])
                await show_cards_by_rarity(update, context, rarity=rarity, start_index=new_index)
            return
            
            user_card_ids = user_data["cards"]
            card_counts = Counter(user_card_ids)
            unique_card_ids = list(card_counts.keys())
            
            # ⭐ СОРТИРУЕМ ДЛЯ СТАБИЛЬНОЙ НАВИГАЦИИ ⭐
            unique_card_ids.sort()
            
            total_cards = len(unique_card_ids)
            
            action = "prev" if "prev" in query.data else "next"
            current_index = int(query.data.split("_")[-1])
            
            # ⭐ ЛИНЕЙНАЯ НАВИГАЦИЯ (без циклического перехода) ⭐
            if action == "prev":
                new_index = current_index - 1
            else:
                new_index = current_index + 1
            
            # Проверка границ
            if new_index < 0 or new_index >= total_cards:
                await query.answer("Нельзя пролистнуть дальше", show_alert=True)
                return
            
            card = find_card_by_id(unique_card_ids[new_index], data["cards"])
            if not card:
                await query.edit_message_text("Ошибка: существо не найдено")
                return
            
            count = card_counts[card["id"]]
            caption = generate_card_caption(card, user_data, count=count, show_bonus=False)
            
            # ⭐ ФОРМИРУЕМ КНОПКИ С УЧЁТОМ ГРАНИЦ ⭐
            nav_buttons = []
            
            # Кнопка "<" появляется только если это не первая карта
            if new_index > 0:
                nav_buttons.append(
                    InlineKeyboardButton("<", callback_data=f"card_prev_{new_index}")
                )
            
            # Кнопка с номером карты
            nav_buttons.append(
                InlineKeyboardButton(f"{new_index + 1}/{total_cards}", callback_data="card_info")
            )
            
            # Кнопка ">" появляется только если это не последняя карта
            if new_index < total_cards - 1:
                nav_buttons.append(
                    InlineKeyboardButton(">", callback_data=f"card_next_{new_index}")
                )
            
            keyboard = InlineKeyboardMarkup([
                nav_buttons,
                [InlineKeyboardButton("🔙 Назад", callback_data="barracks_back")]
            ])
            
            try:
                # ⭐ УНИВЕРСАЛЬНАЯ ЛОГИКА: file_id или URL ⭐
                media_source = card.get("media_source", "url")
                media_value = card.get("file_id") if media_source == "file_id" else card["image_url"]

                if card.get("media_type") == "animation":
                    media = InputMediaAnimation(media=media_value, caption=caption, parse_mode="HTML")
                else:
                    media = InputMediaPhoto(media=media_value, caption=caption, parse_mode="HTML")
                
                await query.edit_message_media(media=media, reply_markup=keyboard)
            except Exception as edit_error:
                if "Message is not modified" in str(edit_error):
                    return
                logger.error(f"Ошибка редактирования: {edit_error}")
                try:
                    await query.message.delete()
                except:
                    pass
                
                if card.get("media_type") == "animation":
                    await context.bot.send_animation(
                        chat_id=query.message.chat_id,
                        animation=card["image_url"],
                        caption=caption,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                else:
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=card["image_url"],
                        caption=caption,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
            return
        
    except Exception as e:
        logger.error(f"Ошибка в mycards_callback: {e}")
        await query.answer("Произошла ошибка", show_alert=True)
        
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает профиль пользователя с аватаркой."""
    try:
        # ⭐ ОПРЕДЕЛЯЕМ: callback query или команда ⭐
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            user_id = str(query.from_user.id)
            chat_id = query.message.chat_id
            is_callback = True
        else:
            user_id = str(update.effective_user.id)
            chat_id = update.effective_chat.id
            is_callback = False
        
        data = load_data()
        user_data = data["users"].get(user_id)
        if not user_data:
            if is_callback:
                await query.edit_message_text("❌ Вы ещё не начали игру!\nНажмите /start")
            else:
                await update.message.reply_text("❌ Вы ещё не начали игру!\nНажмите /start")
            return
        
        # ⭐ Миграция для старых пользователей ⭐
        if "avatar_url" not in user_data:
            user_data["avatar_url"] = DEFAULT_AVATAR_URL
        if "avatars" not in user_data:
            user_data["avatars"] = [DEFAULT_AVATAR_URL]
            save_data(data)
        
        # Считаем уникальные карты пользователя
        user_card_ids = user_data.get("cards", [])
        unique_cards = len(set(user_card_ids))
        
        # Считаем общее количество доступных карт в игре
        total_available_cards = len([card for card in data["cards"]])
        
        # Процент коллекции
        collection_percent = (
            round((unique_cards / total_available_cards * 100), 1)
            if total_available_cards > 0
            else 0
        )
        
        # Считаем карты по редкостям
        card_counts = Counter(user_card_ids)
        rarity_stats = {}
        for card_id in set(user_card_ids):
            card = find_card_by_id(card_id, data["cards"])
            if card:
                rarity = card.get("rarity", "T1")
                rarity_stats[rarity] = rarity_stats.get(rarity, 0) + 1
        
        # Формируем статистику по редкостям
        rarity_text = ""
        for rarity in [
            "Common", "Rare", "Rare Team-up", "Epic", "Epic Team-up",
            "Legendary", "Legendary Team-up", "Highlight", "Limited",
        ]:
            if rarity in rarity_stats:
                rarity_text += f"• {rarity}: {rarity_stats[rarity]} шт.\n"
        
        if not rarity_text:
            rarity_text = "Пока нет существ\n"
        
        profile_text = (
            f"👤 **Профиль игрока**\n"
            f"🆔 ID: `{user_id}`\n"
            f"💰 Бэт-коинов: {user_data.get('cents', 0)}\n"
            f"💥 Очков репутации (сезон): {user_data.get('season_points', 0)}\n"
            f"💎 Очков репутации (всего): {user_data.get('total_points', 0)}\n"
            f"📦 Собрано карт: {unique_cards}/{total_available_cards}\n"
            f"📊 Заполненность: {collection_percent}%\n"
            f"🔢 Всего получено: {len(user_card_ids)}\n"
            f"📈 По редкостям:\n"
            f"{rarity_text}"
            f"🔍 Бесплатные попытки: {user_data.get('free_rolls', 0)}\n"
        )
        
        # ⭐ КНОПКИ ПРОФИЛЯ ⭐
        keyboard = [
            [InlineKeyboardButton("🖼 Мои аватарки", callback_data="my_avatars_0")],
            [InlineKeyboardButton("🔍 Изучить чужое дело", callback_data="view_other_start")],  # ⭐ НОВОЕ
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # ⭐ ОТПРАВЛЯЕМ ПРОФИЛЬ С АВАТАРКОЙ ⭐
        avatar_url = user_data.get("avatar_url", DEFAULT_AVATAR_URL)
        
        if is_callback:
            # Удаляем старое сообщение
            try:
                await query.message.delete()
            except:
                pass
            
            # Отправляем фото с текстом профиля
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=avatar_url,
                caption=profile_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            # Отправляем фото с текстом профиля
            await update.message.reply_photo(
                photo=avatar_url,
                caption=profile_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Ошибка показа профиля: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("❌ Произошла ошибка при загрузке профиля")

async def start_view_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начинает процесс изучения чужого дела — запрашивает @никнейм."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        
        # ⭐ Переходим в состояние ввода ⭐
        context.user_data[user_id] = {"step": "view_other_username"}
        
        # ⭐ Удаляем старое сообщение и отправляем запрос ⭐
        try:
            await query.message.delete()
        except:
            pass
        
        # ⭐ НОВОЕ: Клавиатура с кнопкой отмены ⭐
        keyboard = [[KeyboardButton("❌ Отменить расследование")]]
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=(
                "🔍 **Изучить чужое дело**\n\n"
                "Введите @никнейм игрока, чьё досье хотите изучить:\n"
                "Пример: `@username`\n\n"
                "⚠️ Никнейм должен быть точным — иначе поиск не найдёт игрока."
            ),
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в start_view_other: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


async def process_other_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ввод @никнейма и показывает чужой профиль."""
    try:
        user_id = str(update.effective_user.id)
        text = update.message.text.strip()
        
        # ⭐ Проверка отмены ⭐
        if text == "❌ Отменить расследование":
            if user_id in context.user_data:
                del context.user_data[user_id]
    
            # ⭐ Убираем ReplyKeyboard и возвращаем главное меню ⭐
            main_keyboard = [
                [KeyboardButton("🔍 Получить досье")],
                [KeyboardButton("📁 Мой архив")],
                [KeyboardButton("📋 Меню")],
            ]
            await update.message.reply_text(
                "❌ Расследование отменено.\n"
                "Вы вернулись в главное меню.",
                reply_markup=ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
            )
            return
        
        # ⭐ Проверка формата ⭐
        if not text.startswith("@"):
            await update.message.reply_text(
                "❌ Никнейм должен начинаться с @!\n"
                "Повторите ввод (например: `@username`):",
                parse_mode="Markdown"
            )
            return
        
        target_username = text[1:].strip().lower()
        if not target_username:
            await update.message.reply_text("❌ Пустой никнейм! Повторите ввод:")
            return
        
        # ⭐ Ищем игрока ⭐
        data = load_data()
        target_user_id = None
        target_user_data = None
        
        for uid, udata in data["users"].items():
            user_username = udata.get("username", "")
            if user_username and user_username.lower() == target_username:
                target_user_id = uid
                target_user_data = udata
                break
        
        if not target_user_data:
            await update.message.reply_text(
                f"❌ Игрок с никнеймом @{target_username} не найден!\n"
                f"Проверьте правильность написания или попросите игрока установить никнейм в Telegram.\n\n"
                f"Повторите ввод или нажмите ❌ Отмена:"
            )
            return
        
        # ⭐ Проверка: не ищет ли игрок сам себя ⭐
        if target_user_id == user_id:
            if user_id in context.user_data:
                del context.user_data[user_id]
            await update.message.reply_text(
                "😅 Это ваше собственное дело!\n"
                "Используйте кнопку «👤 Личное дело» для просмотра своего профиля."
            )
            return
        
        # ⭐ Очищаем состояние ⭐
        if user_id in context.user_data:
            del context.user_data[user_id]
        
        # ⭐ ПОКАЗЫВАЕМ ЧУЖОЙ ПРОФИЛЬ ⭐
        await show_other_profile(update, context, target_user_id, target_user_data, data)
        
    except Exception as e:
        logger.error(f"Ошибка в process_other_username: {e}")
        if user_id in context.user_data:
            del context.user_data[user_id]
        await update.message.reply_text("❌ Произошла ошибка при поиске игрока")


async def show_other_profile(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target_user_id: str,
    target_user_data: Dict,
    data: Dict
) -> None:
    """Показывает профиль другого игрока с аватаркой и полной статистикой."""
    try:
        chat_id = update.effective_chat.id
        
        # ⭐ Миграция для старых пользователей ⭐
        if "avatar_url" not in target_user_data:
            target_user_data["avatar_url"] = DEFAULT_AVATAR_URL
        
        # Имя игрока
        first_name = target_user_data.get("first_name", "Игрок")
        last_name = target_user_data.get("last_name", "")
        username = target_user_data.get("username", "")
        display_name = f"{first_name} {last_name}".strip() if last_name else first_name
        
        # ⭐ ЭКРАНИРОВАНИЕ СПЕЦСИМВОЛОВ MARKDOWN ⭐
        display_name_escaped = escape_markdown(display_name)
        username_escaped = escape_markdown(username) if username else ""
        
        # Статистика карт
        user_card_ids = target_user_data.get("cards", [])
        unique_cards = len(set(user_card_ids))
        total_available_cards = len([card for card in data["cards"]])
        collection_percent = (
            round((unique_cards / total_available_cards * 100), 1)
            if total_available_cards > 0
            else 0
        )
        
        # Карты по редкостям
        card_counts = Counter(user_card_ids)
        rarity_stats = {}
        for card_id in set(user_card_ids):
            card = find_card_by_id(card_id, data["cards"])
            if card:
                rarity = card.get("rarity", "T1")
                rarity_stats[rarity] = rarity_stats.get(rarity, 0) + 1
        
        rarity_text = ""
        for rarity in [
            "Common", "Rare", "Rare Team-up", "Epic", "Epic Team-up",
            "Legendary", "Legendary Team-up", "Highlight", "Limited",
        ]:
            if rarity in rarity_stats:
                rarity_text += f"• {rarity}: {rarity_stats[rarity]} шт.\n"
        
        if not rarity_text:
            rarity_text = "Пока нет существ\n"
        
        # Клан
        clan_id = data.get("user_clan", {}).get(target_user_id)
        clan_text = ""
        if clan_id:
            clan = None
            if clan_id in data.get("clans", {}):
                clan = data["clans"][clan_id]
            else:
                for c in data.get("clans", {}).values():
                    if c.get("name") == clan_id:
                        clan = c
                        break
            if clan:
                # ⭐ ЭКРАНИРОВАНИЕ НАЗВАНИЯ КЛАНА ⭐
                clan_name_escaped = escape_markdown(clan['name'])
                clan_text = f"🏰 Клан: **{clan_name_escaped}**\n"
        
        # ⭐ ФОРМИРУЕМ ТЕКСТ ПРОФИЛЯ (ВСЕ ПОЛЯ ЭКРАНИРОВАНЫ) ⭐
        profile_text = (
            f"🕵️ **Досье игрока**\n"
            f"👤 Имя: {display_name_escaped}\n"
        )
        if username_escaped:
            profile_text += f"🔗 Никнейм: @{username_escaped}\n"
        profile_text += f"🆔 ID: `{target_user_id}`\n"
        if clan_text:
            profile_text += clan_text
        profile_text += (
            f"\n"
            f"💰 Бэт-коинов: {target_user_data.get('cents', 0)}\n"
            f"💥 Очков репутации (сезон): {target_user_data.get('season_points', 0)}\n"
            f"💎 Очков репутации (всего): {target_user_data.get('total_points', 0)}\n"
            f"📦 Собрано карт: {unique_cards}/{total_available_cards}\n"
            f"📊 Заполненность: {collection_percent}%\n"
            f"🔢 Всего получено: {len(user_card_ids)}\n"
            f"📈 По редкостям:\n"
            f"{rarity_text}"
            f"🔍 Бесплатные попытки: {target_user_data.get('free_rolls', 0)}\n"
        )
        
        # ⭐ КНОПКИ ⭐
        keyboard = [
            [InlineKeyboardButton("🔍 Изучить ещё одно дело", callback_data="view_other_start")],
            [InlineKeyboardButton("🔙 Назад в своё дело", callback_data="profile_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # ⭐ ОТПРАВЛЯЕМ С АВАТАРКОЙ ⭐
        avatar_url = target_user_data.get("avatar_url", DEFAULT_AVATAR_URL)

        # Отправляем фото профиля с inline-кнопками
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=avatar_url,
            caption=profile_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

         # ⭐ Убираем ReplyKeyboard и возвращаем главное меню ⭐
        main_keyboard = [
            [KeyboardButton("🔍 Получить досье")],
            [KeyboardButton("📁 Мой архив")],
            [KeyboardButton("📋 Меню")],
        ]
        await update.message.reply_text(
            "🔍",
            reply_markup=ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
        )
        logger.info(f"Игрок {update.effective_user.id} изучил дело игрока {target_user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка в show_other_profile: {e}")
        await update.message.reply_text("❌ Произошла ошибка при показе досье")
        
async def my_avatars(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
    """Показывает галерею аватарок игрока с навигацией."""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data:
            await query.edit_message_text("❌ Вы ещё не начали игру!")
            return
        
        # ⭐ Миграция для старых пользователей ⭐
        if "avatar_url" not in user_data:
            user_data["avatar_url"] = DEFAULT_AVATAR_URL
        if "avatars" not in user_data:
            user_data["avatars"] = [DEFAULT_AVATAR_URL]
            save_data(data)
        
        avatars = user_data.get("avatars", [DEFAULT_AVATAR_URL])
        current_avatar = user_data.get("avatar_url", DEFAULT_AVATAR_URL)
        
        if not avatars:
            avatars = [DEFAULT_AVATAR_URL]
            user_data["avatars"] = avatars
            save_data(data)
        
        total_avatars = len(avatars)
        
        # Корректировка индекса
        if page < 0:
            page = 0
        elif page >= total_avatars:
            page = total_avatars - 1
        
        # Сохраняем текущий индекс
        context.user_data[f"avatar_page_{user_id}"] = page
        
        current_page_avatar = avatars[page]
        is_active = (current_page_avatar == current_avatar)
        
        # ⭐ ФОРМИРУЕМ CAPTION ⭐
        caption = (
            f"🖼 **Мои аватарки**\n"
            f"📷 Аватарка {page + 1} из {total_avatars}\n"
        )
        if is_active:
            caption += f"✅ **Эта аватарка активна**"
        else:
            caption += f"💡 Нажмите кнопку ниже, чтобы установить эту аватарку"
        
        # ⭐ ФОРМИРУЕМ КЛАВИАТУРУ ⭐
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"avatar_nav_{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_avatars}", callback_data="avatar_info"))
        if page < total_avatars - 1:
            nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"avatar_nav_{page + 1}"))
        
        # Кнопка установки
        if is_active:
            set_button = InlineKeyboardButton("✅ Активная", callback_data="avatar_active")
        else:
            set_button = InlineKeyboardButton("✅ Установить как активную", callback_data=f"avatar_set_{page}")
        
        keyboard = [
            nav_buttons,
            [set_button],
            [InlineKeyboardButton("🔙 Назад в профиль", callback_data="profile_back")]
        ]
        
        # ⭐ ОТПРАВЛЯЕМ АВАТАРКУ ⭐
        try:
            media = InputMediaPhoto(
                media=current_page_avatar,
                caption=caption,
                parse_mode="Markdown"
            )
            await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as edit_error:
            if "Message is not modified" in str(edit_error):
                await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
                return
            logger.error(f"Ошибка редактирования аватарки: {edit_error}")
            try:
                await query.message.delete()
            except:
                pass
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=current_page_avatar,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Ошибка в my_avatars: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


async def avatar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок галереи аватарок."""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = str(query.from_user.id)
        
        # ⭐ Навигация ⭐
        if query.data.startswith("avatar_nav_"):
            try:
                page = int(query.data.replace("avatar_nav_", ""))
                await my_avatars(update, context, page=page)
            except (ValueError, IndexError):
                await query.answer("❌ Ошибка навигации", show_alert=True)
            return
        
        # ⭐ Установка аватарки ⭐
        if query.data.startswith("avatar_set_"):
            try:
                page = int(query.data.replace("avatar_set_", ""))
                data = load_data()
                user_data = data["users"].get(user_id)
                
                if not user_data:
                    await query.answer("❌ Профиль не найден", show_alert=True)
                    return
                
                avatars = user_data.get("avatars", [DEFAULT_AVATAR_URL])
                if page < 0 or page >= len(avatars):
                    await query.answer("❌ Аватарка не найдена", show_alert=True)
                    return
                
                # Устанавливаем аватарку
                user_data["avatar_url"] = avatars[page]
                save_data(data)
                
                await query.answer("✅ Аватарка установлена!", show_alert=True)
                await my_avatars(update, context, page=page)
            except (ValueError, IndexError) as e:
                logger.error(f"Ошибка установки аватарки: {e}")
                await query.answer("❌ Ошибка данных", show_alert=True)
            return
        
        # ⭐ Инфо ⭐
        if query.data == "avatar_info":
            await query.answer("📄 Используйте ◀️ и ▶️ для навигации", show_alert=False)
            return
        
        # ⭐ Активная ⭐
        if query.data == "avatar_active":
            await query.answer("✅ Эта аватарка уже активна", show_alert=False)
            return
    except Exception as e:
        logger.error(f"Ошибка в avatar_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)
            

async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок профиля."""
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "profile_back":
            await my_profile(update, context)
        elif query.data.startswith("my_avatars_"):
            # Переход в галерею аватарок
            try:
                page = int(query.data.replace("my_avatars_", ""))
                await my_avatars(update, context, page=page)
            except (ValueError, IndexError):
                await my_avatars(update, context, page=0)
        elif query.data == "view_other_start":
            # ⭐ НОВОЕ: Запуск изучения чужого дела ⭐
            await start_view_other(update, context)
    except Exception as e:
        logger.error(f"Ошибка profile_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик инлайн-кнопок навигации."""

    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)

        if not user_data or not user_data.get("cards"):
            await query.edit_message_text("У вас больше нет существ!")
            return

        user_card_ids = user_data["cards"]
        card_counts = Counter(user_card_ids)
        unique_card_ids = list(card_counts.keys())
        total_cards = len(unique_card_ids)

        if query.data and ("card_prev" in query.data or "card_next" in query.data):
            action = "prev" if "prev" in query.data else "next"
            current_index = int(query.data.split("_")[-1])
            if action == "prev":
                new_index = current_index - 1
            else:
                new_index = current_index + 1

            # Проверка границ
            if new_index < 0 or new_index >= total_cards:
                await query.answer("Нельзя пролистнуть дальше", show_alert=True)
                return
            card = find_card_by_id(unique_card_ids[new_index], data["cards"])

            if not card:
                await query.edit_message_text("Карточка не найдена!")
                return

            count = card_counts[card["id"]]
            caption = generate_card_caption(
                card, user_data, count=count, show_bonus=False
            )
            nav_buttons = []

            # Кнопка "<" появляется только если это не первая карта
            if new_index > 0:
                nav_buttons.append(
                    InlineKeyboardButton("<", callback_data=f"card_prev_{new_index}")
                )

            # Кнопка с номером карты
            nav_buttons.append(
                InlineKeyboardButton(f"{new_index + 1}/{total_cards}", callback_data="card_info")
            )

            # Кнопка ">" появляется только если это не последняя карта
            if new_index < total_cards - 1:
                nav_buttons.append(
                    InlineKeyboardButton(">", callback_data=f"card_next_{new_index}")
                )
            keyboard = InlineKeyboardMarkup([
                nav_buttons,
                [InlineKeyboardButton("🔙 Назад", callback_data="barracks_back")]
            ])

            logger.info(
                f"Попытка показать существо #{card['id']}: {card['image_url'][:100]}"
            )

            try:
                if card.get("media_type") == "animation" or card["image_url"].lower().endswith((".mp4", ".webm", ".mov")):
                    media = InputMediaVideo(
                    media=card["image_url"], 
                    caption=caption,
                    supports_streaming=True
                    )
                else:
                    media = InputMediaPhoto(media=card["image_url"], caption=caption)
                
                await query.edit_message_media(media=media, reply_markup=keyboard)
            except Exception as edit_error:
                logger.error(
                    f"❌ Ошибка редактирования существа #{card['id']}: {edit_error}"
                )
                logger.error(f"URL: {card['image_url']}")
                try:
                    await query.message.delete()
                except:
                    pass
                    
                if card.get("media_type") == "animation" or card["image_url"].lower().endswith((".mp4", ".webm", ".mov")):
                    await context.bot.send_video(
                        chat_id=query.message.chat_id,
                        video=card["image_url"],
                        caption=caption,
                        reply_markup=keyboard,
                        supports_streaming=True
                    )
                else:
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=card["image_url"],
                        caption=caption,
                        reply_markup=keyboard,
                    )

        elif query.data == "barracks_back":
            try:
                await query.message.delete()
            except:
                pass
            await show_user_cards(update, context)    
    except Exception as e:
        logger.error(f"Ошибка в callback: {e}")
        await query.answer("Произошла ошибка", show_alert=True)

def get_card_with_fixed_rarity(cards: List[Dict]) -> Optional[Dict]:

    if not cards:
        return None
        
    # Группируем карты по редкостям
    cards_by_rarity = {}
    for card in cards:
        rarity = card.get("rarity", "Classic")
        if rarity not in cards_by_rarity:
            cards_by_rarity[rarity] = []
        cards_by_rarity[rarity].append(card)
        
    # Создаём список редкостей с весами
    available_rarities = []
    weights = []
    for rarity, rarity_cards in cards_by_rarity.items():
        if rarity_cards:  # Если есть карты такой редкости
            probability = RARITY_BONUSES.get(rarity, {"probability": 0}).get(
                "probability", 0
            )
            if probability > 0:
                available_rarities.append(rarity)
                weights.append(probability)
    
    if not available_rarities:
        return None
    
    total_weight = sum(weights)

    if total_weight == 0:
        return None
    
    normalized_weights = [w / total_weight for w in weights]
    chosen_rarity = random.choices(available_rarities, weights=normalized_weights, k=1)[
        0
    ]
    rarity_cards = cards_by_rarity[chosen_rarity]
    return random.choice(rarity_cards)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений (кнопки)."""
    try:
        user_id = str(update.effective_user.id)
        text = update.message.text if update.message else None

        # ⭐ ОБРАБОТКА ФОТО ДЛЯ УСТАНОВКИ АВАТАРКИ КЛАНА ⭐
        if update.message.photo and user_id in context.user_data:
            if context.user_data[user_id].get("step") == "clan_set_avatar":
                await process_clan_avatar_photo(update, context)
                return

        # ⭐ СОСТОЯНИЕ ЗАМЕНЫ МЕДИА ЧЕРЕЗ /edit_card ⭐
        if user_id in context.user_data:
            user_state = context.user_data.get(user_id, {})
            step = user_state.get("step", "")
    
            if step == "edit_card_waiting_media":
                # Обработка отмены
                if text and text.lower() == "/cancel":
                    del context.user_data[user_id]
                    await update.message.reply_text("❌ Редактирование отменено.")
                    return
        
                # Проверяем, что пришло медиа
                if not (update.message.photo or update.message.video or update.message.animation):
                    await update.message.reply_text(
                        "⚠️ Отправьте фото, видео или GIF!\n"
                        "❌ Для отмены: /cancel"
                    )
                    return
        
                # Получаем file_id
                if update.message.photo:
                    new_file_id = update.message.photo[-1].file_id
                    new_media_type = "photo"
                elif update.message.video:
                    new_file_id = update.message.video.file_id
                    new_media_type = "animation"
                elif update.message.animation:
                    new_file_id = update.message.animation.file_id
                    new_media_type = "animation"
        
                # ⭐ Обновляем карту ⭐
                card_id = user_state["edit_card_id"]
                data = load_data()
                card = find_card_by_id(card_id, data["cards"])
        
                if not card:
                    del context.user_data[user_id]
                    await update.message.reply_text(f"❌ Карта с ID {card_id} не найдена!")
                    return
        
                # Сохраняем старые значения для отчёта
                old_source = card.get("media_source", "url")
                old_url = card.get("image_url", "")
                old_file_id = card.get("file_id", "")
        
                # ⭐ Обновляем поля карты ⭐
                card["file_id"] = new_file_id
                card["media_source"] = "file_id"
                card["media_type"] = new_media_type
                card["image_url"] = ""  # Очищаем URL
        
                save_data(data)
        
                # ⭐ Очищаем состояние ⭐
                del context.user_data[user_id]
        
                # ⭐ Отправляем отчёт ⭐
                await update.message.reply_text(
                    f"✅ **Медиа карты #{card_id} обновлено!**\n\n"
                    f"🏷 {card.get('title')}\n"
                    f"🌟 {card.get('rarity')}\n"
                    f"📺 Тип: {'🎬 Видео/Анимация' if new_media_type == 'animation' else '📷 Фото'}\n"
                    f"📤 Источник: file_id\n\n"
                    f"🔄 Было: {old_source} ({old_url or old_file_id})\n"
                    f"✅ Стало: file_id"
                )
        
                # ⭐ Отправляем превью ⭐
                try:
                    if new_media_type == "animation":
                        await context.bot.send_video(
                            chat_id=update.effective_chat.id,
                            video=new_file_id,
                            caption=f"Превью карты #{card_id}",
                            supports_streaming=True
                        )
                    else:
                        await context.bot.send_photo(
                            chat_id=update.effective_chat.id,
                            photo=new_file_id,
                            caption=f"Превью карты #{card_id}"
                        )
                except Exception as preview_error:
                    logger.warning(f"Не удалось отправить превью: {preview_error}")
        
                return

        data = load_data()
        user_data = data["users"].get(user_id)
        text = update.message.text

        # ⭐ ПРОВЕРКА ИСТЕЧЕНИЯ БЭТ-ПАССА ⭐
        if user_data and user_data.get("has_batpass", False):
            expires_at = user_data.get("batpass_expires_at", 0)
            if expires_at > 0:
                from datetime import datetime, timezone, timedelta
                msk_tz = timezone(timedelta(hours=3))
                now = int(datetime.now(msk_tz).timestamp())
        
                if now >= expires_at:
                    # Бэт-пасс истёк
                    user_data["has_batpass"] = False
                    user_data["batpass_expires_at"] = 0
                    save_data(data)
            
                    # Уведомляем игрока
                    try:
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text="⏰ <b>Ваш Бэт-пасс истёк!</b>\n\nВы можете приобрести новый у администратора.",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Не удалось уведомить игрока {user_id} об истечении Бэт-пасса: {e}")

        # ⭐ ОБРАБОТКА МЕДИА ДЛЯ ДОБАВЛЕНИЯ КАРТЫ ⭐
        if user_id in context.user_data:
            user_state = context.user_data.get(user_id, {})
            step = user_state.get("step", "")
    
            # Если ожидается медиа — обрабатываем фото/видео
            if step == ADD_CARD_WAITING_MEDIA:
                if update.message.photo or update.message.video or update.message.animation:
                    await process_add_card_media(update, context)
                    return
                elif text and text.lower() == "/cancel":
                    del context.user_data[user_id]
                    await update.message.reply_text("❌ Добавление карты отменено.")
                    return
                else:
                    await update.message.reply_text(
                        "⚠️ Отправьте фото, видео или GIF!\n"
                        "❌ Для отмены: /cancel"
                    )
                    return
    
            # Если ожидается название
            if step == ADD_CARD_WAITING_TITLE:
                if text.lower() == "/cancel":
                    del context.user_data[user_id]
                    await update.message.reply_text("❌ Добавление карты отменено.")
                    return
        
                user_state["title"] = text
                user_state["step"] = ADD_CARD_WAITING_RARITY
        
                # Список редкостей
                rarities = [
                    "Common", "Rare", "Rare Team-up",
                    "Epic", "Epic Team-up",
                    "Legendary", "Legendary Team-up",
                    "Highlight", "Limited"
                ]
                rarity_text = "\n".join([f"• {r}" for r in rarities])
        
                await update.message.reply_text(
                    f"✅ Название: **{text}**\n\n"
                    f"🌟 **Шаг 3/4:** Выберите редкость:\n\n"
                    f"{rarity_text}\n\n"
                    f"❌ Для отмены: /cancel",
                    parse_mode="Markdown"
                )
                return
    
            # Если ожидается редкость
            if step == ADD_CARD_WAITING_RARITY:
                if text.lower() == "/cancel":
                    del context.user_data[user_id]
                    await update.message.reply_text("❌ Добавление карты отменено.")
                    return
        
                valid_rarities = [
                    "Common", "Rare", "Rare Team-up",
                    "Epic", "Epic Team-up",
                    "Legendary", "Legendary Team-up",
                    "Highlight", "Limited"
                ]
        
                if text not in valid_rarities:
                    await update.message.reply_text(
                        f"❌ Неверная редкость!\n"
                        f"Доступные: {', '.join(valid_rarities)}"
                    )
                    return
        
                user_state["rarity"] = text
                user_state["step"] = ADD_CARD_WAITING_CATCHPHRASE
        
                await update.message.reply_text(
                    f"✅ Редкость: **{text}**\n\n"
                    f"💬 **Шаг 4/4:** Введите catchphrase (короткую фразу персонажа)\n"
                    f"Или отправьте «нет» чтобы пропустить\n\n"
                    f"❌ Для отмены: /cancel",
                    parse_mode="Markdown"
                )
                return
    
            # Если ожидается catchphrase
            if step == ADD_CARD_WAITING_CATCHPHRASE:
                if text.lower() == "/cancel":
                    del context.user_data[user_id]
                    await update.message.reply_text("❌ Добавление карты отменено.")
                    return
    
                catchphrase = None if text.lower() == "нет" else text
                user_state["catchphrase"] = catchphrase
    
                # ⭐ ПЕРЕХОДИМ К ВОПРОСУ ПРО CLASSIC ⭐
                user_state["step"] = ADD_CARD_WAITING_CLASSIC
    
                await update.message.reply_text(
                    f"✅ Catchphrase: **{catchphrase or 'пропущено'}**\n\n"
                    f"🏛 **Шаг 5/5:** Является ли эта карта Classic?\n\n"
                    f"Ответьте **да** или **нет**\n\n"
                    f"❌ Для отмены: /cancel",
                    parse_mode="Markdown"
                )
                return

            # ⭐ НОВОЕ: Если ожидается ответ про Classic ⭐
            if step == ADD_CARD_WAITING_CLASSIC:
                if text.lower() == "/cancel":
                    del context.user_data[user_id]
                    await update.message.reply_text("❌ Добавление карты отменено.")
                    return
    
                # ⭐ Парсим ответ ⭐
                is_classic = text.lower().strip() in ["да", "true", "1", "yes", "classic"]
    
                # ⭐ ИСПРАВЛЕНИЕ 1: Заменяем \\n на реальный перенос строки ⭐
                catchphrase_raw = user_state.get("catchphrase")
                if catchphrase_raw:
                    catchphrase_raw = catchphrase_raw.replace("\\n", "\n")
                    user_state["catchphrase"] = catchphrase_raw
    
                # ⭐ СОЗДАЁМ НОВУЮ КАРТУ ⭐
                data = load_data()
                new_id = max([c["id"] for c in data["cards"]], default=0) + 1
    
                new_card = {
                    "id": new_id,
                    "title": user_state["title"],
                    "rarity": user_state["rarity"],
                    "catchphrase": user_state["catchphrase"],
                    "available": True,
                    "media_type": user_state["media_type"],
                    "media_source": "file_id",
                    "file_id": user_state["file_id"],
                    "image_url": "",
                    "is_classic": is_classic,
                }
    
                data["cards"].append(new_card)
                save_data(data)
    
                # ⭐ Очищаем состояние ⭐
                del context.user_data[user_id]
    
                # ⭐ ИСПРАВЛЕНИЕ 2: Экранируем пользовательские данные для Markdown ⭐
                import html as html_module
    
                def escape_md(text: str) -> str:
                    """Экранирует спецсимволы Markdown."""
                    if not text:
                        return ""
                    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
                    for char in special_chars:
                        text = text.replace(char, f'\\{char}')
                    return text
    
                title_escaped = escape_md(user_state["title"])
                catchphrase_escaped = escape_md(user_state["catchphrase"] or "")
    
                # ⭐ Формируем текст ответа ⭐
                catchphrase_text = f"💬 {catchphrase_escaped}" if catchphrase_escaped else ""
                classic_text = "🏛 **Classic**" if is_classic else ""
    
                result_text = (
                    f"✅ **Карточка #{new_id} добавлена!**\n"
                    f"🏷 {title_escaped}\n"
                    f"{catchphrase_text}\n"
                    f"🌟 {user_state['rarity']}\n"
                    f"📺 {'Анимация' if user_state['media_type'] == 'animation' else 'Фото'}\n"
                    f"{classic_text}\n"
                    f"📤 Источник: file\\_id"
                )
    
                # ⭐ Отправляем сообщение с fallback ⭐
                try:
                    await update.message.reply_text(
                        result_text,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.warning(f"Ошибка отправки Markdown: {e}. Пробую без parse_mode.")
                    # Fallback: отправляем без парсинга
                    await update.message.reply_text(
                        f"✅ Карточка #{new_id} добавлена!\n"
                        f"🏷 {user_state['title']}\n"
                        f"💬 {user_state['catchphrase'] or ''}\n"
                        f"🌟 {user_state['rarity']}\n"
                        f"📺 {'Анимация' if user_state['media_type'] == 'animation' else 'Фото'}\n"
                        f"🏛 Classic: {'Да' if is_classic else 'Нет'}\n"
                        f"📤 Источник: file_id"
                    )
    
                # ⭐ Отправляем превью карты ⭐
                try:
                    if user_state["media_type"] == "animation":
                        await context.bot.send_video(
                            chat_id=update.effective_chat.id,
                            video=user_state["file_id"],
                            caption=f"Превью карты #{new_id}",
                            supports_streaming=True
                        )
                    else:
                        await context.bot.send_photo(
                            chat_id=update.effective_chat.id,
                            photo=user_state["file_id"],
                            caption=f"Превью карты #{new_id}"
                        )
                except Exception as preview_error:
                    logger.warning(f"Не удалось отправить превью: {preview_error}")
    
                return

        # ⭐ СОСТОЯНИЕ ПОИСКА В АРХИВЕ ⭐
        if user_id in context.user_data:
            user_step = context.user_data[user_id].get("step", "")
            if user_step == "archive_search":
                await archive_search_execute(update, context)
                return
        
        # ⭐ ПРОВЕРКА: если пользователь в шаге выбора партнёра для трейда ⭐
        if user_id in context.user_data:
            trade_info = context.user_data[user_id]
            step = trade_info.get("step", "")
            if step in ["select_partner", "search_mode"]:
                await process_partner_selection(update, context)
                return
        # ===== ДОБАВИТЬ В НАЧАЛО handle_message() =====

        # ⭐ КНОПКА "🏰 Кланы" в главном меню ⭐
        if text == "🏰 Кланы":
            await clan_menu(update, context)
            return

        # ⭐ ВНУТРИ МЕНЮ КЛАНОВ ⭐
        if text == "➕ Создать клан":
            await create_clan_flow(update, context)
            return

        if text == "📋 Мой клан" or text == "🔒 Мой клан (не в клане)":
            await my_clan_view(update, context)
            return

        elif text == "🏆 Топ кланов":
            await top_clans(update, context)
            return

        if text == "✏️ Описание клана":
            await edit_clan_description_start(update, context)
            return

        if text == "🖼 Установить аватарку клана":  # ⭐ НОВОЕ
            await set_clan_avatar_start(update, context)
            return

        if text == "🔙 Назад в кланы":
            await clan_menu(update, context)
            return

        # ⭐ ПРОЦЕСС СОЗДАНИЯ КЛАНА ⭐
        if user_id in context.user_data:
            user_step = context.user_data[user_id].get("step", "")
    
            if user_step == "clan_create_confirm":
                await confirm_clan_creation(update, context)
                return
    
            if user_step == "clan_enter_name":
                await process_clan_name(update, context)
                return
    
            if user_step == "clan_invite_enter_username":
                await process_clan_invite(update, context)
                return

            if user_step == "clan_edit_description":
                await process_clan_description_input(update, context)
                return
            if user_step == "view_other_username":
                await process_other_username(update, context)
                return

        # ⭐ ВЫХОД ИЗ КЛАНА ⭐
        if text == "🚪 Покинуть клан":
            await leave_clan_confirm(update, context)
            return

        if text == "✅ Да, покинуть клан" or text == "❌ Отмена":
            # Проверяем, что это не отмена создания клана
            if user_id not in context.user_data or context.user_data[user_id].get("step") != "clan_enter_name":
                await process_leave_clan(update, context)
                return

        # ⭐ ПРИГЛАШЕНИЕ В КЛАН ⭐
        if text == "📨 Пригласить игрока":
            await invite_clan_member(update, context)
            return
    
        # ⭐ КНОПКА "🔙 НАЗАД В ГЛАВНОЕ МЕНЮ" ⭐
        if text == "🔙 Назад в главное меню":
            # Сбрасываем состояние поиска противника, если оно было активно
            if user_id in context.user_data and context.user_data[user_id].get("step") == "battle_find_opponent":
                del context.user_data[user_id]["step"]
            
            keyboard = [
                [KeyboardButton("🔍 Получить досье")],
                [KeyboardButton("📁 Мой архив")],
                [KeyboardButton("📋 Меню")],
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "🏠 Главное меню\nДобро пожаловать! Используйте кнопки ниже:",
                reply_markup=reply_markup
            )
            return

        elif text == "📋 Меню":
            await submenu(update, context)
            return

        elif text == "🔙 Назад":
            await submenu(update, context)
            return

        elif text == "👤 Личное дело":
            await my_profile(update, context)
            return

        elif text == "📁 Мой архив":
            await archive_menu(update, context)
            return

        elif text == "📊 Просмотр архива":
            await show_user_cards(update, context)
            return

        elif text == "🔨 Крафт":
            await craft_menu(update, context)
            return

        elif text == "📜 Квесты":
            await quests_menu(update, context)
            return
                    
        elif text == "🛍️ Магазин":
            await shop_menu(update, context)
            return

        if text == "🔍 Получить досье":

            user_data = data["users"].get(user_id)

            if not user_data:

                user_data = {
                    "username": update.effective_user.username or "",
                    "first_name": update.effective_user.first_name or "",
                    "last_name": update.effective_user.last_name or "",
                    "cards": [],
                    "total_points": 0,
                    "season_points": 0,
                    "cents": 0,
                    "last_card_time": 0,
                    "free_rolls": 0,
                    "last_dice_time": 0,
                    "card_notification_sent": False, 
                }

                data["users"][user_id] = user_data

            # ⭐ НОВОЕ: Отмечаем активность пользователя сегодня ⭐
            from datetime import datetime, timezone, timedelta
            msk_tz = timezone(timedelta(hours=3))
            today_str = datetime.now(msk_tz).strftime("%Y-%m-%d")
            user_data["last_daily_activity"] = today_str
    
            # ⭐ Если регистрация ещё не записана (для старых пользователей) ⭐
            if not user_data.get("registered_at"):
                user_data["registered_at"] = today_str

            COOLDOWN_SECONDS = 3 * 60 * 60
            current_time = int(time.time())
            if is_batpass_active(user_data):
                COOLDOWN_SECONDS = 9000
            time_passed = current_time - user_data.get("last_card_time", 0)

            # ⭐ ПРОВЕРКА: является ли пользователь админом ⭐
            is_super_admin = (user_id == SUPER_ADMIN_ID)

            # ⭐ ПРОВЕРКА: есть ли бесплатные попытки ⭐
            free_rolls = user_data.get("free_rolls", 0)
            use_free_roll = False

            # ⭐ АДМИНЫ ПРОПУСКАЮТ КУЛДАУН ⭐
            if is_super_admin:
                # Админы всегда могут получить карту (без кулдауна)
                pass
            elif time_passed >= COOLDOWN_SECONDS:
                # Обычная попытка (кулдаун прошёл)
                pass
            elif free_rolls > 0:
                # Используем бесплатную попытку
                use_free_roll = True
            else:
                # Нет бесплатных попыток и кулдаун не прошёл
                remaining = COOLDOWN_SECONDS - time_passed
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                seconds = remaining % 60
                time_text = ""
                if hours > 0:
                    time_text += f"{hours} ч "
                if minutes > 0:
                    time_text += f"{minutes} мин "
                time_text += f"{seconds} сек"

                await update.message.reply_text(
                    f"⏳ До получения следующего досье: {time_text}\n\n"
                    f"🎲 Или бросьте кубик для бесплатной попытки!"
                )
                return

            # Собираем доступные карты
            available_cards = [
                card
                for card in data["cards"]
                if card["available"]
            ]

            if not available_cards:
                await update.message.reply_text("⏳ Ожидайте новых существ!")
                return
            card = get_card_with_fixed_rarity(available_cards)

            if not card:
                await update.message.reply_text("⏳ Ожидайте новых существ!")
                return
            bonus = RARITY_BONUSES.get(card["rarity"], {"cents": 0, "points": 0})
            user_data["total_points"] += bonus["points"]
            user_data["season_points"] += bonus["points"]
            user_data["cents"] += bonus["cents"]
            user_data["cards"].append(card["id"])

            # ⭐ ОБНОВЛЕНИЕ ВРЕМЕНИ И БЕСПЛАТНЫХ ПОПЫТОК ⭐
            if use_free_roll:
                user_data["free_rolls"] -= 1  # Тратим бесплатную попытку
                # Время НЕ обновляем!
            elif not is_super_admin:
                # ⭐ Админам НЕ обновляем время (чтобы кулдаун не сбрасывался) ⭐
                user_data["last_card_time"] = current_time
            user_data["notification_sent"] = False  # ← ДОБАВЬТЕ
            update_seasonal_on_card_get(user_data, card["rarity"])
            save_data(data)

            # ⭐ НОВОЕ: Планируем уведомление для следующего получения ⭐
            if is_batpass_active(user_data) and not use_free_roll:
                from datetime import datetime, timezone, timedelta
                msk_tz = timezone(timedelta(hours=3))
                now = int(datetime.now(msk_tz).timestamp())
    
                notification_time = current_time + 9000  # 2.5 часа
                delay_seconds = 9000
                job_name = f"card_notify_{user_id}"
    
                # Отменяем старый job, если есть
                for job in context.job_queue.get_jobs_by_name(job_name):
                    job.schedule_removal()
    
                # Планируем новый job
                context.job_queue.run_once(
                    send_card_notification,
                    when=delay_seconds,
                    data={"user_id": user_id},
                    name=job_name
                )
    
                logger.info(f"Запланировано уведомление для игрока {user_id} через {delay_seconds} сек")
            
            # Ежедневный квест
            if card["rarity"] == "Common":
                await update_quest_progress(context, user_id, "common_4", 1)

            # Еженедельные квесты
            if card["rarity"] == "Rare":
                await update_weekly_quest_progress(context, user_id, "weekly_rare_6", 1)
            if card["rarity"] == "Epic Team-up":
                await update_weekly_quest_progress(context, user_id, "weekly_epic_tu_1", 1)
            caption = generate_card_caption(card, user_data, count=1, show_bonus=True)
            await send_card(update, card, context, caption=caption)

        elif text == "🍺 Бар":
            await bar_menu(update, context)

        elif text == "🔗 Рефералка":
            await referral_menu(update, context)

        elif text == "🔥 Сжигание":
            await burn_menu(update, context)
            return

        elif text == "🎲 Кубик":
            await dice(update, context)

        elif text == "🎰 Казино":
            await open_casino_from_button(update, context)

        elif text == "🏀 Баскет":
            await basket_menu(update, context)
            return

        elif text == "🎯 Дартс":
            await darts_menu(update, context)
            return

        elif text == "🏆 Топ игроков":  # ← ДОБАВЬТЕ ЭТОТ БЛОК
            await top_players(update, context)

        elif text == "🔄 Трейд":  # ← ДОБАВЬТЕ
            await trade_menu(update, context)

    except (NetworkError, TimedOut) as e:
        logger.warning(f"Сетевая ошибка: {e}")

    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")

async def add_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начинает процесс добавления новой карточки."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        
        if not is_admin(user_id, data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        # ⭐ НОВОЕ: Запрашиваем отправку файла ⭐
        context.user_data[user_id] = {
            "step": ADD_CARD_WAITING_MEDIA
        }
        
        await update.message.reply_text(
            "➕ **Добавление новой карты**\n\n"
            "📤 **Шаг 1/4:** Отправьте фото или видео карты\n\n"
            "⚠️ Поддерживаются:\n"
            "• 📷 Фото (JPG, PNG)\n"
            "• 🎬 Видео (MP4, WEBM)\n"
            "• 🎞 Анимации (GIF)\n\n"
            "❌ Для отмены: /cancel",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в add_card: {e}")
        await update.message.reply_text("❌ Ошибка при запуске добавления карты")

async def list_cards(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Список всех карточек (с разбивкой на части)."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        if not data["cards"]:
            await update.message.reply_text("📭 Нет добавленных карточек.")
            return
        
        cards_list = []
        for card in data["cards"]:
            status = "✅" if card["available"] else "❌"
            
            card_info = (
                f"{status} ID: {card['id']}\n"
                f"📺 Тип: {'Анимация' if card.get('media_type') == 'animation' else 'Фото'}\n"
                f"🏷 {card['title']}\n"
                f"🌟 {card['rarity']}\n"
                f"🔗 {card['image_url'][:30]}...\n"
            )
            cards_list.append(card_info)
        
        # Разбиваем на сообщения по 4000 символов
        MAX_LENGTH = 4000
        current_message = "📋 Все карточки:\n"
        
        for card_info in cards_list:
            if len(current_message) + len(card_info) + 2 > MAX_LENGTH:
                await update.message.reply_text(current_message)
                current_message = "📋 Все карточки (продолжение):\n" + card_info
            else:
                current_message += card_info + "\n"
        
        if current_message.strip():
            await update.message.reply_text(current_message)
            
    except Exception as e:
        logger.error(f"Ошибка показа карточек: {e}")
        await update.message.reply_text("❌ Ошибка при получении списка")

async def process_add_card_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает полученный медиафайл для новой карты."""
    try:
        user_id = str(update.effective_user.id)
        
        if user_id not in context.user_data:
            return
        
        user_state = context.user_data[user_id]
        if user_state.get("step") != ADD_CARD_WAITING_MEDIA:
            return
        
        # ⭐ Определяем тип медиа ⭐
        file_id = None
        media_type = "photo"
        
        if update.message.photo:
            # Фото — берём самое большое
            file_id = update.message.photo[-1].file_id
            media_type = "photo"
        elif update.message.video:
            # Видео
            file_id = update.message.video.file_id
            media_type = "animation"  # Считаем как анимацию для автовоспроизведения
        elif update.message.animation:
            # GIF/анимация
            file_id = update.message.animation.file_id
            media_type = "animation"
        else:
            await update.message.reply_text(
                "❌ Неверный тип файла!\n"
                "Отправьте фото, видео или GIF."
            )
            return
        
        # ⭐ Сохраняем информацию о файле ⭐
        user_state["file_id"] = file_id
        user_state["media_type"] = media_type
        user_state["media_source"] = "file_id"  # ⭐ НОВОЕ: источник — file_id
        
        # ⭐ Переходим к следующему шагу ⭐
        user_state["step"] = ADD_CARD_WAITING_TITLE
        
        await update.message.reply_text(
            f"✅ Медиа получено!\n"
            f"📺 Тип: {'🎬 Видео/Анимация' if media_type == 'animation' else '📷 Фото'}\n\n"
            f"📝 **Шаг 2/4:** Введите название карты\n\n"
            f"❌ Для отмены: /cancel",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка process_add_card_media: {e}")
        await update.message.reply_text("❌ Ошибка при обработке файла")



async def toggle_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Включение/выключение карточки."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return

        if not context.args:
            await update.message.reply_text("ℹ️ Используйте: /toggle_card [ID]")
            return
        try:
            card_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("ℹ️ ID должен быть числом!")
            return

        for card in data["cards"]:
            if card["id"] == card_id:
                card["available"] = not card["available"]
                save_data(data)
                await update.message.reply_text(
                    f"ℹ️ Карточка #{card_id} {'включена' if card['available'] else 'выключена'}"
                )
                return
        await update.message.reply_text(f"⚠️ Карточка #{card_id} не найдена")
    except Exception as e:
        logger.error(f"Ошибка переключения карточки: {e}")
        await update.message.reply_text("❌ Ошибка при изменении")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Рассылка сообщения всем пользователям."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        if not context.args:
            await update.message.reply_text("ℹ️ Используйте: /broadcast [текст]")
            return
        message_text = " ".join(context.args)
        users = data.get("users", {})
        if not users:
            await update.message.reply_text("ℹ️ Нет пользователей для рассылки!")
            return
        status = await update.message.reply_text(
            f"📢 Рассылка для {len(users)} пользователей..."
        )
        success, failed = 0, 0
        for i, user_id in enumerate(users.keys(), 1):
            try:
                await context.bot.send_message(chat_id=user_id, text=message_text)
                success += 1
            except Exception as e:
                failed += 1
            if i % 5 == 0 or i == len(users):
                await status.edit_text(
                    f"📢 Отправлено {i}/{len(users)}\n✅ Успешно: {success} | ❌ Ошибок: {failed}"
                )
        await status.edit_text(
            f"✅ Рассылка завершена!\nВсего: {len(users)}\nУспешно: {success}\nОшибок: {failed}"
        )
    except Exception as e:
        logger.error(f"Ошибка рассылки: {e}")
        await update.message.reply_text("❌ Ошибка при рассылке")

async def reset_all_cards(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сброс всех карточек у всех пользователей."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        reset_count = 0
        for user_data in data["users"].values():
            if "cards" in user_data:
                user_data["cards"] = []
                reset_count += 1
        save_data(data)
        await update.message.reply_text(
            f"✅ Сброшены карточки у {reset_count} пользователей!"
        )
    except Exception as e:
        logger.error(f"Ошибка сброса карточек: {e}")
        await update.message.reply_text("❌ Ошибка при сбросе")

async def delete_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Полное удаление карточки из системы."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        if not context.args:
            await update.message.reply_text("ℹ️ Используйте: /delete_card [ID]")
            return
        try:
            card_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("ℹ️ ID должен быть числом!")
            return
            
        removed_users = 0
        
        # Удаляем из общего списка карт
        data["cards"] = [card for card in data["cards"] if card["id"] != card_id]
        
        # Удаляем из коллекций пользователей
        for user_data in data["users"].values():
            if "cards" in user_data and card_id in user_data["cards"]:
                user_data["cards"] = [
                    cid for cid in user_data["cards"] if cid != card_id
                ]
                removed_users += 1

        save_data(data)
        await update.message.reply_text(
            f"✅ Карточка #{card_id} удалена!\n"
            f"Удалена у {removed_users} пользователей."
        )

    except Exception as e:
        logger.error(f"Ошибка удаления карточки: {e}")
        await update.message.reply_text("❌ Ошибка при удалении")

async def reset_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сброс карточек конкретного пользователя."""

    try:
        data = load_data()

        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return

        if not context.args:
            await update.message.reply_text("ℹ️ Используйте: /reset_user [ID]")
            return
        target_user_id = context.args[0]

        if target_user_id in data["users"]:
            data["users"][target_user_id]["cards"] = []
            save_data(data)
            await update.message.reply_text(
                f"✅ Карточки пользователя {target_user_id} сброшены!"
            )

        else:
            await update.message.reply_text(
                f"ℹ️ Пользователь {target_user_id} не найден"
            )

    except Exception as e:
        logger.error(f"Ошибка сброса пользователя: {e}")
        await update.message.reply_text("❌ Ошибка при сбросе")

async def check_cards(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Статистика карточек с разбивкой по редкостям."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        all_cards = data.get("cards", [])
        total = len(all_cards)
        available = sum(1 for card in all_cards if card.get("available", True))
        disabled = total - available
        
        # ⭐ Статистика по редкостям (включая выключенные) ⭐
        rarity_stats = {}
        for card in all_cards:
            rarity = card.get("rarity", "Unknown")
            if rarity not in rarity_stats:
                rarity_stats[rarity] = {"total": 0, "available": 0, "disabled": 0}
            rarity_stats[rarity]["total"] += 1
            if card.get("available", True):
                rarity_stats[rarity]["available"] += 1
            else:
                rarity_stats[rarity]["disabled"] += 1
        
        # ⭐ Формируем текст ⭐
        message_text = (
            f"📊 **Общая статистика карт**\n"
            f"📦 Всего карт: {total}\n"
            f"✅ Включено: {available}\n"
            f"❌ Выключено: {disabled}\n"
            f"👥 Пользователей: {len(data.get('users', {}))}\n\n"
            f"📈 **По редкостям:**\n"
        )
        
        # ⭐ Сортировка редкостей в логическом порядке ⭐
        rarity_order = [
            "Common", "Rare", "Rare Team-up",
            "Epic", "Epic Team-up",
            "Legendary", "Legendary Team-up",
            "Highlight", "Limited"
        ]
        
        # Сначала выводим известные редкости в порядке
        for rarity in rarity_order:
            if rarity in rarity_stats:
                stats = rarity_stats[rarity]
                message_text += (
                    f"• **{rarity}**: {stats['total']} "
                    f"(✅{stats['available']} / ❌{stats['disabled']})\n"
                )
        
        # Затем выводим неизвестные редкости (если появятся)
        for rarity, stats in rarity_stats.items():
            if rarity not in rarity_order:
                message_text += (
                    f"• **{rarity}**: {stats['total']} "
                    f"(✅{stats['available']} / ❌{stats['disabled']})\n"
                )
        
        await update.message.reply_text(message_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка проверки статистики: {e}")
        await update.message.reply_text("❌ Ошибка при проверке")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Перечисляет всех пользователей бота с краткой статистикой."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        users = data.get("users", {})
        if not users:
            await update.message.reply_text("📭 Нет пользователей!")
            return
        
        # ⭐ Сортируем пользователей по ID ⭐
        sorted_users = sorted(users.items(), key=lambda x: x[0])
        
        # ⭐ Формируем список ⭐
        user_lines = []
        for uid, udata in sorted_users:
            first_name = udata.get("first_name", "")
            last_name = udata.get("last_name", "")
            username = udata.get("username", "")
            
            # Формируем отображаемое имя
            if username:
                display_name = f"@{username}"
            elif first_name or last_name:
                display_name = f"{first_name} {last_name}".strip()
            else:
                display_name = "Без имени"
            
            # ⭐ ЭКРАНИРОВАНИЕ СПЕЦСИМВОЛОВ MARKDOWN ⭐
            display_name_escaped = escape_markdown(display_name)
            
            # Краткая статистика
            cards_count = len(udata.get("cards", []))
            cents = udata.get("cents", 0)
            season_points = udata.get("season_points", 0)
            total_points = udata.get("total_points", 0)
            
            # Проверяем, является ли пользователь админом
            is_user_admin = "⚙️" if uid in data.get("admins", []) else ""
            
            user_lines.append(
                f"`{uid}` {is_user_admin} — {display_name_escaped}\n"
                f"   🃏{cards_count} | 💰{cents} | 💥{season_points} | 💎{total_points}"
            )
        
        # ⭐ Разбиваем на сообщения по 4000 символов ⭐
        MAX_LENGTH = 4000
        header = f"👥 **Всего пользователей: {len(users)}**\n\n"
        
        current_message = header
        for line in user_lines:
            if len(current_message) + len(line) + 2 > MAX_LENGTH:
                await update.message.reply_text(current_message, parse_mode="Markdown")
                current_message = f"👥 **Пользователи (продолжение):**\n\n" + line + "\n"
            else:
                current_message += line + "\n"
        
        if current_message.strip() and current_message != header:
            await update.message.reply_text(current_message, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка list_users: {e}")
        await update.message.reply_text("❌ Ошибка при получении списка")

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список администраторов."""

    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        admins = data.get("admins", [])

        if not admins:
            await update.message.reply_text("Список администраторов пуст.")
            return
        response = "👥 Администраторы:\n"

        for admin_id in admins:
            # Попробуем получить username из данных пользователя (если есть)
            user_info = data["users"].get(admin_id, {})
            name = user_info.get("username") or user_info.get("first_name") or admin_id
            response += f"• {admin_id} (@{name})\n"
        await update.message.reply_text(response)

    except Exception as e:
        logger.error(f"Ошибка при показе админов: {e}")
        await update.message.reply_text(
            "❌ Ошибка при получении списка администраторов"
        )

async def edit_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Редактирование параметров карты."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/edit_card [ID] [параметр] [новое_значение]\n"
                "**Параметры:**\n"
                "• title - название карты\n"
                "• url - URL изображения\n"
                "• rarity - редкость\n"
                "• catchphrase - цитата (или 'нет')\n"
                "• available - статус (true/false)\n"
                "• classic - метка Classic (да/нет)\n"
                "• media - заменить медиафайл (отправьте фото/видео после команды)",
                parse_mode="Markdown",
            )
            return

        card_id = int(context.args[0])
        param = context.args[1].lower()

        # ⭐ НОВОЕ: Для параметра media не требуется значение в команде ⭐
        if param == "media":
            # Проверяем, что карта существует
            card = find_card_by_id(card_id, data["cards"])
            if not card:
                await update.message.reply_text(f"❌ Карта с ID {card_id} не найдена!")
                return
    
            # ⭐ Переходим в состояние ожидания медиа ⭐
            context.user_data[str(update.effective_user.id)] = {
                "step": "edit_card_waiting_media",
                "edit_card_id": card_id
            }
    
            await update.message.reply_text(
                f"📝 **Редактирование карты #{card_id}**\n"
                f"🏷 {card.get('title')}\n\n"
                f"📤 **Отправьте новое фото или видео** для замены медиафайла\n\n"
                f"❌ Для отмены: /cancel",
                parse_mode="Markdown"
            )
            return

        # Для остальных параметров требуется значение
        if len(context.args) < 3:
            await update.message.reply_text(
                f"⚠️ Для параметра `{param}` нужно указать значение!\n\n"
                f"Пример: `/edit_card {card_id} {param} новое_значение`",
                parse_mode="Markdown"
            )
            return

        new_value = " ".join(context.args[2:])
        
        card = find_card_by_id(card_id, data["cards"])
        if not card:
            await update.message.reply_text(f"⚠️ Карта #{card_id} не найдена")
            return
        
        # ⭐ ДОБАВЛЯЕМ classic В СПИСОК ДОПУСТИМЫХ ПАРАМЕТРОВ
        valid_params = ["title", "url", "rarity", "available", "catchphrase", "classic"]
        if param not in valid_params:
            await update.message.reply_text(
                f"⚠️ Неверный параметр! Доступные: {', '.join(valid_params)}"
            )
            return
        
        old_value = card.get(param, "не задано")
        
        if param == "available":
            new_value_bool = new_value.lower() in ["true", "1", "yes", "вкл", "on", "да"]
            card[param] = new_value_bool
            display_new = new_value_bool
            display_old = old_value
            
        # ⭐ НОВОЕ: ОБРАБОТКА ПАРАМЕТРА classic
        elif param == "classic":
            new_value_bool = new_value.lower() in ["да", "true", "1", "yes", "classic"]
            card["is_classic"] = new_value_bool
            display_new = "Да" if new_value_bool else "Нет"
            display_old = "Да" if card.get("is_classic") else "Нет"
            
        elif param == "catchphrase":
            if new_value.lower() != "нет":
                card[param] = new_value.replace("\\n", "\n")
            else:
                card[param] = None
            display_new = new_value
            display_old = old_value
            
        elif param == "rarity":
            if new_value not in RARITY_BONUSES:
                await update.message.reply_text(
                    f"⚠️ Недопустимая редкость!\n"
                    f"Доступные: {', '.join(RARITY_BONUSES.keys())}"
                )
                return
            card[param] = new_value
            card["media_type"] = determine_media_type(card.get("image_url", ""), new_value)
            display_new = new_value
            display_old = old_value
            
        elif param == "url":
            card["image_url"] = new_value
            card["media_type"] = determine_media_type(new_value, card.get("rarity", ""))
            display_new = new_value
            display_old = old_value

        elif param == "media":
            # ⭐ НОВОЕ: Замена медиафайла ⭐
            if not update.message.photo and not update.message.video and not update.message.animation:
                await update.message.reply_text(
                    "⚠️ Отправьте фото или видео для замены!\n"
                    "Используйте: /edit_card [ID] media"
                )
                return
    
            # Определяем file_id
            if update.message.photo:
                new_file_id = update.message.photo[-1].file_id
                new_media_type = "photo"
            elif update.message.video:
                new_file_id = update.message.video.file_id
                new_media_type = "animation"
            elif update.message.animation:
                new_file_id = update.message.animation.file_id
                new_media_type = "animation"
    
            card["file_id"] = new_file_id
            card["media_source"] = "file_id"
            card["media_type"] = new_media_type
            card["image_url"] = ""  # Очищаем URL
    
            await update.message.reply_text(
                f"✅ Медиа карты #{card_id} обновлено!\n"
                f"📺 Тип: {'🎬 Видео' if new_media_type == 'animation' else '📷 Фото'}\n"
                f"📤 Источник: file_id"
            )
            return
            
        else:  # title
            card[param] = new_value
            display_new = new_value
            display_old = old_value
        
        save_data(data)
        
        # ⭐ ФОРМИРУЕМ ОТВЕТ С УЧЁТОМ classic
        response = (
            f"✅ **Карта #{card_id} обновлена!**\n"
            f"📝 Параметр: {param}\n"
            f"❌ Было: {display_old}\n"
            f"✅ Стало: {display_new}\n"
            f"🏷 {card.get('title')}\n"
            f"🌟 {card.get('rarity')}\n"
            f"{'✅ Включена' if card.get('available') else '❌ Выключена'}"
        )
        if card.get("is_classic"):
            response += "\n🏛 **Classic**"
        if card.get("catchphrase"):
            response += f"\n💬 _\"{card['catchphrase']}\"_"
            
        await update.message.reply_text(response, parse_mode="Markdown")
        
    except ValueError:
        await update.message.reply_text("⚠️ ID должен быть числом!")
    except Exception as e:
        logger.error(f"Ошибка редактирования карты: {e}")
        await update.message.reply_text("❌ Ошибка при редактировании")
        
async def card_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает подробную информацию о карте."""
    try:
        if not context.args:
            await update.message.reply_text("ℹ️ Используйте: /card_info [ID]")
            return
        
        card_id = int(context.args[0])
        data = load_data()
        card = find_card_by_id(card_id, data["cards"])
        
        if not card:
            await update.message.reply_text(f"⚠️ Карта #{card_id} не найдена")
            return
        
        # Считаем у скольких игроков есть эта карта
        players_count = 0
        for user_data in data["users"].values():
            if card_id in user_data.get("cards", []):
                players_count += 1
        
        info_text = (
            f"📊 **Информация о карте #{card_id}**\n"
            f"🏷 **Название:** {card.get('title')}\n"
            f"🌟 **Редкость:** {card.get('rarity')}\n"
            f"🏛 **Classic:** {'Да' if card.get('is_classic') else 'Нет'}\n"
        )

        if card.get("catchphrase"):
            info_text += f"💬 _\"{card['catchphrase']}\"_\n"
        
        info_text += (
            f"📺 **Тип:** {'Анимация' if card.get('media_type') == 'animation' else 'Фото'}\n"
            f"{'✅ **Статус:** Включена\n' if card.get('available') else '❌ **Статус:** Выключена\n'}"
            f"🔗 **URL:** `{card.get('image_url')}`\n"
            f"👥 **Есть у игроков:** {players_count}\n"
        )
        
        await update.message.reply_text(info_text, parse_mode="Markdown")
        
    except ValueError:
        await update.message.reply_text("⚠️ ID должен быть числом!")
    except Exception as e:
        logger.error(f"Ошибка показа инфо карты: {e}")
        await update.message.reply_text("❌ Ошибка")

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавляет нового администратора."""
    try:

        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return

        if not context.args:
            await update.message.reply_text(
                "ℹ️ Используйте: /add_admin [ID пользователя]"
            )
            return
        new_admin_id = context.args[0]
        admins = data.setdefault("admins", [])

        if new_admin_id in admins:
            await update.message.reply_text(
                f"ℹ️ Пользователь {new_admin_id} уже администратор."
            )
            return
        admins.append(new_admin_id)
        save_data(data)
        await update.message.reply_text(
            f"✅ Пользователь {new_admin_id} добавлен в администраторы."
        )
    except Exception as e:
        logger.error(f"Ошибка добавления админа: {e}")
        await update.message.reply_text("❌ Ошибка при добавлении администратора")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаляет администратора."""
    try:
        data = load_data()

        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return

        if not context.args:
            await update.message.reply_text(
                "ℹ️ Используйте: /remove_admin [ID пользователя]"
            )
            return
        admin_id = context.args[0]
        admins = data.get("admins", [])
        
        if admin_id not in admins:
            await update.message.reply_text(
                f"ℹ️ Пользователь {admin_id} не является администратором."
            )
            return

        # Нельзя удалить последнего админа (по желанию)
        if len(admins) == 1:
            await update.message.reply_text(
                "⚠️ Нельзя удалить последнего администратора!"
            )
            return
            
        admins.remove(admin_id)
        save_data(data)
        await update.message.reply_text(
            f"✅ Пользователь {admin_id} удалён из администраторов."
        )
    except Exception as e:
        logger.error(f"Ошибка удаления админа: {e}")
        await update.message.reply_text("❌ Ошибка при удалении администратора")
        
async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Бросок кубика для получения бесплатных попыток (раз в неделю, с Бэт-пассом — 2 раза)."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data:
            user_data = {
                "username": update.effective_user.username or "",
                "first_name": update.effective_user.first_name or "",
                "last_name": update.effective_user.last_name or "",
                "cards": [],
                "total_points": 0,
                "season_points": 0,
                "cents": 0,
                "last_card_time": 0,
                "free_rolls": 0,
                "last_dice_time": 0,
            }
            data["users"][user_id] = user_data

        # ⭐ Миграция для старых пользователей ⭐
        if "weekly_dice_rolls" not in user_data:
            user_data["weekly_dice_rolls"] = 1
        
        # ⭐ ПРОВЕРКА ЕЖЕНЕДЕЛЬНОГО СБРОСА ⭐
        check_dice_reset(user_data)
        
        # ⭐ НОВОЕ: Проверяем Бэт-пасс для определения максимума бросков ⭐
        max_rolls = 2 if is_batpass_active(user_data) else 1
        
        # ⭐ Проверяем, есть ли доступные броски ⭐
        rolls_left = user_data.get("weekly_dice_rolls", 0)
        
        if rolls_left <= 0:
            # ⭐ Броски закончились — показываем время до следующего понедельника ⭐
            import datetime
            msk_tz = datetime.timezone(datetime.timedelta(hours=3))
            now_msk = datetime.datetime.now(msk_tz)
            
            days_until_monday = (7 - now_msk.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
                
            next_monday = now_msk.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=days_until_monday)
            remaining_seconds = int((next_monday - now_msk).total_seconds())
            
            days = remaining_seconds // 86400
            hours = (remaining_seconds % 86400) // 3600
            minutes = (remaining_seconds % 3600) // 60
            
            time_text = ""
            if days > 0:
                time_text += f"{days} дн. "
            time_text += f"{hours} ч {minutes} мин"
            
            # ⭐ НОВОЕ: Показываем лимит с учётом Бэт-пасса ⭐
            batpass_text = " (🎫 Бэт-пасс: 2 броска/нед.)" if is_batpass_active(user_data) else ""
            
            await update.message.reply_text(
                f"⏳ **Все броски кубика на этой неделе использованы!**\n\n"
                f"🎲 Лимит: {max_rolls} бросок(а){batpass_text}\n"
                f"⏳ Следующий бросок через: {time_text}\n"
                f"📅 В понедельник в 00:00 МСК",
                parse_mode="Markdown"
            )
            return

        # ⭐ ОТПРАВЛЯЕМ НАСТОЯЩИЙ КУБИК TELEGRAM ⭐
        sent_dice = await context.bot.send_dice(chat_id=update.effective_chat.id, emoji="🎲")
        dice_value = sent_dice.dice.value  # Значение от 1 до 6
        
        # Добавляем бесплатные попытки (ровно столько, сколько выпало)
        user_data["free_rolls"] = user_data.get("free_rolls", 0) + dice_value
        
        # ⭐ НОВОЕ: Уменьшаем счётчик бросков ⭐
        user_data["weekly_dice_rolls"] = rolls_left - 1
        user_data["last_dice_time"] = int(time.time())  # Для обратной совместимости
        save_data(data)
        
        rolls_left_after = user_data["weekly_dice_rolls"]
        
        await asyncio.sleep(4)
        
        # ⭐ Формируем текст с учётом оставшихся бросков ⭐
        if rolls_left_after > 0:
            remaining_text = f"🎲 Осталось бросков на этой неделе: **{rolls_left_after}**"
        else:
            remaining_text = "✅ Все броски на этой неделе использованы!\n📅 Следующий бросок в понедельник в 00:00 МСК"
        
        batpass_info = ""
        if is_batpass_active(user_data):
            batpass_info = "\n🎫 _Бэт-пасс: 2 броска/нед._"
        
        await update.message.reply_text(
            f"🔍 **Получено бесплатных попыток:** {dice_value}\n"
            f"📊 **Всего бесплатных попыток:** {user_data['free_rolls']}\n\n"
            f"{remaining_text}"
            f"{batpass_info}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка броска кубика: {e}")
        await update.message.reply_text("❌ Произошла ошибка")

def check_dice_reset(user_data: Dict) -> None:
    """Проверяет и сбрасывает возможность броска кубика в понедельник в 00:00 по МСК."""
    import datetime
    msk_tz = datetime.timezone(datetime.timedelta(hours=3))
    now_msk = datetime.datetime.now(msk_tz)
    
    # Получаем текущий год и номер недели по ISO (понедельник - первый день недели)
    current_year, current_week, _ = now_msk.isocalendar()
    last_year = user_data.get("last_dice_reset_year", 0)
    last_week = user_data.get("last_dice_reset_week", 0)
    
    # ⭐ Миграция для старых пользователей ⭐
    if "weekly_dice_rolls" not in user_data:
        user_data["weekly_dice_rolls"] = 1
    
    # Если год или неделя изменились, сбрасываем счётчик
    if last_year == 0 or current_year != last_year or current_week != last_week:
        # ⭐ НОВОЕ: Определяем количество бросков по Бэт-пассу ⭐
        max_rolls = 2 if is_batpass_active(user_data) else 1
        user_data["weekly_dice_rolls"] = max_rolls
        user_data["last_dice_time"] = 0  # Для обратной совместимости
        user_data["last_dice_reset_year"] = current_year
        user_data["last_dice_reset_week"] = current_week


async def dice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки кубика."""
    await dice(update, context)


async def bar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню Бара."""
    try:
        # ⭐ КЛАВИАТУРА С КНОПКАМИ ⭐
        keyboard = [
            [KeyboardButton("🎲 Кубик"), KeyboardButton("🎰 Казино"), KeyboardButton("🏀 Баскет")],
            [KeyboardButton("🎯 Дартс"), KeyboardButton("🏆 Топ игроков"), KeyboardButton("🔄 Трейд")],
            [KeyboardButton("🔥 Сжигание"), KeyboardButton("🔗 Рефералка"), KeyboardButton("🔙 Назад")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text="🍺 Добро пожаловать в Бар!",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Ошибка в bar_menu: {e}")
        


async def casino_play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Игра в казино."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        if not user_data:
            await query.edit_message_text("❌ Вы ещё не начали игру!")
            return

        # ⭐ ПРОВЕРКА: является ли пользователь админом ⭐
        is_super_admin = (user_id == SUPER_ADMIN_ID)

        # Проверяем сброс попыток
        check_casino_reset(user_data)
        attempts = user_data.get("casino_attempts", 0)
        cents = user_data.get("cents", 0)        
        
        # ⭐ АДМИНЫ ПРОПУСКАЮТ ПРОВЕРКИ ⭐
        if not is_super_admin:
            # Проверяем попытки
            if attempts <= 0:
                await query.edit_message_text(
                    "❌ **Лимит попыток исчерпан!**\n\n"
                    "Приходите завтра после 00:00 МСК 🕛",
                    parse_mode="Markdown",
                )
                return

            # Проверяем баланс
            if cents < 1500:
                await query.edit_message_text(
                    f"❌ **Недостаточно бэт-коинов!**\n\n"
                    f"Нужно: 1500 бэт-коинов\n"
                    f"У вас: {cents} бэт-коинов\n\n",
                    parse_mode="Markdown",
                )
                return

            # Списываем центы и попытки
            user_data["cents"] -= 1500
            user_data["casino_attempts"] -= 1
        save_data(data)        
        # ⭐ ОТПРАВЛЯЕМ СЛОТ TELEGRAM ⭐
        sent_slot = await context.bot.send_dice(
            chat_id=query.message.chat_id, emoji="🎰"
        )
        
        # ⭐ ПОЛУЧАЕМ ЗНАЧЕНИЕ (1-64) ⭐
        slot_value = sent_slot.dice.value

        # ⭐ ПРОВЕРЯЕМ ПОБЕДУ (только 1, 22, 43, 64) ⭐
        is_win = slot_value in [1, 22, 43, 64]

        # ⭐ КНОПКА "СЫГРАТЬ ЕЩЁ" ⭐
        keyboard = [[InlineKeyboardButton("🎰 Сыграть ещё", callback_data="casino_play")]]
        
        if is_win:
            # Добавляем 10 бесплатных попыток
            await asyncio.sleep(2)
            user_data["free_rolls"] = user_data.get("free_rolls", 0) + 10
            save_data(data)
            await query.message.reply_text(
                f"🎉 **ДЖЕКПОТ!** 🎉\n\n"
                f"✨ **3 одинаковых символа!**\n"
                f"🎁 Получено: 10 бесплатных попыток\n"
                f"📊 Всего попыток: {user_data['free_rolls']}\n\n"
                f"🎲 Осталось игр в казино: {user_data['casino_attempts']}",
                reply_markup=InlineKeyboardMarkup(keyboard), 
                parse_mode="Markdown",
            )
            await update_weekly_quest_progress(context, user_id, "weekly_casino_win", 1)

        else:
            await asyncio.sleep(2)
            #attempts = user_data['casino_attempts'] + 2 if is_batpass_active(user_data) else user_data['casino_attempts']
            
            await query.message.reply_text(
                f"😔 Не повезло! Попробуйте ещё раз.\n\n"
                f"💰 Списано: 1500 бэт-коинов\n"
                f"🎲 Осталось попыток: {user_data['casino_attempts']}\n"
                f"💰 Ваш баланс: {user_data['cents']} бэт-коинов",
                reply_markup=InlineKeyboardMarkup(keyboard), 
                parse_mode="Markdown",
            )
            
    except Exception as e:
        logger.error(f"Ошибка в casino_play: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


async def casino_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        query = update.callback_query
        await query.answer()
        if query.data == "casino_menu":
            await casino_menu(update, context)

        elif query.data == "casino_play":
            await casino_play(update, context)

    except Exception as e:
        logger.error(f"Ошибка casino_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def add_card_to_player(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавляет карту игроку по ID или @никнейму."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        # Проверяем аргументы
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/add_card_to_player [ID_или_@никнейм] [ID_карты] [количество]\n"
                "**Примеры:**\n"
                "/add_card_to_player 881692999 45 - добавить 1 карту\n"
                "/add_card_to_player @username 45 5 - добавить 5 карт",
                parse_mode="Markdown",
            )
            return
        
        target_input = context.args[0]
        card_id = int(context.args[1])
        count = int(context.args[2]) if len(context.args) > 2 else 1
        
        # ⭐ ОПРЕДЕЛЯЕМ ID ИГРОКА ⭐
        target_user_id = None
        if target_input.startswith("@"):
            username_to_find = target_input[1:].strip().lower()
            for uid, udata in data["users"].items():
                if udata.get("username", "").lower() == username_to_find:
                    target_user_id = uid
                    break
            if not target_user_id:
                await update.message.reply_text(f"⚠️ Игрок с никнеймом @{username_to_find} не найден!")
                return
        else:
            target_user_id = target_input
        
        # Проверяем существование карты
        card = find_card_by_id(card_id, data["cards"])
        if not card:
            await update.message.reply_text(f"⚠️ Карта #{card_id} не найдена!")
            return
        
        # Добавляем карту(ы) в коллекцию игрока
        user_data = data["users"].get(target_user_id)
        if not user_data:
            await update.message.reply_text(f"⚠️ Игрок с ID {target_user_id} не найден!")
            return
        
        if "cards" not in user_data:
            user_data["cards"] = []
        
        for _ in range(count):
            user_data["cards"].append(card_id)
        
        save_data(data)
        
        # ⭐ ОТЧЁТ АДМИНУ ⭐
        await update.message.reply_text(
            f"✅ **Карта добавлена!**\n"
            f"👤 Игрок: {target_user_id}\n"
            f"🃏 Карта: {card['title']} (#{card_id})\n"
            f"🌟 Редкость: {card['rarity']}\n"
            f"📦 Количество: {count} шт.\n"
            f"📊 Всего карт у игрока: {len(user_data['cards'])}",
            parse_mode="Markdown",
        )
        
        # ⭐ НОВОЕ: УВЕДОМЛЕНИЕ ИГРОКУ ⭐
        try:
            # Формируем caption
            if count > 1:
                caption_text = (
                    f"🎁 <b>Вам была выдана награда!</b>\n\n"
                    f"🃏 <b>Карта:</b> {card['title']}\n"
                    f"🌟 <b>Редкость:</b> {card['rarity']}\n"
                    f"📦 <b>Количество:</b> {count} шт."
                )
            else:
                caption_text = (
                    f"🎁 <b>Вам была выдана награда!</b>\n\n"
                    f"🃏 <b>Карта:</b> {card['title']}\n"
                    f"🌟 <b>Редкость:</b> {card['rarity']}"
                )
            
            # ⭐ Универсальная логика: file_id или URL ⭐
            media_source = card.get("media_source", "url")
            media_value = card.get("file_id") if media_source == "file_id" else card.get("image_url", "")
            
            if not media_value:
                # Если медиа нет, отправляем просто текст
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=caption_text,
                    parse_mode="HTML"
                )
            elif card.get("media_type") == "animation" or (isinstance(media_value, str) and media_value.lower().endswith((".mp4", ".webm", ".gif"))):
                await context.bot.send_video(
                    chat_id=target_user_id,
                    video=media_value,
                    caption=caption_text,
                    parse_mode="HTML",
                    supports_streaming=True
                )
            else:
                await context.bot.send_photo(
                    chat_id=target_user_id,
                    photo=media_value,
                    caption=caption_text,
                    parse_mode="HTML"
                )
        except Exception as notify_error:
            logger.warning(f"Не удалось уведомить игрока {target_user_id}: {notify_error}")
            # Не прерываем работу — админу уже отправили отчёт
        
        logger.info(f"Админ {update.effective_user.id} выдал карту #{card_id} игроку {target_user_id} (x{count})")
        
    except ValueError:
        await update.message.reply_text("⚠️ ID карты и количество должны быть числами!")
    except Exception as e:
        logger.error(f"Ошибка добавления карты игроку: {e}")
        await update.message.reply_text("❌ Ошибка при добавлении карты")

async def add_rolls_to_player(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавляет определённое количество бесплатных попыток игроку."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        # Проверяем аргументы
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/add_rolls_to_player [ID_или_@никнейм] [количество]\n"
                "**Примеры:**\n"
                "/add_rolls_to_player 881692999 10 - добавить 10 попыток\n"
                "/add_rolls_to_player @username 10 - добавить 10 попыток",
                parse_mode="Markdown",
            )
            return
        
        target_input = context.args[0]
        rolls_count = int(context.args[1])
        target_user_id = None
        is_new_user = False
        
        # ⭐ ОПРЕДЕЛЯЕМ ID ИГРОКА ⭐
        if target_input.startswith("@"):
            username_to_find = target_input[1:].strip().lower()
            for uid, udata in data["users"].items():
                if udata.get("username", "").lower() == username_to_find:
                    target_user_id = uid
                    break
            if not target_user_id:
                await update.message.reply_text(f"⚠️ Игрок с никнеймом @{username_to_find} не найден!")
                return
        else:
            target_user_id = target_input
            if target_user_id not in data["users"]:
                is_new_user = True
                # Создаём нового пользователя
                data["users"][target_user_id] = {
                    "username": "",
                    "first_name": "Admin Granted",
                    "last_name": "",
                    "cards": [],
                    "total_points": 0,
                    "season_points": 0,
                    "cents": 0,
                    "last_card_time": 0,
                    "free_rolls": 0,
                    "last_dice_time": 0,
                    "casino_attempts": 5,
                    "last_casino_reset": 0,
                    "used_promo_codes": [],
                    "referral_invites": [],
                    "referral_rewards_claimed": [],
                    "daily_quests": [],
                    "weekly_quests": [],
                    "avatar_url": DEFAULT_AVATAR_URL,
                    "avatars": [DEFAULT_AVATAR_URL],
                    "pending_season_boxes": 0,
                    "pending_rolls_box": 0,
                    "pending_superman_heroes_boxes": 0,
                    "pending_superman_villain_boxes": 0,
                    "last_daily_activity": None,
                    "registered_at": None,
                }
        
        user_data = data["users"][target_user_id]
        
        # Добавляем попытки
        old_rolls = user_data.get("free_rolls", 0)
        user_data["free_rolls"] = old_rolls + rolls_count
        save_data(data)
        
        # ⭐ ОТЧЁТ АДМИНУ ⭐
        await update.message.reply_text(
            f"✅ **Наймы добавлены!**\n"
            f"👤 Герой: {target_user_id}\n"
            f"🔍 Добавлено: {rolls_count}\n"
            f"📊 Было: {old_rolls}\n"
            f"📈 Стало: {user_data['free_rolls']}\n"
            f"{'🆕 Герой создан!' if is_new_user else ''}",
            parse_mode="Markdown",
        )
        
        # ⭐ НОВОЕ: УВЕДОМЛЕНИЕ ИГРОКУ ⭐
        try:
            # Определяем склонение слова "попытка"
            if rolls_count % 10 == 1 and rolls_count % 100 != 11:
                word = "попытка"
            elif rolls_count % 10 in [2, 3, 4] and rolls_count % 100 not in [12, 13, 14]:
                word = "попытки"
            else:
                word = "попыток"
            
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"🎁 <b>Вам была выдана награда!</b>\n\n"
                    f"🔍 <b>Получено:</b> {rolls_count} бесплатных {word}\n"
                    f"📊 <b>Всего попыток:</b> {user_data['free_rolls']}"
                ),
                parse_mode="HTML"
            )
        except Exception as notify_error:
            logger.warning(f"Не удалось уведомить игрока {target_user_id}: {notify_error}")
            # Не прерываем работу — админу уже отправили отчёт
        
        logger.info(f"Админ {update.effective_user.id} выдал {rolls_count} попыток игроку {target_user_id}")
        
    except ValueError:
        await update.message.reply_text("⚠️ Количество должно быть числом!")
    except Exception as e:
        logger.error(f"Ошибка добавления попыток: {e}")
        await update.message.reply_text("❌ Ошибка при добавлении попыток")

async def top_players(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает топ-10 игроков по очков репутации игроков по поинтам в сезоне (админы исключены)."""
    try:
        data = load_data()
        users = data.get("users", {})
        admin_list = data.get("admins", [])
        
        # ⭐ ФИЛЬТРУЕМ АДМИНОВ ⭐
        non_admin_users = {
            uid: udata for uid, udata in users.items()
            if uid not in admin_list
        }
        
        # Сортируем пользователей по season_points (только не-админы)
        sorted_users = sorted(
            non_admin_users.items(),
            key=lambda x: x[1].get("season_points", 0),
            reverse=True
        )
        
        # Берём топ-10
        top_10 = sorted_users[:10]
        
        # Формируем сообщение
        message_text = "🏆 **Топ игроков этого сезона**\n\n"
        
        if not top_10:
            message_text += "📭 Пока нет игроков в топе!"
        else:
            for rank, (user_id, user_data) in enumerate(top_10, 1):
                # Получаем имя из профиля Telegram
                first_name = user_data.get("first_name", "Игрок")
                last_name = user_data.get("last_name", "")
                
                # Формируем полное имя
                if last_name:
                    username = f"{first_name} {last_name}"
                else:
                    username = first_name
                
                points = user_data.get("season_points", 0)
                
                # Медали для топ-3
                if rank == 1:
                    medal = "🥇"
                elif rank == 2:
                    medal = "🥈"
                elif rank == 3:
                    medal = "🥉"
                else:
                    medal = f"{rank}."
                
                message_text += f"{medal} **{username}** — {points} очков репутации\n"
        
        # ⭐ ПОКАЗЫВАЕМ МЕСТО ТОЛЬКО ЕСЛИ ПОЛЬЗОВАТЕЛЬ НЕ АДМИН ⭐
        current_user_id = str(update.effective_user.id)
        
        # Проверяем, является ли текущий пользователь админом
        if current_user_id not in admin_list:
            current_user_data = users.get(current_user_id, {})
            current_points = current_user_data.get("season_points", 0)
            
            # Находим место пользователя (среди не-админов)
            user_rank = None
            for rank, (uid, _) in enumerate(sorted_users, 1):
                if uid == current_user_id:
                    user_rank = rank
                    break
            
            # Если пользователя нет в топе
            if not user_rank:
                user_rank = len(sorted_users) + 1
            
            message_text += "\n" + "─" * 30 + "\n"
            
            if user_rank <= 10:
                message_text += f"✅ **Ваше место:** {user_rank}\n"
            else:
                message_text += f"📍 **Ваше место:** {user_rank}\n"
            
            message_text += f"💥 **Ваши очки репутации:** {current_points}"
        else:
            # ⭐ ДЛЯ АДМИНОВ - СООБЩЕНИЕ ЧТО ОНИ НЕ УЧАСТВУЮТ ⭐
            message_text += "\n" + "─" * 30 + "\n"
            message_text += "⚙️ **Вы администратор**\n"
            message_text += "Ваш прогресс не учитывается в топе"
        
        await update.message.reply_text(
            message_text,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в top_players: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке топа")

async def top_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки обновления топа."""
    try:
        query = update.callback_query
        await query.answer()
        
        # Просто вызываем top_players заново
        await top_players(update, context)
        
    except Exception as e:
        logger.error(f"Ошибка в top_callback: {e}")
        await query.answer("❌ Ошибка при обновлении", show_alert=True)

async def reset_season_points(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сбрасывает поинты за сезон у конкретного игрока."""
    try:
        data = load_data()
        
        # Проверка на админа
        user_id = str(update.effective_user.id)
        if not is_admin(user_id, data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        # Проверяем аргументы
        if not context.args:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n\n"
                "/reset_season_points [ID_игрока]\n\n"
                "**Пример:**\n"
                "/reset_season_points 881692999",
                parse_mode="Markdown"
            )
            return
        
        target_user_id = context.args[0]
        
        # Проверяем существование игрока
        if target_user_id not in data["users"]:
            await update.message.reply_text(f"⚠️ Игрок {target_user_id} не найден!")
            return
        
        # Сохраняем старые поинты
        old_points = data["users"][target_user_id].get("season_points", 0)
        
        # Сбрасываем поинты
        data["users"][target_user_id]["season_points"] = 0
        
        save_data(data)
        
        # Получаем имя игрока
        player_data = data["users"][target_user_id]
        player_name = player_data.get("first_name", "Игрок")
        if player_data.get("last_name"):
            player_name += f" {player_data['last_name']}"
        
        await update.message.reply_text(
            f"✅ **Сезонные очки репутации сброшены!**\n\n"
            f"👤 Игрок: {player_name}\n"
            f"🆔 ID: {target_user_id}\n"
            f"📊 Было очков репутации: {old_points}\n"
            f"📈 Стало очков репутации: 0\n\n"
            f"⚠️ Общие очки репутации (total_points) не изменены.",
            parse_mode="HTML"
        )
        
        logger.info(f"Админ {user_id} сбросил сезонный очков репутации игроку {target_user_id} ({old_points} → 0)")
        
    except Exception as e:
        logger.error(f"Ошибка reset_season_points: {e}")
        await update.message.reply_text("❌ Ошибка при сбросе поинтов")

async def create_promo_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Создание промокода на карту."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        # Проверяем аргументы
        if not context.args or len(context.args) < 3:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/create_promo [КОД] [ID_карты] [кол-во_использований]\n"
                "**Примеры:**\n"
                "/create_promo NEWCARD2024 45 100\n"
                "/create_promo BONUS 12 50\n"
                "/create_promo RANDOMCARD random 100 ← **НОВАЯ ФУНКЦИЯ!**",
                parse_mode="Markdown"
            )
            return
        
        promo_code = context.args[0].upper()  # Приводим к верхнему регистру
        card_arg = context.args[1]
        max_uses = int(context.args[2])
        
        # Проверяем, существует ли уже такой промокод
        if promo_code in data["promo_codes"]:
            await update.message.reply_text(
                f"⚠️ Промокод **{promo_code}** уже существует!\n"
                f"Удалите его сначала командой /delete_promo {promo_code}",
                parse_mode="Markdown"
            )
            return
        
        # ⭐ ПРОВЕРЯЕМ ТИП КАРТЫ (КОНКРЕТНАЯ ИЛИ СЛУЧАЙНАЯ) ⭐
        is_random = card_arg.lower() == "random"
        
        if is_random:
            # ⭐ СОЗДАЁМ ПРОМОКОД НА СЛУЧАЙНУЮ КАРТУ ⭐
            data["promo_codes"][promo_code] = {
                "card_id": "random",  # Специальное значение для случайной карты
                "card_title": "Случайная карта",
                "card_rarity": "Random",
                "max_uses": max_uses,
                "current_uses": 0,
                "created_by": str(update.effective_user.id),
                "created_at": int(time.time()),
                "is_random": True  # Флаг для случайной карты
            }
            
            await update.message.reply_text(
                f"✅ **Промокод создан!**\n"
                f"🎁 Код: **{promo_code}**\n"
                f"🃏 Карта: **Случайная из доступных**\n"
                f"📊 Лимит использований: {max_uses}\n"
                f"⏰ Создан: {time.strftime('%d.%m.%Y %H:%M', time.localtime())}\n"
                f"Игроки могут активировать командой:\n"
                f"`/promo {promo_code}`",
                parse_mode="Markdown"
            )
        else:
            # ⭐ СОЗДАЁМ ПРОМОКОД НА КОНКРЕТНУЮ КАРТУ (СТАРАЯ ЛОГИКА) ⭐
            card_id = int(card_arg)
            
            # Проверяем существование карты
            card = find_card_by_id(card_id, data["cards"])
            if not card:
                await update.message.reply_text(f"⚠️ Карта #{card_id} не найдена!")
                return
            
            # Создаём промокод
            data["promo_codes"][promo_code] = {
                "card_id": card_id,
                "card_title": card["title"],
                "card_rarity": card["rarity"],
                "max_uses": max_uses,
                "current_uses": 0,
                "created_by": str(update.effective_user.id),
                "created_at": int(time.time()),
                "is_random": False
            }
            
            await update.message.reply_text(
                f"✅ **Промокод создан!**\n"
                f"🎁 Код: **{promo_code}**\n"
                f"🃏 Карта: {card['title']} (#{card_id})\n"
                f"🌟 Редкость: {card['rarity']}\n"
                f"📊 Лимит использований: {max_uses}\n"
                f"⏰ Создан: {time.strftime('%d.%m.%Y %H:%M', time.localtime())}\n"
                f"Игроки могут активировать командой:\n"
                f"`/promo {promo_code}`",
                parse_mode="Markdown"
            )
        
        save_data(data)
        logger.info(f"Админ создал промокод {promo_code} {'на случайную карту' if is_random else f'на карту #{card_arg}'}")
        
    except ValueError:
        await update.message.reply_text("⚠️ ID карты и количество должны быть числами!")
    except Exception as e:
        logger.error(f"Ошибка create_promo_code: {e}")
        await update.message.reply_text("❌ Ошибка при создании промокода")

async def activate_promo_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Активация промокода игроком."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        
        # Проверяем аргументы
        if not context.args:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/promo [КОД]\n"
                "**Пример:**\n"
                "/promo NEWCARD2024",
                parse_mode="Markdown"
            )
            return
        
        promo_code = context.args[0].upper()  # Приводим к верхнему регистру
        
        # Проверяем существование промокода
        if promo_code not in data["promo_codes"]:
            await update.message.reply_text(
                "❌ **Промокод не найден!**\n"
                "Проверьте правильность ввода кода."
            )
            return
        
        promo_info = data["promo_codes"][promo_code]
        
        # Проверяем, не использовал ли игрок этот промокод раньше
        user_data = data["users"].get(user_id, {})
        used_promo_codes = user_data.get("used_promo_codes", [])
        if promo_code in used_promo_codes:
            await update.message.reply_text(
                "❌ **Вы уже использовали этот промокод!**\n"
                "Один промокод можно активировать только один раз."
            )
            return
        
        # Проверяем лимит использований
        if promo_info["current_uses"] >= promo_info["max_uses"]:
            await update.message.reply_text(
                "❌ **Лимит активаций исчерпан!**\n"
                "Этот промокод больше не действителен."
            )
            return
        
        # ⭐ ПРОВЕРЯЕМ ТИП КАРТЫ (СЛУЧАЙНАЯ ИЛИ КОНКРЕТНАЯ) ⭐
        is_random = promo_info.get("is_random", False)
        
        if is_random:
            # ⭐ ВЫБИРАЕМ СЛУЧАЙНУЮ КАРТУ ИЗ ДОСТУПНЫХ ⭐
            available_cards = [
                card for card in data["cards"]
                if card.get("available", True)
            ]
            
            if not available_cards:
                await update.message.reply_text(
                    "❌ **Ошибка!**\n"
                    "В системе нет доступных карт для выдачи."
                )
                return
            
            # Выбираем случайную карту
            card = random.choice(available_cards)
            card_id = card["id"]
        else:
            # ⭐ СТАРАЯ ЛОГИКА: КОНКРЕТНАЯ КАРТА ⭐
            card_id = promo_info["card_id"]
            card = find_card_by_id(card_id, data["cards"])
            if not card:
                await update.message.reply_text(
                    "❌ **Ошибка!**\n"
                    "Карта для этого промокода больше не существует."
                )
                return
        
        # Проверяем, существует ли пользователь в базе
        if user_id not in data["users"]:
            user_data = {
                "username": update.effective_user.username or "",
                "first_name": update.effective_user.first_name or "",
                "last_name": update.effective_user.last_name or "",
                "cards": [],
                "total_points": 0,
                "season_points": 0,
                "cents": 0,
                "last_card_time": 0,
                "free_rolls": 0,
                "last_dice_time": 0,
                "used_promo_codes": []
            }
            data["users"][user_id] = user_data
        
        # Добавляем карту игроку
        data["users"][user_id]["cards"].append(card_id)
        
        # Отмечаем промокод как использованный
        data["users"][user_id]["used_promo_codes"].append(promo_code)
        
        # Увеличиваем счётчик использований
        data["promo_codes"][promo_code]["current_uses"] += 1
        
        save_data(data)
        
        # Отправляем карту игроку
        caption = (
            f"🎉 Промокод активирован!\n"
            f"🃏 Вы получили: {card['title']}\n"
            f"🌟 Редкость: {card['rarity']}\n"
            f"Приятной игры!"
        )
        await send_card(update, card, context, caption=caption)
        
        logger.info(f"Игрок {user_id} активировал промокод {promo_code} {'(случайная карта)' if is_random else ''}")
        
    except Exception as e:
        logger.error(f"Ошибка activate_promo_code: {e}")
        await update.message.reply_text("❌ Ошибка при активации промокода")

async def delete_promo_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаление промокода."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        if not context.args:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/delete_promo [КОД]\n\n"
                "**Пример:**\n"
                "/delete_promo NEWCARD2024",
                parse_mode="Markdown"
            )
            return
        
        promo_code = context.args[0].upper()
        
        if promo_code not in data["promo_codes"]:
            await update.message.reply_text(f"⚠️ Промокод **{promo_code}** не найден!")
            return
        
        promo_info = data["promo_codes"][promo_code]
        del data["promo_codes"][promo_code]
        save_data(data)
        
        await update.message.reply_text(
            f"✅ **Промокод удалён!**\n\n"
            f"🎁 Код: {promo_code}\n"
            f"🃏 Карта: {promo_info['card_title']}\n"
            f"📊 Использован раз: {promo_info['current_uses']}/{promo_info['max_uses']}"
        )
        
        logger.info(f"Админ удалил промокод {promo_code}")
        
    except Exception as e:
        logger.error(f"Ошибка delete_promo_code: {e}")
        await update.message.reply_text("❌ Ошибка при удалении промокода")

async def list_promo_codes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Список всех промокодов."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        promo_codes = data.get("promo_codes", {})
        if not promo_codes:
            await update.message.reply_text("📭 Нет активных промокодов!")
            return
        
        message_text = "🎁 **Активные промокоды:**\n"
        for code, info in promo_codes.items():
            status = "✅ Активен" if info["current_uses"] < info["max_uses"] else "❌ Исчерпан"
            # ⭐ ДОБАВЛЯЕМ ТИП КАРТЫ ⭐
            card_type = "🎲 Случайная" if info.get("is_random", False) else f"🃏 {info['card_title']}"
            message_text += (
                f"🔖 **{code}**\n"
                f"{card_type}\n"
                f"📊 Использовано: {info['current_uses']}/{info['max_uses']}\n"
                f"📈 Статус: {status}\n"
                "\n"
            )
        
        # Разбиваем на сообщения по 4000 символов
        MAX_LENGTH = 4000
        if len(message_text) > MAX_LENGTH:
            parts = [message_text[i:i+MAX_LENGTH] for i in range(0, len(message_text), MAX_LENGTH)]
            for part in parts:
                await update.message.reply_text(part, parse_mode="Markdown")
        else:
            await update.message.reply_text(message_text, parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Ошибка list_promo_codes: {e}")
        await update.message.reply_text("❌ Ошибка при получении списка промокодов")

async def open_casino_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Открывает казино при нажатии на кнопку в главном меню."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        # Проверяем сброс попыток
        check_casino_reset(user_data)
        save_data(data)
        
        attempts = user_data.get("casino_attempts", 5) if user_data else 5
        cents = user_data.get("cents", 0) if user_data else 0
        
        # ⭐ НОВОЕ: Отображение баланса с индикаторами ⭐
        if cents >= 1500:
            balance_text = f"💰 Ваш баланс: **{cents}** бэт-коинов ✅"
        else:
            balance_text = f"💰 Ваш баланс: **{cents}** бэт-коинов ❌ _(недостаточно)_"
        
        keyboard = [[InlineKeyboardButton("🎰 Сыграть)", callback_data="casino_play")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        max_casino_attempts = 7 if is_batpass_active(user_data) else 5
        
        await update.message.reply_text(
            f"🎰 **Казино**\n"
            f"📜 **Правила:**\n"
            f"• Стоимость игры: 1500 бэт-коинов\n"
            f"• Крутите слот и получите 3 одинаковых значения\n"
            f"• При победе: 10 бесплатных попыток\n"
            f"• Лимит: {max_casino_attempts} игр в день (сброс в 00:00 МСК)\n"
            f"{balance_text}\n",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в open_casino_from_button: {e}")
        await update.message.reply_text("❌ Ошибка при открытии казино")
async def craft_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню выбора рецепта крафта."""
    try:
        query = update.callback_query if hasattr(update, 'callback_query') else None
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            text = "❌ У вас нет карт для крафта!"
            if query:
                await query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return
        
        # Создаём inline-клавиатуру с рецептами
        keyboard = []
        for rule_key, rule in CRAFT_RULES.items():
            keyboard.append([
                InlineKeyboardButton(
                    rule["button_text"],
                    callback_data=f"craft_recipe_{rule_key}"
                )
            ])
        
        caption = (
            "🔨 **Мастерская крафта**\n\n"
            "Выберите рецепт для улучшения карт:\n"
            "• Соберите нужное количество дубликатов указанной редкости\n"
            "• Получите 1 карту более высокой редкости + награды!"
        )
        
        if query:
            try:
                await query.edit_message_text(
                    caption,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            except:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
        else:
            await update.message.reply_text(
                caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Ошибка в craft_menu: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Ошибка", show_alert=True)
        else:
            await update.message.reply_text("❌ Ошибка при открытии мастерской")

async def craft_select_card(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    rule_key: str,
    page: int = 0
) -> None:
    """Показывает доступные карты выбранной редкости для крафта."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            await query.edit_message_text("❌ У вас нет карт!")
            return
        
        rule = CRAFT_RULES.get(rule_key)
        if not rule:
            await query.edit_message_text("❌ Неверный рецепт крафта!")
            return
        
        from_rarity = rule["from_rarity"]
        count_needed = rule["count_needed"]
        
        # Считаем карты пользователя по редкости
        user_card_ids = user_data["cards"]
        card_counts = Counter(user_card_ids)
        
        # Фильтруем карты нужной редкости, которых достаточно для крафта
        craftable_cards = []
        for card_id, count in card_counts.items():
            card = find_card_by_id(card_id, data["cards"])
            if card and card.get("rarity") == from_rarity and count >= count_needed:
                craftable_cards.append((card_id, count, card))
        
        if not craftable_cards:
            await query.edit_message_text(
                f"❌ У вас недостаточно карт редкости **{from_rarity}** для крафта!\n\n"
                f"📋 Нужно: {count_needed} одинаковых карт\n"
                f"💡 Продолжайте собирать карты и попробуйте снова!",
                parse_mode="Markdown"
            )
            return
        
        # Сортируем карты по названию для удобства
        craftable_cards.sort(key=lambda x: x[2]["title"])
        total_cards = len(craftable_cards)
        
        # Пагинация
        if page < 0:
            page = 0
        elif page >= total_cards:
            page = total_cards - 1
        
        # Сохраняем состояние в context
        if user_id not in context.user_data:
            context.user_data[user_id] = {}
        context.user_data[user_id]["craft_rule"] = rule_key
        context.user_data[user_id]["craft_page"] = page
        
        # Получаем карту для текущей страницы
        card_id, count, card = craftable_cards[page]
        
        # Создаём клавиатуру
        keyboard = []
        
        # Кнопка крафта
        keyboard.append([
            InlineKeyboardButton(
                f"🔨 Скрафтить ({count_needed} шт.)",
                callback_data=f"craft_execute_{rule_key}|{card_id}"
            )
        ])

        # Кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"craft_page_{rule_key}|{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_cards}", callback_data="craft_info"))
        if page < total_cards - 1:
            nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"craft_page_{rule_key}|{page + 1}"))
        
        # ⭐ ИСПРАВЛЕНИЕ: ДОБАВЛЯЕМ КНОПКИ НАВИГАЦИИ В КЛАВИАТУРУ ⭐
        if nav_buttons:
            keyboard.append(nav_buttons)

        # Кнопки возврата
        keyboard.append([
            InlineKeyboardButton("🔙 Назад", callback_data="craft_back")
        ])
        
        caption = (
            f"🔨 **Выберите карту для крафта**\n\n"
            f"📦 Рецепт: {rule['button_text']}\n"
            f"🃏 Карта: **{card['title']}**\n"
            f"🌟 Редкость: {card['rarity']}\n"
            f"📊 У вас: {count} шт. (нужно {count_needed})\n\n"
            f"⚠️ {count_needed} карт **{card['title']}** будут удалены!"
        )
        
        await query.edit_message_text(
            caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в craft_select_card: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)
        
async def craft_execute(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    rule_key: str,
    card_id: int
) -> None:
    """Выполняет крафт карты."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data:
            await query.edit_message_text("❌ Вы ещё не начали игру!")
            return
        
        rule = CRAFT_RULES.get(rule_key)
        if not rule:
            await query.edit_message_text("❌ Неверный рецепт!")
            return
        
        from_rarity = rule["from_rarity"]
        to_rarity = rule["to_rarity"]
        count_needed = rule["count_needed"]
        
        # Проверяем, есть ли у игрока нужное количество карт
        user_card_ids = user_data.get("cards", [])
        card_counts = Counter(user_card_ids)
        
        if card_counts.get(card_id, 0) < count_needed:
            await query.edit_message_text(
                f"❌ Недостаточно карт!\n"
                f"Нужно: {count_needed}, у вас: {card_counts.get(card_id, 0)}"
            )
            return
        
        # Находим карту-источник
        source_card = find_card_by_id(card_id, data["cards"])
        if not source_card:
            await query.edit_message_text("❌ Карта не найдена!")
            return
        
        # Находим доступные карты целевой редкости
        available_upgrade_cards = [
            c for c in data["cards"]
            if c.get("rarity") == to_rarity and c.get("available", True)
        ]
        
        if not available_upgrade_cards:
            await query.edit_message_text(
                f"❌ В системе нет доступных карт редкости **{to_rarity}** для выдачи!",
                parse_mode="Markdown"
            )
            return
        
        # === ВЫПОЛНЯЕМ КРАФТ ===
        
        # Удаляем нужное количество карт из коллекции
        removed = 0
        new_cards_list = []
        for cid in user_card_ids:
            if cid == card_id and removed < count_needed:
                removed += 1
            else:
                new_cards_list.append(cid)
        user_data["cards"] = new_cards_list
        
        # Выбираем случайную карту целевой редкости
        new_card = random.choice(available_upgrade_cards)
        user_data["cards"].append(new_card["id"])
        
        # Начисляем награды за получение новой карты
        bonus = RARITY_BONUSES.get(new_card["rarity"], {"cents": 0, "points": 0})
        user_data["total_points"] += bonus["points"]
        user_data["season_points"] += bonus["points"]
        user_data["cents"] += bonus["cents"]
        
        save_data(data)
        
        # === ОТПРАВЛЯЕМ РЕЗУЛЬТАТ ===
        result_text = (
            f"✅ **Крафт успешен!** 🔨\n\n"
            f"🗑️ Использовано: {count_needed}x {source_card['title']} ({from_rarity})\n"
            f"🎁 Получено: **{new_card['title']}**\n"
            f"🌟 Редкость: {new_card['rarity']}\n\n"
            f"💰 +{bonus['cents']} бэт-коинов\n"
            f"💥 +{bonus['points']} очков репутации"
        )

        # Еженедельный квест: сделать 3 крафта
        await update_weekly_quest_progress(context, user_id, "weekly_craft_3", 1)
        
        # ⭐ 1. Сначала редактируем текущее сообщение с результатом ⭐
        await query.edit_message_text(result_text, parse_mode="Markdown")
        
        # ⭐ 2. Отправляем полученную карту ОТДЕЛЬНЫМ сообщением ⭐
        caption = generate_card_caption(new_card, user_data, count=1, show_bonus=False)
        await send_card(update, new_card, context, caption=caption)
        
        # ⭐ 3. Отправляем НОВОЕ сообщение с меню выбора карт (не редактируем!) ⭐
        await _send_craft_select_menu(context, query.message.chat_id, user_id, rule_key, page=0)
        
        logger.info(f"Игрок {user_id} выполнил крафт: {rule_key}, карта #{card_id} → #{new_card['id']}")
        
    except Exception as e:
        logger.error(f"Ошибка в craft_execute: {e}")
        await query.answer("❌ Произошла ошибка при крафте", show_alert=True)


async def _send_craft_select_menu(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: str,
    rule_key: str,
    page: int = 0
) -> None:
    """Вспомогательная функция для отправки меню выбора карт как НОВОГО сообщения."""
    try:
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ У вас нет карт для крафта!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад к рецептам", callback_data="craft_menu")
                ]])
            )
            return
        
        rule = CRAFT_RULES.get(rule_key)
        if not rule:
            return
        
        from_rarity = rule["from_rarity"]
        count_needed = rule["count_needed"]
        
        # Считаем карты пользователя по редкости
        user_card_ids = user_data["cards"]
        card_counts = Counter(user_card_ids)
        
        # Фильтруем карты нужной редкости, которых достаточно для крафта
        craftable_cards = []
        for card_id, count in card_counts.items():
            card = find_card_by_id(card_id, data["cards"])
            if card and card.get("rarity") == from_rarity and count >= count_needed:
                craftable_cards.append((card_id, count, card))
        
        if not craftable_cards:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"❌ У вас недостаточно карт редкости **{from_rarity}** для крафта!\n\n"
                    f"📋 Нужно: {count_needed} одинаковых карт\n"
                    f"💡 Продолжайте собирать карты и попробуйте снова!"
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📋 Другие рецепты", callback_data="craft_menu"),
                    InlineKeyboardButton("🔙 Назад", callback_data="craft_back")
                ]]),
                parse_mode="Markdown"
            )
            return
        
        # Сортируем карты по названию
        craftable_cards.sort(key=lambda x: x[2]["title"])
        total_cards = len(craftable_cards)
        
        # Пагинация
        if page < 0:
            page = 0
        elif page >= total_cards:
            page = total_cards - 1
        
        # Сохраняем состояние в context
        if user_id not in context.user_data:
            context.user_data[user_id] = {}
        context.user_data[user_id]["craft_rule"] = rule_key
        context.user_data[user_id]["craft_page"] = page
        
        # Получаем карту для текущей страницы
        card_id, count, card = craftable_cards[page]
        
        # Создаём клавиатуру
        keyboard = []
        
        # Кнопка крафта
        keyboard.append([
            InlineKeyboardButton(
                f"🔨 Скрафтить ({count_needed} шт.)",
                callback_data=f"craft_execute_{rule_key}|{card_id}"
            )
        ])

        # Кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"craft_page_{rule_key}|{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_cards}", callback_data="craft_info"))
        if page < total_cards - 1:
            nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"craft_page_{rule_key}|{page + 1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)

        # Кнопки возврата
        keyboard.append([
            InlineKeyboardButton("📋 Другие рецепты", callback_data="craft_menu"),
            InlineKeyboardButton("🔙 Назад", callback_data="craft_back")
        ])
        
        caption = (
            f"🔨 **Выберите карту для крафта**\n\n"
            f"📦 Рецепт: {rule['button_text']}\n"
            f"🃏 Карта: **{card['title']}**\n"
            f"🌟 Редкость: {card['rarity']}\n"
            f"📊 У вас: {count} шт. (нужно {count_needed})\n\n"
            f"🎁 После крафта вы получите:\n"
            f"• 1 случайную карту редкости **{rule['to_rarity']}**\n"
            f"• Награду за получение новой карты 💰💥\n\n"
            f"⚠️ {count_needed} карт **{card['title']}** будут удалены!"
        )
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в _send_craft_select_menu: {e}")

async def craft_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок крафта."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        
        # Меню рецептов крафта
        if query.data == "craft_menu":
            await craft_menu(update, context)
            return
        
        # Выбор рецепта
        if query.data.startswith("craft_recipe_"):
            rule_key = query.data.replace("craft_recipe_", "")
            await craft_select_card(update, context, rule_key, page=0)
            return
        
        # Пагинация
        if query.data.startswith("craft_page_"):
            # Парсим по |
            suffix = query.data.replace("craft_page_", "")
            try:
                rule_key, page_str = suffix.split("|")
                page = int(page_str)
                await craft_select_card(update, context, rule_key, page=page)
            except (ValueError, IndexError):
                await query.answer("❌ Ошибка навигации!", show_alert=True)
                logger.error(f"Неверный формат craft_page: {query.data}")
            return
        
        # Информация
        if query.data == "craft_info":
            await query.answer("📄 Используйте ◀️ и ▶️ для навигации", show_alert=False)
            return
        
        # Выполнение крафта
        if query.data.startswith("craft_execute_"):
            # Парсим по |, так как rule_key может содержать _
            suffix = query.data.replace("craft_execute_", "")
            try:
                rule_key, card_id_str = suffix.split("|")
                card_id = int(card_id_str)
                await craft_execute(update, context, rule_key, card_id)
            except (ValueError, IndexError):
                await query.answer("❌ Ошибка данных крафта!", show_alert=True)
                logger.error(f"Неверный формат craft_execute: {query.data}")
            return
        
        # Назад в главное меню
        if query.data == "craft_back":
            await craft_menu(update, context)  # Просто вызываем существующую функцию
            return
        
    except Exception as e:
        logger.error(f"Ошибка в craft_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

def get_user_clan(user_id: str, data: Dict) -> Optional[str]:
    """Возвращает название клана пользователя или None."""
    return data.get("user_clan", {}).get(user_id)

def get_clan_data(clan_identifier: str, data: Dict) -> Optional[Dict]:
    """Возвращает данные клана по ID или по названию."""
    clans = data.get("clans", {})
    
    # Сначала ищем по ключу (clan_id) — быстрый путь
    if clan_identifier in clans:
        return clans[clan_identifier]
    
    # Если не нашли, ищем по названию — для совместимости
    for clan in clans.values():
        if clan.get("name") == clan_identifier:
            return clan
    return None

def is_clan_leader(user_id: str, clan_id: str, data: Dict) -> bool:
    """Проверяет, является ли пользователь главой клана."""
    clan = get_clan_data(clan_id, data)
    return clan and clan.get("leader_id") == user_id

def can_create_clan(user_id: str, data: Dict) -> tuple[bool, str]:
    """Проверяет, может ли пользователь создать клан."""
    # Проверка: уже в клане
    if get_user_clan(user_id, data):
        return False, "Вы уже состоите в клане!"
    
    # Проверка: достаточно ли средств
    user_data = data["users"].get(user_id, {})
    if user_data.get("cents", 0) < CLAN_CREATION_COST:
        return False, f"Недостаточно бэт-коинов! Нужно {CLAN_CREATION_COST}"
    
    return True, ""

async def create_clan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /create_clan."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        
        # Проверка: уже в клане
        if get_user_clan(user_id, data):
            await update.message.reply_text("❌ Вы уже состоите в клане!")
            return
        
        if not context.args:
            await update.message.reply_text("ℹ️ Используйте: /create_clan [Название_клана]")
            return
            
        clan_name = " ".join(context.args)
        
        # Вызываем внутреннюю логику
        success, message = _create_clan_logic(clan_name, user_id, data)
        save_data(data)
        
        if success:
            await update.message.reply_text(
                f"✅ {message}\n"
                f"👥 Участники: 1/{MAX_CLAN_MEMBERS}\n"
                f"Чтобы пригласить игрока: /invite_clan @username",
                parse_mode="Markdown"
            )
            logger.info(f"Пользователь {user_id} создал клан {clan_name}")
        else:
            await update.message.reply_text(f"❌ {message}")
            
    except Exception as e:
        logger.error(f"Ошибка create_clan: {e}")
        await update.message.reply_text("❌ Ошибка при создании клана")
        
def leave_clan(user_id: str, data: Dict) -> tuple[bool, str]:
    """Выход из клана или роспуск клана (если лидер и последний участник)."""
    clan_identifier = get_user_clan(user_id, data)  # ← Может быть clan_id или clan_name
    if not clan_identifier:
        return False, "Вы не состоите в клане!"
    
    clan = get_clan_data(clan_identifier, data)
    if not clan:
        return False, "Ошибка: клан не найден!"
    
    is_leader = user_id == clan["leader_id"]
    clan_name = clan["name"]
    
    if is_leader and len(clan["members"]) > 1:
        return False, (
            "Вы не можете покинуть клан, пока в нём есть другие участники!\n"
            "Передайте лидерство или расформируйте клан."
        )
    
    # Удаляем пользователя из клана
    if user_id in clan["members"]:
        del clan["members"][user_id]
    
    # ⭐ ИСПРАВЛЕНИЕ: Если клан пуст — удаляем его по РЕАЛЬНОМУ ключу ⭐
    if not clan["members"]:
        # Ищем ключ, по которому этот клан хранится в словаре
        for cid, c in list(data["clans"].items()):
            if c is clan:
                del data["clans"][cid]
                break
    
    # Удаляем привязку пользователя
    if user_id in data["user_clan"]:
        del data["user_clan"][user_id]
    
    if is_leader:
        return True, f"Клан **{clan_name}** распущен."
    else:
        return True, f"Вы покинули клан **{clan_name}**."
        
def get_clan_members_list(clan_id: str, data: Dict) -> str:
    """Формирует текст со списком участников клана и их очками репутации (HTML)."""
    clan = get_clan_data(clan_id, data)
    if not clan:
        return "❌ Клан не найден!"
    
    members_text = f"👥 Участники клана <b>{html.escape(clan['name'])}</b>:\n"
    for member_id, member_info in clan["members"].items():
        user_data = data["users"].get(member_id, {})
        username = user_data.get("first_name", "Неизвестно")
        if user_data.get("last_name"):
            username += f" {user_data['last_name']}"
        
        # ⭐ Экранируем имя участника ⭐
        username_escaped = html.escape(username)
        
        reputation = user_data.get("season_points", 0)
        role_emoji = "👑" if member_info.get("role") == "leader" else "•"
        members_text += f"{role_emoji} {username_escaped} — {reputation} очков репутации\n"
    return members_text

async def invite_player_to_clan(
    inviter_id: str,
    target_username: str,
    data: Dict,
    context: ContextTypes.DEFAULT_TYPE
) -> tuple[bool, str]:
    """Приглашает игрока в клан по @никнейму. Возвращает (success, message)."""
    # Находим клан приглашающего
    inviter_clan_name = get_user_clan(inviter_id, data)
    if not inviter_clan_name:
        return False, "Вы не состоите в клане!"
    
    clan = get_clan_data(inviter_clan_name, data)
    if not clan:
        return False, "Ошибка: клан не найден!"
    
    # Проверяем, что приглашающий — лидер клана
    if clan.get("leader_id") != inviter_id:
        return False, "Только глава клана может приглашать участников!"
    
    # Проверяем лимит участников
    if len(clan["members"]) >= MAX_CLAN_MEMBERS:
        return False, f"Клан заполнен! Максимум {MAX_CLAN_MEMBERS} участников."
    
    # Ищем целевого пользователя по никнейму
    target_user_id = None
    for uid, udata in data.get("users", {}).items():
        # Сравниваем никнеймы без @ и в нижнем регистре
        user_username = udata.get("username", "")
        if user_username and user_username.lower() == target_username.lower():
            target_user_id = uid
            break
    
    if not target_user_id:
        return False, f"Пользователь @{target_username} не найден!"
    
    # Нельзя пригласить самого себя
    if target_user_id == inviter_id:
        return False, "Вы не можете пригласить самого себя!"
    
    # Проверяем, не состоит ли пользователь уже в клане
    if get_user_clan(target_user_id, data):
        return False, "Этот игрок уже состоит в клане!"
    
    # Проверяем, не приглашён ли уже пользователь
    target_user_data = data["users"].get(target_user_id, {})
    if target_user_data.get("clan_invite_pending"):
        return False, "У этого игрока уже есть ожидающее приглашение!"
    
    # Создаём приглашение
    target_user_data["clan_invite_pending"] = {
        "clan_name": inviter_clan_name,
        "inviter_id": inviter_id,
        "invited_at": int(time.time())
    }
    data["users"][target_user_id] = target_user_data
    
    # Уведомляем целевого пользователя
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                f"🏰 Вас пригласили в клан **{inviter_clan_name}**!\n"
                f"Для принятия приглашения используйте команду:\n"
                f"`/accept_clan_invite`"
                f"⏳ *Приглашение действительно в течение 1 часа.*"
            ),
            parse_mode="Markdown"
        )
    except Exception as notify_error:
        logger.warning(f"Не удалось отправить уведомление о приглашении: {notify_error}")
    
    return True, f"Приглашение отправлено пользователю @{target_username}!"
        
async def join_clan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Присоединение к клану по ID."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        
        if not context.args:
            await update.message.reply_text("ℹ️ Используйте: /join_clan [ID_клана]")
            return
            
        clan_id = context.args[0]
        
        # Проверяем существование клана
        if clan_id not in data.get("clans", {}):
            await update.message.reply_text("❌ Клан не найден!")
            return
            
        clan = data["clans"][clan_id]
        
        # Проверяем, не состоит ли пользователь уже в клане
        for c in data.get("clans", {}).values():
            if user_id in c.get("members", []):
                await update.message.reply_text("❌ Вы уже состоите в клане!")
                return
                
        # ⭐ ПРОВЕРКА ЛИМИТА УЧАСТНИКОВ ⭐
        can_join, reason = can_join_clan(clan_id, data)
        if not can_join:
            await update.message.reply_text(
                f"{reason}"
                f"👥 Сейчас в клане: {len(clan['members'])}/{MAX_CLAN_MEMBERS}"
            )
            return
        
        # Добавляем участника
        clan["members"][user_id] = {"joined_at": int(time.time()), "role": "member"}
        save_data(data)
        
        await update.message.reply_text(
            f"✅ Вы присоединились к клану **«{clan['name']}»**!"
            f"👥 Участники: {len(clan['members'])}/{MAX_CLAN_MEMBERS}",
            parse_mode="Markdown"
        )
        logger.info(f"Пользователь {user_id} присоединился к клану {clan_id}")
        
    except Exception as e:
        logger.error(f"Ошибка join_clan: {e}")
        await update.message.reply_text("❌ Ошибка при вступлении в клан")

# ===== МЕНЮ КЛАНОВ =====
async def clan_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает главное меню кланов."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        
        clan_name = get_user_clan(user_id, data)
        
        # Кнопки меню
        keyboard = [
            [KeyboardButton("➕ Создать клан")],
            [KeyboardButton("📋 Мой клан" if clan_name else "🔒 Мой клан (не в клане)")],
            [KeyboardButton("🏆 Топ кланов")],
            [KeyboardButton("🔙 Назад")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        caption = (
            "🏰 **Кланы**\n\n"
            "Объединяйтесь с другими игроками!\n\n"
            "• Создайте свой клан за 30 000 бэт-коинов\n"
            "• Приглашайте друзей и развивайте клан вместе\n"
            "• Следите за прогрессом участников"
        )
        
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            try:
                await query.message.delete()
            except:
                pass
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text = caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Ошибка в clan_menu: {e}")
        await update.message.reply_text("❌ Ошибка при открытии меню кланов")


async def create_clan_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начинает процесс создания клана."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        
        # Проверки
        can_create, error_msg = can_create_clan(user_id, data)
        if not can_create:
            keyboard = [[KeyboardButton("🔙 Назад в кланы")]]
            await update.message.reply_text(
                f"❌ {error_msg}",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return
        
        # Запрашиваем подтверждение
        context.user_data[user_id] = {"step": "clan_create_confirm"}
        
        keyboard = [
            [KeyboardButton("✅ Да, создать за 30000")],
            [KeyboardButton("❌ Отмена")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        user_data = data["users"].get(user_id, {})
        creation_cost = 0 if is_batpass_active(user_data) else CLAN_CREATION_COST

        cost_text = "**Бесплатно** (Бэт-пасс)" if creation_cost == 0 else f"**{creation_cost:,}** бэт-коинов"
        
        await update.message.reply_text(
            f"🏰 **Создание клана**\n\n"
            f"Стоимость: **{cost_text}**\n\n"
            f"После подтверждения вам нужно будет ввести название клана.\n"
            f"Название должно быть уникальным!\n\n"
            f"Подтверждаете создание?",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в create_clan_flow: {e}")
        await update.message.reply_text("❌ Ошибка")


async def confirm_clan_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает подтверждение создания клана."""
    try:
        user_id = str(update.effective_user.id)
        text = update.message.text.strip()
        
        if text == "✅ Да, создать за 30000":
            # Переход к вводу названия
            context.user_data[user_id]["step"] = "clan_enter_name"
            keyboard = [[KeyboardButton("❌ Отмена создания")]]
            await update.message.reply_text(
                "✏️ Введите название вашего клана:\n\n"
                "• Только латиница или кириллица\n"
                "• 3-20 символов\n"
                "• Без специальных символов",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
        elif text == "❌ Отмена":
            if user_id in context.user_data:
                del context.user_data[user_id]
            keyboard = [[KeyboardButton("🔙 Назад в кланы")]]
            await update.message.reply_text(
                "❌ Создание клана отменено.",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            
    except Exception as e:
        logger.error(f"Ошибка в confirm_clan_creation: {e}")


async def process_clan_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ввод названия клана."""
    try:
        user_id = str(update.effective_user.id)
        clan_name = update.message.text.strip()
        data = load_data()
        
        # Проверка отмены
        if clan_name == "❌ Отмена создания":
            if user_id in context.user_data:
                del context.user_data[user_id]
            keyboard = [[KeyboardButton("🔙 Назад в кланы")]]
            await update.message.reply_text(
                "❌ Создание клана отменено.",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return
        
        # Валидация названия
        if len(clan_name) < 3 or len(clan_name) > 20:
            await update.message.reply_text("❌ Название должно содержать от 3 до 20 символов!\nПовторите ввод:")
            return
        
        if not clan_name.replace(" ", "").isalnum():
            await update.message.reply_text("❌ Название может содержать только буквы и цифры!\nПовторите ввод:")
            return
        
        # ✅ ИСПРАВЛЕННЫЙ ВЫЗОВ:
        success, message = _create_clan_logic(clan_name, user_id, data)
        save_data(data)
        
        if user_id in context.user_data:
            del context.user_data[user_id]
        
        keyboard = [[KeyboardButton("🔙 Назад в кланы")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        if success:
            await update.message.reply_text(
                f"✅ {message}",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(f"❌ {message}", reply_markup=reply_markup)
            
    except Exception as e:
        logger.error(f"Ошибка в process_clan_name: {e}")
        await update.message.reply_text("❌ Ошибка при создании клана")

async def my_clan_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает информацию о клане пользователя."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        clan_id = get_user_clan(user_id, data)
        if not clan_id:
            keyboard = [
                [KeyboardButton("➕ Создать клан")],
                [KeyboardButton("🔙 Назад в кланы")]
            ]
            await update.message.reply_text(
                "❌ Вы не состоите в клане!\n"
                "Создайте свой клан или попросите главу другого клана пригласить вас.",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return
        
        clan = get_clan_data(clan_id, data)
        if not clan:
            await update.message.reply_text("❌ Ошибка: данные клана повреждены!")
            return
        
        is_leader = user_id == clan["leader_id"]
        
        # Формируем сообщение
        members_list = get_clan_members_list(clan["name"], data)
        
        # Описание клана
        description_text = ""
        clan_description = clan.get("description", "")
        if clan_description:
            escaped_desc = html.escape(clan_description)
            description_text = (
                f"\n📝 <b>Описание клана:</b>\n"
                f"<blockquote><i>{escaped_desc}</i></blockquote>\n"
            )
        
        clan_name_escaped = html.escape(clan['name'])
        message_text = (
            f"🏰 <b>Ваш клан: {clan_name_escaped}</b>\n"
            f"{description_text}"
            f"{members_list}\n"
            f"📊 Всего участников: {len(clan['members'])}\n"
            f"📅 Создан: {datetime.datetime.fromtimestamp(clan['created_at']).strftime('%d.%m.%Y')}"
        )
        
        # Кнопки для лидера
        if is_leader:
            keyboard = [
                [KeyboardButton("📨 Пригласить игрока")],
                [KeyboardButton("✏️ Описание клана")],
                [KeyboardButton("🖼 Установить аватарку клана")],  # ⭐ НОВОЕ
                [KeyboardButton("🚪 Покинуть клан")],
                [KeyboardButton("🔙 Назад в кланы")]
            ]
        else:
            keyboard = [
                [KeyboardButton("🚪 Покинуть клан")],
                [KeyboardButton("🔙 Назад в кланы")]
            ]
        
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # ⭐ ОТПРАВКА С АВАТАРКОЙ КЛАНА ⭐
        clan_avatar = clan.get("clan_avatar")
        
        if clan_avatar:
            # Если есть аватарка клана, отправляем фото
            await update.message.reply_photo(
                photo=clan_avatar,
                caption=message_text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        else:
            # Если аватарки нет, отправляем текст
            await update.message.reply_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Ошибка в my_clan_view: {e}")
        await update.message.reply_text("❌ Ошибка при показе информации о клане")

async def set_clan_avatar_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начинает процесс установки аватарки клана."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        clan_id = get_user_clan(user_id, data)
        
        if not clan_id:
            await update.message.reply_text("❌ Вы не состоите в клане!")
            return
        
        clan = get_clan_data(clan_id, data)
        if not clan:
            await update.message.reply_text("❌ Ошибка: клан не найден!")
            return
        
        if clan.get("leader_id") != user_id:
            await update.message.reply_text("❌ Только глава клана может изменять аватарку!")
            return
        
        # Переходим в состояние ожидания фото
        context.user_data[user_id] = {"step": "clan_set_avatar"}
        
        # Убираем клавиатуру клана
        await update.message.reply_text(
            "🖼 <b>Установка аватарки клана</b>\n\n"
            "Отправьте фото, которое станет аватаркой клана.\n"
            "Все участники клана будут видеть эту аватарку в разделе «Мой Клан».\n\n"
            "Отправьте фото или нажмите ❌ Отмена",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("❌ Отмена")]],
                resize_keyboard=True
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка в set_clan_avatar_start: {e}")
        await update.message.reply_text("❌ Ошибка")

async def process_clan_avatar_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает фото для установки аватарки клана."""
    try:
        user_id = str(update.effective_user.id)
        
        # Проверяем, что пользователь в состоянии ожидания фото
        if user_id not in context.user_data or context.user_data[user_id].get("step") != "clan_set_avatar":
            return
        
        # Проверяем, что отправлено фото
        if not update.message.photo:
            await update.message.reply_text(
                "❌ Пожалуйста, отправьте фото!\n"
                "Или нажмите ❌ Отмена"
            )
            return
        
        data = load_data()
        clan_id = get_user_clan(user_id, data)
        
        if not clan_id:
            if user_id in context.user_data:
                del context.user_data[user_id]
            await update.message.reply_text("❌ Вы не состоите в клане!")
            return
        
        clan = get_clan_data(clan_id, data)
        if not clan or clan.get("leader_id") != user_id:
            if user_id in context.user_data:
                del context.user_data[user_id]
            await update.message.reply_text("❌ Только глава клана может изменять аватарку!")
            return
        
        # Получаем file_id самого большого фото
        photo = update.message.photo[-1]  # Последнее фото - самое большое
        file_id = photo.file_id
        
        # Сохраняем аватарку клана
        clan["clan_avatar"] = file_id
        save_data(data)
        
        # Очищаем состояние
        if user_id in context.user_data:
            del context.user_data[user_id]
        
        # Убираем клавиатуру и возвращаем меню клана
        await update.message.reply_text(
            "✅ Аватарка клана установлена!\n"
            "Все участники клана теперь видят новую аватарку.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        # Возвращаем меню клана
        await my_clan_view(update, context)
        
    except Exception as e:
        logger.error(f"Ошибка в process_clan_avatar_photo: {e}")
        await update.message.reply_text("❌ Ошибка при установке аватарки")

async def leave_clan_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запрашивает подтверждение выхода из клана."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        
        clan_name = get_user_clan(user_id, data)
        if not clan_name:
            await update.message.reply_text("❌ Вы не состоите в клане!")
            return
        
        is_leader = is_clan_leader(user_id, clan_name, data)
        warning = (
            "⚠️ **ВНИМАНИЕ:** Как глава клана, вы не можете покинуть его, "
            "пока в клане есть другие участники!\n\n"
            if is_leader and len(get_clan_data(clan_name, data)["members"]) > 1
            else ""
        )
        
        keyboard = [
            [KeyboardButton("✅ Да, покинуть клан")],
            [KeyboardButton("❌ Отмена")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            f"{warning}Вы уверены, что хотите покинуть клан **{clan_name}**?",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в leave_clan_confirm: {e}")


async def process_leave_clan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает выход из клана."""
    try:
        user_id = str(update.effective_user.id)
        text = update.message.text.strip()
        data = load_data()
        
        if text == "✅ Да, покинуть клан":
            success, message = leave_clan(user_id, data)
            save_data(data)
            
            keyboard = [[KeyboardButton("🔙 Назад в кланы")]]
            await update.message.reply_text(
                f"{'✅' if success else '❌'} {message}",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                parse_mode="Markdown"
            )
        elif text == "❌ Отмена":
            keyboard = [[KeyboardButton("🔙 Назад в кланы")]]
            await update.message.reply_text(
                "❌ Выход из клана отменён.",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            
    except Exception as e:
        logger.error(f"Ошибка в process_leave_clan: {e}")


async def invite_clan_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запрашивает @никнейм для приглашения в клан."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        
        clan_name = get_user_clan(user_id, data)
        if not clan_name:
            await update.message.reply_text("❌ Вы не состоите в клане!")
            return
        
        if not is_clan_leader(user_id, clan_name, data):
            await update.message.reply_text("❌ Только глава клана может приглашать участников!")
            return
        
        context.user_data[user_id] = {"step": "clan_invite_enter_username"}
        
        keyboard = [[KeyboardButton("❌ Отмена")]]
        await update.message.reply_text(
            "✏️ Введите @никнейм игрока для приглашения:\n\n"
            "Пример: `@username`",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в invite_clan_member: {e}")


async def process_clan_invite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ввод @никнейма для приглашения."""
    try:
        user_id = str(update.effective_user.id)
        text = update.message.text.strip()
        data = load_data()
        
        if text == "❌ Отмена":
            if user_id in context.user_data:
                del context.user_data[user_id]
            keyboard = [[KeyboardButton("🔙 Назад в кланы")]]
            await update.message.reply_text(
                "❌ Приглашение отменено.",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return
        
        if not text.startswith("@"):
            await update.message.reply_text(
                "❌ Никнейм должен начинаться с @!\n"
                "Повторите ввод:"
            )
            return
        
        target_username = text[1:].strip()
        success, message = await invite_player_to_clan(user_id, target_username, data, context)
        save_data(data)
        
        if user_id in context.user_data:
            del context.user_data[user_id]
        
        keyboard = [[KeyboardButton("🔙 Назад в кланы")]]
        await update.message.reply_text(
            f"{'✅' if success else '❌'} {message}",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        
    except Exception as e:
        logger.error(f"Ошибка в process_clan_invite: {e}")


# ===== КОМАНДА ДЛЯ ПРИНЯТИЯ ПРИГЛАШЕНИЯ =====
async def accept_clan_invite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /accept_clan_invite."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id, {})
        invite = user_data.get("clan_invite_pending")
        if not invite:
            await update.message.reply_text("❌ У вас нет ожидающих приглашений в клан!")
            return

        # ⭐ ПРОВЕРКА СРОКА ДЕЙСТВИЯ ПРИГЛАШЕНИЯ (1 ЧАС) ⭐
        invited_at = invite.get("invited_at", 0)
        current_time = int(time.time())
        if current_time - invited_at > 3600:  # 3600 секунд = 1 час
            user_data["clan_invite_pending"] = None
            save_data(data)
            await update.message.reply_text(
                "❌ Срок действия приглашения в клан истёк (прошло больше 1 часа).\n"
                "Попросите главу клана отправить новое приглашение."
            )
            return
        # ⭐ КОНЕЦ ПРОВЕРКИ ⭐

        clan_name = invite["clan_name"]
        inviter_id = invite["inviter_id"]

        # Проверки
        if get_user_clan(user_id, data):
            await update.message.reply_text("❌ Вы уже состоите в клане!")
            return

        clan = get_clan_data(clan_name, data)
        if not clan:
            await update.message.reply_text("❌ Клан больше не существует!")
            return

        # Добавляем пользователя в клан
        clan["members"][user_id] = {"joined_at": int(time.time()), "role": "member"}
        data["user_clan"][user_id] = clan_name
        user_data["clan_invite_pending"] = None
        save_data(data)

        # Уведомляем лидера
        try:
            await context.bot.send_message(
                chat_id=inviter_id,
                text=f"✅ Игрок {user_data.get('first_name', 'Новый участник')} принял приглашение в клан **{clan_name}**!",
                parse_mode="Markdown"
            )
        except:
            pass

        await update.message.reply_text(
            f"🎉 Вы успешно вступили в клан **{clan_name}**!\n"
            f"Используйте кнопку «📋 Мой клан» для просмотра участников.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в accept_clan_invite: {e}")
        await update.message.reply_text("❌ Ошибка при принятии приглашения")

def get_clan_member_count(clan_id: str, data: Dict) -> int:
    """Возвращает текущее количество участников в клане."""
    clan = data.get("clans", {}).get(clan_id)
    if not clan:
        return 0
    return len(clan.get("members", []))

def can_join_clan(clan_id: str, data: Dict) -> tuple[bool, str]:
    """
    Проверяет, можно ли присоединиться к клану.
    Возвращает: (можно_ли_войти, сообщение_о_причине)
    """
    clan = data.get("clans", {}).get(clan_id)
    if not clan:
        return False, "❌ Клан не найден!"
    
    member_count = len(clan.get("members", []))
    if member_count >= MAX_CLAN_MEMBERS:
        return False, f"❌ Клан заполнен! Максимум {MAX_CLAN_MEMBERS} участников."
    
    return True, ""

def _create_clan_logic(clan_name: str, user_id: str, data: Dict) -> tuple[bool, str]:
    """Внутренняя логика создания клана. Возвращает (success, message)."""
    # Проверка: имя уже занято
    for clan in data.get("clans", {}).values():
        if clan["name"].lower() == clan_name.lower():
            return False, f"Клан с названием «{clan_name}» уже существует!"

    # Проверка и списание бэт-коинов
    if user_id not in data.get("users", {}):
        return False, "Ошибка: профиль пользователя не найден."

    user_data = data["users"][user_id]

    # ⭐ НОВОЕ: Проверяем Бэт-пасс ⭐
    creation_cost = 0 if is_batpass_active(user_data) else CLAN_CREATION_COST

    if creation_cost > 0:
        current_cents = user_data.get("cents", 0)
        if current_cents < creation_cost:
            return False, f"Недостаточно бэт-коинов! Нужно {creation_cost}."
    
        # ✅ Списываем стоимость создания
        user_data["cents"] -= creation_cost
    
    # Создаём клан
    clan_id = f"clan_{int(time.time())}_{user_id}"
    data.setdefault("clans", {})[clan_id] = {
        "id": clan_id,
        "name": clan_name,
        "creator": user_id,
        "leader_id": user_id,  # ← Добавьте это поле!
        "members": {user_id: {"joined_at": int(time.time()), "role": "leader"}},  # ← dict, не list!
        "max_members": MAX_CLAN_MEMBERS,
        "created_at": int(time.time()),
        "description": "",
        "clan_avatar": None,
    }
    # Привязываем пользователя к клану
    data.setdefault("user_clan", {})[user_id] = clan_name
    
    return True, f"Клан **«{clan_name}»** успешно создан!"

async def basket_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню и правила игры Баскет."""
    try:
        # ⭐ ПОЛУЧАЕМ ID ИГРОКА И ЕГО БАЛАНС ⭐
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id, {})
        current_balance = user_data.get("cents", 0)
        plays_today = user_data.get("basket_plays", 0)
        
        # ⭐ ПРОВЕРКА: достаточно ли бэт-коинов ⭐
        if current_balance >= BASKET_GAME_COST:
            balance_text = f"💰 Ваш баланс: **{current_balance}** бэт-коинов ✅"
        else:
            balance_text = f"💰 Ваш баланс: **{current_balance}** бэт-коинов ❌ _(недостаточно)_"
        
        # ⭐ ПРОВЕРКА: сколько игр осталось сегодня ⭐
        remaining_plays = MAX_BASKET_DAILY_PLAYS - plays_today
        
        keyboard = [[InlineKeyboardButton("🏀 Сыграть", callback_data="basket_play")]]
        caption = (
            f"🏀 **Игра «Баскет»**\n"
            f"📜 **Правила:**\n"
            f"• Стоимость игры: {BASKET_GAME_COST} бэт-коинов\n"
            f"• Бот бросает 3 баскетбольных мяча 🏀\n"
            f"• За каждое попадание вы получаете 1 бесплатную попытку\n"
            f"• Лимит: {MAX_BASKET_DAILY_PLAYS} игр в день (сброс в 00:00 МСК)\n\n"
            f"{balance_text}"
        )
        
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            try:
                await query.message.delete()
            except:
                pass
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                text=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Ошибка в basket_menu: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("❌ Ошибка при открытии меню Баскета")

async def basket_play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Логика игры в Баскет."""
    try:
        query = update.callback_query
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        if not user_data:
            await query.edit_message_text("❌ Вы ещё не начали игру!")
            return

        # Сброс дневного лимита в 00:00 МСК
        msk_tz = datetime.timezone(datetime.timedelta(hours=3))
        now_msk = datetime.datetime.now(msk_tz)
        last_reset = user_data.get("basket_last_reset", 0)
        if last_reset == 0 or now_msk.day != datetime.datetime.fromtimestamp(last_reset, msk_tz).day:
            user_data["basket_plays"] = 0
            user_data["basket_last_reset"] = int(now_msk.timestamp())

        if user_data.get("basket_plays", 0) >= MAX_BASKET_DAILY_PLAYS:
            await query.edit_message_text("❌ Лимит игр на сегодня исчерпан! Приходите завтра после 00:00 МСК.")
            return

        if user_data.get("cents", 0) < BASKET_GAME_COST:
            await query.edit_message_text(f"❌ Недостаточно бэт-коинов! Нужно {BASKET_GAME_COST}. У вас: {user_data.get('cents', 0)}")
            return

        # Списание средств и учёт игры
        user_data["cents"] -= BASKET_GAME_COST
        user_data["basket_plays"] += 1
        save_data(data)
        

        await query.edit_message_text("🏀 Бросаем мячи...")

        hits = 0
        for _ in range(3):
            await asyncio.sleep(1.5)
            dice_msg = await context.bot.send_dice(chat_id=query.message.chat_id, emoji="🏀")
            # В Telegram 🏀 кубик выдаёт значения 1-5. 4 и 5 считаем попаданием.
            if dice_msg.dice.value >= 4:
                hits += 1

        if hits > 0:
            user_data["free_rolls"] = user_data.get("free_rolls", 0) + hits
            save_data(data)
            await query.message.reply_text(
                f"🏀 **Результат:** {hits}/3 попаданий!\n\n"
                f"🎁 Получено бесплатных попыток: {hits}\n",
                parse_mode="Markdown"
            )
            
        else:
            await query.message.reply_text("😔 Не повезло! 0/3 попаданий. Попробуйте ещё раз.")

        await update_quest_progress(context, user_id, "basket_3", 1)
            
        # Возвращаем меню
        keyboard = [[InlineKeyboardButton("🏀 Сыграть ещё", callback_data="basket_play")]]
        await query.message.reply_text(
            "🏀 **Баскет**\nХотите сыграть ещё раз?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Ошибка в basket_play: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def basket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок игры Баскет."""
    try:
        query = update.callback_query
        await query.answer()
        if query.data == "basket_play":
            await basket_play(update, context)
    except Exception as e:
        logger.error(f"Ошибка в basket_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

# ===== МАГАЗИН =====
# 🖼 ССЫЛКИ НА ИЗОБРАЖЕНИЯ (ЗАМЕНИТЕ НА СВОИ)
SHOP_MAIN_IMAGE = "https://files.catbox.moe/evkd6c.jpg"  # Главное меню
SHOP_DONATE_IMAGE = "https://files.catbox.moe/1tcx0h.jpg"    # Донат
CLASSIC_BOX_IMAGE = "https://files.catbox.moe/pezd3a.jpg"
SEASON_BOX_IMAGE = "https://files.catbox.moe/l3hxku.jpg"
ROLLS_BOX_IMAGE = "https://files.catbox.moe/ubyjxo.jpg"

# Список боксов для навигации
SHOP_BOXES = [
    {"name": "Rolls-Box", "price": 25000, "image": ROLLS_BOX_IMAGE, "is_rolls_box": True},
    {"name": "Classic-Box", "price": 30000, "image": CLASSIC_BOX_IMAGE, "is_classic_box": True},
    {"name": "Season-Box", "price": 0, "image": SEASON_BOX_IMAGE, "is_season_box": True},
    {"name": "Superman Heroes Box", "price": 0, "image": SUPERMAN_HEROES_IMAGE, "is_superman_heroes": True},
    {"name": "Superman Villain Box", "price": 0, "image": SUPERMAN_VILLAIN_IMAGE, "is_superman_villain": True},
]

async def shop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Главное меню магазина."""
    keyboard = [
        [InlineKeyboardButton("📦 Боксы", callback_data="shop_boxes")],
        [InlineKeyboardButton("🎴 Сезонные карты", callback_data="shop_seasonal")], 
        [InlineKeyboardButton("💎 Донат", callback_data="shop_donate")],
        [InlineKeyboardButton("🎫 Бэт-пасс", callback_data="shop_batpass")], 
    ]
    if hasattr(update, 'callback_query') and update.callback_query:
        try:
            await update.callback_query.message.delete()
        except:
            pass
        await context.bot.send_photo(
            chat_id=update.callback_query.message.chat_id,
            photo=SHOP_MAIN_IMAGE,
            caption="🛍️ **Добро пожаловать в Магазин!**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_photo(
            photo=SHOP_MAIN_IMAGE,
            caption="🛍️ **Добро пожаловать в Магазин!**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def shop_donate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Раздел Донат."""
    keyboard = [
        [InlineKeyboardButton("💬 Написать @Be9onder", url="https://t.me/Be9onder")],
        [InlineKeyboardButton("🔙 Назад в Магазин", callback_data="shop_menu")]
    ]
    
    text = (
        "💎 <b>Обменник валют Готэма</b>\n\n"
        "Приобрести местную валюту можно по выгодному курсу:\n\n"
        "• <b>100₽</b> — 10 000 Бэт-коинов 💰\n"
        "• <b>249₽</b> — 35 000 Бэт-коинов 💰\n"
        "• <b>499₽</b> — 80 000 Бэт-коинов 💰\n\n"
        "Для обмена обращаться сюда: @Be9onder"
    )
    
    if hasattr(update, 'callback_query') and update.callback_query:
        try:
            await update.callback_query.message.delete()
        except:
            pass
        await context.bot.send_message(
            chat_id=update.callback_query.message.chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

async def shop_boxes(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
    """Раздел Боксы с навигацией."""
    query = update.callback_query if hasattr(update, 'callback_query') and update.callback_query else None
    user_id = str(query.from_user.id if query else update.effective_user.id)
    chat_id = query.message.chat_id if query else update.effective_chat.id
    
    data = load_data()
    user_data = data["users"].get(user_id, {})
    if not context.user_data.get("shop_box_index"):
        context.user_data["shop_box_index"] = 0
        
    current_box = SHOP_BOXES[page]
    
    # Определение цены для отображения
    if current_box.get("is_rolls_box"):
        display_price = user_data.get("rolls_box_price", 25000)
    else:
        display_price = current_box["price"]
    
    # Формирование текста в зависимости от типа бокса
    if current_box.get("is_rolls_box"):
        text = (
            f"📦 **{current_box['name']}**\n"
            f"Цена: {display_price} бэт-коинов\n"
            f"🎁 Содержимое: **15 бесплатных попыток**\n"
            f"⚠️ Цена растёт на 5000 с каждой покупкой!"
        )
    elif current_box.get("is_classic_box"):
        text = (
            f"🏛 **{current_box['name']}**\n"
            f"💰 Цена: {display_price} бэт-коинов\n"
            f"🎁 Содержимое:\n"
            f"• 10 случайных Classic-карт\n"
            f"• Гарантированно 1 карта Epic\n"
        )
    elif current_box.get("is_season_box"):
        pending = user_data.get("pending_season_boxes", 0)
        text = (
            f"🎁 **{current_box['name']}**\n"
            f"💰 Цена: **799₽**\n"
            f"🎁 Содержимое:\n"
            f"• Все карты из сезонного магазина\n"
            f"• Эксклюзивная Epic Team-Up\n"
            f"• Сезонная аватарка 🖼\n"
            f"• 10 бесплатных попыток 🔍\n\n"
            f"💳 Для покупки напишите: @Be9onder"
        )
    # ⭐ НОВОЕ: Superman Heroes Box ⭐
    elif current_box.get("is_superman_heroes"):
        pending = user_data.get("pending_superman_heroes_boxes", 0)
        text = (
            f"🦸‍♂️ **{current_box['name']}**\n"
            f"💰 Цена: **179₽**\n"
            f"🎁 Содержимое: набор карт героев по Мои приключения с Суперменом\n\n"
            f"💳 Для покупки напишите: @Be9onder"
        )
    # ⭐ НОВОЕ: Superman Villain Box ⭐
    elif current_box.get("is_superman_villain"):
        pending = user_data.get("pending_superman_villain_boxes", 0)
        text = (
            f"🦹‍♂️ **{current_box['name']}**\n"
            f"💰 Цена: **179₽**\n"
            f"🎁 Содержимое: набор карт злодеев по Мои приключения с Суперменом\n\n"
            f"💳 Для покупки напишите: @Be9onder"
        )
    else:
        text = f"📦 **{current_box['name']}**\nЦена: {display_price} бэт-коинов"
    
    # Формирование клавиатуры
    keyboard = []
    if current_box.get("is_season_box"):
        pending = user_data.get("pending_season_boxes", 0)
        if pending > 0:
            keyboard.append([InlineKeyboardButton(f"🎁 Открыть Season-Box ({pending} шт.)", callback_data="shop_open_season_box")])
        keyboard.append([InlineKeyboardButton("💬 Написать @Be9onder", url="https://t.me/Be9onder")])
        
    # ⭐ НОВОЕ: Логика кнопок для Superman боксов ⭐
    elif current_box.get("is_superman_heroes") or current_box.get("is_superman_villain"):
        box_type = "heroes" if current_box.get("is_superman_heroes") else "villain"
        pending_key = f"pending_superman_{box_type}_boxes"
        pending = user_data.get(pending_key, 0)
        
        if pending > 0:
            emoji = "🦸‍♂️" if box_type == "heroes" else "🦹‍♂️"
            keyboard.append([InlineKeyboardButton(f"{emoji} Открыть ({pending} шт.)", callback_data=f"shop_open_superman_{box_type}")])
        keyboard.append([InlineKeyboardButton("💬 Написать @Be9onder", url="https://t.me/Be9onder")])
        
    else:
        keyboard.append([InlineKeyboardButton(f"💰 Купить за {display_price} бэт-коинов", callback_data=f"shop_buy_box_{page}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад в Магазин", callback_data="shop_menu")])
    
    # Навигация
    nav_btns = []
    if page > 0:
        nav_btns.append(InlineKeyboardButton("◀️", callback_data=f"shop_boxes_{page-1}"))
    nav_btns.append(InlineKeyboardButton(f"{page+1}/{len(SHOP_BOXES)}", callback_data="shop_info"))
    if page < len(SHOP_BOXES) - 1:
        nav_btns.append(InlineKeyboardButton("▶️", callback_data=f"shop_boxes_{page+1}"))
    keyboard.insert(-1, nav_btns)
    
    # Отправка
    if query:
        try:
            await query.message.delete()
        except:
            pass
        
        # ⭐ Универсальная отправка: пытаемся отправить фото, если не выйдет (например, file_id битый) - отправим текст ⭐
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=current_box["image"],
                caption=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception as photo_err:
            logger.warning(f"Не удалось отправить фото бокса: {photo_err}. Отправляю текст.")
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
    else:
        await update.message.reply_photo(
            photo=current_box["image"],
            caption=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def open_classic_box(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    price_paid: int
) -> None:
    """Открывает Classic-Box: 10 Classic-карт + 1 гарантированная Epic."""
    try:
        query = update.callback_query
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        # ⭐ Собираем все доступные Classic-карты ⭐
        classic_cards = [
            c for c in data["cards"]
            if c.get("is_classic") and c.get("available", True)
        ]
        
        # ⭐ Classic-карты редкости Epic (для гарантии) ⭐
        classic_epic_cards = [
            c for c in classic_cards
            if c.get("rarity") == "Epic"
        ]
        
        # Проверка: достаточно ли карт в системе
        if not classic_cards:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ **Ошибка!**\nВ системе нет доступных Classic-карт.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад в магазин", callback_data="shop_menu")
                ]]),
                parse_mode="Markdown"
            )
            return
        
        if not classic_epic_cards:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ **Ошибка!**\nВ системе нет Classic-карт редкости Epic.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад в магазин", callback_data="shop_menu")
                ]]),
                parse_mode="Markdown"
            )
            return
        
        # ⭐ ВЫБИРАЕМ КАРТЫ ⭐
        # 1 гарантированная Epic
        guaranteed_epic = random.choice(classic_epic_cards)
        
        # 9 случайных Classic-карт (могут повторяться, включая Epic)
        other_9 = random.choices(classic_cards, k=9)
        
        # Итоговый набор из 10 карт
        result_cards = [guaranteed_epic] + other_9
        
        # ⭐ ДОБАВЛЯЕМ КАРТЫ В КОЛЛЕКЦИЮ ИГРОКА (дубликаты как обычно) ⭐
        for card in result_cards:
            user_data["cards"].append(card["id"])
        
        save_data(data)
        
        # ⭐ ФОРМИРУЕМ АЛЬБОМ (media group) ⭐
        media_group = []
        for i, card in enumerate(result_cards):
            # Caption только у первого элемента (ограничение Telegram)
            caption = None
            if i == 0:
                caption = (
                    f"🏛 <b>Classic-Box открыт!</b>\n"
                    f"🎁 Получено 10 Classic-карт\n"
                    f"💰 Списано: {price_paid} бэт-коинов\n"
                    f"💳 Остаток: {user_data['cents']} бэт-коинов"
                )
            
            # Определяем тип медиа
            if card.get("media_type") == "animation" or card["image_url"].lower().endswith((".mp4", ".webm")):
                media_group.append(
                    InputMediaAnimation(
                        media=card["image_url"],
                        caption=caption,
                        parse_mode="HTML" if caption else None
                    )
                )
            else:
                media_group.append(
                    InputMediaPhoto(
                        media=card["image_url"],
                        caption=caption,
                        parse_mode="HTML" if caption else None
                    )
                )
        
        # ⭐ ОТПРАВЛЯЕМ АЛЬБОМ ⭐
        try:
            await context.bot.send_media_group(
                chat_id=query.message.chat_id,
                media=media_group
            )
        except Exception as media_error:
            # ⭐ FALLBACK: если альбом не получился (например, смешанные типы) — шлём по одному ⭐
            logger.warning(f"Не удалось отправить альбом: {media_error}. Отправляю по одному.")
            for i, card in enumerate(result_cards):
                cap = None
                if i == 0:
                    cap = (
                        f"🏛 <b>Classic-Box открыт!</b>\n"
                        f"🎁 Получено 10 Classic-карт\n"
                        f"⭐ Гарантированная Epic: <b>{html.escape(guaranteed_epic['title'])}</b>\n"
                        f"💰 Списано: {price_paid} бэт-коинов"
                    )
                
                if card.get("media_type") == "animation" or card["image_url"].lower().endswith((".mp4", ".webm")):
                    await context.bot.send_video(
                        chat_id=query.message.chat_id,
                        video=card["image_url"],
                        caption=cap,
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Назад в магазин", callback_data="shop_menu")
                        ]]),
                        parse_mode="HTML" if cap else None,
                        supports_streaming=True
                    )
                else:
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=card["image_url"],
                        caption=cap,
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Назад в магазин", callback_data="shop_menu")
                        ]]),
                        parse_mode="HTML" if cap else None
                    )
                await asyncio.sleep(0.3)
        
        logger.info(f"Игрок {user_id} открыл Classic-Box за {price_paid} бэт-коинов")
        
    except Exception as e:
        logger.error(f"Ошибка открытия Classic-Box: {e}")
        try:
            await context.bot.send_message(
                chat_id=update.callback_query.message.chat_id,
                text="❌ Произошла ошибка при открытии Classic-Box",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад в магазин", callback_data="shop_menu")
                ]])
            )
        except Exception:
            pass

async def open_season_box(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Открывает 1 Season-Box: все сезонные карты + ID 67 + аватарка + 10 попыток."""
    try:
        query = update.callback_query
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        if not user_data:
            await query.answer("❌ Профиль не найден", show_alert=True)
            return
        
        # ⭐ Миграция ⭐
        if "pending_season_boxes" not in user_data:
            user_data["pending_season_boxes"] = 0
        if "avatars" not in user_data:
            user_data["avatars"] = [DEFAULT_AVATAR_URL]
            
        pending = user_data["pending_season_boxes"]
        if pending <= 0:
            await query.answer("❌ У вас нет накопленных Season-Box", show_alert=True)
            return
        
        # ⭐ Собираем все сезонные карты ⭐
        seasonal_cards = []
        for cid_str in data.get("seasonal_cards", {}).keys():
            card = find_card_by_id(int(cid_str), data["cards"])
            if card:
                seasonal_cards.append(card)
                
        # ⭐ Эксклюзивная карта ID 67 ⭐
        exclusive_card = find_card_by_id(67, data["cards"])
        if exclusive_card and exclusive_card not in seasonal_cards:
            seasonal_cards.append(exclusive_card)
            
        # ⭐ Выдаём карты (дубликаты как обычно) ⭐
        for card in seasonal_cards:
            user_data["cards"].append(card["id"])
            
        # ⭐ Сезонная аватарка (если её нет) ⭐
        avatar_added = False
        if SEASON_BOX_AVATAR_URL not in user_data["avatars"]:
            user_data["avatars"].append(SEASON_BOX_AVATAR_URL)
            avatar_added = True
            
        # ⭐ 10 бесплатных попыток ⭐
        user_data["free_rolls"] = user_data.get("free_rolls", 0) + 10
        
        # ⭐ Уменьшаем счётчик pending ⭐
        user_data["pending_season_boxes"] = pending - 1
        save_data(data)
        
        await query.answer("🎁 Season-Box открыт!", show_alert=True)
        
        # ⭐ ФОРМИРУЕМ АЛЬБОМ (media group) ⭐
        # ⚠️ ВАЖНО: Telegram не поддерживает InputMediaAnimation в send_media_group!
        # Используем InputMediaVideo для MP4/GIF/WebM
        media_group = []
        for i, card in enumerate(seasonal_cards):
            caption = None
            if i == 0:
                caption = (
                    f"🎁 <b>Season-Box открыт!</b>\n"
                    f"🎴 Получено {len(seasonal_cards)} карт\n"
                    f"🔍 +10 бесплатных попыток\n"
                    f"🖼 {'+Сезонная аватарка' if avatar_added else ''}\n"
                    f"📦 Осталось открытых боксов: {user_data['pending_season_boxes']}"
                )
            
            # ⭐ ИСПРАВЛЕНИЕ: Используем InputMediaVideo вместо InputMediaAnimation ⭐
            media_group.append(
                InputMediaVideo(
                    media=card["image_url"],
                    caption=caption,
                    parse_mode="HTML" if caption else None,
                    supports_streaming=True
                ) if (card.get("media_type") == "animation" 
                      or card["image_url"].lower().endswith((".mp4", ".webm", ".gif")))
                else InputMediaPhoto(
                    media=card["image_url"],
                    caption=caption,
                    parse_mode="HTML" if caption else None
                )
            )
        
        # ⭐ ОТПРАВЛЯЕМ АЛЬБОМ ⭐
        try:
            await context.bot.send_media_group(
                chat_id=query.message.chat_id,
                media=media_group
            )
        except Exception as media_error:
            # ⭐ FALLBACK: если альбом не получился — шлём по одному ⭐
            logger.warning(f"Не удалось отправить альбом: {media_error}. Отправляю по одному.")
            for i, card in enumerate(seasonal_cards):
                cap = None
                if i == 0:
                    cap = (
                        f"🎁 <b>Season-Box открыт!</b>\n"
                        f"🎴 Получено {len(seasonal_cards)} карт\n"
                        f"🔍 +10 бесплатных попыток\n"
                        f"🖼 {'+Сезонная аватарка' if avatar_added else ''}"
                    )
                
                if card.get("media_type") == "animation" or card["image_url"].lower().endswith((".mp4", ".webm", ".gif")):
                    await context.bot.send_video(
                        chat_id=query.message.chat_id,
                        video=card["image_url"],
                        caption=cap,
                        parse_mode="HTML" if cap else None,
                        supports_streaming=True
                    )
                else:
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=card["image_url"],
                        caption=cap,
                        parse_mode="HTML" if cap else None
                    )
                await asyncio.sleep(0.3)
        
        # ⭐ Финальное сообщение ⭐
        kb = []
        if user_data["pending_season_boxes"] > 0:
            kb.append([InlineKeyboardButton(
                f"🎁 Открыть ещё ({user_data['pending_season_boxes']} шт.)",
                callback_data="shop_open_season_box"
            )])
        kb.append([InlineKeyboardButton("🔙 Назад в магазин", callback_data="shop_menu")])
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="✅ <b>Season-Box успешно открыт!</b>",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )
        
        logger.info(f"Игрок {user_id} открыл Season-Box (осталось: {user_data['pending_season_boxes']})")
        
    except Exception as e:
        logger.error(f"Ошибка открытия Season-Box: {e}")
        try:
            await context.bot.send_message(
                chat_id=update.callback_query.message.chat_id,
                text="❌ Произошла ошибка при открытии Season-Box",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад в магазин", callback_data="shop_menu")
                ]])
            )
        except Exception:
            pass

async def open_superman_box(update: Update, context: ContextTypes.DEFAULT_TYPE, box_type: str) -> None:
    """Универсальная функция открытия Superman боксов."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data:
            await query.answer("❌ Профиль не найден", show_alert=True)
            return
        
        # Определяем параметры бокса
        if box_type == "heroes":
            box_name = "Superman Heroes Box"
            emoji = "🦸‍♂️"
            pending_key = "pending_superman_heroes_boxes"
            cards_list = SUPERMAN_HEROES_CARDS
        else:
            box_name = "Superman Villain Box"
            emoji = "🦹‍♂️"
            pending_key = "pending_superman_villain_boxes"
            cards_list = SUPERMAN_VILLAIN_CARDS
        
        pending = user_data.get(pending_key, 0)
        if pending <= 0:
            await query.answer(f"❌ У вас нет накопленных {box_name}", show_alert=True)
            return
        
        # Собираем карты
        box_cards = []
        for card_id in cards_list:
            card = find_card_by_id(card_id, data["cards"])
            if card:
                box_cards.append(card)
        
        if not box_cards:
            await query.answer("❌ В боксе нет доступных карт (проверьте константы)", show_alert=True)
            return
        
        # Выдаём карты
        for card in box_cards:
            user_data["cards"].append(card["id"])
        
        # Уменьшаем счётчик
        user_data[pending_key] = pending - 1
        save_data(data)
        
        await query.answer(f"{emoji} {box_name} открыт!", show_alert=True)
        
        # ФОРМИРУЕМ АЛЬБОМ
        media_group = []
        for i, card in enumerate(box_cards):
            caption = None
            if i == 0:
                caption = (
                    f"{emoji} <b>{box_name} открыт!</b>\n"
                    f"🎴 Получено {len(box_cards)} карт\n"
                    f"📦 Осталось открытых боксов: {user_data[pending_key]}"
                )
            
            # Универсальная логика: file_id или URL
            media_source = card.get("media_source", "url")
            media_value = card.get("file_id") if media_source == "file_id" else card.get("image_url", "")
            
            if not media_value:
                logger.warning(f"У карты #{card['id']} отсутствует медиа! Пропускаем.")
                continue
            
            if card.get("media_type") == "animation" or (isinstance(media_value, str) and media_value.lower().endswith((".mp4", ".webm", ".gif"))):
                media_group.append(
                    InputMediaVideo(media=media_value, caption=caption, parse_mode="HTML" if caption else None, supports_streaming=True)
                )
            else:
                media_group.append(
                    InputMediaPhoto(media=media_value, caption=caption, parse_mode="HTML" if caption else None)
                )
        
        # ОТПРАВЛЯЕМ АЛЬБОМ
        try:
            await context.bot.send_media_group(chat_id=query.message.chat_id, media=media_group)
        except Exception as media_error:
            logger.warning(f"Не удалось отправить альбом: {media_error}. Отправляю по одному.")
            for i, card in enumerate(box_cards):
                cap = f"{emoji} <b>{box_name} открыт!</b>\n🎴 Получено {len(box_cards)} карт" if i == 0 else None
                
                media_source = card.get("media_source", "url")
                media_value = card.get("file_id") if media_source == "file_id" else card.get("image_url", "")
                if not media_value: continue
                
                try:
                    if card.get("media_type") == "animation" or (isinstance(media_value, str) and media_value.lower().endswith((".mp4", ".webm", ".gif"))):
                        await context.bot.send_video(chat_id=query.message.chat_id, video=media_value, caption=cap, parse_mode="HTML" if cap else None, supports_streaming=True)
                    else:
                        await context.bot.send_photo(chat_id=query.message.chat_id, photo=media_value, caption=cap, parse_mode="HTML" if cap else None)
                except Exception:
                    continue
                await asyncio.sleep(0.3)
        
        # Финальное сообщение
        kb = []
        if user_data[pending_key] > 0:
            kb.append([InlineKeyboardButton(f"{emoji} Открыть ещё ({user_data[pending_key]} шт.)", callback_data=f"shop_open_superman_{box_type}")])
        kb.append([InlineKeyboardButton("🔙 Назад к бокosм", callback_data="shop_boxes_0")])
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"✅ <b>{box_name} успешно открыт!</b>",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка открытия Superman box: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


# Обёртки для callback-обработчиков
async def open_superman_heroes_box(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await open_superman_box(update, context, "heroes")

async def open_superman_villain_box(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await open_superman_box(update, context, "villain")

async def give_superman_box(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выдаёт Superman-бокс игроку."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/give\\_superman\\_box \\[heroes\\|villain\\] \\[@никнейм\\] \\[количество\\]\n\n"
                "**Примеры:**\n"
                "/give\\_superman\\_box heroes @username\n"
                "/give\\_superman\\_box villain @username 3",
                parse_mode="Markdown"
            )
            return
        
        box_type = context.args[0].lower()
        target_input = context.args[1]
        count = int(context.args[2]) if len(context.args) > 2 else 1
        
        if box_type not in ["heroes", "villain"]:
            await update.message.reply_text("⚠️ Неверный тип! Используйте `heroes` или `villain`")
            return
        if count <= 0:
            await update.message.reply_text("⚠️ Количество должно быть положительным!")
            return
        
        # Определяем ID игрока
        target_user_id = None
        if target_input.startswith("@"):
            username_to_find = target_input[1:].strip().lower()
            for uid, udata in data["users"].items():
                if udata.get("username", "").lower() == username_to_find:
                    target_user_id = uid
                    break
            if not target_user_id:
                await update.message.reply_text(f"⚠️ Игрок @{username_to_find} не найден!")
                return
        else:
            target_user_id = target_input
            if target_user_id not in data["users"]:
                await update.message.reply_text(f"⚠️ Игрок с ID {target_user_id} не найден!")
                return
        
        user_data = data["users"][target_user_id]
        pending_key = f"pending_superman_{box_type}_boxes"
        
        # Миграция
        if pending_key not in user_data:
            user_data[pending_key] = 0
        
        user_data[pending_key] += count
        save_data(data)
        
        # ⭐ Уведомление игроку с кнопкой "Открыть" ⭐
        try:
            box_name = "Superman Heroes Box" if box_type == "heroes" else "Superman Villain Box"
            emoji = "🦸‍♂️" if box_type == "heroes" else "🦹‍♂️"
            
            # Склонение
            if count % 10 == 1 and count % 100 != 11: 
                box_word = "бокс"
            elif count % 10 in [2, 3, 4] and count % 100 not in [12, 13, 14]: 
                box_word = "бокса"
            else: 
                box_word = "боксов"
            
            image_url = SUPERMAN_HEROES_IMAGE if box_type == "heroes" else SUPERMAN_VILLAIN_IMAGE
            
            # ⭐ ФОРМИРУЕМ КНОПКУ ОТКРЫТИЯ ⭐
            keyboard = [[
                InlineKeyboardButton(
                    f"{emoji} Открыть {box_name}", 
                    callback_data=f"shop_open_superman_{box_type}"
                )
            ]]
            
            try:
                await context.bot.send_photo(
                    chat_id=int(target_user_id),
                    photo=image_url,
                    caption=(
                        f"{emoji} <b>Вам был выдан {box_name}!</b>\n\n"
                        f"Нажмите кнопку ниже, чтобы открыть бокс:"
                    ),
                    reply_markup=InlineKeyboardMarkup(keyboard), # ⭐ ДОБАВЛЕНО ⭐
                    parse_mode="HTML"
                )
            except Exception:
                # Fallback, если картинка не загрузилась
                await context.bot.send_message(
                    chat_id=int(target_user_id),
                    text=(
                        f"{emoji} <b>Вам был выдан {box_name}!</b>\n\n"
                        f"📦 <b>Количество:</b> {count} {box_word}\n\n"
                        f"Нажмите кнопку ниже, чтобы открыть бокс:"
                    ),
                    reply_markup=InlineKeyboardMarkup(keyboard), # ⭐ ДОБАВЛЕНО ⭐
                    parse_mode="HTML"
                )
        except Exception as notify_error:
            logger.warning(f"Не удалось уведомить игрока {target_user_id}: {notify_error}")
        
        await update.message.reply_text(
            f"✅ **{box_name} выдан!**\n"
            f"👤 Игрок: {target_user_id}\n"
            f"📦 Количество: {count} шт.\n"
            f"📊 Всего накоплено: {user_data[pending_key]}",
            parse_mode="Markdown"
        )
        
    except ValueError:
        await update.message.reply_text("⚠️ Количество должно быть числом!")
    except Exception as e:
        logger.error(f"Ошибка give_superman_box: {e}")
        await update.message.reply_text("❌ Ошибка при выдаче бокса")
        
async def give_season_box(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выдаёт Season-Box игроку по ID или @никнейму."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
            
        if not context.args:
            await update.message.reply_text(
                "ℹ️ **Формат:**\n/give_season_box [ID_или_@никнейм]\n"
                "**Примеры:**\n/give_season_box 881692999\n/give_season_box @username",
                parse_mode="Markdown"
            )
            return
            
        target = context.args[0]
        target_id = None
        
        if target.startswith("@"):
            uname = target[1:].strip().lower()
            for uid, u in data["users"].items():
                if u.get("username", "").lower() == uname:
                    target_id = uid
                    break
            if not target_id:
                await update.message.reply_text(f"⚠️ Игрок @{uname} не найден!")
                return
        else:
            if target not in data["users"]:
                await update.message.reply_text(f"⚠️ Игрок с ID {target} не найден!")
                return
            target_id = target
            
        user_data = data["users"][target_id]
        if "pending_season_boxes" not in user_data:
            user_data["pending_season_boxes"] = 0
            
        user_data["pending_season_boxes"] += 1
        save_data(data)
        
        # Уведомление игроку
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    "🎁 <b>Вам начислен Season-Box!</b>\n\n"
                    f"📦 Накоплено боксов: <b>{user_data['pending_season_boxes']}</b>\n"
                    f"Нажмите кнопку ниже, чтобы открыть его:\n\n"
                    f"🎁 Содержимое:\n"
                    f"• Все сезонные карты\n"
                    f"• Эксклюзивная Epic Team-Up\n"
                    f"• Сезонная аватарка 🖼\n"
                    f"• 10 бесплатных попыток 🔍"
                ),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎁 Открыть сейчас", callback_data="shop_open_season_box")]]),
                parse_mode="HTML"
            )
        except Exception as notify_err:
            logger.warning(f"Не удалось уведомить игрока {target_id}: {notify_err}")
            
        await update.message.reply_text(
            f"✅ **Season-Box выдан!**\n"
            f"👤 Игрок: {target_id}\n"
            f"📦 Всего накоплено: {user_data['pending_season_boxes']}",
            parse_mode="Markdown"
        )
        logger.info(f"Админ выдал Season-Box игроку {target_id}")
    except Exception as e:
        logger.error(f"Ошибка give_season_box: {e}")
        await update.message.reply_text("❌ Ошибка при выдаче Season-Box")


async def shop_seasonal(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
    """Показывает сезонные карты с навигацией."""
    try:
        query = update.callback_query if hasattr(update, 'callback_query') and update.callback_query else None
        user_id = str(query.from_user.id if query else update.effective_user.id)
        chat_id = query.message.chat_id if query else update.effective_chat.id
        
        data = load_data()
        user_data = data["users"].get(user_id, {})
        seasonal = data.get("seasonal_cards", {})
        
        if not seasonal:
            text = "📭 **Сезонные карты**\n\nСейчас нет доступных сезонных карт."
            keyboard = [[InlineKeyboardButton("🔙 Назад в Магазин", callback_data="shop_menu")]]
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            return
        
        # Сортируем по ID для стабильной навигации
        seasonal_list = list(seasonal.items())
        total_cards = len(seasonal_list)
        
        # Корректировка индекса
        if page < 0:
            page = 0
        elif page >= total_cards:
            page = total_cards - 1
        
        # Сохраняем текущий индекс
        context.user_data[f"seasonal_page_{user_id}"] = page
        
        card_id_str, price = seasonal_list[page]
        card_id = int(card_id_str)
        card = find_card_by_id(card_id, data["cards"])
        
        if not card:
            if query:
                await query.edit_message_text("⚠️ Карта не найдена!")
            else:
                await update.message.reply_text("⚠️ Карта не найдена!")
            return
        
        # ⭐ Определяем, хватает ли бэт-коинов ⭐
        user_cents = user_data.get("cents", 0)
        can_afford = user_cents >= price
        
        # ⭐ Формируем caption (стандартный, как в архиве) ⭐
        caption = generate_card_caption(card, user_data=None, count=1, show_bonus=False)
        caption += f"\n\n💰 <b>Цена:</b> {price} бэт-коинов"
        if not can_afford:
            caption += f"\n❌ <i>Недостаточно бэт-коинов (у вас: {user_cents})</i>"
        
        # ⭐ Формируем клавиатуру ⭐
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"ss_nav_{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_cards}", callback_data="ss_info"))
        if page < total_cards - 1:
            nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"ss_nav_{page + 1}"))
        
        # ⭐ Кнопка покупки: активная или серая ⭐
        if can_afford:
            buy_button = InlineKeyboardButton(
                f"💰 Купить за {price} бэт-коинов",
                callback_data=f"ss_buy_{card_id}"
            )
        else:
            buy_button = InlineKeyboardButton(
                f"❌ Недостаточно бэт-коинов",
                callback_data="ss_no_cents"
            )
        
        keyboard = [
            nav_buttons,
            [buy_button],
            [InlineKeyboardButton("🔙 Назад в Магазин", callback_data="shop_menu")]
        ]
        
        # ⭐ Отправляем карту ⭐
        if query:
            try:
                if card.get("media_type") == "animation":
                    media = InputMediaAnimation(
                        media=card["image_url"],
                        caption=caption,
                        parse_mode="HTML"
                    )
                else:
                    media = InputMediaPhoto(
                        media=card["image_url"],
                        caption=caption,
                        parse_mode="HTML"
                    )
                await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception as edit_error:
                if "Message is not modified" in str(edit_error):
                    # Просто обновляем клавиатуру
                    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
                    return
                logger.error(f"Ошибка редактирования сезонной карты: {edit_error}")
                try:
                    await query.message.delete()
                except:
                    pass
                await send_card(update, card, context, caption=caption, 
                               reply_markup=InlineKeyboardMarkup(keyboard), 
                               chat_id=chat_id)
        else:
            await send_card(update, card, context, caption=caption,
                           reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Ошибка shop_seasonal: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("❌ Произошла ошибка")


async def shop_seasonal_buy(update: Update, context: ContextTypes.DEFAULT_TYPE, card_id: int) -> None:
    """Покупка сезонной карты."""
    try:
        query = update.callback_query
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id, {})
        
        card_id_str = str(card_id)
        seasonal = data.get("seasonal_cards", {})
        
        if card_id_str not in seasonal:
            await query.answer("⚠️ Карта больше не в сезонных!", show_alert=True)
            return
        
        price = seasonal[card_id_str]
        user_cents = user_data.get("cents", 0)
        
        if user_cents < price:
            await query.answer("❌ Недостаточно бэт-коинов!", show_alert=True)
            return
        
        card = find_card_by_id(card_id, data["cards"])
        if not card:
            await query.answer("⚠️ Карта не найдена!", show_alert=True)
            return
        
        # ⭐ Списываем бэт-коины ⭐
        user_data["cents"] = user_cents - price
        
        # ⭐ Добавляем карту (дубликаты как обычно) ⭐
        user_data["cards"].append(card_id)
        
        save_data(data)
        
        # ⭐ Уведомление ⭐
        await query.answer(f"✅ Вы купили {card['title']}!", show_alert=True)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=(
                f"✅ **Покупка успешна!**\n"
                f"🃏 Карта: **{card['title']}**\n"
                f"🌟 Редкость: {card['rarity']}\n"
                f"💰 Списано: {price} бэт-коинов\n"
                f"💳 Остаток: {user_data['cents']} бэт-коинов"
            ),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад в магазин", callback_data="shop_menu")
            ]]),
            parse_mode="Markdown"
        )
        
        logger.info(f"Игрок {user_id} купил сезонную карту #{card_id} за {price}")
    except Exception as e:
        logger.error(f"Ошибка shop_seasonal_buy: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


async def shop_seasonal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок сезонных карт."""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = str(query.from_user.id)
        
        # ⭐ Навигация ⭐
        if query.data.startswith("ss_nav_"):
            try:
                page = int(query.data.replace("ss_nav_", ""))
                await shop_seasonal(update, context, page=page)
            except (ValueError, IndexError):
                await query.answer("❌ Ошибка навигации", show_alert=True)
            return
        
        # ⭐ Покупка ⭐
        if query.data.startswith("ss_buy_"):
            try:
                card_id = int(query.data.replace("ss_buy_", ""))
                await shop_seasonal_buy(update, context, card_id)
            except (ValueError, IndexError):
                await query.answer("❌ Ошибка данных", show_alert=True)
            return
        
        # ⭐ Инфо ⭐
        if query.data == "ss_info":
            await query.answer("📄 Используйте ◀️ и ▶️ для навигации", show_alert=False)
            return
        
        # ⭐ Недостаточно бэт-коинов ⭐
        if query.data == "ss_no_cents":
            await query.answer("❌ Недостаточно бэт-коинов для покупки!", show_alert=True)
            return
    except Exception as e:
        logger.error(f"Ошибка shop_seasonal_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)
        
async def shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик всех кнопок магазина."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "shop_menu":
        await shop_menu(update, context)
    elif query.data == "shop_batpass":
        await shop_batpass(update, context)
        return
    elif query.data == "shop_seasonal":
        await shop_seasonal(update, context, page=0)
    elif query.data == "shop_donate":
        await shop_donate(update, context)
    elif query.data == "shop_tries":
        await shop_tries(update, context)
    elif query.data.startswith("shop_boxes"):
        if query.data == "shop_boxes":
            page = 0
        else:
            try:
                page = int(query.data.split("_")[-1])
            except (ValueError, IndexError):
                await query.answer("❌ Ошибка навигации", show_alert=True)
                return
        context.user_data["shop_box_index"] = page
        await shop_boxes(update, context, page)
        
    elif query.data.startswith("shop_buy_box"):
        try:
            page = int(query.data.split("_")[-1])
            box = SHOP_BOXES[page]
            user_id = str(query.from_user.id)
            data = load_data()
            user_data = data["users"].get(user_id, {})
        
            # ⭐ Определяем цену (для Rolls-Box — индивидуальная) ⭐
            if box.get("is_rolls_box"):
                current_price = user_data.get("rolls_box_price", 25000)
            else:
                current_price = box["price"]
        
            if user_data.get("cents", 0) < current_price:
                await query.answer("❌ Недостаточно бэт-коинов!", show_alert=True)
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="❌ **Ошибка покупки**\nНедостаточно бэт-коинов!",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад в магазин", callback_data="shop_menu")
                    ]]),
                    parse_mode="Markdown"
                )
            else:
                # ✅ Успешная покупка
                user_data["cents"] -= current_price

                # ⭐ НОВОЕ: Обновляем сезонные квесты при покупке бокса ⭐
                if box.get("is_rolls_box"):
                    update_seasonal_on_box_buy(user_data, "rolls")
                elif box.get("is_classic_box"):
                    update_seasonal_on_box_buy(user_data, "classic")  # ⭐ ДОБАВЛЕНО: Обновляем квест!
                    await query.answer("🏛 Открываем Classic-Box...", show_alert=False)
                    save_data(data)  # ⭐ ВАЖНО: Сохраняем обновление сезонного квеста!
                    await open_classic_box(update, context, current_price)
                    return
            
                # ⭐ Логика для Rolls-Box ⭐
                if box.get("is_rolls_box"):
                    user_data["free_rolls"] = user_data.get("free_rolls", 0) + 15
                    user_data["rolls_box_price"] = current_price + 5000  # Повышаем цену
                
                    save_data(data)
                    await query.answer(f"✅ Вы купили {box['name']}!", show_alert=True)
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text=(
                            f"✅ **Покупка успешна!**\n"
                            f"📦 Вы приобрели: **{box['name']}**\n"
                            f"🎁 Получено: **15 бесплатных попыток**\n"
                            f"💰 Списано: {current_price} бэт-коинов\n"
                            f"💳 Остаток: {user_data['cents']} бэт-коинов\n"
                            f"⚠️ Новая цена бокса: {current_price + 5000} бэт-коинов"
                        ),
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Назад в магазин", callback_data="shop_menu")
                        ]]),
                        parse_mode="Markdown"
                    )
                else:
                    # Обычный бокс
                    save_data(data)
                    await query.answer(f"✅ Вы купили {box['name']}!", show_alert=True)
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text=(
                            f"✅ **Покупка успешна!**\n"
                            f"📦 Вы приобрели: **{box['name']}**\n"
                            f"💰 Списано: {current_price} бэт-коинов\n"
                            f"💳 Остаток: {user_data['cents']} бэт-коинов"
                        ),
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Назад в магазин", callback_data="shop_menu")
                        ]]),
                        parse_mode="Markdown"
                    )
        except Exception as e:
            logger.error(f"Ошибка покупки бокса: {e}")
            await query.answer("❌ Произошла ошибка", show_alert=True)

    elif query.data == "shop_open_season_box":
        await open_season_box(update, context)

    elif query.data == "shop_open_superman_heroes":
        await open_superman_heroes_box(update, context)
        
    elif query.data == "shop_open_superman_villain":
        await open_superman_villain_box(update, context)

    elif query.data == "shop_info":
        await query.answer("📦 Используйте ◀️ и ▶️ для навигации по боксам", show_alert=False)

# ===== МЕНЮ СЖИГАНИЯ =====
async def burn_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню выбора редкости для сжигания (3×3 сетка)."""
    try:
        query = update.callback_query if hasattr(update, 'callback_query') else None
        user_id = str(update.effective_user.id)
        
        # ⭐ НОВОЕ: Очищаем сохранённые данные навигации при входе в меню ⭐
        # Это нужно, чтобы при повторном выборе той же редкости
        # создавалось новое сообщение, а не редактировалось старое
        context.user_data.pop(f"burn_nav_msg_{user_id}", None)
        context.user_data.pop(f"burn_nav_rarity_{user_id}", None)
        context.user_data.pop(f"burn_nav_index_{user_id}", None)
        
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            text = "❌ У вас нет карт для сжигания!"
            if query:
                await query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return
        
        # ⭐ СЕТКА 3×3: 9 редкостей ⭐
        rarities = [
            "Common", "Rare", "Rare Team-up",
            "Epic", "Epic Team-up", "Legendary",
            "Legendary Team-up", "Highlight", "Limited"
        ]
        keyboard = []
        for i in range(0, len(rarities), 3):
            row = []
            for rarity in rarities[i:i+3]:
                # Проверяем, есть ли у игрока карты этой редкости
                has_cards = any(
                    (c := find_card_by_id(cid, data["cards"])) and c.get("rarity") == rarity
                    for cid in set(user_data["cards"])
                )
                emoji = "🔥" if has_cards else "⚪"
                row.append(InlineKeyboardButton(
                    f"{emoji} {rarity}",
                    callback_data=f"burn_rarity_{rarity}"
                ))
            keyboard.append(row)
        
        # Кнопка "Все карты"
        keyboard.append([InlineKeyboardButton("📋 Все карты", callback_data="burn_all")])
        keyboard.append([InlineKeyboardButton("🔥 Сжечь ВСЁ", callback_data="burn_all_preview")])
        
        caption = (
            "🔥 **Меню сжигания**\n\n"
            "💡 **Сжигать можно только дубликаты карт!**\n"
            "Выберите редкость для просмотра карт:\n\n"
            "💰 **Награды за сжигание:**\n"
            "• Common: 100 бэт-коинов 💰\n"
            "• Rare: 200 бэт-коинов 💰\n"
            "• Rare Team-up: 300 бэт-коинов 💰\n"
            "• Epic: 1 бесплатный найм 🔍\n"
            "• Epic Team-up: 3 бесплатных найма 🔍\n"
            "• Legendary: 5 бесплатных наймов 🔍\n"
            "• Legendary Team-up: 7 бесплатных наймов 🔍\n"
            "• Highlight: 10 бесплатных наймов 🔍\n\n"
            "🔒 **Карты редкости Limited защищены от массового сжигания!**"
        )
        
        if query:
            try:
                await query.message.delete()
            except:
                pass
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Ошибка в burn_menu: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Ошибка", show_alert=True)
        else:
            await update.message.reply_text("❌ Ошибка при открытии меню сжигания")


async def show_burn_cards(update: Update, context: ContextTypes.DEFAULT_TYPE, rarity: Optional[str] = None, start_index: int = 0) -> None:
    """Показывает карты для сжигания (ТОЛЬКО ДУБЛИКАТЫ) с навигацией."""
    try:
        query = update.callback_query if hasattr(update, 'callback_query') and update.callback_query else None
        user_id = str(query.from_user.id if query else update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            msg = "❌ У вас нет карт для сжигания!"
            saved_msg_id = context.user_data.get(f"burn_nav_msg_{user_id}")
            if query and saved_msg_id:
                try:
                    await context.bot.edit_message_text(
                        chat_id=query.message.chat_id,
                        message_id=saved_msg_id,
                        text=msg,
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Назад в меню сжигания", callback_data="burn_menu")
                        ]])
                    )
                except:
                    pass
            elif query:
                await query.edit_message_text(msg)
            else:
                await update.message.reply_text(msg)
            return
        
        user_card_ids = user_data["cards"]
        card_counts = Counter(user_card_ids)
        
        # ⭐ ИСПРАВЛЕНИЕ: Фильтруем только карты с дубликатами (count > 1) ⭐
        cards_to_show = []
        for card_id, count in card_counts.items():
            if count <= 1:
                continue  # ⭐ Пропускаем карты без дубликатов ⭐
            
            card = find_card_by_id(card_id, data["cards"])
            if card:
                if rarity is None or card.get("rarity") == rarity:
                    cards_to_show.append((card, count))
        
        if not cards_to_show:
            msg = (
                f"❌ У вас нет карт с дубликатами{f' редкости {rarity}' if rarity else ''}!\n\n"
                f"💡 Сжигать можно только дубликаты карт.\n"
                f"У каждой карты всегда остаётся минимум 1 копия."
            )
            saved_msg_id = context.user_data.get(f"burn_nav_msg_{user_id}")
            if query and saved_msg_id:
                try:
                    await context.bot.edit_message_text(
                        chat_id=query.message.chat_id,
                        message_id=saved_msg_id,
                        text=msg,
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Назад в меню сжигания", callback_data="burn_menu")
                        ]])
                    )
                except:
                    pass
            elif query:
                await query.edit_message_text(msg)
            else:
                await update.message.reply_text(msg)
            return
        
        # Сортируем по ID
        cards_to_show.sort(key=lambda x: x[0]["id"])
        total_cards = len(cards_to_show)
        
        # Корректировка индекса
        start_index = max(0, min(start_index, total_cards - 1))
        card, count = cards_to_show[start_index]
        
        # ⭐ ИСПРАВЛЕНИЕ: Показываем количество ДУБЛИКАТОВ (count - 1) ⭐
        duplicates_count = count - 1
        
        reward = BURN_REWARDS.get(card["rarity"], {"cents": 0, "free_rolls": 0})
        reward_parts = []
        if reward["cents"] > 0:
            reward_parts.append(f"💰 {reward['cents']} бэт-коинов")
        if reward["free_rolls"] > 0:
            reward_parts.append(f"🔍 {reward['free_rolls']} попыток")
        
        caption = (
            f"{card['title']}\n"
            f"Редкость: {card['rarity']}\n"
            f"🛡 Всего в архиве: {count} шт.\n"
            f"🔥 **Дубликатов для сжигания: {duplicates_count}**\n\n"
            f"🎁 При сжигании Вы получите:\n"
            f"{'| '.join(reward_parts) if reward_parts else 'Ничего'}\n\n"
            f"📊 {start_index + 1}/{total_cards}"
        )
        
        # Клавиатура навигации
        keyboard = []
        nav_buttons = []
        if start_index > 0:
            nav_buttons.append(InlineKeyboardButton("<", callback_data=f"burn_prev_{card['rarity']}_{start_index - 1}"))
        nav_buttons.append(InlineKeyboardButton(f"{start_index + 1}/{total_cards}", callback_data="burn_info"))
        if start_index < total_cards - 1:
            nav_buttons.append(InlineKeyboardButton(">", callback_data=f"burn_next_{card['rarity']}_{start_index + 1}"))
        keyboard.append(nav_buttons)
        
        # Кнопки действий
        keyboard.append([
            InlineKeyboardButton("🔥 Сжечь 1 дубликат", callback_data=f"burn_confirm_{card['id']}"),
        ])
        keyboard.append([
            InlineKeyboardButton("🔙 Назад в меню сжигания", callback_data="burn_menu")
        ])
        
        # ⭐ УНИВЕРСАЛЬНАЯ ЛОГИКА: file_id или URL ⭐
        media_source = card.get("media_source", "url")
        media_value = card.get("file_id") if media_source == "file_id" else card["image_url"]
        
        # ⭐ ПРОВЕРЯЕМ, СМЕНИЛАСЬ ЛИ РЕДКОСТЬ ⭐
        saved_msg_id = context.user_data.get(f"burn_nav_msg_{user_id}")
        saved_rarity = context.user_data.get(f"burn_nav_rarity_{user_id}")
        
        if saved_rarity != rarity:
            saved_msg_id = None
            context.user_data.pop(f"burn_nav_msg_{user_id}", None)
        
        if query and saved_msg_id:
            try:
                if card.get("media_type") == "animation":
                    media = InputMediaAnimation(media=media_value, caption=caption, parse_mode="Markdown")
                else:
                    media = InputMediaPhoto(media=media_value, caption=caption, parse_mode="Markdown")
                await context.bot.edit_message_media(
                    chat_id=query.message.chat_id,
                    message_id=saved_msg_id,
                    media=media,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as edit_error:
                error_str = str(edit_error)
                if "Message is not modified" in error_str:
                    context.user_data[f"burn_nav_rarity_{user_id}"] = rarity
                    context.user_data[f"burn_nav_index_{user_id}"] = start_index
                    return
                else:
                    logger.warning(f"Не удалось отредактировать навигацию: {edit_error}. Отправляю новое.")
                    context.user_data.pop(f"burn_nav_msg_{user_id}", None)
                    saved_msg_id = None
        
        if not saved_msg_id:
            try:
                if query:
                    if card.get("media_type") == "animation":
                        sent_message = await query.message.reply_animation(
                            animation=media_value,
                            caption=caption,
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode="Markdown"
                        )
                    else:
                        sent_message = await query.message.reply_photo(
                            photo=media_value,
                            caption=caption,
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode="Markdown"
                        )
                    context.user_data[f"burn_nav_msg_{user_id}"] = sent_message.message_id
                else:
                    if card.get("media_type") == "animation":
                        sent_message = await update.message.reply_animation(
                            animation=media_value,
                            caption=caption,
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode="Markdown"
                        )
                    else:
                        sent_message = await update.message.reply_photo(
                            photo=media_value,
                            caption=caption,
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode="Markdown"
                        )
                    context.user_data[f"burn_nav_msg_{user_id}"] = sent_message.message_id
            except Exception as send_error:
                logger.error(f"Не удалось отправить новое сообщение: {send_error}")
                if query:
                    await query.answer("❌ Ошибка при показе карты", show_alert=True)
                return
        
        context.user_data[f"burn_nav_rarity_{user_id}"] = rarity
        context.user_data[f"burn_nav_index_{user_id}"] = start_index
        
    except Exception as e:
        logger.error(f"Ошибка в show_burn_cards: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("❌ Произошла ошибка")

async def burn_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, card_id: int) -> None:
    """Отправляет ОТДЕЛЬНОЕ сообщение с подтверждением сжигания 1 дубликата."""
    try:
        query = update.callback_query
        user_id = str(query.from_user.id)
        data = load_data()
        card = find_card_by_id(card_id, data["cards"])
        
        if not card:
            await query.answer("❌ Карта не найдена!", show_alert=True)
            return
        
        user_data = data["users"].get(user_id)
        if not user_data or card_id not in user_data.get("cards", []):
            await query.answer("❌ У вас нет этой карты!", show_alert=True)
            return
        
        # ⭐ ИСПРАВЛЕНИЕ: Проверяем количество копий ⭐
        card_count = user_data["cards"].count(card_id)
        
        if card_count < 2:
            # ⭐ Нельзя сжечь единственную копию ⭐
            await query.answer(
                "❌ Нельзя сжечь единственную копию карты!\n"
                "У вас должна остаться хотя бы 1 копия.",
                show_alert=True
            )
            return
        
        duplicates_count = card_count - 1
        
        reward = BURN_REWARDS.get(card["rarity"], {"cents": 0, "free_rolls": 0})
        reward_parts = []
        if reward["cents"] > 0:
            reward_parts.append(f"💰 {reward['cents']} бэт-коинов")
        if reward["free_rolls"] > 0:
            reward_parts.append(f"🔍 {reward['free_rolls']} попыток")
        
        text = (
            f"🔥 **Подтверждение сжигания**\n\n"
            f"🏷 Карта: {card['title']}\n"
            f"🌟 Редкость: {card['rarity']}\n\n"
            f"🛡 Всего в архиве: **{card_count}** шт.\n"
            f"✅ Останется: **{card_count - 1}** шт.\n\n"
            f"🎁 При сжигании вы получите:\n"
            f"{'| '.join(reward_parts) if reward_parts else 'Ничего'}\n"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, сжечь 1 дубликат", callback_data=f"burn_execute_{card_id}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"burn_show_{card['rarity']}")
            ]
        ]
        
        # Удаляем старое сообщение и отправляем новое
        try:
            await query.message.delete()
        except:
            pass
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        await query.answer("🔥 Подтвердите сжигание ниже", show_alert=False)
        
    except Exception as e:
        logger.error(f"Ошибка в burn_confirm: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def burn_execute(update: Update, context: ContextTypes.DEFAULT_TYPE, card_id: int) -> None:
    """Выполняет сжигание 1 дубликата карты."""
    try:
        query = update.callback_query
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data:
            await query.answer("❌ Профиль не найден!", show_alert=True)
            return
        
        card = find_card_by_id(card_id, data["cards"])
        if not card:
            await query.answer("❌ Карта не найдена!", show_alert=True)
            return
        
        # ⭐ ИСПРАВЛЕНИЕ: Проверяем количество копий ⭐
        card_count = user_data["cards"].count(card_id)
        
        if card_count < 2:
            await query.answer(
                "❌ Нельзя сжечь единственную копию карты!",
                show_alert=True
            )
            return
        
        # ⭐ УДАЛЯЕМ ОДНУ КОПИЮ КАРТЫ (оставляя минимум 1) ⭐
        user_data["cards"].remove(card_id)
        update_seasonal_on_burn(user_data, card["rarity"])
        
        # ⭐ ВЫДАЁМ НАГРАДУ ⭐
        reward = BURN_REWARDS.get(card["rarity"], {"cents": 0, "free_rolls": 0})
        user_data["cents"] = user_data.get("cents", 0) + reward["cents"]
        user_data["free_rolls"] = user_data.get("free_rolls", 0) + reward["free_rolls"]
        
        save_data(data)
        
        # ⭐ ТРИГГЕРЫ КВЕСТОВ ⭐
        if card["rarity"] == "Common":
            await update_quest_progress(context, user_id, "burn_common_3", 1)
        elif card["rarity"] == "Rare":
            await update_weekly_quest_progress(context, user_id, "weekly_burn_rare_4", 1)
        
        # ⭐ Формируем текст ⭐
        reward_parts = []
        if reward["cents"] > 0:
            reward_parts.append(f"💰 +{reward['cents']} бэт-коинов")
        if reward["free_rolls"] > 0:
            reward_parts.append(f"🔍 +{reward['free_rolls']} бесплатных попыток")
        
        # ⭐ ИСПРАВЛЕНИЕ: Показываем, что осталось ⭐
        remaining_count = card_count - 1
        
        text = (
            f"✅ **Сжигание успешно!** 🔥\n\n"
            f"🗑️ Сожжён 1 дубликат карты: **{card['title']}**\n"
            f"🛡 Осталось в архиве: **{remaining_count}** шт.\n"
            f"🌟 Редкость: {card['rarity']}\n\n"
            f"🎁 Награда получена:\n"
            f"{'| '.join(reward_parts) if reward_parts else 'Ничего'}"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔙 Назад к картам", callback_data=f"burn_show_{card['rarity']}")],
            [InlineKeyboardButton("🔙 В меню сжигания", callback_data="burn_menu")]
        ]
        
        try:
            await query.message.delete()
        except:
            pass
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        logger.info(f"Игрок {user_id} сжёг 1 дубликат карты #{card_id} ({card['rarity']}), осталось {remaining_count} шт.")
        
    except Exception as e:
        logger.error(f"Ошибка в burn_execute: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def burn_all_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает предпросмотр награды за сжигание ВСЕХ ДУБЛИКАТОВ карт."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            await query.edit_message_text("❌ У вас нет карт для сжигания!")
            return
        
        # ⭐ ИСПРАВЛЕНИЕ: Считаем только дубликаты ⭐
        total_cents = 0
        total_rolls = 0
        cards_to_burn = []  # Список (card, count_to_burn)
        total_duplicates = 0
        
        card_counts = Counter(user_data["cards"])
        
        for cid, count in card_counts.items():
            card = find_card_by_id(cid, data["cards"])
            if not card:
                continue
            
            # ⭐ Пропускаем карты без дубликатов ⭐
            if count <= 1:
                continue
            
            # ⭐ Сжигаем только дубликаты (count - 1) ⭐
            duplicates = count - 1
            total_duplicates += duplicates
            
            reward = BURN_REWARDS.get(card["rarity"], {"cents": 0, "free_rolls": 0})
            total_cents += reward["cents"] * duplicates
            total_rolls += reward["free_rolls"] * duplicates
            cards_to_burn.append((card, duplicates))
        
        if total_duplicates == 0:
            await query.edit_message_text(
                "❌ У вас нет дубликатов карт!\n\n"
                "💡 Сжигать можно только дубликаты.\n"
                "У каждой карты всегда остаётся минимум 1 копия."
            )
            return
        
        # ⭐ ФОРМИРУЕМ ТЕКСТ ⭐
        text = (
            f"🔥 **Сжечь ВСЕ дубликаты карт?**\n\n"
            f"📦 Дубликатов будет сожжено: **{total_duplicates}**\n"
            f"🛡 Уникальных карт останется: **{len(card_counts)}**\n\n"
            f"🎁 **Вы получите:**\n"
            f"💰 Бэт-коинов: {total_cents}\n"
            f"🔍 Бесплатных попыток: {total_rolls}\n"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Да, сжечь все дубликаты", callback_data="burn_all_execute")],
            [InlineKeyboardButton("❌ Отмена", callback_data="burn_menu")]
        ]
        
        # ⭐ Универсальная логика отправки ⭐
        try:
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception as e:
            error_str = str(e)
            if "There is no text" in error_str:
                try:
                    await query.message.delete()
                except:
                    pass
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            elif "Message is not modified" in error_str:
                return
            else:
                logger.error(f"Ошибка в burn_all_preview: {e}")
                await query.answer("❌ Произошла ошибка", show_alert=True)
                
    except Exception as e:
        logger.error(f"Ошибка в burn_all_preview: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


async def burn_all_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выполняет сжигание ВСЕХ дубликатов карт (оставляя 1 копию каждой)."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            await query.edit_message_text("❌ У вас нет карт для сжигания!")
            return
        
        # ⭐ ИСПРАВЛЕНИЕ: Считаем и сжигаем только дубликаты ⭐
        total_cents = 0
        total_rolls = 0
        cards_to_burn = []  # Список (card_id, duplicates_count)
        total_duplicates = 0
        burned_common = 0
        burned_rare = 0
        
        card_counts = Counter(user_data["cards"])
        
        for cid, count in card_counts.items():
            card = find_card_by_id(cid, data["cards"])
            if not card:
                continue
            
            # ⭐ Пропускаем карты без дубликатов ⭐
            if count <= 1:
                continue
            
            # ⭐ Сжигаем только дубликаты (count - 1) ⭐
            duplicates = count - 1
            total_duplicates += duplicates
            
            reward = BURN_REWARDS.get(card["rarity"], {"cents": 0, "free_rolls": 0})
            total_cents += reward["cents"] * duplicates
            total_rolls += reward["free_rolls"] * duplicates
            cards_to_burn.append((cid, duplicates))
            
            # Считаем для квестов
            if card["rarity"] == "Common":
                burned_common += duplicates
            elif card["rarity"] == "Rare":
                burned_rare += duplicates
        
        if total_duplicates == 0:
            await query.edit_message_text(
                "❌ У вас нет дубликатов карт!\n\n"
                "💡 Сжигать можно только дубликаты."
            )
            return
        
        # ⭐ УДАЛЯЕМ ДУБЛИКАТЫ КАРТ (оставляя 1 копию каждой) ⭐
        for card_id, duplicates_count in cards_to_burn:
            for _ in range(duplicates_count):
                if card_id in user_data["cards"]:
                    user_data["cards"].remove(card_id)
        
        # ⭐ ВЫДАЁМ НАГРАДУ ⭐
        user_data["cents"] = user_data.get("cents", 0) + total_cents
        user_data["free_rolls"] = user_data.get("free_rolls", 0) + total_rolls
        save_data(data)
        
        # ⭐ ТРИГГЕРЫ КВЕСТОВ ⭐
        if burned_common > 0:
            await update_quest_progress(context, user_id, "burn_common_3", burned_common)
        if burned_rare > 0:
            await update_weekly_quest_progress(context, user_id, "weekly_burn_rare_4", burned_rare)
        
        # ⭐ ФОРМИРУЕМ ТЕКСТ ⭐
        unique_cards_count = len(set(user_data["cards"]))
        
        text = (
            f"✅ **Сжигание успешно!** 🔥\n\n"
            f"🗑️ Сожжено дубликатов: **{total_duplicates}**\n"
            f"🛡 Уникальных карт осталось: **{unique_cards_count}**\n\n"
            f"🎁 **Награда получена:**\n"
            f"💰 +{total_cents} бэт-коинов\n"
            f"🔍 +{total_rolls} бесплатных попыток\n\n"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Назад в меню сжигания", callback_data="burn_menu")]]
        
        # ⭐ Универсальная логика отправки ⭐
        try:
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception as e:
            error_str = str(e)
            if "There is no text" in error_str:
                try:
                    await query.message.delete()
                except:
                    pass
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            elif "Message is not modified" in error_str:
                return
            else:
                logger.error(f"Ошибка в burn_all_execute: {e}")
                await query.answer("❌ Произошла ошибка", show_alert=True)
        
        logger.info(
            f"Игрок {user_id} сжёг {total_duplicates} дубликатов, "
            f"осталось {unique_cards_count} уникальных карт"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в burn_all_execute: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def burn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик всех callback кнопок сжигания."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)

        # ⭐ НОВОЕ: Отмена подтверждения ⭐
        if query.data == "burn_cancel_confirm":
            try:
                await query.message.delete()
            except:
                pass
            return
        
        # ⭐ НОВОЕ: Закрыть результат сжигания ⭐
        if query.data == "burn_close_result":
            try:
                await query.message.delete()
            except:
                pass
            return
        
        # Меню редкостей
        # ⭐ ОБРАБОТКА СЖИГАНИЯ ВСЕХ КАРТ ⭐
        if query.data == "burn_all_preview":
            await burn_all_preview(update, context)
            return
        if query.data == "burn_all_execute":
            await burn_all_execute(update, context)
            return
            
        if query.data == "burn_menu":
            await burn_menu(update, context)
            return
        
        # Выбор редкости
        if query.data.startswith("burn_rarity_"):
            rarity = query.data.replace("burn_rarity_", "")
            context.user_data.pop(f"burn_nav_msg_{user_id}", None)
            context.user_data.pop(f"burn_nav_rarity_{user_id}", None)
            context.user_data.pop(f"burn_nav_index_{user_id}", None)
            await show_burn_cards(update, context, rarity=rarity, start_index=0)
            return
        
        # Все карты
        if query.data == "burn_all":
            context.user_data.pop(f"burn_nav_msg_{user_id}", None)
            context.user_data.pop(f"burn_nav_rarity_{user_id}", None)
            context.user_data.pop(f"burn_nav_index_{user_id}", None)
            await show_burn_cards(update, context, rarity="all", start_index=0)
            return
        
        # Навигация: ПРЕДЫДУЩАЯ
        if query.data.startswith("burn_prev_"):
            parts = query.data.replace("burn_prev_", "").split("_")
            rarity = parts[0] if parts[0] != "all" else None
            index = int(parts[1])
            await show_burn_cards(update, context, rarity=rarity, start_index=index)
            return
        
        # Навигация: СЛЕДУЮЩАЯ
        if query.data.startswith("burn_next_"):
            parts = query.data.replace("burn_next_", "").split("_")
            rarity = parts[0] if parts[0] != "all" else None
            index = int(parts[1])
            await show_burn_cards(update, context, rarity=rarity, start_index=index)
            return
        
        # Инфо
        if query.data == "burn_info":
            await query.answer("📄 Используйте ◀️ и ▶️ для навигации", show_alert=False)
            return
        
        # Подтверждение сжигания
        if query.data.startswith("burn_confirm_"):
            card_id = int(query.data.replace("burn_confirm_", ""))
            await burn_confirm(update, context, card_id)
            return
        
        # Выполнение сжигания
        if query.data.startswith("burn_execute_"):
            card_id = int(query.data.replace("burn_execute_", ""))
            await burn_execute(update, context, card_id)
            return
        
        # Возврат к показу карты после отмены
        if query.data.startswith("burn_show_"):
            rarity = query.data.replace("burn_show_", "")
            await show_burn_cards(update, context, rarity=rarity if rarity != "None" else None, start_index=0)
            return
        
        # Назад в меню сжигания
        if query.data == "burn_back":
            # ⭐ НОВОЕ: Очищаем сохранённые данные навигации ⭐
            context.user_data.pop(f"burn_nav_msg_{user_id}", None)
            context.user_data.pop(f"burn_nav_rarity_{user_id}", None)
            context.user_data.pop(f"burn_nav_index_{user_id}", None)
            await burn_menu(update, context)
            return
            
    except Exception as e:
        logger.error(f"Ошибка в burn_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def darts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню и правила игры Дартс."""
    try:
        # ⭐ НОВОЕ: Получаем данные игрока ⭐
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id, {})
        current_balance = user_data.get("cents", 0)
        plays_today = user_data.get("darts_plays", 0)
        
        # ⭐ НОВОЕ: Индикаторы баланса ⭐
        if current_balance >= DARTS_GAME_COST:
            balance_text = f"💰 Ваш баланс: **{current_balance}** бэт-коинов ✅"
        else:
            balance_text = f"💰 Ваш баланс: **{current_balance}** бэт-коинов ❌ _(недостаточно)_"
        
        keyboard = [[InlineKeyboardButton("🎯 Сыграть", callback_data="darts_play")]]
        caption = (
            f"🎯 **Мини-игра «Дартс»**\n"
            f"📜 **Правила:**\n"
            f"• Стоимость игры: {DARTS_GAME_COST} бэт-коинов\n"
            f"• Бот бросает 3 дротика 🎯\n"
            f"• Мишень имеет 5 зон: от 1 до 5 очков\n"
            f"• Наберите {DARTS_WIN_THRESHOLD}+ очков за 3 броска, чтобы получить 5 бесплатных попыток 🎲\n"
            f"• Лимит: {MAX_DARTS_DAILY_PLAYS} игр в день (сброс в 00:00 МСК)\n\n"
            f"{balance_text}\n"
        )
        
        if hasattr(update, 'callback_query') and update.callback_query:
            try:
                await update.callback_query.message.delete()
            except:
                pass
            await context.bot.send_message(
                chat_id=update.callback_query.message.chat_id,
                text=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                text=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Ошибка в darts_menu: {e}")
        await update.message.reply_text("❌ Ошибка при открытии меню Дартс")

async def darts_play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Логика игры в Дартс."""
    try:
        query = update.callback_query
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        if not user_data:
            await query.edit_message_text("❌ Вы ещё не начали игру!")
            return

        # Сброс дневного лимита в 00:00 МСК
        msk_tz = datetime.timezone(datetime.timedelta(hours=3))
        now_msk = datetime.datetime.now(msk_tz)
        last_reset = user_data.get("darts_last_reset", 0)
        if last_reset == 0 or now_msk.day != datetime.datetime.fromtimestamp(last_reset, msk_tz).day:
            user_data["darts_plays"] = 0
            user_data["darts_last_reset"] = int(now_msk.timestamp())

        is_admin_user = is_admin(user_id, data)
        if not is_admin_user and user_data.get("darts_plays", 0) >= MAX_DARTS_DAILY_PLAYS:
            await query.edit_message_text("❌ Лимит игр на сегодня исчерпан! Приходите завтра после 00:00 МСК.")
            return

        if not is_admin_user and user_data.get("cents", 0) < DARTS_GAME_COST:
            await query.edit_message_text(f"❌ Недостаточно бэт-коинов! Нужно {DARTS_GAME_COST}. У вас: {user_data.get('cents', 0)}")
            return

        # Списание средств и учёт игры
        if not is_admin_user:
            user_data["cents"] -= DARTS_GAME_COST
            user_data["darts_plays"] += 1
        save_data(data)

        await query.edit_message_text("🎯 Бросаем дротики...")
        total_points = 0
        results = []

        for _ in range(3):
            await asyncio.sleep(1.5)
            dice_msg = await context.bot.send_dice(chat_id=query.message.chat_id, emoji="🎯")
            # Telegram 🎯 выдаёт 1-6. Адаптируем под 5 зон мишени (6 -> 5)
            points = min(dice_msg.dice.value, 6)
            points -= 1
            total_points += points
            results.append(points)

        win = total_points >= DARTS_WIN_THRESHOLD
        if win:
            user_data["free_rolls"] = user_data.get("free_rolls", 0) + 5
            save_data(data)
            await update_quest_progress(context, user_id, "darts_win_2", 1)

        await query.message.reply_text(
            f"🎯 **Результаты бросков:** {', '.join(map(str, results))}\n"
            f"📊 **Итого очков:** {total_points}/10\n"
            f"{'✅ Победа! Получено 5 бесплатных попыток 🎲' if win else '😔 Не хватило очков. Попробуйте ещё раз.'}",
            parse_mode="Markdown"
        )

        # Возвращаем меню
        keyboard = [[InlineKeyboardButton("🎯 Сыграть ещё", callback_data="darts_play")]]
        await query.message.reply_text(
            "🎯 **Дартс**\nХотите сыграть ещё раз?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в darts_play: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def darts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок игры Дартс."""
    try:
        query = update.callback_query
        await query.answer()
        if query.data == "darts_play":
            await darts_play(update, context)
    except Exception as e:
        logger.error(f"Ошибка в darts_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def top_clans(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает топ-10 кланов по очкам репутации (без учёта админов)."""
    try:
        data = load_data()
        clans = data.get("clans", {})
        users = data.get("users", {})
        admins = set(data.get("admins", []))  # ⭐ НОВОЕ: множество ID админов
        
        if not clans:
            await update.message.reply_text("📭 Пока нет созданных кланов!")
            return
        
        clan_scores = []
        for clan_id, clan_data in clans.items():
            total_rep = 0
            member_count = len(clan_data.get("members", {}))
            
            # Суммируем total_points всех участников КРОМЕ админов
            for member_id in clan_data.get("members", {}):
                # ⭐ НОВОЕ: Пропускаем администраторов ⭐
                if member_id in admins:
                    continue
                
                user_data = users.get(member_id, {})
                total_rep += user_data.get("total_points", 0)
            
            clan_scores.append({
                "id": clan_id,
                "name": clan_data.get("name", "Без названия"),
                "reputation": total_rep,
                "members": member_count
            })
        
        # Сортировка по репутации (по убыванию)
        clan_scores.sort(key=lambda x: x["reputation"], reverse=True)
        top_10 = clan_scores[:10]
        
        message_text = "🏆 **Топ кланов по репутации**\n"
        message_text += "_⚙️ Очки администраторов не учитываются_\n\n"
        
        for rank, clan in enumerate(top_10, 1):
            if rank == 1:
                medal = "🥇"
            elif rank == 2:
                medal = "🥈"
            elif rank == 3:
                medal = "🥉"
            else:
                medal = f"{rank}."
            
            message_text += f"{medal} **{clan['name']}**\n"
            message_text += f" 👥 Участников: {clan['members']}\n"
            message_text += f" 💎 Репутация: {clan['reputation']}\n\n"
        
        # ⭐ ПОКАЗЫВАЕМ МЕСТО КЛАНА ПОЛЬЗОВАТЕЛЯ ⭐
        user_id = str(update.effective_user.id)
        user_clan_id = data.get("user_clan", {}).get(user_id)
        
        if user_clan_id:
            user_clan_rank = None
            for rank, clan in enumerate(clan_scores, 1):
                if clan["id"] == user_clan_id:
                    user_clan_rank = rank
                    break
            
            if not user_clan_rank:
                user_clan_rank = len(clan_scores) + 1
            
            message_text += "─" * 30 + "\n"
            if user_clan_rank <= 10:
                message_text += f"✅ **Ваш клан в топе! Место: {user_clan_rank}**\n"
            else:
                message_text += f"📍 **Ваш клан вне топ-10. Место: {user_clan_rank}**\n"
            
            current_clan_data = next((c for c in clan_scores if c["id"] == user_clan_id), None)
            if current_clan_data:
                message_text += f"💎 Репутация вашего клана: {current_clan_data['reputation']}"
        
        await update.message.reply_text(message_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка в top_clans: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке топа кланов")

async def submenu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает подменю."""
    try:
        keyboard = [
            [KeyboardButton("👤 Личное дело")],
            [KeyboardButton("📜 Квесты"), KeyboardButton("🏰 Кланы")],
            [KeyboardButton("🛍️ Магазин"), KeyboardButton("🍺 Бар")],
            [KeyboardButton("🔙 Назад в главное меню")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # ⭐ ОТПРАВКА С КАРТИНКОЙ ⭐
        await update.message.reply_photo(
            photo=MENU_IMAGE,
            caption="📋 Меню\nВыберите раздел:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Ошибка в submenu: {e}")

async def archive_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню 'Мой архив'."""
    try:
        keyboard = [
            [KeyboardButton("🔨 Крафт")],
            [KeyboardButton("📊 Просмотр архива")],
            [KeyboardButton("🔙 Назад в главное меню")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "📁 Мой архив\nВыберите действие:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Ошибка в archive_menu: {e}")

def get_random_available_card_by_rarity(data: Dict, rarity: str) -> Optional[Dict]:
    """Возвращает случайную доступную карту указанной редкости."""
    available_cards = [
        c for c in data.get("cards", []) 
        if c.get("rarity") == rarity and c.get("available", True)
    ]
    if available_cards:
        return random.choice(available_cards)
    return None

async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Меню реферальной системы."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id, {})
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        
        invites = user_data.get("referral_invites", [])
        count = len(invites)
        claimed = user_data.get("referral_rewards_claimed", [])
        
        # ⭐ Формируем список приглашенных с экранированием ⭐
        if invites:
            lines = []
            for i, inv_id in enumerate(invites, 1):
                inv_data = data["users"].get(inv_id, {})
                inv_name = inv_data.get("username") or inv_data.get("first_name") or f"ID: {inv_id}"
                inv_name_escaped = escape_markdown(inv_name)
                lines.append(f"{i}. {inv_name_escaped}\n")
            invite_list_text = "".join(lines)
        else:
            invite_list_text = "Список пуст\n"
        
        # ⭐ Статусы наград ⭐
        reward_1 = "✅ Получено" if 1 in claimed else ("🎁 **ДОСТУПНО!**" if count >= 1 else "🔒 За 1 приглашение")
        reward_3 = "✅ Получено" if 3 in claimed else ("🎁 **ДОСТУПНО!**" if count >= 3 else "🔒 За 3 приглашения")
        
        # ⭐ ИСПРАВЛЕНИЕ: Используем Markdown-ссылку вместо экранирования ⭐
        # Формат [текст](URL) не требует экранирования URL
        ref_link_markdown = f"[Нажмите, чтобы скопировать]({ref_link})"
        
        text = (
            f"🔗 **Реферальная система**\n\n"
            f"Приглашайте друзей и получайте ценные награды!\n\n"
            f"📎 **Ваша уникальная ссылка:**\n"
            f"{ref_link_markdown}\n"
            f"👤 Или вручную: `{ref_link}`\n\n"
            f"👥 **Всего приглашено:** {count}\n\n"
            f"📋 **Список приглашенных:**\n"
            f"{invite_list_text}\n"
            f"🎁 **Награды:**\n"
            f"1️⃣ 1 приглашение: Случайная карта редкости **Epic**\n"
            f"   Статус: {reward_1}\n\n"
            f"3️⃣ 3 приглашения: Случайная карта редкости **Epic Team-up**\n"
            f"   Статус: {reward_3}\n\n"
            f"💡 _Награды выдаются автоматически в момент приглашения нового игрока!_"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Назад в Личное дело", callback_data="my_profile")]]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Ошибка в referral_menu: {e}")

# ===== ЕЖЕДНЕВНЫЕ КВЕСТЫ =====
DAILY_QUESTS_POOL = [
    {"id": "common_4", "desc": "Получить 4 карты редкости Common через «Получить досье»", "reward_type": "cents", "reward_amount": 500, "target": 4},
    {"id": "darts_win_2", "desc": "Победить в дартсе 2 раза", "reward_type": "free_rolls", "reward_amount": 1, "target": 2},
    {"id": "burn_common_3", "desc": "Сжечь 3 карты редкости Common", "reward_type": "free_rolls", "reward_amount": 1, "target": 3},
    {"id": "trade_2", "desc": "Совершить 2 трейда", "reward_type": "cents", "reward_amount": 250, "target": 2},
    {"id": "basket_3", "desc": "Сыграть в баскет 3 раза", "reward_type": "cents", "reward_amount": 500, "target": 3},
]

def check_daily_quests_reset(user_data: Dict) -> None:
    """Проверяет и сбрасывает ежедневные квесты в 00:00 МСК."""
    msk_tz = datetime.timezone(datetime.timedelta(hours=3))
    now_msk = datetime.datetime.now(msk_tz)
    
    last_reset = user_data.get("daily_quests_last_reset", 0)
    last_reset_dt = datetime.datetime.fromtimestamp(last_reset, msk_tz) if last_reset else None
    
    # Если сегодня ещё не сбрасывали
    if not last_reset_dt or now_msk.date() != last_reset_dt.date():
        # Выбираем 3 случайных квеста
        selected = random.sample(DAILY_QUESTS_POOL, 3)
        user_data["daily_quests"] = []
        for q in selected:
            user_data["daily_quests"].append({
                "id": q["id"],
                "desc": q["desc"],
                "reward_type": q["reward_type"],
                "reward_amount": q["reward_amount"],
                "target": q["target"],
                "progress": 0,
                "completed": False,
                "claimed": False
            })
        user_data["daily_quests_last_reset"] = int(now_msk.timestamp())


async def notify_quest_completed(context: ContextTypes.DEFAULT_TYPE, chat_id: int, quest: Dict) -> None:
    """Отправляет отдельное уведомление о выполнении квеста."""
    reward_text = ""
    if quest["reward_type"] == "cents":
        reward_text = f"{quest['reward_amount']} Бэт-коинов 💰"
    elif quest["reward_type"] == "free_rolls":
        reward_text = f"{quest['reward_amount']} бесплатная попытка 🔍"
    
    text = (
        f"✅ <b>Выполнен квест!</b>\n\n"
        f"📋 {quest['desc']}\n"
        f"🎁 Ваша награда: {reward_text}"
    )
    try:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о квесте: {e}")


async def update_quest_progress(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: str,
    quest_id: str,
    amount: int = 1
) -> None:
    """
    Обновляет прогресс квеста. Вызывается из игровых функций.
    ⚡ ВАЖНО: Добавляйте вызов этой функции в соответствующие места:
    - handle_message() при получении карты Common → update_quest_progress(..., "common_4", 1)
    - darts_play() при победе → update_quest_progress(..., "darts_win_2", 1)
    - burn_execute() при сжигании карты Common → update_quest_progress(..., "burn_common_3", 1)
    - trade_final_callback() при успешном трейде → update_quest_progress(..., "trade_2", 1)
    - basket_play() при любой игре → update_quest_progress(..., "basket_3", 1)
    """
    data = load_data()
    user_data = data["users"].get(user_id)
    if not user_data:
        return
    
    check_daily_quests_reset(user_data)
    
    quests = user_data.get("daily_quests", [])
    changed = False
    
    for quest in quests:
        if quest["id"] == quest_id and not quest["completed"]:
            quest["progress"] = min(quest["progress"] + amount, quest["target"])
            if quest["progress"] >= quest["target"]:
                quest["completed"] = True
                # Выдаём награду
                if quest["reward_type"] == "cents":
                    user_data["cents"] = user_data.get("cents", 0) + quest["reward_amount"]
                elif quest["reward_type"] == "free_rolls":
                    user_data["free_rolls"] = user_data.get("free_rolls", 0) + quest["reward_amount"]
                
                changed = True
                save_data(data)
                
                # Отправляем уведомление
                await notify_quest_completed(context, int(user_id), quest)
                logger.info(f"Игрок {user_id} выполнил квест {quest_id}")
            else:
                changed = True
    
    if changed and not any(q["id"] == quest_id and q["completed"] for q in quests):
        save_data(data)

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ СЕЗОННЫХ КВЕСТОВ =====

def init_seasonal_quests(user_data: Dict) -> None:
    """Инициализирует структуру сезонных квестов."""
    if "seasonal_quests" not in user_data:
        user_data["seasonal_quests"] = {"completed": [], "progress": {}}


def get_current_seasonal_quest_id(sq: Dict) -> Optional[int]:
    """Возвращает ID текущего активного квеста или None (если все выполнены)."""
    for quest_id in range(1, 13):
        if quest_id not in sq.get("completed", []):
            return quest_id
    return None


def get_current_seasonal_quest(user_data: Dict) -> Optional[Dict]:
    """Возвращает данные текущего активного квеста или None."""
    init_seasonal_quests(user_data)
    sq = user_data["seasonal_quests"]
    quest_id = get_current_seasonal_quest_id(sq)
    if quest_id is None:
        return None
    return SEASONAL_QUESTS[quest_id]


def update_seasonal_progress(user_data: Dict, quest_id: int, amount: int = 1) -> None:
    """Обновляет прогресс сезонного квеста."""
    init_seasonal_quests(user_data)
    sq = user_data["seasonal_quests"]
    
    # Если квест уже выполнен (награда забрана) — ничего не делаем
    if quest_id in sq["completed"]:
        return
    
    # Если это не текущий квест — ничего не делаем
    current_id = get_current_seasonal_quest_id(sq)
    if current_id != quest_id:
        return
    
    quest = SEASONAL_QUESTS[quest_id]
    quest_id_str = str(quest_id)
    current_progress = sq["progress"].get(quest_id_str, 0)
    new_progress = min(current_progress + amount, quest["target"])
    sq["progress"][quest_id_str] = new_progress


def update_seasonal_on_card_get(user_data: Dict, rarity: str) -> None:
    """Обновляет сезонные квесты при получении карты через «Получить досье»."""
    current_quest = get_current_seasonal_quest(user_data)
    if not current_quest:
        return
    if current_quest["type"] == "get_cards" and current_quest.get("rarity") == rarity:
        update_seasonal_progress(user_data, current_quest["id"], 1)


def update_seasonal_on_burn(user_data: Dict, rarity: str) -> None:
    """Обновляет сезонные квесты при сжигании карты."""
    current_quest = get_current_seasonal_quest(user_data)
    if not current_quest:
        return
    if current_quest["type"] == "burn_cards" and current_quest.get("rarity") == rarity:
        update_seasonal_progress(user_data, current_quest["id"], 1)


def update_seasonal_on_box_buy(user_data: Dict, box_type: str) -> None:
    """Обновляет сезонные квесты при покупке бокса. box_type: 'rolls' или 'classic'."""
    current_quest = get_current_seasonal_quest(user_data)
    if not current_quest:
        return
    if current_quest["type"] == "buy_box" and current_quest.get("box") == box_type:
        update_seasonal_progress(user_data, current_quest["id"], 1)


def claim_seasonal_reward(user_data: Dict, quest_id: int) -> bool:
    """Выдаёт награду за сезонный квест. Возвращает True, если успешно."""
    init_seasonal_quests(user_data)
    sq = user_data["seasonal_quests"]
    
    if quest_id in sq["completed"]:
        return False
    
    quest = SEASONAL_QUESTS.get(quest_id)
    if not quest:
        return False
    
    quest_id_str = str(quest_id)
    if sq["progress"].get(quest_id_str, 0) < quest["target"]:
        return False
    
    # Выдаём награду
    reward = quest["reward"]
    if "cents" in reward:
        user_data["cents"] = user_data.get("cents", 0) + reward["cents"]
    if "rep_points" in reward:
        user_data["season_points"] = user_data.get("season_points", 0) + reward["rep_points"]
        user_data["total_points"] = user_data.get("total_points", 0) + reward["rep_points"]
    if "free_rolls" in reward:
        user_data["free_rolls"] = user_data.get("free_rolls", 0) + reward["free_rolls"]
    if "avatar" in reward:
        avatar_url = reward["avatar"]
        avatars = user_data.setdefault("avatars", [])
        if avatar_url not in avatars:
            avatars.append(avatar_url)
    
    sq["completed"].append(quest_id)
    return True


def check_clan_quest(user_id: str, data: Dict) -> bool:
    """Проверяет выполнение квеста 5 (вступление в клан)."""
    return bool(get_user_clan(user_id, data))


def check_seasonal_cards_quest(user_data: Dict, data: Dict) -> bool:
    """Проверяет выполнение квеста 8 (все сезонные карты)."""
    seasonal_ids = set(int(k) for k in data.get("seasonal_cards", {}).keys())
    if not seasonal_ids:
        return False
    user_cards = set(user_data.get("cards", []))
    return seasonal_ids.issubset(user_cards)


def format_seasonal_reward(reward: Dict) -> str:
    """Форматирует награду квеста в читаемый вид."""
    parts = []
    if "cents" in reward:
        parts.append(f"{reward['cents']} бэт-коинов 💰")
    if "rep_points" in reward:
        parts.append(f"{reward['rep_points']} очков репутации 💥")
    if "free_rolls" in reward:
        parts.append(f"{reward['free_rolls']} бесплатных попыток 🔍")
    if "avatar" in reward:
        parts.append("Сезонная аватарка 🖼")
    return " | ".join(parts) if parts else "—"

async def quests_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню квестов с тремя разделами."""
    keyboard = [
        [InlineKeyboardButton("📅 Ежедневные", callback_data="quests_daily")],
        [InlineKeyboardButton("📆 Еженедельные", callback_data="quests_weekly")],
        [InlineKeyboardButton("🏆 Сезонные", callback_data="quests_seasonal")],
        [InlineKeyboardButton("🔙 Назад", callback_data="quests_back")]
    ]
    text = (
        "📜 <b>Квесты</b>\n"
        "Выберите раздел:\n"
        "• 📅 <b>Ежедневные</b> — обновляются каждый день в 00:00 МСК\n"
        "• 📆 <b>Еженедельные</b> — обновляются каждый понедельник в 00:00 МСК\n"
        "• 🏆 <b>Сезонные</b> — обновляются каждый сезон"
    )
    
    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query
        try:
            await query.message.delete()
        except:
            pass
        # ⭐ ОТПРАВКА С КАРТИНКОЙ ⭐
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=QUESTS_IMAGE,
            caption=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    else:
        # ⭐ ОТПРАВКА С КАРТИНКОЙ ⭐
        await update.message.reply_photo(
            photo=QUESTS_IMAGE,
            caption=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

async def quests_seasonal_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает текущий сезонный квест."""
    try:
        query = update.callback_query if hasattr(update, 'callback_query') and update.callback_query else None
        user_id = str(query.from_user.id if query else update.effective_user.id)
        chat_id = query.message.chat_id if query else update.effective_chat.id
        
        data = load_data()
        user_data = data["users"].get(user_id)
        if not user_data:
            text = "❌ Вы ещё не начали игру!"
            keyboard = [[InlineKeyboardButton("🔙 Назад к квестам", callback_data="quests_menu")]]
            if query:
                await query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return
        
        init_seasonal_quests(user_data)
        save_data(data)
        
        sq = user_data["seasonal_quests"]
        current_quest_id = get_current_seasonal_quest_id(sq)
        
        if current_quest_id is None:
            # Все квесты выполнены
            text = (
                "🎉 <b>Поздравляю!</b>\n\n"
                "Вы выполнили все сезонные квесты!\n"
                "Ждите следующего сезона!"
            )
            keyboard = [[InlineKeyboardButton("🔙 Назад к квестам", callback_data="quests_menu")]]
        else:
            quest = SEASONAL_QUESTS[current_quest_id]
            quest_id_str = str(current_quest_id)
            progress = sq["progress"].get(quest_id_str, 0)
            target = quest["target"]
            reward_text = format_seasonal_reward(quest["reward"])
            is_completed = progress >= target
            
            # Специальный случай: квест 8 — показываем прогресс по сезонным картам
            extra_info = ""
            if quest["type"] == "seasonal_cards":
                seasonal_ids = set(int(k) for k in data.get("seasonal_cards", {}).keys())
                user_cards = set(user_data.get("cards", []))
                owned = len(seasonal_ids.intersection(user_cards))
                total = len(seasonal_ids)
                extra_info = f"\n📊 Карт в магазине: {owned}/{total}"
            
            if quest.get("check_button"):
                # Квест с кнопкой "Проверить"
                text = (
                    f"🏆 <b>Сезонный квест {current_quest_id}/12</b>\n\n"
                    f"📋 {quest['desc']}{extra_info}\n\n"
                    f"🎁 Награда: {reward_text}"
                )
                if is_completed:
                    text += "\n\n✅ <b>Условие выполнено!</b>"
                    keyboard = [
                        [InlineKeyboardButton("🎁 Забрать награду", callback_data=f"sq_claim_{current_quest_id}")],
                        [InlineKeyboardButton("🔙 Назад к квестам", callback_data="quests_menu")]
                    ]
                else:
                    keyboard = [
                        [InlineKeyboardButton("🔍 Проверить", callback_data=f"sq_check_{current_quest_id}")],
                        [InlineKeyboardButton("🔙 Назад к квестам", callback_data="quests_menu")]
                    ]
            else:
                # Обычный квест с прогресс-баром
                progress_bar_len = 10
                filled = int((progress / target) * progress_bar_len) if target > 0 else 0
                bar = "█" * filled + "░" * (progress_bar_len - filled)
                
                text = (
                    f"🏆 <b>Сезонный квест {current_quest_id}/12</b>\n\n"
                    f"📋 {quest['desc']}\n"
                    f"📊 Прогресс: [{bar}] {progress}/{target}\n\n"
                    f"🎁 Награда: {reward_text}"
                )
                
                if is_completed:
                    text += "\n\n✅ <b>Выполнено!</b>"
                    keyboard = [
                        [InlineKeyboardButton("🎁 Забрать награду", callback_data=f"sq_claim_{current_quest_id}")],
                        [InlineKeyboardButton("🔙 Назад к квестам", callback_data="quests_menu")]
                    ]
                else:
                    keyboard = [[InlineKeyboardButton("🔙 Назад к квестам", callback_data="quests_menu")]]
        
        if query:
            try:
                await query.message.delete()
            except:
                pass
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Ошибка в quests_seasonal_view: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Произошла ошибка", show_alert=True) 

async def seasonal_quest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок сезонных квестов (Проверить / Забрать награду)."""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data:
            await query.answer("❌ Профиль не найден", show_alert=True)
            return
        
        init_seasonal_quests(user_data)
        
        # ⭐ Кнопка "Проверить" ⭐
        if query.data.startswith("sq_check_"):
            quest_id = int(query.data.replace("sq_check_", ""))
            quest = SEASONAL_QUESTS.get(quest_id)
            
            if not quest:
                await query.answer("❌ Квест не найден", show_alert=True)
                return
            
            # Проверяем условие
            completed = False
            if quest["type"] == "clan":
                completed = check_clan_quest(user_id, data)
            elif quest["type"] == "seasonal_cards":
                completed = check_seasonal_cards_quest(user_data, data)
            
            if completed:
                # Устанавливаем прогресс = target
                user_data["seasonal_quests"]["progress"][str(quest_id)] = quest["target"]
                save_data(data)
                await query.answer("✅ Условие выполнено! Заберите награду.", show_alert=True)
            else:
                await query.answer("❌ Условие ещё не выполнено", show_alert=True)
                return
            
            # Показываем обновлённый квест
            await quests_seasonal_view(update, context)
            return
        
        # ⭐ Кнопка "Забрать награду" ⭐
        if query.data.startswith("sq_claim_"):
            quest_id = int(query.data.replace("sq_claim_", ""))
            quest = SEASONAL_QUESTS.get(quest_id)
            
            if not quest:
                await query.answer("❌ Квест не найден", show_alert=True)
                return
            
            success = claim_seasonal_reward(user_data, quest_id)
            if not success:
                await query.answer("❌ Нельзя забрать награду", show_alert=True)
                return
            
            save_data(data)
            
            # Формируем сообщение о награде
            reward_text = format_seasonal_reward(quest["reward"])
            
            await query.answer("🎁 Награда получена!", show_alert=True)
            
            try:
                await query.message.delete()
            except:
                pass
            
            # Проверяем, есть ли ещё квесты
            next_quest_id = get_current_seasonal_quest_id(user_data["seasonal_quests"])
            
            if next_quest_id is None:
                # Все квесты выполнены
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=(
                        f"🎉 <b>Сезонный квест #{quest_id} выполнен!</b>\n\n"
                        f"🎁 Награда:\n{reward_text}\n\n"
                        f"🏆 <b>Поздравляю! Вы выполнили все сезонные квесты!</b>\n"
                        f"Ждите следующего сезона!"
                    ),
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад к квестам", callback_data="quests_menu")
                    ]]),
                    parse_mode="HTML"
                )
            else:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=(
                        f"🎉 <b>Сезонный квест #{quest_id} выполнен!</b>\n\n"
                        f"🎁 Награда:\n{reward_text}\n\n"
                        f"Открыт следующий квест!"
                    ),
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🏆 Следующий квест", callback_data="quests_seasonal")
                    ]]),
                    parse_mode="HTML"
                )
            return
    except Exception as e:
        logger.error(f"Ошибка в seasonal_quest_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def quests_daily_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список активных ежедневных квестов."""
    query = update.callback_query if hasattr(update, 'callback_query') else None
    user_id = str(query.from_user.id if query else update.effective_user.id)
    chat_id = query.message.chat_id if query else update.effective_chat.id
    
    data = load_data()
    user_data = data["users"].get(user_id)
    if not user_data:
        text = "❌ Вы ещё не начали игру!"
        if query:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return
    
    check_daily_quests_reset(user_data)
    save_data(data)
    
    quests = user_data.get("daily_quests", [])
    
    # Определяем время до следующего сброса
    msk_tz = datetime.timezone(datetime.timedelta(hours=3))
    now_msk = datetime.datetime.now(msk_tz)
    tomorrow = (now_msk + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    remaining = int((tomorrow - now_msk).total_seconds())
    hours = remaining // 3600
    minutes = (remaining % 3600) // 60
    
    text = f"📅 <b>Ежедневные квесты</b>\n⏳ Обновление через: {hours}ч {minutes}мин\n\n"
    
    for quest in quests:
        status_icon = "✅" if quest["completed"] else "⬜"
        progress_bar_len = 10
        filled = int((quest["progress"] / quest["target"]) * progress_bar_len) if quest["target"] > 0 else 0
        bar = "█" * filled + "░" * (progress_bar_len - filled)
        
        reward_text = ""
        if quest["reward_type"] == "cents":
            reward_text = f"{quest['reward_amount']} 💰"
        elif quest["reward_type"] == "free_rolls":
            reward_text = f"{quest['reward_amount']} 🔍"
        
        text += (
            f"{status_icon} {quest['desc']}\n"
            f"   [{bar}] {quest['progress']}/{quest['target']}\n"
            f"   🎁 Награда: {reward_text}\n\n"
        )
    
    keyboard = [[InlineKeyboardButton("🔙 Назад к квестам", callback_data="quests_menu")]]
    
    if query:
        try:
            await query.message.delete()
        except:
            pass
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )


async def quests_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок квестов."""
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "quests_menu":
            await quests_menu(update, context)
        elif query.data == "quests_daily":
            await quests_daily_view(update, context)
        elif query.data == "quests_weekly":
            await quests_weekly_view(update, context)
        elif query.data == "quests_seasonal":
            await quests_seasonal_view(update, context)
        elif query.data == "quests_back":
            await query.message.delete()
            await submenu(update, context)
    except Exception as e:
        logger.error(f"Ошибка в quests_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

# ===== КОНЕЦ БЛОКА ЕЖЕДНЕВНЫХ КВЕСТОВ =====

# ===== ЕЖЕНЕДЕЛЬНЫЕ КВЕСТЫ =====

WEEKLY_QUESTS_POOL = [
    {
        "id": "weekly_casino_win",
        "desc": "Выиграть в казино",
        "reward_type": "rep_points",
        "reward_amount": 1000,
        "target": 1
    },
    {
        "id": "weekly_craft_3",
        "desc": "Сделать 3 крафта",
        "reward_type": "free_rolls",
        "reward_amount": 5,
        "target": 3
    },
    {
        "id": "weekly_rare_6",
        "desc": "Получить 6 карт редкости Rare через «Получить досье»",
        "reward_type": "cents",
        "reward_amount": 500,
        "target": 6
    },
    {
        "id": "weekly_burn_rare_4",
        "desc": "Сжечь 4 карты редкости Rare",
        "reward_type": "free_rolls",
        "reward_amount": 2,
        "target": 4
    },
    {
        "id": "weekly_epic_tu_1",
        "desc": "Получить карту редкости Epic Team-up через «Получить досье»",
        "reward_type": "cents",
        "reward_amount": 1000,
        "target": 1
    },
]


def check_weekly_quests_reset(user_data: Dict) -> None:
    """Проверяет и сбрасывает еженедельные квесты в понедельник 00:00 МСК."""
    msk_tz = datetime.timezone(datetime.timedelta(hours=3))
    now_msk = datetime.datetime.now(msk_tz)
    
    current_year, current_week, _ = now_msk.isocalendar()
    
    last_year = user_data.get("weekly_quests_last_reset_year", 0)
    last_week = user_data.get("weekly_quests_last_reset_week", 0)
    
    # Если год или неделя изменились — сбрасываем
    if last_year == 0 or current_year != last_year or current_week != last_week:
        # ⭐ Показываем ВСЕ 5 еженедельных квестов (без случайного выбора) ⭐
        user_data["weekly_quests"] = []
        for q in WEEKLY_QUESTS_POOL:
            user_data["weekly_quests"].append({
                "id": q["id"],
                "desc": q["desc"],
                "reward_type": q["reward_type"],
                "reward_amount": q["reward_amount"],
                "target": q["target"],
                "progress": 0,
                "completed": False,
                "claimed": False
            })
        
        user_data["weekly_quests_last_reset_year"] = current_year
        user_data["weekly_quests_last_reset_week"] = current_week


async def update_weekly_quest_progress(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: str,
    quest_id: str,
    amount: int = 1
) -> None:
    """Обновляет прогресс еженедельного квеста."""
    data = load_data()
    user_data = data["users"].get(user_id)
    if not user_data:
        return
    
    check_weekly_quests_reset(user_data)
    
    quests = user_data.get("weekly_quests", [])
    changed = False
    
    for quest in quests:
        if quest["id"] == quest_id and not quest["completed"]:
            quest["progress"] = min(quest["progress"] + amount, quest["target"])
            if quest["progress"] >= quest["target"]:
                quest["completed"] = True
                # Выдаём награду
                if quest["reward_type"] == "cents":
                    user_data["cents"] = user_data.get("cents", 0) + quest["reward_amount"]
                elif quest["reward_type"] == "free_rolls":
                    user_data["free_rolls"] = user_data.get("free_rolls", 0) + quest["reward_amount"]
                elif quest["reward_type"] == "rep_points":
                    user_data["season_points"] = user_data.get("season_points", 0) + quest["reward_amount"]
                    user_data["total_points"] = user_data.get("total_points", 0) + quest["reward_amount"]
                
                changed = True
                save_data(data)
                
                # Отправляем уведомление
                reward_text = ""
                if quest["reward_type"] == "cents":
                    reward_text = f"{quest['reward_amount']} Бэт-коинов 💰"
                elif quest["reward_type"] == "free_rolls":
                    reward_text = f"{quest['reward_amount']} бесплатных попыток 🔍"
                elif quest["reward_type"] == "rep_points":
                    reward_text = f"{quest['reward_amount']} очков репутации 💥"
                
                text = (
                    f"✅ <b>Выполнен еженедельный квест!</b>\n\n"
                    f"📋 {quest['desc']}\n"
                    f"🎁 Ваша награда: {reward_text}"
                )
                try:
                    await context.bot.send_message(chat_id=int(user_id), text=text, parse_mode="HTML")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления о недельном квесте: {e}")
                
                logger.info(f"Игрок {user_id} выполнил недельный квест {quest_id}")
            else:
                changed = True
    
    if changed and not any(q["id"] == quest_id and q["completed"] for q in quests):
        save_data(data)

async def quests_weekly_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список активных еженедельных квестов."""
    query = update.callback_query if hasattr(update, 'callback_query') else None
    user_id = str(query.from_user.id if query else update.effective_user.id)
    chat_id = query.message.chat_id if query else update.effective_chat.id
    
    data = load_data()
    user_data = data["users"].get(user_id)
    if not user_data:
        text = "❌ Вы ещё не начали игру!"
        if query:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return
    
    check_weekly_quests_reset(user_data)
    save_data(data)
    
    quests = user_data.get("weekly_quests", [])
    
    # Определяем время до следующего понедельника
    msk_tz = datetime.timezone(datetime.timedelta(hours=3))
    now_msk = datetime.datetime.now(msk_tz)
    days_until_monday = (7 - now_msk.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = now_msk.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=days_until_monday)
    remaining = int((next_monday - now_msk).total_seconds())
    days = remaining // 86400
    hours = (remaining % 86400) // 3600
    minutes = (remaining % 3600) // 60
    
    text = (
        f"📆 <b>Еженедельные квесты</b>\n"
        f"⏳ Обновление через: {days}д {hours}ч {minutes}мин\n\n"
    )
    
    for quest in quests:
        status_icon = "✅" if quest["completed"] else "⬜"
        progress_bar_len = 10
        filled = int((quest["progress"] / quest["target"]) * progress_bar_len) if quest["target"] > 0 else 0
        bar = "█" * filled + "░" * (progress_bar_len - filled)
        
        reward_text = ""
        if quest["reward_type"] == "cents":
            reward_text = f"{quest['reward_amount']} 💰"
        elif quest["reward_type"] == "free_rolls":
            reward_text = f"{quest['reward_amount']} 🔍"
        elif quest["reward_type"] == "rep_points":
            reward_text = f"{quest['reward_amount']} 💥"
        
        text += (
            f"{status_icon} {quest['desc']}\n"
            f"   [{bar}] {quest['progress']}/{quest['target']}\n"
            f"   🎁 Награда: {reward_text}\n\n"
        )
    
    keyboard = [[InlineKeyboardButton("🔙 Назад к квестам", callback_data="quests_menu")]]
    
    if query:
        try:
            await query.message.delete()
        except:
            pass
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

async def reset_weekly_quests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Принудительно сбрасывает еженедельные квесты у всех пользователей."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        
        if not is_admin(user_id, data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        reset_count = 0
        for uid, udata in data["users"].items():
            if "weekly_quests" in udata:
                udata["weekly_quests"] = []
            if "weekly_quests_last_reset_year" in udata:
                udata["weekly_quests_last_reset_year"] = 0
            if "weekly_quests_last_reset_week" in udata:
                udata["weekly_quests_last_reset_week"] = 0
            reset_count += 1
        
        save_data(data)
        await update.message.reply_text(
            f"✅ Еженедельные квесты сброшены у {reset_count} пользователей!\n"
            f"При следующем входе в раздел квестов они будут инициализированы из нового пула."
        )
        logger.info(f"Админ {user_id} принудительно сбросил еженедельные квесты у {reset_count} игроков")
    except Exception as e:
        logger.error(f"Ошибка reset_weekly_quests: {e}")
        await update.message.reply_text("❌ Ошибка при сбросе")


# ===== КОНЕЦ БЛОКА ЕЖЕНЕДЕЛЬНЫХ КВЕСТОВ =====

def escape_markdown(text: str) -> str:
    """Экранирует специальные символы Markdown, чтобы текст отображался как есть."""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

async def edit_clan_description_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начинает процесс редактирования описания клана."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        clan_id = get_user_clan(user_id, data)
        
        if not clan_id:
            await update.message.reply_text("❌ Вы не состоите в клане!")
            return
        
        clan = get_clan_data(clan_id, data)
        if not clan:
            await update.message.reply_text("❌ Ошибка: клан не найден!")
            return
        
        if clan.get("leader_id") != user_id:
            await update.message.reply_text("❌ Только глава клана может изменять описание!")
            return
        
        current_desc = clan.get("description", "")
        
        # ⭐ Переходим в состояние ввода ⭐
        context.user_data[user_id] = {"step": "clan_edit_description"}
        
        keyboard = [[KeyboardButton("❌ Отмена")]]
        
        if current_desc:
            text = (
                f"✏️ **Редактирование описания клана**\n\n"
                f"📝 **Текущее описание:**\n_{escape_markdown(current_desc)}_\n\n"
                f"Введите новое описание (до 300 символов):\n"
                f"• Разрешены буквы, цифры, эмодзи, переносы строк\n"
                f"• Для удаления описания отправьте: `нет`"
            )
        else:
            text = (
                f"✏️ **Создание описания клана**\n\n"
                f"📝 Описание пока не задано.\n\n"
                f"Введите описание (до 300 символов):\n"
                f"• Разрешены буквы, цифры, эмодзи, переносы строк"
            )
        
        await update.message.reply_text(
            text,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в edit_clan_description_start: {e}")
        await update.message.reply_text("❌ Ошибка")


async def process_clan_description_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ввод описания клана."""
    try:
        user_id = str(update.effective_user.id)
        text = update.message.text.strip()
        data = load_data()
        
        # ⭐ Проверка отмены ⭐
        if text == "❌ Отмена":
            if user_id in context.user_data:
                del context.user_data[user_id]
            keyboard = [[KeyboardButton("🔙 Назад в кланы")]]
            await update.message.reply_text(
                "❌ Редактирование описания отменено.",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return
        
        clan_id = get_user_clan(user_id, data)
        if not clan_id:
            if user_id in context.user_data:
                del context.user_data[user_id]
            await update.message.reply_text("❌ Вы не состоите в клане!")
            return
        
        clan = get_clan_data(clan_id, data)
        if not clan or clan.get("leader_id") != user_id:
            if user_id in context.user_data:
                del context.user_data[user_id]
            await update.message.reply_text("❌ Только глава клана может изменять описание!")
            return
        
        # ⭐ Проверка: удаление описания ⭐
        if text.lower() == "нет":
            clan["description"] = ""
            save_data(data)
            if user_id in context.user_data:
                del context.user_data[user_id]
            keyboard = [[KeyboardButton("🔙 Назад в кланы")]]
            await update.message.reply_text(
                "✅ Описание клана удалено.",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return
        
        # ⭐ Проверка длины ⭐
        if len(text) > 300:
            await update.message.reply_text(
                f"❌ Описание слишком длинное! ({len(text)}/300 символов)\n"
                f"Пожалуйста, сократите его."
            )
            return
        
        if len(text) < 3:
            await update.message.reply_text(
                "❌ Описание слишком короткое! Минимум 3 символа.\n"
                f"Повторите ввод:"
            )
            return
        
        # ⭐ Сохраняем описание ⭐
        clan["description"] = text
        save_data(data)
        
        if user_id in context.user_data:
            del context.user_data[user_id]
        
        keyboard = [[KeyboardButton("🔙 Назад в кланы")]]
        await update.message.reply_text(
            f"✅ **Описание клана обновлено!**\n\n"
            f"📝 Новое описание:\n_{escape_markdown(text)}_",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в process_clan_description_input: {e}")
        await update.message.reply_text("❌ Ошибка при сохранении описания")

async def add_seasonal_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавляет карту в раздел 'Сезонные карты'."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/add_seasonal [ID_карты] [цена]\n"
                "**Пример:**\n"
                "/add_seasonal 45 50000",
                parse_mode="Markdown"
            )
            return
        
        try:
            card_id = int(context.args[0])
            price = int(context.args[1])
        except ValueError:
            await update.message.reply_text("⚠️ ID и цена должны быть числами!")
            return
        
        if price < 0:
            await update.message.reply_text("⚠️ Цена не может быть отрицательной!")
            return
        
        # Проверяем существование карты
        card = find_card_by_id(card_id, data["cards"])
        if not card:
            await update.message.reply_text(f"⚠️ Карта #{card_id} не найдена!")
            return
        
        # Проверяем, нет ли уже этой карты в сезонных
        if str(card_id) in data["seasonal_cards"]:
            await update.message.reply_text(
                f"⚠️ Карта #{card_id} уже в сезонных!\n"
                f"Используйте /edit_seasonal для изменения цены."
            )
            return
        
        # Добавляем
        data["seasonal_cards"][str(card_id)] = price
        save_data(data)
        
        await update.message.reply_text(
            f"✅ **Карта добавлена в сезонные!**\n"
            f"🃏 Карта: {card['title']} (#{card_id})\n"
            f"🌟 Редкость: {card['rarity']}\n"
            f"💰 Цена: {price} бэт-коинов",
            parse_mode="Markdown"
        )
        logger.info(f"Админ добавил карту #{card_id} в сезонные за {price}")
    except Exception as e:
        logger.error(f"Ошибка add_seasonal_card: {e}")
        await update.message.reply_text("❌ Ошибка при добавлении")


async def edit_seasonal_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Изменяет цену сезонной карты."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/edit_seasonal [ID_карты] [новая_цена]\n"
                "**Пример:**\n"
                "/edit_seasonal 45 75000",
                parse_mode="Markdown"
            )
            return
        
        try:
            card_id = int(context.args[0])
            new_price = int(context.args[1])
        except ValueError:
            await update.message.reply_text("⚠️ ID и цена должны быть числами!")
            return
        
        if new_price < 0:
            await update.message.reply_text("⚠️ Цена не может быть отрицательной!")
            return
        
        card_id_str = str(card_id)
        if card_id_str not in data["seasonal_cards"]:
            await update.message.reply_text(
                f"⚠️ Карта #{card_id} не в сезонных!\n"
                f"Используйте /add_seasonal для добавления."
            )
            return
        
        old_price = data["seasonal_cards"][card_id_str]
        data["seasonal_cards"][card_id_str] = new_price
        save_data(data)
        
        card = find_card_by_id(card_id, data["cards"])
        card_title = card["title"] if card else f"#{card_id}"
        
        await update.message.reply_text(
            f"✅ **Цена сезонной карты обновлена!**\n"
            f"🃏 Карта: {card_title}\n"
            f"❌ Было: {old_price} бэт-коинов\n"
            f"✅ Стало: {new_price} бэт-коинов",
            parse_mode="Markdown"
        )
        logger.info(f"Админ изменил цену карты #{card_id}: {old_price} → {new_price}")
    except Exception as e:
        logger.error(f"Ошибка edit_seasonal_card: {e}")
        await update.message.reply_text("❌ Ошибка при редактировании")


async def remove_seasonal_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаляет карту из сезонных."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        if not context.args:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/remove_seasonal [ID_карты]\n"
                "**Пример:**\n"
                "/remove_seasonal 45",
                parse_mode="Markdown"
            )
            return
        
        try:
            card_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("⚠️ ID должен быть числом!")
            return
        
        card_id_str = str(card_id)
        if card_id_str not in data["seasonal_cards"]:
            await update.message.reply_text(f"⚠️ Карта #{card_id} не в сезонных!")
            return
        
        old_price = data["seasonal_cards"][card_id_str]
        del data["seasonal_cards"][card_id_str]
        save_data(data)
        
        card = find_card_by_id(card_id, data["cards"])
        card_title = card["title"] if card else f"#{card_id}"
        
        await update.message.reply_text(
            f"✅ **Карта удалена из сезонных!**\n"
            f"🃏 Карта: {card_title}\n"
            f"💰 Была цена: {old_price} бэт-коинов",
            parse_mode="Markdown"
        )
        logger.info(f"Админ удалил карту #{card_id} из сезонных")
    except Exception as e:
        logger.error(f"Ошибка remove_seasonal_card: {e}")
        await update.message.reply_text("❌ Ошибка при удалении")


async def list_seasonal_cards(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список всех сезонных карт."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        seasonal = data.get("seasonal_cards", {})
        if not seasonal:
            await update.message.reply_text("📭 Нет сезонных карт!")
            return
        
        message_text = "🎴 **Сезонные карты:**\n\n"
        for card_id_str, price in seasonal.items():
            card_id = int(card_id_str)
            card = find_card_by_id(card_id, data["cards"])
            if card:
                status = "✅" if card.get("available", True) else "❌"
                message_text += (
                    f"{status} #{card_id} — **{card['title']}**\n"
                    f"   🌟 {card['rarity']} | 💰 {price} бэт-коинов\n\n"
                )
            else:
                message_text += f"⚠️ #{card_id} — карта не найдена | 💰 {price}\n\n"
        
        message_text += f"📊 Всего: {len(seasonal)} карт"
        
        await update.message.reply_text(message_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка list_seasonal_cards: {e}")
        await update.message.reply_text("❌ Ошибка при получении списка")

async def add_cents_to_player(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавляет (или списывает) бэт-коины игроку по ID или @никнейму."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        # Проверяем аргументы
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/add_cents_to_player [ID_или_@никнейм] [количество]\n"
                "**Примеры:**\n"
                "/add_cents_to_player 881692999 5000 — добавить 5000 бэт-коинов\n"
                "/add_cents_to_player @username 5000 — добавить 5000 бэт-коинов\n"
                "/add_cents_to_player 881692999 -1000 — списать 1000 бэт-коинов",
                parse_mode="Markdown"
            )
            return
        
        target_input = context.args[0]
        cents_amount = int(context.args[1])
        target_user_id = None
        is_new_user = False
        
        # ⭐ ОПРЕДЕЛЯЕМ ID ИГРОКА ⭐
        if target_input.startswith("@"):
            username_to_find = target_input[1:].strip().lower()
            for uid, udata in data["users"].items():
                if udata.get("username", "").lower() == username_to_find:
                    target_user_id = uid
                    break
            if not target_user_id:
                await update.message.reply_text(f"⚠️ Игрок с никнеймом @{username_to_find} не найден!")
                return
        else:
            target_user_id = target_input
            if target_user_id not in data["users"]:
                is_new_user = True
                # Создаём нового игрока с нулевыми параметрами
                data["users"][target_user_id] = {
                    "username": "",
                    "first_name": "Admin Granted",
                    "last_name": "",
                    "cards": [],
                    "total_points": 0,
                    "season_points": 0,
                    "cents": 0,
                    "last_card_time": 0,
                    "free_rolls": 0,
                    "last_dice_time": 0,
                    "casino_attempts": 5,
                    "last_casino_reset": 0,
                    "used_promo_codes": [],
                    "referral_invites": [],
                    "referral_rewards_claimed": [],
                    "daily_quests": [],
                    "weekly_quests": [],
                    "avatar_url": DEFAULT_AVATAR_URL,
                    "avatars": [DEFAULT_AVATAR_URL],
                    "pending_season_boxes": 0,
                }
        
        user_data = data["users"][target_user_id]
        
        # ⭐ Добавляем/списываем бэт-коины ⭐
        old_cents = user_data.get("cents", 0)
        new_cents = old_cents + cents_amount
        
        # ⭐ Защита от ухода в минус ⭐
        if new_cents < 0:
            await update.message.reply_text(
                f"⚠️ Нельзя списать больше, чем есть у игрока!\n"
                f"💰 У игрока: {old_cents} бэт-коинов\n"
                f"❌ Вы пытаетесь списать: {-cents_amount} бэт-коинов"
            )
            return
        
        user_data["cents"] = new_cents
        save_data(data)
        
        # ⭐ Формируем текст ответа ⭐
        if cents_amount > 0:
            action_text = f"💰 Добавлено: +{cents_amount} бэт-коинов"
        elif cents_amount < 0:
            action_text = f"💸 Списано: {cents_amount} бэт-коинов"
        else:
            action_text = "ℹ️ Количество равно 0 — баланс не изменился"
        
        await update.message.reply_text(
            f"✅ **Баланс игрока изменён!**\n"
            f"👤 Игрок: {target_user_id}\n"
            f"{action_text}\n"
            f"📊 Было: {old_cents}\n"
            f"📈 Стало: {new_cents}\n"
            f"{'🆕 Игрок создан!' if is_new_user else ''}",
            parse_mode="Markdown"
        )
        
        logger.info(
            f"Админ изменил баланс игрока {target_user_id}: "
            f"{old_cents} → {new_cents} ({'+' if cents_amount >= 0 else ''}{cents_amount})"
        )
        
    except ValueError:
        await update.message.reply_text("⚠️ Количество должно быть числом!")
    except Exception as e:
        logger.error(f"Ошибка добавления бэт-коинов: {e}")
        await update.message.reply_text("❌ Ошибка при изменении баланса")

async def daily_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает статистику активности и новых пользователей за сегодня."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        from datetime import datetime, timezone, timedelta
        
        # ⭐ Определяем сегодняшнюю дату в МСК ⭐
        msk_tz = timezone(timedelta(hours=3))
        today_str = datetime.now(msk_tz).strftime("%Y-%m-%d")
        today_display = datetime.now(msk_tz).strftime("%d.%m.%Y")
        
        users = data.get("users", {})
        
        # ⭐ Считаем активных пользователей сегодня ⭐
        active_today = []
        for uid, udata in users.items():
            if udata.get("last_daily_activity") == today_str:
                active_today.append(uid)
        
        # ⭐ Считаем новых пользователей сегодня ⭐
        new_today = []
        for uid, udata in users.items():
            if udata.get("registered_at") == today_str:
                new_today.append(uid)
        
        # ⭐ Считаем статистику за вчера ⭐
        yesterday = datetime.now(msk_tz) - timedelta(days=1)
        yesterday_str = yesterday.strftime("%Y-%m-%d")
        yesterday_display = yesterday.strftime("%d.%m.%Y")
        
        active_yesterday = sum(1 for u in users.values() if u.get("last_daily_activity") == yesterday_str)
        new_yesterday = sum(1 for u in users.values() if u.get("registered_at") == yesterday_str)
        
        # ⭐ Считаем статистику за неделю ⭐
        week_ago = datetime.now(msk_tz) - timedelta(days=7)
        week_ago_str = week_ago.strftime("%Y-%m-%d")
        
        active_week = sum(1 for u in users.values() 
                         if u.get("last_daily_activity") and u.get("last_daily_activity") >= week_ago_str)
        new_week = sum(1 for u in users.values() 
                      if u.get("registered_at") and u.get("registered_at") >= week_ago_str)
        
        # ⭐ Общее количество пользователей ⭐
        total_users = len(users)
        
        # ⭐ Формируем текст ответа ⭐
        message_text = (
            f"📊 **Статистика активности**\n\n"
            f"📅 **Сегодня ({today_display}):**\n"
            f"• 🟢 Активных: **{len(active_today)}**\n"
            f"• 🆕 Новых: **{len(new_today)}**\n\n"
            f"📅 **Вчера ({yesterday_display}):**\n"
            f"• 🟢 Активных: **{active_yesterday}**\n"
            f"• 🆕 Новых: **{new_yesterday}**\n\n"
            f"📅 **За последние 7 дней:**\n"
            f"• 🟢 Активных: **{active_week}**\n"
            f"• 🆕 Новых: **{new_week}**\n\n"
            f"👥 **Всего пользователей:** **{total_users}**"
        )
        
        # ⭐ Если есть активные сегодня — показываем их список ⭐
        if active_today:
            message_text += f"\n\n🟢 **Активные сегодня:**\n"
            for i, uid in enumerate(active_today[:20], 1):  # Показываем максимум 20
                udata = users.get(uid, {})
                name = udata.get("username") or udata.get("first_name") or f"ID: {uid}"
                # ⭐ ИСПРАВЛЕНИЕ: Экранируем имя ⭐
                name_escaped = escape_markdown(name)
                message_text += f"{i}\. {name_escaped}\n"
            
            if len(active_today) > 20:
                message_text += f"\.\.\. и ещё {len(active_today) - 20}\n"
        
        # ⭐ Если есть новые сегодня — показываем их список ⭐
        if new_today:
            message_text += f"\n🆕 **Новые сегодня:**\n"
            for i, uid in enumerate(new_today[:20], 1):
                udata = users.get(uid, {})
                name = udata.get("username") or udata.get("first_name") or f"ID: {uid}"
                # ⭐ ИСПРАВЛЕНИЕ: Экранируем имя ⭐
                name_escaped = escape_markdown(name)
                message_text += f"{i}\. {name_escaped}\n"
            
            if len(new_today) > 20:
                message_text += f"\.\.\. и ещё {len(new_today) - 20}\n"
        
        await update.message.reply_text(message_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка daily_stats: {e}")
        await update.message.reply_text("❌ Ошибка при получении статистики")


async def check_probabilities(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает реальные вероятности выпадения карт по редкостям."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        # Собираем доступные карты
        available_cards = [c for c in data["cards"] if c.get("available", True)]
        
        # Группируем по редкостям
        cards_by_rarity = {}
        for card in available_cards:
            rarity = card.get("rarity", "Unknown")
            if rarity not in cards_by_rarity:
                cards_by_rarity[rarity] = []
            cards_by_rarity[rarity].append(card)
        
        # Собираем веса
        available_rarities = []
        weights = []
        for rarity, rarity_cards in cards_by_rarity.items():
            if rarity_cards:
                probability = RARITY_BONUSES.get(rarity, {"probability": 0}).get("probability", 0)
                if probability > 0:
                    available_rarities.append(rarity)
                    weights.append(probability)
        
        if not available_rarities:
            await update.message.reply_text("❌ Нет доступных карт с положительной вероятностью!")
            return
        
        total_weight = sum(weights)
        
        # Формируем отчёт
        message_text = (
            f"📊 **Реальные вероятности выпадения карт**\n\n"
            f"📦 Всего доступных карт: **{len(available_cards)}**\n"
            f"🎯 Сумма весов: **{total_weight}**\n\n"
            f"**По редкостям:**\n"
        )
        
        # Сортируем по вероятности (по убыванию)
        rarity_data = []
        for rarity, weight in zip(available_rarities, weights):
            normalized = round((weight / total_weight) * 100, 2)
            card_count = len(cards_by_rarity[rarity])
            # Вероятность конкретной карты этой редкости
            per_card = round(normalized / card_count, 2) if card_count > 0 else 0
            rarity_data.append({
                "rarity": rarity,
                "weight": weight,
                "normalized": normalized,
                "card_count": card_count,
                "per_card": per_card
            })
        
        rarity_data.sort(key=lambda x: x["normalized"], reverse=True)
        
        for rd in rarity_data:
            message_text += (
                f"\n🌟 **{rd['rarity']}**\n"
                f"   • Вес: {rd['weight']}\n"
                f"   • Шанс редкости: **{rd['normalized']}%**\n"
                f"   • Карт в базе: {rd['card_count']}\n"
                f"   • Шанс конкретной карты: **{rd['per_card']}%**\n"
            )
        
        # ⭐ Симуляция 1000 выпадений для проверки ⭐
        message_text += "\n\n🎲 **Симуляция 1000 выпадений:**\n"
        simulation = {}
        normalized_weights = [w / total_weight for w in weights]
        
        for _ in range(1000):
            chosen_rarity = random.choices(available_rarities, weights=normalized_weights, k=1)[0]
            simulation[chosen_rarity] = simulation.get(chosen_rarity, 0) + 1
        
        for rarity, count in sorted(simulation.items(), key=lambda x: x[1], reverse=True):
            actual_percent = round((count / 1000) * 100, 2)
            expected = next((rd["normalized"] for rd in rarity_data if rd["rarity"] == rarity), 0)
            diff = round(actual_percent - expected, 2)
            diff_sign = "+" if diff >= 0 else ""
            message_text += f"• {rarity}: {count}/1000 ({actual_percent}%) [ожид. {expected}%, откл. {diff_sign}{diff}%]\n"
        
        await update.message.reply_text(message_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка check_probabilities: {e}")
        await update.message.reply_text("❌ Ошибка при проверке вероятностей")

async def give_batpass(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выдаёт Бэт-пасс игроку на определённое количество дней."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        # Проверяем аргументы
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/give_batpass [@никнейм] [дней]\n"
                "**Примеры:**\n"
                "/give_batpass @username 30 - выдать на 30 дней\n"
                "/give_batpass 881692999 7 - выдать на 7 дней",
                parse_mode="Markdown"
            )
            return
        
        target_input = context.args[0]
        days = int(context.args[1])
        
        if days <= 0:
            await update.message.reply_text("⚠️ Количество дней должно быть положительным!")
            return
        
        # Определяем ID игрока
        target_user_id = None
        if target_input.startswith("@"):
            username_to_find = target_input[1:].strip().lower()
            for uid, udata in data["users"].items():
                if udata.get("username", "").lower() == username_to_find:
                    target_user_id = uid
                    break
            if not target_user_id:
                await update.message.reply_text(f"⚠️ Игрок с никнеймом @{username_to_find} не найден!")
                return
        else:
            target_user_id = target_input
            if target_user_id not in data["users"]:
                await update.message.reply_text(f"⚠️ Игрок с ID {target_user_id} не найден!")
                return
        
        user_data = data["users"][target_user_id]
        
        # ⭐ Миграция ⭐
        if "batpass_privileges" not in user_data:
            user_data["batpass_privileges"] = {
                "reduced_cooldown": True,
            }
        
        # ⭐ Выдаём Бэт-пасс ⭐
        from datetime import datetime, timezone, timedelta
        msk_tz = timezone(timedelta(hours=3))
        expires_at = int((datetime.now(msk_tz) + timedelta(days=days)).timestamp())
        
        user_data["has_batpass"] = True
        user_data["batpass_expires_at"] = expires_at
        
        save_data(data)
        
        # ⭐ НОВОЕ: Планируем уведомление, если у игрока есть кулдаун ⭐
        if user_data.get("last_card_time", 0) > 0:
            from datetime import datetime, timezone, timedelta
            msk_tz = timezone(timedelta(hours=3))
            now = int(datetime.now(msk_tz).timestamp())
    
            last_card_time = user_data.get("last_card_time", 0)
            cooldown = 9000  # 2.5 часа для Бэт-пасса
            notification_time = last_card_time + cooldown
    
            if notification_time > now:
                delay_seconds = notification_time - now
                job_name = f"card_notify_{target_user_id}"
        
                # Отменяем старый job, если есть
                for job in context.job_queue.get_jobs_by_name(job_name):
                    job.schedule_removal()
        
                # Планируем новый job
                context.job_queue.run_once(
                    send_card_notification,
                    when=delay_seconds,
                    data={"user_id": target_user_id},
                    name=job_name
                )
        
                logger.info(f"Запланировано уведомление для игрока {target_user_id} через {delay_seconds} сек")
        
        # ⭐ Отчёт админу ⭐
        expires_display = datetime.fromtimestamp(expires_at, msk_tz).strftime("%d.%m.%Y %H:%M МСК")
        await update.message.reply_text(
            f"✅ **Бэт-пасс выдан!**\n"
            f"👤 Игрок: {target_user_id}\n"
            f"📅 Срок: {days} дней\n"
            f"⏰ Истекает: {expires_display}",
            parse_mode="Markdown"
        )
        
        # ⭐ Уведомление игроку ⭐
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"🎫 <b>Вам выдан Бэт-пасс!</b>\n\n"
                    f"📅 <b>Срок действия:</b> {days} дней\n"
                    f"⏰ <b>Истекает:</b> {expires_display}"
                ),
                parse_mode="HTML"
            )
        except Exception as notify_error:
            logger.warning(f"Не удалось уведомить игрока {target_user_id}: {notify_error}")
        
        logger.info(f"Админ выдал Бэт-пасс игроку {target_user_id} на {days} дней")
        
    except ValueError:
        await update.message.reply_text("⚠️ Количество дней должно быть числом!")
    except Exception as e:
        logger.error(f"Ошибка give_batpass: {e}")
        await update.message.reply_text("❌ Ошибка при выдаче Бэт-пасса")

async def remove_batpass(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отзывает Бэт-пасс у игрока."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        if not context.args:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/remove_batpass [@никнейм_или_ID]\n"
                "**Примеры:**\n"
                "/remove_batpass @username\n"
                "/remove_batpass 881692999",
                parse_mode="Markdown"
            )
            return
        
        target_input = context.args[0]
        target_user_id = None
        
        # Определяем ID игрока
        if target_input.startswith("@"):
            username_to_find = target_input[1:].strip().lower()
            for uid, udata in data["users"].items():
                if udata.get("username", "").lower() == username_to_find:
                    target_user_id = uid
                    break
            if not target_user_id:
                await update.message.reply_text(f"⚠️ Игрок с никнеймом @{username_to_find} не найден!")
                return
        else:
            target_user_id = target_input
            if target_user_id not in data["users"]:
                await update.message.reply_text(f"⚠️ Игрок с ID {target_user_id} не найден!")
                return
        
        user_data = data["users"][target_user_id]
        
        # Проверяем, есть ли Бэт-пасс
        if not user_data.get("has_batpass", False):
            await update.message.reply_text(f"⚠️ У игрока {target_user_id} нет Бэт-пасса!")
            return
        
        # ⭐ Отзываем Бэт-пасс ⭐
        user_data["has_batpass"] = False
        user_data["batpass_expires_at"] = 0
        save_data(data)

        # ⭐ НОВОЕ: Отменяем уведомление, если оно было запланировано ⭐
        job_name = f"card_notify_{target_user_id}"
        for job in context.job_queue.get_jobs_by_name(job_name):
            job.schedule_removal()
            logger.info(f"Отменено уведомление для игрока {target_user_id}")
        
        await update.message.reply_text(
            f"✅ **Бэт-пасс отозван!**\n"
            f"👤 Игрок: {target_user_id}",
            parse_mode="Markdown"
        )
        
        # ⭐ Уведомление игроку ⭐
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="🎫 <b>Ваш Бэт-пасс был отозван администратором.</b>",
                parse_mode="HTML"
            )
        except Exception as notify_error:
            logger.warning(f"Не удалось уведомить игрока {target_user_id}: {notify_error}")
        
        logger.info(f"Админ отозвал Бэт-пасс у игрока {target_user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка remove_batpass: {e}")
        await update.message.reply_text("❌ Ошибка при отзыве Бэт-пасса")

async def give_card_to_batpass(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выдаёт карту всем игрокам с активным Бэт-пассом."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        # Проверяем аргументы
        if not context.args or len(context.args) < 1:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/give_card_to_batpass [ID_карты] [количество]\n"
                "**Примеры:**\n"
                "/give_card_to_batpass 45 - выдать 1 карту всем\n"
                "/give_card_to_batpass 45 3 - выдать 3 карты всем",
                parse_mode="Markdown"
            )
            return
        
        card_id = int(context.args[0])
        count = int(context.args[1]) if len(context.args) > 1 else 1
        
        # Проверяем существование карты
        card = find_card_by_id(card_id, data["cards"])
        if not card:
            await update.message.reply_text(f"⚠️ Карта #{card_id} не найдена!")
            return
        
        # ⭐ Собираем список игроков с активным Бэт-пассом ⭐
        from datetime import datetime, timezone, timedelta
        msk_tz = timezone(timedelta(hours=3))
        now = int(datetime.now(msk_tz).timestamp())
        
        batpass_holders = []
        for uid, udata in data["users"].items():
            if udata.get("has_batpass", False):
                expires_at = udata.get("batpass_expires_at", 0)
                if expires_at > now:
                    batpass_holders.append(uid)
        
        if not batpass_holders:
            await update.message.reply_text(
                "⚠️ Нет игроков с активным Бэт-пассом!"
            )
            return
        
        # ⭐ Выдаём карту каждому ⭐
        success_count = 0
        failed_count = 0
        
        for uid in batpass_holders:
            user_data = data["users"][uid]
            
            # Добавляем карту
            if "cards" not in user_data:
                user_data["cards"] = []
            
            for _ in range(count):
                user_data["cards"].append(card_id)
            
            # ⭐ Уведомляем игрока ⭐
            try:
                # Формируем caption
                if count > 1:
                    caption_text = (
                        f"🎁 <b>Вам была выдана награда!</b>\n\n"
                        f"🃏 <b>Карта:</b> {card['title']}\n"
                        f"🌟 <b>Редкость:</b> {card['rarity']}\n"
                        f"📦 <b>Количество:</b> {count} шт.\n\n"
                        f"🎫 <i>Награда за Бэт-пасс</i>"
                    )
                else:
                    caption_text = (
                        f"🎁 <b>Вам была выдана награда!</b>\n\n"
                        f"🃏 <b>Карта:</b> {card['title']}\n"
                        f"🌟 <b>Редкость:</b> {card['rarity']}\n\n"
                        f"🎫 <i>Награда за Бэт-пасс</i>"
                    )
                
                # ⭐ Универсальная логика: file_id или URL ⭐
                media_source = card.get("media_source", "url")
                media_value = card.get("file_id") if media_source == "file_id" else card.get("image_url", "")
                
                if not media_value:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=caption_text,
                        parse_mode="HTML"
                    )
                elif card.get("media_type") == "animation" or (isinstance(media_value, str) and media_value.lower().endswith((".mp4", ".webm", ".gif"))):
                    await context.bot.send_video(
                        chat_id=uid,
                        video=media_value,
                        caption=caption_text,
                        parse_mode="HTML",
                        supports_streaming=True
                    )
                else:
                    await context.bot.send_photo(
                        chat_id=uid,
                        photo=media_value,
                        caption=caption_text,
                        parse_mode="HTML"
                    )
                
                success_count += 1
            except Exception as notify_error:
                logger.warning(f"Не удалось уведомить игрока {uid}: {notify_error}")
                failed_count += 1
                # ⭐ Продолжаем выдачу остальным ⭐
                continue
        
        save_data(data)
        
        # ⭐ Отчёт админу ⭐
        await update.message.reply_text(
            f"✅ **Карта выдана игрокам с Бэт-пассом!**\n\n"
            f"🃏 Карта: {card['title']} (#{card_id})\n"
            f"🌟 Редкость: {card['rarity']}\n"
            f"📦 Количество: {count} шт.\n\n"
            f"👥 Всего получателей: {len(batpass_holders)}\n"
            f"✅ Успешно: {success_count}\n"
            f"❌ Не удалось уведомить: {failed_count}",
            parse_mode="Markdown"
        )
        
        logger.info(
            f"Админ выдал карту #{card_id} (x{count}) "
            f"{len(batpass_holders)} игрокам с Бэт-пассом "
            f"(успешно: {success_count}, не удалось: {failed_count})"
        )
        
    except ValueError:
        await update.message.reply_text("⚠️ ID карты и количество должны быть числами!")
    except Exception as e:
        logger.error(f"Ошибка give_card_to_batpass: {e}")
        await update.message.reply_text("❌ Ошибка при выдаче карты")

async def check_and_schedule_notifications(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Проверяет всех игроков с Бэт-пассом и планирует уведомления.
    Запускается каждую минуту через JobQueue.
    """
    try:
        data = load_data()
        from datetime import datetime, timezone, timedelta
        msk_tz = timezone(timedelta(hours=3))
        now = int(datetime.now(msk_tz).timestamp())
        
        # Получаем список уже запланированных jobs
        existing_jobs = {
            job.name: job for job in context.job_queue.jobs()
            if job.name and job.name.startswith("card_notify_")
        }
        
        for user_id, user_data in data.get("users", {}).items():
            # Проверяем, что у игрока активный Бэт-пасс
            if not is_batpass_active(user_data):
                continue
            
            # Вычисляем время окончания кулдауна
            last_card_time = user_data.get("last_card_time", 0)
            cooldown = 9000  # 2.5 часа
            notification_time = last_card_time + cooldown
            
            # Если время уведомления в будущем
            if notification_time > now:
                job_name = f"card_notify_{user_id}"
                
                # Если job ещё не запланирован
                if job_name not in existing_jobs:
                    delay_seconds = notification_time - now
                    
                    # Планируем job
                    context.job_queue.run_once(
                        send_card_notification,
                        when=delay_seconds,
                        data={"user_id": user_id},
                        name=job_name
                    )
                    
                    logger.debug(f"Запланировано уведомление для игрока {user_id} через {delay_seconds} сек")
        
    except Exception as e:
        logger.error(f"Ошибка check_and_schedule_notifications: {e}")

async def send_card_notification(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет уведомление о возможности получить досье."""
    try:
        job = context.job
        user_id = job.data["user_id"]
        
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data:
            return
        
        # ⭐ Проверяем, что Бэт-пасс всё ещё активен ⭐
        if not is_batpass_active(user_data):
            logger.info(f"Бэт-пасс игрока {user_id} истёк, уведомление не отправлено")
            return
        
        # ⭐ Проверяем, что кулдаун действительно прошёл ⭐
        last_card_time = user_data.get("last_card_time", 0)
        cooldown = 9000  # 2.5 часа
        current_time = int(time.time())
        
        if current_time - last_card_time < cooldown:
            logger.info(f"Кулдаун игрока {user_id} ещё не прошёл, уведомление не отправлено")
            return
        
        # ⭐ Отправляем уведомление ⭐
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text="⏰ <b>Вы можете получить новое досье!</b>",
                parse_mode="HTML"
            )
            logger.info(f"Уведомление отправлено игроку {user_id}")
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление игроку {user_id}: {e}")
        
    except Exception as e:
        logger.error(f"Ошибка send_card_notification: {e}")

async def shop_batpass(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает информацию о Бэт-пассе."""
    try:
        query = update.callback_query if hasattr(update, 'callback_query') else None
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id, {})
        
        from datetime import datetime, timezone, timedelta
        msk_tz = timezone(timedelta(hours=3))
        now = int(datetime.now(msk_tz).timestamp())
        
        # ⭐ Проверяем, активен ли Бэт-пасс ⭐
        has_active_batpass = False
        remaining_text = ""
        
        if user_data.get("has_batpass", False):
            expires_at = user_data.get("batpass_expires_at", 0)
            if expires_at > now:
                has_active_batpass = True
                remaining_seconds = expires_at - now
                
                # Форматируем оставшееся время
                days = remaining_seconds // 86400
                hours = (remaining_seconds % 86400) // 3600
                minutes = (remaining_seconds % 3600) // 60
                
                parts = []
                if days > 0:
                    parts.append(f"{days} дн.")
                if hours > 0 or days > 0:
                    parts.append(f"{hours} ч.")
                parts.append(f"{minutes} мин.")
                
                remaining_text = " ".join(parts)
                expires_display = datetime.fromtimestamp(expires_at, msk_tz).strftime("%d.%m.%Y %H:%M МСК")
        
        # ⭐ Формируем текст ⭐
        text = "🎫 <b>Бэт-пасс</b>\n\n"
        
        if has_active_batpass:
            text += (
                f"✅ <b>Ваш Бэт-пасс активен!</b>\n"
                f"⏰ <b>Осталось:</b> {remaining_text}\n"
                f"📅 <b>Истекает:</b> {expires_display}\n\n"
            )
        else:
            text += (
                "❌ <b>У вас нет активного Бэт-пасса</b>\n\n"
                "Приобретите Бэт-пасс, чтобы получить эксклюзивные привилегии!\n\n"
            )
        
        text += (
            "✨ <b>Привилегии Бэт-пасса:</b>\n"
            "• 🔍 Получение досье раз в 2.5 часа\n"
            "• 🎲 2 броска кубика в неделю\n"
            "• 🏰 Бесплатное создание кланов\n"
            "• ⏰ Уведомления о получении нового досье\n"
            "• 🃏 Бесплатное получение ежнедельной карты из магазина\n"
            "• 💸 Скидка на донат 20% кроме покупки Бэт-пасса\n"
            "• 🎰 7 попыток в казино в день\n\n"
            "💰 <b>Стоимость:</b>\n"
            "• 1 месяц — <b>149₽</b>\n"
            "• 3 месяца — <b>399₽</b>\n"
            "• 6 месяцев — <b>599₽</b>\n"
            "• 12 месяцев — <b>999₽</b>\n\n"
            "💬 <b>Для покупки писать:</b> @Be9onder"
        )
        
        # ⭐ Клавиатура ⭐
        keyboard = [
            [InlineKeyboardButton("💬 Написать @Be9onder", url="https://t.me/Be9onder")],
            [InlineKeyboardButton("🔙 Назад в магазин", callback_data="shop_menu")],
        ]
        
        if query:
            try:
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML"
                )
            except Exception as e:
                error_str = str(e)
                if "Message is not modified" in error_str:
                    # Сообщение уже содержит то же самое — просто выходим
                    return
                elif "There is no text" in error_str:
                    # ⭐ НОВОЕ: Сообщение — медиа (фото/видео), удаляем и отправляем новое ⭐
                    try:
                        await query.message.delete()
                    except:
                        pass
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text=text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="HTML"
                    )
                else:
                    logger.error(f"Ошибка редактирования shop_batpass: {e}")
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Ошибка shop_batpass: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Ошибка", show_alert=True)
        else:
            await update.message.reply_text("❌ Ошибка при открытии раздела Бэт-пасс")

# ===== ЗАПУСК БОТА =====

def main() -> None:
    try:
        if BOT_TOKEN == "ВАШ_ТОКЕН_БОТА" or INITIAL_ADMIN_ID == "ВАШ_ID_АДМИНА":
            print("ЗАМЕНИТЕ BOT_TOKEN И INITIAL_ADMIN_ID НА РЕАЛЬНЫЕ ЗНАЧЕНИЯ!")
            input("Нажмите Enter для выхода...")
            return

        if not os.path.exists(DATA_FILE):
            save_data(load_data())
            print("Создан новый файл данных")

        # Регистрируем обработчики
        application = Application.builder().token(BOT_TOKEN).build()
        
        # ⭐ НОВОЕ: Планируем уведомления при старте бота ⭐
        application.job_queue.run_repeating(
            check_and_schedule_notifications,
            interval=60,  # Каждую минуту
            first=5,      # Через 5 секунд после старта
            name="notification_scheduler"
        )
        
        handlers = [
            CommandHandler("start", start),
            CommandHandler("profile", my_profile),
            CommandHandler("dice", dice),
            CommandHandler("help", help_command),
            CommandHandler("top", top_players),
            CommandHandler("trade", trade_menu),  # ← ДОБАВЬТЕ
            CommandHandler("add_card", add_card),
            CommandHandler("add_card_to_player", add_card_to_player),
            CommandHandler("add_rolls_to_player", add_rolls_to_player),
            CommandHandler("edit_card", edit_card),
            CommandHandler("card_info", card_info),
            CommandHandler("cards", list_cards),
            CommandHandler("toggle_card", toggle_card),
            CommandHandler("broadcast", broadcast),
            CommandHandler("reset_all_cards", reset_all_cards),
            CommandHandler("reset_season_points", reset_season_points), 
            CommandHandler("delete_card", delete_card),
            CommandHandler("reset_user", reset_user),
            CommandHandler("check_cards", check_cards),
            CommandHandler("list_users", list_users),
            CommandHandler("daily_stats", daily_stats),
            CommandHandler("list_admins", list_admins),
            CommandHandler("add_admin", add_admin),
            CommandHandler("remove_admin", remove_admin),
            CommandHandler("create_promo", create_promo_code),
            CommandHandler("delete_promo", delete_promo_code),
            CommandHandler("list_promo", list_promo_codes),
            CommandHandler("promo", activate_promo_code),
            CommandHandler("craft", craft_menu),
            CommandHandler("accept_clan_invite", accept_clan_invite),
            CommandHandler("topclans", top_clans),
            CommandHandler("reset_weekly_quests", reset_weekly_quests),
            CommandHandler("add_seasonal", add_seasonal_card),
            CommandHandler("edit_seasonal", edit_seasonal_card),
            CommandHandler("remove_seasonal", remove_seasonal_card),
            CommandHandler("list_seasonal", list_seasonal_cards),
            CommandHandler("give_season_box", give_season_box),
            CommandHandler("add_cents_to_player", add_cents_to_player),
            CommandHandler("check_probabilities", check_probabilities),
            CommandHandler("give_batpass", give_batpass),
            CommandHandler("remove_batpass", remove_batpass),
            CommandHandler("give_card_to_batpass", give_card_to_batpass),
            CommandHandler("give_superman_box", give_superman_box),
            MessageHandler(filters.PHOTO | filters.VIDEO | filters.ANIMATION, handle_message),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            CallbackQueryHandler(mycards_callback, pattern=r"^(mycards_|barracks_|card_).*"),
            CallbackQueryHandler(dice_callback, pattern=r"^dice_.*"),
            CallbackQueryHandler(casino_callback, pattern=r"^casino_.*"),
            CallbackQueryHandler(top_callback, pattern=r"^top_.*"),
            CallbackQueryHandler(trade_button_callback, pattern=r"^trade_(accept|decline)_btn_.*"),
            CallbackQueryHandler(trade_offer_callback, pattern=r"^trade_offer_.*"),
            CallbackQueryHandler(trade_return_callback, pattern=r"^trade_return_.*"),
            CallbackQueryHandler(trade_search_callback, pattern=r"^trade_search_.*"),
            CallbackQueryHandler(trade_final_callback, pattern=r"^trade_final_(confirm|decline)_.*"),
            CallbackQueryHandler(trade_callback, pattern=r"^trade_.*"),
            CallbackQueryHandler(profile_callback, pattern=r"^(profile_back|view_other_start|my_avatars_.*)"),
            CallbackQueryHandler(craft_callback, pattern=r"^craft_.*"),
            CallbackQueryHandler(basket_callback, pattern=r"^basket_.*"),
            CallbackQueryHandler(shop_callback, pattern=r"^shop_.*"),
            CallbackQueryHandler(burn_callback, pattern=r"^burn_.*"),
            CallbackQueryHandler(darts_callback, pattern=r"^darts_.*"),
            CallbackQueryHandler(quests_callback, pattern=r"^quests_.*"),
            CallbackQueryHandler(shop_seasonal_callback, pattern=r"^ss_.*"),
            CallbackQueryHandler(avatar_callback, pattern=r"^avatar_.*"),
            CallbackQueryHandler(seasonal_quest_callback, pattern=r"^sq_.*"),
            CallbackQueryHandler(archive_search_start, pattern=r"^archive_search_(all|Common|Rare|Epic|Legendary|Highlight|Limited|Rare Team-up|Epic Team-up|Legendary Team-up)$"),
            CallbackQueryHandler(archive_search_callback, pattern=r"^archive_search_(prev|next|info|cancel).*"),
            CallbackQueryHandler(open_superman_heroes_box, pattern=r"^shop_open_superman_heroes$"),
            CallbackQueryHandler(open_superman_villain_box, pattern=r"^shop_open_superman_villain$"),
        ]

        for handler in handlers:
            application.add_handler(handler)
            application.add_handler(CallbackQueryHandler(referral_menu, pattern="^referral_menu$"))
        
        print("Бот успешно запущен! Ctrl+C для остановки")
        logger.info("Бот запущен")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")
        print(f"Ошибка запуска: {e}")
        input("Нажмите Enter для выхода...")

__all__ = [
'load_data',
'save_data',
'is_admin',
'find_card_by_id',
]    

if __name__ == "__main__":

    main()
