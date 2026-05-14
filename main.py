import logging
import json
import asyncio
import threading
import os
import random
import time
import datetime
from typing import Optional, Dict, Any, List
from collections import Counter
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaAnimation,
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
AUTO_ANIMATED_RARITIES = ["Animated!"]
SUPER_ADMIN_ID = "881692999"
_gold_digger_last_check = None

FORT_IMAGE_URL = "https://ibb.co/gZwy5v0G"
FOREST_IMAGE_URL = "https://ibb.co/DgTPVmTr"
TAVERN_IMAGE_URL = "https://ibb.co/jPQv7mYn"
BARRACKS_IMAGE_URL = "https://ibb.co/cSVxP3kh"
DUNGEON_IMAGE_URL = "https://ibb.co/yBckMfHf"
ALTAR_IMAGE_URL = "https://ibb.co/S7c5NL6v"
REFUGEE_CAMP_IMAGE_URL = "https://ibb.co/qY2W2TpR"
MERCENARY_GUILD_IMAGE_URL = "https://ibb.co/dwV8jyks"
FREE_ROLLS_IMAGE_URL = "https://ibb.co/Zpc9ntMB"
BATTLES_IMAGE_URL = "https://ibb.co/Zpc9ntMB"

ANTI_SHOOTER_CREATURES = [69, 114]
GOLD_DIGGER_CARD_IDS = [180, 181]
DOUBLE_COUNTERATTACK_CREATURE_ID = 42
INFINITE_COUNTERATTACK_CREATURE_IDS = [87, 148]
ENTANGLING_CREATURE_IDS = [61, 106]

FREE_ROLLS_PACKAGE = {
    "id": "free_rolls_package",
    "title": "15 наймов",
    "price": 35000,
    "rolls": 15,
}

MAX_ARMY_SQUADS = 5

SACRIFICE_REWARDS = {
    "UpgradeT1": {"cents": 100, "free_rolls": 0},  # 200/2 = 100
    "UpgradeT2": {"cents": 250, "free_rolls": 0},  # 500/2 = 250
    "UpgradeT3": {"cents": 500, "free_rolls": 0},  # 1000/2 = 500
    "UpgradeT4": {"cents": 1000, "free_rolls": 0},  # 2000/2 = 1000
    "UpgradeT5": {"cents": 0, "free_rolls": 3},
    "UpgradeT6": {"cents": 0, "free_rolls": 7},
    "UpgradeT7": {"cents": 0, "free_rolls": 15},
    "T8": {"cents": 0, "free_rolls": 25}
}

# Бонусы по редкостям


RARITY_BONUSES = {
    "T1": {"cents": 100, "points": 100, "probability": 53.16},
    "T2": {"cents": 250, "points": 250, "probability": 20.8},
    "T3": {"cents": 500, "points": 500, "probability": 11.8},
    "T4": {"cents": 1000, "points": 1000, "probability": 6.91},
    "T5": {"cents": 2000, "points": 2000, "probability": 4.51},
    "T6": {"cents": 5000, "points": 5000, "probability": 1.96},
    "T7": {"cents": 10000, "points": 10000, "probability": 0.78},
    "T8": {"cents": 50000, "points": 50000, "probability": 0.08},
    "UpgradeT1": {"cents": 200, "points": 200, "probability": 100},
    "UpgradeT2": {"cents": 500, "points": 500, "probability": 100},
    "UpgradeT3": {"cents": 1000, "points": 1000, "probability": 100},
    "UpgradeT4": {"cents": 2000, "points": 2000, "probability": 100},
    "UpgradeT5": {"cents": 4000, "points": 4000, "probability": 100},
    "UpgradeT6": {"cents": 10000, "points": 10000, "probability": 100},
    "UpgradeT7": {"cents": 20000, "points": 20000, "probability": 100},
    "T3 special": {"cents": 0, "points": 0, "probability": 0},
    "T1 (HoMM4)": {"cents": 0, "points": 0, "probability": 0},
    "T3 (HoMM4)": {"cents": 0, "points": 0, "probability": 0},
    "T5 (HoMM4)": {"cents": 0, "points": 0, "probability": 0},
    "T7 (HoMM4)": {"cents": 0, "points": 0, "probability": 0},
    "T8 (HoMM4)": {"cents": 0, "points": 0, "probability": 0},
    "T4 (HoMM4)": {"cents": 0, "points": 0, "probability": 0},
    "T4 (Olden era)": {"cents": 0, "points": 0, "probability": 0},
}


# Настройка логирования


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot_errors.log"), logging.StreamHandler()],
)


logger = logging.getLogger(__name__)


# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====


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

            if "achievements" not in data:
                data["achievements"] = {
                    "Замок": {"cards": [], "reward_claimed": False},
                    "Оплот": {"cards": [], "reward_claimed": False},
                    "Башня": {"cards": [], "reward_claimed": False},
                    "Инферно": {"cards": [], "reward_claimed": False},
                    "Некрополис": {"cards": [], "reward_claimed": False},
                    "Темница": {"cards": [], "reward_claimed": False},
                    "Цитадель": {"cards": [], "reward_claimed": False},
                    "Крепость": {"cards": [], "reward_claimed": False},
                    "Сопряжение": {"cards": [], "reward_claimed": False},
                    "Фабрика": {"cards": [], "reward_claimed": False},
                    "Могущество_царя_драконов": {"cards": [], "reward_claimed": False},
                }

            if "mercenary_guild" not in data:
                data["mercenary_guild"] = {
                    "creatures": [],  # Список существ для продажи
                    "max_slots": 4    # Максимум 4 существа
                }

            if "pending_battles" not in data:
                data["pending_battles"] = {}

            if "active_battles" not in data:
                data["active_battles"] = {}

            # Добавьте в load_data() после загрузки данных:
            for card in data.get("cards", []):
                if "attack" not in card:
                    card["attack"] = 0
                if "defense" not in card:
                    card["defense"] = 0
                if "damage" not in card:
                    card["damage"] = 0
                if "health" not in card:
                    card["health"] = 0
                if "speed" not in card:
                    card["speed"] = 0
            
            for user_id, user_data in data.get("users", {}).items():
                if "last_card_time" not in user_data:
                    user_data["last_card_time"] = 0
                if "free_rolls" not in user_data:
                    user_data["free_rolls"] = 0
                if "last_dice_time" not in user_data:
                    user_data["last_dice_time"] = 0
                if "casino_attempts" not in user_data:
                    user_data["casino_attempts"] = 10
                if "last_casino_reset" not in user_data:
                    user_data["last_casino_reset"] = 0
                # ⭐ ДОБАВЛЯЕМ ОТСЛЕЖИВАНИЕ ДОСТИЖЕНИЙ ⭐
                if "claimed_achievements" not in user_data:
                    user_data["claimed_achievements"] = []
                if "notification_sent" not in user_data:
                    user_data["notification_sent"] = False
                if "used_promo_codes" not in user_data:
                    user_data["used_promo_codes"] = []
                if "refugee_camp_last_reset" not in user_data:
                    user_data["refugee_camp_last_reset"] = 0  # ← Время последнего сброса
                if "refugee_camp_offered_card" not in user_data:
                    user_data["refugee_camp_offered_card"] = None
                if "refugee_camp_purchased" not in user_data:
                    user_data["refugee_camp_purchased"] = False
                if "army_squads" not in user_data:
                    user_data["army_squads"] = []  # Список из 5 отрядов
                if "army_page" not in user_data:
                    user_data["army_page"] = 0
                if "battle_level" not in user_data:
                    user_data["battle_level"] = 0  # ← Уровень боевого опыта
                if "battle_experience" not in user_data:
                    user_data["battle_experience"] = 0  # Боевой опыт за сражения
                if "win_streak" not in user_data:
                    user_data["win_streak"] = 0
                if "battle_challenges_today" not in user_data:
                    user_data["battle_challenges_today"] = 0  # Количество вызовов сегодня
                if "battle_challenges_last_reset" not in user_data:
                    user_data["battle_challenges_last_reset"] = 0  # Время последнего сброса
                if "gold_digger_last_income" not in user_data:
                    user_data["gold_digger_last_income"] = ""
            return data
            
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {e}")
            return {
                "users": {},
                "cards": [],
                "season": 1,
                "admins": [INITIAL_ADMIN_ID],
                "active_trades": {},
                "mercenary_guild": {
                    "creatures": [],
                    "max_slots": 4
                },
                "achievements": {
                    "Замок": {"cards": [], "reward_claimed": False},
                    "Оплот": {"cards": [], "reward_claimed": False},
                    "Башня": {"cards": [], "reward_claimed": False},
                    "Инферно": {"cards": [], "reward_claimed": False},
                    "Некрополис": {"cards": [], "reward_claimed": False},
                    "Темница": {"cards": [], "reward_claimed": False},
                    "Цитадель": {"cards": [], "reward_claimed": False},
                    "Крепость": {"cards": [], "reward_claimed": False},
                    "Сопряжение": {"cards": [], "reward_claimed": False},
                }
            }
    
    return {
        "users": {},
        "cards": [],
        "season": 1,
        "admins": [INITIAL_ADMIN_ID],
        "active_trades": {},
        "mercenary_guild": {
            "creatures": [],
            "max_slots": 4
        },
        "achievements": {
            "Замок": {"cards": [], "reward_claimed": False},
            "Оплот": {"cards": [], "reward_claimed": False},
            "Башня": {"cards": [], "reward_claimed": False},
            "Инферно": {"cards": [], "reward_claimed": False},
            "Некрополис": {"cards": [], "reward_claimed": False},
            "Темница": {"cards": [], "reward_claimed": False},
            "Цитадель": {"cards": [], "reward_claimed": False},
            "Крепость": {"cards": [], "reward_claimed": False},
            "Сопряжение": {"cards": [], "reward_claimed": False},
        }
    }

def check_casino_reset(user_data: Dict) -> None:
    """Проверяет и сбрасывает попытки казино в полночь по МСК."""

    import datetime

    # Получаем текущее время по МСК

    msk_tz = datetime.timezone(datetime.timedelta(hours=3))

    now_msk = datetime.datetime.now(msk_tz)

    # Получаем дату последнего сброса

    last_reset = user_data.get("last_casino_reset", 0)

    # Если сегодня ещё не сбрасывали

    if (
        last_reset == 0
        or now_msk.day != datetime.datetime.fromtimestamp(last_reset, msk_tz).day
    ):

        user_data["casino_attempts"] = 10

        user_data["last_casino_reset"] = int(now_msk.timestamp())


