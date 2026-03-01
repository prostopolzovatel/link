import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram import F
from aiogram.client.default import DefaultBotProperties
from datetime import datetime

# Токен и админ ID
BOT_TOKEN = "8489477150:AAGaipKgwWfiSgH3IdRyAnyNBXwAE_bknf0"
ADMIN_ID = 8423212939

# Цены
BOT_PRICE = 100  # Звезд за разработку
HOSTING_PRICE = 60  # Звезд за хостинг

# Состояния заказов
ORDER_STATUSES = {
    "pending": "⏳ Ожидание",
    "development": "🔧 В разработке",
    "completed": "✅ Готово",
    "rejected": "❌ Отклонён"
}

# База данных
orders_db = {}
user_orders = {}  # {user_id: order_id}
users_db = set()  # Множество всех пользователей, которые interacted с ботом
admin_states = {}  # Для хранения состояний админа
user_states = {}  # Для хранения состояний пользователей
support_requests = {}  # Для обращений в поддержку
active_support_chats = {}  # {user_id: support_id} для активных диалогов

# Инициализация бота
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

# Клавиатуры
def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Заказать разработку бота", callback_data="order_bot")],
        [InlineKeyboardButton(text="📋 Мои заказы", callback_data="my_orders")],
        [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")]
    ])
    return keyboard

def get_admin_main_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Все заказы", callback_data="admin_orders")],
        [InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="👥 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🆘 Обращения в поддержку", callback_data="admin_support")],
        [InlineKeyboardButton(text="🔙 Выход", callback_data="back_to_main")]
    ])
    return keyboard

def get_admin_keyboard(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔧 В разработку", callback_data=f"status_development_{order_id}"),
            InlineKeyboardButton(text="⏳ В ожидание", callback_data=f"status_pending_{order_id}")
        ],
        [
            InlineKeyboardButton(text="✅ Готово", callback_data=f"status_completed_{order_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_order_{order_id}")
        ],
        [
            InlineKeyboardButton(text="🔗 Отправить ссылку", callback_data=f"send_link_{order_id}"),
            InlineKeyboardButton(text="📢 Уведомить", callback_data=f"notify_user_{order_id}")
        ],
        [
            InlineKeyboardButton(text="🔙 К списку заказов", callback_data="admin_orders")
        ]
    ])
    return keyboard

def get_user_order_keyboard(order_id):
    buttons = []
    order = orders_db.get(order_id, {})
    
    # Если заказ отклонён
    if order.get("status") == "rejected":
        buttons.append([InlineKeyboardButton(text="🆘 Связаться с поддержкой", callback_data=f"support_order_{order_id}")])
        buttons.append([InlineKeyboardButton(text="📦 Создать новый заказ", callback_data="order_bot")])
        buttons.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")])
    
    # Если есть ссылка и статус "Готово", показываем кнопки
    elif order.get("link") and order.get("status") == "completed":
        buttons.append([InlineKeyboardButton(text="🔗 Получить ссылку для проверки", callback_data=f"get_link_{order_id}")])
        buttons.append([InlineKeyboardButton(text="✅ Бот работает, оплатить", callback_data=f"pay_bot_{order_id}")])
        buttons.append([InlineKeyboardButton(text="❌ Есть вопросы", callback_data=f"support_order_{order_id}")])
        buttons.append([InlineKeyboardButton(text="📦 Сделать еще заказ", callback_data="order_bot")])
        buttons.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")])
    
    # Если разработка оплачена, предлагаем хостинг
    elif order.get("paid") and not order.get("hosting_paid"):
        buttons.append([InlineKeyboardButton(text=f"💻 Оплатить хостинг ({HOSTING_PRICE} ⭐)", callback_data=f"pay_hosting_{order_id}")])
        buttons.append([InlineKeyboardButton(text="🆘 Поддержка", callback_data=f"support_order_{order_id}")])
        buttons.append([InlineKeyboardButton(text="📦 Сделать еще заказ", callback_data="order_bot")])
        buttons.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")])
    
    # Если только создан заказ
    else:
        buttons.append([InlineKeyboardButton(text="🆘 Связаться с поддержкой", callback_data=f"support_order_{order_id}")])
        buttons.append([InlineKeyboardButton(text="📦 Сделать еще заказ", callback_data="order_bot")])
        buttons.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_support_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Написать сообщение админу", callback_data="write_to_admin")],
        [InlineKeyboardButton(text="❓ Часто задаваемые вопросы", callback_data="faq")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    return keyboard

def get_faq_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏱ Сроки разработки", callback_data="faq_time")],
        [InlineKeyboardButton(text="💰 Оплата", callback_data="faq_payment")],
        [InlineKeyboardButton(text="🔧 Что входит", callback_data="faq_include")],
        [InlineKeyboardButton(text="💻 Что такое хостинг", callback_data="faq_hosting")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_support")]
    ])
    return keyboard

def get_back_to_main_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 На главную", callback_data="back_to_main")]
    ])
    return keyboard

def get_continue_dialog_keyboard(support_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Продолжить диалог", callback_data=f"continue_dialog_{support_id}")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")]
    ])
    return keyboard

def get_notification_type_keyboard(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ Статус заказа", callback_data=f"notify_status_{order_id}")],
        [InlineKeyboardButton(text="💰 Напоминание об оплате", callback_data=f"notify_payment_{order_id}")],
        [InlineKeyboardButton(text="🔗 Ссылка на бота", callback_data=f"notify_link_{order_id}")],
        [InlineKeyboardButton(text="📝 Произвольное сообщение", callback_data=f"notify_custom_{order_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_order_{order_id}")]
    ])
    return keyboard

def get_broadcast_confirm_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить рассылку", callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_panel")]
    ])
    return keyboard

# Команда старт
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    
    # Добавляем пользователя в базу
    users_db.add(user_id)
    
    await message.answer(
        "👋 Добро пожаловать в магазин разработки Telegram ботов!\n\n"
        f"💰 <b>Наши цены:</b>\n"
        f"• Разработка бота: {BOT_PRICE} ⭐\n"
        f"• Хостинг на месяц: {HOSTING_PRICE} ⭐\n\n"
        f"⏱ <b>Сроки разработки:</b> от 1 до 5 дней\n\n"
        "Что бы вы хотели сделать?",
        reply_markup=get_main_keyboard()
    )

