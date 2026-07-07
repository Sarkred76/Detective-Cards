import logging
import json
import asyncio
import random
import time
from typing import Optional, Dict, Any, List
from collections import Counter
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.ext import ContextTypes

# ⭐ ИМПОРТ ФУНКЦИЙ ИЗ MAIN.PY ⭐
# Эти функции будут импортированы в main.py
# Убедитесь что они доступны через импорт

logger = logging.getLogger(__name__)

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (если нужны) =====

def get_card_media_value(card: Dict) -> str:
    """Возвращает правильный источник медиа для карты (file_id или URL)."""
    media_source = card.get("media_source", "url")
    if media_source == "file_id":
        return card.get("file_id", "")
    return card.get("image_url", "")


def is_card_animation(card: Dict, media_value: str) -> bool:
    """Определяет, является ли карта анимацией/видео."""
    if card.get("media_type") == "animation":
        return True
    if isinstance(media_value, str) and media_value.lower().endswith((".mp4", ".webm", ".gif")):
        return True
    return False
    
def find_card_by_id(card_id: int, cards: List[Dict]) -> Optional[Dict]:
    """Находит карточку по ID."""
    for card in cards:
        if card["id"] == card_id:
            return card
    return None


def load_data() -> Dict[str, Any]:
    """Загружает данные из файла."""
    # ⭐ ВАЖНО: Эта функция должна быть в main.py или отдельном utils.py ⭐
    # Для работы трейда нужно импортировать её из main.py
    from main import load_data as main_load_data
    return main_load_data()


def save_data(data: Dict[str, Any]) -> None:
    """Сохраняет данные в файл."""
    # ⭐ ВАЖНО: Эта функция должна быть в main.py или отдельном utils.py ⭐
    from main import save_data as main_save_data
    main_save_data(data)


def is_admin(user_id: str, data: Dict[str, Any]) -> bool:
    """Проверяет, является ли пользователь администратором."""
    from main import is_admin as main_is_admin
    return main_is_admin(user_id, data)


async def trade_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Меню трейда."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            await update.message.reply_text("❌ У вас нет карт для трейда!")
            return
        
        # ⭐ ДОБАВЛЕНЫ КНОПКИ ДЛЯ 2v2, 3v3, 4v4, 5v5 ⭐
        keyboard = [
            [InlineKeyboardButton("1 ↔ 1", callback_data="trade_1v1")],
            [InlineKeyboardButton("2 ↔ 2", callback_data="trade_2v2")],
            [InlineKeyboardButton("3 ↔ 3", callback_data="trade_3v3")],
            [InlineKeyboardButton("4 ↔ 4", callback_data="trade_4v4")],
            [InlineKeyboardButton("5 ↔ 5", callback_data="trade_5v5")],
            [InlineKeyboardButton("❌ Отмена", callback_data="trade_cancel")],
        ]
        
        await update.message.reply_text(
            "🔄 Трейд\n\n"
            "Выберите тип обмена:\n\n"
            "📝 После выбора нужно будет указать игрока и выбрать карты.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в trade_menu: {e}")
        await update.message.reply_text("❌ Ошибка при открытии меню трейда")


