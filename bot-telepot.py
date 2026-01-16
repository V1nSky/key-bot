import telepot
from telepot.loop import MessageLoop
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
import time
import os
from dotenv import load_dotenv
from database import Database
from key_generator import KeyGenerator

load_dotenv()

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x]

# Инициализация
bot = telepot.Bot(BOT_TOKEN)
db = Database()
key_gen = KeyGenerator()

print("Бот запущен!")


# ============= КЛАВИАТУРЫ =============

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Купить ключ", callback_data="buy_key")],
        [InlineKeyboardButton(text="💳 Способы оплаты", callback_data="payment_methods")],
        [InlineKeyboardButton(text="📦 Мои покупки", callback_data="my_purchases")],
        [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")]
    ])


def admin_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="💰 Новые оплаты", callback_data="admin_payments")],
        [InlineKeyboardButton(text="🔑 Управление ключами", callback_data="admin_keys")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="start")]
    ])


def payment_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"paid_{order_id}")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="start")]
    ])


def back_to_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="start")]
    ])


def confirm_payment_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{order_id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_id}")]
    ])


# ============= ОБРАБОТЧИКИ =============

def handle(msg):
    content_type, chat_type, chat_id = telepot.glance(msg)
    
    if content_type != 'text':
        return
    
    text = msg.get('text', '')
    user_id = msg['from']['id']
    username = msg['from'].get('username', 'Пользователь')
    
    # Регистрация пользователя
    db.add_user(user_id, username)
    
    # Команды
    if text == '/start':
        welcome_text = f"""
👋 Добро пожаловать, {msg['from'].get('first_name', 'друг')}!

Это бот для автоматической продажи цифровых ключей.

Выберите действие:
"""
        if user_id in ADMIN_IDS:
            welcome_text += "\n🔧 Вы авторизованы как администратор"
        
        bot.sendMessage(chat_id, welcome_text, reply_markup=main_menu_kb())
    
    elif text == '/admin':
        if user_id not in ADMIN_IDS:
            bot.sendMessage(chat_id, "❌ У вас нет доступа к админ-панели")
            return
        
        bot.sendMessage(chat_id, "🔧 Админ-панель\n\nВыберите действие:", reply_markup=admin_menu_kb())
    
    elif text.startswith('/addkey '):
        if user_id not in ADMIN_IDS:
            return
        
        key_value = text.replace('/addkey ', '').strip()
        if db.add_key(key_value):
            bot.sendMessage(chat_id, f"✅ Ключ {key_value} добавлен")
        else:
            bot.sendMessage(chat_id, "❌ Ключ уже существует или ошибка")
    
    elif text.startswith('/addkeys'):
        if user_id not in ADMIN_IDS:
            return
        
        parts = text.split()
        count = int(parts[1]) if len(parts) > 1 else 1
        
        added = 0
        for _ in range(count):
            key_value = key_gen.generate()
            if db.add_key(key_value):
                added += 1
        
        bot.sendMessage(chat_id, f"✅ Добавлено {added} ключей")
    
    elif text == '/listkeys':
        if user_id not in ADMIN_IDS:
            return
        
        keys = db.get_all_keys()
        
        text = f"🔑 Всего ключей: {len(keys)}\n\n"
        for key in keys[:20]:
            status = "✅" if key['is_used'] == 0 else "❌"
            text += f"{status} `{key['key_value']}`\n"
        
        if len(keys) > 20:
            text += f"\n... и ещё {len(keys) - 20}"
        
        bot.sendMessage(chat_id, text, parse_mode='Markdown')