# Команда админа
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав администратора.")
        return
    
    await message.answer(
        "👑 <b>Админ-панель</b>\n\n"
        f"👥 Всего пользователей: {len(users_db)}\n"
        f"📦 Всего заказов: {len(orders_db)}\n"
        f"💬 Обращений в поддержку: {len(support_requests)}",
        reply_markup=get_admin_main_keyboard()
    )

# Админ панель
@dp.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    await callback_query.message.edit_text(
        "👑 <b>Админ-панель</b>\n\n"
        f"👥 Всего пользователей: {len(users_db)}\n"
        f"📦 Всего заказов: {len(orders_db)}\n"
        f"💬 Обращений в поддержку: {len(support_requests)}",
        reply_markup=get_admin_main_keyboard()
    )

# Рассылка
@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    admin_states[ADMIN_ID] = {"action": "waiting_broadcast_text"}
    
    await callback_query.message.edit_text(
        "📢 <b>Создание рассылки</b>\n\n"
        f"👥 Всего получателей: {len(users_db)} пользователей\n\n"
        "Отправьте текст для рассылки. Это будет чистое сообщение без кнопок.\n\n"
        "Поддерживается HTML-форматирование.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_panel")]
        ])
    )

# Статистика
@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    # Подсчет статистики
    total_users = len(users_db)
    total_orders = len(orders_db)
    
    orders_by_status = {}
    for status in ORDER_STATUSES:
        count = sum(1 for order in orders_db.values() if order.get("status") == status)
        orders_by_status[status] = count
    
    paid_orders = sum(1 for order in orders_db.values() if order.get("paid"))
    hosting_paid = sum(1 for order in orders_db.values() if order.get("hosting_paid"))
    active_support = len(support_requests)
    
    text = "📊 <b>Статистика</b>\n\n"
    text += f"👥 <b>Пользователи:</b>\n"
    text += f"• Всего: {total_users}\n\n"
    
    text += f"📦 <b>Заказы:</b>\n"
    text += f"• Всего: {total_orders}\n"
    for status, count in orders_by_status.items():
        text += f"• {ORDER_STATUSES[status]}: {count}\n"
    text += f"\n"
    
    text += f"💰 <b>Платежи:</b>\n"
    text += f"• Оплатили разработку: {paid_orders}\n"
    text += f"• Оплатили хостинг: {hosting_paid}\n\n"
    
    text += f"💬 <b>Поддержка:</b>\n"
    text += f"• Обращений: {active_support}"
    
    await callback_query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
        ])
    )

# Обработка текста для рассылки
@dp.message(F.chat.id == ADMIN_ID)
async def handle_admin_broadcast(message: types.Message):
    user_id = message.from_user.id
    
    if user_id in admin_states and admin_states[user_id]["action"] == "waiting_broadcast_text":
        broadcast_text = message.text
        
        # Сохраняем текст рассылки
        admin_states[user_id] = {
            "action": "broadcast_preview",
            "text": broadcast_text
        }
        
        # Показываем предпросмотр
        await message.answer(
            f"📢 <b>Предпросмотр рассылки:</b>\n\n"
            f"{broadcast_text}\n\n"
            f"👥 Будет отправлено {len(users_db)} пользователям",
            reply_markup=get_broadcast_confirm_keyboard()
        )
    
    # Обработка других админских сообщений
    elif user_id in admin_states:
        state = admin_states[user_id]
        
        if state["action"] == "send_link":
            order_id = state["order_id"]
            link = message.text
            
            if order_id in orders_db:
                orders_db[order_id]["link"] = link
                user_id = orders_db[order_id]["user_id"]
                
                await bot.send_message(
                    user_id,
                    f"🔗 <b>Ссылка на вашего бота готова!</b>\n\n"
                    f"Ссылка: {link}\n\n"
                    f"🤖 <b>Инструкция:</b>\n"
                    f"1. Перейдите по ссылке и протестируйте бота\n"
                    f"2. Проверьте весь функционал по ТЗ\n"
                    f"3. Если всё работает - нажмите кнопку оплаты\n\n"
                    f"⚠️ После оплаты я передам вам права на бота!",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text=f"💫 Оплатить разработку ({BOT_PRICE} ⭐)", callback_data=f"pay_bot_{order_id}")],
                        [InlineKeyboardButton(text="❌ Есть вопросы", callback_data=f"support_order_{order_id}")]
                    ])
                )
                
                await message.answer(
                    f"✅ Ссылка отправлена пользователю для заказа #{order_id}\n\n"
                    f"Ссылка: {link}"
                )
                
                del admin_states[ADMIN_ID]
            else:
                await message.answer("❌ Заказ не найден!")
        
        elif state["action"] == "reject_order":
            order_id = state["order_id"]
            reject_reason = message.text
            
            if order_id in orders_db:
                orders_db[order_id]["status"] = "rejected"
                orders_db[order_id]["reject_reason"] = reject_reason
                user_id = orders_db[order_id]["user_id"]
                
                await bot.send_message(
                    user_id,
                    f"❌ <b>Заказ #{order_id} отклонён</b>\n\n"
                    f"<b>Причина отклонения:</b>\n{reject_reason}\n\n"
                    f"Пожалуйста, свяжитесь с поддержкой для уточнения деталей или создайте новый заказ.",
                    reply_markup=get_user_order_keyboard(order_id)
                )
                
                admin_text = f"❌ <b>Заказ #{order_id} ОТКЛОНЁН</b>\n\n"
                admin_text += f"👤 Пользователь: @{orders_db[order_id]['username']} (ID: {user_id})\n"
                admin_text += f"📊 Статус: {ORDER_STATUSES['rejected']}\n"
                admin_text += f"📝 Причина: {reject_reason}\n\n"
                admin_text += f"📝 <b>ТЗ:</b>\n{orders_db[order_id]['tz'][:200]}{'...' if len(orders_db[order_id]['tz']) > 200 else ''}"
                
                await bot.send_message(ADMIN_ID, admin_text)
                
                await message.answer(
                    f"✅ Заказ #{order_id} отклонён. Причина отправлена пользователю."
                )
                
                del admin_states[ADMIN_ID]
            else:
                await message.answer("❌ Заказ не найден!")
        
        elif state["action"] == "reply_to_user":
            reply_data = admin_states[ADMIN_ID]
            user_to_reply = reply_data["user_id"]
            support_id = reply_data["support_id"]
            
            await bot.send_message(
                user_to_reply,
                f"✉️ <b>Ответ от администратора:</b>\n\n{message.text}",
                reply_markup=get_continue_dialog_keyboard(support_id)
            )
            
            if support_id in support_requests:
                support_requests[support_id]["answered"] = True
            
            await message.answer(f"✅ Ответ отправлен пользователю!")
            del admin_states[ADMIN_ID]
        
        elif state["action"] == "custom_notification":
            order_id = state["order_id"]
            notification_text = message.text
            user_id = orders_db[order_id]["user_id"]
            
            await bot.send_message(
                user_id,
                f"📢 <b>Уведомление от администратора</b>\n\n"
                f"{notification_text}",
                reply_markup=get_user_order_keyboard(order_id)
            )
            
            await message.answer(
                f"✅ Произвольное уведомление отправлено пользователю для заказа #{order_id}"
            )
            
            del admin_states[ADMIN_ID]