def save_data(data: Dict[str, Any]) -> None:
    """Сохраняет данные в файл."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()  # ⭐ СБРАСЫВАЕМ БУФЕР ⭐
            os.fsync(f.fileno())  # ⭐ ГАРАНТИРУЕМ ЗАПИСЬ НА ДИСК ⭐
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

    nav_buttons = [
        InlineKeyboardButton("<", callback_data=f"card_prev_{current_index}"),
        InlineKeyboardButton(
            f"{current_index + 1}/{total_cards}", callback_data="card_info"
        ),
        InlineKeyboardButton(">", callback_data=f"card_next_{current_index}"),
    ]

    return InlineKeyboardMarkup([nav_buttons])


def determine_media_type(url: str, rarity: str) -> str:
    """Определяет тип медиа на основе URL и редкости."""

    if rarity in AUTO_ANIMATED_RARITIES:

        return "animation"

    if any(url.lower().endswith(ext) for ext in ANIMATED_FORMATS):

        return "animation"

    return "photo"


def generate_card_caption(
    card: Dict,
    user_data: Optional[Dict] = None,  # ← ИСПРАВЛЕНО: был "user_ Optional"
    count: int = 1,
    show_bonus: bool = False,
) -> str:  # ← ИСПРАВЛЕНО: скобка и -> str на одной строке
    """Генерирует описание карточки с количеством дубликатов."""
    
    # ⭐ БАЗОВЫЙ CAPTION ⭐
    if user_data is None:
        # Если нет данных пользователя — показываем минимальную информацию
        caption = f"⚔️ {card['title']}\n🌟 Редкость: {card['rarity']}"
    else:
        # Если есть данные пользователя — показываем полную информацию
        caption = f"⚔️ Вы наняли существо\n{card['title']}\nРедкость: {card['rarity']}"
    
    # ⭐ ДОБАВЛЯЕМ ФРАКЦИЮ ⭐
    if card.get("faction"):
        caption += f"\nФракция: {card['faction']}"
    
    # ⭐ ДОБАВЛЯЕМ АТРИБУТЫ ⭐
    if card.get("attack") or card.get("defense") or card.get("damage") or card.get("health") or card.get("speed"):
        if card.get("attack"):
            caption += f"\n⚔️ {card['attack']}"
        if card.get("defense"):
            caption += f"\n🛡️ {card['defense']}"
        if card.get("damage"):
            caption += f"\n💥 {format_damage_display(card['damage'])}"
        if card.get("health"):
            caption += f"\n❤️ {card['health']}"
        if card.get("speed"):
            caption += f"\n👟 {card['speed']}"
    
    # ⭐ ПОКАЗЫВАЕМ БОНУСЫ ТОЛЬКО ПРИ ПОЛУЧЕНИИ НОВОЙ КАРТЫ ⭐
    if show_bonus and user_data is not None:
        bonus = RARITY_BONUSES.get(card["rarity"], {"cents": 0, "points": 0})
        caption += f"\n\n💰 +{bonus['cents']} золота\n💥 +{bonus['points']} опыта"
    
    # ⭐ ДОБАВЛЯЕМ КОЛИЧЕСТВО, ЕСЛИ ЕСТЬ ДУБЛИКАТЫ ⭐
    if count > 1:
        caption += f"\n📦 Количество: {count} шт."
    
    # ⭐ ДОБАВЛЯЕМ ОПЫТ ТОЛЬКО ЕСЛИ ЕСТЬ user_data ⭐
    if user_data is not None:
        caption += (
            f"\n\nОпыта в этом сезоне: {user_data.get('season_points', 0)}"
            f"\nОпыта за все время: {user_data.get('total_points', 0)}"
        )
    
    return caption


async def send_card(
    update_or_chat_id: Update,
    card: Dict,
    context: ContextTypes.DEFAULT_TYPE,
    caption: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    chat_id: Optional[int] = None,
) -> None:
    """Отправляет карточку в зависимости от типа медиа."""

    if isinstance(update_or_chat_id, Update):

        chat_id = update_or_chat_id.effective_chat.id

    if chat_id is None:

        return

    if card.get("media_type") == "animation":

        await context.bot.send_animation(
            chat_id=chat_id,
            animation=card["image_url"],
            caption=caption,
            reply_markup=reply_markup,
        )

    else:

        await context.bot.send_photo(
            chat_id=chat_id,
            photo=card["image_url"],
            caption=caption,
            reply_markup=reply_markup,
        )


async def edit_card_message(
    query, card: Dict, caption: str, reply_markup: InlineKeyboardMarkup
) -> None:
    """Редактирует сообщение с карточкой."""

    if card.get("media_type") == "animation":

        media = InputMediaAnimation(media=card["image_url"], caption=caption)

    else:

        media = InputMediaPhoto(media=card["image_url"], caption=caption)

    await query.edit_message_media(media=media, reply_markup=reply_markup)


# ===== КОМАНДЫ ПОЛЬЗОВАТЕЛЯ =====


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    try:
        keyboard = [
            [KeyboardButton("⚔️ Нанять существо")],
            [KeyboardButton("🏰 Город")],
            [KeyboardButton("🌲 Лес"), KeyboardButton("🍺 Таверна")],
            [KeyboardButton("🦇 Подземелье")],
            [KeyboardButton("⚔️ Сражения")], 
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Добро пожаловать! Используйте кнопки ниже:", reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Ошибка в start: {e}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список команд."""
    try:
        user_id = str(update.effective_user.id)
        # Безопасная проверка админа
        try:
            data = load_data()
            admin_list = data.get("admins", [])
            admin = user_id in admin_list
        except Exception as e:
            logger.error(f"Ошибка проверки админа: {e}")
            admin = False
        
        response = "📜 Доступные команды:\n\n"
        
        # Основные команды
        response += "🎮 Основные команды:\n"
        response += "⚔️ Нанять существо - нанять существо\n"
        response += "🛡 Казарма - посмотреть нанятых существ\n"
        response += "👑 Мой герой - статистика героя\n"
        response += "🏆 Топ героев - рейтинг по опыту\n"
        response += "🎲 Бросить кубик - получить бесплатные наймы\n"
        response += "🍺 Таверна - казино, трейд и другие игры\n"
        response += "🔨 Крафт - скрафтить новое существо из 2 дубликатов\n"
        response += "🔄 Трейд - обмен картами с героями\n"
        response += "🏆 Достижения - награды за сбор карт фракций\n\n"
        
        # Команды для всех
        response += "📝 Команды:\n"
        response += "/start - начать работу с ботом\n"
        response += "/help - показать это сообщение\n"
        response += "/profile - мой профиль\n"
        response += "/dice - бросить кубик\n"
        response += "/craft - крафт существ\n"
        response += "/top - топ героев\n"
        response += "/trade - трейд существ\n"
        response += "/trade_accept - принять трейд\n"
        response += "/trade_decline - отклонить трейд\n"
        response += "/promo [КОД] - активировать промокод\n\n"
        
        # Админ-команды
        if admin:
            response += "⚙️ Админ-команды:\n"
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
            response += "/set_achievement_cards [Фракция] [ID...] - настроить достижение\n"
            response += "/mercenary_add [ID] [цена] - добавить в Гильдию Наёмников\n"
            response += "/mercenary_remove [ID] - удалить из Гильдии\n"
            response += "/mercenary_list - список Гильдии\n"
            response += "/mercenary_price [ID] [цена] - обновить цену\n\n"
        
        response += "💡 Нужна помощь?\n"
        response += "Напишите администратору бота."
        
        # ⭐ ИСПРАВЛЕНИЕ: УБРАЛИ parse_mode="Markdown" ⭐
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
                rarity = card.get("rarity", "T1")
                if rarity not in rarity_cards:
                    rarity_cards[rarity] = []
                rarity_cards[rarity].append((card_id, card_counts[card_id]))
        
        # ⭐ СЧИТАЕМ КАРТЫ ПО ФРАКЦИЯМ ⭐
        faction_cards = {}
        for card_id in user_card_ids:
            card = find_card_by_id(card_id, data["cards"])
            if card and card.get("faction"):
                faction = card["faction"]
                if faction not in faction_cards:
                    faction_cards[faction] = set()
                faction_cards[faction].add(card_id)
        
        if not rarity_cards:
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text("У вас пока нет существ!")
            else:
                await update.message.reply_text("У вас пока нет существ!")
            return
        
        # ⭐ СОЗДАЁМ МЕНЮ ВЫБОРА СПОСОБА ПРОСМОТРА ⭐
        keyboard = [
            [InlineKeyboardButton("📊 По редкости", callback_data="barracks_rarity")],
            [InlineKeyboardButton("⚔️ По фракции", callback_data="barracks_faction")],
            [InlineKeyboardButton("📋 Все существа", callback_data="barracks_all")],
        ]
        
        # ⭐ ПРОВЕРКА: callback или сообщение ⭐
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            # ⭐ УДАЛЯЕМ СТАРОЕ СООБЩЕНИЕ И ОТПРАВЛЯЕМ НОВОЕ ⭐
            try:
                await query.message.delete()
            except:
                pass
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=BARRACKS_IMAGE_URL,  # ← Изображение Казармы
                caption=(
                    "🛡 Казарма\n\n"
                    "Выберите способ просмотра:\n"
                    "• 📊 По редкости\n"
                    "• ⚔️ По фракции\n"
                    "• 📋 Все существа"
                ),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=BARRACKS_IMAGE_URL,  # ← Изображение Казармы
                caption=(
                    "🛡 Казарма\n\n"
                    "Выберите способ просмотра:\n"
                    "• 📊 По редкости\n"
                    "• ⚔️ По фракции\n"
                    "• 📋 Все существа"
                ),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
    except Exception as e:
        logger.error(f"Ошибка при показе меню существ: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("Произошла ошибка")
            
async def show_cards_by_faction(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    faction: str,
    start_index: int = 0
) -> None:
    """Показывает существ конкретной фракции."""
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
        
        faction_cards = []
        for card_id, count in card_counts.items():
            card = find_card_by_id(card_id, data["cards"])
            if card and card.get("faction") == faction:
                faction_cards.append((card_id, count))
        
        if not faction_cards:
            if query:
                await query.edit_message_text(f"У вас нет существ фракции {faction}!")
            else:
                await update.message.reply_text(f"У вас нет существ фракции {faction}!")
            return
        
        faction_cards.sort(key=lambda x: x[0])
        total_cards = len(faction_cards)
        
        if start_index < 0:
            start_index = 0
        elif start_index >= total_cards:
            start_index = total_cards - 1
        
        card_id, count = faction_cards[start_index]
        card = find_card_by_id(card_id, data["cards"])
        
        if not card:
            if query:
                await query.edit_message_text("Ошибка: существо не найдено")
            else:
                await update.message.reply_text("Ошибка: существо не найдено")
            return
        
        nav_buttons = []
        if start_index > 0:
            nav_buttons.append(InlineKeyboardButton("<", callback_data=f"barracks_faction_nav_{faction}_{start_index - 1}"))
        nav_buttons.append(InlineKeyboardButton(f"{start_index + 1}/{total_cards}", callback_data="card_info"))
        if start_index < total_cards - 1:
            nav_buttons.append(InlineKeyboardButton(">", callback_data=f"barracks_faction_nav_{faction}_{start_index + 1}"))
        
        keyboard = [nav_buttons]
        keyboard.append([
            InlineKeyboardButton("⚔️ Назад в казарму", callback_data="mycards_back_to_rarities")
        ])
        
        caption = generate_card_caption(card, user_data, count=count, show_bonus=False)
        
        if query:
            try:
                media = InputMediaPhoto(media=card["image_url"], caption=caption)
                await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception as edit_error:
                logger.error(f"Ошибка редактирования: {edit_error}")
                try:
                    await query.message.delete()
                except:
                    pass
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=card["image_url"],
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            await send_card(update, card, context, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        logger.error(f"Ошибка при показе существ фракции {faction}: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("Произошла ошибка")

async def show_faction_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню выбора фракции."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)

        if not user_data or not user_data.get("cards"):
            await query.edit_message_text("❌ У вас пока нет существ!")
            return
        
        user_card_ids = user_data["cards"]
        
        # ⭐ СЧИТАЕМ КАРТЫ ПО ФРАКЦИЯМ ⭐
        faction_cards = {}
        for card_id in user_card_ids:
            card = find_card_by_id(card_id, data["cards"])
            if card and card.get("faction"):
                faction = card["faction"]
                if faction not in faction_cards:
                    faction_cards[faction] = set()
                faction_cards[faction].add(card_id)

        if not faction_cards:
            await query.edit_message_text("❌ У вас нет существ с фракциями!")
            return
        
        # Список всех фракций
        all_factions = [
            "Замок", "Оплот", "Башня", "Инферно",
            "Некрополис", "Темница", "Цитадель", "Крепость", "Сопряжение", "Причал", "Фабрика", "Кронверк","Нейтральный"
        ]
        
        # Создаём клавиатуру
        keyboard = []
        for faction in all_factions:
            if faction in faction_cards:
                count = len(faction_cards[faction])
                keyboard.append([
                    InlineKeyboardButton(
                        f"⚔️ {faction} ({count} шт.)",
                        callback_data=f"barracks_faction_select_{faction}"
                    )
                ])
        
        # Кнопка "Назад"
        keyboard.append([
            InlineKeyboardButton("🔙 Назад в казарму", callback_data="barracks_back")
        ])
        
        try:
            await query.message.delete()
        except:
            pass
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="⚔️ Выберите фракцию:\nПросмотрите существ по принадлежности к фракции:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Ошибка в show_faction_menu: {e}")
        await query.answer("Произошла ошибка", show_alert=True)


async def show_cards_by_rarity(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    rarity: str,
    start_index: int = 0
) -> None:
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
            if query:
                await query.edit_message_text(f"У вас нет существ редкости {rarity}!")
            else:
                await update.message.reply_text(f"У вас нет существ редкости {rarity}!")
            return
        
        # Сортируем карты по ID
        rarity_cards.sort(key=lambda x: x[0])
        total_cards = len(rarity_cards)
        
        # Обработка навигации
        if start_index < 0:
            start_index = 0
        elif start_index >= total_cards:
            start_index = total_cards - 1
        
        card_id, count = rarity_cards[start_index]
        card = find_card_by_id(card_id, data["cards"])
        
        if not card:
            if query:
                await query.edit_message_text("Ошибка: существо не найдено")
            else:
                await update.message.reply_text("Ошибка: существо не найдено")
            return
        
        # Создаём клавиатуру навигации
        nav_buttons = []
        if start_index > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    "<",
                    callback_data=f"mycards_nav_{rarity}_{start_index - 1}"
                )
            )
        nav_buttons.append(
            InlineKeyboardButton(
                f"{start_index + 1}/{total_cards}",
                callback_data="card_info"
            )
        )
        if start_index < total_cards - 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    ">",
                    callback_data=f"mycards_nav_{rarity}_{start_index + 1}"
                )
            )
        
        # ⭐ КНОПКА "НАЗАД" ⭐
        keyboard = [nav_buttons]
        keyboard.append([
            InlineKeyboardButton(
                "🔙 Назад в казарму",
                callback_data="mycards_back_to_rarities"
            )
        ])
        
        # Генерируем описание
        caption = generate_card_caption(card, user_data, count=count, show_bonus=False)
        
        if query:
            try:
                media = InputMediaPhoto(media=card["image_url"], caption=caption)
                await query.edit_message_media(
                    media=media,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as edit_error:
                logger.error(f"Ошибка редактирования: {edit_error}")
                try:
                    await query.message.delete()
                except:
                    pass
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=card["image_url"],
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            await send_card(update, card, context, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        logger.error(f"Ошибка при показе карт редкости {rarity}: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("Произошла ошибка")
            
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
                rarity = card.get("rarity", "T1")
                if rarity not in rarity_cards:
                    rarity_cards[rarity] = []
                rarity_cards[rarity].append((card_id, card_counts[card_id]))
        
        if not rarity_cards:
            await query.edit_message_text("У вас пока нет существ!")
            return
        
        keyboard = []
        for rarity in ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"]:
            if rarity in rarity_cards:
                keyboard.append([
                    InlineKeyboardButton(rarity, callback_data=f"barracks_rarity_select_{rarity}")
                ])
        
        upgrade_rarities = [r for r in rarity_cards.keys() if r.startswith("Upgrade")]
        if upgrade_rarities:
            keyboard.append([])
            for rarity in sorted(upgrade_rarities):
                keyboard.append([
                    InlineKeyboardButton(rarity, callback_data=f"barracks_rarity_select_{rarity}")
                ])
        
        keyboard.append([
            InlineKeyboardButton("🔙 Назад в казарму", callback_data="barracks_back")
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
        
        # ⭐ НОВЫЕ КНОПКИ КАЗАРМЫ (barracks_) ⭐
        
        # Кнопка "По редкости" → показать меню редкостей
        if query.data == "barracks_rarity":
            await show_rarity_menu(update, context)
            return
        
        # Кнопка "По фракции" → показать меню фракций
        elif query.data == "barracks_faction":
            await show_faction_menu(update, context)
            return
        
        # Кнопка "Все существа" → показать все карты с навигацией
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
            
            card = find_card_by_id(unique_card_ids[0], data["cards"])
            if not card:
                await query.edit_message_text("Ошибка: существо не найдено")
                return
            
            # ⭐ ИСПРАВЛЕНИЕ: создаём клавиатуру сразу с кнопкой "Назад" ⭐
            nav_buttons = [
                InlineKeyboardButton("<", callback_data=f"card_prev_0"),
                InlineKeyboardButton(f"1/{len(unique_card_ids)}", callback_data="card_info"),
                InlineKeyboardButton(">", callback_data=f"card_next_0"),
            ]
            keyboard = InlineKeyboardMarkup([
                nav_buttons,
                [InlineKeyboardButton("🔙 Назад в казарму", callback_data="barracks_back")]
            ])
            
            count = card_counts[card["id"]]
            caption = generate_card_caption(card, user_data, count=count, show_bonus=False)
            
            try:
                media = InputMediaPhoto(media=card["image_url"], caption=caption)
                await query.edit_message_media(media=media, reply_markup=keyboard)
            except Exception as edit_error:
                logger.error(f"Ошибка редактирования: {edit_error}")
                try:
                    await query.message.delete()
                except:
                    pass
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=card["image_url"],
                    caption=caption,
                    reply_markup=keyboard
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
        
        # ⭐ СТАРАЯ ЛОГИКА (mycards_) ⭐
        
        # Кнопка "Все карты" (старая)
        elif query.data == "mycards_all":
            if not user_data or not user_data.get("cards"):
                await query.edit_message_text("У вас пока нет существ!")
                return
            
            user_card_ids = user_data["cards"]
            card_counts = Counter(user_card_ids)
            unique_card_ids = list(card_counts.keys())
            
            if not unique_card_ids:
                await query.edit_message_text("У вас пока нет существ!")
                return
            
            card = find_card_by_id(unique_card_ids[0], data["cards"])
            if not card:
                await query.edit_message_text("Ошибка: существо не найдено")
                return
            
            # ⭐ ИСПРАВЛЕНИЕ: создаём клавиатуру сразу с кнопкой "Назад" ⭐
            nav_buttons = [
                InlineKeyboardButton("<", callback_data=f"card_prev_0"),
                InlineKeyboardButton(f"1/{len(unique_card_ids)}", callback_data="card_info"),
                InlineKeyboardButton(">", callback_data=f"card_next_0"),
            ]
            keyboard = InlineKeyboardMarkup([
                nav_buttons,
                [InlineKeyboardButton("🔙 Назад к редкостям", callback_data="mycards_back_to_rarities")]
            ])
            
            count = card_counts[card["id"]]
            caption = generate_card_caption(card, user_data, count=count, show_bonus=False)
            
            try:
                media = InputMediaPhoto(media=card["image_url"], caption=caption)
                await query.edit_message_media(media=media, reply_markup=keyboard)
            except Exception as edit_error:
                logger.error(f"Ошибка редактирования: {edit_error}")
                try:
                    await query.message.delete()
                except:
                    pass
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=card["image_url"],
                    caption=caption,
                    reply_markup=keyboard
                )
            return
        
        # Кнопка "Назад к редкостям" (старая)
        elif query.data == "mycards_back_to_rarities":
            try:
                await query.message.delete()
            except:
                pass
            await show_user_cards(update, context)
            return
        
        # Выбор редкости (старая логика)
        elif query.data.startswith("mycards_rarity_"):
            rarity = query.data.replace("mycards_rarity_", "")
            await show_cards_by_rarity(update, context, rarity, start_index=0)
            return
        
        # Навигация по картам редкости (старая логика)
        elif query.data.startswith("mycards_nav_"):
            parts = query.data.replace("mycards_nav_", "").split("_")
            rarity = parts[0]
            index = int(parts[1]) if len(parts) > 1 else 0
            await show_cards_by_rarity(update, context, rarity, start_index=index)
            return
        
        # ⭐ НАВИГАЦИЯ ПО ФРАКЦИЯМ (barracks_) ⭐
        elif query.data.startswith("barracks_faction_"):
            if query.data.startswith("barracks_faction_nav_"):
                # Навигация внутри фракции
                parts = query.data.replace("barracks_faction_nav_", "").split("_")
                faction = parts[0]
                index = int(parts[1]) if len(parts) > 1 else 0
                await show_cards_by_faction(update, context, faction, start_index=index)
            elif query.data.startswith("barracks_faction_select_"):
                # Выбор фракции
                faction = query.data.replace("barracks_faction_select_", "")
                await show_cards_by_faction(update, context, faction, start_index=0)
            elif query.data == "barracks_back_to_factions":
                # Назад к списку фракций
                await show_faction_menu(update, context)
            return
        
        # ⭐ НАВИГАЦИЯ ПО РЕДКОСТЯМ (barracks_) ⭐
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
        
    except Exception as e:
        logger.error(f"Ошибка в mycards_callback: {e}")
        await query.answer("Произошла ошибка", show_alert=True)

async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает профиль пользователя."""
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
        
        # Считаем уникальные карты пользователя
        user_card_ids = user_data.get("cards", [])
        unique_cards = len(set(user_card_ids))
        
        # Считаем общее количество доступных карт в игре
        total_available_cards = len(
            [card for card in data["cards"] if card.get("available", True)]
        )
        
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
            "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8",
            "UpgradeT1", "UpgradeT2", "UpgradeT3", "UpgradeT4",
            "UpgradeT5", "UpgradeT6", "UpgradeT7",
        ]:
            if rarity in rarity_stats:
                rarity_text += f"• {rarity}: {rarity_stats[rarity]} шт.\n"
        
        if not rarity_text:
            rarity_text = "Пока нет существ\n"
        
        claimed_count = len(user_data.get("claimed_achievements", []))
        
        profile_text = (
            f"👤 Профиль героя\n\n"
            f"🆔 ID: `{user_id}`\n"
            f"💰 Золото: {user_data.get('cents', 0)}\n"
            f"💥 Опыта (сезон): {user_data.get('season_points', 0)}\n"
            f"💎 Опыта (всего): {user_data.get('total_points', 0)}\n\n"
            f"🐦‍🔥 Коллекция:\n"
            f"📦 Собрано существ: {unique_cards}/{total_available_cards}\n"
            f"📊 Заполненность: {collection_percent}%\n"
            f"🔢 Всего получено: {len(user_card_ids)} (с дубликатами)\n\n"
            f"📈 По редкостям:\n"
            f"{rarity_text}\n"
            f"🎲 Бесплатные наймы: {user_data.get('free_rolls', 0)}\n"
            f"🏆 Достижения: {claimed_count}/9\n"
        )
        
        keyboard = [[InlineKeyboardButton("🏆 Достижения", callback_data="achievements_menu")]]
        
        # ⭐ ОТПРАВЛЯЕМ В ЗАВИСИМОСТИ ОТ ТИПА ⭐
        if is_callback:
            # Удаляем старое сообщение и отправляем новое
            try:
                await query.message.delete()
            except:
                pass
            await context.bot.send_message(
                chat_id=chat_id,
                text=profile_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode = "Markdown"
            )
        else:
            await update.message.reply_text(
                profile_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode = "Markdown"
            )
        
    except Exception as e:
        logger.error(f"Ошибка показа профиля: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("❌ Произошла ошибка при загрузке профиля")
            

async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок профиля."""
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "achievements_menu":
            await achievements_menu(update, context)
        elif query.data == "profile_back":
            await my_profile(update, context)  # ← Вызывает универсальную my_profile
        elif query.data.startswith("achievement_claim_"):
            await claim_achievement(update, context)
        elif query.data == "achievement_claimed":
            await query.answer("✅ Вы уже получили эту награду!", show_alert=True)
        elif query.data == "achievement_progress":
            await query.answer("📊 Собирайте существ для завершения!", show_alert=True)
        
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

            new_index = (
                (current_index - 1) % total_cards
                if action == "prev"
                else (current_index + 1) % total_cards
            )

            card = find_card_by_id(unique_card_ids[new_index], data["cards"])

            if not card:

                await query.edit_message_text("Карточка не найдена!")

                return

            count = card_counts[card["id"]]

            caption = generate_card_caption(
                card, user_data, count=count, show_bonus=False
            )

            nav_buttons = [
                InlineKeyboardButton("<", callback_data=f"card_prev_{new_index}"),
                InlineKeyboardButton(f"{new_index + 1}/{total_cards}", callback_data="card_info"),
                InlineKeyboardButton(">", callback_data=f"card_next_{new_index}"),
            ]
            keyboard = InlineKeyboardMarkup([
                nav_buttons,
                [InlineKeyboardButton("🔙 Назад в казарму", callback_data="barracks_back")]
            ])

            # ⭐ ДОБАВЬТЕ ЛОГИРОВАНИЕ ⭐

            logger.info(
                f"Попытка показать существо #{card['id']}: {card['image_url'][:100]}"
            )

            try:

                media = InputMediaPhoto(media=card["image_url"], caption=caption)

                await query.edit_message_media(media=media, reply_markup=keyboard)

            except Exception as edit_error:

                logger.error(
                    f"❌ Ошибка редактирования существа #{card['id']}: {edit_error}"
                )

                logger.error(f"URL: {card['image_url']}")

                # Отправляем как новое сообщение

                try:

                    await query.message.delete()

                except:

                    pass

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
    """


    Двухэтапный выбор:


    1. Выбираем редкость по фиксированному шансу


    2. Из всех карт этой редкости выбираем случайную


    """

    if not cards:

        return None

    # Группируем карты по редкостям

    cards_by_rarity = {}

    for card in cards:

        rarity = card.get("rarity", "T1")

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

    # Этап 1: Выбираем редкость по фиксированному шансу

    total_weight = sum(weights)

    if total_weight == 0:

        return None

    # Нормализуем веса до 100%

    normalized_weights = [w / total_weight for w in weights]

    # Выбираем редкость

    chosen_rarity = random.choices(available_rarities, weights=normalized_weights, k=1)[
        0
    ]

    # Этап 2: Выбираем случайную карту из этой редкости

    rarity_cards = cards_by_rarity[chosen_rarity]

    return random.choice(rarity_cards)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений (кнопки)."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)

         # ⭐ ПРОВЕРКА ЗОЛОТОИСКАТЕЛЕЙ (как с казино) ⭐
        if user_data:
            await check_gold_digger_reset(user_id, user_data, data, context)
            save_data(data)

        text = update.message.text
        
        # ⭐ ПРОВЕРКА: если пользователь в шаге выбора партнёра для трейда ⭐
        if user_id in context.user_data:
            trade_info = context.user_data[user_id]
            step = trade_info.get("step", "")
            if step in ["select_partner", "search_mode"]:
                await process_partner_selection(update, context)
                return
        
        # ⭐ КНОПКА "🔙 НАЗАД В МЕНЮ" ⭐
        if text == "🔙 Назад в меню":
            # ⭐ СБРАСЫВАЕМ СОСТОЯНИЕ ПОИСКА ПРОТИВНИКА ⭐
            if user_id in context.user_data:
                if "step" in context.user_data[user_id]:
                    if context.user_data[user_id]["step"] == "battle_find_opponent":
                        del context.user_data[user_id]["step"]
                        logger.info(f"Сброшен поиск противника для пользователя {user_id}")
            # Возврат в главное меню
            keyboard = [
                [KeyboardButton("⚔️ Нанять существо")],
                [KeyboardButton("🏰 Город")],
                [KeyboardButton("🌲 Лес"), KeyboardButton("🍺 Таверна")],
                [KeyboardButton("🦇 Подземелье")],
                [KeyboardButton("⚔️ Сражения")],
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "🏠 Главное меню\n\nДобро пожаловать! Используйте кнопки ниже:",
                reply_markup=reply_markup
            )
            return
        
        # ⭐ КНОПКА "🌲 ЛЕС" ⭐
        elif text == "🌲 Лес":
            await forest_menu(update, context)
            return

        elif text == "🏕️ Лагерь Беженцев":
            await refugee_camp(update, context)
            return

        elif text.startswith("💰 Купить за ") and "золота" in text:
            await buy_refugee_creature(update, context)
            return

        elif text == "🏰 Город":
            await city_menu(update, context)
            return

        elif text == "🦇 Подземелье":
            await dungeon_menu(update, context)
            return

        elif text == "🩸 Жертвенный алтарь":
            await sacrifice_altar(update, context)
            return

        elif text == "🪓 Гильдия Наёмников":
            await mercenary_guild(update, context)
            return

        elif text == "⚔️ Сражения":
            await battles_menu(update, context)
            return

        elif text == "🛡️ Моя Армия":
            await my_army(update, context)
            return

        elif text == "🏆 Топ сражений":
            await top_battles(update, context)

        elif text == "🔙 Назад в Подземелье":
            await dungeon_menu(update, context)
            return

        elif text == "🔙 Назад в Сражения":
            await battles_menu(update, context)
            return

        # ⭐ КНОПКА "🔙 НАЗАД В ТАВЕРНУ" ⭐
        elif text == "🔙 Назад в Таверну":
            await mini_games(update, context)
            return

        elif text == "🔙 Назад в Лес":
            await forest_menu(update, context)
            return

        elif text == "🏰 Форт на холме":
            await craft(update, context)
            return

        elif text == "🔍 Найти противника":
            await select_battle_opponent(update, context)  # ← ВЫЗЫВАЕМ ОТДЕЛЬНУЮ ФУНКЦИЮ
            return

        # Обработка @никнейма
        if user_id in context.user_data:
            battle_info = context.user_data[user_id]
            if battle_info.get("step") == "battle_find_opponent":
                await process_opponent_selection(update, context)  # ← Вызываем функцию
                return

        if text == "⚔️ Нанять существо":

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

            COOLDOWN_SECONDS = 2 * 60 * 60
            current_time = int(time.time())
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
                    f"⏳ До следующего найма: {time_text}\n\n"
                    f"🎲 Или бросьте кубик для бесплатного найма!"
                )
                return

            # Собираем доступные карты
            available_cards = [
                card
                for card in data["cards"]
                if card["available"]
                and card.get("rarity")
                not in [
                    "UpgradeT1",
                    "UpgradeT2",
                    "UpgradeT3",
                    "UpgradeT4",
                    "UpgradeT5",
                    "UpgradeT6",
                    "UpgradeT7",
                ]
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
            save_data(data)
            caption = generate_card_caption(card, user_data, count=1, show_bonus=True)
            await send_card(update, card, context, caption=caption)

        elif text == "🍺 Таверна":

            await mini_games(update, context)

        elif text == "🎲 Бросить кубик":

            await dice(update, context)

        elif text == "🎰 Казино":

            await open_casino_from_button(update, context)

        elif text == "👑 Мой герой":

            await my_profile(update, context)

        elif text == "🛡 Казарма":

            await show_user_cards(update, context)

        elif text == "🏆 Топ героев":  # ← ДОБАВЬТЕ ЭТОТ БЛОК
            
            await top_players(update, context)

        elif text == "🔄 Трейд":  # ← ДОБАВЬТЕ
            
            await trade_menu(update, context)

    except (NetworkError, TimedOut) as e:

        logger.warning(f"Сетевая ошибка: {e}")

    except Exception as e:

        logger.error(f"Ошибка обработки сообщения: {e}")


# ===== АДМИН-КОМАНДЫ =====


async def add_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавление новой карточки (многострочно)."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        full_text = update.message.text
        lines = full_text.split("\n")
        
        # ⭐ НОВЫЙ ФОРМАТ: 6 строк (с уроном) ⭐
        if len(lines) < 6:
            await update.message.reply_text(
                "ℹ️ Формат:\n"
                "/add_card\n"
                "URL\n"
                "Название\n"
                "Редкость\n"
                "Фракция (или 'нет')\n"
                "Урон (число или диапазон, например: 15 или 10-20)"
            )
            return
        
        url = lines[1].strip()
        title = lines[2].strip()
        rarity = lines[3].strip()
        faction = lines[4].strip()
        damage = lines[5].strip()  # ⭐ УРОН ⭐
        
        # ⭐ ПРОВЕРКА ФОРМАТА УРОНА ⭐
        if "-" in damage:
            # Диапазон
            try:
                min_dmg, max_dmg = map(int, damage.split("-"))
                if min_dmg > max_dmg:
                    await update.message.reply_text("⚠️ Минимальный урон не может быть больше максимального!")
                    return
            except ValueError:
                await update.message.reply_text("⚠️ Некорректный формат урона! Пример: 15 или 10-20")
                return
        else:
            # Число
            try:
                int(damage)
            except ValueError:
                await update.message.reply_text("⚠️ Урон должен быть числом или диапазоном! Пример: 15 или 10-20")
                return
        
        if rarity not in RARITY_BONUSES:
            await update.message.reply_text(
                f"⚠️ Допустимые редкости: {', '.join(RARITY_BONUSES.keys())}"
            )
            return
        
        data = load_data()
        
        # Вычисляем новый ID
        if data["cards"]:
            new_id = max(card["id"] for card in data["cards"]) + 1
        else:
            new_id = 1
        
        media_type = determine_media_type(url, rarity)
        
        # ⭐ ДОБАВЛЯЕМ ВСЕ АТРИБУТЫ ⭐
        new_card = {
            "id": new_id,
            "image_url": url,
            "title": title,
            "rarity": rarity,
            "faction": faction if faction.lower() != "нет" else None,
            "available": True,
            "media_type": media_type,
            # ⭐ АТРИБУТЫ ⭐
            "attack": 0,
            "defense": 0,
            "damage": damage,  # ← МОЖЕТ БЫТЬ "10-20" ИЛИ "15"
            "health": 0,
            "speed": 0,
        }
        
        data["cards"].append(new_card)
        save_data(data)
        
        faction_text = f"\n⚔️ {faction}" if faction.lower() != "нет" else ""
        damage_display = format_damage_display(damage)
        
        await update.message.reply_text(
            f"✅ Карточка #{new_id} добавлена!\n"
            f"🏷 {title}\n"
            f"🌟 {rarity}{faction_text}\n"
            f"💥 Урон: {damage_display}\n"
            f"📺 {'Анимация' if media_type == 'animation' else 'Фото'}"
        )
        
    except Exception as e:
        logger.error(f"Ошибка добавления карточки: {e}")
        await update.message.reply_text("❌ Ошибка при добавлении")

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
            faction_text = f"⚔️ {card.get('faction', '—')}" if card.get('faction') else "⚔️ —"
            
            card_info = (
                f"{status} ID: {card['id']}\n"
                f"📺 Тип: {'Анимация' if card.get('media_type') == 'animation' else 'Фото'}\n"
                f"🏷 {card['title']}\n"
                f"🌟 {card['rarity']}\n"
                f"{faction_text}\n"  # ⭐ ДОБАВЛЯЕМ ФРАКЦИЮ ⭐
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
    """Статистика карточек."""

    try:

        data = load_data()

        if not is_admin(str(update.effective_user.id), data):

            await update.message.reply_text("🚫 Только для администратора!")

            return

        available = sum(1 for card in data["cards"] if card["available"])

        await update.message.reply_text(
            f"📊 Статистика:\n"
            f"Всего карточек: {len(data['cards'])}\n"
            f"Доступно: {available}\n"
            f"Пользователей: {len(data['users'])}"
        )

    except Exception as e:

        logger.error(f"Ошибка проверки статистики: {e}")

        await update.message.reply_text("❌ Ошибка при проверке")


# ===== НОВЫЕ КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ АДМИНАМИ =====


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
        
        # Проверяем аргументы
        if not context.args or len(context.args) < 3:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/edit_card [ID] [параметр] [новое_значение]\n"
                "**Параметры:**\n"
                "• title - название карты\n"
                "• url - URL изображения\n"
                "• rarity - редкость (T1-T8, UpgradeT1-UpgradeT7)\n"
                "• faction - фракция (текст)\n"
                "• available - статус (true/false)\n"
                "• attack - атака (число или диапазон, например: 15 или 10-20)\n"
                "• defense - защита (число или диапазон)\n"
                "• damage - урон (число или диапазон)\n"
                "• health - здоровье (число или диапазон)\n"
                "• speed - скорость (число или диапазон)\n"
                "• stats - ВСЕ характеристики сразу (атака защита урон здоровье скорость)\n"
                "**Примеры:**\n"
                "/edit_card 45 title Новая карта\n"
                "/edit_card 45 damage 15\n"
                "/edit_card 45 damage 10-20\n"
                "/edit_card 45 attack 100\n"
                "/edit_card 45 stats 100 50 75 200 30",
                parse_mode="HTML",
            )
            return
        
        card_id = int(context.args[0])
        param = context.args[1].lower()
        new_value = " ".join(context.args[2:])
        
        # Находим карту
        card = find_card_by_id(card_id, data["cards"])
        if not card:
            await update.message.reply_text(f"⚠️ Карта #{card_id} не найдена")
            return
        
        # Обновляем параметр
        valid_params = [
            "title", "url", "rarity", "faction", "available",
            "attack", "defense", "damage", "health", "speed", "stats", "shooter", "ability", "hates", "resistant_to"
        ]
        if param not in valid_params:
            await update.message.reply_text(
                f"⚠️ Неверный параметр! Доступные: {', '.join(valid_params)}"
            )
            return
        
        # Сохраняем старое значение
        old_value = card.get(param, "не задано")
        
        # ⭐ ОБРАБОТКА ВСЕХ ХАРАКТЕРИСТИК СРАЗУ ⭐
        if param == "stats":
            # Ожидаем 5 чисел или диапазонов: атака защита урон здоровье скорость
            stats_parts = new_value.split()
            if len(stats_parts) != 5:
                await update.message.reply_text(
                    "⚠️ **Неверный формат!**\n"
                    "Нужно указать 5 значений:\n"
                    "/edit_card [ID] stats [атака] [защита] [урон] [здоровье] [скорость]\n"
                    "Пример: /edit_card 45 stats 100 50 10-20 200 30",
                    parse_mode="HTML"
                )
                return
            
            try:
                # Проверяем и сохраняем каждое значение (может быть числом или диапазоном)
                for i, stat_name in enumerate(["attack", "defense", "damage", "health", "speed"]):
                    value = stats_parts[i]
                    # Проверяем, является ли диапазоном
                    if "-" in value:
                        parts = value.split("-")
                        if len(parts) != 2:
                            raise ValueError(f"Неверный формат диапазона: {value}")
                        min_val, max_val = int(parts[0]), int(parts[1])
                        if min_val > max_val:
                            raise ValueError(f"Минимальное значение больше максимального: {value}")
                        card[stat_name] = value  # Сохраняем как строку "10-20"
                    else:
                        # Обычное число
                        card[stat_name] = int(value)
                
                old_value = (
                    f"⚔️{card.get('attack', 0)} 🛡️{card.get('defense', 0)} "
                    f"💥{card.get('damage', 0)} ❤️{card.get('health', 0)} "
                    f"👟{card.get('speed', 0)}"
                )
                new_value = (
                    f"⚔️{stats_parts[0]} 🛡️{stats_parts[1]} 💥{stats_parts[2]} "
                    f"❤️{stats_parts[3]} 👟{stats_parts[4]}"
                )
            except ValueError as e:
                await update.message.reply_text(f"⚠️ Ошибка: {e}")
                return
        
        # ⭐ ОБРАБОТКА ОТДЕЛЬНЫХ ХАРАКТЕРИСТИК ⭐
        elif param in ["attack", "defense", "damage", "health", "speed"]:
            # Проверяем, является ли значение диапазоном
            if "-" in new_value:
                parts = new_value.split("-")
                if len(parts) != 2:
                    await update.message.reply_text(
                        "⚠️ Неверный формат диапазона! Пример: 10-20"
                    )
                    return
                try:
                    min_val, max_val = int(parts[0]), int(parts[1])
                    if min_val > max_val:
                        await update.message.reply_text(
                            "⚠️ Минимальное значение не может быть больше максимального!"
                        )
                        return
                    card[param] = new_value  # Сохраняем как строку "10-20"
                except ValueError:
                    await update.message.reply_text("⚠️ Значение должно быть числом или диапазоном!")
                    return
            else:
                # Обычное число
                try:
                    card[param] = int(new_value)
                except ValueError:
                    await update.message.reply_text(f"⚠️ {param} должно быть числом!")
                    return
        
        # ⭐ ОБРАБОТКА ОСТАЛЬНЫХ ПАРАМЕТРОВ ⭐
        elif param == "available":
            new_value = new_value.lower() in ["true", "1", "yes", "вкл", "on"]
            card[param] = new_value
        elif param == "shooter":  # ← ДОБАВЛЕНО
            new_value = new_value.lower() in ["true", "1", "yes", "вкл", "on"]
            card[param] = new_value
        elif param == "ability":
            card[param] = new_value
        elif param == "hates":
            card[param] = new_value
        elif param == "resistant_to":
            card[param] = new_value
        elif param == "rarity":
            if new_value not in RARITY_BONUSES:
                await update.message.reply_text(
                    f"⚠️ Недопустимая редкость!\n"
                    f"Доступные: {', '.join(RARITY_BONUSES.keys())}"
                )
                return
            card[param] = new_value
            card["media_type"] = determine_media_type(card.get("image_url", ""), new_value)
        elif param == "url":
            card["image_url"] = new_value
            card["media_type"] = determine_media_type(new_value, card.get("rarity", ""))
        else:
            # title или faction
            card[param] = new_value
        
        save_data(data)
        
        # Формируем ответ
        response = (
            f"✅ **Карта #{card_id} обновлена!**\n"
            f"📝 Параметр: {param}\n"
            f"❌ Было: {old_value}\n"
            f"✅ Стало: {new_value}\n"
            f"🏷 {card.get('title')}\n"
            f"🌟 {card.get('rarity')}"
        )
        
        # Добавляем фракцию в ответ, если она есть
        if card.get("faction"):
            response += f"\n⚔️ {card['faction']}"
        
        # ⭐ ОТОБРАЖАЕМ ВСЕ ХАРАКТЕРИСТИКИ ⭐
        response += f"\n\n**Характеристики:**"
        response += f"\n⚔️ Атака: {card.get('attack', 0)}"
        response += f"\n🛡️ Защита: {card.get('defense', 0)}"
        response += f"\n💥 Урон: {card.get('damage', 0)}"
        response += f"\n❤️ Здоровье: {card.get('health', 0)}"
        response += f"\n👟 Скорость: {card.get('speed', 0)}"
        
        response += f"\n\n{'✅ Включена' if card.get('available') else '❌ Выключена'}"
        
        await update.message.reply_text(response, parse_mode="HTML")
        
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
        )
        
        # ⭐ ДОБАВЛЯЕМ ФРАКЦИЮ ⭐
        if card.get("faction"):
            info_text += f"⚔️ **Фракция:** {card['faction']}\n"
        
        # ⭐ ДОБАВЛЯЕМ АТРИБУТЫ ⭐
        info_text += "\n**Характеристики:**\n"
        info_text += f"⚔️ Атака: {card.get('attack', 0)}\n"
        info_text += f"🛡️ Защита: {card.get('defense', 0)}\n"
        info_text += f"💥 Урон: {format_damage_display(card.get('damage', 0))}\n"  # ← ФОРМАТИРОВАНИЕ
        info_text += f"❤️ Здоровье: {card.get('health', 0)}\n"
        info_text += f"👟 Скорость: {card.get('speed', 0)}\n"
        
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


async def craft(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Крафт 2 одинаковых карт в новую карту редкости Upgrade."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        # ⭐ КЛАВИАТУРА С КНОПКОЙ НАЗАД В ЛЕС ⭐
        forest_keyboard = [
            [KeyboardButton("🔙 Назад в Лес")],
        ]
        forest_reply_markup = ReplyKeyboardMarkup(forest_keyboard, resize_keyboard=True)
        
        if not user_data or not user_data.get("cards"):
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text("❌ У вас нет существ для улучшения!")
            else:
                await update.message.reply_text(
                    "❌ У вас нет существ для улучшения!",
                    reply_markup=forest_reply_markup
                )
            return
        
        # Считаем количество каждой карты
        card_counts = Counter(user_data["cards"])
        
        # Находим карты, которых 2 или больше
        craftable_cards = {
            card_id: count for card_id, count in card_counts.items() if count >= 2
        }
        
        if not craftable_cards:
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(
                    "❌ Нет существ для улучшения!\n"
                    "📋 Для улучшения нужно 2 одинаковых существа."
                )
            else:
                await update.message.reply_text(
                    "❌ Нет существ для улучшения!\n"
                    "📋 Для улучшения нужно 2 одинаковых существа.\n"
                    "🔹 2x T1 → UpgradeT1\n"
                    "🔹 2x T2 → UpgradeT2\n"
                    "🔹 2x T3 → UpgradeT3\n"
                    "🔹 2x T4 → UpgradeT4\n"
                    "🔹 2x T5 → UpgradeT5\n"
                    "🔹 2x T6 → UpgradeT6\n"
                    "🔹 2x T7 → UpgradeT7\n"
                    "Собирайте дубликаты и попробуйте снова!",
                    reply_markup=forest_reply_markup
                )
            return
        
        # Фильтруем только карты, которые можно крафтить (T1-T7)
        craftable_by_rarity = {}
        for card_id, count in craftable_cards.items():
            card = find_card_by_id(card_id, data["cards"])
            if card and card.get("rarity") in ["T1", "T2", "T3", "T4", "T5", "T6", "T7"]:
                craftable_by_rarity[card_id] = {
                    "count": count,
                    "rarity": card["rarity"],
                    "title": card["title"],
                }
        
        if not craftable_by_rarity:
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text("❌ Для улучшения подходят только существа редкости T1-T7!")
            else:
                await update.message.reply_text(
                    "❌ Для улучшения подходят только существа редкости T1-T7!",
                    reply_markup=forest_reply_markup
                )
            return
        
        # ⭐ СОХРАНЯЕМ СПИСОК КАРТ В context.user_data ⭐
        context.user_data[user_id] = {
            "step": "craft_select",
            "craftable_cards": craftable_by_rarity,
            "craft_page": 0,
            "craft_cards_per_page": 5,
        }
        
        # ⭐ ОТПРАВЛЯЕМ КЛАВИАТУРУ С КНОПКОЙ "НАЗАД В ЛЕС" ⭐
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=FORT_IMAGE_URL,
            caption="Добро пожаловать в Форт на холме!",
            reply_markup=forest_reply_markup,
            parse_mode="Markdown"
        )
        
        # ⭐ ПОКАЗЫВАЕМ ПЕРВУЮ СТРАНИЦУ ⭐
        await show_craft_page(update, context, 0)
        
    except Exception as e:
        logger.error(f"Ошибка крафта: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("❌ Произошла ошибка при улучшении")


async def show_craft_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    """Показывает страницу списка карт для крафта."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        
        # ⭐ КЛАВИАТУРА С КНОПКОЙ НАЗАД В ЛЕС ⭐
        forest_keyboard = [
            [KeyboardButton("🔙 Назад в Лес")],
        ]
        forest_reply_markup = ReplyKeyboardMarkup(forest_keyboard, resize_keyboard=True)
        
        if user_id not in context.user_data:
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.answer("❌ Сессия улучшения истекла!", show_alert=True)
            else:
                await update.message.reply_text(
                    "❌ Сессия улучшения истекла!",
                    reply_markup=forest_reply_markup
                )
            return
        
        craft_info = context.user_data[user_id]
        craftable_cards = craft_info.get("craftable_cards", {})
        cards_per_page = craft_info.get("craft_cards_per_page", 5)
        
        if not craftable_cards:
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.answer("❌ Нет существ для улучшения!", show_alert=True)
            else:
                await update.message.reply_text(
                    "❌ Нет существ для улучшения!",
                    reply_markup=forest_reply_markup
                )
            return
        
        # ⭐ КОНВЕРТИРУЕМ В СПИСОК ⭐
        cards_list = list(craftable_cards.items())
        total_cards = len(cards_list)
        
        # ⭐ РАСЧЁТ СТРАНИЦ ⭐
        total_pages = (total_cards + cards_per_page - 1) // cards_per_page
        
        # Корректируем страницу
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        context.user_data[user_id]["craft_page"] = page
        
        # Получаем карты для текущей страницы
        start_index = page * cards_per_page
        end_index = min(start_index + cards_per_page, total_cards)
        page_cards = cards_list[start_index:end_index]
        
        # ⭐ СОЗДАЁМ INLINE КЛАВИАТУРУ ДЛЯ ВЫБОРА КАРТ ⭐
        inline_keyboard = []
        for card_id, info in page_cards:
            inline_keyboard.append([
                InlineKeyboardButton(
                    f"{info['title']} ({info['count']} шт.) → Upgrade{info['rarity']}",
                    callback_data=f"craft_{card_id}"
                )
            ])
        
        # ⭐ КНОПКИ НАВИГАЦИИ ⭐
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"craft_nav_{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="craft_page_info"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"craft_nav_{page + 1}"))
        
        if nav_buttons:
            inline_keyboard.append(nav_buttons)
        
        caption = (
            "🔨 **Выберите существо для улучшения:**\n"
            "2 существа будут уничтожены, вы получите 1 случайное существо улучшенной редкости\n"
            f"📄 Страница {page + 1}/{total_pages}\n"
            f"🐦‍🔥 Доступно для улучшения: {total_cards}"
        )
        
        # ⭐ ПРОВЕРЯЕМ ЕСТЬ ЛИ CALLBACK QUERY ⭐
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            # ⭐ ПЫТАЕМСЯ ОТРЕДАКТИРОВАТЬ СУЩЕСТВУЮЩЕЕ СООБЩЕНИЕ ⭐
            try:
                await query.edit_message_text(
                    caption,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard),
                    parse_mode="Markdown"
                )
            except Exception as edit_error:
                logger.error(f"Ошибка редактирования: {edit_error}")
                # ⭐ ЕСЛИ НЕ МОЖНО ОТРЕДАКТИРОВАТЬ - ОТПРАВЛЯЕМ НОВОЕ ⭐
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=caption,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard),
                    parse_mode="Markdown"
                )
        else:
            # ⭐ ПЕРВЫЙ ЗАПУСК - ОТПРАВЛЯЕМ НОВОЕ СООБЩЕНИЕ ⭐
            await update.message.reply_text(
                caption,
                reply_markup=InlineKeyboardMarkup(inline_keyboard),
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"Ошибка show_craft_page: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("❌ Произошла ошибка")
            
async def craft_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик навигации по страницам крафта."""
    try:
        query = update.callback_query
        await query.answer()
        
        # ⭐ НОВАЯ КНОПКА: НАЗАД В ЛЕС ⭐
        if query.data == "craft_back_to_forest":
            user_id = str(query.from_user.id)
            if user_id in context.user_data:
                del context.user_data[user_id]
            try:
                await query.message.delete()
            except:
                pass
            # Возвращаем в меню Леса
            await forest_menu(update, context)
            return
        
        # ⭐ НАВИГАЦИЯ ПО СТРАНИЦАМ ⭐
        if query.data.startswith("craft_nav_"):
            page = int(query.data.split("_")[-1])
            # ⭐ ВАЖНО: ВЫЗЫВАЕМ show_craft_page С UPDATE, ЧТОБЫ ОН МОГ ОТРЕДАКТИРОВАТЬ ⭐
            await show_craft_page(update, context, page)
            return
        
        elif query.data == "craft_page_info":
            await query.answer("📄 Используйте ◀️ и ▶️ для навигации", show_alert=False)
        
        elif query.data == "craft_cancel":
            user_id = str(query.from_user.id)
            if user_id in context.user_data:
                del context.user_data[user_id]
            # ⭐ ВОЗВРАЩАЕМ КЛАВИАТУРУ ЛЕСА ⭐
            forest_keyboard = [
                [KeyboardButton("🔙 Назад в Лес")],
            ]
            forest_reply_markup = ReplyKeyboardMarkup(forest_keyboard, resize_keyboard=True)
            await query.edit_message_text(
                "❌ Улучшение отменено",
                reply_markup=forest_reply_markup
            )
            
    except Exception as e:
        logger.error(f"Ошибка craft_nav_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def process_craft(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: str,
    card_id: int,
    data: Dict,
    query=None,
) -> None:
    """Обрабатывает крафт конкретной карты."""
    try:
        user_data = data["users"].get(user_id)
        # Проверяем, что у пользователя ещё есть 2+ карт
        card_counts = Counter(user_data["cards"])
        if card_counts.get(card_id, 0) < 2:
            if query:
                await query.answer("❌ Недостаточно существ для улучшения!", show_alert=True)
            else:
                await update.message.reply_text("❌ Недостаточно существ для улучшения!")
            return
        
        # Находим информацию о карте
        card = find_card_by_id(card_id, data["cards"])
        if not card:
            if query:
                await query.answer("❌ Существо не найдена!", show_alert=True)
            else:
                await update.message.reply_text("❌ Существо не найдена!")
            return
        
        # Определяем целевую редкость (T1-T7)
        source_rarity = card.get("rarity", "")
        rarity_map = {
            "T1": "UpgradeT1",
            "T2": "UpgradeT2",
            "T3": "UpgradeT3",
            "T4": "UpgradeT4",
            "T5": "UpgradeT5",
            "T6": "UpgradeT6",
            "T7": "UpgradeT7",
        }
        if source_rarity not in rarity_map:
            if query:
                await query.answer(f"❌ Существ редкости {source_rarity} нельзя улучшить!", show_alert=True)
            else:
                await update.message.reply_text(f"❌ Существ редкости {source_rarity} нельзя улучшить!")
            return
        
        target_rarity = rarity_map[source_rarity]
        
        # Находим все карты целевой редкости
        upgrade_cards = [
            c
            for c in data["cards"]
            if c.get("rarity") == target_rarity and c.get("available", True)
        ]
        if not upgrade_cards:
            if query:
                await query.answer(f"❌ В системе нет существ редкости {target_rarity}!", show_alert=True)
            else:
                await update.message.reply_text(f"❌ В системе нет существ редкости {target_rarity}!")
            return
        
        # Удаляем 2 существа из казармы
        removed = 0
        new_cards_list = []
        for cid in user_data["cards"]:
            if cid == card_id and removed < 2:
                removed += 1
            else:
                new_cards_list.append(cid)
        user_data["cards"] = new_cards_list
        
        # Выбираем случайную карту улучшенной редкости
        new_card = random.choice(upgrade_cards)
        user_data["cards"].append(new_card["id"])
        
        # ⭐ НАЧИСЛЯЕМ НАГРАДЫ ЗА КАРТУ ⭐
        bonus = RARITY_BONUSES.get(new_card["rarity"], {"cents": 0, "points": 0})
        user_data["total_points"] += bonus["points"]
        user_data["season_points"] += bonus["points"]
        user_data["cents"] += bonus["cents"]
        
        # ========================================
        save_data(data)
        
        # ⭐ ОТПРАВЛЯЕМ РЕЗУЛЬТАТ КАК НОВОЕ СООБЩЕНИЕ ⭐
        result_text = (
            f"✅ **Улучшение прошло успешно!**\n\n"
            f"🔨 **Использовано:** 2x {card['title']} ({card['rarity']})\n"
            f"🎁 **Получено:** {new_card['title']}\n"
            f"💰 **+{bonus['cents']} золота**\n"
            f"💥 **+{bonus['points']} опыта**"
        )
        
        if query:
            # ⭐ ОТПРАВЛЯЕМ НОВОЕ СООБЩЕНИЕ С РЕЗУЛЬТАТОМ ⭐
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=result_text,
                parse_mode="Markdown"
            )
            # ⭐ ОТПРАВЛЯЕМ КАРТУ ⭐
            caption = generate_card_caption(new_card, user_data, count=1, show_bonus=False)
            await send_card(update, new_card, context, caption=caption, chat_id=query.message.chat_id)
            await show_craft_page(update, context, 0)
        else:
            await update.message.reply_text(result_text, parse_mode="Markdown")
            caption = generate_card_caption(new_card, user_data, count=1, show_bonus=False)
            await send_card(update, new_card, context, caption=caption)
            await show_craft_page(update, context, 0)
            
    except Exception as e:
        logger.error(f"Ошибка обработки крафта: {e}")
        if query:
            await query.answer("❌ Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("❌ Произошла ошибка при улучшении")


async def craft_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок крафта."""
    try:
        query = update.callback_query
        await query.answer()
        
        # ⭐ НАВИГАЦИЯ ПО СТРАНИЦАМ ⭐
        if query.data.startswith("craft_nav_") or query.data in ["craft_page_info", "craft_cancel"]:
            await craft_nav_callback(update, context)
            return
        
        # ⭐ ВЫБОР КАРТЫ ДЛЯ КРАФТА ⭐
        if query.data.startswith("craft_"):
            user_id = str(query.from_user.id)
            card_id = int(query.data.split("_")[1])
            
            # ⭐ ЗАГРУЖАЕМ ДАННЫЕ ПЕРЕД КРАФТОМ ⭐
            data = load_data()
            
            # ⭐ ВЫПОЛНЯЕМ КРАФТ ⭐
            await process_craft(update, context, user_id, card_id, data, query)
            
            # ⭐ ПЕРЕЗАГРУЖАЕМ ДАННЫЕ ПОСЛЕ КРАФТА ⭐
            data = load_data()  # ← ДОБАВЬТЕ ЭТУ СТРОКУ!
            
            # ⭐ ПРОВЕРЯЕМ, ЕСТЬ ЛИ ЕЩЁ КАРТЫ ДЛЯ КРАФТА ⭐
            user_data = data["users"].get(user_id)
            if user_data and user_data.get("cards"):
                card_counts = Counter(user_data["cards"])
                craftable_cards = {
                    cid: count for cid, count in card_counts.items() if count >= 2
                }
                
                # Фильтруем только карты T1-T7
                craftable_by_rarity = {}
                for cid, count in craftable_cards.items():
                    card = find_card_by_id(cid, data["cards"])
                    if card and card.get("rarity") in ["T1", "T2", "T3", "T4", "T5", "T6", "T7"]:
                        craftable_by_rarity[cid] = {
                            "count": count,
                            "rarity": card["rarity"],
                            "title": card["title"],
                        }
                
                if craftable_by_rarity:
                    # ⭐ ОБНОВЛЯЕМ context.user_data ⭐
                    context.user_data[user_id] = {
                        "step": "craft_select",
                        "craftable_cards": craftable_by_rarity,
                        "craft_page": 0,
                        "craft_cards_per_page": 5,
                    }
                    # ⭐ ОТПРАВЛЯЕМ НОВОЕ СООБЩЕНИЕ С МЕНЮ КРАФТА ⭐
                    await show_craft_page(update, context, 0)
                    return
            
            # ⭐ ЕСЛИ НЕТ СУЩЕСТВ ДЛЯ КРАФТА ⭐
            forest_keyboard = [
                [KeyboardButton("🔙 Назад в Лес")],
            ]
            forest_reply_markup = ReplyKeyboardMarkup(forest_keyboard, resize_keyboard=True)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ Больше нет существ для улучшения!",
                reply_markup=forest_reply_markup
            )
            
    except Exception as e:
        logger.error(f"Ошибка callback крафта: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)
        
async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Бросок кубика для получения бесплатных попыток."""

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

        # Проверка кулдауна (6 часов)

        DICE_COOLDOWN = 12 * 60 * 60

        current_time = int(time.time())

        time_passed = current_time - user_data.get("last_dice_time", 0)

        if time_passed < DICE_COOLDOWN:

            remaining = DICE_COOLDOWN - time_passed

            hours = remaining // 3600

            minutes = (remaining % 3600) // 60

            await update.message.reply_text(
                f"⏳ Следующий бросок через: {hours} ч {minutes} мин\n\n"
                f"🎲 У вас есть {user_data.get('free_rolls', 0)} бесплатных наймов"
            )

            return

        # ⭐ ОТПРАВЛЯЕМ НАСТОЯЩИЙ КУБИК TELEGRAM ⭐

        sent_dice = await context.bot.send_dice(
            chat_id=update.effective_chat.id, emoji="🎲"  # Именно кубик!
        )

        # ⭐ ПОЛУЧАЕМ РЕАЛЬНОЕ ЗНАЧЕНИЕ ИЗ КУБИКА ⭐

        dice_value = sent_dice.dice.value  # Значение от 1 до 6

        # Добавляем бесплатные попытки (ровно столько, сколько выпало)

        user_data["free_rolls"] = user_data.get("free_rolls", 0) + dice_value

        user_data["last_dice_time"] = current_time

        save_data(data)

        await asyncio.sleep(4)

        await update.message.reply_text(
            f"🎲 Выпало: {dice_value}!\n\n"
            f"✨ Получено бесплатных наймов: {dice_value}\n"
            f"📊 Всего бесплатных наймов: {user_data['free_rolls']}\n\n"
            f"⏳ Следующий бросок через 12 часов"
        )

    except Exception as e:

        logger.error(f"Ошибка броска кубика: {e}")

        await update.message.reply_text("❌ Произошла ошибка")


async def dice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки кубика."""

    await dice(update, context)


async def mini_games(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню Таверны с изображением."""
    try:
        # ⭐ КЛАВИАТУРА С КНОПКАМИ ⭐
        keyboard = [
            [KeyboardButton("🎲 Бросить кубик")],
            [KeyboardButton("🎰 Казино")],
            [KeyboardButton("🏆 Топ героев")],
            [KeyboardButton("🔄 Трейд")],
            [KeyboardButton("🔙 Назад в меню")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        caption = (
            "🍺 Добро пожаловать в Таверну!"
        )

        await context.bot.send_photo(
                chat_id=update.effective_chat.id, 
                photo=TAVERN_IMAGE_URL,  # ← Изображение Таверны
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Ошибка в mini_games: {e}")
        
           

async def casino_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню казино."""

    try:

        query = update.callback_query

        await query.answer()

        user_id = str(query.from_user.id)

        data = load_data()

        user_data = data["users"].get(user_id)

        if not user_data:

            await query.edit_message_text("❌ Вы ещё не начали игру!")

            return

        # Проверяем сброс попыток

        check_casino_reset(user_data)

        save_data(data)

        attempts = user_data.get("casino_attempts", 10)

        cents = user_data.get("cents", 0)

        keyboard = [
            [InlineKeyboardButton("🎰 Играть (3000 золота)", callback_data="casino_play")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🎰 **Казино**\n\n"
            f"📜 **Правила:**\n"
            f"• Стоимость игры: 3000 золота\n"
            f"• Крутите слот и получите 3 одинаковых значения\n"
            f"• При победе: 10 бесплатных наймов существ\n"
            f"• Попыток сегодня: {attempts}/10\n"
            f"• Сброс в 00:00 МСК\n\n"
            f"💰 Ваш баланс: {cents} золота\n"
            f"🎲 Осталось попыток: {attempts}",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    except Exception as e:

        logger.error(f"Ошибка в casino_menu: {e}")


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

            if cents < 3000:

                await query.edit_message_text(
                    f"❌ **Недостаточно золота!**\n\n"
                    f"Нужно: 3000 золота\n"
                    f"У вас: {cents} золота\n\n"
                    f"Нанимайте существ и получайте больше наград! 💰",
                    parse_mode="Markdown",
                )

                return

            # Списываем центы и попытки

            user_data["cents"] -= 3000

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

        if is_win:

            # Добавляем 10 бесплатных попыток

            await asyncio.sleep(2)

            user_data["free_rolls"] = user_data.get("free_rolls", 0) + 10

            save_data(data)

            await query.message.reply_text(
                f"🎉 **ДЖЕКПОТ!** 🎉\n\n"
                f"✨ **3 одинаковых символа!**\n"
                f"🎁 Получено: 10 бесплатных наймов\n"
                f"📊 Всего наймов: {user_data['free_rolls']}\n\n"
                f"🎲 Осталось попыток в казино: {user_data['casino_attempts']}",
                parse_mode="Markdown",
            )

        else:

            await asyncio.sleep(2)

            await query.message.reply_text(
                f"😔 Не повезло! Попробуйте ещё раз.\n\n"
                f"💰 Списано: 3000 золота\n"
                f"🎲 Осталось попыток: {user_data['casino_attempts']}\n"
                f"💰 Ваш баланс: {user_data['cents']} золота",
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


async def add_card_to_player(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Добавляет определённую карту определённому игроку."""

    try:

        data = load_data()

        if not is_admin(str(update.effective_user.id), data):

            await update.message.reply_text("🚫 Только для администратора!")

            return

        # Проверяем аргументы

        if not context.args or len(context.args) < 2:

            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n\n"
                "/add_card_to_player [ID_игрока] [ID_карты] [количество]\n\n"
                "**Примеры:**\n"
                "/add_card_to_player 881692999 45 - добавить 1 карту\n"
                "/add_card_to_player 881692999 45 5 - добавить 5 карт",
                parse_mode="Markdown",
            )

            return

        target_user_id = context.args[0]

        card_id = int(context.args[1])

        count = int(context.args[2]) if len(context.args) > 2 else 1

        # Проверяем существование игрока

        if target_user_id not in data["users"]:

            await update.message.reply_text(f"⚠️ герой {target_user_id} не найден!")

            return

        # Проверяем существование карты

        card = find_card_by_id(card_id, data["cards"])

        if not card:

            await update.message.reply_text(f"⚠️ Существо #{card_id} не найдено!")

            return

        # Добавляем карту(ы) в коллекцию игрока

        user_data = data["users"][target_user_id]

        if "cards" not in user_data:

            user_data["cards"] = []

        for _ in range(count):

            user_data["cards"].append(card_id)

        save_data(data)

        await update.message.reply_text(
            f"✅ **Карта добавлена!**\n\n"
            f"👤 Игрок: {target_user_id}\n"
            f"🃏 Карта: {card['title']} (#{card_id})\n"
            f"🌟 Редкость: {card['rarity']}\n"
            f"📦 Количество: {count} шт.\n\n"
            f"Всего карт у игрока: {len(user_data['cards'])}",
            parse_mode="Markdown",
        )

    except ValueError:

        await update.message.reply_text("⚠️ ID должен быть числом!")

    except Exception as e:

        logger.error(f"Ошибка добавления карты игроку: {e}")

        await update.message.reply_text("❌ Ошибка при добавлении карты")


async def add_rolls_to_player(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Добавляет определённое количество бесплатных попыток игроку."""

    try:

        data = load_data()

        if not is_admin(str(update.effective_user.id), data):

            await update.message.reply_text("🚫 Только для администратора!")

            return

        # Проверяем аргументы

        if not context.args or len(context.args) < 2:

            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n\n"
                "/add_rolls_to_player [ID_игрока] [количество]\n\n"
                "**Примеры:**\n"
                "/add_rolls_to_player 881692999 10 - добавить 10 попыток\n"
                "/add_rolls_to_player 881692999 100 - добавить 100 попыток",
                parse_mode="Markdown",
            )

            return

        target_user_id = context.args[0]

        rolls_count = int(context.args[1])

        # Проверяем существование игрока

        if target_user_id not in data["users"]:

            # Создаём нового игрока если не существует

            user_data = {
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
                "casino_attempts": 10,
                "last_casino_reset": 0,
            }

            data["users"][target_user_id] = user_data

            created = True

        else:

            user_data = data["users"][target_user_id]

            created = False

        # Добавляем попытки

        old_rolls = user_data.get("free_rolls", 0)

        user_data["free_rolls"] = old_rolls + rolls_count

        save_data(data)

        await update.message.reply_text(
            f"✅ **Наймы добавлены!**\n\n"
            f"👤 Герой: {target_user_id}\n"
            f"🎲 Добавлено: {rolls_count}\n"
            f"📊 Было: {old_rolls}\n"
            f"📈 Стало: {user_data['free_rolls']}\n\n"
            f"{'🆕 Герой создан!' if created else ''}",
            parse_mode="Markdown",
        )

    except ValueError:

        await update.message.reply_text("⚠️ Количество должно быть числом!")

    except Exception as e:

        logger.error(f"Ошибка добавления наймов герою: {e}")

        await update.message.reply_text("❌ Ошибка при добавлении наймов")

async def top_players(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает топ-10 героев по опыту игроков по поинтам в сезоне (админы исключены)."""
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
        message_text = "🏆 **Топ героев этого сезона**\n\n"
        
        if not top_10:
            message_text += "📭 Пока нет героев в топе!"
        else:
            for rank, (user_id, user_data) in enumerate(top_10, 1):
                # Получаем имя из профиля Telegram
                first_name = user_data.get("first_name", "Герой")
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
                
                message_text += f"{medal} **{username}** — {points} опыта\n"
        
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
            
            message_text += f"💥 **Ваш опыт:** {current_points}"
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
                "/reset_season_points [ID_героя]\n\n"
                "**Пример:**\n"
                "/reset_season_points 881692999",
                parse_mode="Markdown"
            )
            return
        
        target_user_id = context.args[0]
        
        # Проверяем существование игрока
        if target_user_id not in data["users"]:
            await update.message.reply_text(f"⚠️ Герой {target_user_id} не найден!")
            return
        
        # Сохраняем старые поинты
        old_points = data["users"][target_user_id].get("season_points", 0)
        
        # Сбрасываем поинты
        data["users"][target_user_id]["season_points"] = 0
        
        save_data(data)
        
        # Получаем имя игрока
        player_data = data["users"][target_user_id]
        player_name = player_data.get("first_name", "Герой")
        if player_data.get("last_name"):
            player_name += f" {player_data['last_name']}"
        
        await update.message.reply_text(
            f"✅ **Сезонный опыт сброшен!**\n\n"
            f"👤 Герой: {player_name}\n"
            f"🆔 ID: {target_user_id}\n"
            f"📊 Было опыта: {old_points}\n"
            f"📈 Стало опыта: 0\n\n"
            f"⚠️ Общий опыт (total_points) не изменен.",
            parse_mode="HTML"
        )
        
        logger.info(f"Админ {user_id} сбросил сезонный опыт герою {target_user_id} ({old_points} → 0)")
        
    except Exception as e:
        logger.error(f"Ошибка reset_season_points: {e}")
        await update.message.reply_text("❌ Ошибка при сбросе поинтов")


async def achievements_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Меню достижений."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        if not user_data:
            await query.edit_message_text("❌ Вы ещё не начали игру!")
            return

        # Получаем карты пользователя
        user_card_ids = user_data.get("cards", [])
        claimed_achievements = user_data.get("claimed_achievements", [])

        # Считаем карты по фракциям
        faction_cards = {}
        for card_id in user_card_ids:
            card = find_card_by_id(card_id, data["cards"])
            if card and card.get("faction"):
                faction = card["faction"]
                if faction not in faction_cards:
                    faction_cards[faction] = set()
                faction_cards[faction].add(card_id)

        # ⭐ СЧИТАЕМ КАРТЫ РЕДКОСТИ T8 ⭐
        t8_cards_user = set()
        for card_id in user_card_ids:
            card = find_card_by_id(card_id, data["cards"])
            if card and card.get("rarity") == "T8":
                t8_cards_user.add(card_id)

        # Список фракций
        factions = [
            "Замок", "Оплот", "Башня", "Инферно",
            "Некрополис", "Темница", "Цитадель", "Крепость", "Сопряжение", "Фабрика"
        ]

        # Создаём клавиатуру
        keyboard = []
        
        # ⭐ ДОБАВЛЯЕМ ФРАКЦИОННЫЕ ДОСТИЖЕНИЯ ⭐
        for i, faction in enumerate(factions, 1):
            faction_data = data["achievements"].get(faction, {"cards": []})
            total_cards = len(faction_data.get("cards", []))
            user_cards_count = len(faction_cards.get(faction, set()))

            # Проверяем, собрано ли достижение
            is_complete = user_cards_count >= total_cards and total_cards > 0
            is_claimed = faction in claimed_achievements

            if is_complete and not is_claimed:
                status = "🎁 ЗАБРАТЬ"
                callback = f"achievement_claim_{i}"
            elif is_claimed:
                status = "✅ Получено"
                callback = "achievement_claimed"
            else:
                status = f"📊 {user_cards_count}/{total_cards}"
                callback = "achievement_progress"

            keyboard.append([
                InlineKeyboardButton(
                    f"{i}. {faction} - {status}",
                    callback_data=callback
                )
            ])

        # ⭐ ДОБАВЛЯЕМ ДОСТИЖЕНИЕ "МОГУЩЕСТВО ЦАРЯ ДРАКОНОВ" ⭐
        # Находим всех существ T8 в системе
        all_t8_cards = set()
        for card in data["cards"]:
            if card.get("rarity") == "T8" and card.get("available", True):
                all_t8_cards.add(card["id"])

        total_t8 = len(all_t8_cards)
        user_t8_count = len(t8_cards_user)
        dragon_king_achievement = "Могущество_царя_драконов"
        is_dragon_complete = user_t8_count >= total_t8 and total_t8 > 0
        is_dragon_claimed = dragon_king_achievement in claimed_achievements

        if is_dragon_complete and not is_dragon_claimed:
            dragon_status = "🎁 ЗАБРАТЬ"
            dragon_callback = "achievement_claim_dragon"
        elif is_dragon_claimed:
            dragon_status = "✅ Получено"
            dragon_callback = "achievement_claimed"
        else:
            dragon_status = f"📊 {user_t8_count}/{total_t8}"
            dragon_callback = "achievement_progress"

        keyboard.append([
            InlineKeyboardButton(
                f"10. Могущество царя драконов - {dragon_status}",
                callback_data=dragon_callback
            )
        ])

        # ⭐ КНОПКА НАЗАД ⭐
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="profile_back")])

        await query.edit_message_text(
            "🏆 **Достижения**\n"
            "Соберите всех существ отдельной фракции или редкости,\n"
            "чтобы получить награду!\n"
            "\n"
            "🎁 **Награда за фракционное достижение:**\n"
            "• 30 бесплатных наймов\n"
            "• 30000 золота\n"
            "\n"
            "🎁 **Награда за T8 достижение:**\n"
            "• special существо\n"
            "\n"
            "Выберите достижение:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в achievements_menu: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def claim_achievement(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Получение награды за достижение."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        if not user_data:
            await query.edit_message_text("❌ Вы ещё не начали игру!")
            return

        # ⭐ СПЕЦИАЛЬНАЯ ОБРАБОТКА ДЛЯ "МОГУЩЕСТВО ЦАРЯ ДРАКОНОВ" ⭐
        if query.data == "achievement_claim_dragon":
            dragon_king_achievement = "Могущество_царя_драконов"
            claimed_achievements = user_data.get("claimed_achievements", [])

            # Проверяем, не получена ли уже награда
            if dragon_king_achievement in claimed_achievements:
                await query.edit_message_text("❌ Вы уже получили награду за это достижение!")
                return

            # Получаем карты пользователя
            user_card_ids = user_data.get("cards", [])

            # ⭐ СЧИТАЕМ КАРТЫ РЕДКОСТИ T8 ⭐
            t8_cards_user = set()
            for card_id in user_card_ids:
                card = find_card_by_id(card_id, data["cards"])
                if card and card.get("rarity") == "T8":
                    t8_cards_user.add(card_id)

            # Находим всех существ T8 в системе
            all_t8_cards = set()
            for card in data["cards"]:
                if card.get("rarity") == "T8" and card.get("available", True):
                    all_t8_cards.add(card["id"])

            # Проверяем, собрано ли достижение
            if len(t8_cards_user) < len(all_t8_cards) or len(all_t8_cards) == 0:
                await query.edit_message_text(
                    f"❌ Достижение не завершено!\n"
                    f"📊 Собрано: {len(t8_cards_user)}/{len(all_t8_cards)}\n"
                    f"🏷 Нужно собрать всех существ редкости T8"
                )
                return

            # ⭐ ID СУЩЕСТВА ДЛЯ НАГРАДЫ ⭐
            DRAGON_KING_CARD_ID = 173  # ← УКАЖИТЕ НУЖНЫЙ ID СУЩЕСТВА

            # Находим карту
            reward_card = find_card_by_id(DRAGON_KING_CARD_ID, data["cards"])
            if reward_card:
                # Добавляем карту игроку
                user_data["cards"].append(DRAGON_KING_CARD_ID)

                # Отмечаем достижение как полученное
                claimed_achievements.append(dragon_king_achievement)
                user_data["claimed_achievements"] = claimed_achievements
                save_data(data)

                # ⭐ ОТПРАВЛЯЕМ КАРТУ СУЩЕСТВА С ОПИСАНИЕМ ⭐
                caption = generate_card_caption(reward_card, user_data, count=1, show_bonus=True)
                await send_card(update, reward_card, context, caption=caption)

                await query.edit_message_text(
                    f"🎉 Достижение получено!\n"
                    f"🏆 Могущество царя драконов\n"
                    f"🎁 Награда:\n"
                    f"• 🐉 {reward_card['title']}\n"
                    f"Поздравляем!",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад к достижениям", callback_data="achievements_menu")
                    ]])
                )
                logger.info(f"Пользователь {user_id} получил достижение: Могущество царя драконов и существо #{DRAGON_KING_CARD_ID}")
                return
            else:
                await query.edit_message_text("❌ Ошибка: существо для награды не найдено!")
                return

        # ⭐ СТАРАЯ ЛОГИКА ДЛЯ ФРАКЦИОННЫХ ДОСТИЖЕНИЙ ⭐
        # Получаем номер достижения из callback_data
        achievement_num = int(query.data.split("_")[-1])
        factions = [
            "Замок", "Оплот", "Башня", "Инферно",
            "Некрополис", "Темница", "Цитадель", "Крепость", "Сопряжение", "Фабрика"
        ]
        if achievement_num < 1 or achievement_num > len(factions):
            await query.edit_message_text("❌ Неверное достижение!")
            return

        faction = factions[achievement_num - 1]
        claimed_achievements = user_data.get("claimed_achievements", [])

        # Проверяем, не получена ли уже награда
        if faction in claimed_achievements:
            await query.edit_message_text("❌ Вы уже получили награду за это достижение!")
            return

        # Получаем карты пользователя
        user_card_ids = user_data.get("cards", [])

        # Считаем карты по фракциям
        faction_cards = set()
        for card_id in user_card_ids:
            card = find_card_by_id(card_id, data["cards"])
            if card and card.get("faction") == faction:
                faction_cards.add(card_id)

        # Проверяем, собрано ли достижение
        faction_data = data["achievements"].get(faction, {"cards": []})
        total_cards = len(faction_data.get("cards", []))
        if len(faction_cards) < total_cards or total_cards == 0:
            await query.edit_message_text(
                f"❌ Достижение не завершено!\n"
                f"📊 Собрано: {len(faction_cards)}/{total_cards}\n"
                f"🏷 Фракция: {faction}"
            )
            return

        # ⭐ ВЫДАЁМ НАГРАДУ ⭐
        user_data["free_rolls"] = user_data.get("free_rolls", 0) + 30
        user_data["cents"] = user_data.get("cents", 0) + 30000
        claimed_achievements.append(faction)
        user_data["claimed_achievements"] = claimed_achievements
        save_data(data)

        await query.edit_message_text(
            f"🎉 **Достижение получено!**\n"
            f"🏆 {achievement_num}. {faction}\n"
            f"🎁 **Награда:**\n"
            f"• 🎲 +30 бесплатных наймов\n"
            f"• 💰 +30000 золота\n"
            f"Поздравляем!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад к достижениям", callback_data="achievements_menu")
            ]]),
            parse_mode="Markdown"
        )
        logger.info(f"Пользователь {user_id} получил достижение: {faction}")
    except Exception as e:
        logger.error(f"Ошибка claim_achievement: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def set_achievement_cards(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавляет карты в достижение фракции."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/set_achievement_cards [Фракция] [ID_карты1] [ID_карты2] ...\n\n"
                "**Пример:**\n"
                "/set_achievement_cards Замок 1 2 3 4 5",
                parse_mode="Markdown"
            )
            return
        
        faction = context.args[0]
        card_ids = [int(x) for x in context.args[1:]]
        
        valid_factions = [
            "Замок", "Оплот", "Башня", "Инферно",
            "Некрополис", "Темница", "Цитадель", "Крепость", "Сопряжение", "Фабрика"
        ]
        
        if faction not in valid_factions:
            await update.message.reply_text(
                f"⚠️ Недопустимая фракция!\n"
                f"Доступные: {', '.join(valid_factions)}"
            )
            return
        
        # Проверяем существование карт
        for card_id in card_ids:
            if not find_card_by_id(card_id, data["cards"]):
                await update.message.reply_text(f"⚠️ Существо #{card_id} не найдено!")
                return
        
        # Сохраняем карты достижения
        data["achievements"][faction]["cards"] = card_ids
        save_data(data)
        
        await update.message.reply_text(
            f"✅ **Достижение обновлено!**\n\n"
            f"🏷 Фракция: {faction}\n"
            f"🐦‍🔥 Существ: {len(card_ids)}\n"
            f"📋 ID: {', '.join(map(str, card_ids))}",
            parse_mode="Markdown"
        )
        
        logger.info(f"Админ обновил достижение {faction}: {card_ids}")
        
    except ValueError:
        await update.message.reply_text("⚠️ ID карт должны быть числами!")
    except Exception as e:
        logger.error(f"Ошибка set_achievement_cards: {e}")
        await update.message.reply_text("❌ Ошибка при настройке достижения")


