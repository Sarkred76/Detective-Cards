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
            await update.message.reply_text("❌ У вас нет существ для трейда!")
            return
        
        keyboard = [
            [InlineKeyboardButton("1 ↔ 1", callback_data="trade_1v1")],
            [InlineKeyboardButton("❌ Отмена", callback_data="trade_cancel")],
        ]
        
        await update.message.reply_text(
            "🔄 **Трейд существ**\n\n"
            "Выберите тип обмена:\n"
            "• 1 ↔ 1 - обмен 1 существо на 1\n"
            "📝 После выбора нужно будет указать героя и выбрать существ.",
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
            "👤 **Введите @никнейм героя**\n\n"
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


async def process_partner_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка выбора партнёра или поиска существа."""
    try:
        user_id = str(update.effective_user.id)
        text = update.message.text.strip()

        # Проверяем, есть ли активный трейд
        if user_id not in context.user_data:
            return # Если сессия закончилась, просто выходим

        trade_info = context.user_data[user_id]
        step = trade_info.get("step", "")

        # 1. Проверяем команду отмены (/cancel)
        if text.lower() == "/cancel":
            if step == "search_mode":
                # Если была команда отмены в режиме поиска
                trade_info["step"] = "select_cards" # Возвращаемся к выбору
                await update.message.reply_text("❌ Поиск отменён\nВыберите существо кнопками:")
                # Здесь можно повторно вызвать функцию показа текущей карты для выбора
                # await show_current_card_for_trade(update, context) # Если реализуете
                return
            elif step == "select_partner":
                # Если была команда отмены на этапе выбора партнера
                del context.user_data[user_id]
                await update.message.reply_text("❌ Трейд отменён")
                return
            else:
                # Для других шагов можно игнорировать /cancel или обработать по-другому
                return

        # 2. Если пользователь в режиме поиска, вызываем функцию поиска
        if step == "search_mode":
            # ВАЖНО: вызываем функцию поиска, передав update и context
            await search_creatures_for_trade(update, context)
            # Завершаем выполнение этой функции, чтобы не выполнялась остальная логика
            return

        # 3. Если пользователь не в режиме поиска, но не в "select_partner", выходим
        if step != "select_partner":
            # Это может быть лишним, если другие шаги обрабатываются в другом месте,
            # но пусть будет для ясности.
            return

        # 4. Логика выбора партнера (если step == "select_partner")
        partner_id = None
        data = load_data()
        if text.startswith("@"):
            # Поиск партнера по username
            for uid, udata in data["users"].items():
                if udata.get("username") and udata["username"] == text[1:]:
                    partner_id = uid
                    break

            if not partner_id:
                if user_id in context.user_data:
                    del context.user_data[user_id] # Удаляем сессию, так как ошибка
                await update.message.reply_text("⚠️ Герой с таким @никнеймом не найден!\nНачните трейд заново /trade")
                return # Выходим после ошибки
        else:
            # Если текст не начинается с @, и не была обработана команда /cancel,
            # и не был вызван поиск, то это ошибка на этапе выбора партнера.
            # Но теперь, если пользователь ввел название существа, мы не должны сюда попадать,
            # потому что шаг "search_mode" обрабатывается выше.
            # Однако, если он ввел что-то неожиданное на шаге "select_partner",
            # сообщим ему об этом.
            await update.message.reply_text("⚠️ Введите @никнейм героя для выбора партнера.")
            return # Выходим, не продолжая логику выбора партнера

        # 5. Если partner_id найден и прошли все проверки
        if partner_id:
            # Проверяем существование партнёра
            if partner_id not in data["users"]:
                await update.message.reply_text("⚠️ Герой не найден!")
                # Удаляем сессию, если нужно
                if user_id in context.user_data:
                     del context.user_data[user_id]
                return

            if partner_id == user_id:
                await update.message.reply_text("⚠️ Нельзя трейдиться с самим собой!")
                return

            # Сохраняем партнёра и переходим к следующему шагу
            trade_info["partner_id"] = partner_id
            trade_info["step"] = "select_cards"
            # ... (остальная логика из оригинального кода для выбора карт)
            # Пример продолжения (может отличаться в вашем коде):
            trade_type = trade_info["trade_type"]
            cards_count = int(trade_type.split("v")[0])
            trade_info["cards_count"] = cards_count
            trade_info["selected_cards"] = []

            await update.message.reply_text(
                f"✅ Партнёр: {partner_id}\n"
                f"🐦‍🔥 Выберите {cards_count} существ для обмена.\n"
                f"Используйте кнопки для навигации:\n"
                f"• [<] [>] - листать существ\n"
                f"• [✅ Выбрать] - добавить существо\n"
                f"• [🔍 Поиск] - найти по названию\n"
                f"• [➡️ Далее] - завершить выбор",
                parse_mode="Markdown"
            )
            # Показываем первую карту для выбора
            user_data = data["users"][user_id]
            user_card_ids = user_data.get("cards", [])
            if len(user_card_ids) < cards_count:
                await update.message.reply_text("❌ Недостаточно существ для трейда!")
                del context.user_data[user_id]
                return

            trade_info["user_card_ids"] = user_card_ids
            trade_info["current_index"] = 0
            if user_card_ids: # Проверяем, что список не пуст
                 card = find_card_by_id(user_card_ids[0], data["cards"])
                 if card:
                     caption = f"{card['title']}\nРедкость: {card['rarity']}\n0/{cards_count} выбрано"
                     keyboard = [
                         [
                             InlineKeyboardButton("<", callback_data=f"trade_prev_0"),
                             InlineKeyboardButton("✅ Выбрать", callback_data=f"trade_select_0"),
                             InlineKeyboardButton(">", callback_data=f"trade_next_0"),
                         ],
                         [
                             InlineKeyboardButton("➡️ Далее", callback_data="trade_finish_select"),
                         ],
                         [
                             InlineKeyboardButton("🔍 Поиск", callback_data="trade_open_search"), # Кнопка поиска
                         ]
                     ]
                     await update.message.reply_photo(
                         photo=card["image_url"],
                         caption=caption,
                         reply_markup=InlineKeyboardMarkup(keyboard)
                     )
            else:
                 await update.message.reply_text("❌ У вас нет существ для трейда.")
                 del context.user_data[user_id]

    except Exception as e:
        logger.error(f"Ошибка process_partner_selection: {e}")
        # Попробуем уведомить пользователя, но аккуратно, чтобы не вызвать рекурсию
        try:
             await update.message.reply_text("❌ Ошибка при обработке вашего запроса.")
        except:
             pass # Игнорируем ошибку при отправке сообщения об ошибке
        # Удаляем сессию, чтобы избежать зависания в некорректном состоянии
        try:
             user_id = str(update.effective_user.id)
             if user_id in context.user_data:
                  del context.user_data[user_id]
        except:
             pass

async def search_creatures_for_trade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Поиск существ по названию во время трейда."""
    try:
        user_id = str(update.effective_user.id)
        text = update.message.text.strip()
        
        # Проверяем, находится ли пользователь в режиме выбора карт для трейда
        if user_id not in context.user_data:
            await update.message.reply_text("❌ Вы не находитесь в режиме трейда!\nНачните с команды /trade")
            return
        
        trade_info = context.user_data[user_id]
        step = trade_info.get("step", "")
        if step not in ["select_cards", "select_return_cards", "search_mode"]:
            if step != "search_mode":
                if step not in ["select_cards", "select_return_cards", "search_mode"]:
                    await update.message.reply_text(f"❌ Невозможно выполнить поиск. Текущий шаг трейда: '{step}'.")
                    return
        
        # Проверяем, есть ли данные пользователя
        data = load_data()
        user_data = data["users"].get(user_id)
        if not user_data or not user_data.get("cards"):
            await update.message.reply_text("❌ У вас нет существ для трейда!")
            return
        
        # Ищем существ по названию
        search_query = text.lower()
        user_card_ids = user_data["cards"]
        card_counts = Counter(user_card_ids)
        
        found_creatures = []
        for card_id, count in card_counts.items():
            card = find_card_by_id(card_id, data["cards"])
            if card and search_query in card["title"].lower():
                found_creatures.append((card, count, card_id))
        
        if not found_creatures:
            await update.message.reply_text(
                f"❌ Существ с названием \"{text}\" не найдено!\n"
                "Попробуйте другой запрос или введите @никнейм для выбора партнёра.")
            if step == "search_mode":
                trade_info["step"] = "select_cards" # Возвращаемся к выбору
                await update.message.reply_text(" 🐦‍🔥 Выберите существо кнопками:")
            return
        
        # Показываем результаты поиска
        if len(found_creatures) == 1:
            # Если найдено одно существо — показываем его сразу
            card, count, card_id = found_creatures[0]
            
            # Проверяем, сколько карт нужно выбрать
            cards_count = trade_info.get("cards_count", 1)
            selected_cards = trade_info.get("selected_cards", [])
            
            keyboard = [
                [InlineKeyboardButton(f"✅ Выбрать: {card['title']}", callback_data=f"trade_search_select_{card_id}")]
            ]
            keyboard.append([InlineKeyboardButton("❌ Отмена поиска", callback_data="trade_search_cancel")])
            
            trade_info["step"] = "search_results"
            trade_info["search_query"] = search_query
            await update.message.reply_photo(
                photo=card["image_url"],
                caption=f"{card['title']}\nРедкость: {card['rarity']}\n🛡 В казарме: {count} шт.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            # Если найдено несколько — показываем список
            keyboard = []
            for card, count, card_id in found_creatures[:10]:  # Показываем максимум 10
                keyboard.append([
                    InlineKeyboardButton(
                        f"{card['title']} ({count} шт.)",
                        callback_data=f"trade_search_select_{card_id}"
                    )
                ])
            keyboard.append([InlineKeyboardButton("❌ Отмена поиска", callback_data="trade_search_cancel")])
            
            await update.message.reply_text(
                f"🔍 **Найдено существ: {len(found_creatures)}**\n\n"
                f"По запросу: \"{text}\"\n\n"
                f"Выберите существо для трейда:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        # Сохраняем информацию о поиске
        trade_info["step"] = "search_results"
        trade_info["search_query"] = search_query
        
    except Exception as e:
        logger.error(f"Ошибка search_creatures_for_trade: {e}")
        await update.message.reply_text("❌ Ошибка при поиске существ")

async def trade_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора существа из поиска."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)

        # Проверяем, находится ли пользователь в сессии трейда
        if user_id not in context.user_data:
            await query.edit_message_text(text="❌ Сессия трейда истекла!") # Используем edit_message_text для текстового сообщения
            return

        trade_info = context.user_data[user_id]
        step = trade_info.get("step", "")

        # --- Обработка нажатия кнопки "Выбрать" из результатов поиска ---
        if query.data.startswith("trade_search_select_"):
            card_id_str = query.data.split("_")[-1]
            try:
                card_id = int(card_id_str)
            except ValueError:
                await query.answer("❌ Неверный ID карты.", show_alert=True)
                return

            # --- ИСПРАВЛЕНИЕ: Загрузка данных ---
            data = load_data() # <-- ЭТА СТРОКА БЫЛА ПРОПУЩЕНА ИЛИ НЕПРАВИЛЬНО РАСПОЛОЖЕНА
            # ---------------------------------

            # Проверяем, есть ли у игрока это существо
            user_data = data["users"].get(user_id)
            if not user_data or card_id not in user_data.get("cards", []):
                # Попробуем отредактировать текстовое сообщение
                try:
                    await query.edit_message_text(text="❌ У вас нет этого существа!")
                except:
                    # Если не получилось (например, уже удалено), просто выйдем
                    pass
                return

            # Определяем, какой тип выбора сейчас (отправитель или получатель)
            # Используем step до поиска
            prev_step = trade_info.get("previous_step_before_search", "select_cards")
            if prev_step not in ["select_cards", "select_return_cards"]:
                 # Fallback
                 prev_step = "select_cards" if "cards_offered_by_sender" not in trade_info else "select_return_cards"

            cards_count_key = "cards_count"
            selected_cards_key = "selected_cards"
            user_card_ids_key = "user_card_ids"

            # Логика общая для отправителя и получателя
            selected_cards = trade_info.get(selected_cards_key, [])
            cards_count = trade_info.get(cards_count_key, 1)

            # Проверяем, не превышено ли количество выбранных карт
            if len(selected_cards) >= cards_count:
                await query.answer(f"❌ Вы уже выбрали {cards_count} существ!", show_alert=True)
                return

            # Проверяем, не выбрана ли уже эта карта
            # Для отправителя и получателя selected_cards содержит индексы в user_card_ids
            user_card_ids = trade_info.get(user_card_ids_key, [])
            try:
                 card_index = user_card_ids.index(card_id)
            except ValueError:
                 # Карта есть в казарме (проверено выше), но не в user_card_ids сессии?
                 await query.answer("❌ Ошибка: карта не найдена в списке.", show_alert=True)
                 return

            if card_index in selected_cards:
                await query.answer("❌ Это существо уже выбрано!", show_alert=True)
                return

            # Добавляем индекс карты в выбранные
            selected_cards.append(card_index)
            trade_info[selected_cards_key] = selected_cards # Обновляем список

            # --- ОБНОВЛЕНИЕ: Проверяем тип сообщения перед редактированием ---
            # Сообщение может быть с фото (caption) или с текстом (text).
            # Если у сообщения есть photo, значит, это результат single-card search, и можно edit_caption.
            # Если у сообщения есть только text, значит, это список, и нужно edit_text или удалить и отправить новое.

            # Проверяем, есть ли фото (то есть caption)
            if query.message.photo:
                 # Это сообщение с фото и caption (одна карта)
                 card = find_card_by_id(card_id, data["cards"])
                 if card:
                     card_counts = Counter(user_data["cards"])
                     card_in_user_deck = card_counts.get(card["id"], 0)
                     await query.message.edit_caption(
                         caption=(
                             f"🔍 **Найдено существо:**\n"
                             f"🏷 {card['title']}\n"
                             f"🌟 Редкость: {card['rarity']}\n"
                             f"🛡 В казарме: {card_in_user_deck} шт.\n"
                             f"📊 Выбрано: {len(selected_cards)}/{cards_count}\n"
                             f"✅ Выбрано: {card['title']}"
                         ),
                         reply_markup=InlineKeyboardMarkup([
                             [InlineKeyboardButton("✅ Выбрано", callback_data=f"trade_search_selected_{card_id}")]
                         ])
                     )

                     # Если набрали нужное количество, возвращаемся к основному выбору
                     if len(selected_cards) >= cards_count:
                          await query.answer(f"✅ Выбрано {cards_count} существ! Нажмите '➡️ Далее'.", show_alert=False)
                          # Возвращаем step к предыдущему ("select_cards" или "select_return_cards")
                          trade_info["step"] = prev_step
                          # Удаляем предыдущий шаг, так как он использован
                          if "previous_step_before_search" in trade_info:
                              del trade_info["previous_step_before_search"]
                          # --- ОБНОВЛЕНИЕ СООБЩЕНИЯ С ИНТЕРФЕЙСОМ ВЫБОРА ---
                          # Теперь нужно показать интерфейс, соответствующий prev_step.
                          # В данном случае, это "select_return_cards" или "select_cards".
                          # Показываем текущую карту (например, последнюю выбранную или первую доступную)
                          # с полным интерфейсом trade_return_callback или trade_callback.
                          # Мы не можем вызвать trade_return_callback напрямую изнутри trade_search_callback,
                          # но можем повторить логику обновления сообщения оттуда.

                          # Получаем текущий индекс для отображения (например, индекс последней выбранной карты)
                          # или оставляем старый current_index, если он был.
                          # Для простоты, покажем ту, которую только что выбрали (card_index).
                          display_index = card_index # Показываем только что выбранную карту

                          card_to_display = find_card_by_id(user_card_ids[display_index], data["cards"])
                          if card_to_display:
                              card_counts_display = Counter(user_card_ids)
                              card_in_collection = card_counts_display.get(card_to_display["id"], 1)
                              selected_count_now = len(selected_cards)

                              caption = (
                                  f"{card_to_display['title']}\n"
                                  f"Редкость: {card_to_display['rarity']}\n"
                                  f"📦 В казарме: {card_in_collection} шт.\n\n"
                                  f"📊 Выбрано: {selected_count_now}/{cards_count}"
                              )

                              is_selected_display = display_index in selected_cards
                              select_text = "❌ Убрать" if is_selected_display else "✅ Выбрать"

                              # Определяем, какую функцию обработки использовать для кнопок
                              # Если prev_step был "select_return_cards", используем кнопки trade_return_...
                              # Если был "select_cards", используем trade_...
                              button_prefix = "trade_return_" if prev_step == "select_return_cards" else "trade_"

                              keyboard = [
                                  [
                                      InlineKeyboardButton("<", callback_data=f"{button_prefix}prev_{display_index}"),
                                      InlineKeyboardButton(select_text, callback_data=f"{button_prefix}select_{display_index}"),
                                      InlineKeyboardButton(">", callback_data=f"{button_prefix}next_{display_index}"),
                                  ],
                                  [
                                      InlineKeyboardButton("➡️ Далее", callback_data=f"{button_prefix}finish"), # Используем правильный finish
                                  ],
                                  [
                                      InlineKeyboardButton("🔍 Поиск", callback_data=f"{button_prefix}search_button"), # Используем правильную кнопку поиска
                                  ]
                              ]

                              media = InputMediaPhoto(media=card_to_display["image_url"], caption=caption)
                              # Редактируем ТЕКУЩЕЕ сообщение (с результатами поиска) на сообщение с интерфейсом
                              await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
                          # ----------------------------------------------
                     else:
                          await query.answer(f"✅ Добавлено: {card['title']}. Осталось выбрать {cards_count - len(selected_cards)}", show_alert=False)
            else:
                 # Это сообщение с текстом (список карт). Мы не можем редактировать caption.
                 # Лучший способ - удалить это сообщение и отправить новое с результатом выбора.
                 # Но это может быть неудобно.
                 # ВАРИАНТ: Отправить отдельное уведомление и не редактировать старое.
                 # Однако, для согласованности, лучше попытаться редактировать текст.
                 # У сообщения с текстом есть query.message.text.
                 # Попробуем edit_text.
                 card = find_card_by_id(card_id, data["cards"])
                 if card:
                     card_counts = Counter(user_data["cards"])
                     card_in_user_deck = card_counts.get(card["id"], 0)
                     new_text = (
                         f"🔍 **Найдено существо:**\n"
                         f"🏷 {card['title']}\n"
                         f"🌟 Редкость: {card['rarity']}\n"
                         f"🛡 В казарме: {card_in_user_deck} шт.\n"
                         f"📊 Выбрано: {len(selected_cards)}/{cards_count}\n"
                         f"✅ Выбрано: {card['title']}"
                     )
                     # Обновляем клавиатуру на "Выбрано"
                     new_keyboard = InlineKeyboardMarkup([
                         [InlineKeyboardButton("✅ Выбрано", callback_data=f"trade_search_selected_{card_id}")]
                     ])
                     await query.edit_message_text(text=new_text, reply_markup=new_keyboard)

                     # Если набрали нужное количество, возвращаемся к основному выбору
                     if len(selected_cards) >= cards_count:
                          await query.answer(f"✅ Выбрано {cards_count} существ! Нажмите '➡️ Далее'.", show_alert=False)
                          # Возвращаем step к предыдущему ("select_cards" или "select_return_cards")
                          trade_info["step"] = prev_step
                          # Удаляем предыдущий шаг, так как он использован
                          if "previous_step_before_search" in trade_info:
                              del trade_info["previous_step_before_search"]
                          # --- ОБНОВЛЕНИЕ СООБЩЕНИЯ С ИНТЕРФЕЙСОМ ВЫБОРА ---
                          # Теперь нужно показать интерфейс, соответствующий prev_step.
                          # Показываем текущую карту (например, последнюю выбранную или первую доступную)
                          # с полным интерфейсом trade_return_callback или trade_callback.

                          # Получаем текущий индекс для отображения (например, индекс последней выбранной карты)
                          # или оставляем старый current_index, если он был.
                          # Для простоты, покажем ту, которую только что выбрали (card_index).
                          display_index = card_index # Показываем только что выбранную карту

                          card_to_display = find_card_by_id(user_card_ids[display_index], data["cards"])
                          if card_to_display:
                              card_counts_display = Counter(user_card_ids)
                              card_in_collection = card_counts_display.get(card_to_display["id"], 1)
                              selected_count_now = len(selected_cards)

                              caption = (
                                  f"{card_to_display['title']}\n"
                                  f"Редкость: {card_to_display['rarity']}\n"
                                  f"📦 В казарме: {card_in_collection} шт.\n\n"
                                  f"📊 Выбрано: {selected_count_now}/{cards_count}"
                              )

                              is_selected_display = display_index in selected_cards
                              select_text = "❌ Убрать" if is_selected_display else "✅ Выбрать"

                              # Определяем, какую функцию обработки использовать для кнопок
                              # Если prev_step был "select_return_cards", используем кнопки trade_return_...
                              # Если был "select_cards", используем trade_...
                              button_prefix = "trade_return_" if prev_step == "select_return_cards" else "trade_"

                              keyboard = [
                                  [
                                      InlineKeyboardButton("<", callback_data=f"{button_prefix}prev_{display_index}"),
                                      InlineKeyboardButton(select_text, callback_data=f"{button_prefix}select_{display_index}"),
                                      InlineKeyboardButton(">", callback_data=f"{button_prefix}next_{display_index}"),
                                  ],
                                  [
                                      InlineKeyboardButton("➡️ Далее", callback_data=f"{button_prefix}finish"), # Используем правильный finish
                                  ],
                                  [
                                      InlineKeyboardButton("🔍 Поиск", callback_data=f"{button_prefix}search_button"), # Используем правильную кнопку поиска
                                  ]
                              ]

                              # Удаляем старое сообщение с текстом
                              try:
                                  await query.message.delete()
                              except:
                                  pass # Игнорируем, если не удалось удалить
                              # Отправляем новое сообщение с фото и интерфейсом
                              await context.bot.send_photo(
                                  chat_id=query.message.chat_id,
                                  photo=card_to_display["image_url"],
                                  caption=caption,
                                  reply_markup=InlineKeyboardMarkup(keyboard)
                              )
                          # ----------------------------------------------
                     else:
                          await query.answer(f"✅ Добавлено: {card['title']}. Осталось выбрать {cards_count - len(selected_cards)}", show_alert=False)


            return # Важно выйти после обработки выбора

        # --- Обработка нажатия кнопки "Отмена поиска" ---
        elif query.data == "trade_search_cancel":
            if user_id in context.user_data:
                trade_info = context.user_data[user_id]
                # Возвращаемся к предыдущему шагу выбора ("select_cards" или "select_return_cards")
                # Используем сохранённое значение
                prev_step = trade_info.get("previous_step_before_search", "select_cards")
                if prev_step not in ["select_cards", "select_return_cards"]:
                     # Fallback, если предыдущий шаг не сохранён или неверный
                     prev_step = "select_cards" if "cards_offered_by_sender" not in trade_info else "select_return_cards"

                trade_info["step"] = prev_step
                # Удаляем сообщение с результатами поиска
                try:
                    await query.message.delete()
                except:
                    pass # Игнорируем, если не удалось удалить
                # Отправляем сообщение и показываем интерфейс выбора карт снова
                await query.message.reply_text("❌ Поиск отменён\nВыберите существо кнопками:")
                # Важно: шаг изменен.
            return # Важно выйти после обработки отмены

        # --- Обработка других кнопок, если они есть ---
        # В этой версии trade_search_callback НЕ обрабатывает trade_search_button.
        # Кнопка trade_search_button должна обрабатываться в trade_callback или trade_return_callback,
        # где она сохраняет previous_step_before_search.


    except Exception as e:
        logger.error(f"Ошибка trade_search_callback: {e}")
        # Попробуем уведомить пользователя, но аккуратно
        try:
             await query.answer("❌ Ошибка при обработке поиска", show_alert=True)
        except:
             pass # Игнорируем ошибку при отправке сообщения об ошибке


async def trade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок трейда."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        
        # ⭐ ОБРАБОТКА ВЫБОРА ТИПА ТРЕЙДА
        if query.data in ["trade_1v1", "trade_2v2", "trade_3v3"]:
            trade_type = query.data.split("_")[1]  # "1v1", "2v2", "3v3"
            await select_trade_partner(update, context, trade_type)
            return
        
        # Отмена
        if query.data == "trade_cancel":
            if user_id in context.user_data:
                del context.user_data[user_id]
            await query.edit_message_text("❌ Трейд отменён")
            return
        
        # Проверяем сессию для остальных кнопок
        if user_id not in context.user_data:
            await query.edit_message_text("❌ Сессия трейда истекла!")
            return
        
        trade_info = context.user_data[user_id]
        data = load_data()
        
        # Навигация
        if query.data.startswith("trade_prev_") or query.data.startswith("trade_next_"):
            action = "prev" if "prev" in query.data else "next"
            current_index = trade_info.get("current_index", 0)
            user_card_ids = trade_info.get("user_card_ids", [])
            
            if not user_card_ids:
                await query.answer("❌ Существа не найдены!", show_alert=True)
                return
            
            if action == "prev":
                current_index = (current_index - 1) % len(user_card_ids)
            else:
                current_index = (current_index + 1) % len(user_card_ids)
            
            trade_info["current_index"] = current_index
            
            card = find_card_by_id(user_card_ids[current_index], data["cards"])
            if card:
                selected_count = len(trade_info.get("selected_cards", []))
                cards_count = trade_info.get("cards_count", 1)
                
                # ⭐ СЧИТАЕМ КОЛИЧЕСТВО КАРТЫ В КОЛЛЕКЦИИ ⭐
                card_counts = Counter(user_card_ids)
                card_in_collection = card_counts.get(card["id"], 1)
                
                caption = (
                    f"{card['title']}\n"
                    f"Редкость: {card['rarity']}\n"
                    f"🛡 В казарме: {card_in_collection} шт.\n\n"
                    f"{selected_count}/{cards_count} выбрано"
                )
                
                is_selected = current_index in trade_info.get("selected_cards", [])
                select_text = "❌ Убрать" if is_selected else "✅ Выбрать"
                
                keyboard = [
                    [
                        InlineKeyboardButton("<", callback_data=f"trade_prev_{current_index}"),
                        InlineKeyboardButton(select_text, callback_data=f"trade_select_{current_index}"),
                        InlineKeyboardButton(">", callback_data=f"trade_next_{current_index}"),
                    ],
                    [InlineKeyboardButton("➡️ Далее", callback_data="trade_finish_select")],
                    [InlineKeyboardButton("🔍 Поиск", callback_data="trade_open_search")],
                ]
                
                media = InputMediaPhoto(media=card["image_url"], caption=caption)
                await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # Выбор карты
        elif query.data.startswith("trade_select_"):
            card_index = int(query.data.split("_")[-1])
            selected_cards = trade_info.get("selected_cards", [])
            cards_count = trade_info.get("cards_count", 1)
            user_card_ids = trade_info.get("user_card_ids", [])
            
            if card_index in selected_cards:
                selected_cards.remove(card_index)
            else:
                if len(selected_cards) >= cards_count:
                    await query.answer("❌ Максимум существ выбрано!", show_alert=True)
                    return
                selected_cards.append(card_index)
            
            trade_info["selected_cards"] = selected_cards
            
            # Обновляем отображение
            current_index = trade_info.get("current_index", 0)
            card = find_card_by_id(user_card_ids[current_index], data["cards"])
            if card:
                # ⭐ СЧИТАЕМ КОЛИЧЕСТВО КАРТЫ В КОЛЛЕКЦИИ ⭐
                card_counts = Counter(user_card_ids)
                card_in_collection = card_counts.get(card["id"], 1)
                
                caption = (
                    f"{card['title']}\n"
                    f"Редкость: {card['rarity']}\n"
                    f"🛡 В казарме: {card_in_collection} шт.\n\n"
                    f"{len(selected_cards)}/{cards_count} выбрано"
                )
                
                is_selected = current_index in selected_cards
                select_text = "❌ Убрать" if is_selected else "✅ Выбрать"
                
                keyboard = [
                    [
                        InlineKeyboardButton("<", callback_data=f"trade_prev_{current_index}"),
                        InlineKeyboardButton(select_text, callback_data=f"trade_select_{current_index}"),
                        InlineKeyboardButton(">", callback_data=f"trade_next_{current_index}"),
                    ],
                    [InlineKeyboardButton("➡️ Далее", callback_data="trade_finish_select")],
                    [InlineKeyboardButton("🔍 Поиск", callback_data="trade_open_search")],
                ]
                
                media = InputMediaPhoto(media=card["image_url"], caption=caption)
                await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # Завершение выбора

        elif query.data == "trade_open_search":
            # ⭐ КНОПКА ПОИСКА В ИНТЕРФЕЙСЕ ВЫБОРА КАРТ ОТПРАВИТЕЛЯ ⭐
            if user_id in context.user_data:
                trade_info = context.user_data[user_id]
                # СОХРАНЯЕМ ТЕКУЩИЙ ШАГ ПЕРЕД ПЕРЕХОДОМ К ПОИСКУ
                trade_info["previous_step_before_search"] = trade_info["step"]
                trade_info["step"] = "search_mode"
            await query.answer("🔍 Введите название существа для поиска", show_alert=False)
            await query.message.reply_text(
                "🔍 **Поиск существ**\n"
                "Введите часть названия существа:\n"
                "Например: \"дракон\", \"демон\", \"огр\"\n"
                "❌ Для отмены: /cancel",
                parse_mode="Markdown"
            )
            # ВАЖНО: return здесь, чтобы не выполнялись другие проверки
            return

        
        elif query.data == "trade_finish_select":
            selected_cards = trade_info.get("selected_cards", [])
            cards_count = trade_info.get("cards_count", 1)
            user_card_ids = trade_info.get("user_card_ids", [])
            partner_id = trade_info["partner_id"]
            
            if len(selected_cards) != cards_count:
                await query.answer(f"❌ Выберите ровно {cards_count} существ!", show_alert=True)
                return
            
            # Переходим к подтверждению
            trade_info["step"] = "confirm"
            
            # Формируем список карт для отображения
            selected_card_ids = [user_card_ids[i] for i in selected_cards]
            trade_info["selected_card_ids"] = selected_card_ids
            
            # Удаляем сообщение с картами и отправляем текстовое
            try:
                await query.message.delete()
            except:
                pass
            
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(
                    f"✅ Вы выбрали {cards_count} существ\n\n"
                    f"👤 Партнёр: {trade_info['partner_id']}\n\n"
                    f"📩 Отправляю запрос на обмен..."
                ),
                parse_mode="Markdown"
            )
            
            # В конце функции trade_callback, где сохраняем трейд для партнёра:

            # Отправляем запрос партнёру

            # ⭐ СОХРАНЯЕМ ТРЕЙД В ФАЙЛ (вместо context.user_data) ⭐
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
                "selected_card_ids": selected_card_ids,  # Карты, которые отправитель предлагает
            }

            # Уведомляем партнёра
            try:
                # Получаем имя отправителя
                sender_data = data["users"].get(user_id, {})
                sender_name = sender_data.get("first_name", "Герой")
                if sender_data.get("last_name"):
                    sender_name += f" {sender_data['last_name']}"
                if sender_data.get("username"):
                    sender_name = f"@{sender_data['username']}"
    
                # Получаем информацию о картах
                cards_info = []
                for card_id in selected_card_ids:
                    card = find_card_by_id(card_id, data["cards"])
                    if card:
                        cards_info.append(f"• {card['title']} ({card['rarity']})")
    
                cards_text = "\n".join(cards_info) if cards_info else "Нет существ"
    
                # ⭐ ДОБАВЛЯЕМ ИНЛАЙН-КНОПКИ ⭐
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Принять", callback_data=f"trade_accept_btn_{user_id}"),
                        InlineKeyboardButton("❌ Отклонить", callback_data=f"trade_decline_btn_{user_id}"),
                    ]
                ]
    
                await context.bot.send_message(
                    chat_id=partner_id,
                    text=(
                        f"🔄 **Вам предложили обмен!**\n\n"
                        f"👤 От: {sender_name}\n"
                        f"🐦‍🔥 Существ в обмене: {cards_count}\n\n"
                        f"📋 **Карты отправителя:**\n"
                        f"{cards_text}\n\n"
                        f"Нажмите кнопку для действия:"
                    ),
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML"
                )
            except Exception as notify_error:
                logger.error(f"Не удалось уведомить партнёра: {notify_error}")
                await query.message.reply_text("⚠️ Не удалось уведомить героя")
    
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
                await query.edit_message_text("❌ Герой, который отправил трейд, больше не существует!")
                return
            
            # Проверяем, что карты ещё существуют у отправителя
            if not cards_offered:
                del data["active_trades"][user_id]
                save_data(data)
                await query.edit_message_text("❌ Карты для обмена больше не доступны!")
                return
            
            # Получаем имя отправителя
            sender_data = data["users"].get(from_user, {})
            sender_name = sender_data.get("first_name", "Герой")
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
                f"✅ **Запрос принят от {sender_name}**\n\n"
                f"🐦‍🔥 Существ в обмене: {len(cards_offered)}\n\n"
                f"📋 **Просмотрите существ ниже:**\n"
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
                
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=card["image_url"],
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        
        # Отклонение трейда
        elif query.data.startswith("trade_decline_btn_"):
            del data["active_trades"][user_id]
            save_data(data)
            
            await query.edit_message_text("❌ Трейд отклонён")
            
            # Уведомляем отправителя
            try:
                await context.bot.send_message(
                    chat_id=from_user,
                    text=f"❌ Герой отклонил ваш запрос на обмен."
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
            await query.answer("❌ Существа не найдены!", show_alert=True)
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
                    InlineKeyboardButton("✅ Принять обмен", callback_data="trade_accept_confirm"),
                    InlineKeyboardButton("❌ Отклонить", callback_data="trade_decline_from_view"),
                ])
                
                media = InputMediaPhoto(media=card["image_url"], caption=caption)
                await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # Принятие обмена
        elif query.data == "trade_offer_accept":
            # Переходим к выбору своих карт
            context.user_data[user_id]["step"] = "select_return_cards"
            from_user = trade_info.get("trade_partner")
            cards_count = len(cards_offered)
            
            await query.message.reply_text(
                f"✅ Запрос принят!\n\n"
                f"🐦‍🔥 Теперь выберите {cards_count} существ для обмена\n\n"
                "Используйте кнопки для выбора...",
                parse_mode="Markdown"
            )
            
            # Показываем карты пользователя для выбора
            user_data = data["users"][user_id]
            user_card_ids = user_data.get("cards", [])
            
            if len(user_card_ids) < cards_count:
                await query.message.reply_text(
                    f"❌ Недостаточно существ для трейда!\n"
                    f"У вас: {len(user_card_ids)} существ, нужно: {cards_count}"
                )
                if "incoming_trade" in context.user_data.get(user_id, {}):
                    del context.user_data[user_id]["incoming_trade"]
                return
            
            context.user_data[user_id]["user_card_ids"] = user_card_ids
            context.user_data[user_id]["cards_count"] = cards_count
            context.user_data[user_id]["selected_cards"] = []
            context.user_data[user_id]["current_index"] = 0
            
            # Показываем первую карту
            if not user_card_ids:
                await query.message.reply_text("❌ У вас нет существ!")
                return
            
            card = find_card_by_id(user_card_ids[0], data["cards"])
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
                await query.message.reply_photo(
                    photo=card["image_url"],
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        
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
                        text=f"❌ Герой отклонил ваш запрос на обмен."
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
        user_card_ids = trade_info.get("user_card_ids", [])
        # Навигация
        if query.data.startswith("trade_return_prev_") or query.data.startswith("trade_return_next_"):
            action = "prev" if "prev" in query.data else "next"
            current_index = trade_info.get("current_index", 0)
            if not user_card_ids:
                await query.answer("❌ Существа не найдены!", show_alert=True)
                return
            if action == "prev":
                current_index = (current_index - 1) % len(user_card_ids)
            else:
                current_index = (current_index + 1) % len(user_card_ids)
            trade_info["current_index"] = current_index
            card = find_card_by_id(user_card_ids[current_index], data["cards"])
            if card:
                selected_count = len(trade_info.get("selected_cards", []))
                cards_count = trade_info.get("cards_count", 1)
                card_counts = Counter(user_card_ids)
                card_in_collection = card_counts.get(card["id"], 1)
                caption = (
                    f"{card['title']}\n"
                    f"Редкость: {card['rarity']}\n"
                    f"🛡 В казарме: {card_in_collection} шт.\n"
                    f"{selected_count}/{cards_count} выбрано"
                )
                is_selected = current_index in trade_info.get("selected_cards", [])
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
                media = InputMediaPhoto(media=card["image_url"], caption=caption)
                await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
        # Выбор карты
        elif query.data.startswith("trade_return_select_"):
            card_index = int(query.data.split("_")[-1])
            selected_cards = trade_info.get("selected_cards", [])
            cards_count = trade_info.get("cards_count", 1)
            if card_index in selected_cards:
                selected_cards.remove(card_index)
            else:
                if len(selected_cards) >= cards_count:
                    await query.answer("❌ Максимум существ выбрано!", show_alert=True)
                    return
                selected_cards.append(card_index)
            trade_info["selected_cards"] = selected_cards
            current_index = trade_info.get("current_index", 0)
            card = find_card_by_id(user_card_ids[current_index], data["cards"])
            if card:
                card_counts = Counter(user_card_ids)
                card_in_collection = card_counts.get(card["id"], 1)
                caption = (
                    f"{card['title']}\n"
                    f"Редкость: {card['rarity']}\n"
                    f"🛡 В казарме: {card_in_collection} шт.\n"
                    f"{len(selected_cards)}/{cards_count} выбрано"
                )
                is_selected = current_index in selected_cards
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
                media = InputMediaPhoto(media=card["image_url"], caption=caption)
                await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
        elif query.data == "trade_return_search_button":
            # КНОПКА ПОИСКА В ИНТЕРФЕЙСЕ ВЫБОРА КАРТ ПОЛУЧАТЕЛЯ
            if user_id in context.user_data:
                trade_info = context.user_data[user_id]
                # СОХРАНЯЕМ ТЕКУЩИЙ ШАГ ПЕРЕД ПЕРЕХОДОМ К ПОИСКУ
                trade_info["previous_step_before_search"] = trade_info["step"]
                trade_info["step"] = "search_mode"
            await query.answer("🔍 Введите название существа для поиска", show_alert=False)
            await query.message.reply_text(
                "🔍 **Поиск существ**\n"
                "Введите часть названия существа:\n"
                "Например: \"дракон\", \"демон\", \"огр\"\n"
                "❌ Для отмены: /cancel",
                parse_mode="Markdown"
            )
            return
        # ⭐ ЗАВЕРШЕНИЕ ВЫБОРА КАРТ ⭐
        elif query.data == "trade_return_finish":
            selected_cards = trade_info.get("selected_cards", [])
            cards_count = trade_info.get("cards_count", 1)
            if len(selected_cards) != cards_count:
                await query.answer(f"❌ Выберите ровно {cards_count} существ!", show_alert=True)
                return
            # Получаем выбранные карты
            selected_card_ids = [user_card_ids[i] for i in selected_cards]
            received_cards = trade_info.get("received_cards", [])  # Карты от отправителя
            partner_id = trade_info.get("trade_partner")  # ID отправителя (Игрок А)
            # ⭐ СОХРАНЯЕМ В ФАЙЛ ВМЕСТО context.user_data ⭐
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
            # ⭐ ИСПРАВЛЕНИЕ: Очищаем context.user_data Получателя ⭐
            if user_id in context.user_data:
                del context.user_data[user_id]
            # Отправляем уведомление отправителю (Игрок А)
            try:
                sender_data = data["users"].get(user_id, {})
                sender_name = sender_data.get("first_name", "Герой")
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
                        f"🔄 **Герой готов к обмену!**\n"
                        f"👤 {sender_name} предлагает:\n"
                        f"{return_cards_text}\n"
                        f"📋 **Ваше предложение:**\n"
                        f"{offered_cards_text}\n"
                        f"Нажмите кнопку для подтверждения:"
                    ),
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
                # ⭐ ИСПРАВЛЕНИЕ: удаляем фото и отправляем текстовое сообщение ⭐
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
            # Очищаем трейд
            del data["active_trades"][user_id]
            save_data(data)
            # ⭐ ИСПРАВЛЕНИЕ: Очищаем context.user_data для ОБОИХ пользователей ⭐
            if user_id in context.user_data:
                del context.user_data[user_id]
            if partner_id in context.user_data:
                del context.user_data[partner_id]
            await query.edit_message_text(
                "✅ **Обмен завершён!**\n"
                f"🐦‍🔥 Вы отдали: {len(received_cards)} существ\n"
                f"🐦‍🔥 Вы получили: {len(selected_return_cards)} существ",
                parse_mode="Markdown"
            )
            # Уведомляем получателя
            try:
                await context.bot.send_message(
                    chat_id=partner_id,
                    text=(
                        "✅ **Обмен завершён!**\n"
                        f"🐦‍🔥 Вы отдали: {len(selected_return_cards)} существ\n"
                        f"🐦‍🔥 Вы получили: {len(received_cards)} существ"
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