# Подтверждение рассылки
@dp.callback_query(F.data == "broadcast_confirm")
async def broadcast_confirm(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    if ADMIN_ID not in admin_states or admin_states[ADMIN_ID]["action"] != "broadcast_preview":
        await callback_query.message.edit_text(
            "❌ Ошибка: не найден текст рассылки",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_panel")]
            ])
        )
        return
    
    broadcast_text = admin_states[ADMIN_ID]["text"]
    
    # Отправляем сообщение о начале рассылки
    await callback_query.message.edit_text(
        f"📢 <b>Рассылка началась!</b>\n\n"
        f"👥 Всего получателей: {len(users_db)}\n"
        f"⏳ Ожидайте завершения...",
        reply_markup=None
    )
    
    # Статистика рассылки
    success_count = 0
    fail_count = 0
    
    # Отправляем сообщение каждому пользователю
    for user_id in users_db:
        try:
            await bot.send_message(
                user_id,
                broadcast_text,
                parse_mode="HTML"
            )
            success_count += 1
            await asyncio.sleep(0.05)  # Небольшая задержка чтобы не флудить
        except Exception as e:
            fail_count += 1
            print(f"Ошибка отправки пользователю {user_id}: {e}")
    
    # Очищаем состояние
    del admin_states[ADMIN_ID]
    
    # Отправляем отчет админу
    await bot.send_message(
        ADMIN_ID,
        f"📢 <b>Рассылка завершена!</b>\n\n"
        f"✅ Успешно отправлено: {success_count}\n"
        f"❌ Не удалось отправить: {fail_count}\n"
        f"👥 Всего получателей: {len(users_db)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_panel")]
        ])
    )

# Отмена рассылки
@dp.callback_query(F.data == "broadcast_cancel")
async def broadcast_cancel(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    if ADMIN_ID in admin_states:
        del admin_states[ADMIN_ID]
    
    await callback_query.message.edit_text(
        "❌ Рассылка отменена",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_panel")]
        ])
    )

# Просмотр всех заказов для админа
@dp.callback_query(F.data == "admin_orders")
async def admin_orders(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    if not orders_db:
        await callback_query.message.edit_text(
            "📦 Заказов пока нет.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
            ])
        )
        return
    
    text = "📦 <b>Список всех заказов:</b>\n\n"
    
    # Сортируем заказы по дате (сначала новые)
    sorted_orders = sorted(orders_db.items(), key=lambda x: x[1]['created_at'], reverse=True)
    
    for order_id, order in sorted_orders[:10]:  # Показываем последние 10 заказов
        status_text = ORDER_STATUSES.get(order['status'], 'Неизвестно')
        text += f"#{order_id} | @{order['username']} | {status_text} | {order['created_at']}\n"
    
    text += f"\nПоказано {min(10, len(orders_db))} из {len(orders_db)} заказов"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    # Добавляем кнопки для каждого заказа
    for order_id, _ in sorted_orders[:5]:  # Показываем первые 5 заказов для быстрого доступа
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"Заказ #{order_id}", callback_data=f"view_order_{order_id}")
        ])
    
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

# Просмотр обращений в поддержку
@dp.callback_query(F.data == "admin_support")
async def admin_support(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    if not support_requests:
        await callback_query.message.edit_text(
            "💬 Нет обращений в поддержку.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
            ])
        )
        return
    
    text = "🆘 <b>Обращения в поддержку:</b>\n\n"
    
    # Сортируем обращения по времени (сначала новые)
    sorted_requests = sorted(support_requests.items(), key=lambda x: x[1]['time'], reverse=True)
    
    for support_id, req in sorted_requests[:10]:
        status = "✅" if req.get('answered') else "⏳"
        order_info = f" (Заказ #{req['order_id']})" if 'order_id' in req else ""
        text += f"#{support_id} {status} | @{req['username']}{order_info} | {req['time'][:10]}\n"
        text += f"📝 {req['message'][:50]}...\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

# Просмотр конкретного заказа админом
@dp.callback_query(F.data.startswith("view_order_"))
async def view_order(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    order_id = int(callback_query.data.split("_")[2])
    
    if order_id in orders_db:
        order = orders_db[order_id]
        user_id = order["user_id"]
        status_text = ORDER_STATUSES.get(order['status'], 'Неизвестно')
        
        admin_text = f"🆕 <b>Заказ #{order_id}</b>\n\n"
        admin_text += f"👤 Пользователь: @{order['username']} (ID: {user_id})\n"
        admin_text += f"📅 Дата: {order['created_at']}\n"
        admin_text += f"📊 Статус: {status_text}\n"
        
        if order.get("link"):
            admin_text += f"🔗 Ссылка: {order['link']}\n"
        
        if order.get("paid"):
            admin_text += f"💰 Разработка: ✅ Оплачена\n"
            
        if order.get("hosting_paid"):
            admin_text += f"💻 Хостинг: ✅ Оплачен\n"
        
        if order.get("reject_reason"):
            admin_text += f"\n❌ <b>Причина отклонения:</b>\n{order['reject_reason']}\n"
        
        admin_text += f"\n📝 <b>ТЗ:</b>\n{order['tz'][:500]}{'...' if len(order['tz']) > 500 else ''}"
        
        await callback_query.message.edit_text(
            admin_text,
            reply_markup=get_admin_keyboard(order_id)
        )

# Обработчик заказа - сначала запрашиваем ТЗ
@dp.callback_query(F.data == "order_bot")
async def order_bot_start(callback_query: CallbackQuery):
    await callback_query.answer()
    user_id = callback_query.from_user.id
    
    # Устанавливаем состояние - ожидаем ТЗ
    user_states[user_id] = {"action": "waiting_for_tz"}
    
    await callback_query.message.edit_text(
        "📝 <b>Опишите техническое задание</b>\n\n"
        "Пожалуйста, подробно опишите:\n"
        "• Какой функционал нужен\n"
        "• Какие команды должны быть\n"
        "• Примеры похожих ботов (если есть)\n"
        "• Любые другие пожелания\n\n"
        "Отправьте ваше ТЗ одним сообщением:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_main")]
        ])
    )