async def select_trade_partner(update: Update, context: ContextTypes.DEFAULT_TYPE, trade_type: str) -> None:
    """Запрос ID или @никнейма партнёра."""
    try:
        user_id = str(update.effective_user.id)
        
        # Получаем query из callback_query
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            await query.answer()
            message = query.message
        else:
            message = update.message
        
        # Сохраняем тип трейда во временное хранилище
        context.user_data[user_id] = {
            "trade_type": trade_type,
            "step": "select_partner"
        }
        
        await message.reply_text(
            "👤 Введите @никнейм игрока\n\n"
            "Пример:\n"
            "• @username\n\n",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка select_trade_partner: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Ошибка при выборе партнёра", show_alert=True)
        else:
            await update.message.reply_text("❌ Ошибка при выборе партнёра")


# ... (импорты и вспомогательные функции без изменений) ...

async def process_partner_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка выбора партнёра или поиска карт."""
    try:
        user_id = str(update.effective_user.id)
        text = update.message.text.strip()

        if user_id not in context.user_data:
            return

        trade_info = context.user_data[user_id]
        step = trade_info.get("step", "")

        # 1. Обработка /cancel
        if text.lower() == "/cancel":
            if step == "search_mode":
                # ⭐ ПРИ ОТМЕНЕ ПОИСКА ВОЗВРАЩАЕМ ПОЛНЫЙ СПИСОК ⭐
                trade_info["step"] = trade_info.get("previous_step_before_search", "select_cards")
                if "previous_step_before_search" in trade_info:
                    del trade_info["previous_step_before_search"]
        
                full_card_ids = trade_info.get("full_card_ids", [])
                trade_info["display_card_ids"] = full_card_ids
                # ⭐ Восстанавливаем маппинг ⭐
                trade_info["display_to_full_map"] = {i: i for i in range(len(full_card_ids))}
                trade_info["current_index"] = 0
        
                await update.message.reply_text("❌ Поиск отменён. Показан полный список карт.")
                # ⭐ selected_full_indices НЕ трогаем — выбор сохраняется! ⭐
                await _show_trade_card(update, context, trade_info, full_card_ids, 0)
                return
            elif step == "select_partner":
                del context.user_data[user_id]
                await update.message.reply_text("❌ Трейд отменён")
                return
            else:
                return

        # 2. Если пользователь в режиме поиска
        if step == "search_mode":
            await search_creatures_for_trade(update, context)
            return

        if step != "select_partner":
            return

        # 4. Логика выбора партнера (без изменений)
        partner_id = None
        data = load_data()
        if text.startswith("@"):
            for uid, udata in data["users"].items():
                if udata.get("username") and udata["username"] == text[1:]:
                    partner_id = uid
                    break

            if not partner_id:
                if user_id in context.user_data:
                    del context.user_data[user_id]
                await update.message.reply_text("⚠️ Игрок с таким @никнеймом не найден!\nНачните трейд заново /trade")
                return
        else:
            await update.message.reply_text("⚠️ Введите @никнейм игрока для выбора партнера.")
            return

        if partner_id:
            if partner_id not in data["users"]:
                await update.message.reply_text("⚠️ Игрок не найден!")
                if user_id in context.user_data:
                     del context.user_data[user_id]
                return

            if partner_id == user_id:
                await update.message.reply_text("⚠️ Нельзя трейдиться с самим собой!")
                return

            trade_info["partner_id"] = partner_id
            trade_info["step"] = "select_cards"
            trade_type = trade_info["trade_type"]
            cards_count = int(trade_type.split("v")[0])
            trade_info["cards_count"] = cards_count
            # ⭐ ИСПРАВЛЕНИЕ: Инициализируем с маппингом ⭐
            user_data = data["users"][user_id]
            full_card_ids = user_data.get("cards", [])

            if len(full_card_ids) < cards_count:
                await update.message.reply_text("❌ Недостаточно карт для трейда!")
                del context.user_data[user_id]
                return

            trade_info["full_card_ids"] = full_card_ids
            trade_info["display_card_ids"] = full_card_ids
            # ⭐ Маппинг: индекс в display → индекс в full (при старте они совпадают) ⭐
            trade_info["display_to_full_map"] = {i: i for i in range(len(full_card_ids))}
            trade_info["selected_full_indices"] = []  # ⭐ Индексы в ПОЛНОМ списке ⭐
            trade_info["current_index"] = 0

            await update.message.reply_text(
                f"✅ Партнёр: {partner_id}\n"
                f"🐦‍🔥 Выберите {cards_count} карты для обмена.\n"
                f"Используйте кнопки для навигации:\n"
                f"• [<] [>] - листать карты\n"
                f"• [✅ Выбрать] - добавить карту\n"
                f"• [🔍 Поиск] - найти по названию\n"
                f"• [➡️ Далее] - завершить выбор",
                parse_mode="Markdown"
            )

            # ⭐ ПОКАЗЫВАЕМ ПЕРВУЮ КАРТУ ⭐
            await _show_trade_card(update, context, trade_info, full_card_ids, 0)

    except Exception as e:
        logger.error(f"Ошибка process_partner_selection: {e}")
        try:
             await update.message.reply_text("❌ Ошибка при обработке вашего запроса.")
        except:
             pass
        try:
             user_id = str(update.effective_user.id)
             if user_id in context.user_data:
                  del context.user_data[user_id]
        except:
             pass


async def _show_trade_card(update_or_query, context, trade_info, display_card_ids, index):
    """
    ⭐ УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ОТОБРАЖЕНИЯ КАРТЫ ДЛЯ ТРЕЙДА ⭐
    Поддерживает дубликаты карт, поиск и file_id.
    """
    if not display_card_ids:
        if hasattr(update_or_query, 'message'):
            await update_or_query.message.reply_text("❌ Карты не найдены!")
        return

    # Корректировка индекса
    index = max(0, min(index, len(display_card_ids) - 1))
    trade_info["current_index"] = index
    
    card_id = display_card_ids[index]
    data = load_data()
    card = find_card_by_id(card_id, data["cards"])
    
    if not card:
        return

    user_id = str(trade_info.get("user_id", ""))
    if not user_id and hasattr(update_or_query, 'from_user'):
        user_id = str(update_or_query.from_user.id)
        
    user_data = data["users"].get(user_id, {})
    all_user_cards = user_data.get("cards", [])
    
    # ⭐ Считаем количество в архиве (по полному списку) ⭐
    card_counts = Counter(all_user_cards)
    card_in_collection = card_counts.get(card["id"], 1)
    
    # ⭐ Используем индексы в ПОЛНОМ списке ⭐
    selected_full_indices = trade_info.get("selected_full_indices", [])
    cards_count = trade_info.get("cards_count", 1)
    
    caption = (
        f"{card['title']}\n"
        f"Редкость: {card['rarity']}\n"
        f"🛡 В архиве: {card_in_collection} шт.\n\n"
        f"{len(selected_full_indices)}/{cards_count} выбрано"
    )
    
    # ⭐ Проверяем по индексу в полном списке ⭐
    display_to_full_map = trade_info.get("display_to_full_map", {})
    full_index = display_to_full_map.get(index, index)
    is_selected = full_index in selected_full_indices
    select_text = "❌ Убрать" if is_selected else "✅ Выбрать"
    
    # Определяем префикс кнопок
    step = trade_info.get("step", "select_cards")
    
    if step == "select_return_cards":
        button_prefix = "trade_return_"
        search_callback = "trade_return_search_button"
        finish_callback = "trade_return_finish"
    else:
        button_prefix = "trade_"
        search_callback = "trade_open_search"
        finish_callback = "trade_finish_select"
    
    keyboard = [
        [
            InlineKeyboardButton("<", callback_data=f"{button_prefix}prev_{index}"),
            InlineKeyboardButton(select_text, callback_data=f"{button_prefix}select_{index}"),
            InlineKeyboardButton(">", callback_data=f"{button_prefix}next_{index}"),
        ],
        [InlineKeyboardButton("➡️ Далее", callback_data=finish_callback)],
        [InlineKeyboardButton("🔍 Поиск", callback_data=search_callback)],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ⭐ НОВОЕ: Универсальная логика для file_id и URL ⭐
    media_value = get_card_media_value(card)
    is_animation = is_card_animation(card, media_value)
    
    # Отправка или редактирование сообщения
    if hasattr(update_or_query, 'edit_message_media'):
        try:
            if is_animation:
                media = InputMediaAnimation(media=media_value, caption=caption)
            else:
                media = InputMediaPhoto(media=media_value, caption=caption)
            await update_or_query.edit_message_media(media=media, reply_markup=reply_markup)
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Ошибка редактирования в _show_trade_card: {e}")
    elif hasattr(update_or_query, 'message'):
        try:
            if is_animation:
                await update_or_query.message.reply_animation(
                    animation=media_value,
                    caption=caption,
                    reply_markup=reply_markup
                )
            else:
                await update_or_query.message.reply_photo(
                    photo=media_value,
                    caption=caption,
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.error(f"Ошибка отправки в _show_trade_card: {e}")

async def search_creatures_for_trade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    ⭐ ПОИСК С ПОДДЕРЖКОЙ ДУБЛИКАТОВ ⭐
    Фильтрует список, сохраняя маппинг индексов.
    """
    try:
        user_id = str(update.effective_user.id)
        text = update.message.text.strip()
        
        if user_id not in context.user_data:
            await update.message.reply_text("❌ Вы не находитесь в режиме трейда!\nНачните с команды /trade")
            return
        
        trade_info = context.user_data[user_id]
        step = trade_info.get("step", "")
        if step not in ["select_cards", "select_return_cards", "search_mode"]:
            await update.message.reply_text(f"❌ Невозможно выполнить поиск. Текущий шаг трейда: '{step}'.")
            return
        
        data = load_data()
        user_data = data["users"].get(user_id)
        if not user_data or not user_data.get("cards"):
            await update.message.reply_text("❌ У вас нет карт для трейда!")
            return
        
        search_query = text.lower()
        full_card_ids = trade_info.get("full_card_ids", user_data["cards"])
        
        # ⭐ ФИЛЬТРУЕМ, СОХРАНЯЯ МАППИНГ ИНДЕКСОВ ⭐
        filtered_ids = []
        display_to_full_map = {}
        
        for full_index, card_id in enumerate(full_card_ids):
            card = find_card_by_id(card_id, data["cards"])
            if card and search_query in card["title"].lower():
                display_index = len(filtered_ids)
                filtered_ids.append(card_id)
                display_to_full_map[display_index] = full_index
        
        if not filtered_ids:
            await update.message.reply_text(
                f"❌ Карт с названием \"{text}\" не найдено!\n"
                "Попробуйте другой запрос или нажмите /cancel для возврата."
            )
            return
        
        # ⭐ ОБНОВЛЯЕМ СЕССИЮ ⭐
        trade_info["display_card_ids"] = filtered_ids
        trade_info["display_to_full_map"] = display_to_full_map
        trade_info["current_index"] = 0
        
        # Возвращаемся к шагу выбора
        prev_step = trade_info.get("previous_step_before_search", "select_cards")
        trade_info["step"] = prev_step
        if "previous_step_before_search" in trade_info:
            del trade_info["previous_step_before_search"]
        
        await update.message.reply_text(
            f"🔍 Найдено карт: {len(filtered_ids)}\n"
            f"По запросу: \"{text}\"\n\n"
            f"Выберите карту кнопками ниже:"
        )
        
        # ⭐ ПОКАЗЫВАЕМ ПЕРВУЮ НАЙДЕННУЮ КАРТУ ⭐
        await _show_trade_card(update, context, trade_info, filtered_ids, 0)
        
    except Exception as e:
        logger.error(f"Ошибка search_creatures_for_trade: {e}")
        await update.message.reply_text("❌ Ошибка при поиске карт")

async def trade_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок из результатов поиска."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)

        if user_id not in context.user_data:
            await query.edit_message_text(text="❌ Сессия трейда истекла!")
            return

        trade_info = context.user_data[user_id]

        # --- Обработка отмены поиска ---
        if query.data == "trade_search_cancel":
            prev_step = trade_info.get("previous_step_before_search", "select_cards")
            if prev_step not in ["select_cards", "select_return_cards"]:
                prev_step = "select_cards"

            trade_info["step"] = prev_step
            if "previous_step_before_search" in trade_info:
                del trade_info["previous_step_before_search"]

            # Удаляем сообщение поиска
            try:
                await query.message.delete()
            except:
                pass

            # Возвращаем ПОЛНЫЙ список карт
            data = load_data()
            user_data = data["users"].get(user_id)
            full_card_ids = user_data.get("cards", []) if user_data else []
            trade_info["user_card_ids"] = full_card_ids
            trade_info["current_index"] = 0

            await query.message.reply_text("❌ Поиск отменён. Показан полный список карт.")
            
            # Показываем первую карту через универсальную функцию
            # (если вы её добавили) или дублируем логику отображения
            if full_card_ids:
                card = find_card_by_id(full_card_ids[0], data["cards"])
                if card:
                    card_counts = Counter(full_card_ids)
                    caption = (
                        f"{card['title']}\n"
                        f"Редкость: {card['rarity']}\n"
                        f"🛡 В архиве: {card_counts.get(card['id'], 1)} шт.\n\n"
                        f"0/{trade_info.get('cards_count', 1)} выбрано"
                    )
                    button_prefix = "trade_return_" if prev_step == "select_return_cards" else "trade_"
                    keyboard = [
                        [
                            InlineKeyboardButton("<", callback_data=f"{button_prefix}prev_0"),
                            InlineKeyboardButton("✅ Выбрать", callback_data=f"{button_prefix}select_0"),
                            InlineKeyboardButton(">", callback_data=f"{button_prefix}next_0"),
                        ],
                        [InlineKeyboardButton("➡️ Далее", callback_data=f"{button_prefix}finish")],
                        [InlineKeyboardButton("🔍 Поиск", callback_data=f"{button_prefix}search_button")],
                    ]
                    # ⭐ НОВОЕ: Универсальная логика ⭐
                    media_value = get_card_media_value(card)
                    is_animation = is_card_animation(card, media_value)

                    try:
                        if is_animation:
                            await context.bot.send_animation(
                                chat_id=query.message.chat_id,
                                animation=media_value,
                                caption=caption,
                                reply_markup=InlineKeyboardMarkup(keyboard)
                            )
                        else:
                            await context.bot.send_photo(
                                chat_id=query.message.chat_id,
                                photo=media_value,
                                caption=caption,
                                reply_markup=InlineKeyboardMarkup(keyboard)
                            )
                    except Exception as e:
                        logger.error(f"Ошибка отправки после отмены поиска: {e}")
            return

        # Если вдруг пришла старая кнопка выбора из поиска — игнорируем
        # (выбор теперь идёт через обычные кнопки навигации)
        if query.data.startswith("trade_search_select_"):
            await query.answer("⚠️ Используйте кнопки навигации для выбора", show_alert=True)
            return

    except Exception as e:
        logger.error(f"Ошибка trade_search_callback: {e}")
        try:
            await query.answer("❌ Ошибка при обработке поиска", show_alert=True)
        except:
            pass


async def trade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок трейда (отправитель)."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        
        if query.data in ["trade_1v1", "trade_2v2", "trade_3v3", "trade_4v4", "trade_5v5"]:
            trade_type = query.data.split("_")[1]
            await select_trade_partner(update, context, trade_type)
            return
        
        if query.data == "trade_cancel":
            if user_id in context.user_data:
                del context.user_data[user_id]
            await query.edit_message_text("❌ Трейд отменён")
            return
        
        if user_id not in context.user_data:
            await query.edit_message_text("❌ Сессия трейда истекла!")
            return
        
        trade_info = context.user_data[user_id]
        # ⭐ ДОБАВЛЯЕМ user_id В trade_info ДЛЯ _show_trade_card ⭐
        trade_info["user_id"] = user_id
        
        user_card_ids = trade_info.get("user_card_ids", [])
        
        # Навигация
        if query.data.startswith("trade_prev_") or query.data.startswith("trade_next_"):
            action = "prev" if "prev" in query.data else "next"
            current_index = trade_info.get("current_index", 0)

            display_card_ids = trade_info.get("display_card_ids", [])
            
            if not display_card_ids:
                await query.answer("❌ Карты не найдены!", show_alert=True)
                return
            
            if action == "prev":
                current_index = (current_index - 1) % len(display_card_ids)
            else:
                current_index = (current_index + 1) % len(display_card_ids)
            
            # ⭐ ИСПОЛЬЗУЕМ ОБЩУЮ ФУНКЦИЮ ⭐
            await _show_trade_card(query, context, trade_info, display_card_ids, current_index)
        
        # Выбор карты
        elif query.data.startswith("trade_select_"):
            display_index = int(query.data.split("_")[-1])
    
            # ⭐ ИСПРАВЛЕНИЕ: Работаем с индексами в полном списке ⭐
            selected_full_indices = trade_info.get("selected_full_indices", [])
            cards_count = trade_info.get("cards_count", 1)
            display_to_full_map = trade_info.get("display_to_full_map", {})
    
            # Получаем индекс в полном списке
            full_index = display_to_full_map.get(display_index, display_index)
    
            if full_index in selected_full_indices:
                # Убираем карту
                selected_full_indices.remove(full_index)
            else:
                # Добавляем карту
                if len(selected_full_indices) >= cards_count:
                    await query.answer("❌ Максимум карт выбрано!", show_alert=True)
                    return
                selected_full_indices.append(full_index)
    
            trade_info["selected_full_indices"] = selected_full_indices
    
            # ⭐ ИСПОЛЬЗУЕМ ОБЩУЮ ФУНКЦИЮ ⭐
            current_index = trade_info.get("current_index", 0)
            display_card_ids = trade_info.get("display_card_ids", [])
            await _show_trade_card(query, context, trade_info, display_card_ids, current_index)
        
        elif query.data == "trade_open_search":
            trade_info["previous_step_before_search"] = trade_info["step"]
            trade_info["step"] = "search_mode"
            await query.answer("🔍 Введите название карты для поиска", show_alert=False)
            await query.message.reply_text(
                "🔍 Поиск карт\n"
                "Введите часть названия:\n"
                "❌ Для отмены: /cancel",
                parse_mode="Markdown"
            )
            return
        
        elif query.data == "trade_finish_select":
            # ⭐ ИСПРАВЛЕНИЕ: Используем selected_full_indices ⭐
            selected_full_indices = trade_info.get("selected_full_indices", [])
            cards_count = trade_info.get("cards_count", 1)
            partner_id = trade_info["partner_id"]
            full_card_ids = trade_info.get("full_card_ids", [])
    
            if len(selected_full_indices) != cards_count:
                await query.answer(f"❌ Выберите ровно {cards_count} карт!", show_alert=True)
                return
    
            # ⭐ Получаем ID карт по индексам ⭐
            selected_card_ids = [full_card_ids[i] for i in selected_full_indices]
    
            trade_info["step"] = "confirm"
            trade_info["selected_card_ids"] = selected_card_ids
    
            try:
                await query.message.delete()
            except:
                pass
    
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(
                    f"✅ Вы выбрали {cards_count} карт\n\n"
                    f"👤 Партнёр: {trade_info['partner_id']}\n\n"
                    f"📩 Отправляю запрос на обмен..."
                ),
                parse_mode="Markdown"
            )
    
            data = load_data()
            data["active_trades"][partner_id] = {
                "from_user": user_id,
                "cards_offered": selected_card_ids,
                "trade_type": trade_info["trade_type"],
                "timestamp": int(time.time())
            }
            save_data(data)

            logger.info(f"Трейд сохранён в файл: {user_id} → {partner_id}")

            context.user_data[user_id] = {
                "step": "waiting_for_receiver_response",
                "trade_partner": partner_id,
                "selected_card_ids": selected_card_ids,
            }

            try:
                sender_data = data["users"].get(user_id, {})
                sender_name = sender_data.get("first_name", "Игрок")
                if sender_data.get("last_name"):
                    sender_name += f" {sender_data['last_name']}"
                if sender_data.get("username"):
                    sender_name = f"@{sender_data['username']}"

                cards_info = []
                for card_id in selected_card_ids:
                    card = find_card_by_id(card_id, data["cards"])
                    if card:
                        cards_info.append(f"• {card['title']} ({card['rarity']})")

                cards_text = "\n".join(cards_info) if cards_info else "Нет карт"

                keyboard = [
                    [
                        InlineKeyboardButton("✅ Принять", callback_data=f"trade_accept_btn_{user_id}"),
                        InlineKeyboardButton("❌ Отклонить", callback_data=f"trade_decline_btn_{user_id}"),
                    ]
                ]

                await context.bot.send_message(
                    chat_id=partner_id,
                    text=(
                        f"🔄 Вам предложили обмен!\n\n"
                        f"👤 От: {sender_name}\n"
                        f"🐦‍🔥 Карт в обмене: {cards_count}\n\n"
                        f"📋 Карты отправителя:\n"
                        f"{cards_text}\n\n"
                        f"Нажмите кнопку для действия:"
                    ),
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML"
                )
            except Exception as notify_error:
                logger.error(f"Не удалось уведомить партнёра: {notify_error}")
                await query.message.reply_text("⚠️ Не удалось уведомить игрока")
    
    except Exception as e:
        logger.error(f"Ошибка trade_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def trade_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок Принять/Отклонить трейд."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        
        # ⭐ ЧИТАЕМ ТРЕЙД ИЗ ФАЙЛА ⭐
        data = load_data()
        
        if user_id not in data.get("active_trades", {}):
            logger.warning(f"Трейд не найден для пользователя {user_id}")
            await query.edit_message_text("❌ Трейд не найден или истёк!")
            return
        
        trade_info = data["active_trades"][user_id]
        from_user = trade_info["from_user"]
        cards_offered = trade_info["cards_offered"]
        
        logger.info(f"trade_button_callback: {user_id} принимает трейд от {from_user}")
        
        # Принятие трейда
        if query.data.startswith("trade_accept_btn_"):
            # Проверяем, что отправитель существует
            if from_user not in data["users"]:
                del data["active_trades"][user_id]
                save_data(data)
                await query.edit_message_text("❌ Игрок, который отправил трейд, больше не существует!")
                return
            
            # Проверяем, что карты ещё существуют у отправителя
            if not cards_offered:
                del data["active_trades"][user_id]
                save_data(data)
                await query.edit_message_text("❌ Карты для обмена больше не доступны!")
                return
            
            # Получаем имя отправителя
            sender_data = data["users"].get(from_user, {})
            sender_name = sender_data.get("first_name", "Игрок")
            if sender_data.get("last_name"):
                sender_name += f" {sender_data['last_name']}"
            
            # ⭐ СОХРАНЯЕМ ВРЕМЕННО В context.user_data ДЛЯ НАВИГАЦИИ ⭐
            context.user_data[user_id] = {
                "step": "view_offered_cards",
                "trade_partner": from_user,
                "received_cards": cards_offered,
                "current_offer_index": 0
            }
            
            # Удаляем трейд из активных (чтобы не принять дважды)
            del data["active_trades"][user_id]
            save_data(data)
            
            await query.edit_message_text(
                f"✅ Запрос принят от {sender_name}\n\n"
                f"🐦‍🔥 Карт в обмене: {len(cards_offered)}\n\n"
                f"📋 Просмотрите карты ниже:\n"
                f"Используйте [<] [>] для навигации",
                parse_mode="Markdown"
            )
            
            # Показываем первую карту
            card = find_card_by_id(cards_offered[0], data["cards"])
            if card:
                card_counts = Counter(cards_offered)
                card_in_offer = card_counts.get(card["id"], 1)
                
                caption = (
                    f"{card['title']}\n"
                    f"Редкость: {card['rarity']}\n"
                    f"📦 В предложении: {card_in_offer} шт.\n\n"
                    f"1/{len(cards_offered)}"
                )
                
                keyboard = []
                nav_buttons = []
                
                if len(cards_offered) > 1:
                    nav_buttons.append(
                        InlineKeyboardButton("<", callback_data="trade_offer_prev_0")
                    )
                
                nav_buttons.append(
                    InlineKeyboardButton(
                        f"1/{len(cards_offered)}",
                        callback_data="trade_offer_info"
                    )
                )
                
                if len(cards_offered) > 1:
                    nav_buttons.append(
                        InlineKeyboardButton(">", callback_data="trade_offer_next_0")
                    )
                
                keyboard.append(nav_buttons)
                keyboard.append([
                    InlineKeyboardButton("✅ Принять обмен", callback_data="trade_offer_accept"),
                    InlineKeyboardButton("❌ Отклонить", callback_data="trade_offer_decline"),
                ])
                
                # ⭐ НОВОЕ: Универсальная логика ⭐
                media_value = get_card_media_value(card)
                is_animation = is_card_animation(card, media_value)

                try:
                    if is_animation:
                        await context.bot.send_animation(
                            chat_id=query.message.chat_id,
                            animation=media_value,
                            caption=caption,
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    else:
                        await context.bot.send_photo(
                            chat_id=query.message.chat_id,
                            photo=media_value,
                            caption=caption,
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                except Exception as e:
                    logger.error(f"Ошибка отправки карты предложения: {e}")
        
        # Отклонение трейда
        elif query.data.startswith("trade_decline_btn_"):
            del data["active_trades"][user_id]
            save_data(data)
            
            await query.edit_message_text("❌ Трейд отклонён")
            
            # Уведомляем отправителя
            try:
                await context.bot.send_message(
                    chat_id=from_user,
                    text=f"❌ Игрок отклонил ваш запрос на обмен."
                )
            except:
                pass
        
    except Exception as e:
        logger.error(f"Ошибка trade_button_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def trade_offer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок просмотра карт предложения."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        
        # Читаем из context.user_data (туда сохранили после принятия)
        if user_id not in context.user_data:
            await query.edit_message_text("❌ Сессия трейда истекла!")
            return
        
        trade_info = context.user_data[user_id]
        if trade_info.get("step") != "view_offered_cards":
            return
        
        cards_offered = trade_info.get("received_cards", [])
        if not cards_offered:
            await query.answer("❌ Карты не найдены!", show_alert=True)
            return
        
        # Навигация
        if query.data.startswith("trade_offer_prev_") or query.data.startswith("trade_offer_next_"):
            action = "prev" if "prev" in query.data else "next"
            current_index = trade_info.get("current_offer_index", 0)
            
            if action == "prev":
                current_index = (current_index - 1) % len(cards_offered)
            else:
                current_index = (current_index + 1) % len(cards_offered)
            
            trade_info["current_offer_index"] = current_index
            
            card = find_card_by_id(cards_offered[current_index], data["cards"])
            if card:
                card_counts = Counter(cards_offered)
                card_in_offer = card_counts.get(card["id"], 1)
                
                caption = (
                    f"{card['title']}\n"
                    f"Редкость: {card['rarity']}\n"
                    f"📦 В предложении: {card_in_offer} шт.\n\n"
                    f"{current_index + 1}/{len(cards_offered)}"
                )
                
                keyboard = []
                nav_buttons = []
                
                if len(cards_offered) > 1:
                    nav_buttons.append(
                        InlineKeyboardButton("<", callback_data=f"trade_offer_prev_{current_index}")
                    )
                
                nav_buttons.append(
                    InlineKeyboardButton(
                        f"{current_index + 1}/{len(cards_offered)}",
                        callback_data="trade_offer_info"
                    )
                )
                
                if len(cards_offered) > 1:
                    nav_buttons.append(
                        InlineKeyboardButton(">", callback_data=f"trade_offer_next_{current_index}")
                    )
                
                keyboard.append(nav_buttons)
                keyboard.append([
                    InlineKeyboardButton("✅ Принять обмен", callback_data="trade_offer_accept"),
                    InlineKeyboardButton("❌ Отклонить", callback_data="trade_offer_decline"),
                ])
                
                # ⭐ НОВОЕ: Универсальная логика ⭐
                media_value = get_card_media_value(card)
                is_animation = is_card_animation(card, media_value)

                try:
                    if is_animation:
                        media = InputMediaAnimation(media=media_value, caption=caption)
                    else:
                        media = InputMediaPhoto(media=media_value, caption=caption)
                    await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
                except Exception as e:
                    if "Message is not modified" not in str(e):
                        logger.error(f"Ошибка редактирования в trade_offer_callback: {e}")
        
        # Принятие обмена
        elif query.data == "trade_offer_accept":
            # Переходим к выбору своих карт
            context.user_data[user_id]["step"] = "select_return_cards"
            from_user = trade_info.get("trade_partner")
            cards_count = len(cards_offered)
    
            await query.message.reply_text(
                f"✅ Запрос принят!\n\n"
                f"🐦‍🔥 Теперь выберите {cards_count} карты для обмена\n\n"
                "Используйте кнопки для выбора...",
                parse_mode="Markdown"
            )
    
            # Показываем карты пользователя для выбора
            user_data = data["users"][user_id]
            full_card_ids = user_data.get("cards", [])
    
            if len(full_card_ids) < cards_count:
                await query.message.reply_text(
                    f"❌ Недостаточно карт для трейда!\n"
                    f"У вас: {len(full_card_ids)} карт, нужно: {cards_count}"
                )
                if "incoming_trade" in context.user_data.get(user_id, {}):
                    del context.user_data[user_id]["incoming_trade"]
                return
    
            # ⭐ ИСПРАВЛЕНИЕ: Инициализируем с маппингом ⭐
            context.user_data[user_id]["full_card_ids"] = full_card_ids
            context.user_data[user_id]["display_card_ids"] = full_card_ids
            context.user_data[user_id]["display_to_full_map"] = {i: i for i in range(len(full_card_ids))}
            context.user_data[user_id]["cards_count"] = cards_count
            context.user_data[user_id]["selected_full_indices"] = []  # ⭐ Индексы в полном списке ⭐
            context.user_data[user_id]["current_index"] = 0
    
            # Показываем первую карту
            if not full_card_ids:
                await query.message.reply_text("❌ У вас нет карт!")
                return
    
            card = find_card_by_id(full_card_ids[0], data["cards"])
            if card:
                caption = f"{card['title']}\nРедкость: {card['rarity']}\n\n0/{cards_count} выбрано"
                keyboard = [
                    [
                        InlineKeyboardButton("<", callback_data="trade_return_prev_0"),
                        InlineKeyboardButton("✅ Выбрать", callback_data="trade_return_select_0"),
                        InlineKeyboardButton(">", callback_data="trade_return_next_0"),
                    ],
                    [InlineKeyboardButton("➡️ Отправить встречное предложение", callback_data="trade_return_finish")],
                ]
                # ⭐ НОВОЕ: Универсальная логика ⭐
                media_value = get_card_media_value(card)
                is_animation = is_card_animation(card, media_value)

                try:
                    if is_animation:
                        await query.message.reply_animation(
                            animation=media_value,
                            caption=caption,
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    else:
                        await query.message.reply_photo(
                            photo=media_value,
                            caption=caption,
                        reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                except Exception as e:
                    logger.error(f"Ошибка отправки первой карты: {e}")
        
        # Отклонение обмена
        elif query.data == "trade_offer_decline":
            if "incoming_trade" in context.user_data.get(user_id, {}):
                trade_info = context.user_data[user_id]["incoming_trade"]
                from_user = trade_info["from_user"]
                
                del context.user_data[user_id]["incoming_trade"]
                
                await query.edit_message_text("❌ Трейд отклонён")
                
                # Уведомляем отправителя
                try:
                    await context.bot.send_message(
                        chat_id=from_user,
                        text=f"❌ Игрок отклонил ваш запрос на обмен."
                    )
                except:
                    pass
        
    except Exception as e:
        logger.error(f"Ошибка trade_offer_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def trade_return_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок выбора карт для ответного трейда."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)  # Это ПОЛУЧАТЕЛЬ (Игрок Б)
        if user_id not in context.user_data:
            await query.edit_message_text("❌ Сессия трейда истекла!")
            return
        trade_info = context.user_data[user_id]
        if trade_info.get("step") != "select_return_cards":
            await query.edit_message_text("❌ Сессия выбора карт истекла!")
            return
        data = load_data()
        display_card_ids = trade_info.get("display_card_ids", [])
        
        # Навигация
        if query.data.startswith("trade_return_prev_") or query.data.startswith("trade_return_next_"):
            action = "prev" if "prev" in query.data else "next"
            current_index = trade_info.get("current_index", 0)
            if not display_card_ids:
                await query.answer("❌ Карты не найдены!", show_alert=True)
                return
            if action == "prev":
                current_index = (current_index - 1) % len(display_card_ids)
            else:
                current_index = (current_index + 1) % len(display_card_ids)
            trade_info["current_index"] = current_index
            card = find_card_by_id(display_card_ids[current_index], data["cards"])
            if card:
                selected_count = len(trade_info.get("selected_full_indices", []))
                cards_count = trade_info.get("cards_count", 1)
                card_counts = Counter(trade_info.get("full_card_ids", []))
                card_in_collection = card_counts.get(card["id"], 1)
                caption = (
                    f"{card['title']}\n"
                    f"Редкость: {card['rarity']}\n"
                    f"🛡 В архиве: {card_in_collection} шт.\n"
                    f"{selected_count}/{cards_count} выбрано"
                )
                # ⭐ ИСПРАВЛЕНИЕ: Проверяем по индексу в полном списке ⭐
                display_to_full_map = trade_info.get("display_to_full_map", {})
                full_index = display_to_full_map.get(current_index, current_index)
                is_selected = full_index in trade_info.get("selected_full_indices", [])
                select_text = "❌ Убрать" if is_selected else "✅ Выбрать"
                keyboard = [
                    [
                        InlineKeyboardButton("<", callback_data=f"trade_return_prev_{current_index}"),
                        InlineKeyboardButton(select_text, callback_data=f"trade_return_select_{current_index}"),
                        InlineKeyboardButton(">", callback_data=f"trade_return_next_{current_index}"),
                    ],
                    [InlineKeyboardButton("➡️ Далее", callback_data="trade_return_finish")],
                    [InlineKeyboardButton("🔍 Поиск", callback_data="trade_return_search_button")],
                ]
                # ⭐ НОВОЕ: Универсальная логика ⭐
                media_value = get_card_media_value(card)
                is_animation = is_card_animation(card, media_value)

                try:
                    if is_animation:
                        media = InputMediaAnimation(media=media_value, caption=caption)
                    else:
                        media = InputMediaPhoto(media=media_value, caption=caption)
                    await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
                except Exception as e:
                    if "Message is not modified" not in str(e):
                        logger.error(f"Ошибка редактирования в trade_return_callback: {e}")
        # Выбор карты
        elif query.data.startswith("trade_return_select_"):
            display_index = int(query.data.split("_")[-1])
    
            # ⭐ ИСПРАВЛЕНИЕ: Работаем с индексами в полном списке ⭐
            selected_full_indices = trade_info.get("selected_full_indices", [])
            cards_count = trade_info.get("cards_count", 1)
            display_to_full_map = trade_info.get("display_to_full_map", {})
    
            # Получаем индекс в полном списке
            full_index = display_to_full_map.get(display_index, display_index)
    
            if full_index in selected_full_indices:
                # Убираем карту
                selected_full_indices.remove(full_index)
            else:
                # Добавляем карту
                if len(selected_full_indices) >= cards_count:
                    await query.answer("❌ Максимум карт выбрано!", show_alert=True)
                    return
                selected_full_indices.append(full_index)
    
            trade_info["selected_full_indices"] = selected_full_indices
    
            current_index = trade_info.get("current_index", 0)
            display_card_ids = trade_info.get("display_card_ids", [])
    
            card_id = display_card_ids[current_index]
            card = find_card_by_id(card_id, data["cards"])
            if card:
                card_counts = Counter(trade_info.get("full_card_ids", []))
                card_in_collection = card_counts.get(card["id"], 1)
                caption = (
                    f"{card['title']}\n"
                    f"Редкость: {card['rarity']}\n"
                    f"🛡 В архиве: {card_in_collection} шт.\n"
                    f"{len(selected_full_indices)}/{cards_count} выбрано"
                )
                is_selected = full_index in selected_full_indices
                select_text = "❌ Убрать" if is_selected else "✅ Выбрать"
                keyboard = [
                    [
                        InlineKeyboardButton("<", callback_data=f"trade_return_prev_{current_index}"),
                        InlineKeyboardButton(select_text, callback_data=f"trade_return_select_{current_index}"),
                        InlineKeyboardButton(">", callback_data=f"trade_return_next_{current_index}"),
                    ],
                    [InlineKeyboardButton("➡️ Далее", callback_data="trade_return_finish")],
                    [InlineKeyboardButton("🔍 Поиск", callback_data="trade_return_search_button")],
                ]
                # ⭐ НОВОЕ: Универсальная логика ⭐
                media_value = get_card_media_value(card)
                is_animation = is_card_animation(card, media_value)

                try:
                    if is_animation:
                        media = InputMediaAnimation(media=media_value, caption=caption)
                    else:
                        media = InputMediaPhoto(media=media_value, caption=caption)
                    await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
                except Exception as e:
                    if "Message is not modified" not in str(e):
                        logger.error(f"Ошибка редактирования при выборе: {e}")
        
        elif query.data == "trade_return_search_button":
            # КНОПКА ПОИСКА В ИНТЕРФЕЙСЕ ВЫБОРА КАРТ ПОЛУЧАТЕЛЯ
            if user_id in context.user_data:
                trade_info = context.user_data[user_id]
                # СОХРАНЯЕМ ТЕКУЩИЙ ШАГ ПЕРЕД ПЕРЕХОДОМ К ПОИСКУ
                trade_info["previous_step_before_search"] = trade_info["step"]
                trade_info["step"] = "search_mode"
            await query.answer("🔍 Введите название карты для поиска", show_alert=False)
            await query.message.reply_text(
                "🔍 Поиск карт\n"
                "❌ Для отмены: /cancel",
                parse_mode="Markdown"
            )
            return
        # ⭐ ЗАВЕРШЕНИЕ ВЫБОРА КАРТ ⭐
        elif query.data == "trade_return_finish":
            # ⭐ ИСПРАВЛЕНИЕ: Используем selected_full_indices ⭐
            selected_full_indices = trade_info.get("selected_full_indices", [])
            cards_count = trade_info.get("cards_count", 1)
            full_card_ids = trade_info.get("full_card_ids", [])
    
            if len(selected_full_indices) != cards_count:
                await query.answer(f"❌ Выберите ровно {cards_count} карт!", show_alert=True)
                return
    
            # ⭐ Получаем ID карт по индексам ⭐
            selected_card_ids = [full_card_ids[i] for i in selected_full_indices]
    
            received_cards = trade_info.get("received_cards", [])  # Карты от отправителя
            partner_id = trade_info.get("trade_partner")  # ID отправителя (Игрок А)
    
            # ⭐ СОХРАНЯЕМ В ФАЙЛ ⭐
            data = load_data()
            data["active_trades"][partner_id] = {
                "from_user": partner_id,
                "receiver_id": user_id,
                "sender_cards": received_cards,
                "receiver_cards": selected_card_ids,
                "step": "waiting_sender_confirm",
                "timestamp": int(time.time())
            }
            save_data(data)
    
            # ⭐ Очищаем context.user_data Получателя ⭐
            if user_id in context.user_data:
                del context.user_data[user_id]
    
            # Отправляем уведомление отправителю (Игрок А)
            try:
                sender_data = data["users"].get(user_id, {})
                sender_name = sender_data.get("first_name", "Игрок")
                if sender_data.get("last_name"):
                    sender_name += f" {sender_data['last_name']}"
        
                # Информация о картах получателя
                return_cards_info = []
                for card_id in selected_card_ids:
                    card = find_card_by_id(card_id, data["cards"])
                    if card:
                        return_cards_info.append(f"• {card['title']} ({card['rarity']})")
                return_cards_text = "\n".join(return_cards_info) if return_cards_info else "Нет карт"
        
                # Информация о картах отправителя (что он получит)
                offered_cards_info = []
                for card_id in received_cards:
                    card = find_card_by_id(card_id, data["cards"])
                    if card:
                        offered_cards_info.append(f"• {card['title']} ({card['rarity']})")
                offered_cards_text = "\n".join(offered_cards_info) if offered_cards_info else "Нет карт"
        
                # Инлайн-кнопки для подтверждения
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Подтвердить обмен", callback_data=f"trade_final_confirm_{user_id}"),
                        InlineKeyboardButton("❌ Отменить", callback_data=f"trade_final_decline_{user_id}"),
                    ]
                ]
        
                await context.bot.send_message(
                    chat_id=partner_id,
                    text=(
                        f"🔄 Игрок готов к обмену!\n"
                        f"👤 {sender_name} предлагает:\n"
                        f"{return_cards_text}\n"
                        f"📋 Ваше предложение:\n"
                        f"{offered_cards_text}\n"
                        f"Нажмите кнопку для подтверждения:"
                    ),
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
        
                try:
                    await query.message.delete()
                except:
                    pass
                await query.message.reply_text(
                    "✅ Ваш ответ отправлен!\n"
                    "⏳ Ожидайте подтверждения от отправителя..."
                )
            except Exception as notify_error:
                logger.error(f"Не удалось уведомить отправителя: {notify_error}")
                await query.answer("❌ Ошибка при отправке подтверждения", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка trade_return_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


async def trade_final_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик финального подтверждения трейда."""
    try:
        from main import update_quest_progress
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)  # Это ОТПРАВИТЕЛЬ (Игрок А)
        data = load_data()
        # ⭐ ЧИТАЕМ ИЗ ФАЙЛА ВМЕСТО context.user_data ⭐
        if user_id not in data.get("active_trades", {}):
            await query.edit_message_text("❌ Трейд не найден или истёк!")
            return
        trade_info = data["active_trades"][user_id]
        # Проверяем шаг
        if trade_info.get("step") != "waiting_sender_confirm":
            await query.edit_message_text("❌ Трейд не ожидает подтверждения!")
            return
        partner_id = trade_info.get("receiver_id") or trade_info.get("from_user")  # ID получателя (Игрок Б)
        received_cards = trade_info.get("sender_cards", [])  # Карты, которые отправитель предлагает
        selected_return_cards = trade_info.get("receiver_cards", [])  # Карты, которые выбрал получатель
        # Подтверждение обмена
        if query.data.startswith("trade_final_confirm_"):
            if not selected_return_cards:
                await query.edit_message_text("❌ Ошибка: карты партнёра не найдены!")
                return
            # Выполняем обмен
            user_data = data["users"][user_id]
            partner_data = data["users"][partner_id]
            # Удаляем карты у отправителя
            for card_id in received_cards:
                if card_id in user_data["cards"]:
                    user_data["cards"].remove(card_id)
            # Добавляем карты от получателя отправителю
            user_data["cards"].extend(selected_return_cards)
            # Удаляем карты у получателя
            for card_id in selected_return_cards:
                if card_id in partner_data["cards"]:
                    partner_data["cards"].remove(card_id)
            # Добавляем карты от отправителя получателю
            partner_data["cards"].extend(received_cards)
            save_data(data)
            await update_quest_progress(context, user_id, "trade_2", 1)
            data = load_data()
            # Очищаем трейд
            del data["active_trades"][user_id]
            save_data(data)
            # ⭐ ИСПРАВЛЕНИЕ: Очищаем context.user_data для ОБОИХ пользователей ⭐
            if user_id in context.user_data:
                del context.user_data[user_id]
            if partner_id in context.user_data:
                del context.user_data[partner_id]
            await query.edit_message_text(
                "✅ Обмен завершён!\n",
                parse_mode="Markdown"
            )
            # Уведомляем получателя
            try:
                await context.bot.send_message(
                    chat_id=partner_id,
                    text=(
                        "✅ Обмен завершён!\n"
                    ),
                    parse_mode="Markdown"
                )
            except:
                pass
        # Отмена обмена
        elif query.data.startswith("trade_final_decline_"):
            # Очищаем трейд
            del data["active_trades"][user_id]
            save_data(data)
            # ⭐ ИСПРАВЛЕНИЕ: Очищаем context.user_data для ОБОИХ пользователей ⭐
            if user_id in context.user_data:
                del context.user_data[user_id]
            if partner_id in context.user_data:
                del context.user_data[partner_id]
            await query.edit_message_text("❌ Обмен отменён")
            # Уведомляем получателя
            try:
                await context.bot.send_message(
                    chat_id=partner_id,
                    text="❌ Отправитель отменил обмен."
                )
            except:
                pass
    except Exception as e:
        logger.error(f"Ошибка trade_final_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)
