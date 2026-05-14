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

FORT_IMAGE_URL = "https://ibb.co/gZwy5v0G"
FOREST_IMAGE_URL = "https://ibb.co/DgTPVmTr"
TAVERN_IMAGE_URL = "https://ibb.co/jPQv7mYn"
BARRACKS_IMAGE_URL = "https://ibb.co/cSVxP3kh"
DUNGEON_IMAGE_URL = "https://ibb.co/yBckMfHf"
ALTAR_IMAGE_URL = "https://ibb.co/S7c5NL6v"
REFUGEE_CAMP_IMAGE_URL = "https://ibb.co/qY2W2TpR"
MERCENARY_GUILD_IMAGE_URL = "https://ibb.co/dwV8jyks"
FREE_ROLLS_IMAGE_URL = "https://ibb.co/Zpc9ntMB"

FREE_ROLLS_PACKAGE = {
    "id": "free_rolls_package",
    "title": "15 наймов",
    "price": 35000,
    "rolls": 15,
}

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

            if "mercenary_guild" not in data:
                data["mercenary_guild"] = {
                    "creatures": [],  # Список существ для продажи
                    "max_slots": 4    # Максимум 4 существа
                }

            if "pending_battles" not in data:
                data["pending_battles"] = {}

            if "active_battles" not in data:
                data["active_battles"] = {}
            
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
                if "used_promo_codes" not in user_data:
                    user_data["used_promo_codes"] = []
                if "refugee_camp_last_reset" not in user_data:
                    user_data["refugee_camp_last_reset"] = 0  # ← Время последнего сброса
                if "refugee_camp_offered_card" not in user_data:
                    user_data["refugee_camp_offered_card"] = None
                if "refugee_camp_purchased" not in user_data:
                    user_data["refugee_camp_purchased"] = False
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
    
    
    # ⭐ ПОКАЗЫВАЕМ БОНУСЫ ТОЛЬКО ПРИ ПОЛУЧЕНИИ НОВОЙ КАРТЫ ⭐
    if show_bonus and user_data is not None:
        bonus = RARITY_BONUSES.get(card["rarity"], {"cents": 0, "points": 0})
        caption += f"\n\n💰 +{bonus['cents']} бэт-коинов\n💥 +{bonus['points']} опыта"
    
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
            [KeyboardButton("Устроить допрос")],
            [KeyboardButton("🏰 Город")],
            [KeyboardButton("🌲 Лес"), KeyboardButton("🍺 Таверна")],
            [KeyboardButton("🦇 Подземелье")]
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
        
        if not rarity_cards:
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text("У вас пока нет существ!")
            else:
                await update.message.reply_text("У вас пока нет существ!")
            return
        
        # ⭐ СОЗДАЁМ МЕНЮ ВЫБОРА СПОСОБА ПРОСМОТРА ⭐
        keyboard = [
            [InlineKeyboardButton("📊 По редкости", callback_data="barracks_rarity")],
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
        
        
        profile_text = (
            f"👤 Профиль героя\n\n"
            f"🆔 ID: `{user_id}`\n"
            f"💰 Бэт-коины: {user_data.get('cents', 0)}\n"
            f"💥 Опыта (сезон): {user_data.get('season_points', 0)}\n"
            f"💎 Опыта (всего): {user_data.get('total_points', 0)}\n\n"
            f"🐦‍🔥 Коллекция:\n"
            f"📦 Собрано существ: {unique_cards}/{total_available_cards}\n"
            f"📊 Заполненность: {collection_percent}%\n"
            f"🔢 Всего получено: {len(user_card_ids)} (с дубликатами)\n\n"
            f"📈 По редкостям:\n"
            f"{rarity_text}\n"
            f"🎲 Бесплатные наймы: {user_data.get('free_rolls', 0)}\n"
        )
        
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
       
        if query.data == "profile_back":
            await my_profile(update, context)
        
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
                [KeyboardButton("Устроить допрос")],
                [KeyboardButton("🏰 Город")],
                [KeyboardButton("🌲 Лес"), KeyboardButton("🍺 Таверна")],
                [KeyboardButton("🦇 Подземелье")]
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

        elif text.startswith("💰 Купить за ") and "бэт-коинов" in text:
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

        elif text == "🔙 Назад в Подземелье":
            await dungeon_menu(update, context)
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

        if text == "Устроить допрос":

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
        
        if len(lines) < 4 :
            await update.message.reply_text(
                "ℹ️ Формат:\n"
                "/add_card\n"
                "URL\n"
                "Название\n"
                "Редкость\n"
            )
            return
        
        url = lines[1].strip()
        title = lines[2].strip()
        rarity = lines[3].strip()
        
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
            "available": True,
            "media_type": media_type,
        }
        
        data["cards"].append(new_card)
        save_data(data)
        
        await update.message.reply_text(
            f"✅ Карточка #{new_id} добавлена!\n"
            f"🏷 {title}\n"
            f"🌟 {rarity}\n"
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
            f"💰 **+{bonus['cents']} бэт-коинов**\n"
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
            [InlineKeyboardButton("🎰 Играть (3000 бэт-коинов)", callback_data="casino_play")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🎰 **Казино**\n\n"
            f"📜 **Правила:**\n"
            f"• Стоимость игры: 3000 бэт-коинов\n"
            f"• Крутите слот и получите 3 одинаковых значения\n"
            f"• При победе: 10 бесплатных наймов существ\n"
            f"• Попыток сегодня: {attempts}/10\n"
            f"• Сброс в 00:00 МСК\n\n"
            f"💰 Ваш баланс: {cents} бэт-коинов\n"
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
                    f"❌ **Недостаточно бэт-коинов!**\n\n"
                    f"Нужно: 3000 бэт-коинов\n"
                    f"У вас: {cents} бэт-коинов\n\n"
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
                f"💰 Списано: 3000 бэт-коинов\n"
                f"🎲 Осталось попыток: {user_data['casino_attempts']}\n"
                f"💰 Ваш баланс: {user_data['cents']} бэт-коинов",
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
                [KeyboardButton("Устроить допрос")],
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
            [InlineKeyboardButton("🎰 Играть (3000 бэт-коинов)", callback_data="casino_play")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🎰 **Казино**\n\n"
            f"📜 **Правила:**\n"
            f"• Стоимость игры: 3000 бэт-коинов\n"
            f"• Крутите слот и получите 3 одинаковых значения\n"
            f"• При победе: 10 бесплатных наймов существ\n"
            f"• Попыток сегодня: {attempts}/10\n"
            f"• Сброс в 00:00 МСК\n"
            f"💰 Ваш баланс: {cents} бэт-коинов\n",
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
                    "• UpgradeT1-T4: бэт-коинов (50% от награды за крафт)\n"
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
                    "• UpgradeT1-T4: бэт-коинов (50% от награды за крафт)\n"
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
                    reward_text = f"💰 {reward['cents']} бэт-коинов"
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
                    reward_text = f"💰 {reward['cents']} бэт-коинов"
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
                reward_text.append(f"💰 +{reward['cents']} бэт-коинов")
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
                reward_text.append(f"💰 +{reward['cents']} бэт-коинов")
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
                [KeyboardButton(f"💰 Купить за {price} бэт-коинов")],
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
                f"💰 Цена: {price} бэт-коинов\n\n"
                f"✅ Вы уже купили это существо сегодня!\n"
                f"⏰ Следующее предложение завтра в 00:00 МСК"
            )
        else:
            caption = (
                "🏕️ Лагерь Беженцев\n\n"
                f"🃏 Существо дня: {offered_card['title']}\n"
                f"🌟 Редкость: {offered_card['rarity']}\n"
                f"💰 Цена: {price} бэт-коинов (2x от награды за найм)\n\n"
                f"⚠️ Можно купить только 1 раз в день!\n"
                f"⏰ Обновляется в 00:00 МСК\n\n"
                f"💳 Ваш баланс: {user_data.get('cents', 0)} бэт-коинов"
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
                f"❌ Недостаточно бэт-коинов!\n"
                f"💰 Нужно: {price} бэт-коинов\n"
                f"💳 У вас: {user_data.get('cents', 0)} бэт-коинов\n\n"
                f"Нанимайте существ и получайте больше наград!",
            )
            return
        
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
            f"💰 Списано: {price} бэт-коинов\n\n"
            f"⏰ Следующее предложение завтра в 00:00 МСК"
        )
        
        await send_card(update, offered_card, context, caption=caption)
        
        logger.info(f"Игрок {user_id} купил существо #{offered_card_id} в Лагере Беженцев за {price} бэт-коинов")
        
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
                "/mercenary_add [ID_карты] [цена_в_бэт-коинах]\n\n"
                "**Пример:**\n"
                "/mercenary_add 45 5000 - добавить карту #45 за 5000 бэт-коинов",
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
            f"💰 Цена: {price} бэт-коинов\n"
            f"📊 Всего существ в Гильдии: {len(guild['creatures'])}/{guild['max_slots']}",
        )
        
        logger.info(f"Админ добавил существо #{card_id} за {price} бэт-коинов в Гильдию Наёмников")
        
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
                    f"💰 Цена была: {removed['price']} бэт-коинов\n"
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
                f"   💰 Цена: {creature['price']} бэт-коинов\n"
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
                    f"💰 Было: {old_price} бэт-коинов\n"
                    f"💰 Стало: {new_price} бэт-коинов",
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
            buy_text = f"💰 Купить за {item['price']} бэт-коинов"
            callback_data = f"mercenary_buy_rolls"
        else:
            buy_text = f"💰 Купить за {item['price']} бэт-коинов"
            callback_data = f"mercenary_buy_{item['card_id']}"
        
        if not can_afford:
            buy_text += " ❌ (Недостаточно бэт-коинов)"
        
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
                f"💰 Цена: {item['price']} бэт-коинов\n"
                f"💳 Ваш баланс: {user_data.get('cents', 0) if user_data else 0} бэт-коинов\n"
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
                f"💰 Цена: {item['price']} бэт-коинов\n"
                f"💳 Ваш баланс: {user_data.get('cents', 0) if user_data else 0} бэт-коинов\n"
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
            await query.answer("🪓 Гильдия Наёмников - покупайте существ и наймы за бэт-коины!", show_alert=False)
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
                await query.answer(f"❌ Недостаточно бэт-коинов! Нужно {price}", show_alert=True)
                return
            
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
                    f"💰 Списано: {price} бэт-коинов\n"
                    f"💳 Остаток: {user_data['cents']} бэт-коинов"
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
                await query.answer(f"❌ Недостаточно бэт-коинов! Нужно {price}", show_alert=True)
                return
            
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
                    f"💰 Списано: {price} бэт-коинов\n"
                    f"💳 Остаток: {user_data['cents']} бэт-коинов"
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
            
            logger.info(f"Игрок {user_id} купил существо #{card_id} за {price} бэт-коинов в Гильдии Наёмников")
            return
        
        # ⭐ КНОПКА "НАЗАД В ГИЛЬДИЮ" (после покупки) ⭐
        if query.data == "mercenary_back_to_guild":
            await show_mercenary_page(update, context, context.user_data.get(user_id, {}).get("mercenary_page", 0))
            return
        
    except Exception as e:
        logger.error(f"Ошибка mercenary_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

  
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
            CommandHandler("create_promo", create_promo_code),
            CommandHandler("delete_promo", delete_promo_code),
            CommandHandler("list_promo", list_promo_codes),
            CommandHandler("promo", activate_promo_code),
            CommandHandler("mercenary_add", mercenary_add),
            CommandHandler("mercenary_remove", mercenary_remove),
            CommandHandler("mercenary_list", mercenary_list),
            CommandHandler("mercenary_price", mercenary_update_price),
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
        ]

        for handler in handlers:
            application.add_handler(handler) 

        
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