# Обработка полученного ТЗ
@dp.message(F.text)
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    
    # Добавляем пользователя в базу при любом сообщении
    users_db.add(user_id)
    
    # Обработка ТЗ для нового заказа
    if user_id in user_states and user_states[user_id]["action"] == "waiting_for_tz":
        tz_text = message.text
        
        # Анимация создания заказа
        loading_msg = await message.answer("🔄 Создаю ваш заказ...")
        await asyncio.sleep(1)
        
        # Создаем заказ
        order_id = len(orders_db) + 1
        
        orders_db[order_id] = {
            "user_id": user_id,
            "username": message.from_user.username,
            "tz": tz_text,
            "status": "pending",
            "link": None,
            "paid": False,
            "hosting_paid": False,
            "reject_reason": None,
            "created_at": datetime.now().strftime("%d.%m.%Y %H:%M")
        }
        user_orders[user_id] = order_id
        
        # Уведомляем админа с полным ТЗ
        admin_text = f"🆕 <b>НОВЫЙ ЗАКАЗ #{order_id}</b>\n\n"
        admin_text += f"👤 Пользователь: @{message.from_user.username} (ID: {user_id})\n"
        admin_text += f"📅 Дата: {orders_db[order_id]['created_at']}\n"
        admin_text += f"📊 Статус: {ORDER_STATUSES['pending']}\n\n"
        admin_text += f"📝 <b>ТЕХНИЧЕСКОЕ ЗАДАНИЕ:</b>\n{tz_text}"
        
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=get_admin_keyboard(order_id))
        
        # Ответ пользователю
        await loading_msg.edit_text(
            f"✅ <b>Заказ #{order_id} создан!</b>\n\n"
            f"📊 Статус: {ORDER_STATUSES['pending']}\n"
            f"⏱ Ожидаемое время разработки: 1-5 дней\n\n"
            f"📝 <b>Ваше ТЗ:</b>\n{tz_text[:200]}{'...' if len(tz_text) > 200 else ''}\n\n"
            "Как только администратор начнет работу, вы получите уведомление.",
            reply_markup=get_user_order_keyboard(order_id)
        )
        
        # Очищаем состояние
        del user_states[user_id]
        return
    
    # Обработка сообщений в поддержку от пользователей
    elif user_id in user_states and user_states[user_id]["action"] in ["support_message", "order_support", "continue_support"]:
        state = user_states[user_id]
        
        if state["action"] == "support_message":
            # Отправляем админу
            support_id = len(support_requests) + 1
            support_requests[support_id] = {
                "user_id": user_id,
                "username": message.from_user.username,
                "message": message.text,
                "time": datetime.now().strftime("%d.%m.%Y %H:%M"),
                "answered": False,
                "active": True
            }
            active_support_chats[user_id] = support_id
            
            await bot.send_message(
                ADMIN_ID,
                f"🆘 <b>Обращение в поддержку #{support_id}</b>\n\n"
                f"👤 От: @{message.from_user.username} (ID: {user_id})\n"
                f"📅 Время: {support_requests[support_id]['time']}\n"
                f"📝 Сообщение:\n{message.text}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✏️ Ответить", callback_data=f"reply_support_{support_id}")]
                ])
            )
            
            await message.answer(
                "✅ Ваше сообщение отправлено администратору. Ожидайте ответа!",
                reply_markup=get_main_keyboard()
            )
            del user_states[user_id]
            
        elif state["action"] == "order_support":
            order_id = state["order_id"]
            support_id = len(support_requests) + 1
            support_requests[support_id] = {
                "user_id": user_id,
                "username": message.from_user.username,
                "order_id": order_id,
                "message": message.text,
                "time": datetime.now().strftime("%d.%m.%Y %H:%M"),
                "answered": False,
                "active": True
            }
            active_support_chats[user_id] = support_id
            
            await bot.send_message(
                ADMIN_ID,
                f"🆘 <b>Обращение по заказу #{order_id}</b>\n\n"
                f"👤 От: @{message.from_user.username} (ID: {user_id})\n"
                f"📅 Время: {support_requests[support_id]['time']}\n"
                f"📝 Сообщение:\n{message.text}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✏️ Ответить", callback_data=f"reply_support_{support_id}")]
                ])
            )
            
            await message.answer(
                f"✅ Ваш вопрос по заказу #{order_id} отправлен администратору. Ожидайте ответа!",
                reply_markup=get_main_keyboard()
            )
            del user_states[user_id]
        
        elif state["action"] == "continue_support":
            support_id = state["support_id"]
            if support_id in support_requests:
                support_requests[support_id]["message"] += f"\n\n[Продолжение] {message.text}"
                support_requests[support_id]["time"] = datetime.now().strftime("%d.%m.%Y %H:%M")
                support_requests[support_id]["answered"] = False
                
                order_info = ""
                if "order_id" in support_requests[support_id]:
                    order_info = f" по заказу #{support_requests[support_id]['order_id']}"
                
                await bot.send_message(
                    ADMIN_ID,
                    f"🆘 <b>Продолжение диалога #{support_id}{order_info}</b>\n\n"
                    f"👤 От: @{message.from_user.username} (ID: {user_id})\n"
                    f"📅 Время: {support_requests[support_id]['time']}\n"
                    f"📝 Сообщение:\n{message.text}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✏️ Ответить", callback_data=f"reply_support_{support_id}")]
                    ])
                )
                
                await message.answer(
                    "✅ Ваше сообщение отправлено администратору. Ожидайте ответа!",
                    reply_markup=get_continue_dialog_keyboard(support_id)
                )
        return

