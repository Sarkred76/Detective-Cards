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

# Бонусы по редкостям
RARITY_BONUSES = {
    "Common": {"cents": 100, "points": 200, "probability": 57},
    "Rare": {"cents": 250, "points": 300, "probability": 22.5},
    "Rare Team-up": {"cents": 500, "points": 600, "probability": 10},
    "Epic": {"cents": 750, "points": 1000, "probability": 6},
    "Epic Team-up": {"cents": 1000, "points": 1250, "probability": 2.2},
    "Legendary": {"cents": 1250, "points": 1750, "probability": 1.7},
    "Legendary Team-up": {"cents": 2000, "points": 2500, "probability": 0.4},
    "Highlight": {"cents": 3000, "points": 4000, "probability": 0.2},
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
        user_data["casino_attempts"] = 5
        user_data["last_casino_reset"] = int(now_msk.timestamp())

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
        caption = f"⚔️ {card['title']}"
    else:
        caption = f"🔍 У Вас новый\n подозреваемый!\n\n{html.escape(card['title'])}"

    caption += f"\nРедкость: {card['rarity']}"
    
    # ⭐ НОВОЕ: ЦИТАТА ЧЕРЕЗ BLOCKQUOTE (HTML-тег) ⭐
    if card.get("catchphrase"):
        # <blockquote> — это и есть "цитата" в Telegram
        # <i> внутри — курсив
        # ⭐ ЗАМЕНЯЕМ ПЕРЕНОСЫ НА <br> ДЛЯ HTML ⭐
        escaped_phrase = html.escape(card['catchphrase']).replace("\n", "<br>")
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

async def send_card(update_or_chat_id: Update, card: Dict, context: ContextTypes.DEFAULT_TYPE, caption: Optional[str] = None, reply_markup: Optional[InlineKeyboardMarkup] = None, chat_id: Optional[int] = None) -> None:
    if isinstance(update_or_chat_id, Update):
        chat_id = update_or_chat_id.effective_chat.id
    if chat_id is None:
        return

    url = card["image_url"]
    
    try:
        # ⭐ Пытаемся отправить как видео (автовоспроизведение в чате)
        if card.get("media_type") == "animation" or url.lower().endswith((".mp4", ".webm")):
            await context.bot.send_video(
                chat_id=chat_id,
                video=url,
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup,
                supports_streaming=True,  # Включает inline-плеер
                width=400,  # Опционально: размер превью
                height=400
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
        # ⭐ Если видео не загрузилось, отправляем как документ/фото с fallback
        logger.warning(f"Не удалось отправить как видео: {e}. Отправляю как фото/документ.")
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=url,
            caption=caption,
            parse_mode="HTML",
            reply_markup=reply_markup
        )

async def edit_card_message(query, card: Dict, caption: str, reply_markup: InlineKeyboardMarkup) -> None:
    """Редактирует сообщение с карточкой."""
    try:
        if card.get("media_type") == "animation":
            media = InputMediaAnimation(
                media=card["image_url"], 
                caption=caption,
                parse_mode="HTML"  # ← ДОБАВЛЕНО
            )
        else:
            media = InputMediaPhoto(
                media=card["image_url"], 
                caption=caption,
                parse_mode="HTML"  # ← ДОБАВЛЕНО
            )
        await query.edit_message_media(media=media, reply_markup=reply_markup)
    except Exception as e:
        # ⭐ ИГНОРИРУЕМ ОШИБКУ "Message is not modified" ⭐
        if "Message is not modified" in str(e):
            logger.debug(f"Сообщение не изменилось, пропускаем редактирование")
            return
        logger.error(f"Ошибка редактирования сообщения: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start с поддержкой реферальной системы."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        
        # Инициализация пользователя, если его нет
        if user_id not in data["users"]:
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
                "referral_rewards_claimed": []
            }
            save_data(data)

        user_data = data["users"][user_id]

        # ⭐ ОБРАБОТКА РЕФЕРАЛЬНОЙ ССЫЛКИ ⭐
        referrer_id = None
        if context.args and context.args[0].startswith("ref_"):
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
                    
                    # Отправляем карту рефереру
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
                    callback_data=f"barracks_rarity_nav_{rarity}_{start_index - 1}"
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
                    callback_data=f"barracks_rarity_nav_{rarity}_{start_index + 1}"
                )
            )
        
        # ⭐ КНОПКА "НАЗАД" ⭐
        keyboard = [nav_buttons]
        keyboard.append([
            InlineKeyboardButton(
                "🔙 Назад",
                callback_data="barracks_back"
            )
        ])
        
        # Генерируем описание (уже содержит HTML-теги для catchphrase)
        caption = generate_card_caption(card, user_data, count=count, show_bonus=False)

        if query:
            try:
                # ⭐ ДОБАВЛЕНО parse_mode="HTML" В InputMedia ⭐
                if card.get("media_type") == "animation":
                    media = InputMediaAnimation(
                        media=card["image_url"], 
                        caption=caption,
                        parse_mode="HTML"  # ← ЭТО ИСПРАВЛЯЕТ КУРСИВ И QUOTE
                    )
                else:
                    media = InputMediaPhoto(
                        media=card["image_url"], 
                        caption=caption,
                        parse_mode="HTML"  # ← ЭТО ИСПРАВЛЯЕТ КУРСИВ И QUOTE
                    )
        
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
                # ⭐ ОТПРАВЛЯЕМ С УЧЁТОМ ТИПА МЕДИА ⭐
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
        else:
            # ⭐ ДЛЯ ОБЫЧНЫХ СООБЩЕНИЙ ИСПОЛЬЗУЕМ send_card ⭐
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
            
            # ⭐ СОРТИРУЕМ ДЛЯ СТАБИЛЬНОЙ НАВИГАЦИИ ⭐
            unique_card_ids.sort()
            
            card = find_card_by_id(unique_card_ids[0], data["cards"])
            if not card:
                await query.edit_message_text("Ошибка: существо не найдено")
                return
            
            # ⭐ ЛИНЕЙНАЯ НАВИГАЦИЯ (как в сортировке по редкости) ⭐
            nav_buttons = []
            
            # Кнопка "<" отсутствует для первой карты
            nav_buttons.append(
                InlineKeyboardButton(f"1/{len(unique_card_ids)}", callback_data="card_info")
            )
            
            # Кнопка ">" появляется только если карт больше 1
            if len(unique_card_ids) > 1:
                nav_buttons.append(
                    InlineKeyboardButton(">", callback_data=f"card_next_0")
                )
            
            keyboard = InlineKeyboardMarkup([
                nav_buttons,
                [InlineKeyboardButton("🔙 Назад", callback_data="barracks_back")]
            ])
            
            count = card_counts[card["id"]]
            caption = generate_card_caption(card, user_data, count=count, show_bonus=False)
            
            try:
                if card.get("media_type") == "animation":
                    media = InputMediaAnimation(media=card["image_url"], caption=caption, parse_mode="HTML")
                else:
                    media = InputMediaPhoto(media=card["image_url"], caption=caption, parse_mode="HTML")
                
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
            if not user_data or not user_data.get("cards"):
                await query.edit_message_text("У вас пока нет существ!")
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
                if card.get("media_type") == "animation":
                    media = InputMediaAnimation(media=card["image_url"], caption=caption, parse_mode="HTML")
                else:
                    media = InputMediaPhoto(media=card["image_url"], caption=caption, parse_mode="HTML")
                
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
            "Common", "Rare", "Rare Team-up", "Epic", "Epic Team-up", "Legendary", "Legendary Team-up", "Highlight", "Limited", 
        ]:
            if rarity in rarity_stats:
                rarity_text += f"• {rarity}: {rarity_stats[rarity]} шт.\n"
        if not rarity_text:
            rarity_text = "Пока нет существ\n"
            
        profile_text = (
            f"👤 Профиль игрока\n"
            f"🆔 ID: `{user_id}`\n"
            f"💰 Бэт-коинов: {user_data.get('cents', 0)}\n"
            f"💥 Очков репутации (сезон): {user_data.get('season_points', 0)}\n"
            f"💎 Очков репутации (всего): {user_data.get('total_points', 0)}\n\n"
            f"📦 Собрано карт: {unique_cards}/{total_available_cards}\n"
            f"📊 Заполненность: {collection_percent}%\n"
            f"🔢 Всего получено: {len(user_card_ids)}\n"
            f"📈 По редкостям:\n"
            f"{rarity_text}\n"
            f"🔍 Бесплатные попытки: {user_data.get('free_rolls', 0)}\n"
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
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                profile_text,
                parse_mode="Markdown"
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

        elif text == "🔙 Назад в меню":
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

            COOLDOWN_SECONDS = 3 * 60 * 60
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
            save_data(data)
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

        elif text == "🔗 Реферальная система":
            await referral_menu(update, context)

        elif text == "🔥 Сжигание":
            await burn_menu(update, context)
            return

        elif text == "🎲 Бросить кубик":
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
    """Добавление новой карточки (многострочно)."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        full_text = update.message.text
        lines = full_text.split("\n")
        
        if len(lines) < 5 :
            await update.message.reply_text(
                "ℹ️ Формат:\n"
                "/add_card\n"
                "URL\n"
                "Название\n"
                "Редкость\n"
                "Цитата (или 'нет')"
            )
            return
        
        url = lines[1].strip()
        title = lines[2].strip()
        rarity = lines[3].strip()
        catchphrase = lines[4].strip()
        
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

        # ⭐ ПРЕОБРАЗУЕМ \n В РЕАЛЬНЫЕ ПЕРЕНОСЫ ⭐
        if catchphrase.lower() != "нет":
            catchphrase = catchphrase.replace("\\n", "\n")
        else:
            catchphrase = None
        
        # ⭐ ДОБАВЛЯЕМ ВСЕ АТРИБУТЫ ⭐
        new_card = {
            "id": new_id,
            "image_url": url,
            "title": title,
            "rarity": rarity,
            "catchphrase": catchphrase,
            "available": True,
            "media_type": media_type,
        }
        
        data["cards"].append(new_card)
        save_data(data)

        catchphrase_text = f"\n💬 {catchphrase}" if catchphrase.lower() != "нет" else ""
        
        await update.message.reply_text(
            f"✅ Карточка #{new_id} добавлена!\n"
            f"🏷 {title}{catchphrase_text}\n"
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
                "• rarity - редкость (Common - Highlight, Limited)\n"
                "• catchphrase - цитата (текст, или 'нет' для удаления)\n"
                "• available - статус (true/false)\n",
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
            "title", "url", "rarity", "available", "catchphrase"
        ]
        if param not in valid_params:
            await update.message.reply_text(
                f"⚠️ Неверный параметр! Доступные: {', '.join(valid_params)}"
            )
            return
        
        # Сохраняем старое значение
        old_value = card.get(param, "не задано")
        
        # ⭐ ОБРАБОТКА ОСТАЛЬНЫХ ПАРАМЕТРОВ ⭐
        if param == "available":
            new_value = new_value.lower() in ["true", "1", "yes", "вкл", "on"]
            card[param] = new_value
        elif param == "catchphrase":
            if new_value.lower() != "нет":
                # ⭐ ПРЕОБРАЗУЕМ \n В РЕАЛЬНЫЕ ПЕРЕНОСЫ ⭐
                card[param] = new_value.replace("\\n", "\n")
            else:
                card[param] = None
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

        if card.get("catchphrase"):
            response += f"\n💬 _\"{card['catchphrase']}\"_"
        
        response += f"\n\n{'✅ Включена' if card.get('available') else '❌ Выключена'}"
        
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
    """Бросок кубика для получения бесплатных попыток (раз в неделю, сброс в понедельник 00:00 МСК)."""
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

        # ⭐ ПРОВЕРКА ЕЖЕНЕДЕЛЬНОГО СБРОСА ⭐
        check_dice_reset(user_data)
        
        current_time = int(time.time())
        last_dice_time = user_data.get("last_dice_time", 0)
        
        # Если last_dice_time != 0, значит на этой неделе игрок уже бросал кубик
        if last_dice_time != 0:
            import datetime
            msk_tz = datetime.timezone(datetime.timedelta(hours=3))
            now_msk = datetime.datetime.now(msk_tz)
            
            # Вычисляем, сколько дней осталось до следующего понедельника
            days_until_monday = (7 - now_msk.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7  # Если сегодня понедельник, но бросок уже был, ждем 7 дней
                
            next_monday = now_msk.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=days_until_monday)
            remaining_seconds = int((next_monday - now_msk).total_seconds())
            
            days = remaining_seconds // 86400
            hours = (remaining_seconds % 86400) // 3600
            minutes = (remaining_seconds % 3600) // 60
            
            time_text = ""
            if days > 0:
                time_text += f"{days} дн. "
            time_text += f"{hours} ч {minutes} мин"
            
            await update.message.reply_text(
                f"⏳ Вы уже бросали кубик на этой неделе!\n"
                f"Следующий бросок будет доступен в понедельник.\n"
                f"Осталось ждать: {time_text}\n"
                f"🔍 У вас есть {user_data.get('free_rolls', 0)} бесплатных попыток"
            )
            return

        # ⭐ ОТПРАВЛЯЕМ НАСТОЯЩИЙ КУБИК TELEGRAM ⭐
        sent_dice = await context.bot.send_dice(chat_id=update.effective_chat.id, emoji="🎲")
        dice_value = sent_dice.dice.value  # Значение от 1 до 6
        
        # Добавляем бесплатные попытки (ровно столько, сколько выпало)
        user_data["free_rolls"] = user_data.get("free_rolls", 0) + dice_value
        user_data["last_dice_time"] = current_time
        save_data(data)
        
        await asyncio.sleep(4)
        await update.message.reply_text(
            f"🎲 Выпало: {dice_value}!\n"
            f"🔍 Получено бесплатных попыток: {dice_value}\n"
            f"📊 Всего бесплатных попыток: {user_data['free_rolls']}\n"
            f"⏳ Следующий бросок доступен в следующий понедельник в 00:00 МСК"
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
    
    # Если год или неделя изменились, сбрасываем время последнего броска
    if last_year == 0 or current_year != last_year or current_week != last_week:
        user_data["last_dice_time"] = 0
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
            [KeyboardButton("🎲 Бросить кубик"), KeyboardButton("🎰 Казино"), KeyboardButton("🏀 Баскет")],
            [KeyboardButton("🎯 Дартс"), KeyboardButton("🏆 Топ игроков"), KeyboardButton("🔄 Трейд")],
            [KeyboardButton("🔥 Сжигание"), KeyboardButton("🔗 Реферальная система"), KeyboardButton("🔙 Назад в меню")]
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
                    f"У вас: {cents} бэт-коинов\n\n"
                    f"Нанимайте существ и получайте больше наград! 💰",
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
                parse_mode="Markdown",
            )
            await update_weekly_quest_progress(context, user_id, "weekly_casino_win", 1)

        else:
            await asyncio.sleep(2)
            await query.message.reply_text(
                f"😔 Не повезло! Попробуйте ещё раз.\n\n"
                f"💰 Списано: 1500 бэт-коинов\n"
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

async def add_card_to_player(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавляет определённую карту определённому игроку (по ID или @никнейму)."""
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
            if target_user_id not in data["users"]:
                await update.message.reply_text(f"⚠️ Игрок с ID {target_user_id} не найден!")
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
            f"✅ **Карта добавлена!**\n"
            f"👤 Игрок: {target_user_id}\n"
            f"🃏 Карта: {card['title']} (#{card_id})\n"
            f"🌟 Редкость: {card['rarity']}\n"
            f"📦 Количество: {count} шт.\n"
            f"Всего карт у игрока: {len(user_data['cards'])}",
            parse_mode="Markdown",
        )
    except ValueError:
        await update.message.reply_text("⚠️ ID карты и количество должны быть числами!")
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

        # ⭐ ЛОГИКА ПОИСКА ПО @НИКНЕЙМУ ⭐
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
            # Если ввели ID
            target_user_id = target_input
            # Если игрока с таким ID нет, пометим для создания
            if target_user_id not in data["users"]:
                is_new_user = True

        # Создаем игрока, если его нет (работает только для ID)
        if target_user_id not in data["users"]:
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
                "casino_attempts": 5,
                "last_casino_reset": 0,
            }
            data["users"][target_user_id] = user_data
        else:
            user_data = data["users"][target_user_id]

        # Добавляем попытки
        old_rolls = user_data.get("free_rolls", 0)
        user_data["free_rolls"] = old_rolls + rolls_count
        save_data(data)

        await update.message.reply_text(
            f"✅ **Наймы добавлены!**\n"
            f"👤 Герой: {target_user_id}\n"
            f"🔍 Добавлено: {rolls_count}\n"
            f"📊 Было: {old_rolls}\n"
            f"📈 Стало: {user_data['free_rolls']}\n"
            f"{'🆕 Герой создан!' if is_new_user else ''}",
            parse_mode="Markdown",
        )
    except ValueError:
        await update.message.reply_text("⚠️ Количество должно быть числом!")
    except Exception as e:
        logger.error(f"Ошибка добавления наймов герою: {e}")
        await update.message.reply_text("❌ Ошибка при добавлении наймов")

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
        
        keyboard = [
            [InlineKeyboardButton("🎰 Сыграть)", callback_data="casino_play")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🎰 **Казино**\n\n"
            f"📜 **Правила:**\n"
            f"• Стоимость игры: 1500 бэт-коинов\n"
            f"• Крутите слот и получите 3 одинаковых значения\n"
            f"• При победе: 10 бесплатных попыток\n"
            f"• Лимит: 5 игр в день (сброс в 00:00 МСК)\n",
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
    clan_id = get_user_clan(user_id, data)  # ← Получаем ID
    if not clan_id:
        return False, "Вы не состоите в клане!"
    
    clan = get_clan_data(clan_id, data)  # ← Исправлено: используем clan_id
    if not clan:
        return False, "Ошибка: клан не найден!"
    
    is_leader = user_id == clan["leader_id"]
    clan_name = clan["name"]  # ← Сохраняем имя для сообщения
    
    if is_leader and len(clan["members"]) > 1:
        return False, "Вы не можете покинуть клан, пока в нём есть другие участники!\nПередайте лидерство или расформируйте клан."
    
    # Удаляем пользователя из клана
    if user_id in clan["members"]:
        del clan["members"][user_id]
    
    # Если клан пуст — удаляем его
    if not clan["members"]:
        del data["clans"][clan_id]  # ← Используем clan_id как ключ
    
    # Удаляем привязку пользователя
    if user_id in data["user_clan"]:
        del data["user_clan"][user_id]
    
    return True, f"Вы покинули клан **{clan_name}**." if not is_leader else f"Клан **{clan_name}** распущен."

def get_clan_members_list(clan_id: str, data: Dict) -> str:
    """Формирует текст со списком участников клана и их очками репутации."""
    clan = get_clan_data(clan_id, data)
    if not clan:
        return "❌ Клан не найден!"
    
    # ← Исправлено: clan["name"] вместо clan_name
    members_text = f"👥 Участники клана **{clan['name']}**:\n\n"
    
    for member_id, member_info in clan["members"].items():
        user_data = data["users"].get(member_id, {})
        username = user_data.get("first_name", "Неизвестно")
        if user_data.get("last_name"):
            username += f" {user_data['last_name']}"
        
        reputation = user_data.get("season_points", 0)
        role_emoji = "👑" if member_info.get("role") == "leader" else "•"
        
        members_text += f"{role_emoji} {username} — {reputation} очков репутации\n"
    
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
            [KeyboardButton("🔙 Назад в меню")]
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
        
        await update.message.reply_text(
            f"🏰 **Создание клана**\n\n"
            f"Стоимость: **30 000 бэт-коинов**\n\n"
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
                "❌ Вы не состоите в клане!\n\n"
                "Создайте свой клан или попросите главу другого клана пригласить вас.",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return
        
        clan = get_clan_data(clan_id, data)
        if not clan:
            await update.message.reply_text("❌ Ошибка: данные клана повреждены!")
            return
        
        is_leader = user_id == clan["leader_id"]
        clan_name = clan["name"] 
        
        # Формируем сообщение
        members_list = get_clan_members_list(clan["name"], data)
        
        message_text = (
            f"🏰 **Ваш клан: {clan["name"]}**\n\n"
            f"{members_list}\n"
            f"📊 Всего участников: {len(clan['members'])}\n"
            f"📅 Создан: {datetime.datetime.fromtimestamp(clan['created_at']).strftime('%d.%m.%Y')}"
        )
        
        # Кнопки для лидера
        if is_leader:
            keyboard = [
                [KeyboardButton("📨 Пригласить игрока")],
                [KeyboardButton("🚪 Покинуть клан")],
                [KeyboardButton("🔙 Назад в кланы")]
            ]
        else:
            keyboard = [
                [KeyboardButton("🚪 Покинуть клан")],
                [KeyboardButton("🔙 Назад в кланы")]
            ]
        
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в my_clan_view: {e}")
        await update.message.reply_text("❌ Ошибка при показе информации о клане")


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
        
    current_cents = data["users"][user_id].get("cents", 0)
    if current_cents < CLAN_CREATION_COST:
        return False, f"Недостаточно бэт-коинов! Нужно {CLAN_CREATION_COST}."
        
    # ✅ Списываем стоимость создания
    data["users"][user_id]["cents"] -= CLAN_CREATION_COST
    
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
    }
    # Привязываем пользователя к клану
    data.setdefault("user_clan", {})[user_id] = clan_name
    
    return True, f"Клан **«{clan_name}»** успешно создан!"

async def basket_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню и правила игры Баскет."""
    keyboard = [[InlineKeyboardButton("🏀 Сыграть", callback_data="basket_play")]]
    caption = (
        "🏀 **Игра «Баскет»**\n\n"
        "📜 **Правила:**\n"
        "• Стоимость игры: 800 бэт-коинов\n"
        "• Бот бросает 3 баскетбольных мяча 🏀\n"
        "• За каждое попадание вы получаете 1 бесплатную попытку\n"
        "• Лимит: 5 игр в день (сброс в 00:00 МСК)"
    )
    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query
        try: await query.message.delete()
        except: pass
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
SHOP_MAIN_IMAGE = "https://files.catbox.moe/e8verh.jpg"  # Главное меню
SHOP_DONATE_IMAGE = "https://files.catbox.moe/1tcx0h.jpg"    # Донат
SHOP_BOX_IMAGE = "https://files.catbox.moe/0qmfkc.jpg"         # Общая картинка бокса

# Список боксов для навигации
SHOP_BOXES = [
    {"name": "Бокс Суща", "price": 100000, "image": SHOP_BOX_IMAGE},
    {"name": "Бокс Игната", "price": 100000, "image": SHOP_BOX_IMAGE},
    {"name": "Бокс Наруми", "price": 100000, "image": SHOP_BOX_IMAGE},
    {"name": "Бокс Шадива", "price": 100000, "image": SHOP_BOX_IMAGE}
]

async def shop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Главное меню магазина."""
    keyboard = [
        [InlineKeyboardButton("📦 Боксы", callback_data="shop_boxes")],
        [InlineKeyboardButton("🎟️ Попытки", callback_data="shop_tries")],
        [InlineKeyboardButton("💎 Донат", callback_data="shop_donate")],
    ]
    # Если вызов через callback, удаляем старое сообщение
    if hasattr(update, 'callback_query') and update.callback_query:
        try: 
            await update.callback_query.message.delete()
        except: 
            pass
        await context.bot.send_photo(
            chat_id=update.callback_query.message.chat_id,  # ← ИСПРАВЛЕНО
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

async def shop_tries(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Раздел Попытки."""
    keyboard = [
        [InlineKeyboardButton("🎟️ Купить 10 попыток за 10 000 бэт-коинов", callback_data="shop_buy_10_tries")],
        [InlineKeyboardButton("🔙 Назад в Магазин", callback_data="shop_menu")]
    ]
    text = "🎟️ **Покупка попыток**\n\nВыберите предложение:"
    if hasattr(update, 'callback_query') and update.callback_query:
        try: 
            await update.callback_query.message.delete()
        except: 
            pass
        await context.bot.send_message(
            chat_id=update.callback_query.message.chat_id,  # ← ИСПРАВЛЕНО
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

async def shop_boxes(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
    """Раздел Боксы с навигацией."""
    if not context.user_data.get("shop_box_index"):
        context.user_data["shop_box_index"] = 0
        
    current_box = SHOP_BOXES[page]
    keyboard = [
        [InlineKeyboardButton(f"💰 Купить за {current_box['price']} бэт-коинов", callback_data=f"shop_buy_box_{page}")],
        [InlineKeyboardButton("🔙 Назад в Магазин", callback_data="shop_menu")]
    ]
    
    # Навигация ◀️ ▶️
    nav_btns = []
    if page > 0: 
        nav_btns.append(InlineKeyboardButton("◀️", callback_data=f"shop_boxes_{page-1}"))
    nav_btns.append(InlineKeyboardButton(f"{page+1}/{len(SHOP_BOXES)}", callback_data="shop_info"))
    if page < len(SHOP_BOXES) - 1: 
        nav_btns.append(InlineKeyboardButton("▶️", callback_data=f"shop_boxes_{page+1}"))
    
    keyboard.insert(1, nav_btns)

    text = f"📦 **{current_box['name']}**\n\nЦена: {current_box['price']} бэт-коинов"
    if hasattr(update, 'callback_query') and update.callback_query:
        try: 
            await update.callback_query.message.delete()
        except: 
            pass
        await context.bot.send_photo(
            chat_id=update.callback_query.message.chat_id,  # ← ИСПРАВЛЕНО
            photo=current_box["image"], 
            caption=text, 
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
        
async def shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик всех кнопок магазина."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "shop_menu":
        await shop_menu(update, context)
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
            
            if user_data.get("cents", 0) < box["price"]:
                # ❌ Ошибка: недостаточно средств
                await query.answer("❌ Недостаточно бэт-коинов!", show_alert=True)
                await context.bot.send_message(  # ← ДОБАВЛЕНО
                    chat_id=query.message.chat_id,
                    text="❌ **Ошибка покупки**\n\nНедостаточно бэт-коинов!",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад в магазин", callback_data="shop_menu")
                    ]]),
                    parse_mode="Markdown"
                )
            else:
                # ✅ Успешная покупка
                user_data["cents"] -= box["price"]
                save_data(data)
                
                await query.answer(f"✅ Вы купили {box['name']}!", show_alert=True)
                await context.bot.send_message(  # ← ДОБАВЛЕНО
                    chat_id=query.message.chat_id,
                    text=(
                        f"✅ **Покупка успешна!**\n\n"
                        f"📦 Вы приобрели: **{box['name']}**\n"
                        f"💰 Списано: {box['price']} бэт-коинов\n"
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
            
    elif query.data == "shop_buy_10_tries":
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id, {})
        
        if user_data.get("cents", 0) < 10000:
            await query.answer("❌ Недостаточно бэт-коинов!", show_alert=True)
            await context.bot.send_message(  # ← ДОБАВЛЕНО
                chat_id=query.message.chat_id,
                text="❌ **Ошибка покупки**\n\nНедостаточно бэт-коинов для покупки 10 попыток!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="shop_tries")
                ]]),
                parse_mode="Markdown"
            )
        else:
            user_data["cents"] -= 10000
            user_data["free_rolls"] = user_data.get("free_rolls", 0) + 10
            save_data(data)
            
            await query.answer("✅ Куплено 10 бесплатных попыток!", show_alert=True)
            await context.bot.send_message(  # ← ДОБАВЛЕНО
                chat_id=query.message.chat_id,
                text=(
                    f"✅ **Покупка успешна!**\n\n"
                    f"🎟️ Добавлено: **10 бесплатных попыток**\n"
                    f"💰 Списано: 10 000 бэт-коинов\n"
                    f"💳 Остаток: {user_data['cents']} бэт-коинов"
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="shop_tries")
                ]]),
                parse_mode="Markdown"
            )

    elif query.data == "shop_info":
        await query.answer("📦 Используйте ◀️ и ▶️ для навигации по боксам", show_alert=False)

# ===== МЕНЮ СЖИГАНИЯ =====
async def burn_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню выбора редкости для сжигания (3×3 сетка)."""
    try:
        query = update.callback_query if hasattr(update, 'callback_query') else None
        user_id = str(update.effective_user.id)
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
        keyboard.append([
            InlineKeyboardButton("📋 Все карты", callback_data="burn_all")
        ])
        keyboard.append([
            InlineKeyboardButton("🔥 Сжечь ВСЁ", callback_data="burn_all_preview")
        ])
        
        caption = (
            "🔥 **Меню сжигания**\n"
            "Выберите редкость для просмотра карт:\n\n"
            "💰 **Награды за сжигание:**\n"
            "• Common: 100 бэт-коинов 💰\n"
            "• Rare: 200 бэт-коинов 💰\n"
            "• Rare Team-up: 300 бэт-коинов 💰\n"
            "• Epic: 1 бесплатный найм 🎲\n"
            "• Epic Team-up: 3 бесплатных найма 🎲\n"
            "• Legendary: 5 бесплатных наймов 🎲\n"
            "• Legendary Team-up: 7 бесплатных наймов 🎲\n"
            "• Highlight: 10 бесплатных наймов 🎲"
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
        logger.error(f"Ошибка в burn_menu: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Ошибка", show_alert=True)
        else:
            await update.message.reply_text("❌ Ошибка при открытии меню сжигания")


async def show_burn_cards(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    rarity: Optional[str] = None,
    start_index: int = 0
) -> None:
    """Показывает карты для сжигания с навигацией."""
    try:
        query = update.callback_query if hasattr(update, 'callback_query') else None
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            if query:
                await query.edit_message_text("❌ У вас нет карт!")
            else:
                await update.message.reply_text("❌ У вас нет карт!")
            return
        
        # Считаем количество каждой карты (дубликаты)
        card_counts = Counter(user_data["cards"])
        unique_card_ids = list(card_counts.keys())
        
        # Фильтруем по редкости если нужно
        if rarity and rarity != "all":
            display_cards = [
                cid for cid in unique_card_ids
                if (c := find_card_by_id(cid, data["cards"])) and c.get("rarity") == rarity
            ]
        else:
            display_cards = unique_card_ids
        
        if not display_cards:
            msg = f"❌ У вас нет карт{' этой редкости' if rarity and rarity != 'all' else ''}!"
            if query:
                await query.edit_message_text(msg)
            else:
                await update.message.reply_text(msg)
            return
        
        # Сортируем для стабильной навигации
        display_cards.sort()
        total_cards = len(display_cards)
        
        # Корректировка индекса
        start_index = max(0, min(start_index, total_cards - 1))
        
        current_card_id = display_cards[start_index]
        card = find_card_by_id(current_card_id, data["cards"])
        count = card_counts[current_card_id]
        
        if not card:
            if query:
                await query.edit_message_text("❌ Ошибка: карта не найдена!")
            else:
                await update.message.reply_text("❌ Ошибка: карта не найдена!")
            return
        
        # ⭐ НАГРАДА ЗА СЖИГАНИЕ ⭐
        reward = BURN_REWARDS.get(card["rarity"], {"cents": 0, "free_rolls": 0})
        reward_parts = []
        if reward["cents"] > 0:
            reward_parts.append(f"💰 +{reward['cents']} бэт-коинов")
        if reward["free_rolls"] > 0:
            reward_parts.append(f"🎲 +{reward['free_rolls']} бесплатных наймов")
        
        caption = (
            f"🔥 {card['title']}\n"
            f"🌟 Редкость: {card['rarity']}\n"
            f"📦 В коллекции: {count} шт.\n\n"
            f"🎁 При сжигании вы получите:\n"
            f"{' | '.join(reward_parts) if reward_parts else 'Ничего'}"
        )
        
        # ⭐ КЛАВИАТУРА: навигация + действия ⭐
        nav_row = []
        if start_index > 0:
            nav_row.append(InlineKeyboardButton(
                "◀️", callback_data=f"burn_prev_{rarity or 'all'}_{start_index - 1}"
            ))
        nav_row.append(InlineKeyboardButton(
            f"{start_index + 1}/{total_cards}", callback_data="burn_info"
        ))
        if start_index < total_cards - 1:
            nav_row.append(InlineKeyboardButton(
                "▶️", callback_data=f"burn_next_{rarity or 'all'}_{start_index + 1}"
            ))
        
        keyboard = [nav_row]
        keyboard.append([
            InlineKeyboardButton("🔥 Сжечь", callback_data=f"burn_confirm_{current_card_id}"),
            InlineKeyboardButton("🔙 Назад", callback_data="burn_back")
        ])
        
        if query:
            try:
                if card.get("media_type") == "animation":
                    media = InputMediaAnimation(media=card["image_url"], caption=caption)
                else:
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
                await send_card(update, card, context, caption=caption, 
                              reply_markup=InlineKeyboardMarkup(keyboard),
                              chat_id=query.message.chat_id)
        else:
            await send_card(update, card, context, caption=caption, 
                          reply_markup=InlineKeyboardMarkup(keyboard))
            
    except Exception as e:
        logger.error(f"Ошибка в show_burn_cards: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("❌ Произошла ошибка")


async def burn_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, card_id: int) -> None:
    """Показывает подтверждение сжигания."""
    try:
        query = update.callback_query
        user_id = str(query.from_user.id)
        data = load_data()
        
        card = find_card_by_id(card_id, data["cards"])
        if not card:
            await query.answer("❌ Карта не найдена!", show_alert=True)
            return
        
        reward = BURN_REWARDS.get(card["rarity"], {"cents": 0, "free_rolls": 0})
        reward_parts = []
        if reward["cents"] > 0:
            reward_parts.append(f"💰 +{reward['cents']} бэт-коинов")
        if reward["free_rolls"] > 0:
            reward_parts.append(f"🎲 +{reward['free_rolls']} бесплатных наймов")
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"burn_execute_{card_id}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"burn_show_{card['rarity']}")
            ]
        ]

        try:
            await query.edit_message_text(
                f"❓ **Подтвердите сжигание**\n\n"
                f"🃏 Карта: {card['title']}\n"
                f"🌟 Редкость: {card['rarity']}\n\n"
                f"🎁 Вы получите:\n"
                f"{' | '.join(reward_parts) if reward_parts else 'Ничего'}\n\n"
                f"⚠️ Карта будет безвозвратно удалена из коллекции!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception:
            await query.edit_message_caption(
                f"❓ **Подтвердите сжигание**\n\n"
                f"🃏 Карта: {card['title']}\n"
                f"🌟 Редкость: {card['rarity']}\n\n"
                f"🎁 Вы получите:\n"
                f"{' | '.join(reward_parts) if reward_parts else 'Ничего'}\n\n"
                f"⚠️ Карта будет безвозвратно удалена из коллекции!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Ошибка в burn_confirm: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


async def burn_execute(update: Update, context: ContextTypes.DEFAULT_TYPE, card_id: int) -> None:
    """Выполняет сжигание карты."""
    try:
        query = update.callback_query
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        # Проверяем наличие карты
        if card_id not in user_data.get("cards", []):
            await query.answer("❌ У вас нет этой карты!", show_alert=True)
            return
        
        card = find_card_by_id(card_id, data["cards"])
        if not card:
            await query.answer("❌ Карта не найдена!", show_alert=True)
            return

        # ⭐ УДАЛЯЕМ ОДНУ КОПИЮ КАРТЫ ⭐
        user_data["cards"].remove(card_id)

        # ⭐ НОВЫЙ ТРИГГЕР: сжигание карты Rare ⭐
        if card["rarity"] == "Rare":
            await update_weekly_quest_progress(context, user_id, "weekly_burn_rare_4", 1)

        # ⭐ НОВЫЙ ТРИГГЕР: сжечь карту Common ⭐
        if card["rarity"] == "Common":
            await update_quest_progress(context, user_id, "burn_common_3", 1)
        
        # ⭐ ВЫДАЁМ НАГРАДУ ⭐
        reward = BURN_REWARDS.get(card["rarity"], {"cents": 0, "free_rolls": 0})
        user_data["cents"] = user_data.get("cents", 0) + reward["cents"]
        user_data["free_rolls"] = user_data.get("free_rolls", 0) + reward["free_rolls"]
        
        save_data(data)
        
        reward_parts = []
        if reward["cents"] > 0:
            reward_parts.append(f"💰 +{reward['cents']} бэт-коинов")
        if reward["free_rolls"] > 0:
            reward_parts.append(f"🎲 +{reward['free_rolls']} бесплатных наймов")
        
        keyboard = [[InlineKeyboardButton("🔙 Назад в сжигание", callback_data="burn_back")]]

        try:
            await query.edit_message_text(
                f"✅ **Сжигание успешно!** 🔥\n\n"
                f"🗑️ Удалено: {card['title']}\n"
                f"🌟 Редкость: {card['rarity']}\n\n"
                f"🎁 Награда получена:\n"
                f"{' | '.join(reward_parts)}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception:
            await query.edit_message_caption(
                f"✅ **Сжигание успешно!** 🔥\n\n"
                f"🗑️ Удалено: {card['title']}\n"
                f"🌟 Редкость: {card['rarity']}\n\n"
                f"🎁 Награда получена:\n"
                f"{' | '.join(reward_parts)}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        logger.info(f"Игрок {user_id} сжёг карту #{card_id} ({card['rarity']})")
        
    except Exception as e:
        logger.error(f"Ошибка в burn_execute: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def burn_all_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает предпросмотр награды за сжигание ВСЕХ карт."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)

        if not user_data or not user_data.get("cards"):
            await query.edit_message_text("❌ У вас нет карт для сжигания!")
            return

        total_cents = 0
        total_rolls = 0
        card_counts = Counter(user_data["cards"])

        # Подсчитываем общую награду
        for card_id, count in card_counts.items():
            card = find_card_by_id(card_id, data["cards"])
            if card:
                reward = BURN_REWARDS.get(card["rarity"], {"cents": 0, "free_rolls": 0})
                total_cents += reward["cents"] * count
                total_rolls += reward["free_rolls"] * count

        total_cards = len(user_data["cards"])

        text = (
            f"🔥 **Сжечь ВСЕ карты?**\n\n"
            f"📦 Всего карт в коллекции: {total_cards}\n\n"
            f"💰 Вы получите: {total_cents} бэт-коинов\n"
            f"🎲 Вы получите: {total_rolls} бесплатных наймов\n\n"
            f"⚠️ **ВНИМАНИЕ!** Все ваши карты будут безвозвратно удалены!"
        )

        keyboard = [
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data="burn_all_execute"),
                InlineKeyboardButton("❌ Отмена", callback_data="burn_back")
            ]
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка в burn_all_preview: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


async def burn_all_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выполняет сжигание ВСЕХ карт и выдачу наград."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)

        if not user_data or not user_data.get("cards"):
            await query.edit_message_text("❌ У вас нет карт для сжигания!")
            return

        # Снова пересчитываем награду (для безопасности)
        total_cents = 0
        total_rolls = 0
        card_counts = Counter(user_data["cards"])
        total_cards_burned = len(user_data["cards"]) # Сохраняем количество до очистки

        for card_id, count in card_counts.items():
            card = find_card_by_id(card_id, data["cards"])
            if card:
                reward = BURN_REWARDS.get(card["rarity"], {"cents": 0, "free_rolls": 0})
                total_cents += reward["cents"] * count
                total_rolls += reward["free_rolls"] * count

        # ⭐ ОЧИЩАЕМ КОЛЛЕКЦИЮ И ВЫДАЕМ НАГРАДУ ⭐
        user_data["cards"] = []
        user_data["cents"] = user_data.get("cents", 0) + total_cents
        user_data["free_rolls"] = user_data.get("free_rolls", 0) + total_rolls
        save_data(data)

        text = (
            f"✅ **Все карты успешно сожжены!** 🔥\n\n"
            f"🗑️ Удалено карт: {total_cards_burned}\n"
            f"💰 Получено бэт-коинов: +{total_cents}\n"
            f"🎲 Получено бесплатных наймов: +{total_rolls}"
        )

        keyboard = [[InlineKeyboardButton("🔙 Назад в меню сжигания", callback_data="burn_back")]]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        logger.info(f"Игрок {user_id} сжёг ВСЕ карты ({total_cards_burned} шт.)")
        
    except Exception as e:
        logger.error(f"Ошибка в burn_all_execute: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


async def burn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик всех callback кнопок сжигания."""
    try:
        query = update.callback_query
        await query.answer()
        
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
            await show_burn_cards(update, context, rarity=rarity, start_index=0)
            return
        
        # Все карты
        if query.data == "burn_all":
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
            await burn_menu(update, context)
            return
            
    except Exception as e:
        logger.error(f"Ошибка в burn_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def darts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню и правила игры Дартс."""
    keyboard = [[InlineKeyboardButton("🎯 Сыграть", callback_data="darts_play")]]
    caption = (
        "🎯 **Мини-игра «Дартс»**\n\n"
        "📜 **Правила:**\n"
        "• Стоимость игры: 1000 бэт-коинов\n"
        "• Бот бросает 3 дротика 🎯\n"
        "• Мишень имеет 5 зон: от 1 до 5 очков\n"
        "• Наберите 10+ очков за 3 броска, чтобы получить 3 бесплатные попытки 🎲\n"
        "• Лимит: 5 игр в день (сброс в 00:00 МСК)\n"
    )
    if hasattr(update, 'callback_query') and update.callback_query:
        try: await update.callback_query.message.delete()
        except: pass
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
            user_data["free_rolls"] = user_data.get("free_rolls", 0) + 3
            save_data(data)
            await update_quest_progress(context, user_id, "darts_win_2", 1)

        await query.message.reply_text(
            f"🎯 **Результаты бросков:** {', '.join(map(str, results))}\n"
            f"📊 **Итого очков:** {total_points}/10\n"
            f"{'✅ Победа! Получено 3 бесплатные попытки 🎲' if win else '😔 Не хватило очков. Попробуйте ещё раз.'}",
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
    """Показывает топ-10 кланов по очкам репутации."""
    try:
        data = load_data()
        clans = data.get("clans", {})
        users = data.get("users", {})

        if not clans:
            await update.message.reply_text("📭 Пока нет созданных кланов!")
            return

        clan_scores = []
        for clan_id, clan_data in clans.items():
            total_rep = 0
            member_count = len(clan_data.get("members", {}))
            
            # Суммируем total_points всех участников
            for member_id in clan_data.get("members", {}):
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

        message_text = "🏆 **Топ кланов по репутации**\n\n"
        for rank, clan in enumerate(top_10, 1):
            if rank == 1: medal = "🥇"
            elif rank == 2: medal = "🥈"
            elif rank == 3: medal = "🥉"
            else: medal = f"{rank}."

            message_text += f"{medal} **{clan['name']}**\n"
            message_text += f"   👥 Участников: {clan['members']}\n"
            message_text += f"   💎 Репутация: {clan['reputation']}\n\n"

        # Показываем место клана пользователя, если он в клане
        user_id = str(update.effective_user.id)
        user_clan_id = data.get("user_clan", {}).get(user_id)
        if user_clan_id:
            user_clan_rank = None
            for i, c in enumerate(clan_scores, 1):
                if c["id"] == user_clan_id:
                    user_clan_rank = i
                    break
            
            if user_clan_rank:
                message_text += "\n" + "─" * 30 + "\n"
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
        await update.message.reply_text(
            "📋 Меню\nВыберите раздел:",
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

        # Формируем список приглашенных
        if invites:
            lines = []
            for i, inv_id in enumerate(invites, 1):
                inv_user = data["users"].get(inv_id, {})
                name = inv_user.get("username")
                if not name:
                    name = inv_user.get("first_name", f"Пользователь {inv_id}")
                else:
                    name = f"@{name}"
                lines.append(f"{i}. {name}")
            invite_list_text = "\n".join(lines)
        else:
            invite_list_text = "Список пуст"

        # Статусы наград
        reward_1 = "✅ Получено" if 1 in claimed else ("🎁 **ДОСТУПНО!**" if count >= 1 else "🔒 За 1 приглашение")
        reward_3 = "✅ Получено" if 3 in claimed else ("🎁 **ДОСТУПНО!**" if count >= 3 else "🔒 За 3 приглашения")

        text = (
            f"🔗 **Реферальная система**\n\n"
            f"Приглашайте друзей и получайте ценные награды!\n\n"
            f"📎 **Ваша уникальная ссылка:**\n`{ref_link}`\n\n"
            f"👥 **Всего приглашено:** {count}\n"
            f"📋 **Список приглашенных:**\n{invite_list_text}\n\n"
            f"🎁 **Награды:**\n"
            f"1️⃣ 1 приглашение: Случайная карта редкости **Epic**\n"
            f"   Статус: {reward_1}\n"
            f"3️⃣ 3 приглашения: Случайная карта редкости **Epic Team-up**\n"
            f"   Статус: {reward_3}\n\n"
            f"💡 *Награды выдаются автоматически в момент приглашения нового игрока!*"
        )

        keyboard = [[InlineKeyboardButton("🔙 Назад в Личное дело", callback_data="my_profile")]]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Ошибка в referral_menu: {e}")

# ===== ЕЖЕДНЕВНЫЕ КВЕСТЫ =====
DAILY_QUESTS_POOL = [
    {"id": "common_4", "desc": "Получить 4 карты редкости Common", "reward_type": "cents", "reward_amount": 500, "target": 4},
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

async def quests_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню квестов с тремя разделами."""
    keyboard = [
        [InlineKeyboardButton("📅 Ежедневные", callback_data="quests_daily")],
        [InlineKeyboardButton("📆 Еженедельные", callback_data="quests_weekly")],
        [InlineKeyboardButton("🏆 Сезонные", callback_data="quests_seasonal")],
        [InlineKeyboardButton("🔙 Назад в меню", callback_data="quests_back")]
    ]
    text = (
        "📜 <b>Квесты</b>\n\n"
        "Выберите раздел:\n\n"
        "• 📅 <b>Ежедневные</b> — обновляются каждый день в 00:00 МСК\n"
        "• 📆 <b>Еженедельные</b> — обновляются каждый понедельник в 00:00 МСК\n"
        "• 🏆 <b>Сезонные</b> — скоро"
    )
    
    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query
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
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )


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
            await query.message.delete()
            keyboard = [[InlineKeyboardButton("🔙 Назад к квестам", callback_data="quests_menu")]]
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="🏆 <b>Сезонные квесты</b>\n\n🔒 Скоро появятся!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
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
        "desc": "Получить 6 карт редкости Rare",
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
        "desc": "Получить карту редкости Epic Team-up",
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


# ===== КОНЕЦ БЛОКА ЕЖЕНЕДЕЛЬНЫХ КВЕСТОВ =====

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
            CommandHandler("craft", craft_menu),
            CommandHandler("accept_clan_invite", accept_clan_invite),
            CommandHandler("topclans", top_clans),
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
            CallbackQueryHandler(profile_callback, pattern=r"^(achievements_menu|profile_back|achievement_.*)"),
            CallbackQueryHandler(craft_callback, pattern=r"^craft_.*"),
            CallbackQueryHandler(basket_callback, pattern=r"^basket_.*"),
            CallbackQueryHandler(shop_callback, pattern=r"^shop_.*"),
            CallbackQueryHandler(burn_callback, pattern=r"^burn_.*"),
            CallbackQueryHandler(darts_callback, pattern=r"^darts_.*"),
            CallbackQueryHandler(quests_callback, pattern=r"^quests_.*"),
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