async def check_card_notifications(application: Application) -> None:
    """Фоновая проверка уведомлений каждую минуту."""
    while True:
        try:
            await asyncio.sleep(60)  # Проверяем каждую минуту
            data = load_data()
            current_time = int(time.time())
            COOLDOWN_SECONDS = 2 * 60 * 60  # 2 часа
            notified_count = 0
            
            # ⭐ СОБИРАЕМ СПИСОК ПОЛЬЗОВАТЕЛЕЙ ДЛЯ УВЕДОМЛЕНИЯ ⭐
            users_to_notify = []
            for user_id, user_data in data["users"].items():
                last_card_time = user_data.get("last_card_time", 0)
                notification_sent = user_data.get("notification_sent", False)
                
                # Проверяем: прошло ли 2 часа И уведомление ещё не отправлено
                if last_card_time > 0 and not notification_sent:
                    time_passed = current_time - last_card_time
                    if time_passed >= COOLDOWN_SECONDS:
                        users_to_notify.append(user_id)
            
            # ⭐ ОТПРАВЛЯЕМ УВЕДОМЛЕНИЯ ⭐
            for user_id in users_to_notify:
                try:
                    await application.bot.send_message(
                        chat_id=user_id,
                        text=(
                            "🎉 **Вы снова можете нанять существо!**\n\n"
                            "⏰ Кулдаун завершился.\n"
                            "⚔️ Нажмите кнопку «⚔️ Нанять существо»"
                        ),
                        parse_mode="Markdown"
                    )
                    # ⭐ ОБНОВЛЯЕМ ФЛАГ В ДАННЫХ ⭐
                    data["users"][user_id]["notification_sent"] = True
                    notified_count += 1
                    logger.info(f"Уведомление отправлено пользователю {user_id}")
                except Exception as send_error:
                    pass
            
            # ⭐ СОХРАНЯЕМ ДАННЫЕ ОДИН РАЗ ПОСЛЕ ВСЕХ УВЕДОМЛЕНИЙ ⭐
            if notified_count > 0:
                save_data(data)
                logger.info(f"Отправлено {notified_count} уведомлений, данные сохранены")
            
        except Exception as e:
            pass
        await asyncio.sleep(60)

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
            f"🎉 **Промокод активирован!**\n"
            f"🎁 Код: {promo_code}\n"
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