# Продолжить диалог
@dp.callback_query(F.data.startswith("continue_dialog_"))
async def continue_dialog(callback_query: CallbackQuery):
    await callback_query.answer()
    support_id = int(callback_query.data.split("_")[2])
    user_id = callback_query.from_user.id
    
    if support_id in support_requests and support_requests[support_id]["user_id"] == user_id:
        user_states[user_id] = {"action": "continue_support", "support_id": support_id}
        
        await callback_query.message.edit_text(
            "📝 Напишите ваше сообщение. Диалог с администратором продолжается.\n\n"
            "Мы ответим вам в ближайшее время!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")]
            ])
        )
    else:
        await callback_query.message.edit_text(
            "❌ Диалог не найден или у вас нет доступа к нему.",
            reply_markup=get_back_to_main_keyboard()
        )

# Просмотр заказов
@dp.callback_query(F.data == "my_orders")
async def my_orders(callback_query: CallbackQuery):
    await callback_query.answer()
    user_id = callback_query.from_user.id
    
    # Анимация
    loading_msg = await callback_query.message.edit_text("🔄 Загружаю ваши заказы...")
    await asyncio.sleep(0.5)
    
    if user_id in user_orders:
        order_id = user_orders[user_id]
        order = orders_db.get(order_id, {})
        
        # Получаем правильный статус из словаря
        status_key = order.get('status', 'pending')
        status_text = ORDER_STATUSES.get(status_key, "⏳ Ожидание")
        
        text = f"📋 <b>Заказ #{order_id}</b>\n\n"
        text += f"📅 Дата создания: {order.get('created_at', 'Неизвестно')}\n"
        text += f"📊 Статус: {status_text}\n"
        
        if order.get("link"):
            text += f"🔗 Ссылка: {order['link']}\n"
        
        if order.get("paid"):
            text += f"💰 Разработка: ✅ Оплачена\n"
            
        if order.get("hosting_paid"):
            text += f"💻 Хостинг: ✅ Оплачен\n"
        
        if order.get("reject_reason"):
            text += f"\n❌ <b>Причина отклонения:</b>\n{order['reject_reason']}\n"
        
        text += f"\n📝 <b>ТЗ:</b>\n{order.get('tz', 'Не указано')[:200]}{'...' if len(order.get('tz', '')) > 200 else ''}"
        
        await loading_msg.edit_text(text, reply_markup=get_user_order_keyboard(order_id))
    else:
        await loading_msg.edit_text(
            "У вас пока нет заказов. Хотите создать первый?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📦 Заказать разработку", callback_data="order_bot")],
                [InlineKeyboardButton(text="🔙 На главную", callback_data="back_to_main")]
            ])
        )

# Админские колбэки для изменения статуса
@dp.callback_query(F.data.startswith("status_"))
async def change_status(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id != ADMIN_ID:
        await bot.send_message(callback_query.from_user.id, "❌ У вас нет прав администратора.")
        return
    
    # Анимация изменения статуса
    await callback_query.message.edit_text("🔄 Обновляю статус...")
    await asyncio.sleep(0.5)
    
    parts = callback_query.data.split("_")
    status = parts[1]  # development, pending, completed
    order_id = int(parts[2])
    
    if order_id in orders_db:
        orders_db[order_id]["status"] = status
        user_id = orders_db[order_id]["user_id"]
        
        # Получаем правильный статус из словаря
        status_text = ORDER_STATUSES.get(status, "⏳ Ожидание")
        
        # Разные сообщения для разных статусов
        status_messages = {
            "development": "🔧 Разработка началась! Мы приступили к работе над вашим ботом.",
            "completed": "✅ Бот готов! Администратор скоро отправит вам ссылку для проверки.",
            "pending": "⏳ Заказ в очереди на разработку."
        }
        
        message_text = status_messages.get(status, f"Статус вашего заказа #{order_id} изменен")
        
        # Отправляем уведомление пользователю с правильным статусом
        await bot.send_message(
            user_id,
            f"🔄 <b>Статус вашего заказа #{order_id} изменен!</b>\n\n"
            f"{message_text}\n\n"
            f"<b>Новый статус: {status_text}</b>",
            reply_markup=get_user_order_keyboard(order_id)
        )
        
        # Обновляем сообщение админа
        admin_text = f"🆕 <b>Заказ #{order_id}</b>\n\n"
        admin_text += f"👤 Пользователь: @{orders_db[order_id]['username']} (ID: {user_id})\n"
        admin_text += f"📊 Статус: {status_text}\n\n"
        admin_text += f"📝 <b>ТЗ:</b>\n{orders_db[order_id]['tz'][:200]}{'...' if len(orders_db[order_id]['tz']) > 200 else ''}"
        
        await callback_query.message.edit_text(
            admin_text,
            reply_markup=get_admin_keyboard(order_id)
        )

# Отправка ссылки пользователю
@dp.callback_query(F.data.startswith("send_link_"))
async def send_link_prompt(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    order_id = int(callback_query.data.split("_")[2])
    
    if order_id not in orders_db:
        await bot.send_message(ADMIN_ID, "❌ Заказ не найден!")
        return
    
    admin_states[ADMIN_ID] = {"action": "send_link", "order_id": order_id}
    
    await bot.send_message(
        ADMIN_ID,
        f"✏️ Введите ссылку на бота для заказа #{order_id}:"
    )

# Отклонение заказа с запросом причины
@dp.callback_query(F.data.startswith("reject_order_"))
async def reject_order_prompt(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    order_id = int(callback_query.data.split("_")[2])
    
    if order_id not in orders_db:
        await bot.send_message(ADMIN_ID, "❌ Заказ не найден!")
        return
    
    admin_states[ADMIN_ID] = {"action": "reject_order", "order_id": order_id}
    
    await bot.send_message(
        ADMIN_ID,
        f"✏️ Введите причину отклонения заказа #{order_id}:"
    )

# Уведомление пользователя
@dp.callback_query(F.data.startswith("notify_user_"))
async def notify_user_menu(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    order_id = int(callback_query.data.split("_")[2])
    
    if order_id not in orders_db:
        await bot.send_message(ADMIN_ID, "❌ Заказ не найден!")
        return
    
    await callback_query.message.edit_text(
        f"📢 <b>Уведомление пользователя для заказа #{order_id}</b>\n\n"
        f"Выберите тип уведомления:",
        reply_markup=get_notification_type_keyboard(order_id)
    )

@dp.callback_query(F.data.startswith("notify_status_"))
async def notify_status(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    order_id = int(callback_query.data.split("_")[2])
    
    if order_id in orders_db:
        user_id = orders_db[order_id]["user_id"]
        status_text = ORDER_STATUSES.get(orders_db[order_id]["status"], "Неизвестно")
        
        await bot.send_message(
            user_id,
            f"📢 <b>Уведомление о статусе заказа #{order_id}</b>\n\n"
            f"Текущий статус вашего заказа: {status_text}\n\n"
            f"Спасибо за ожидание! Если у вас есть вопросы, обратитесь в поддержку.",
            reply_markup=get_user_order_keyboard(order_id)
        )
        
        await callback_query.message.edit_text(
            f"✅ Уведомление о статусе отправлено пользователю для заказа #{order_id}",
            reply_markup=get_admin_keyboard(order_id)
        )

@dp.callback_query(F.data.startswith("notify_payment_"))
async def notify_payment(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    order_id = int(callback_query.data.split("_")[2])
    
    if order_id in orders_db:
        user_id = orders_db[order_id]["user_id"]
        
        payment_text = "💳 <b>Напоминание об оплате</b>\n\n"
        
        if not orders_db[order_id]["paid"] and orders_db[order_id]["link"]:
            payment_text += f"Ваш бот для заказа #{order_id} готов и ожидает оплаты.\n\n"
            payment_text += f"💰 Стоимость разработки: {BOT_PRICE} ⭐\n\n"
            payment_text += "После оплаты вы получите полный код бота и права на него."
            
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"💫 Оплатить ({BOT_PRICE} ⭐)", callback_data=f"pay_bot_{order_id}")],
                [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_main")]
            ])
            
        elif orders_db[order_id]["paid"] and not orders_db[order_id]["hosting_paid"]:
            payment_text += f"Ваш бот для заказа #{order_id} уже оплачен, но хостинг еще не активирован.\n\n"
            payment_text += f"💻 Стоимость хостинга на месяц: {HOSTING_PRICE} ⭐\n\n"
            payment_text += "После оплаты хостинга бот будет работать 24/7."
            
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"💻 Оплатить хостинг ({HOSTING_PRICE} ⭐)", callback_data=f"pay_hosting_{order_id}")],
                [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_main")]
            ])
        else:
            payment_text += f"По заказу #{order_id} все платежи завершены. Спасибо!"
            reply_markup = get_user_order_keyboard(order_id)
        
        await bot.send_message(user_id, payment_text, reply_markup=reply_markup)
        
        await callback_query.message.edit_text(
            f"✅ Напоминание об оплате отправлено пользователю для заказа #{order_id}",
            reply_markup=get_admin_keyboard(order_id)
        )