def handle_callback(msg):
    query_id, from_id, data = telepot.glance(msg, flavor='callback_query')
    chat_id = msg['message']['chat']['id']
    message_id = msg['message']['message_id']
    
    # Главное меню
    if data == 'start':
        bot.editMessageText(
            (chat_id, message_id),
            "👋 Главное меню\n\nВыберите действие:",
            reply_markup=main_menu_kb()
        )
        bot.answerCallbackQuery(query_id)
    
    # Купить ключ
    elif data == 'buy_key':
        available_keys = db.get_available_keys_count()
        
        if available_keys == 0:
            bot.answerCallbackQuery(query_id, text="❌ К сожалению, ключи закончились", show_alert=True)
            return
        
        price = 500
        order_id = db.create_order(from_id, price)
        
        payment_text = f"""
🔑 Покупка ключа

💰 Цена: {price} ₽
📦 Доступно ключей: {available_keys}

📋 Реквизиты для оплаты:

💳 Карта СБП: 2200 7007 1234 5678
👤 Получатель: Иван И.
💬 Комментарий: ORDER{order_id}

⚠️ ВАЖНО: Обязательно укажите комментарий ORDER{order_id}

После оплаты нажмите кнопку "Я оплатил"
"""
        
        bot.editMessageText((chat_id, message_id), payment_text, reply_markup=payment_kb(order_id))
        bot.answerCallbackQuery(query_id)
    
    # Я оплатил
    elif data.startswith('paid_'):
        order_id = int(data.split('_')[1])
        order = db.get_order(order_id)
        
        if not order:
            bot.answerCallbackQuery(query_id, text="❌ Заказ не найден", show_alert=True)
            return
        
        if order['status'] == 'confirmed':
            bot.answerCallbackQuery(query_id, text="✅ Этот заказ уже подтверждён", show_alert=True)
            return
        
        db.update_order_status(order_id, 'pending')
        
        bot.editMessageText(
            (chat_id, message_id),
            "✅ Спасибо! Ваша оплата отправлена на проверку.\n\n"
            "⏳ Обычно проверка занимает 5-15 минут.\n"
            "Как только платёж подтвердится, вы получите ключ автоматически.",
            reply_markup=back_to_menu_kb()
        )
        
        # Уведомление админам
        for admin_id in ADMIN_IDS:
            try:
                bot.sendMessage(
                    admin_id,
                    f"💰 Новая оплата!\n\n"
                    f"📝 Заказ: ORDER{order_id}\n"
                    f"👤 Пользователь: {from_id}\n"
                    f"💵 Сумма: {order['amount']} ₽",
                    reply_markup=confirm_payment_kb(order_id)
                )
            except Exception as e:
                print(f"Ошибка отправки админу {admin_id}: {e}")
        
        bot.answerCallbackQuery(query_id)
    
    # Способы оплаты
    elif data == 'payment_methods':
        text = """
💳 Способы оплаты

Мы принимаем оплату только внутри РФ:

✅ СБП (Система быстрых платежей)
✅ Банковская карта РФ
✅ ЮMoney (по запросу)

❌ Криптовалюта не принимается
❌ Иностранные карты не принимаются
"""
        bot.editMessageText((chat_id, message_id), text, reply_markup=back_to_menu_kb())
        bot.answerCallbackQuery(query_id)
    
    # Мои покупки
    elif data == 'my_purchases':
        purchases = db.get_user_purchases(from_id)
        
        if not purchases:
            text = "📦 У вас пока нет покупок"
        else:
            text = "📦 Ваши покупки:\n\n"
            for p in purchases:
                text += f"🔑 `{p['key_value']}`\n"
                text += f"📅 {p['purchase_date']}\n"
                text += "─" * 30 + "\n"
        
        bot.editMessageText((chat_id, message_id), text, reply_markup=back_to_menu_kb(), parse_mode='Markdown')
        bot.answerCallbackQuery(query_id)
    
    # Поддержка
    elif data == 'support':
        text = """
🆘 Поддержка

По всем вопросам обращайтесь:
📧 @support_username

Время ответа: обычно в течение 1 часа
"""
        bot.editMessageText((chat_id, message_id), text, reply_markup=back_to_menu_kb())
        bot.answerCallbackQuery(query_id)
    
    # ========== АДМИН ПАНЕЛЬ ==========
    
    elif data == 'admin_stats':
        if from_id not in ADMIN_IDS:
            bot.answerCallbackQuery(query_id, text="❌ Доступ запрещён", show_alert=True)
            return
        
        stats = db.get_statistics()
        
        text = f"""
📊 Статистика

👥 Всего пользователей: {stats['total_users']}
💰 Всего продаж: {stats['total_sales']}
💵 Общая сумма: {stats['total_revenue']} ₽
🔑 Доступно ключей: {stats['available_keys']}
⏳ Ожидают подтверждения: {stats['pending_orders']}
"""
        
        bot.editMessageText((chat_id, message_id), text, reply_markup=admin_menu_kb())
        bot.answerCallbackQuery(query_id)
    
    elif data == 'admin_payments':
        if from_id not in ADMIN_IDS:
            bot.answerCallbackQuery(query_id, text="❌ Доступ запрещён", show_alert=True)
            return
        
        pending = db.get_pending_orders()
        
        if not pending:
            text = "✅ Нет ожидающих оплат"
        else:
            text = f"💰 Ожидают подтверждения ({len(pending)}):\n\n"
            for order in pending[:5]:
                text += f"📝 ORDER{order['id']}\n"
                text += f"👤 User ID: {order['user_id']}\n"
                text += f"💵 Сумма: {order['amount']} ₽\n"
                text += "─" * 30 + "\n"
        
        bot.editMessageText((chat_id, message_id), text, reply_markup=admin_menu_kb())
        bot.answerCallbackQuery(query_id)
    
    elif data == 'admin_keys':
        if from_id not in ADMIN_IDS:
            bot.answerCallbackQuery(query_id, text="❌ Доступ запрещён", show_alert=True)
            return
        
        text = """
🔑 Управление ключами

/addkey XXXX-XXXX-XXXX-XXXX
/addkeys 10
/listkeys
"""
        
        bot.editMessageText((chat_id, message_id), text, reply_markup=admin_menu_kb())
        bot.answerCallbackQuery(query_id)
    
    # Подтверждение оплаты
    elif data.startswith('confirm_'):
        if from_id not in ADMIN_IDS:
            bot.answerCallbackQuery(query_id, text="❌ Доступ запрещён", show_alert=True)
            return
        
        order_id = int(data.split('_')[1])
        order = db.get_order(order_id)
        
        if not order:
            bot.answerCallbackQuery(query_id, text="❌ Заказ не найден", show_alert=True)
            return
        
        key = db.get_next_available_key()
        if not key:
            bot.answerCallbackQuery(query_id, text="❌ Нет доступных ключей!", show_alert=True)
            return
        
        db.confirm_order(order_id, key['id'])
        
        try:
            bot.sendMessage(
                order['user_id'],
                f"✅ Оплата подтверждена!\n\n"
                f"🔑 Ваш ключ: `{key['key_value']}`\n"
                f"📅 Дата покупки: {order['created_at']}\n\n"
                f"Спасибо за покупку! 🎉",
                parse_mode='Markdown'
            )
            
            bot.editMessageText(
                (chat_id, message_id),
                f"✅ Заказ ORDER{order_id} подтверждён\n🔑 Ключ выдан пользователю"
            )
        except Exception as e:
            print(f"Ошибка отправки ключа: {e}")
        
        bot.answerCallbackQuery(query_id, text="✅ Оплата подтверждена")
    
    # Отклонение оплаты
    elif data.startswith('reject_'):
        if from_id not in ADMIN_IDS:
            bot.answerCallbackQuery(query_id, text="❌ Доступ запрещён", show_alert=True)
            return
        
        order_id = int(data.split('_')[1])
        db.update_order_status(order_id, 'rejected')
        
        order = db.get_order(order_id)
        
        try:
            bot.sendMessage(
                order['user_id'],
                "❌ К сожалению, ваша оплата не подтверждена.\n\n"
                "Если вы уверены, что оплатили, свяжитесь с поддержкой."
            )
        except:
            pass
        
        bot.editMessageText((chat_id, message_id), f"❌ Заказ ORDER{order_id} отклонён")
        bot.answerCallbackQuery(query_id, text="Заказ отклонён")


# ============= ЗАПУСК =============

if __name__ == '__main__':
    db.init_db()
    
    MessageLoop(bot, {'chat': handle, 'callback_query': handle_callback}).run_as_thread()
    
    print('Бот запущен и работает!')
    
    # Держим бота запущенным
    while True:
        time.sleep(10)