async def forest_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню Леса с обычными кнопками."""
    try:
        # ⭐ КЛАВИАТУРА С КНОПКАМИ МЕНЮ ⭐
        keyboard = [
            [KeyboardButton("🏰 Форт на холме")],
            [KeyboardButton("🏕️ Лагерь Беженцев")], 
            [KeyboardButton("🔙 Назад в меню")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        caption = (
            "Вы входите в Лес!"
        )
        
        # ⭐ ПРОВЕРКА: callback или сообщение ⭐
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            try:
                await query.message.delete()
            except:
                pass
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=FOREST_IMAGE_URL, 
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=FOREST_IMAGE_URL,  # ← Ссылка на изображение
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Ошибка в forest_menu: {e}")
        # ⭐ ЗАПАСНОЙ ВАРИАНТ: если изображение не загрузилось ⭐
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Ошибка при загрузке изображения", show_alert=True)
        else:
            await update.message.reply_text(
                "🌲 **Лес**\n\n"
                "Добро пожаловать в Лес!\n\n"
                "Здесь вы можете:\n"
                "• 🔨 Получить улучшенное существо из 2 дубликатов\n\n"
                "Выберите действие:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

async def forest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок меню Леса."""
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "forest_craft":
            # Переход в крафт
            await craft(update, context)
        elif query.data == "forest_back":
            # Возврат в главное меню
            try:
                await query.message.delete()
            except:
                pass
            keyboard = [
                [KeyboardButton("⚔️ Нанять существо")],
                [KeyboardButton("🎲 Бросить кубик")],
                [
                    KeyboardButton("🛡 Казарма"),
                    KeyboardButton("👑 Мой герой"),
                ],
                [KeyboardButton("🌲 Лес")],
                [KeyboardButton("🍺 Таверна")],
                [KeyboardButton("🏆 Топ героев")],
                [KeyboardButton("🔄 Трейд")],
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Добро пожаловать! Используйте кнопки ниже:",
                reply_markup=reply_markup
            )
        
    except Exception as e:
        logger.error(f"Ошибка в forest_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def open_casino_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Открывает казино при нажатии на кнопку в главном меню."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        # Проверяем сброс попыток
        check_casino_reset(user_data)
        save_data(data)
        
        attempts = user_data.get("casino_attempts", 10) if user_data else 10
        cents = user_data.get("cents", 0) if user_data else 0
        
        keyboard = [
            [InlineKeyboardButton("🎰 Играть (3000 золота)", callback_data="casino_play")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🎰 **Казино**\n\n"
            f"📜 **Правила:**\n"
            f"• Стоимость игры: 3000 золота\n"
            f"• Крутите слот и получите 3 одинаковых значения\n"
            f"• При победе: 10 бесплатных наймов существ\n"
            f"• Попыток сегодня: {attempts}/10\n"
            f"• Сброс в 00:00 МСК\n"
            f"💰 Ваш баланс: {cents} золота\n",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в open_casino_from_button: {e}")
        await update.message.reply_text("❌ Ошибка при открытии казино")

async def city_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню Города."""
    try:
        # ⭐ КЛАВИАТУРА С КНОПКАМИ ГОРОДА ⭐
        keyboard = [
            [KeyboardButton("🛡 Казарма")],
            [KeyboardButton("👑 Мой герой")],
            [KeyboardButton("🔙 Назад в меню")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
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
                    "🏰 **Город**\n\n"
                    "Добро пожаловать в Город!\n\n"
                    "Здесь вы можете:\n"
                    "• 🛡 Посмотреть своих существ в Казарме\n"
                    "• 👑 Проверить статистику героя\n\n"
                    "Выберите действие:"
                ),
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "🏰 **Город**\n\n"
                "Добро пожаловать в Город!\n\n"
                "Здесь вы можете:\n"
                "• 🛡 Посмотреть своих существ в Казарме\n"
                "• 👑 Проверить статистику героя\n\n"
                "Выберите действие:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Ошибка в city_menu: {e}")


async def dungeon_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню Подземелья."""
    try:
        # ⭐ КЛАВИАТУРА С КНОПКАМИ ПОДЗЕМЕЛЬЯ ⭐
        keyboard = [
            [KeyboardButton("🩸 Жертвенный алтарь")],
            [KeyboardButton("🪓 Гильдия Наёмников")],
            [KeyboardButton("🔙 Назад в меню")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        caption = "🦇 Вы входите в подземелье!"
        
        # ⭐ ПРОВЕРКА: callback или сообщение ⭐
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            try:
                await query.message.delete()
            except:
                pass
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=DUNGEON_IMAGE_URL,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=DUNGEON_IMAGE_URL,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Ошибка в dungeon_menu: {e}")


async def dungeon_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок Подземелья."""
    try:
        query = update.callback_query
        await query.answer()
        
        # ⭐ КНОПКА "ЖЕРТВЕННЫЙ АЛТАРЬ" ⭐
        if query.data == "sacrifice_altar":
            keyboard = [
                [InlineKeyboardButton("📊 По редкости", callback_data="sacrifice_rarity")],
                [InlineKeyboardButton("📋 Все существа", callback_data="sacrifice_all")],
                [InlineKeyboardButton("🔙 Назад в Подземелье", callback_data="dungeon_back")],
            ]
            await query.edit_message_text(
                "🩸 **Жертвенный алтарь**\n\n",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            return
        
        # ⭐ КНОПКА "НАЗАД" ⭐
        elif query.data == "dungeon_back":
            await dungeon_menu(update, context)
            return
        
    except Exception as e:
        logger.error(f"Ошибка в dungeon_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


async def sacrifice_altar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает Жертвенный алтарь для пожертвования существ."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        # ⭐ КЛАВИАТУРА С КНОПКОЙ НАЗАД ⭐
        keyboard = [[KeyboardButton("🔙 Назад в Подземелье")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        if not user_data or not user_data.get("cards"):
            await update.message.reply_text(
                "❌ У вас нет существ для жертвоприношения!",
                reply_markup=reply_markup
            )
            return
        
        # ⭐ ФИЛЬТРУЕМ ТОЛЬКО UpgradeT1-UpgradeT7 ⭐
        upgrade_cards = []
        user_card_ids = user_data["cards"]
        card_counts = Counter(user_card_ids)
        
        for card_id, count in card_counts.items():
            card = find_card_by_id(card_id, data["cards"])
            if card and card.get("rarity") in ["UpgradeT1", "UpgradeT2", "UpgradeT3", 
                                                "UpgradeT4", "UpgradeT5", "UpgradeT6", "UpgradeT7", "T8"]:
                upgrade_cards.append((card_id, count, card))
        
        if not upgrade_cards:
            await update.message.reply_text(
                "❌ У вас нет существ редкости UpgradeT1-UpgradeT7 для жертвоприношения!",
                reply_markup=reply_markup
            )
            return
        
        # ⭐ СОХРАНЯЕМ СПИСОК КАРТ В context.user_data ⭐
        context.user_data[user_id] = {
            "step": "sacrifice_select",
            "sacrifice_cards": upgrade_cards,
        }
        
        # ⭐ INLINE КЛАВИАТУРА ДЛЯ СОРТИРОВКИ ⭐
        inline_keyboard = [
            [InlineKeyboardButton("📊 По редкости", callback_data="sacrifice_rarity")],
            [InlineKeyboardButton("📋 Все существа", callback_data="sacrifice_all")],
        ]
        
        # ⭐ ПРОВЕРКА: callback или сообщение ⭐
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            try:
                await query.message.delete()
            except:
                pass
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=ALTAR_IMAGE_URL,
                caption=(
                    "🩸 Жертвенный алтарь\n\n"
                    "Пожертвуйте существо и получите награду!\n\n"
                    "💰 Награды:\n"
                    "• UpgradeT1-T4: золото (50% от награды за крафт)\n"
                    "• UpgradeT5: 3 найма\n"
                    "• UpgradeT6: 7 наймов\n"
                    "• UpgradeT7: 15 наймов\n"
                    "• T8: 25 бесплатных наймов\n\n"
                    "Выберите способ просмотра:"
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard)
            )
        else:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=ALTAR_IMAGE_URL,
                caption=(
                    "🩸 Жертвенный алтарь\n\n"
                    "Пожертвуйте существо и получите награду!\n\n"
                    "💰 Награды:\n"
                    "• UpgradeT1-T4: золото (50% от награды за крафт)\n"
                    "• UpgradeT5: 3 найма\n"
                    "• UpgradeT6: 7 наймов\n"
                    "• UpgradeT7: 15 наймов\n"
                    "• T8: 25 бесплатных наймов\n\n"
                    "Выберите способ просмотра:"
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard)
            )
        
    except Exception as e:
        logger.error(f"Ошибка в sacrifice_altar: {e}")
        await update.message.reply_text("❌ Ошибка при открытии алтаря")


async def sacrifice_rarity_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню выбора редкости для жертвоприношения."""
    try:
        query = update.callback_query
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            await query.answer("❌ У вас нет существ!", show_alert=True)
            return
        
        # ⭐ СЧИТАЕМ КАРТЫ ПО РЕДКОСТЯМ ⭐
        user_card_ids = user_data["cards"]
        card_counts = Counter(user_card_ids)
        
        rarity_cards = {}
        for card_id, count in card_counts.items():
            card = find_card_by_id(card_id, data["cards"])
            if card:
                rarity = card.get("rarity", "")
                if rarity in ["UpgradeT1", "UpgradeT2", "UpgradeT3", 
                              "UpgradeT4", "UpgradeT5", "UpgradeT6", "UpgradeT7", "T8"]:
                    if rarity not in rarity_cards:
                        rarity_cards[rarity] = 0
                    rarity_cards[rarity] += count
        
        if not rarity_cards:
            await query.answer("❌ Нет существ для жертвоприношения!", show_alert=True)
            return
        
        # ⭐ СОЗДАЁМ КЛАВИАТУРУ С РЕДКОСТЯМИ ⭐
        keyboard = []
        for rarity in ["T8", "UpgradeT7", "UpgradeT6", "UpgradeT5", "UpgradeT4", 
                       "UpgradeT3", "UpgradeT2", "UpgradeT1"]:
            if rarity in rarity_cards:
                count = rarity_cards[rarity]
                keyboard.append([
                    InlineKeyboardButton(
                        f"{rarity} ({count} шт.)",
                        callback_data=f"sacrifice_show_rarity_{rarity}"
                    )
                ])
        
        keyboard.append([
            InlineKeyboardButton("🔙 Назад", callback_data="sacrifice_back")
        ])
        
        # ⭐ УДАЛЯЕМ СТАРОЕ СООБЩЕНИЕ И ОТПРАВЛЯЕМ НОВОЕ ⭐
        try:
            await query.message.delete()
        except:
            pass
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="🩸 Выберите редкость для жертвоприношения:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Ошибка sacrifice_rarity_menu: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


async def sacrifice_show_rarity(update: Update, context: ContextTypes.DEFAULT_TYPE, rarity: str) -> None:
    """Показывает существ конкретной редкости для жертвоприношения."""
    try:
        query = update.callback_query
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            await query.answer("❌ У вас нет существ!", show_alert=True)
            return
        
        # ⭐ СЧИТАЕМ КОЛИЧЕСТВО КАЖДОЙ КАРТЫ ⭐
        user_card_ids = user_data["cards"]
        card_counts = Counter(user_card_ids)
        
        rarity_cards = {}
        for card_id, count in card_counts.items():
            card = find_card_by_id(card_id, data["cards"])
            if card and card.get("rarity") == rarity:
                rarity_cards[card_id] = count
        
        if not rarity_cards:
            await query.answer(f"❌ Нет существ редкости {rarity}!", show_alert=True)
            return
        
        # ⭐ СОЗДАЁМ КЛАВИАТУРУ С СУЩЕСТВАМИ ⭐
        keyboard = []
        for card_id, count in rarity_cards.items():
            card = find_card_by_id(card_id, data["cards"])
            if card:
                reward = SACRIFICE_REWARDS.get(card["rarity"], {})
                reward_text = ""
                if reward.get("cents", 0) > 0:
                    reward_text = f"💰 {reward['cents']} золота"
                if reward.get("free_rolls", 0) > 0:
                    reward_text += f" 🎲 {reward['free_rolls']} наймов"
                
                # ⭐ ДОБАВЛЯЕМ КОЛИЧЕСТВО В ТЕКСТ КНОПКИ ⭐
                keyboard.append([
                    InlineKeyboardButton(
                        f"{card['title']} ({card['rarity']}) {count}шт. - {reward_text}",
                        callback_data=f"sacrifice_confirm_{card_id}"
                    )
                ])
        
        keyboard.append([
            InlineKeyboardButton("🔙 Назад к редкостям", callback_data="sacrifice_rarity")
        ])
        
        # ⭐ УДАЛЯЕМ СТАРОЕ СООБЩЕНИЕ И ОТПРАВЛЯЕМ НОВОЕ ⭐
        try:
            await query.message.delete()
        except:
            pass
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"🩸 Существа редкости {rarity}:\nВыберите существо для жертвоприношения:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Ошибка sacrifice_show_rarity: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


async def sacrifice_all_creatures(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает все существа для жертвоприношения."""
    try:
        query = update.callback_query
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            await query.answer("❌ У вас нет существ!", show_alert=True)
            return
        
        # ⭐ СЧИТАЕМ КОЛИЧЕСТВО КАЖДОЙ КАРТЫ ⭐
        user_card_ids = user_data["cards"]
        card_counts = Counter(user_card_ids)
        
        all_cards = {}
        for card_id, count in card_counts.items():
            card = find_card_by_id(card_id, data["cards"])
            if card and card.get("rarity") in ["UpgradeT1", "UpgradeT2", "UpgradeT3", 
                                                "UpgradeT4", "UpgradeT5", "UpgradeT6", "UpgradeT7", "T8"]:
                all_cards[card_id] = count
        
        if not all_cards:
            await query.answer("❌ Нет существ для жертвоприношения!", show_alert=True)
            return
        
        # ⭐ СОЗДАЁМ КЛАВИАТУРУ СО ВСЕМИ СУЩЕСТВАМИ ⭐
        keyboard = []
        for card_id, count in all_cards.items():
            card = find_card_by_id(card_id, data["cards"])
            if card:
                reward = SACRIFICE_REWARDS.get(card["rarity"], {})
                reward_text = ""
                if reward.get("cents", 0) > 0:
                    reward_text = f"💰 {reward['cents']} золота"
                if reward.get("free_rolls", 0) > 0:
                    reward_text += f" 🎲 {reward['free_rolls']} наймов"
                
                # ⭐ ДОБАВЛЯЕМ КОЛИЧЕСТВО В ТЕКСТ КНОПКИ ⭐
                keyboard.append([
                    InlineKeyboardButton(
                        f"{card['title']} ({card['rarity']}) {count}шт. - {reward_text}",
                        callback_data=f"sacrifice_confirm_{card_id}"
                    )
                ])
        
        keyboard.append([
            InlineKeyboardButton("🔙 Назад", callback_data="sacrifice_back")
        ])
        
        # ⭐ УДАЛЯЕМ СТАРОЕ СООБЩЕНИЕ И ОТПРАВЛЯЕМ НОВОЕ ⭐
        try:
            await query.message.delete()
        except:
            pass
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="🩸 Все существа для жертвоприношения:\nВыберите существо:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Ошибка sacrifice_all_creatures: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


async def sacrifice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок Жертвенного алтаря."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        # ⭐ КНОПКА "ПО РЕДКОСТИ" ⭐
        if query.data == "sacrifice_rarity":
            await sacrifice_rarity_menu(update, context)
            return
        
        # ⭐ КНОПКА "ПОКАЗАТЬ СУЩЕСТВА РЕДКОСТИ" ⭐
        if query.data.startswith("sacrifice_show_rarity_"):
            rarity = query.data.replace("sacrifice_show_rarity_", "")
            await sacrifice_show_rarity(update, context, rarity)
            return
        
        # ⭐ КНОПКА "ВСЕ СУЩЕСТВА" ⭐
        if query.data == "sacrifice_all":
            await sacrifice_all_creatures(update, context)
            return
        
        # ⭐ КНОПКА "ПОДТВЕРДИТЬ ЖЕРТВОПРИНОШЕНИЕ" ⭐
        if query.data.startswith("sacrifice_confirm_"):
            card_id = int(query.data.replace("sacrifice_confirm_", ""))
            
            # Проверяем, есть ли у игрока эта карта
            if not user_data or card_id not in user_data.get("cards", []):
                await query.answer("❌ У вас нет этого существа!", show_alert=True)
                return
            
            # Находим карту
            card = find_card_by_id(card_id, data["cards"])
            if not card:
                await query.answer("❌ Существо не найдено!", show_alert=True)
                return
            
            # Считаем количество этой карты в коллекции
            card_counts = Counter(user_data["cards"])
            count = card_counts.get(card_id, 1)
            
            # Получаем награду
            reward = SACRIFICE_REWARDS.get(card["rarity"], {"cents": 0, "free_rolls": 0})
            reward_text = []
            if reward["cents"] > 0:
                reward_text.append(f"💰 +{reward['cents']} золота")
            if reward["free_rolls"] > 0:
                reward_text.append(f"🎲 +{reward['free_rolls']} бесплатных наймов")
            
            # ⭐ КНОПКИ ПОДТВЕРЖДЕНИЯ ⭐
            keyboard = [
                [
                    InlineKeyboardButton("✅ Подтвердить", callback_data=f"sacrifice_execute_{card_id}"),
                    InlineKeyboardButton("❌ Отмена", callback_data="sacrifice_back")
                ]
            ]
            
            await query.edit_message_text(
                f"❓ Вы уверены, что хотите пожертвовать {card['title']}?\n\n"
                f"🌟 Редкость: {card['rarity']}\n"
                f"📦 В коллекции: {count} шт.\n"
                f"🎁 Награда:\n"
                f"{'\n'.join(reward_text)}\n\n"
                f"⚠️ Существо будет удалено из коллекции!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # ⭐ КНОПКА "ВЫПОЛНИТЬ ЖЕРТВОПРИНОШЕНИЕ" ⭐
        if query.data.startswith("sacrifice_execute_"):
            card_id = int(query.data.replace("sacrifice_execute_", ""))
            
            # Проверяем, есть ли у игрока эта карта
            if not user_data or card_id not in user_data.get("cards", []):
                await query.answer("❌ У вас нет этого существа!", show_alert=True)
                return
            
            # Находим карту
            card = find_card_by_id(card_id, data["cards"])
            if not card:
                await query.answer("❌ Существо не найдено!", show_alert=True)
                return
            
            # ⭐ УДАЛЯЕМ КАРТУ ⭐
            user_data["cards"].remove(card_id)
            
            # ⭐ ВЫДАЁМ НАГРАДУ ⭐
            reward = SACRIFICE_REWARDS.get(card["rarity"], {"cents": 0, "free_rolls": 0})
            user_data["cents"] = user_data.get("cents", 0) + reward["cents"]
            user_data["free_rolls"] = user_data.get("free_rolls", 0) + reward["free_rolls"]
            
            save_data(data)
            
            # ⭐ СООБЩЕНИЕ О НАГРАДЕ ⭐
            reward_text = []
            if reward["cents"] > 0:
                reward_text.append(f"💰 +{reward['cents']} золота")
            if reward["free_rolls"] > 0:
                reward_text.append(f"🎲 +{reward['free_rolls']} бесплатных наймов")
            
            keyboard = [[InlineKeyboardButton("🔙 Назад в алтарь", callback_data="sacrifice_back")]]
            
            await query.edit_message_text(
                f"✅ Жертвоприношение успешно!\n\n"
                f"🩸 Вы пожертвовали: {card['title']}\n"
                f"🌟 Редкость: {card['rarity']}\n\n"
                f"🎁 Награда:\n"
                f"{'\n'.join(reward_text)}",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return
        
        # ⭐ КНОПКА "НАЗАД" ⭐
        if query.data == "sacrifice_back":
            try:
                await query.message.delete()
            except:
                pass
            await sacrifice_altar(update, context)
            return
        
    except Exception as e:
        logger.error(f"Ошибка в sacrifice_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


def check_refugee_camp_reset(user_data: Dict) -> None:
    """Проверяет и сбрасывает Лагерь Беженцев в полночь по МСК."""
    import datetime
    
    # Получаем текущее время по МСК
    msk_tz = datetime.timezone(datetime.timedelta(hours=3))
    now_msk = datetime.datetime.now(msk_tz)
    
    # Получаем дату последнего сброса
    last_reset = user_data.get("refugee_camp_last_reset", 0)
    
    # ⭐ ЕСЛИ НАСТУПИЛ НОВЫЙ ДЕНЬ ⭐
    if (
        last_reset == 0
        or now_msk.day != datetime.datetime.fromtimestamp(last_reset, msk_tz).day
    ):
        # Сбрасываем покупку
        user_data["refugee_camp_purchased"] = False
        # Генерируем новое существо для предложения
        user_data["refugee_camp_offered_card"] = None
        # ⭐ ОБНОВЛЯЕМ ВРЕМЯ СБРОСА ⭐
        user_data["refugee_camp_last_reset"] = int(now_msk.timestamp())
        logger.info(f"Сброс Лагеря Беженцев для пользователя {user_data.get('username', 'unknown')}")
        

async def refugee_camp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает Лагерь Беженцев с ежедневным предложением."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data:
            user_data = {
                "username": update.effective_user.username or "",
                "first_name": update.effective_user.first_name or "",
                "cards": [],
                "total_points": 0,
                "season_points": 0,
                "cents": 0,
                "refugee_camp_last_reset": 0,
                "refugee_camp_offered_card": None,
                "refugee_camp_purchased": False,
            }
            data["users"][user_id] = user_data
        
        # ⭐ ПРОВЕРЯЕМ СБРОС ⭐
        check_refugee_camp_reset(user_data)
        save_data(data)
        
        # ⭐ ГЕНЕРИРУЕМ ПРЕДЛОЖЕНИЕ ЕСЛИ НЕТ ⭐
        if user_data.get("refugee_camp_offered_card") is None:
            # Собираем доступные карты (T1-T7, без Upgrade)
            available_cards = [
                card for card in data["cards"]
                if card["available"]
                and card.get("rarity") in ["T1", "T2", "T3", "T4", "T5", "T6", "T7"]
            ]
            if available_cards:
                # Выбираем случайное существо
                offered_card = random.choice(available_cards)
                user_data["refugee_camp_offered_card"] = offered_card["id"]
                save_data(data)
        
        # ⭐ ПОЛУЧАЕМ ИНФОРМАЦИЮ О СУЩЕСТВЕ ⭐
        offered_card_id = user_data.get("refugee_camp_offered_card")
        offered_card = find_card_by_id(offered_card_id, data["cards"]) if offered_card_id else None
        
        # ⭐ СЧИТАЕМ СТОИМОСТЬ (удвоенная награда за найм) ⭐
        base_reward = RARITY_BONUSES.get(offered_card["rarity"], {"cents": 0}) if offered_card else {"cents": 0}
        price = base_reward["cents"] * 2
        
        # ⭐ ПРОВЕРЯЕМ, КУПИЛ ЛИ УЖЕ ⭐
        purchased = user_data.get("refugee_camp_purchased", False)
        
        # ⭐ КЛАВИАТУРА С КНОПКАМИ ⭐
        if purchased or not offered_card:
            keyboard = [[KeyboardButton("🔙 Назад в Лес")]]
        else:
            keyboard = [
                [KeyboardButton(f"💰 Купить за {price} золота")],
                [KeyboardButton("🔙 Назад в Лес")],
            ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # ⭐ ОТПРАВЛЯЕМ ФОТО ЛАГЕРЯ БЕЖЕНЦЕВ ⭐
        if not offered_card:
            caption = (
                "🏕️ Лагерь Беженцев\n\n"
                "❌ Сегодня нет доступных существ для покупки.\n"
                "Заходите завтра после 00:00 МСК!"
            )
        elif purchased:
            caption = (
                "🏕️ Лагерь Беженцев\n\n"
                f"🃏 Существо дня: {offered_card['title']}\n"
                f"🌟 Редкость: {offered_card['rarity']}\n"
                f"💰 Цена: {price} золота\n\n"
                f"✅ Вы уже купили это существо сегодня!\n"
                f"⏰ Следующее предложение завтра в 00:00 МСК"
            )
        else:
            caption = (
                "🏕️ Лагерь Беженцев\n\n"
                f"🃏 Существо дня: {offered_card['title']}\n"
                f"🌟 Редкость: {offered_card['rarity']}\n"
                f"💰 Цена: {price} золота (2x от награды за найм)\n\n"
                f"⚠️ Можно купить только 1 раз в день!\n"
                f"⏰ Обновляется в 00:00 МСК\n\n"
                f"💳 Ваш баланс: {user_data.get('cents', 0)} золота"
            )
        
        # ⭐ ПРОВЕРКА: callback или сообщение ⭐
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            try:
                await query.message.delete()
            except:
                pass
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=REFUGEE_CAMP_IMAGE_URL,  # ← Изображение Лагеря
                caption=caption,
                reply_markup=reply_markup,
            )
        else:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=REFUGEE_CAMP_IMAGE_URL,  # ← Изображение Лагеря
                caption=caption,
                reply_markup=reply_markup,
            )
        
    except Exception as e:
        logger.error(f"Ошибка в refugee_camp: {e}")
        # ⭐ ЗАПАСНОЙ ВАРИАНТ ⭐
        keyboard = [[KeyboardButton("🔙 Назад в Лес")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "🏕️ Лагерь Беженцев\n\n"
            "❌ Ошибка при открытии Лагеря Беженцев!",
            reply_markup=reply_markup
        )


async def buy_refugee_creature(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает покупку существа в Лагере Беженцев."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data:
            await update.message.reply_text("❌ Вы ещё не начали игру!")
            return
        
        # ⭐ ПРОВЕРЯЕМ СБРОС ⭐
        check_refugee_camp_reset(user_data)
        
        # ⭐ ПРОВЕРЯЕМ, КУПИЛ ЛИ УЖЕ ⭐
        if user_data.get("refugee_camp_purchased", False):
            await update.message.reply_text(
                "❌ Вы уже купили существо сегодня!\n"
                "⏰ Следующее предложение завтра в 00:00 МСК",
            )
            return
        
        # ⭐ ПОЛУЧАЕМ ПРЕДЛОЖЕННОЕ СУЩЕСТВО ⭐
        offered_card_id = user_data.get("refugee_camp_offered_card")
        offered_card = find_card_by_id(offered_card_id, data["cards"]) if offered_card_id else None
        
        if not offered_card:
            await update.message.reply_text("❌ Сегодня нет доступных существ для покупки!")
            return
        
        # ⭐ СЧИТАЕМ СТОИМОСТЬ ⭐
        base_reward = RARITY_BONUSES.get(offered_card["rarity"], {"cents": 0})
        price = base_reward["cents"] * 2
        
        # ⭐ ПРОВЕРЯЕМ БАЛАНС ⭐
        if user_data.get("cents", 0) < price:
            await update.message.reply_text(
                f"❌ Недостаточно золота!\n"
                f"💰 Нужно: {price} золота\n"
                f"💳 У вас: {user_data.get('cents', 0)} золота\n\n"
                f"Нанимайте существ и получайте больше наград!",
            )
            return
        
        # ⭐ СПИСЫВАЕМ ЗОЛОТО ⭐
        user_data["cents"] -= price
        
        # ⭐ ДОБАВЛЯЕМ КАРТУ ⭐
        user_data["cards"].append(offered_card["id"])
        
        # ⭐ ОТМЕЧАЕМ КАК КУПЛЕННОЕ ⭐
        user_data["refugee_camp_purchased"] = True
        # ⭐ ИСПРАВЛЕНИЕ: НЕ обновляем last_reset здесь! ⭐
        # last_reset обновляется ТОЛЬКО в check_refugee_camp_reset() в 00:00 МСК
        
        save_data(data)
        
        # ⭐ ОТПРАВЛЯЕМ КАРТУ ⭐
        caption = (
            f"🏕️ Покупка успешна!\n\n"
            f"🃏 Вы получили: {offered_card['title']}\n"
            f"🌟 Редкость: {offered_card['rarity']}\n"
            f"💰 Списано: {price} золота\n\n"
            f"⏰ Следующее предложение завтра в 00:00 МСК"
        )
        
        await send_card(update, offered_card, context, caption=caption)
        
        logger.info(f"Игрок {user_id} купил существо #{offered_card_id} в Лагере Беженцев за {price} золота")
        
    except Exception as e:
        logger.error(f"Ошибка buy_refugee_creature: {e}")
        await update.message.reply_text("❌ Ошибка при покупке существа")


async def mercenary_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавляет существо в Гильдию Наёмников."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        # Проверяем аргументы: /mercenary_add [ID_карты] [цена]
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/mercenary_add [ID_карты] [цена_в_золоте]\n\n"
                "**Пример:**\n"
                "/mercenary_add 45 5000 - добавить карту #45 за 5000 золота",
                parse_mode="Markdown"
            )
            return
        
        card_id = int(context.args[0])
        price = int(context.args[1])
        
        # Проверяем существование карты
        card = find_card_by_id(card_id, data["cards"])
        if not card:
            await update.message.reply_text(f"⚠️ Карта #{card_id} не найдена!")
            return
        
        # Проверяем лимит слотов
        guild = data["mercenary_guild"]
        if len(guild["creatures"]) >= guild["max_slots"]:
            await update.message.reply_text(
                f"❌ **Лимит достигнут!**\n"
                f"В Гильдии может быть максимум {guild['max_slots']} существ.\n"
                f"Удалите одно существо командой /mercenary_remove",
                parse_mode="Markdown"
            )
            return
        
        # Проверяем, не добавлено ли уже это существо
        for creature in guild["creatures"]:
            if creature["card_id"] == card_id:
                await update.message.reply_text(f"⚠️ Это существо уже есть в Гильдии!")
                return
        
        # Добавляем существо
        guild["creatures"].append({
            "card_id": card_id,
            "price": price,
            "added_by": str(update.effective_user.id),
            "added_at": int(time.time())
        })
        
        save_data(data)
        
        await update.message.reply_text(
            f"✅ Существо добавлено в Гильдию Наёмников!\n\n"
            f"🃏 Карта: {card['title']} (#{card_id})\n"
            f"🌟 Редкость: {card['rarity']}\n"
            f"💰 Цена: {price} золота\n"
            f"📊 Всего существ в Гильдии: {len(guild['creatures'])}/{guild['max_slots']}",
        )
        
        logger.info(f"Админ добавил существо #{card_id} за {price} золота в Гильдию Наёмников")
        
    except ValueError:
        await update.message.reply_text("⚠️ ID и цена должны быть числами!")
    except Exception as e:
        logger.error(f"Ошибка mercenary_add: {e}")
        await update.message.reply_text("❌ Ошибка при добавлении существа")


async def mercenary_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаляет существо из Гильдии Наёмников."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        # Проверяем аргументы: /mercenary_remove [ID_карты]
        if not context.args:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/mercenary_remove [ID_карты]\n\n"
                "**Пример:**\n"
                "/mercenary_remove 45",
                parse_mode="Markdown"
            )
            return
        
        card_id = int(context.args[0])
        
        # Ищем существо в Гильдии
        guild = data["mercenary_guild"]
        for i, creature in enumerate(guild["creatures"]):
            if creature["card_id"] == card_id:
                removed = guild["creatures"].pop(i)
                save_data(data)
                
                card = find_card_by_id(card_id, data["cards"])
                card_name = card["title"] if card else f"#{card_id}"
                
                await update.message.reply_text(
                    f"✅ Существо удалено из Гильдии!\n\n"
                    f"🃏 Карта: {card_name}\n"
                    f"💰 Цена была: {removed['price']} золота\n"
                    f"📊 Осталось существ: {len(guild['creatures'])}/{guild['max_slots']}",
                )
                return
        
        await update.message.reply_text(f"⚠️ Существо #{card_id} не найдено в Гильдии!")
        
    except ValueError:
        await update.message.reply_text("⚠️ ID должен быть числом!")
    except Exception as e:
        logger.error(f"Ошибка mercenary_remove: {e}")
        await update.message.reply_text("❌ Ошибка при удалении существа")


async def mercenary_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список существ в Гильдии Наёмников."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        guild = data["mercenary_guild"]
        
        if not guild["creatures"]:
            await update.message.reply_text(
                "📭 Гильдия Наёмников пуста!\n\n"
                "Добавьте существ командой /mercenary_add",
            )
            return
        
        message_text = "🪓 Гильдия Наёмников\n\n"
        message_text += f"📊 Существ: {len(guild['creatures'])}/{guild['max_slots']}\n\n"
        
        for i, creature in enumerate(guild["creatures"], 1):
            card = find_card_by_id(creature["card_id"], data["cards"])
            card_name = card["title"] if card else "Неизвестно"
            rarity = card["rarity"] if card else "?"
            
            message_text += (
                f"{i}. {card_name} ({rarity})\n"
                f"   💰 Цена: {creature['price']} золота\n"
                f"   🆔 ID: {creature['card_id']}\n\n"
            )
        
        await update.message.reply_text(message_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка mercenary_list: {e}")
        await update.message.reply_text("❌ Ошибка при получении списка")


async def mercenary_update_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обновляет цену существа в Гильдии Наёмников."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        # Проверяем аргументы: /mercenary_price [ID_карты] [новая_цена]
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "ℹ️ Формат команды:\n"
                "/mercenary_price [ID_карты] [новая_цена]\n\n"
                "Пример:\n"
                "/mercenary_price 45 10000"
            )
            return
        
        card_id = int(context.args[0])
        new_price = int(context.args[1])
        
        # Ищем существо в Гильдии
        guild = data["mercenary_guild"]
        for creature in guild["creatures"]:
            if creature["card_id"] == card_id:
                old_price = creature["price"]
                creature["price"] = new_price
                save_data(data)
                
                card = find_card_by_id(card_id, data["cards"])
                card_name = card["title"] if card else f"#{card_id}"
                
                await update.message.reply_text(
                    f"✅ Цена обновлена!\n\n"
                    f"🃏 Карта: {card_name}\n"
                    f"💰 Было: {old_price} золота\n"
                    f"💰 Стало: {new_price} золота",
                )
                return
        
        await update.message.reply_text(f"⚠️ Существо #{card_id} не найдено в Гильдии!")
        
    except ValueError:
        await update.message.reply_text("⚠️ ID и цена должны быть числами!")
    except Exception as e:
        logger.error(f"Ошибка mercenary_update_price: {e}")
        await update.message.reply_text("❌ Ошибка при обновлении цены")

async def mercenary_guild(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает Гильдию Наёмников с доступными товарами."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        guild = data["mercenary_guild"]
        
        # ⭐ ПРОВЕРЯЕМ ЕСТЬ ЛИ ТОВАРЫ ⭐
        has_creatures = len(guild["creatures"]) > 0
        has_rolls_package = True  # Пакет наймов всегда доступен
        
        if not has_creatures and not has_rolls_package:
            keyboard = [[KeyboardButton("🔙 Назад в Подземелье")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "🪓 Гильдия Наёмников\n"
                "❌ Сейчас нет доступных товаров.\n"
                "Заходите позже!",
                reply_markup=reply_markup,
            )
            return

        caption = ("🪓 Вы заходите в Гильдию Наёмников!\n\n")

        # ⭐ ПРОВЕРКА: callback или сообщение ⭐
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            try:
                await query.message.delete()
            except:
                pass
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=MERCENARY_GUILD_IMAGE_URL,  # ← Изображение Гильдии
                caption=caption,
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=MERCENARY_GUILD_IMAGE_URL,  # ← Изображение Гильдии
                caption=caption,
                parse_mode="Markdown"
            )
        
        # ⭐ СОХРАНЯЕМ ИНДЕКС СТРАНИЦЫ В context.user_data ⭐
        if user_id not in context.user_data:
            context.user_data[user_id] = {}
        context.user_data[user_id]["mercenary_page"] = 0
        context.user_data[user_id]["mercenary_type"] = "creatures"  # По умолчанию
        
        # ⭐ ОТПРАВЛЯЕМ ПЕРВУЮ СТРАНИЦУ ⭐
        await show_mercenary_page(update, context, 0)
        
    except Exception as e:
        logger.error(f"Ошибка в mercenary_guild: {e}")
        await update.message.reply_text("❌ Ошибка при открытии Гильдии")


async def show_mercenary_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    """Показывает страницу Гильдии Наёмников с товарами."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        guild = data["mercenary_guild"]
        creatures = guild["creatures"]
        
        # ⭐ ДОБАВЛЯЕМ ПАКЕТ НАЙМОВ КАК ПЕРВЫЙ ТОВАР ⭐
        all_items = [FREE_ROLLS_PACKAGE] + creatures
        total_items = len(all_items)
        
        if total_items == 0:
            await update.message.reply_text("❌ Нет товаров в Гильдии!")
            return
        
        # ⭐ НАВИГАЦИЯ ПО СТРАНИЦАМ ⭐
        items_per_page = 1  # Показываем по 1 товару за раз
        total_pages = total_items
        
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        context.user_data[user_id]["mercenary_page"] = page
        
        # Получаем товар для текущей страницы
        item = all_items[page]
        is_rolls_package = item.get("id") == "free_rolls_package"
        
        # ⭐ ПРОВЕРЯЕМ БАЛАНС ИГРОКА ⭐
        can_afford = user_data.get("cents", 0) >= item["price"] if user_data else False
        
        # ⭐ СОЗДАЁМ INLINE КЛАВИАТУРУ ⭐
        inline_keyboard = []
        
        # Кнопка "Купить"
        if is_rolls_package:
            buy_text = f"💰 Купить за {item['price']} золота"
            callback_data = f"mercenary_buy_rolls"
        else:
            buy_text = f"💰 Купить за {item['price']} золота"
            callback_data = f"mercenary_buy_{item['card_id']}"
        
        if not can_afford:
            buy_text += " ❌ (Недостаточно золота)"
        
        inline_keyboard.append([
            InlineKeyboardButton(buy_text, callback_data=callback_data)
        ])
        
        # Кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"mercenary_nav_{page - 1}"))
        
        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="mercenary_info"))
        
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"mercenary_nav_{page + 1}"))
        
        inline_keyboard.append(nav_buttons)
        
        # ⭐ ФОРМИРУЕМ CAPTION ⭐
        if is_rolls_package:
            caption = (
                f"🎁 Товар: {item['title']}\n"
                f"💰 Цена: {item['price']} золота\n"
                f"💳 Ваш баланс: {user_data.get('cents', 0) if user_data else 0} золота\n"
                f"📊 Страница {page + 1}/{total_pages}"
            )
            # ⭐ ОТПРАВЛЯЕМ БЕЗ ФОТО (текстовое сообщение) ⭐
            if hasattr(update, 'callback_query') and update.callback_query:
                query = update.callback_query
                try:
                    media = InputMediaPhoto(media=FREE_ROLLS_IMAGE_URL, caption=caption)
                    await query.edit_message_media(
                        media=media,
                        reply_markup=InlineKeyboardMarkup(inline_keyboard), 
                    )
                except Exception as edit_error:
                    logger.error(f"Ошибка редактирования: {edit_error}")
                    try:
                        await query.message.delete()
                    except:
                        pass
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=FREE_ROLLS_IMAGE_URL,
                        caption=caption,
                        reply_markup=InlineKeyboardMarkup(inline_keyboard),
                    )
            else:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=FREE_ROLLS_IMAGE_URL,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard),
                )
        else:
            # ⭐ СУЩЕСТВО - ОТПРАВЛЯЕМ С ФОТО ⭐
            card = find_card_by_id(item["card_id"], data["cards"])
            if not card:
                await update.message.reply_text("❌ Ошибка: существо не найдено!")
                return
            
            caption = (
                f"🃏 Существо: {card['title']}\n"
                f"🌟 Редкость: {card['rarity']}\n"
                f"💰 Цена: {item['price']} золота\n"
                f"💳 Ваш баланс: {user_data.get('cents', 0) if user_data else 0} золота\n"
                f"📊 Страница {page + 1}/{total_pages}"
            )
            
            # ⭐ ОТПРАВЛЯЕМ ФОТО СУЩЕСТВА ⭐
            if hasattr(update, 'callback_query') and update.callback_query:
                query = update.callback_query
                try:
                    media = InputMediaPhoto(media=card["image_url"], caption=caption)
                    await query.edit_message_media(
                        media=media,
                        reply_markup=InlineKeyboardMarkup(inline_keyboard),
                    )
                except Exception as edit_error:
                    logger.error(f"Ошибка редактирования: {edit_error}")
                    try:
                        await query.message.delete()
                    except:
                        pass
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=card["image_url"],
                        caption=caption,
                        reply_markup=InlineKeyboardMarkup(inline_keyboard),
                        parse_mode="Markdown"
                    )
            else:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=card["image_url"],
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard),
                    parse_mode="Markdown"
                )
        
    except Exception as e:
        logger.error(f"Ошибка show_mercenary_page: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("❌ Произошла ошибка")


async def mercenary_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок Гильдии Наёмников."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        # ⭐ НАВИГАЦИЯ ПО СТРАНИЦАМ ⭐
        if query.data.startswith("mercenary_nav_"):
            page = int(query.data.replace("mercenary_nav_", ""))
            await show_mercenary_page(update, context, page)
            return
        
        # ⭐ ИНФОРМАЦИЯ ⭐
        if query.data == "mercenary_info":
            await query.answer("🪓 Гильдия Наёмников - покупайте существ и наймы за золото!", show_alert=False)
            return
        
        # ⭐ НАЗАД ⭐
        if query.data == "mercenary_back":
            await dungeon_menu(update, context)
            return
        
        # ⭐ ПОКУПКА ПАКЕТА НАЙМОВ ⭐
        if query.data == "mercenary_buy_rolls":
            package = FREE_ROLLS_PACKAGE
            price = package["price"]
            
            # Проверяем баланс
            if not user_data or user_data.get("cents", 0) < price:
                await query.answer(f"❌ Недостаточно золота! Нужно {price}", show_alert=True)
                return
            
            # ⭐ СПИСЫВАЕМ ЗОЛОТО ⭐
            user_data["cents"] -= price
            
            # ⭐ ДОБАВЛЯЕМ НАЙМЫ ⭐
            user_data["free_rolls"] = user_data.get("free_rolls", 0) + package["rolls"]
            
            save_data(data)
            
            # ⭐ ИСПРАВЛЕНИЕ: УДАЛЯЕМ СООБЩЕНИЕ ПЕРЕД ОТПРАВКОЙ ⭐
            try:
                await query.message.delete()
            except:
                pass
            
            # ⭐ ОТПРАВЛЯЕМ НОВОЕ СООБЩЕНИЕ О ПОКУПКЕ ⭐
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(
                    f"✅ Покупка успешна!\n\n"
                    f"🎁 Вы получили: {package['title']}\n"
                    f"💰 Списано: {price} золота\n"
                    f"💳 Остаток: {user_data['cents']} золота"
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад в Гильдию", callback_data="mercenary_back_to_guild")
                ]]), 
            )
            
            # ⭐ ВОЗВРАЩАЕМ В ГИЛЬДИЮ ЧЕРЕЗ 2 СЕКУНДЫ ⭐
            await asyncio.sleep(2)
            await show_mercenary_page(update, context, context.user_data.get(user_id, {}).get("mercenary_page", 0))
            return
        
        # ⭐ ПОКУПКА СУЩЕСТВА ⭐
        if query.data.startswith("mercenary_buy_"):
            card_id = int(query.data.replace("mercenary_buy_", ""))
            
            # Ищем существо в Гильдии
            guild = data["mercenary_guild"]
            creature = None
            for c in guild["creatures"]:
                if c["card_id"] == card_id:
                    creature = c
                    break
            
            if not creature:
                await query.edit_message_text("❌ Это существо больше недоступно!")
                return
            
            # Проверяем баланс
            price = creature["price"]
            if not user_data or user_data.get("cents", 0) < price:
                await query.answer(f"❌ Недостаточно золота! Нужно {price}", show_alert=True)
                return
            
            # ⭐ СПИСЫВАЕМ ЗОЛОТО ⭐
            user_data["cents"] -= price
            
            # ⭐ ДОБАВЛЯЕМ КАРТУ ⭐
            user_data["cards"].append(card_id)
            
            save_data(data)
            
            # ⭐ ОТПРАВЛЯЕМ КАРТУ ⭐
            card = find_card_by_id(card_id, data["cards"])
            if card:
                caption = (
                    f"✅ Покупка успешна!\n"
                    f"🃏 Вы получили: {card['title']}\n"
                    f"🌟 Редкость: {card['rarity']}\n"
                    f"💰 Списано: {price} золота\n"
                    f"💳 Остаток: {user_data['cents']} золота"
                )
                
                # ⭐ ПОКАЗЫВАЕМ КАРТУ ⭐
                try:
                    await query.message.delete()
                except:
                    pass
                await send_card(update, card, context, caption=caption)
                
                # ⭐ ВОЗВРАЩАЕМ В ГИЛЬДИЮ ⭐
                await asyncio.sleep(2)
                await show_mercenary_page(update, context, context.user_data.get(user_id, {}).get("mercenary_page", 0))
            
            logger.info(f"Игрок {user_id} купил существо #{card_id} за {price} золота в Гильдии Наёмников")
            return
        
        # ⭐ КНОПКА "НАЗАД В ГИЛЬДИЮ" (после покупки) ⭐
        if query.data == "mercenary_back_to_guild":
            await show_mercenary_page(update, context, context.user_data.get(user_id, {}).get("mercenary_page", 0))
            return
        
    except Exception as e:
        logger.error(f"Ошибка mercenary_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

def get_damage_from_range(damage_value) -> int:
    """
    Получает значение урона из диапазона.
    Если диапазон (например, "10-20"), возвращает случайное число.
    Если число, возвращает его.
    """
    if damage_value is None or damage_value == 0:
        return 0
    
    # Проверяем, является ли строкой с диапазоном
    if isinstance(damage_value, str) and "-" in damage_value:
        try:
            min_damage, max_damage = map(int, damage_value.split("-"))
            return random.randint(min_damage, max_damage)
        except ValueError:
            return 0
    else:
        # Если это просто число
        try:
            return int(damage_value)
        except (ValueError, TypeError):
            return 0


def format_damage_display(damage_value) -> str:
    """
    Форматирует отображение урона.
    Если диапазон, возвращает "10-20", если число - "15".
    """
    if damage_value is None or damage_value == 0:
        return "0"
    
    if isinstance(damage_value, str) and "-" in damage_value:
        return damage_value
    else:
        return str(damage_value)

async def battles_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню Сражений."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)

        # ⭐ ПРОВЕРКА И СБРОС СЧЁТЧИКА ВЫЗОВОВ ⭐
        check_battle_challenges_reset(user_data)
        save_data(data)
        
        # ⭐ ПРОВЕРЯЕМ, ЕСТЬ ЛИ АКТИВНАЯ БИТВА ⭐
        has_active_battle = False
        for battle in data.get("active_battles", {}).values():
            if battle.get("red_player") == user_id or battle.get("blue_player") == user_id:
                has_active_battle = True
                break

        # ⭐ ПОЛУЧАЕМ СТАТИСТИКУ СРАЖЕНИЙ ⭐
        battle_experience = user_data.get("battle_experience", 0)
        battle_level = user_data.get("battle_level", 0)
        win_streak = user_data.get("win_streak", 0)
        
        # ⭐ СЧИТАЕМ МЕСТО В ТОПе СРАЖЕНИЙ ⭐
        battle_rank = calculate_battle_rank(user_id, data)

        can_challenge, remaining_challenges = check_battle_challenge_limit(user_id, data)
        
        # ⭐ КЛАВИАТУРА С КНОПКАМИ СРАЖЕНИЙ ⭐
        keyboard = [
            [KeyboardButton("🛡️ Моя Армия")],
            [KeyboardButton("🔍 Найти противника")],
            [KeyboardButton("🏆 Топ сражений")], 
        ]
        
        keyboard.append([KeyboardButton("🔙 Назад в меню")])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        streak_info = f"🔥 Серия побед: {win_streak}\n"
        if win_streak > 0 and win_streak % 5 == 0:
            streak_info += f"🎁 Следующая награда: {win_streak + 5} наймов!\n"
        elif win_streak > 0:
            next_reward = ((win_streak // 5) + 1) * 5
            streak_info += f"🎁 До следующей награды: {next_reward - win_streak} побед\n"

        # ⭐ ПОКАЗЫВАЕМ ПРОГРЕСС ДО СЛЕДУЮЩЕГО УРОВНЯ ⭐
        LEVEL_THRESHOLDS = {
            1: 1000,
            2: 3000,
            3: 7000,
            4: 20000,
            5: 40000,
        }
        
        next_level = battle_level + 1
        if next_level in LEVEL_THRESHOLDS:
            next_exp = LEVEL_THRESHOLDS[next_level]
            exp_needed = max(0, next_exp - battle_experience)
            level_progress = f"📊 Уровень: {battle_level} ({exp_needed} до {next_level} уровня)\n"
        else:
            level_progress = f"📊 Уровень: {battle_level} (МАКС)\n"        
        
        caption = (
            "⚔️ Сражения\n"
            "Управляйте своей армией и сражайтесь с другими героями!\n\n"
            f"💥 Ваш боевой опыт: {battle_experience}\n"
            f"{level_progress}"
            f"🏆 Ваше место в топе сражений: {battle_rank}\n"
            f"{streak_info}"
            f"⚔️ Осталось вызовов сегодня: {remaining_challenges}/3"
        )
        
        # ⭐ ПРОВЕРКА: callback или сообщение ⭐
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            try:
                await query.message.delete()
            except:
                pass
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=BATTLES_IMAGE_URL,
                caption=caption,
                reply_markup=reply_markup
            )
        else:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=BATTLES_IMAGE_URL,
                caption=caption,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Ошибка в battles_menu: {e}")
        keyboard = [
            [KeyboardButton("🛡️ Моя Армия")],
            [KeyboardButton("🔍 Найти противника")],
            [KeyboardButton("🏆 Топ сражений")],
            [KeyboardButton("🔙 Назад в меню")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "⚔️ Сражения\n\nУправляйте своей армией!",
            reply_markup=reply_markup
        )
async def my_army(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает армию пользователя с сортировкой по редкостям."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        # ⭐ КЛАВИАТУРА С КНОПКОЙ НАЗАД ⭐
        keyboard = [[KeyboardButton("🔙 Назад в Сражения")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        if not user_data or not user_data.get("cards"):
            await update.message.reply_text(
                "❌ У вас нет существ в армии!\n"
                "Нанимайте существ, чтобы создать свою армию.",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            return
        
        # ⭐ СЧИТАЕМ СУЩЕСТВ ПО РЕДКОСТЯМ ⭐
        user_card_ids = user_data["cards"]
        card_counts = Counter(user_card_ids)
        
        # ⭐ ГРУППИРУЕМ ПО РЕДКОСТЯМ ⭐
        rarity_groups = {}
        for card_id, count in card_counts.items():
            card = find_card_by_id(card_id, data["cards"])
            if card:
                # ⭐ УБРАЛИ ПРОВЕРКУ has_stats() ⭐
                rarity = card.get("rarity", "T1")
                if rarity not in rarity_groups:
                    rarity_groups[rarity] = []
                rarity_groups[rarity].append((card_id, count, card))
        
        if not rarity_groups:
            await update.message.reply_text(
                "❌ У вас нет существ!",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            return
        
        # ⭐ НОВАЯ СОРТИРОВКА: UpgradeT7, T7, ..., UpgradeT1, T1 ⭐
        rarity_order = [
            "UpgradeT7", "T7",
            "UpgradeT6", "T6",
            "UpgradeT5", "T5",
            "UpgradeT4", "T4",
            "UpgradeT3", "T3",
            "UpgradeT2", "T2",
            "UpgradeT1", "T1"
        ]
        sorted_rarities = [r for r in rarity_order if r in rarity_groups]
        
        # ⭐ СОХРАНЯЕМ ДАННЫЕ В context.user_data ⭐
        context.user_data[user_id] = {
            "step": "army_select",
            "rarity_groups": rarity_groups,
            "sorted_rarities": sorted_rarities,
            "army_page": 0,
            "selected_squads": user_data.get("army_squads", []).copy(),
        }
        
        # ⭐ ОТПРАВЛЯЕМ ПЕРВУЮ СТРАНИЦУ ⭐
        await show_army_page(update, context, 0)
        
    except Exception as e:
        logger.error(f"Ошибка в my_army: {e}")
        await update.message.reply_text("❌ Ошибка при показе армии")


async def show_army_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    """Показывает страницу существ для выбора в отряд."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if user_id not in context.user_data:
            await update.message.reply_text("❌ Сессия армии истекла!")
            return
        
        army_info = context.user_data[user_id]
        rarity_groups = army_info.get("rarity_groups", {})
        sorted_rarities = army_info.get("sorted_rarities", [])
        selected_squads = army_info.get("selected_squads", [])
        
        # ⭐ ИСПРАВЛЕНИЕ: Конвертируем page в int СРАЗУ ⭐
        page = int(page)
        
        # ⭐ СОБИРАЕМ ВСЕ СУЩЕСТВА В СПИСОК ⭐
        all_creatures = []
        for rarity in sorted_rarities:
            for card_id, count, card in rarity_groups.get(rarity, []):
                all_creatures.append((card_id, count, card, rarity))
        
        if not all_creatures:
            await update.message.reply_text("❌ У вас нет существ!")
            return
        
        # ⭐ НАВИГАЦИЯ ПО СТРАНИЦАМ ⭐
        creatures_per_page = 10  # ← ИЗМЕНЕНО С 5 НА 10
        total_pages = (len(all_creatures) + creatures_per_page - 1) // creatures_per_page
        
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        context.user_data[user_id]["army_page"] = page
        
        # ⭐ ПОЛУЧАЕМ СУЩЕСТВА ДЛЯ ТЕКУЩЕЙ СТРАНИЦЫ ⭐
        start_index = page * creatures_per_page
        end_index = min(start_index + creatures_per_page, len(all_creatures))
        page_creatures = all_creatures[start_index:end_index]
        
        # ⭐ СОЗДАЁМ INLINE КЛАВИАТУРУ ⭐
        inline_keyboard = []
        for card_id, count, card, rarity in page_creatures:
            is_selected = any(squad.get("card_id") == card_id for squad in selected_squads)
            
            # ⭐ УБРАЛИ ПРОВЕРКУ СТАТОВ ⭐
            if is_selected:
                button_text = f"✅ {card['title']} - {count} шт."
                callback_data = f"army_remove_{card_id}"
            else:
                button_text = f"➕ {card['title']} ({card['rarity']}) - {count} шт."
                callback_data = f"army_add_{card_id}"
            
            inline_keyboard.append([
                InlineKeyboardButton(button_text, callback_data=callback_data)
            ])
        
        # ⭐ КНОПКИ НАВИГАЦИИ ⭐
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"army_nav_{page - 1}"))
        
        nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="army_info"))
        
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"army_nav_{page + 1}"))
        
        inline_keyboard.append(nav_buttons)
        
        # ⭐ КНОПКА ЗАВЕРШЕНИЯ ⭐
        if len(selected_squads) >= MAX_ARMY_SQUADS:
            inline_keyboard.append([
                InlineKeyboardButton("✅ Завершить формирование армии", callback_data="army_finish")
            ])
        else:
            inline_keyboard.append([
                InlineKeyboardButton(f"📋 Отряды: {len(selected_squads)}/{MAX_ARMY_SQUADS}", 
                                   callback_data="army_squads_info")
            ])

        if selected_squads:  # Показываем только если есть выбранные отряды
            inline_keyboard.append([
                InlineKeyboardButton("🗑️ Сбросить текущую армию", callback_data="army_reset")
            ])
        
        # ⭐ КНОПКА НАЗАД ⭐
        inline_keyboard.append([
            InlineKeyboardButton("🔙 Назад в Сражения", callback_data="army_back")
        ])
        
        # ⭐ ФОРМИРУЕМ CAPTION ⭐
        caption = (
            f"🛡️ Моя Армия\n\n"
            f"📊 Выберите существ для отрядов:\n"
            f"📄 Страница {page + 1}/{total_pages}\n\n"
            f"📋 Текущие отряды: {len(selected_squads)}/{MAX_ARMY_SQUADS}\n"
        )
        
        if selected_squads:
            caption += "\nВаши отряды:\n"
            for i, squad in enumerate(selected_squads, 1):
                card = find_card_by_id(squad["card_id"], data["cards"])
                if card:
                    caption += f"{i}. {card['title']} - {squad['count']} шт.\n"
        
        # ⭐ ОТПРАВЛЯЕМ СООБЩЕНИЕ ⭐
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            try:
                await query.edit_message_text(
                    caption,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard)
                )
            except Exception as edit_error:
                logger.error(f"Ошибка редактирования: {edit_error}")
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=caption,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard)
                )
        else:
            await update.message.reply_text(
                caption,
                reply_markup=InlineKeyboardMarkup(inline_keyboard)
            )
        
    except Exception as e:
        logger.error(f"Ошибка show_army_page: {e}")
        await update.message.reply_text("❌ Произошла ошибка")


async def army_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок армии."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if user_id not in context.user_data:
            await query.edit_message_text("❌ Сессия армии истекла!")
            return
        
        army_info = context.user_data[user_id]
        selected_squads = army_info.get("selected_squads", [])
        
        # ⭐ НАВИГАЦИЯ ПО СТРАНИЦАМ ⭐
        if query.data.startswith("army_nav_"):
            page = int(query.data.replace("army_nav_", ""))
            await show_army_page(update, context, page)
            return
        
        # ⭐ ИНФОРМАЦИЯ ⭐
        if query.data == "army_info":
            await query.answer("📄 Используйте ◀️ и ▶️ для навигации", show_alert=False)
            return
        
        # ⭐ ИНФОРМАЦИЯ ОБ ОТРЯДАХ ⭐
        if query.data == "army_squads_info":
            squads_text = "\n".join([f"{i}. {s['card_id']}: {s['count']} шт." 
                                    for i, s in enumerate(selected_squads, 1)])
            await query.answer(f"📋 Ваши отряды:\n{squads_text}", show_alert=True)
            return
        
        # ⭐ НАЗАД ⭐
        if query.data == "army_back":
            await battles_menu(update, context)
            return

        # ⭐ НОВАЯ КНОПКА СБРОСА АРМИИ ⭐
        if query.data == "army_reset":
            # Очищаем все выбранные отряды
            army_info["selected_squads"] = []
            user_data["army_squads"] = []
            save_data(data)
    
            await query.answer("🗑️ Армия сброшена!", show_alert=False)
            await show_army_page(update, context, army_info.get("army_page", 0))
            return
        
        # ⭐ ДОБАВИТЬ В ОТРЯД ⭐
        if query.data.startswith("army_add_"):
            card_id = int(query.data.replace("army_add_", ""))
            
            # Проверяем, не выбрано ли уже
            if any(squad.get("card_id") == card_id for squad in selected_squads):
                await query.answer("❌ Это существо уже в отряде!", show_alert=True)
                return
            
            # Проверяем, не заполнены ли все отряды
            if len(selected_squads) >= MAX_ARMY_SQUADS:
                await query.answer(f"❌ Максимум {MAX_ARMY_SQUADS} отрядов!", show_alert=True)
                return
            
            # Получаем информацию о карте
            card = find_card_by_id(card_id, data["cards"])
            if not card:
                await query.answer("❌ Существо не найдено!", show_alert=True)
                return
            
            # Считаем количество у игрока
            card_counts = Counter(user_data.get("cards", []))
            max_count = card_counts.get(card_id, 0)
            
            if max_count <= 0:
                await query.answer("❌ У вас нет этого существа!", show_alert=True)
                return
            
            # ⭐ СОХРАНЯЕМ ВРЕМЕННО ВЫБРАННУЮ КАРТУ ⭐
            army_info["pending_add"] = {
                "card_id": card_id,
                "max_count": max_count,
                "card_name": card["title"],
            }
            
            # ⭐ ЗАПРОС КОЛИЧЕСТВА — ИНЛАЙН КЛАВИАТУРА ⭐
            half_count = max_count // 2  # Половина (с округлением вниз)
            
            keyboard = [
                [
                    InlineKeyboardButton(f"1 шт.", callback_data=f"army_qty_1"),
                    InlineKeyboardButton(f"Половина ({half_count} шт.)", callback_data=f"army_qty_{half_count}"),
                    InlineKeyboardButton(f"Все ({max_count} шт.)", callback_data=f"army_qty_{max_count}"),
                ],
                [
                    InlineKeyboardButton("❌ Отмена", callback_data="army_cancel_add")
                ]
            ]
            
            await query.edit_message_text(
                f"➕ Добавление в отряд\n\n"
                f"🃏 Существо: {card['title']}\n"
                f"🌟 Редкость: {card['rarity']}\n"
                f"📦 Доступно: {max_count} шт.\n\n"
                f"Выберите количество:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            # ⭐ УСТАНАВЛИВАЕМ ФЛАГ ОЖИДАНИЯ ⭐
            army_info["step"] = "army_wait_quantity"
            return
        
        # ⭐ ВЫБОР КОЛИЧЕСТВА ⭐
        if query.data.startswith("army_qty_"):
            quantity = int(query.data.replace("army_qty_", ""))
            pending = army_info.get("pending_add", {})
            
            if not pending:
                await query.answer("❌ Ошибка: нет выбранного существа!", show_alert=True)
                return
            
            card_id = pending["card_id"]
            max_count = pending["max_count"]
            
            # Проверяем диапазон
            if quantity < 1 or quantity > max_count:
                await query.answer(f"❌ Неверное количество! Доступно: {max_count}", show_alert=True)
                return
            
            # ⭐ ДОБАВЛЯЕМ В ОТРЯДЫ ⭐
            selected_squads.append({
                "card_id": card_id,
                "count": quantity,
                "added_at": int(time.time()),
            })
            
            # ⭐ СОХРАНЯЕМ В ДАННЫЕ ПОЛЬЗОВАТЕЛЯ ⭐
            user_data["army_squads"] = selected_squads
            save_data(data)
            
            # ⭐ ОЧИЩАЕМ ВРЕМЕННОЕ ⭐
            army_info["pending_add"] = None
            army_info["step"] = "army_select"
            army_info["selected_squads"] = selected_squads
            
            await query.answer(f"✅ Добавлено {quantity} шт. в отряд!", show_alert=False)
            
            # ⭐ ВОЗВРАЩАЕМ К СПИСКУ ⭐
            await show_army_page(update, context, army_info.get("army_page", 0))
            return
        
        # ⭐ ОТМЕНА ДОБАВЛЕНИЯ ⭐
        if query.data == "army_cancel_add":
            army_info["pending_add"] = None
            army_info["step"] = "army_select"
            await show_army_page(update, context, army_info.get("army_page", 0))
            return
        
        # ⭐ УДАЛИТЬ ИЗ ОТРЯДА ⭐
        if query.data.startswith("army_remove_"):
            card_id = int(query.data.replace("army_remove_", ""))
            
            # Находим и удаляем отряд
            army_info["selected_squads"] = [s for s in selected_squads if s.get("card_id") != card_id]
            user_data["army_squads"] = army_info["selected_squads"]
            save_data(data)
            
            await query.answer("✅ Отряд удалён!", show_alert=False)
            await show_army_page(update, context, army_info.get("army_page", 0))
            return
        
        # ⭐ ЗАВЕРШИТЬ ФОРМИРОВАНИЕ ⭐
        if query.data == "army_finish":
            if len(selected_squads) < MAX_ARMY_SQUADS:
                await query.answer(f"❌ Выберите {MAX_ARMY_SQUADS} отрядов! Сейчас: {len(selected_squads)}", 
                                 show_alert=True)
                return
            
            # ⭐ ФОРМИРУЕМ ОТЧЁТ ⭐
            report = "✅ Армия сформирована!\n\n"
            report += f"📋 Ваши {MAX_ARMY_SQUADS} отрядов:\n\n"
            
            for i, squad in enumerate(selected_squads, 1):
                card = find_card_by_id(squad["card_id"], data["cards"])
                if card:
                    report += f"{i}. {card['title']} ({card['rarity']})\n"
                    report += f"   👥 Количество: {squad['count']} шт.\n\n"
            
            keyboard = [[
                InlineKeyboardButton("🔙 Назад в Сражения", callback_data="army_back")
            ]]
            
            await query.edit_message_text(
                report,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            # ⭐ СОХРАНЯЕМ ВРЕМЯ ФОРМИРОВАНИЯ ⭐
            user_data["army_last_formed"] = int(time.time())
            save_data(data)
            
            logger.info(f"Игрок {user_id} сформировал армию из {len(selected_squads)} отрядов")
            return
        
    except Exception as e:
        logger.error(f"Ошибка army_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


def get_army_range(count: int) -> str:
    """Преобразует точное количество в диапазон для показа противнику."""
    if count <= 4:
        return "1-4"
    elif count <= 9:
        return "5-9"
    elif count <= 19:
        return "10-19"
    elif count <= 49:
        return "20-49"
    elif count <= 99:
        return "50-99"
    else:
        return "100+"


def format_army_for_opponent(squads: List[Dict], data: Dict) -> str:
    """Форматирует отображение армии для противника с диапазонами."""
    if not squads:
        return "❌ Армия пуста"
    
    result = []
    for squad in squads:
        card = find_card_by_id(squad["card_id"], data["cards"])
        if card:
            exact_count = squad.get("count", 0)
            range_display = get_army_range(exact_count)
            result.append(f"• {card['title']} ({card['rarity']}): {range_display} шт.")
    
    return "\n".join(result) if result else "❌ Нет существ в армии"

async def select_battle_opponent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запрос @никнейма противника для сражения."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)

        is_valid, missing_cards = validate_army(user_id, data)
        if not is_valid:
            await notify_army_rebuild_needed(update, context, missing_cards)
            return

        # ⭐ ПРОВЕРКА ЛИМИТА ВЫЗОВОВ ⭐
        can_challenge, remaining = check_battle_challenge_limit(user_id, data)
        if not can_challenge:
            await update.message.reply_text(
                "❌ Лимит вызовов исчерпан!\n"
                "Вы можете бросить только 3 вызова в день.\n"
                "Счётчик сбросится в 00:00 МСК.",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("🔙 Назад в Сражения")]],
                    resize_keyboard=True
                )
            )
            return
        
        # Проверяем, есть ли у игрока армия
        if not user_data or not user_data.get("army_squads"):
            await update.message.reply_text(
                "❌ У вас нет сформированной армии!\n"
                "Сначала создайте армию в разделе 🛡️ Моя Армия",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("🔙 Назад в Сражения")]], 
                    resize_keyboard=True
                )
            )
            return
        
        # Запрашиваем @никнейм
        context.user_data[user_id] = {
            "step": "battle_find_opponent",
            "battle_type": "find"
        }
        
        await update.message.reply_text(
            "🔍 Введите @никнейм противника\n\n"
            "Пример: @username\n\n"
            "❌ Для отмены: /cancel",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("🔙 Назад в Сражения")]], 
                resize_keyboard=True
            )
        )
        
    except Exception as e:
        logger.error(f"Ошибка select_battle_opponent: {e}")
        await update.message.reply_text("❌ Ошибка при поиске противника")

async def process_opponent_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка выбора противника для сражения."""
    try:
        user_id = str(update.effective_user.id)
        text = update.message.text.strip()
        data = load_data()
        user_data = data["users"].get(user_id)
        
        # Проверяем, есть ли активный поиск противника
        if user_id not in context.user_data:
            return
        
        battle_info = context.user_data[user_id]
        step = battle_info.get("step", "")

        # ⭐ ПРОВЕРЯЕМ, ЧТО ИГРОК ВСЁ ЕЩЁ В РЕЖИМЕ ПОИСКА ⭐
        if step != "battle_find_opponent":
            return  # Игрок вышел из поиска, не обрабатываем сообщение
        
        # 1. Проверяем команду отмены (/cancel)
        if text.lower() == "/cancel":
            if step == "battle_find_opponent":
                del context.user_data[user_id]
                await update.message.reply_text(
                    "❌ Поиск отменён",
                    reply_markup=ReplyKeyboardMarkup(
                        [[KeyboardButton("🔙 Назад в Сражения")]], 
                        resize_keyboard=True
                    )
                )
            return
        
        # 2. Если пользователь не в шаге поиска, выходим
        if step != "battle_find_opponent":
            return
        
        # 3. Логика выбора противника
        opponent_id = None
        
        if text.startswith("@"):
            username = text[1:].strip()
            # Ищем игрока по @никнейму
            for uid, udata in data["users"].items():
                if udata.get("username") and udata["username"].lower() == username.lower():
                    opponent_id = uid
                    break
            
            if not opponent_id:
                await update.message.reply_text(
                    "⚠️ Игрок с таким @никнеймом не найден!",
                    reply_markup=ReplyKeyboardMarkup(
                        [[KeyboardButton("🔙 Назад в Сражения")]], 
                        resize_keyboard=True
                    )
                )
                return
        else:
            await update.message.reply_text(
                "⚠️ Введите корректный @никнейм (начинается с @)!",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("🔙 Назад в Сражения")]], 
                    resize_keyboard=True
                )
            )
            return
        
        # 4. Проверяем существование противника
        if opponent_id not in data["users"]:
            await update.message.reply_text("⚠️ Герой не найден!")
            return
        
        if opponent_id == user_id:
            await update.message.reply_text("⚠️ Нельзя сражаться с самим собой!")
            return
        
        # 5. Проверяем, есть ли у противника армия
        opponent_data = data["users"].get(opponent_id)
        if not opponent_data or not opponent_data.get("army_squads"):
            await update.message.reply_text("⚠️ У этого игрока нет сформированной армии!")
            return

        can_challenge, remaining = check_battle_challenge_limit(user_id, data)
        if not can_challenge:
            await update.message.reply_text(
                "❌ Лимит вызовов исчерпан!\n"
                "Вы можете бросить только 3 вызова в день.\n"
                "Счётчик сбросится в 00:00 МСК.",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("🔙 Назад в Сражения")]],
                    resize_keyboard=True
                )
            )
            return
        
        # 6. ⭐ ОТПРАВЛЯЕМ ЗАПРОС ПРОТИВНИКУ ⭐
        my_army_text = format_army_for_opponent(user_data.get("army_squads", []), data)
        
        # Создаём инлайн-кнопки для противника
        keyboard = [
            [
                InlineKeyboardButton("✅ Принять вызов", callback_data=f"battle_accept_{user_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"battle_decline_{user_id}")
            ]
        ]
        
        sender_name = user_data.get("first_name", "Герой")
        if user_data.get("username"):
            sender_name = f"@{user_data['username']}"
        
        # Отправляем запрос противнику
        try:
            await context.bot.send_message(
                chat_id=opponent_id,
                text=(
                    f"⚔️ Вам бросили вызов!\n\n"
                    f"👤 От: {sender_name}\n\n"
                    f"🛡️ Армия противника:\n"
                    f"{my_army_text}\n\n"
                    f"Выберите действие:"
                ),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

            # ⭐ УВЕЛИЧИВАЕМ СЧЁТЧИК ВЫЗОВОВ ⭐
            data["users"][user_id]["battle_challenges_today"] = user_data.get("battle_challenges_today", 0) + 1
            
            # Сохраняем ожидающий запрос
            if "pending_battles" not in data:
                data["pending_battles"] = {}
            
            data["pending_battles"][opponent_id] = {
                "from_user": user_id,
                "type": "incoming",
                "timestamp": int(time.time())
            }
            save_data(data)
            
            # Сохраняем состояние для отправителя
            context.user_data[user_id] = {
                "step": "battle_waiting_response",
                "opponent_id": opponent_id,
                "battle_type": "challenge_sent"
            }

             # ⭐ ПОКАЗЫВАЕМ ОСТАТОК ВЫЗОВОВ ⭐
            remaining = 3 - data["users"][user_id]["battle_challenges_today"]
            await update.message.reply_text(
                f"✅ Вызов отправлен игроку @{username}!\n"
                f"⏳ Ожидайте ответа...\n"
                f"📊 Осталось вызовов сегодня: {remaining}/3",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("🔙 Назад в Сражения")]],
                    resize_keyboard=True
                )
            )
            
        except Exception as send_error:
            logger.error(f"Не удалось отправить вызов: {send_error}")
            await update.message.reply_text("❌ Не удалось отправить вызов!")
        
    except Exception as e:
        logger.error(f"Ошибка process_opponent_selection: {e}")
        await update.message.reply_text("❌ Ошибка при обработке запроса")

def has_non_shooter_allies(battle_data: Dict, player_owner: str) -> bool:
    """
    Проверяет, есть ли у игрока живые не-стреляющие союзники.
    Возвращает: True если есть не-стрелки, False если все стрелки
    """
    initiative_list = battle_data.get("initiative_list", [])
    for squad in initiative_list:
        if squad["owner"] == player_owner and squad["count"] > 0:
            if not squad.get("shooter_active", False):
                return True
    return False

async def battle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок сражений."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        
        # ⭐ ПРОТИВНИК ПРИНИМАЕТ ВЫЗОВ ⭐
        if query.data.startswith("battle_accept_"):
            sender_id = query.data.replace("battle_accept_", "")
            
            is_valid, missing_cards = validate_army(user_id, data)
            if not is_valid:
                await query.edit_message_text(
                    "⚠️ Ваша армия требует пересборки!\n\n"
                    "Некоторые существа из вашей армии больше не доступны.\n"
                    "Пожалуйста, пересоберите армию в разделе 🛡️ Моя Армия."
                )
                return
            
            # Проверяем, есть ли у отправителя ещё армия
            sender_data = data["users"].get(sender_id)
            if not sender_data or not sender_data.get("army_squads"):
                await query.edit_message_text("❌ У отправителя больше нет армии!")
                return

            is_valid_sender, _ = validate_army(sender_id, data)
            if not is_valid_sender:
                await query.edit_message_text(
                    "⚠️ Армия отправителя требует пересборки!\n\n"
                    "Отправитель должен пересобрать свою армию."
                )
                return
            
            # ⭐ ОТПРАВЛЯЕМ ВСТРЕЧНЫЙ ЗАПРОС ОТПРАВИТЕЛЮ ⭐
            opponent_army_text = format_army_for_opponent(
                data["users"].get(user_id, {}).get("army_squads", []),
                data
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("⚔️ Начать сражение", callback_data=f"battle_start_{user_id}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"battle_cancel_{user_id}")
                ]
            ]
            
            opponent_name = data["users"].get(user_id, {}).get("first_name", "Герой")
            if data["users"].get(user_id, {}).get("username"):
                opponent_name = f"@{data['users'][user_id]['username']}"
            
            await context.bot.send_message(
                chat_id=sender_id,
                text=(
                    f"⚔️ Противник принял вызов!\n\n"
                    f"👤 Противник: {opponent_name}\n\n"
                    f"🛡️ Армия противника:\n"
                    f"{opponent_army_text}\n\n"
                    f"Выберите действие:"
                ),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            # Обновляем состояние
            if "pending_battles" not in data:
                data["pending_battles"] = {}
            
            data["pending_battles"][sender_id] = {
                "from_user": user_id,
                "type": "counter_request",
                "timestamp": int(time.time())
            }
            save_data(data)
            
            await query.edit_message_text("✅ Вы приняли вызов! Ожидайте подтверждения от противника...")
            return
        
        # ⭐ ПРОТИВНИК ОТКЛОНЯЕТ ВЫЗОВ ⭐
        if query.data.startswith("battle_decline_"):
            sender_id = query.data.replace("battle_decline_", "")
            
            # Уведомляем отправителя
            try:
                await context.bot.send_message(
                    chat_id=sender_id,
                    text="❌ Ваш вызов был отклонён!"
                )
            except:
                pass
            
            # Очищаем ожидающий запрос
            if "pending_battles" in data and user_id in data["pending_battles"]:
                del data["pending_battles"][user_id]
                save_data(data)
            
            await query.edit_message_text("❌ Вы отклонили вызов")
            return
        
        # ⭐ ОТПРАВИТЕЛЬ ПОДТВЕРЖДАЕТ СРАЖЕНИЕ ⭐
        if query.data.startswith("battle_start_"):
            opponent_id = query.data.replace("battle_start_", "")

            is_valid, missing_cards = validate_army(user_id, data)
            if not is_valid:
                await notify_army_rebuild_needed(update, context, missing_cards)
                return
            
            # ⭐ ПРОВЕРКА: валидация армии противника ⭐
            is_valid_opponent, _ = validate_army(opponent_id, data)
            if not is_valid_opponent:
                await query.edit_message_text(
                    "⚠️ Армия противника требует пересборки!\n\n"
                    "Противник должен пересобрать свою армию."
                )
                return
    
            # ⭐ ПОЛУЧАЕМ ДАННЫЕ О СРАЖЕНИИ ⭐
            data = load_data()
    
            # Получаем армии обоих игроков
            sender_data = data["users"].get(user_id, {})
            opponent_data = data["users"].get(opponent_id, {})
    
            red_squads = sender_data.get("army_squads", [])
            blue_squads = opponent_data.get("army_squads", [])
    
            # ⭐ СОЗДАЁМ СПИСОК ИНИЦИАТИВЫ ⭐
            initiative_list = create_initiative_list(red_squads, blue_squads, data)
    
            # ⭐ СОХРАНЯЕМ ДАННЫЕ О СРАЖЕНИИ В ФАЙЛ ⭐
            if "active_battles" not in data:
                data["active_battles"] = {}
    
            battle_key = f"{user_id}_{opponent_id}"
            data["active_battles"][battle_key] = {
                "red_player": user_id,
                "blue_player": opponent_id,
                "red_squads": red_squads,
                "blue_squads": blue_squads,
                "initiative_list": initiative_list,
                "current_turn_index": 0,
                "started_at": int(time.time()),
                "status": "active",
                "entangled": {}
            }
            save_data(data)
    
            # ⭐ СООБЩЕНИЕ О ЦВЕТЕ ИГРОКАМ ⭐
            await query.edit_message_text("✅ Сражение началось! ⚔️\n\nВы 🟥 красный игрок")
    
            # Уведомляем противника
            try:
                await context.bot.send_message(
                    chat_id=opponent_id,
                    text="✅ Сражение началось! ⚔️\n\nВы 🟦 синий игрок"
                )
        
                # ⭐ ПОКАЗЫВАЕМ МЕНЮ БИТВЫ ОБОИМ ИГРОКАМ ⭐
                battle_data = data["active_battles"][battle_key]
                await show_battle_menu(context, battle_data)
        
            except Exception as notify_error:
                logger.error(f"Не удалось уведомить игроков: {notify_error}")
    
            # Очищаем ожидающие запросы
            if "pending_battles" in data:
                if user_id in data["pending_battles"]:
                    del data["pending_battles"][user_id]
                if opponent_id in data["pending_battles"]:
                    del data["pending_battles"][opponent_id]
                save_data(data)
    
            logger.info(f"Сражение началось: {user_id} (🟥) vs {opponent_id} (🟦)")
            return

        if query.data.startswith("battle_attack_"):
            target_index = int(query.data.replace("battle_attack_", ""))
            
            # Находим активную битву
            battle_key = None
            for key, battle in data.get("active_battles", {}).items():
                if user_id in [battle.get("red_player"), battle.get("blue_player")]:
                    battle_key = key
                    break
            
            if not battle_key:
                await query.answer("❌ Активная битва не найдена!", show_alert=True)
                return
            
            battle_data = data["active_battles"][battle_key]
            initiative_list = battle_data.get("initiative_list", [])
            current_turn_index = battle_data.get("current_turn_index", 0)

            # ⭐ ИНИЦИАЛИЗИРУЕМ СЛОВАРЬ ОПУТЫВАНИЯ ЕСЛИ НЕТ ⭐
            if "entangled" not in battle_data:
                battle_data["entangled"] = {}
            
            # Проверяем чей сейчас ход
            if current_turn_index >= len(initiative_list):
                await query.answer("❌ Битва завершена!", show_alert=True)
                return
            
            current_turn = initiative_list[current_turn_index]
            
            # Проверяем что игрок может действовать
            if user_id not in [battle_data.get("red_player"), battle_data.get("blue_player")]:
                await query.answer("❌ Вы не участник этой битвы!", show_alert=True)
                return 
            if current_turn["owner"] == "red" and user_id != battle_data.get("red_player"):
                await query.answer("🚫 Сейчас ходит не ваш отряд!", show_alert=True)
                return
            if current_turn["owner"] == "blue" and user_id != battle_data.get("blue_player"):
                await query.answer("🚫 Сейчас ходит не ваш отряд!", show_alert=True)
                return
            if target_index == current_turn_index:
                await query.answer("🚫 Нельзя атаковать союзный отряд!", show_alert=True)
                return
            if target_index >= len(initiative_list):
                await query.answer("❌ Неверный индекс цели!", show_alert=True)
                return

            # ⭐ ПРОВЕРКА ОПУТЫВАНИЯ ⭐
            # Проверяем, опутан ли текущий отряд
            current_turn_card_id = current_turn["card_id"]
            if current_turn_card_id in battle_data["entangled"]:
                # Отряд опутан - может атаковать только того, кто его опутал
                entangler_card_id = battle_data["entangled"][current_turn_card_id]
                # Проверяем, жив ли ещё опутавший
                entangler_alive = False
                entangler_index = -1
                for idx, squad in enumerate(initiative_list):
                    if squad["card_id"] == entangler_card_id and squad["count"] > 0:
                        entangler_alive = True
                        entangler_index = idx
                        break
                if not entangler_alive:
                    # Освобождаем от опутывания
                    del battle_data["entangled"][current_turn_card_id]
                elif target_index != entangler_index:
                    # Атакует не того, кто опутал
                    await query.answer(
                        "🕸️ Этот отряд опутан! Может атаковать только тот отряд, который его опутал!",
                        show_alert=True
                    )
                    return

            target_squad = initiative_list[target_index]
            
            # Проверяем что цель не свой игрок
            if target_squad["owner"] == current_turn["owner"]:
                await query.answer("🚫 Нельзя атаковать союзный отряд!", show_alert=True)
                return

            # Получаем способности атакующего
            attacker_abilities = current_turn.get("ability", "")
            has_double_attack = "Двойная атака" in attacker_abilities
            has_flying = "Летает" in attacker_abilities or "Летает" in attacker_abilities

            # ⭐ ЗАПОМИНАЕМ ИНДЕКС ТЕКУЩЕГО ХОДА ДЛЯ ПРОВЕРКИ СМЕНЫ РАУНДА ⭐
            previous_turn_index = current_turn_index

            # ⭐ ПРОВЕРКА СТРЕЛКОВ ⭐
            # Проверяем, может ли атакующий атаковать эту цель
            attacker_is_shooter = current_turn.get("shooter_active", False)
            target_is_shooter = target_squad.get("shooter_active", False)
    
            # Если атакующий НЕ стрелок, а цель — стрелок
            if not attacker_is_shooter and target_is_shooter and not has_flying:
                # Проверяем, есть ли у цели не-стреляющие союзники
                target_owner = target_squad["owner"]
                found_non_shooter = False
                for squad in initiative_list:
                    if squad["owner"] == target_owner and squad["count"] > 0:
                        if not squad.get("shooter_active", False):
                            found_non_shooter = True
                            break
        
                # Если есть не-стрелки, нельзя атаковать стрелка
                if found_non_shooter:
                    await query.answer(
                        "🚫 Сначала уничтожьте не-стреляющие отряды!",
                        show_alert=True
                    )
                    return

            # ⭐ СООБЩЕНИЯ ОБ АТАКАХ ⭐
            all_attack_messages = []

            # ⭐ ДОБАВЛЯЕМ ИКОНКУ СТРЕЛКА В СООБЩЕНИЕ ⭐
            attacker_shooter_icon = "🏹" if current_turn.get("shooter_active", False) else ""
            defender_shooter_icon = "🏹" if target_squad.get("shooter_active", False) else ""

            # ⭐ ПРОВЕРКА АТАКИ ПО ОБЛАСТИ ⭐
            attacker_abilities = current_turn.get("ability", "")
            has_area_attack = "Атака по области" in attacker_abilities
            area_attack_messages = []
            area_attack_targets = []

            if has_area_attack:
                # Ищем ближайшего врага ДО целевого отряда (пропуская свои отряды)
                for i in range(target_index - 1, -1, -1):
                    check_unit = initiative_list[i]
                    if check_unit["owner"] != current_turn["owner"]:
                        # Проверяем защиту стрелка
                        if not (check_unit.get("shooter_active", False) and 
                                has_non_shooter_allies(battle_data, check_unit["owner"])):
                            area_attack_targets.append((i, check_unit, "слева"))
                        break  # Нашли первого врага, дальше не ищем
    
                # Ищем ближайшего врага ПОСЛЕ целевого отряда (пропуская свои отряды)
                for i in range(target_index + 1, len(initiative_list)):
                    check_unit = initiative_list[i]
                    if check_unit["owner"] != current_turn["owner"]:
                        # Проверяем защиту стрелка
                        if not (check_unit.get("shooter_active", False) and 
                                has_non_shooter_allies(battle_data, check_unit["owner"])):
                            area_attack_targets.append((i, check_unit, "справа"))
                        break  # Нашли первого врага, дальше не ищем

            # ⭐ ФУНКЦИЯ ДЛЯ ОДНОЙ АТАКИ ⭐
            def perform_attack(current_turn, target_squad, battle_data, data):
                """Выполняет одну атаку и возвращает сообщения"""
                messages = []
                # ⭐ РАСЧЁТ УРОНА ⭐
                final_damage, killed_count, remaining_damage = calculate_battle_damage(
                    current_turn, target_squad, data
                )
            
                # ⭐ НАНОСИМ УРОН ⭐
                target_squad["count"] -= killed_count
                if "dead_creatures" not in battle_data:
                    battle_data["dead_creatures"] = {
                        "red_player": {},  # {card_id: count}
                        "blue_player": {}
                    }

                # Добавляем погибших к соответствующему игроку
                target_owner = target_squad["owner"]
                card_id = target_squad["card_id"]
                if card_id not in battle_data["dead_creatures"][f"{target_owner}_player"]:
                    battle_data["dead_creatures"][f"{target_owner}_player"][card_id] = 0
                battle_data["dead_creatures"][f"{target_owner}_player"][card_id] += killed_count
                target_squad["damage_taken"] = target_squad.get("damage_taken", 0) + final_damage

                # ⭐ ЕСЛИ ЦЕЛЬ — СТРЕЛОК И АТАКУЮЩИЙ НЕ СТРЕЛОК, СТРЕЛОК ТЕРЯЕТ СТАТУС ⭐
                if target_squad.get("shooter", False) and not current_turn.get("shooter", False):
                    target_squad["shooter_active"] = False  # ← ТЕРЯЕТ СТАТУС СТРЕЛКА
            
                # ⭐ СООБЩЕНИЕ ОБ АТАКЕ ⭐
                attacker_color = "🟥" if current_turn["owner"] == "red" else "🟦"
                defender_color = "🟦" if target_squad["owner"] == "blue" else "🟥"
                message = (
                    f"{attacker_color} {current_turn['card_name']} {attacker_shooter_icon} нанёс {final_damage} урона!\n"
                    f"{defender_color} {target_squad['card_name']} {defender_shooter_icon} {killed_count} убито!\n"
                )
                messages.append(message)
                return messages, killed_count
            
            # ⭐ ПЕРВАЯ АТАКА ⭐
            attack_messages, first_killed = perform_attack(current_turn, target_squad, battle_data, data)
            all_attack_messages.extend(attack_messages)

            # ⭐ ПРИМЕНЕНИЕ ОПУТЫВАНИЯ ⭐
            # Если у атакующего есть способность "Опутывание", опутываем цель
            attacker_abilities = current_turn.get("ability", "")
            
            has_entangle = "Опутывание" in attacker_abilities
            if has_entangle and target_squad["count"] > 0:
                target_card_id = target_squad["card_id"]
                entangler_card_id = current_turn["card_id"]
                # Сохраняем опутывание
                battle_data["entangled"][target_card_id] = entangler_card_id

            # ⭐ НАНОСИМ УРОН ЦЕЛЯМ АТАКИ ПО ОБЛАСТИ ⭐
            if has_area_attack:
                for area_index, area_unit, direction in area_attack_targets:
                    # Рассчитываем урон (такой же как основная атака)
                    area_final_damage, area_killed_count, _ = calculate_battle_damage(
                        current_turn, area_unit, data
                    )
        
                    # Наносим урон
                    area_unit["count"] -= area_killed_count
                    area_unit["damage_taken"] = area_unit.get("damage_taken", 0) + area_final_damage
        
                    # Добавляем погибших
                    area_target_owner = area_unit["owner"]
                    area_card_id = area_unit["card_id"]
                    if area_card_id not in battle_data["dead_creatures"][f"{area_target_owner}_player"]:
                        battle_data["dead_creatures"][f"{area_target_owner}_player"][area_card_id] = 0
                    battle_data["dead_creatures"][f"{area_target_owner}_player"][area_card_id] += area_killed_count
        
                    area_attack_messages.append(
                        f"⚡ {area_unit['card_name']} ({direction}) получил {area_final_damage} урона! "
                        f"{area_killed_count} {area_unit['card_name']} убито!"
                    )
    
                # ⭐ ДОБАВЛЯЕМ СООБЩЕНИЯ ОБ АТАКЕ ПО ОБЛАСТИ ⭐
                if area_attack_messages:
                    all_attack_messages.append("\nАтака по области:")
                    all_attack_messages.extend(area_attack_messages)

            # ⭐ ПРОВЕРКА НА КОНТРАТАКУ ⭐
            counter_attack_message = ""
            # ⭐ ПРОВЕРЯЕМ ВОЗМОЖНОСТЬ КОНТРАТАКИ ⭐
            can_counterattack = (
                target_squad["count"] > 0 and
                target_squad.get("counter_attacks_remaining", 0) > 0 and
                not current_turn.get("shooter_active", False) and
                not current_turn.get("no_counterattack", False)  # ← НОВАЯ ПРОВЕРКА
            )
            if can_counterattack:
                
                # ⭐ ОТРЯД МОЖЕТ КОНТРАТАКОВАТЬ ⭐
                # Считаем урон контратаки (по той же формуле)
                counter_damage, counter_killed, _ = calculate_battle_damage(
                    target_squad, current_turn, data
                )
        
                # Наносим урон контратаки
                current_turn["count"] -= counter_killed
                current_turn["damage_taken"] = current_turn.get("damage_taken", 0) + counter_damage
                
                # ⭐ ЕСЛИ АТАКУЮЩИЙ УМЕР ОТ КОНТРАТАКИ, ОСВОБОЖДАЕМ ЕГО ЖЕРТВЫ ⭐
                if current_turn["count"] <= 0:
                    attacker_card_id = current_turn["card_id"]
                    # Находим всех, кого опутал этот отряд, и освобождаем
                    freed_targets = [cid for cid, entangler in battle_data["entangled"].items() if entangler == attacker_card_id]
                    for freed_id in freed_targets:
                        del battle_data["entangled"][freed_id]
        
                # Добавляем погибших от контратаки
                attacker_owner = current_turn["owner"]
                attacker_card_id = current_turn["card_id"]
                if attacker_card_id not in battle_data["dead_creatures"][f"{attacker_owner}_player"]:
                    battle_data["dead_creatures"][f"{attacker_owner}_player"][attacker_card_id] = 0
                battle_data["dead_creatures"][f"{attacker_owner}_player"][attacker_card_id] += counter_killed
        
                # ⭐ СБРАСЫВАЕМ СЧЁТЧИК КОНТРАТАКИ ⭐
                if target_squad.get("counter_attacks_remaining", 0) < 999:
                    target_squad["counter_attacks_remaining"] -= 1

                attacker_color = "🟥" if current_turn["owner"] == "red" else "🟦"
                defender_color = "🟦" if target_squad["owner"] == "blue" else "🟥"
                counter_attack_message = (
                    f"\n⚔️ {defender_color} {target_squad['card_name']} {defender_shooter_icon} контратакует и наносит {counter_damage} урона в ответ!\n"
                    f"{attacker_color} {current_turn['card_name']} {attacker_shooter_icon} {counter_killed} убито в контратаке!"
                )
                all_attack_messages.append(counter_attack_message)
                
            # ⭐ ЕСЛИ СТРЕЛОК АТАКОВАН НЕ-СТРЕЛКОМ, ОН ТЕРЯЕТ СТАТУС ⭐
            if target_is_shooter and not attacker_is_shooter:
                target_squad["shooter_active"] = False

            # ⭐ ВТОРАЯ АТАКА (ЕСЛИ ЕСТЬ ДВОЙНАЯ АТАКА) ⭐
            if has_double_attack and current_turn["count"] > 0 and target_squad["count"] > 0:
                attack_messages, second_killed = perform_attack(current_turn, target_squad, battle_data, data)
                # Добавляем пометку что это вторая атака
                for msg in attack_messages:
                    msg = msg.replace("нанёс", "нанёс (вторая атака)")
                all_attack_messages.extend(attack_messages)
                # Контратаки больше нет (уже использована)

            # Отправляем сообщение обоим игрокам
            full_message = "\n".join(all_attack_messages)
            for player_id in [battle_data.get("red_player"), battle_data.get("blue_player")]:
                try:
                    await context.bot.send_message(
                        chat_id=player_id,
                        text=full_message
                    )
                except:
                    pass
            
            # ⭐ ПРОВЕРЯЕМ УНИЧТОЖЕНИЕ ОТРЯДА ⭐
            attacker_died = current_turn["count"] <= 0
            
            if target_squad["count"] <= 0:
                # Удаляем отряд из инициативы
                initiative_list.pop(target_index)
                
                 # ⭐ ОЧИЩАЕМ ОПУТЫВАНИЕ ОТ ЭТОГО ОТРЯДА ⭐
                target_card_id = target_squad["card_id"]
                # ⭐ ВАЖНО: Удаляем опутывание НА этом отряде ⭐
                if target_card_id in battle_data["entangled"]:
                    del battle_data["entangled"][target_card_id]
                # Удаляем все опутывания, которые наложил этот отряд
                entangled_to_remove = [k for k, v in battle_data["entangled"].items() if v == target_card_id]
                for entangled_id in entangled_to_remove:
                    if entangled_id in battle_data["entangled"]:
                        del battle_data["entangled"][entangled_id]

                if target_index < current_turn_index:
                    # Удалён отряд ДО текущего хода - сдвигаем индекс на 1 назад
                    current_turn_index -= 1

            # ⭐ ВАЖНО: Если атакующий умер от контратаки, удаляем его тоже ⭐
            if attacker_died:
                # Находим текущий индекс атакующего (мог измениться после удаления цели)
                current_attacker_index = -1
                for idx, squad in enumerate(initiative_list):
                    if squad["card_id"] == current_turn["card_id"] and squad["count"] <= 0:
                        current_attacker_index = idx
                        break
    
                if current_attacker_index >= 0:
                    initiative_list.pop(current_attacker_index)
                    # ⭐ ОЧИЩАЕМ ОПУТЫВАНИЕ ОТ ЭТОГО ОТРЯДА ⭐
                    attacker_card_id = current_turn["card_id"]
                    freed_targets = [k for k, v in battle_data["entangled"].items() if v == attacker_card_id]
                    for freed_id in freed_targets:
                        if freed_id in battle_data["entangled"]:
                            del battle_data["entangled"][freed_id]
                    # Корректируем индекс текущего хода
                    if current_attacker_index < current_turn_index:
                        current_turn_index -= 1
                
                # ⭐ КОРРЕКТИРУЕМ ИНДЕКС ТЕКУЩЕГО ХОДА ⭐
                if current_turn_index >= len(initiative_list):
                    current_turn_index = 0
            
            # ⭐ ПРОВЕРЯЕМ ОКОНЧАНИЕ БИТВЫ ⭐
            red_squads = [u for u in initiative_list if u["owner"] == "red"]
            blue_squads = [u for u in initiative_list if u["owner"] == "blue"]

            rewards, red_killed_health, blue_killed_health = calculate_battle_rewards(battle_data, data)
            
            if not red_squads and not blue_squads:
                # Ничья
                for player_id in [battle_data.get("red_player"), battle_data.get("blue_player")]:
                    try:
                         if player_id in data["users"]:
                            killed_health = rewards[player_id]["killed_health"]
                            # При ничьей оба получают ×2
                            data["users"][player_id]["battle_experience"] += killed_health * 2
                            data["users"][player_id]["cents"] += killed_health * 2
                            # Сбрасываем серию побед при ничьей
                            data["users"][player_id]["win_streak"] = 0
                            await context.bot.send_message(
                                chat_id=player_id,
                                text=f"🤝 Битва завершена вничью!\n\n"
                                     f"💥 +{killed_health * 2} боевого опыта\n"
                                     f"💰 +{killed_health * 2} золота\n"
                                     f"🔥 Серия побед сброшена!"
                )
                    except:
                        pass
                # ⭐ УДАЛЯЕМ ПОГИБШИХ СУЩЕСТВ ⭐
                remove_dead_creatures_from_barracks(battle_data, data)
                del data["active_battles"][battle_key]
                save_data(data)
                return

            if not red_squads:
                # Синий победил
                winner = battle_data.get("blue_player")
                loser = battle_data.get("red_player")
                level_up_rewards = []
                level_up_rewards_loser = []
                streak_reward = 0

                if winner in data["users"]:
                    killed_health = rewards[winner]["killed_health"]
                    # ⭐ Победитель получает ×5 ⭐
                    data["users"][winner]["battle_experience"] += killed_health * 5
                    data["users"][winner]["cents"] += killed_health * 5
                    # Увеличиваем серию побед
                    data["users"][winner]["win_streak"] = data["users"][winner].get("win_streak", 0) + 1
                    win_streak = data["users"][winner]["win_streak"]

                    if win_streak % 5 == 0:
                        streak_reward = win_streak  # 5 побед = 5 наймов, 10 побед = 10 наймов и т.д.
                        data["users"][winner]["free_rolls"] = data["users"][winner].get("free_rolls", 0) + streak_reward
                    
                    level_up_rewards = check_battle_level_up(winner, data)

                if loser in data["users"]:
                    killed_health = rewards[loser]["killed_health"]
                    # ⭐ Проигравший получает ×2 ⭐
                    data["users"][loser]["battle_experience"] += killed_health * 2
                    data["users"][loser]["cents"] += killed_health * 2
                    # Сбрасываем серию побед
                    data["users"][loser]["win_streak"] = 0
                    level_up_rewards_loser = check_battle_level_up(loser, data)
                
                for player_id in [winner, loser]:
                    try:
                        killed_health = rewards[player_id]["killed_health"]
                        if player_id == winner:
                            result = f"🏆 Вы победили!\n\n"
                            result += f"💥 +{killed_health * 5} боевого опыта\n"
                            result += f"💰 +{killed_health * 5} золота\n"
                            result += f"🔥 Серия побед: {data['users'][player_id]['win_streak']}"
                            if streak_reward > 0:
                                result += f"🎁 НАГРАДА ЗА СЕРИЮ: +{streak_reward} наймов!\n"
                                result += "🎉 Вы получили награду за серию побед!\n"
                            if player_id == winner and level_up_rewards:
                                result += "\n🎉 ПОВЫШЕНИЕ УРОВНЯ!\n"
                                for reward in level_up_rewards:
                                    result += f"🎊 Уровень {reward['level']}!\n"
                                    if reward["reward_type"] == "card":
                                        result += f"🃏 Получено: {reward['card_name']}\n"
                                    elif reward["reward_type"] == "gold":
                                        result += f"💰 Получено: {reward['gold']} золота\n"
                                    elif reward["reward_type"] == "rolls":
                                        result += f"🎲 Получено: {reward['rolls']} наймов\n"
                                    elif reward["reward_type"] == "special_card":
                                        result += f"🌟 Получена special-карта!\n"
                        else:
                            result = f"💀 Вы проиграли!\n\n"
                            result += f"💥 +{killed_health * 2} боевого опыта\n"
                            result += f"💰 +{killed_health * 2} золота\n"
                            result += f"🔥 Серия побед сброшена!"
                            if player_id == loser and level_up_rewards_loser:
                                result += "\n🎉 ПОВЫШЕНИЕ УРОВНЯ!\n"
                                for reward in level_up_rewards_loser:
                                    result += f"🎊 Уровень {reward['level']}!\n"
                                    if reward["reward_type"] == "card":
                                        result += f"🃏 Получено: {reward['card_name']}\n"
                                    elif reward["reward_type"] == "gold":
                                        result += f"💰 Получено: {reward['gold']} золота\n"
                                    elif reward["reward_type"] == "rolls":
                                        result += f"🎲 Получено: {reward['rolls']} наймов\n"
                                    elif reward["reward_type"] == "special_card":
                                        result += f"🌟 Получена special-карта!\n"
                        await context.bot.send_message(chat_id=player_id, text=result)

                         # ⭐ ОТПРАВЛЯЕМ SPECIAL-КАРТУ ОТДЕЛЬНЫМ СООБЩЕНИЕМ ⭐
                        if player_id == winner and level_up_rewards:
                            for reward in level_up_rewards:
                                if reward["reward_type"] == "special_card":
                                    special_card = find_card_by_id(reward["card_id"], data["cards"])
                                    if special_card:
                                        caption = generate_card_caption(special_card, data["users"][player_id], count=1, show_bonus=True)
                                        caption += "\n\n🎉 Награда за повышение уровня в сражениях!"
                                        await send_card(update, special_card, context, caption=caption)
            
                        if player_id == loser and level_up_rewards_loser:
                            for reward in level_up_rewards_loser:
                                if reward["reward_type"] == "special_card":
                                    special_card = find_card_by_id(reward["card_id"], data["cards"])
                                    if special_card:
                                        caption = generate_card_caption(special_card, data["users"][player_id], count=1, show_bonus=True)
                                        caption += "\n\n🎉 Награда за повышение уровня в сражениях!"
                                        await send_card(update, special_card, context, caption=caption)
                    
                    except:
                        logger.error(f"Ошибка отправки результата битвы {player_id}: {e}")
                # ⭐ УДАЛЯЕМ ПОГИБШИХ СУЩЕСТВ ⭐
                remove_dead_creatures_from_barracks(battle_data, data)
                del data["active_battles"][battle_key]
                save_data(data)
                return

            if not blue_squads:
                # Красный победил
                winner = battle_data.get("red_player")
                loser = battle_data.get("blue_player")
                level_up_rewards = []
                level_up_rewards_loser = []
                streak_reward = 0

                if winner in data["users"]:
                    killed_health = rewards[winner]["killed_health"]
                    # ⭐ Победитель получает ×5 ⭐
                    data["users"][winner]["battle_experience"] += killed_health * 5
                    data["users"][winner]["cents"] += killed_health * 5
                    # Увеличиваем серию побед
                    data["users"][winner]["win_streak"] = data["users"][winner].get("win_streak", 0) + 1
                    win_streak = data["users"][winner]["win_streak"]

                    if win_streak % 5 == 0:
                        streak_reward = win_streak  # 5 побед = 5 наймов, 10 побед = 10 наймов и т.д.
                        data["users"][winner]["free_rolls"] = data["users"][winner].get("free_rolls", 0) + streak_reward
                    level_up_rewards = check_battle_level_up(winner, data)  

                if loser in data["users"]:
                    killed_health = rewards[loser]["killed_health"]
                    # ⭐ Проигравший получает ×2 ⭐
                    data["users"][loser]["battle_experience"] += killed_health * 2
                    data["users"][loser]["cents"] += killed_health * 2
                    # Сбрасываем серию побед
                    data["users"][loser]["win_streak"] = 0
                    level_up_rewards_loser = check_battle_level_up(loser, data) 
                
                for player_id in [winner, loser]:
                    try:
                        killed_health = rewards[player_id]["killed_health"]
                        if player_id == winner:
                            result = f"🏆 Вы победили!\n\n"
                            result += f"💥 +{killed_health * 5} боевого опыта\n"
                            result += f"💰 +{killed_health * 5} золота\n"
                            result += f"🔥 Серия побед: {data['users'][player_id]['win_streak']}"
                            if streak_reward > 0:
                                result += f"🎁 НАГРАДА ЗА СЕРИЮ: +{streak_reward} наймов!\n"
                                result += "🎉 Вы получили награду за серию побед!\n"
                            if player_id == winner and level_up_rewards:
                                result += "\n🎉 ПОВЫШЕНИЕ УРОВНЯ!\n"
                                for reward in level_up_rewards:
                                    result += f"🎊 Уровень {reward['level']}!\n"
                                    if reward["reward_type"] == "card":
                                        result += f"🃏 Получено: {reward['card_name']}\n"
                                    elif reward["reward_type"] == "gold":
                                        result += f"💰 Получено: {reward['gold']} золота\n"
                                    elif reward["reward_type"] == "rolls":
                                        result += f"🎲 Получено: {reward['rolls']} наймов\n"
                                    elif reward["reward_type"] == "special_card":
                                        result += f"🌟 Получена special-карта!\n"
                        else:
                            result = f"💀 Вы проиграли!\n\n"
                            result += f"💥 +{killed_health * 2} боевого опыта\n"
                            result += f"💰 +{killed_health * 2} золота\n"
                            result += f"🔥 Серия побед сброшена!"
                            if player_id == loser and level_up_rewards_loser:
                                result += "\n🎉 ПОВЫШЕНИЕ УРОВНЯ!\n"
                                for reward in level_up_rewards_loser:
                                    result += f"🎊 Уровень {reward['level']}!\n"
                                    if reward["reward_type"] == "card":
                                        result += f"🃏 Получено: {reward['card_name']}\n"
                                    elif reward["reward_type"] == "gold":
                                        result += f"💰 Получено: {reward['gold']} золота\n"
                                    elif reward["reward_type"] == "rolls":
                                        result += f"🎲 Получено: {reward['rolls']} наймов\n"
                                    elif reward["reward_type"] == "special_card":
                                        result += f"🌟 Получена special-карта!\n"
                        await context.bot.send_message(chat_id=player_id, text=result)

                        # ⭐ ОТПРАВЛЯЕМ SPECIAL-КАРТУ ОТДЕЛЬНЫМ СООБЩЕНИЕМ ⭐
                        if player_id == winner and level_up_rewards:
                            for reward in level_up_rewards:
                                if reward["reward_type"] == "special_card":
                                    special_card = find_card_by_id(reward["card_id"], data["cards"])
                                    if special_card:
                                        caption = generate_card_caption(special_card, data["users"][player_id], count=1, show_bonus=True)
                                        caption += "\n\n🎉 Награда за повышение уровня в сражениях!"
                                        await send_card(update, special_card, context, caption=caption)
            
                        if player_id == loser and level_up_rewards_loser:
                            for reward in level_up_rewards_loser:
                                if reward["reward_type"] == "special_card":
                                    special_card = find_card_by_id(reward["card_id"], data["cards"])
                                    if special_card:
                                        caption = generate_card_caption(special_card, data["users"][player_id], count=1, show_bonus=True)
                                        caption += "\n\n🎉 Награда за повышение уровня в сражениях!"
                                        await send_card(update, special_card, context, caption=caption)
                        
                    except:
                        logger.error(f"Ошибка отправки результата битвы {player_id}: {e}")
                # ⭐ УДАЛЯЕМ ПОГИБШИХ СУЩЕСТВ ⭐
                remove_dead_creatures_from_barracks(battle_data, data)
                del data["active_battles"][battle_key]
                save_data(data)
                return
                
            # ⭐ СЛЕДУЮЩИЙ ХОД ⭐
            if initiative_list and len(initiative_list) > 0:
                if current_turn["count"] <= 0:
                    initiative_list.pop(current_turn_index)
                    if current_turn_index >= len(initiative_list):
                        current_turn_index = 0
                else:
                    current_turn_index = (current_turn_index + 1) % len(initiative_list)
                
                # ⭐ ПРОВЕРКА СМЕНЫ РАУНДА — СБРОС КОНТРАТАК ⭐
                if current_turn_index < previous_turn_index or len(initiative_list) == 0:
                    # Раунд завершился, сбрасываем счётчики контратак у всех отрядов
                    for squad in initiative_list:
                        card = find_card_by_id(squad["card_id"], data["cards"])
                        if card:
                            # ⭐ ВОССТАНАВЛИВАЕМ ПЕРВОНАЧАЛЬНОЕ КОЛИЧЕСТВО КОНТРАТАК ⭐
                            if card["id"] == DOUBLE_COUNTERATTACK_CREATURE_ID:
                                squad["counter_attacks_remaining"] = 2
                            elif card["id"] in INFINITE_COUNTERATTACK_CREATURE_IDS:
                                squad["counter_attacks_remaining"] = 999
                            else:
                                squad["counter_attacks_remaining"] = 1
                # ⭐ КОРРЕКТИРУЕМ ИНДЕКС ЕСЛИ ВЫШЕЛ ЗА ГРАНИЦЫ ⭐
                    if initiative_list and current_turn_index >= len(initiative_list):
                        current_turn_index = 0
            else:
                current_turn_index = 0
                
            battle_data["current_turn_index"] = current_turn_index
            battle_data["initiative_list"] = initiative_list
            save_data(data)
            
            # ⭐ ОБНОВЛЯЕМ МЕНЮ ⭐
            await show_battle_menu(context, battle_data)
            return

        # ⭐ ЗАВЕРШИТЬ БИТВУ ⭐
        if query.data == "battle_end":
            # Находим активную битву
            battle_key = None
            for key, battle in data.get("active_battles", {}).items():
                if user_id in [battle.get("red_player"), battle.get("blue_player")]:
                    battle_key = key
                    break
    
            if not battle_key:
                await query.answer("❌ Активная битва не найдена!", show_alert=True)
                return
    
            remove_dead_creatures_from_barracks(data["active_battles"][battle_key], data)
            del data["active_battles"][battle_key]
            save_data(data)
    
            await query.edit_message_text(
                "✅ Битва завершена!\n\n"
                "Данные о сражении очищены.\n"
                "Все существа остались в вашей казарме."
            )
            return

        # ⭐ ПРОПУСТИТЬ ХОД ⭐
        if query.data == "battle_skip_turn":
            # Находим активную битву
            battle_key = None
            for key, battle in data.get("active_battles", {}).items():
                if user_id in [battle.get("red_player"), battle.get("blue_player")]:
                    battle_key = key
                    break
            if not battle_key:
                await query.answer("❌ Активная битва не найдена!", show_alert=True)
                return
            battle_data = data["active_battles"][battle_key]
            initiative_list = battle_data.get("initiative_list", [])
            current_turn_index = battle_data.get("current_turn_index", 0)
    
            # Проверяем чей сейчас ход
            if current_turn_index >= len(initiative_list):
                await query.answer("❌ Битва завершена!", show_alert=True)
                return
            current_turn = initiative_list[current_turn_index]
    
            # Проверяем что игрок может действовать
            if user_id not in [battle_data.get("red_player"), battle_data.get("blue_player")]:
                await query.answer("❌ Вы не участник этой битвы!", show_alert=True)
                return
            if current_turn["owner"] == "red" and user_id != battle_data.get("red_player"):
                await query.answer("🚫 Сейчас ходит не ваш отряд!", show_alert=True)
                return
            if current_turn["owner"] == "blue" and user_id != battle_data.get("blue_player"):
                await query.answer("🚫 Сейчас ходит не ваш отряд!", show_alert=True)
                return
    
            # ⭐ ЗАПОМИНАЕМ ИНДЕКС ТЕКУЩЕГО ХОДА ДЛЯ ПРОВЕРКИ СМЕНЫ РАУНДА ⭐
            previous_turn_index = current_turn_index
    
            # ⭐ ОТПРАВЛЯЕМ СООБЩЕНИЕ ОБ ПРОПУСКЕ ХОДА ⭐
            skip_message = f"⏭️ {current_turn['card_name']} пропускает ход!"
            for player_id in [battle_data.get("red_player"), battle_data.get("blue_player")]:
                try:
                    await context.bot.send_message(
                        chat_id=player_id,
                        text=skip_message
                    )
                except:
                    pass
    
            # ⭐ ПЕРЕХОДИМ К СЛЕДУЮЩЕМУ ХОДУ ⭐
            current_turn_index = (current_turn_index + 1) % len(initiative_list)
    
            # ⭐ ПРОВЕРКА СМЕНЫ РАУНДА — СБРОС КОНТРАТАК ⭐
            if current_turn_index < previous_turn_index or len(initiative_list) == 0:
                # Раунд завершился, сбрасываем счётчики контратак у всех отрядов
                for squad in initiative_list:
                    card = find_card_by_id(squad["card_id"], data["cards"])
                    if card:
                        # ⭐ ВОССТАНАВЛИВАЕМ ПЕРВОНАЧАЛЬНОЕ КОЛИЧЕСТВО КОНТРАТАК ⭐
                        if card["id"] == DOUBLE_COUNTERATTACK_CREATURE_ID:
                            squad["counter_attacks_remaining"] = 2
                        elif card["id"] in INFINITE_COUNTERATTACK_CREATURE_IDS:
                            squad["counter_attacks_remaining"] = 999
                        else:
                            squad["counter_attacks_remaining"] = 1
    
            # ⭐ КОРРЕКТИРУЕМ ИНДЕКС ЕСЛИ ВЫШЕЛ ЗА ГРАНИЦЫ ⭐
            if initiative_list and current_turn_index >= len(initiative_list):
                current_turn_index = 0
    
            battle_data["current_turn_index"] = current_turn_index
            battle_data["initiative_list"] = initiative_list
            save_data(data)
    
            # ⭐ ОБНОВЛЯЕМ МЕНЮ ⭐
            await show_battle_menu(context, battle_data)
            return

        # ⭐ СДАТЬСЯ ⭐
        if query.data == "battle_surrender":
            # Находим активную битву
            battle_key = None
            for key, battle in data.get("active_battles", {}).items():
                if user_id in [battle.get("red_player"), battle.get("blue_player")]:
                    battle_key = key
                    break
    
            if not battle_key:
                await query.answer("❌ Активная битва не найдена!", show_alert=True)
                return
    
            battle_data = data["active_battles"][battle_key]
    
            # Считаем погибших существ для обоих игроков
            red_squads = battle_data.get("red_squads", [])
            blue_squads = battle_data.get("blue_squads", [])
            initiative_list = battle_data.get("initiative_list", [])
    
            # Считаем сколько существ каждого типа осталось
            remaining_red = {}
            remaining_blue = {}
            for squad in initiative_list:
                card_id = squad["card_id"]
                count = squad["count"]
                if squad["owner"] == "red":
                    remaining_red[card_id] = remaining_red.get(card_id, 0) + count
                else:
                    remaining_blue[card_id] = remaining_blue.get(card_id, 0) + count
    
            # Считаем сколько было до битвы
            initial_red = {}
            initial_blue = {}
            for squad in red_squads:
                card_id = squad["card_id"]
                count = squad["count"]
                initial_red[card_id] = initial_red.get(card_id, 0) + count
            for squad in blue_squads:
                card_id = squad["card_id"]
                count = squad["count"]
                initial_blue[card_id] = initial_blue.get(card_id, 0) + count
    
            # Считаем погибших
            dead_red = sum(initial_red.get(cid, 0) - remaining_red.get(cid, 0) for cid in initial_red)
            dead_blue = sum(initial_blue.get(cid, 0) - remaining_blue.get(cid, 0) for cid in initial_blue)
    
            # Считаем стоимость капитуляции (7 × суммарное здоровье оставшихся существ)
            surrender_cost = 0
            for squad in initiative_list:
                max_health = squad.get("max_health", 10)
                surrender_cost += squad["count"] * max_health
            surrender_cost *= 7
    
            # Кнопки подтверждения
            keyboard = [
                [
                    InlineKeyboardButton("✅ Подтвердить", callback_data=f"battle_surrender_confirm_{battle_key}"),
                    InlineKeyboardButton("❌ Отмена", callback_data="battle_surrender_cancel")
                ]
            ]
    
            await query.edit_message_text(
                f"🏳️ Вы уверены, что хотите сдаться?\n\n"
                f"• Ваши потери: {dead_red} существ\n"
                f"• Потери противника: {dead_blue} существ\n\n"
                f"💰 Стоимость капитуляции: {surrender_cost} золота\n"
                f"Золото будет списано с вас и передано противнику.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        # ⭐ ПОДТВЕРЖДЕНИЕ КАПИТУЛЯЦИИ ⭐
        if query.data.startswith("battle_surrender_confirm_"):
            battle_key = query.data.replace("battle_surrender_confirm_", "")

            if battle_key not in data.get("active_battles", {}):
                await query.answer("❌ Битва не найдена!", show_alert=True)
                return

            battle_data = data["active_battles"][battle_key]

            # Определяем кто сдался и кто победил
            surrendering_player = user_id
            winner_id = battle_data.get("blue_player") if user_id == battle_data.get("red_player") else battle_data.get("red_player")
            loser_id = surrendering_player

            # ⭐ РАССЧИТЫВАЕМ НАГРАДЫ ЗА УБИТЫХ СУЩЕСТВ (как в обычной битве) ⭐
            rewards, red_killed_health, blue_killed_health = calculate_battle_rewards(battle_data, data)

            # ⭐ НАГРАДА ПОБЕДИТЕЛЮ (×5) ⭐
            if winner_id in data["users"]:
                killed_health = rewards[winner_id]["killed_health"]
                # Опыт и золото за убитых существ
                data["users"][winner_id]["battle_experience"] += killed_health * 5
                data["users"][winner_id]["cents"] += killed_health * 5
        
                # Увеличиваем серию побед
                data["users"][winner_id]["win_streak"] = data["users"][winner_id].get("win_streak", 0) + 1
                win_streak = data["users"][winner_id]["win_streak"]
        
                # Награда за серию побед (каждые 5 побед)
                streak_reward = 0
                if win_streak % 5 == 0:
                    streak_reward = win_streak
                    data["users"][winner_id]["free_rolls"] = data["users"][winner_id].get("free_rolls", 0) + streak_reward
        
                # Проверяем повышение уровня
                level_up_rewards = check_battle_level_up(winner_id, data)

            # ⭐ НАГРАДА ПРОИГРАВШЕМУ (×2) ⭐
            if loser_id in data["users"]:
                killed_health = rewards[loser_id]["killed_health"]
                # Опыт и золото за убитых существ
                data["users"][loser_id]["battle_experience"] += killed_health * 2
                data["users"][loser_id]["cents"] += killed_health * 2
        
                # Сбрасываем серию побед
                data["users"][loser_id]["win_streak"] = 0
        
                # Проверяем повышение уровня
                level_up_rewards_loser = check_battle_level_up(loser_id, data)

            # ⭐ СЧИТАЕМ СТОИМОСТЬ КАПИТУЛЯЦИИ ⭐
            surrender_cost = 0
            for squad in battle_data.get("initiative_list", []):
                max_health = squad.get("max_health", 10)
                surrender_cost += squad["count"] * max_health
            surrender_cost *= 7

            # ⭐ ДОПОЛНИТЕЛЬНОЕ ЗОЛОТО ОТ СДАВШЕГОСЯ ПОБЕДИТЕЛЮ ⭐
            if loser_id in data["users"]:
                data["users"][loser_id]["cents"] = max(0, data["users"][loser_id].get("cents", 0) - surrender_cost)
    
            if winner_id in data["users"]:
                data["users"][winner_id]["cents"] = data["users"][winner_id].get("cents", 0) + surrender_cost

            # ⭐ УДАЛЯЕМ ПОГИБШИХ СУЩЕСТВ ИЗ КАЗАРМ ОБОИХ ИГРОКОВ ⭐
            remove_dead_creatures_from_barracks(battle_data, data)

            # Удаляем битву
            del data["active_battles"][battle_key]
            save_data(data)

            # ⭐ ФОРМИРУЕМ СООБЩЕНИЕ ПОБЕДИТЕЛЮ ⭐
            winner_killed_health = rewards[winner_id]["killed_health"]
            winner_result = (
                f"🏆 **Противник сдался! Вы победили!**\n\n"
                f"💥 +{winner_killed_health * 5} боевого опыта\n"
                f"💰 +{winner_killed_health * 5} золота (за убитых)\n"
                f"💰 +{surrender_cost} золота (от противника)\n"
                f"🔥 Серия побед: {data['users'][winner_id]['win_streak']}"
            )
    
            # Добавляем информацию о серии побед
            if streak_reward > 0:
                winner_result += f"\n🎁 **НАГРАДА ЗА СЕРИЮ:** +{streak_reward} наймов!"
    
            # Добавляем информацию о повышении уровня
            if winner_id in data["users"]:
                level_up_rewards = check_battle_level_up(winner_id, data)
                if level_up_rewards:
                    winner_result += "\n\n🎉 **ПОВЫШЕНИЕ УРОВНЯ!**\n"
                    for reward in level_up_rewards:
                        winner_result += f"🎊 **Уровень {reward['level']}!**\n"
                        if reward["reward_type"] == "card":
                            winner_result += f"🃏 Получено: {reward['card_name']}\n"
                        elif reward["reward_type"] == "gold":
                            winner_result += f"💰 Получено: {reward['gold']} золота\n"
                        elif reward["reward_type"] == "rolls":
                            winner_result += f"🎲 Получено: {reward['rolls']} наймов\n"
                        elif reward["reward_type"] == "special_card":
                            winner_result += f"🌟 Получена special-карта!\n"

            # ⭐ ФОРМИРУЕМ СООБЩЕНИЕ ПРОИГРАВШЕМУ ⭐
            loser_killed_health = rewards[loser_id]["killed_health"]
            loser_result = (
                f"🏳️ **Вы сдались! Битва проиграна.**\n\n"
                f"💥 +{loser_killed_health * 2} боевого опыта\n"
                f"💰 +{loser_killed_health * 2} золота (за убитых)\n"
                f"💸 -{surrender_cost} золота (передано противнику)\n"
                f"🔥 Серия побед сброшена!"
            )
    
            # Добавляем информацию о повышении уровня
            if loser_id in data["users"]:
                level_up_rewards_loser = check_battle_level_up(loser_id, data)
                if level_up_rewards_loser:
                    loser_result += "\n\n🎉 **ПОВЫШЕНИЕ УРОВНЯ!**\n"
                    for reward in level_up_rewards_loser:
                        loser_result += f"🎊 **Уровень {reward['level']}!**\n"
                        if reward["reward_type"] == "card":
                            loser_result += f"🃏 Получено: {reward['card_name']}\n"
                        elif reward["reward_type"] == "gold":
                            loser_result += f"💰 Получено: {reward['gold']} золота\n"
                        elif reward["reward_type"] == "rolls":
                            loser_result += f"🎲 Получено: {reward['rolls']} наймов\n"
                        elif reward["reward_type"] == "special_card":
                            loser_result += f"🌟 Получена special-карта!\n"

            # Уведомляем обоих игроков
            try:
                await context.bot.send_message(
                    chat_id=loser_id,
                    text=loser_result,
                    parse_mode="Markdown"
                )
            except:
                pass

            try:
                await context.bot.send_message(
                    chat_id=winner_id,
                    text=winner_result,
                    parse_mode="Markdown"
                )
            except:
                pass

            await query.edit_message_text("✅ Вы сдались! Битва завершена.")
            return

        # ⭐ ОТМЕНА КАПИТУЛЯЦИИ ⭐
        if query.data == "battle_surrender_cancel":
            await query.edit_message_text("❌ Капитуляция отменена. Бой продолжается.")
    
            # Показываем меню битвы снова
            battle_key = None
            for key, battle in data.get("active_battles", {}).items():
                if user_id in [battle.get("red_player"), battle.get("blue_player")]:
                    battle_key = key
                    break
    
            if battle_key:
                battle_data = data["active_battles"][battle_key]
                await show_battle_menu(context, battle_data)
            return
        
        # ⭐ ОТПРАВИТЕЛЬ ОТМЕНЯЕТ СРАЖЕНИЕ ⭐
        if query.data.startswith("battle_cancel_"):
            opponent_id = query.data.replace("battle_cancel_", "")
            
            # Уведомляем противника
            try:
                await context.bot.send_message(
                    chat_id=opponent_id,
                    text="❌ Противник отменил сражение!"
                )
            except:
                pass
            
            # Очищаем ожидающие запросы
            if "pending_battles" in data:
                if user_id in data["pending_battles"]:
                    del data["pending_battles"][user_id]
                if opponent_id in data["pending_battles"]:
                    del data["pending_battles"][opponent_id]
                save_data(data)
            
            await query.edit_message_text("❌ Сражение отменено")
            return
            
        
    except Exception as e:
        logger.error(f"Ошибка battle_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


def create_initiative_list(squads1: List[Dict], squads2: List[Dict], data: Dict) -> List[Dict]:
    """
    Создаёт список инициативы существ для сражения.
    Сортирует по скорости (убывание), при равной скорости — рандом.
    """
    initiative_list = []
    
    # Добавляем отряды первого игрока (🟥 Красный)
    for squad in squads1:
        card = find_card_by_id(squad["card_id"], data["cards"])
        if card:
            counter_attacks = 1  # По умолчанию
            if card["id"] == DOUBLE_COUNTERATTACK_CREATURE_ID:
                counter_attacks = 2  # 2 контратаки
            elif card["id"] in INFINITE_COUNTERATTACK_CREATURE_IDS:
                counter_attacks = 999  # Бесконечность (условно)
                
            initiative_list.append({
                "card_id": squad["card_id"],
                "card_name": card["title"],
                "count": squad["count"],
                "initial_count": squad["count"],
                "max_health": card.get("health", 10),  # ← Максимум здоровья одного существа
                "speed": card.get("speed", 0),
                "owner": "red",
                "random_factor": random.random(),
                "damage_taken": 0,  # ← Полученный урон
                "counter_attacks_remaining": counter_attacks,
                "shooter": card.get("shooter", False),
                "shooter_active": card.get("shooter", False),
                "ability": card.get("ability", ""),
                "no_counterattack": "Безответная атака" in card.get("ability", "")
            })
    
    # Добавляем отряды второго игрока (🟦 Синий)
    for squad in squads2:
        card = find_card_by_id(squad["card_id"], data["cards"])
        if card:
            counter_attacks = 1  # По умолчанию
            if card["id"] == DOUBLE_COUNTERATTACK_CREATURE_ID:
                counter_attacks = 2  # 2 контратаки
            elif card["id"] in INFINITE_COUNTERATTACK_CREATURE_IDS:
                counter_attacks = 999  # Бесконечность (условно)
                
            initiative_list.append({
                "card_id": squad["card_id"],
                "card_name": card["title"],
                "count": squad["count"],
                "initial_count": squad["count"],
                "max_health": card.get("health", 10),
                "speed": card.get("speed", 0),
                "owner": "blue",
                "random_factor": random.random(),
                "damage_taken": 0,
                "counter_attacks_remaining": counter_attacks,
                "shooter": card.get("shooter", False),
                "shooter_active": card.get("shooter", False),
                "ability": card.get("ability", ""),
                "no_counterattack": "Безответная атака" in card.get("ability", "")
            })
    
    # ⭐ СОРТИРОВКА: сначала по скорости (убывание), потом по рандому ⭐
    initiative_list.sort(key=lambda x: (x["speed"], x["random_factor"]), reverse=True)
    return initiative_list


async def show_battle_menu(
    context: ContextTypes.DEFAULT_TYPE,
    battle_data: Dict
) -> None:
    """Показывает меню битвы с отрядами обоих игроков."""
    try:
        data = load_data()
        red_player = battle_data.get("red_player")
        blue_player = battle_data.get("blue_player")
        initiative_list = battle_data.get("initiative_list", [])
        current_turn_index = battle_data.get("current_turn_index", 0)

        initiative_list = [unit for unit in initiative_list if unit.get("count", 0) > 0]
        battle_data["initiative_list"] = initiative_list  # Сохраняем обновлённый список
        
        if not initiative_list:
            logger.error("Список инициативы пуст!")
            return
        
        # Определяем чей сейчас ход
        current_turn = initiative_list[current_turn_index] if current_turn_index < len(initiative_list) else None
        if not current_turn:
            logger.error("Текущий ход не определён!")
            return

        if current_turn["owner"] == "red":
            current_turn_color = "🟥"
        else:
            current_turn_color = "🟦"
        
        # ⭐ СОЗДАЁМ INLINE КЛАВИАТУРУ ⭐
        inline_keyboard = []
        for i, unit in enumerate(initiative_list[:10]):
            # Определяем цвет и эмодзи
            if unit["owner"] == "red":
                color_emoji = "🟥"
            else:
                color_emoji = "🟦"

            # ⭐ ДОБАВЛЯЕМ ИКОНКУ СТРЕЛКА ⭐
            shooter_icon = "🏹" if unit.get("shooter_active", False) else ""
            
            # ⭐ РАССЧИТЫВАЕМ ТЕКУЩЕЕ ЗДОРОВЬЕ ⭐
            alive_count = unit["count"]
            max_health = unit.get("max_health", 10)
            damage_taken = unit.get("damage_taken", 0)
            initial_count = unit.get("initial_count", alive_count)

            # ⭐ ПРОВЕРКА: если отряд полностью уничтожен, пропускаем его ⭐
            if alive_count <= 0:
                continue  # Пропускаем этот отряд в отображении
            
            if alive_count > 0:
                # Урон, который пошёл на убитых существ
                damage_to_dead = (initial_count - alive_count) * max_health
                # Остаточный урон по текущим живым
                remainder = damage_taken - damage_to_dead
                current_hp = max(0, max_health - remainder)
                
                # ⭐ ПРОВЕРКА: если HP = 0, но есть живые существа ⭐
                if current_hp <= 0 and alive_count > 0:
                    # Уменьшаем количество на 1 и восстанавливаем HP
                    alive_count -= 1
                    if alive_count > 0:
                        current_hp = max_health
                    else:
                        current_hp = 0
                        continue
            else:
                current_hp = 0
                continue
            
            # Показываем количество живых существ и здоровье одного
            button_text = f"{color_emoji} {unit['card_name']} {shooter_icon} {alive_count}шт {current_hp}/{max_health}❤️"

            # ⭐ ПОКАЗЫВАЕМ СТАТУС ОПУТЫВАНИЯ ⭐
            if unit["card_id"] in battle_data.get("entangled", {}):
                button_text += " 🕸️"  # Иконка паутины для опутанных
            
            # Callback для атаки
            callback_data = f"battle_attack_{i}"
            inline_keyboard.append([
                InlineKeyboardButton(button_text, callback_data=callback_data)
            ])
            
        # ⭐ ДОБАВЛЯЕМ КНОПКУ "ПРОПУСТИТЬ ХОД" ⭐
        inline_keyboard.append([
            InlineKeyboardButton("⏭️ Пропустить ход", callback_data="battle_skip_turn")
        ])
        inline_keyboard.append([
            InlineKeyboardButton("🏳️ Сдаться", callback_data="battle_surrender")
        ])
        
        # ⭐ ФОРМИРУЕМ CAPTION ⭐
        caption = (
            f"⚔️ БИТВА!\n"
            f"🟥 Красный игрок: {red_player}\n"
            f"🟦 Синий игрок: {blue_player}\n"
            f"📋 Порядок инициативы:\n"
            f"Отряды расположены в порядке скорости (сверху — самые быстрые)\n"
            f"🎯 Сейчас ходит: {current_turn_color} {current_turn['card_name']}\n"
            f"Выберите отряд противника для атаки:"
        )
        
        # ⭐ ОТПРАВЛЯЕМ МЕНЮ ОБОИМ ИГРОКАМ ⭐
        for player_id in [red_player, blue_player]:
            try:
                await context.bot.send_message(
                    chat_id=player_id,
                    text=caption,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard)
                )
                logger.info(f"Меню битвы отправлено игроку {player_id}")
            except Exception as e:
                logger.error(f"Не удалось отправить меню битвы игроку {player_id}: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка show_battle_menu: {e}")

async def end_battle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Завершает текущую битву и очищает данные."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        
        # Ищем активную битву с участием игрока
        battle_key = None
        for key, battle in data.get("active_battles", {}).items():
            if battle.get("red_player") == user_id or battle.get("blue_player") == user_id:
                battle_key = key
                break
        
        if not battle_key:
            await update.message.reply_text("❌ У вас нет активной битвы!")
            return
        
        # ⭐ УДАЛЯЕМ ДАННЫЕ О БИТВЕ ⭐
        del data["active_battles"][battle_key]
        save_data(data)
        
        await update.message.reply_text(
            "✅ Битва завершена!\n\n"
            "Данные о сражении очищены.\n"
            "Вы можете начать новое сражение.",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("🔙 Назад в Сражения")]],
                resize_keyboard=True
            ),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка end_battle: {e}")
        await update.message.reply_text("❌ Ошибка при завершении битвы")

def calculate_battle_damage(attacker_squad, defender_squad, data):
    """
    Расчёт урона в бою.
    Возвращает: (итоговый_урон, количество_убитых, сообщение)
    """
    # Получаем данные существ
    attacker_card = find_card_by_id(attacker_squad["card_id"], data["cards"])
    defender_card = find_card_by_id(defender_squad["card_id"], data["cards"])
    
    if not attacker_card or not defender_card:
        return 0, 0, "❌ Ошибка: существо не найдено!"
    
    # 1. Урон существа × количество в отряде
    base_damage = get_damage_from_range(attacker_card.get("damage", 0))
    total_damage = base_damage * attacker_squad["count"]
    
    # 2. Итоговая атака = атака атакующего - защита защищающегося
    final_attack = attacker_card.get("attack", 0) - defender_card.get("defense", 0)
    
    # 3. Модификация урона
    if final_attack > 0:
        # Увеличение на 5% за каждую единицу
        damage_multiplier = 1 + (final_attack * 0.05)
    elif final_attack < 0:
        # Уменьшение на 2.5% за каждую единицу
        damage_multiplier = 1 + (final_attack * 0.025)
    else:
        damage_multiplier = 1

    # ⭐ 4. ПРОВЕРКА БОНУСА ПРОТИВ СТРЕЛКОВ ⭐
    attacker_card_id = attacker_card["id"]
    defender_is_shooter = defender_squad.get("shooter_active", False)
    
    if attacker_card_id in ANTI_SHOOTER_CREATURES and defender_is_shooter:
        damage_multiplier *= 1.2  # +20% урона по стрелкам
    
    # Итоговый урон (округление вниз)
    final_damage = int(total_damage * damage_multiplier)

    # ⭐ 5. ПРОВЕРКА СПОСОБНОСТИ "НЕНАВИДИТ" ⭐
    hates_list = attacker_card.get("hates", "")
    if hates_list:
        # Преобразуем строку "10,15,20" в список ID
        hated_ids = [int(x.strip()) for x in hates_list.split(",") if x.strip().isdigit()]
        # Если защищающееся существо в списке ненавистных — +50% к финальному урону
        if defender_card["id"] in hated_ids:
            final_damage = int(final_damage * 1.5)  # +50% к финальному урону

    # ⭐ 6. ПРОВЕРКА СОПРОТИВЛЕНИЯ УРОНУ ⭐
    resistant_list = defender_card.get("resistant_to", "")
    if resistant_list:
        # Преобразуем строку "10,15,20" в список ID
        resistant_ids = [int(x.strip()) for x in resistant_list.split(",") if x.strip().isdigit()]
        # Если атакующее существо в списке сопротивления — -20% к финальному урону
        if attacker_card["id"] in resistant_ids:
            final_damage = int(final_damage * 0.8)  # -20% к финальному урону
    
    
    # 7. Расчёт убитых существ
    defender_health = defender_card.get("health", 10)
    # ⭐ ИСПРАВЛЕНИЕ: УЧИТЫВАЕМ УЖЕ ПОЛУЧЕННЫЙ УРОН ⭐
    damage_taken = defender_squad.get("damage_taken", 0)
    total_damage_to_squad = damage_taken + final_damage
    
    # Считаем сколько существ уже было убито до этой атаки
    already_killed = damage_taken // defender_health
    
    # Считаем сколько существ будет убито после этой атаки
    total_killed = total_damage_to_squad // defender_health
    
    # Количество убитых в этой атаке
    killed_count = total_killed - already_killed
    
    # Не может убить больше чем есть в отряде
    killed_count = max(0, min(killed_count, defender_squad["count"]))
    
    # Остаточный урон
    remaining_damage = total_damage_to_squad % defender_health
    
    return final_damage, killed_count, remaining_damage

def validate_army(user_id: str, data: Dict) -> tuple[bool, List[int]]:
    """
    Проверяет, все ли существа в армии всё ещё есть в казарме.
    Возвращает: (valid, missing_card_ids)
    """
    user_data = data["users"].get(user_id, {})
    army_squads = user_data.get("army_squads", [])
    user_cards = user_data.get("cards", [])
    
    # Считаем доступные карты
    card_counts = Counter(user_cards)
    
    missing_cards = []
    for squad in army_squads:
        card_id = squad.get("card_id")
        required_count = squad.get("count", 0)
        available_count = card_counts.get(card_id, 0)
        
        if available_count < required_count:
            missing_cards.append(card_id)
    
    return len(missing_cards) == 0, missing_cards

async def notify_army_rebuild_needed(update: Update, context: ContextTypes.DEFAULT_TYPE, missing_cards: List[int]) -> None:
    """Отправляет уведомление о необходимости пересобрать армию."""
    try:
        data = load_data()
        missing_names = []
        for card_id in missing_cards:
            card = find_card_by_id(card_id, data["cards"])
            if card:
                missing_names.append(card["title"])
        
        missing_text = "\n".join([f"• {name}" for name in missing_names[:5]])
        if len(missing_cards) > 5:
            missing_text += f"\n• ... и ещё {len(missing_cards) - 5} существ"
        
        await update.message.reply_text(
            f"⚠️ Ваша армия требует пересборки!\n\n"
            f"Некоторые существа из вашей армии больше не доступны:\n"
            f"{missing_text}\n\n"
            f"Пожалуйста, зайдите в 🛡️ Моя Армия и пересоберите её."
        )
    except Exception as e:
        logger.error(f"Ошибка notify_army_rebuild_needed: {e}")


def remove_dead_creatures_from_barracks(battle_data: Dict, data: Dict) -> None:
    """
    Удаляет погибших существ из казармы игроков после битвы.
    Сравнивает начальное и конечное количество существ в инициативе.
    """
    red_player = battle_data.get("red_player")
    blue_player = battle_data.get("blue_player")
    red_squads = battle_data.get("red_squads", [])
    blue_squads = battle_data.get("blue_squads", [])
    initiative_list = battle_data.get("initiative_list", [])
    
    # Считаем сколько существ каждого типа осталось после битвы
    remaining_red = {}
    remaining_blue = {}
    
    for squad in initiative_list:
        card_id = squad["card_id"]
        count = squad["count"]
        if squad["owner"] == "red":
            remaining_red[card_id] = remaining_red.get(card_id, 0) + count
        else:
            remaining_blue[card_id] = remaining_blue.get(card_id, 0) + count
    
    # Считаем сколько было до битвы
    initial_red = {}
    initial_blue = {}
    
    for squad in red_squads:
        card_id = squad["card_id"]
        count = squad["count"]
        initial_red[card_id] = initial_red.get(card_id, 0) + count
    
    for squad in blue_squads:
        card_id = squad["card_id"]
        count = squad["count"]
        initial_blue[card_id] = initial_blue.get(card_id, 0) + count
    
    # Удаляем погибших существ из казармы красного игрока
    if red_player in data["users"]:
        user_cards = data["users"][red_player].get("cards", [])
        for card_id, initial_count in initial_red.items():
            remaining_count = remaining_red.get(card_id, 0)
            dead_count = initial_count - remaining_count
            # Удаляем погибших существ из списка карт
            for _ in range(dead_count):
                if card_id in user_cards:
                    user_cards.remove(card_id)
    
    # Удаляем погибших существ из казармы синего игрока
    if blue_player in data["users"]:
        user_cards = data["users"][blue_player].get("cards", [])
        for card_id, initial_count in initial_blue.items():
            remaining_count = remaining_blue.get(card_id, 0)
            dead_count = initial_count - remaining_count
            # Удаляем погибших существ из списка карт
            for _ in range(dead_count):
                if card_id in user_cards:
                    user_cards.remove(card_id)
    
    save_data(data)

def calculate_surrender_cost(battle_data: Dict, player_id: str) -> int:
    """
    Рассчитывает стоимость капитуляции игрока.
    Формула: 7 × суммарное здоровье всех оставшихся отрядов игрока
    """
    total_hp = 0
    
    for squad in battle_data.get("initiative_list", []):
        # Проверяем, принадлежит ли отряд этому игроку
        is_player_squad = False
        if battle_data.get("red_player") == player_id and squad["owner"] == "red":
            is_player_squad = True
        elif battle_data.get("blue_player") == player_id and squad["owner"] == "blue":
            is_player_squad = True
        
        if is_player_squad:
            max_health = squad.get("max_health", 10)
            damage_taken = squad.get("damage_taken", 0)
            initial_count = squad.get("initial_count", squad["count"])
            alive_count = squad["count"]
            
            # Считаем здоровье каждого существа в отряде
            if alive_count > 0:
                damage_to_dead = (initial_count - alive_count) * max_health
                remainder = damage_taken - damage_to_dead
                current_hp = max(0, max_health - remainder)
                if current_hp == 0 and alive_count > 0:
                    alive_count -= 1
                    current_hp = max_health
            else:
                current_hp = 0
            
            # Суммируем здоровье всех существ в отряде
            if alive_count > 0:
                total_hp += (max_health * (alive_count - 1)) + current_hp
    
    # Стоимость капитуляции = 7 × суммарное здоровье
    surrender_cost = total_hp * 7
    return surrender_cost

def calculate_battle_rewards(battle_data: Dict, data: Dict) -> Dict[str, Dict]:
    """
    Рассчитывает награды за битву для обоих игроков.
    Возвращает: {player_id: {"gold": X, "battle_experience": Y}}
    """
    red_player = battle_data.get("red_player")
    blue_player = battle_data.get("blue_player")
    red_squads = battle_data.get("red_squads", [])
    blue_squads = battle_data.get("blue_squads", [])
    initiative_list = battle_data.get("initiative_list", [])
    
    rewards = {
        red_player: {"gold": 0, "battle_experience": 0},
        blue_player: {"gold": 0, "battle_experience": 0}
    }
    
    # Считаем сколько существ каждого типа осталось после битвы
    remaining_red = {}
    remaining_blue = {}
    for squad in initiative_list:
        card_id = squad["card_id"]
        count = squad["count"]
        if squad["owner"] == "red":
            remaining_red[card_id] = remaining_red.get(card_id, 0) + count
        else:
            remaining_blue[card_id] = remaining_blue.get(card_id, 0) + count
    
    # Считаем сколько было до битвы
    initial_red = {}
    initial_blue = {}
    for squad in red_squads:
        card_id = squad["card_id"]
        count = squad["count"]
        initial_red[card_id] = initial_red.get(card_id, 0) + count
    for squad in blue_squads:
        card_id = squad["card_id"]
        count = squad["count"]
        initial_blue[card_id] = initial_blue.get(card_id, 0) + count
    
    # Считаем убитых существ для каждого игрока
    red_killed_health = 0
    blue_killed_health = 0
    
    # Красный убил синих
    for card_id, initial_count in initial_blue.items():
        remaining_count = remaining_blue.get(card_id, 0)
        killed_count = initial_count - remaining_count
        # Находим здоровье существа
        card = find_card_by_id(card_id, data["cards"])
        if card:
            health = card.get("health", 10)
            red_killed_health += killed_count * health
    
    # Синий убил красных
    for card_id, initial_count in initial_red.items():
        remaining_count = remaining_red.get(card_id, 0)
        killed_count = initial_count - remaining_count
        # Находим здоровье существа
        card = find_card_by_id(card_id, data["cards"])
        if card:
            health = card.get("health", 10)
            blue_killed_health += killed_count * health
    
    # Рассчитываем награды

    rewards[red_player]["killed_health"] = red_killed_health    
    rewards[blue_player]["killed_health"] = blue_killed_health
    
    return rewards, red_killed_health, blue_killed_health


def calculate_battle_rank(user_id: str, data: Dict) -> int:
    """
    Считает место игрока в топе сражений по боевому опыту.
    Возвращает: место (1, 2, 3, ...)
    """
    users = data.get("users", {})
    
    # Сортируем всех пользователей по battle_experience
    sorted_users = sorted(
        users.items(),
        key=lambda x: x[1].get("battle_experience", 0),
        reverse=True
    )
    
    # Находим место пользователя
    for rank, (uid, _) in enumerate(sorted_users, 1):
        if uid == user_id:
            return rank
    
    # Если пользователя нет в топе
    return len(sorted_users) + 1

async def top_battles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает топ-10 героев по боевому опыту."""
    try:
        data = load_data()
        users = data.get("users", {})
        admin_list = data.get("admins", [])
        
        # ⭐ ФИЛЬТРУЕМ АДМИНОВ ⭐
        non_admin_users = {
            uid: udata for uid, udata in users.items()
            if uid not in admin_list
        }
        
        # Сортируем пользователей по battle_experience (только не-админы)
        sorted_users = sorted(
            non_admin_users.items(),
            key=lambda x: x[1].get("battle_experience", 0),
            reverse=True
        )
        
        # Берём топ-10
        top_10 = sorted_users[:10]
        
        # Формируем сообщение
        message_text = "🏆 Топ сражений этого сезона\n"
        if not top_10:
            message_text += "📭 Пока нет героев в топе!"
        else:
            for rank, (user_id, user_data) in enumerate(top_10, 1):
                # Получаем имя из профиля Telegram
                first_name = user_data.get("first_name", "Герой")
                last_name = user_data.get("last_name", "")
                # Формируем полное имя
                if last_name:
                    username = f"{first_name} {last_name}"
                else:
                    username = first_name
                battle_exp = user_data.get("battle_experience", 0)
                # Медали для топ-3
                if rank == 1:
                    medal = "🥇"
                elif rank == 2:
                    medal = "🥈"
                elif rank == 3:
                    medal = "🥉"
                else:
                    medal = f"{rank}."
                message_text += f"{medal} {username} — {battle_exp} боевого опыта\n"
        
        # ⭐ ПОКАЗЫВАЕМ МЕСТО ТОЛЬКО ЕСЛИ ПОЛЬЗОВАТЕЛЬ НЕ АДМИН ⭐
        current_user_id = str(update.effective_user.id)
        # Проверяем, является ли текущий пользователь админом
        if current_user_id not in admin_list:
            current_user_data = users.get(current_user_id, {})
            current_battle_exp = current_user_data.get("battle_experience", 0)
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
                message_text += f"✅ Ваше место: {user_rank}\n"
            else:
                message_text += f"📍 Ваше место: {user_rank}\n"
            message_text += f"💥 Ваш боевой опыт: {current_battle_exp}"
        else:
            # ⭐ ДЛЯ АДМИНОВ - СООБЩЕНИЕ ЧТО ОНИ НЕ УЧАСТВУЮТ ⭐
            message_text += "\n" + "─" * 30 + "\n"
            message_text += "⚙️ Вы администратор\n"
            message_text += "Ваш прогресс не учитывается в топе"
        await update.message.reply_text(
            message_text
        )
    except Exception as e:
        logger.error(f"Ошибка в top_battles: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке топа")

def check_battle_challenges_reset(user_data: Dict) -> None:
    """Проверяет и сбрасывает счётчик вызовов в полночь по МСК."""
    import datetime
    # Получаем текущее время по МСК
    msk_tz = datetime.timezone(datetime.timedelta(hours=3))
    now_msk = datetime.datetime.now(msk_tz)
    # Получаем дату последнего сброса
    last_reset = user_data.get("battle_challenges_last_reset", 0)
    # ⭐ ЕСЛИ НАСТУПИЛ НОВЫЙ ДЕНЬ ⭐
    if (
        last_reset == 0
        or now_msk.day != datetime.datetime.fromtimestamp(last_reset, msk_tz).day
    ):
        # Сбрасываем счётчик вызовов
        user_data["battle_challenges_today"] = 0
        # ⭐ ОБНОВЛЯЕМ ВРЕМЯ СБРОСА ⭐
        user_data["battle_challenges_last_reset"] = int(now_msk.timestamp())
        logger.info(f"Сброс счётчика вызовов для пользователя {user_data.get('username', 'unknown')}")

def check_battle_challenge_limit(user_id: str, data: Dict) -> tuple[bool, int]:
    """
    Проверяет, может ли игрок бросить вызов.
    Возвращает: (can_challenge, remaining_challenges)
    """
    user_data = data["users"].get(user_id, {})
    # Проверяем, является ли пользователь админом
    if user_id in data.get("admins", []):
        return True, 999  # Админы без ограничений
    
    # Проверяем лимит (3 вызова в день)
    challenges_today = user_data.get("battle_challenges_today", 0)
    remaining = 3 - challenges_today
    
    return remaining > 0, max(0, remaining)

def check_battle_level_up(user_id: str, data: Dict) -> List[Dict]:
    """
    Проверяет повышение уровня боевого опыта и выдаёт награды.
    Возвращает список полученных наград.
    """
    user_data = data["users"].get(user_id, {})
    battle_exp = user_data.get("battle_experience", 0)
    battle_level = user_data.get("battle_level", 0)
    
    # Пороги уровней и награды
    LEVEL_THRESHOLDS = {
        1: {"exp": 1000, "reward_type": "card", "rarity": "T7"},
        2: {"exp": 3000, "reward_type": "card", "rarity": "UpgradeT6"},
        3: {"exp": 7000, "reward_type": "gold", "amount": 10000},
        4: {"exp": 20000, "reward_type": "rolls", "amount": 20},
        5: {"exp": 40000, "reward_type": "special_card", "card_id": 177},  # ← Укажите ID special-карты
    }
    
    rewards = []
    new_level = battle_level
    
    # Проверяем каждый уровень
    for level, threshold in LEVEL_THRESHOLDS.items():
        if level > battle_level and battle_exp >= threshold["exp"]:
            new_level = level
            reward = {"level": level, **threshold}
            
            # Выдаём награду
            if threshold["reward_type"] == "card":
                # Находим случайную карту нужной редкости
                available_cards = [
                    c for c in data["cards"]
                    if c.get("rarity") == threshold["rarity"] and c.get("available", True)
                ]
                if available_cards:
                    reward_card = random.choice(available_cards)
                    user_data["cards"].append(reward_card["id"])
                    reward["card_name"] = reward_card["title"]
                    reward["card_id"] = reward_card["id"]
            
            elif threshold["reward_type"] == "gold":
                user_data["cents"] = user_data.get("cents", 0) + threshold["amount"]
                reward["gold"] = threshold["amount"]
            
            elif threshold["reward_type"] == "rolls":
                user_data["free_rolls"] = user_data.get("free_rolls", 0) + threshold["amount"]
                reward["rolls"] = threshold["amount"]
            
            elif threshold["reward_type"] == "special_card":
                user_data["cards"].append(threshold["card_id"])
                reward["card_id"] = threshold["card_id"]
            
            rewards.append(reward)
    
    # Обновляем уровень
    if new_level > battle_level:
        user_data["battle_level"] = new_level
    
    return rewards


def can_attack_target(attacker_squad, target_squad, initiative_list, data) -> tuple[bool, str]:
    """
    Проверяет, можно ли атаковать цель.
    Возвращает: (можно_ли_атаковать, причина_запрета)
    """
    # Если атакующий — стрелок, может атаковать кого угодно
    if attacker_squad.get("shooter", False) and attacker_squad.get("shooter_active", True):
        return True, ""
    
    # Если цель — не стрелок, можно атаковать
    if not target_squad.get("shooter", False):
        return True, ""
    
    # Цель — стрелок, атакующий — не стрелок
    # Проверяем, есть ли у цели живые не-стреляющие союзники
    target_owner = target_squad["owner"]
    
    for squad in initiative_list:
        if squad["owner"] == target_owner and squad["count"] > 0:
            # Если есть живой не-стрелок — нельзя атаковать стрелка
            if not squad.get("shooter", False):
                return False, "Сначала уничтожьте не стреляющие отряды!"
    
    # Все не-стрелки мертвы, можно атаковать стрелка
    return True, ""

async def check_gold_digger_reset(user_id: str, user_data: Dict, data: Dict, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Проверяет и начисляет золото за золотоискателей в полночь по МСК.
    Работает аналогично check_casino_reset().
    """
    import datetime
    
    # Получаем текущее время по МСК
    msk_tz = datetime.timezone(datetime.timedelta(hours=3))
    now_msk = datetime.datetime.now(msk_tz)
    today_date = str(now_msk.date())
    
    # Получаем дату последнего начисления
    last_income_date = user_data.get("gold_digger_last_income", "")
    
    # ⭐ ЕСЛИ НАСТУПИЛ НОВЫЙ ДЕНЬ ⭐
    if last_income_date != today_date:
        # Считаем существ со способностью "Золотоискатель"
        gold_digger_count = 0
        gold_digger_names = {}
        
        user_cards = user_data.get("cards", [])
        card_counts = Counter(user_cards)
        
        for card_id, count in card_counts.items():
            if card_id in GOLD_DIGGER_CARD_IDS:
                gold_digger_count += count
                # Сохраняем название для сообщения
                card = find_card_by_id(card_id, data["cards"])
                if card:
                    card_name = card["title"]
                    if card_name not in gold_digger_names:
                        gold_digger_names[card_name] = 0
                    gold_digger_names[card_name] += count
        
        if gold_digger_count > 0:
            # Начисляем золото (50 за каждое существо)
            gold_income = gold_digger_count * 50
            user_data["cents"] = user_data.get("cents", 0) + gold_income
            
            # Сохраняем дату последнего начисления
            user_data["gold_digger_last_income"] = today_date
            save_data(data)
            
            # Формируем сообщение
            creatures_text = ", ".join([f"{name}: {count} шт." for name, count in gold_digger_names.items()])
            message = (
                f"💰 Ваши золотоискатели принесли доход: {gold_income} золота\n\n"
            )
            
            # Отправляем сообщение игроку
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message
                )
                logger.info(f"Игрок {user_id} получил {gold_income} золота от золотоискателей")
            except Exception as send_error:
                logger.error(f"Не удалось отправить сообщение игроку {user_id}: {send_error}")
        
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

        handlers = [
            CommandHandler("start", start),
            CommandHandler("profile", my_profile),
            CommandHandler("dice", dice),
            CommandHandler("craft", craft),
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
            CommandHandler("list_admins", list_admins),
            CommandHandler("add_admin", add_admin),
            CommandHandler("remove_admin", remove_admin),
            CommandHandler("set_achievement_cards", set_achievement_cards),
            CommandHandler("create_promo", create_promo_code),
            CommandHandler("delete_promo", delete_promo_code),
            CommandHandler("list_promo", list_promo_codes),
            CommandHandler("promo", activate_promo_code),
            CommandHandler("mercenary_add", mercenary_add),
            CommandHandler("mercenary_remove", mercenary_remove),
            CommandHandler("mercenary_list", mercenary_list),
            CommandHandler("mercenary_price", mercenary_update_price),
            CommandHandler("top_battles", top_battles),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            CallbackQueryHandler(handle_callback, pattern=r"^card_.*"),
            CallbackQueryHandler(mycards_callback, pattern=r"^(mycards_|barracks_).*"),
            CallbackQueryHandler(craft_callback, pattern=r"^craft_.*"),  # Кнопки крафта
            CallbackQueryHandler(dice_callback, pattern=r"^dice_.*"),
            CallbackQueryHandler(casino_callback, pattern=r"^casino_.*"),
            CallbackQueryHandler(top_callback, pattern=r"^top_.*"),
            CallbackQueryHandler(trade_button_callback, pattern=r"^trade_(accept|decline)_btn_.*"),
            CallbackQueryHandler(trade_search_callback, pattern=r"^trade_search_.*"),
            CallbackQueryHandler(trade_offer_callback, pattern=r"^trade_offer_.*"),
            CallbackQueryHandler(trade_return_callback, pattern=r"^trade_return_.*"),
            CallbackQueryHandler(trade_final_callback, pattern=r"^trade_final_(confirm|decline)_.*"),
            CallbackQueryHandler(trade_callback, pattern=r"^trade_.*"),
            CallbackQueryHandler(profile_callback, pattern=r"^(achievements_menu|profile_back|achievement_.*)"),
            CallbackQueryHandler(dungeon_callback, pattern=r"^dungeon_.*"),
            CallbackQueryHandler(sacrifice_callback, pattern=r"^sacrifice_.*"),
            CallbackQueryHandler(mercenary_callback, pattern=r"^mercenary_.*"),
            CallbackQueryHandler(army_callback, pattern=r"^army_.*"),
            CallbackQueryHandler(battle_callback, pattern=r"^battle_.*"),
        ]

        for handler in handlers:
            application.add_handler(handler) 

        
        print("Бот успешно запущен! Ctrl+C для остановки")
        logger.info("Бот запущен")

        import threading
        notification_thread = threading.Thread(
            target=lambda: asyncio.run(check_card_notifications(application)), 
            daemon=True
        )
        notification_thread.start()
        logger.info("Запущена фоновая задача уведомлений")
        
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