@dp.callback_query(F.data.startswith("notify_link_"))
async def notify_link(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    order_id = int(callback_query.data.split("_")[2])
    
    if order_id in orders_db and orders_db[order_id]["link"]:
        user_id = orders_db[order_id]["user_id"]
        link = orders_db[order_id]["link"]
        
        await bot.send_message(
            user_id,
            f"🔗 <b>Ссылка на вашего бота</b>\n\n"
            f"Ссылка для заказа #{order_id}:\n{link}\n\n"
            f"Если вы еще не тестировали бота, самое время это сделать!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"💫 Оплатить ({BOT_PRICE} ⭐)", callback_data=f"pay_bot_{order_id}")],
                [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_main")]
            ])
        )
        
        await callback_query.message.edit_text(
            f"✅ Ссылка повторно отправлена пользователю для заказа #{order_id}",
            reply_markup=get_admin_keyboard(order_id)
        )
    else:
        await callback_query.message.edit_text(
            f"❌ Для заказа #{order_id} еще нет ссылки. Сначала отправьте ссылку через кнопку '🔗 Отправить ссылку'",
            reply_markup=get_admin_keyboard(order_id)
        )

@dp.callback_query(F.data.startswith("notify_custom_"))
async def notify_custom_prompt(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    order_id = int(callback_query.data.split("_")[2])
    
    if order_id not in orders_db:
        await bot.send_message(ADMIN_ID, "❌ Заказ не найден!")
        return
    
    admin_states[ADMIN_ID] = {"action": "custom_notification", "order_id": order_id}
    
    await bot.send_message(
        ADMIN_ID,
        f"✏️ Введите текст произвольного уведомления для пользователя по заказу #{order_id}:"
    )

# Возврат к заказу
@dp.callback_query(F.data.startswith("back_to_order_"))
async def back_to_order(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    order_id = int(callback_query.data.split("_")[2])
    
    if order_id in orders_db:
        user_id = orders_db[order_id]["user_id"]
        status_text = ORDER_STATUSES.get(orders_db[order_id]["status"], "Неизвестно")
        
        admin_text = f"🆕 <b>Заказ #{order_id}</b>\n\n"
        admin_text += f"👤 Пользователь: @{orders_db[order_id]['username']} (ID: {user_id})\n"
        admin_text += f"📊 Статус: {status_text}\n\n"
        admin_text += f"📝 <b>ТЗ:</b>\n{orders_db[order_id]['tz'][:200]}{'...' if len(orders_db[order_id]['tz']) > 200 else ''}"
        
        await callback_query.message.edit_text(
            admin_text,
            reply_markup=get_admin_keyboard(order_id)
        )

# Оплата разработки бота
@dp.callback_query(F.data.startswith("pay_bot_"))
async def pay_bot(callback_query: CallbackQuery):
    await callback_query.answer()
    order_id = int(callback_query.data.split("_")[2])
    user_id = callback_query.from_user.id
    
    if user_id != orders_db.get(order_id, {}).get("user_id"):
        await bot.send_message(user_id, "❌ Это не ваш заказ.")
        return
    
    if orders_db[order_id]["paid"]:
        await bot.send_message(user_id, "✅ Разработка уже оплачена!")
        return
    
    # Анимация перед оплатой
    await callback_query.message.edit_text("🔄 Подготавливаю счет...")
    await asyncio.sleep(0.5)
    
    # Отправляем инвойс для оплаты разработки звездами
    await bot.send_invoice(
        chat_id=user_id,
        title=f"💫 Оплата разработки бота #{order_id}",
        description="Оплата разработки Telegram бота согласно техническому заданию.",
        payload=f"bot_{order_id}",
        provider_token="",  # Для звезд оставляем пустым
        currency="XTR",
        prices=[types.LabeledPrice(label="Разработка бота", amount=BOT_PRICE)]
    )

# Оплата хостинга
@dp.callback_query(F.data.startswith("pay_hosting_"))
async def pay_hosting(callback_query: CallbackQuery):
    await callback_query.answer()
    order_id = int(callback_query.data.split("_")[2])
    user_id = callback_query.from_user.id
    
    if user_id != orders_db.get(order_id, {}).get("user_id"):
        await bot.send_message(user_id, "❌ Это не ваш заказ.")
        return
    
    if orders_db[order_id]["hosting_paid"]:
        await bot.send_message(user_id, "✅ Хостинг уже оплачен!")
        return
    
    # Анимация перед оплатой
    await callback_query.message.edit_text("🔄 Подготавливаю счет...")
    await asyncio.sleep(0.5)
    
    # Отправляем инвойс для оплаты хостинга звездами
    await bot.send_invoice(
        chat_id=user_id,
        title=f"💻 Оплата хостинга для бота #{order_id}",
        description="Оплата хостинга на 1 месяц. После оплаты бот будет работать 24/7.",
        payload=f"hosting_{order_id}",
        provider_token="",  # Для звезд оставляем пустым
        currency="XTR",
        prices=[types.LabeledPrice(label="Хостинг (1 месяц)", amount=HOSTING_PRICE)]
    )

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_q: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload
    
    if payload.startswith("bot_"):
        # Оплата разработки
        order_id = int(payload.split("_")[1])
        user_id = message.from_user.id
        
        if user_id == orders_db.get(order_id, {}).get("user_id"):
            orders_db[order_id]["paid"] = True
            
            # Анимация успешной оплаты
            await message.answer("🔄 Обрабатываю платеж...")
            await asyncio.sleep(1)
            
            await message.answer(
                "✅ <b>Оплата разработки прошла успешно!</b>\n\n"
                "Администратор скоро передаст вам права на бота.\n\n"
                "💡 <b>Что такое хостинг для бота?</b>\n"
                "Хостинг - это сервер, где бот работает 24/7 без перерывов.\n"
                "Без хостинга бот будет работать только пока включен ваш компьютер.\n\n"
                f"Рекомендуем оплатить хостинг на месяц ({HOSTING_PRICE} ⭐), чтобы бот работал постоянно!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=f"💻 Оплатить хостинг ({HOSTING_PRICE} ⭐)", callback_data=f"pay_hosting_{order_id}")],
                    [InlineKeyboardButton(text="📦 Сделать еще заказ", callback_data="order_bot")],
                    [InlineKeyboardButton(text="🔙 На главную", callback_data="back_to_main")]
                ])
            )
            
            # Уведомляем админа
            await bot.send_message(
                ADMIN_ID,
                f"💰 <b>Оплата разработки</b>\n\n"
                f"Пользователь @{message.from_user.username} оплатил разработку заказа #{order_id}\n"
                f"Сумма: {BOT_PRICE} ⭐\n\n"
                f"Передайте права на бота пользователю!"
            )
    
    elif payload.startswith("hosting_"):
        # Оплата хостинга
        order_id = int(payload.split("_")[1])
        user_id = message.from_user.id
        
        if user_id == orders_db.get(order_id, {}).get("user_id"):
            orders_db[order_id]["hosting_paid"] = True
            
            # Анимация успешной оплаты
            await message.answer("🔄 Обрабатываю платеж...")
            await asyncio.sleep(1)
            
            await message.answer(
                "✅ <b>Оплата хостинга прошла успешно!</b>\n\n"
                "🎉 Отлично! Теперь ваш бот будет работать 24/7 в течение месяца.\n\n"
                "• Сервер работает круглосуточно\n"
                "• Автоматические перезапуски при сбоях\n"
                "• Резервное копирование\n"
                "• Техническая поддержка\n\n"
                "Спасибо за сотрудничество! 🤝",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📦 Сделать еще заказ", callback_data="order_bot")],
                    [InlineKeyboardButton(text="🔙 На главную", callback_data="back_to_main")]
                ])
            )
            
            # Уведомляем админа
            await bot.send_message(
                ADMIN_ID,
                f"💰 <b>Оплата хостинга</b>\n\n"
                f"Пользователь @{message.from_user.username} оплатил хостинг для заказа #{order_id}\n"
                f"Сумма: {HOSTING_PRICE} ⭐\n"
                f"Срок: 1 месяц"
            )

# Получение ссылки
@dp.callback_query(F.data.startswith("get_link_"))
async def get_link(callback_query: CallbackQuery):
    await callback_query.answer()
    order_id = int(callback_query.data.split("_")[2])
    user_id = callback_query.from_user.id
    
    if user_id == orders_db.get(order_id, {}).get("user_id"):
        link = orders_db[order_id].get("link")
        if link:
            await bot.send_message(
                user_id,
                f"🔗 <b>Ссылка на бота:</b>\n{link}\n\n"
                f"После проверки нажмите кнопку оплаты ниже:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=f"💫 Оплатить ({BOT_PRICE} ⭐)", callback_data=f"pay_bot_{order_id}")],
                    [InlineKeyboardButton(text="📦 Сделать еще заказ", callback_data="order_bot")],
                    [InlineKeyboardButton(text="🔙 На главную", callback_data="back_to_main")]
                ])
            )
        else:
            await bot.send_message(user_id, "❌ Ссылка еще не готова.")
    else:
        await bot.send_message(user_id, "❌ Это не ваш заказ.")

# Поддержка
@dp.callback_query(F.data == "support")
async def support_menu(callback_query: CallbackQuery):
    await callback_query.answer()
    await callback_query.message.edit_text(
        "🆘 <b>Центр поддержки</b>\n\n"
        "Выберите нужный раздел:",
        reply_markup=get_support_keyboard()
    )

@dp.callback_query(F.data == "faq")
async def faq_menu(callback_query: CallbackQuery):
    await callback_query.answer()
    await callback_query.message.edit_text(
        "❓ <b>Часто задаваемые вопросы</b>\n\n"
        "Выберите интересующий вас вопрос:",
        reply_markup=get_faq_keyboard()
    )

@dp.callback_query(F.data == "faq_time")
async def faq_time(callback_query: CallbackQuery):
    await callback_query.answer()
    await callback_query.message.edit_text(
        "⏱ <b>Сроки разработки</b>\n\n"
        "• Разработка бота занимает от 1 до 5 дней\n"
        "• Срок зависит от сложности проекта\n"
        "• Вы можете отслеживать статус в разделе 'Мои заказы'\n"
        "• О любых задержках мы уведомляем заранее",
        reply_markup=get_back_to_main_keyboard()
    )

@dp.callback_query(F.data == "faq_payment")
async def faq_payment(callback_query: CallbackQuery):
    await callback_query.answer()
    await callback_query.message.edit_text(
        "💰 <b>Оплата</b>\n\n"
        f"• Разработка бота: {BOT_PRICE} ⭐\n"
        f"• Хостинг на месяц: {HOSTING_PRICE} ⭐\n"
        "• Оплата происходит через Telegram Stars\n"
        "• Сначала оплачивается разработка после проверки\n"
        "• Затем можно оплатить хостинг",
        reply_markup=get_back_to_main_keyboard()
    )

@dp.callback_query(F.data == "faq_include")
async def faq_include(callback_query: CallbackQuery):
    await callback_query.answer()
    await callback_query.message.edit_text(
        "🔧 <b>Что входит в разработку</b>\n\n"
        "• Индивидуальный код бота\n"
        "• Настройка базового функционала\n"
        "• Тестирование\n"
        "• Инструкция по использованию\n"
        "• Передача прав на бота после оплаты\n"
        "• 3 дня бесплатной поддержки после сдачи",
        reply_markup=get_back_to_main_keyboard()
    )

@dp.callback_query(F.data == "faq_hosting")
async def faq_hosting(callback_query: CallbackQuery):
    await callback_query.answer()
    await callback_query.message.edit_text(
        "💻 <b>Что такое хостинг для Telegram бота?</b>\n\n"
        "Хостинг - это удаленный сервер, который работает 24/7.\n\n"
        "🔹 <b>Зачем нужен хостинг?</b>\n"
        "• Без хостинга бот работает только пока включен ваш компьютер\n"
        "• Хостинг обеспечивает круглосуточную работу бота\n"
        "• Автоматический перезапуск при сбоях\n"
        "• Высокая скорость ответов\n\n"
        f"🔹 <b>Наш хостинг ({HOSTING_PRICE} ⭐/мес):</b>\n"
        "• Работа 24/7 без перерывов\n"
        "• Автоматическое резервное копирование\n"
        "• Защита от DDoS-атак\n"
        "• Техническая поддержка\n\n"
        "Оплачивается после разработки бота.",
        reply_markup=get_back_to_main_keyboard()
    )

@dp.callback_query(F.data == "write_to_admin")
async def write_to_admin(callback_query: CallbackQuery):
    await callback_query.answer()
    user_id = callback_query.from_user.id
    user_states[user_id] = {"action": "support_message"}
    
    await callback_query.message.edit_text(
        "📝 Напишите ваше сообщение для администратора.\n\n"
        "Мы ответим вам в ближайшее время!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="support")]
        ])
    )

@dp.callback_query(F.data.startswith("support_order_"))
async def support_order(callback_query: CallbackQuery):
    await callback_query.answer()
    order_id = int(callback_query.data.split("_")[2])
    user_id = callback_query.from_user.id
    
    user_states[user_id] = {"action": "order_support", "order_id": order_id}
    
    await callback_query.message.edit_text(
        f"📝 Напишите ваш вопрос по заказу #{order_id}.\n\n"
        "Мы ответим вам в ближайшее время!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="my_orders")]
        ])
    )

@dp.callback_query(F.data.startswith("reply_support_"))
async def reply_to_support(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    support_id = int(callback_query.data.split("_")[2])
    
    if support_id not in support_requests:
        await bot.send_message(ADMIN_ID, "❌ Обращение не найдено!")
        return
    
    user_id = support_requests[support_id]["user_id"]
    
    admin_states[ADMIN_ID] = {"action": "reply_to_user", "user_id": user_id, "support_id": support_id}
    
    order_info = ""
    if "order_id" in support_requests[support_id]:
        order_info = f" по заказу #{support_requests[support_id]['order_id']}"
    
    await bot.send_message(
        ADMIN_ID,
        f"✏️ Напишите ответ пользователю @{support_requests[support_id]['username']}{order_info}:"
    )

# Навигация
@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback_query: CallbackQuery):
    await callback_query.answer()
    
    if callback_query.from_user.id == ADMIN_ID:
        # Для админа показываем админ-панель
        await callback_query.message.edit_text(
            "👑 <b>Админ-панель</b>\n\n"
            f"👥 Всего пользователей: {len(users_db)}\n"
            f"📦 Всего заказов: {len(orders_db)}\n"
            f"💬 Обращений в поддержку: {len(support_requests)}",
            reply_markup=get_admin_main_keyboard()
        )
    else:
        # Для обычных пользователей показываем главное меню
        await callback_query.message.edit_text(
            "👋 Добро пожаловать в магазин разработки Telegram ботов!\n\n"
            f"💰 <b>Наши цены:</b>\n"
            f"• Разработка бота: {BOT_PRICE} ⭐\n"
            f"• Хостинг на месяц: {HOSTING_PRICE} ⭐\n\n"
            f"⏱ <b>Сроки разработки:</b> от 1 до 5 дней\n\n"
            "Что бы вы хотели сделать?",
            reply_markup=get_main_keyboard()
        )

@dp.callback_query(F.data == "back_to_support")
async def back_to_support(callback_query: CallbackQuery):
    await callback_query.answer()
    await callback_query.message.edit_text(
        "🆘 <b>Центр поддержки</b>\n\n"
        "Выберите нужный раздел:",
        reply_markup=get_support_keyboard()
    )

# Запуск бота
async def main():
    logging.basicConfig(level=logging.INFO)
    print("🤖 Бот запущен и готов к работе!")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print(f"💰 Цены: Разработка {BOT_PRICE} ⭐, Хостинг {HOSTING_PRICE} ⭐")
    print(f"👥 Пользователей в базе: {len(users_db)}")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
