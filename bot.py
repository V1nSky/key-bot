import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
from dotenv import load_dotenv
from database import Database
from key_generator import KeyGenerator

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x]

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
db = Database()
key_gen = KeyGenerator()


class PaymentStates(StatesGroup):
    waiting_payment = State()


# ============= КЛАВИАТУРЫ =============

def main_menu_kb():
    kb = [
        [InlineKeyboardButton(text="🔑 Купить ключ", callback_data="buy_key")],
        [InlineKeyboardButton(text="💳 Способы оплаты", callback_data="payment_methods")],
        [InlineKeyboardButton(text="📦 Мои покупки", callback_data="my_purchases")],
        [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_menu_kb():
    kb = [
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="💰 Новые оплаты", callback_data="admin_payments")],
        [InlineKeyboardButton(text="🔑 Управление ключами", callback_data="admin_keys")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="start")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def payment_kb(order_id):
    kb = [
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"paid_{order_id}")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="start")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def back_to_menu_kb():
    kb = [[InlineKeyboardButton(text="◀️ В главное меню", callback_data="start")]]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def confirm_payment_kb(order_id):
    kb = [
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{order_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ============= ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЕЙ =============

@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Пользователь"
    
    # Регистрация пользователя
    db.add_user(user_id, username)
    
    welcome_text = f"""
👋 Добро пожаловать, {message.from_user.first_name}!

Это бот для автоматической продажи цифровых ключей.

Выберите действие:
"""
    
    if user_id in ADMIN_IDS:
        welcome_text += "\n🔧 Вы авторизованы как администратор"
    
    await message.answer(welcome_text, reply_markup=main_menu_kb())


@router.callback_query(F.data == "start")
async def back_to_start(callback: CallbackQuery):
    await callback.message.edit_text(
        f"👋 Главное меню\n\nВыберите действие:",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "buy_key")
async def buy_key(callback: CallbackQuery):
    # Проверка наличия ключей
    available_keys = db.get_available_keys_count()
    
    if available_keys == 0:
        await callback.answer("❌ К сожалению, ключи закончились", show_alert=True)
        return
    
    price = 500  # Цена в рублях
    
    # Создание заказа
    order_id = db.create_order(callback.from_user.id, price)
    
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
    
    await callback.message.edit_text(payment_text, reply_markup=payment_kb(order_id))
    await callback.answer()


@router.callback_query(F.data.startswith("paid_"))
async def user_paid(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    
    # Проверка существования заказа
    order = db.get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    if order['status'] == 'confirmed':
        await callback.answer("✅ Этот заказ уже подтверждён", show_alert=True)
        return
    
    # Обновление статуса
    db.update_order_status(order_id, 'pending')
    
    await callback.message.edit_text(
        "✅ Спасибо! Ваша оплата отправлена на проверку.\n\n"
        "⏳ Обычно проверка занимает 5-15 минут.\n"
        "Как только платёж подтвердится, вы получите ключ автоматически.",
        reply_markup=back_to_menu_kb()
    )
    
    # Уведомление админам
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"💰 Новая оплата!\n\n"
                f"📝 Заказ: ORDER{order_id}\n"
                f"👤 Пользователь: {callback.from_user.username or callback.from_user.id}\n"
                f"💵 Сумма: {order['amount']} ₽",
                reply_markup=confirm_payment_kb(order_id)
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
    
    await callback.answer()


@router.callback_query(F.data == "payment_methods")
async def payment_methods(callback: CallbackQuery):
    text = """
💳 Способы оплаты

Мы принимаем оплату только внутри РФ:

✅ СБП (Система быстрых платежей)
✅ Банковская карта РФ
✅ ЮMoney (по запросу)

❌ Криптовалюта не принимается
❌ Иностранные карты не принимаются

После выбора товара вы получите реквизиты для оплаты.
"""
    await callback.message.edit_text(text, reply_markup=back_to_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "my_purchases")
async def my_purchases(callback: CallbackQuery):
    user_id = callback.from_user.id
    purchases = db.get_user_purchases(user_id)
    
    if not purchases:
        text = "📦 У вас пока нет покупок"
    else:
        text = "📦 Ваши покупки:\n\n"
        for p in purchases:
            text += f"🔑 {p['key']}\n"
            text += f"📅 {p['purchase_date']}\n"
            text += f"{'─' * 30}\n"
    
    await callback.message.edit_text(text, reply_markup=back_to_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    text = """
🆘 Поддержка

По всем вопросам обращайтесь:
📧 @support_username

Время ответа: обычно в течение 1 часа
"""
    await callback.message.edit_text(text, reply_markup=back_to_menu_kb())
    await callback.answer()


# ============= АДМИН ПАНЕЛЬ =============

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет доступа к админ-панели")
        return
    
    await message.answer(
        "🔧 Админ-панель\n\nВыберите действие:",
        reply_markup=admin_menu_kb()
    )


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
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
    
    await callback.message.edit_text(text, reply_markup=admin_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "admin_payments")
async def admin_payments(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    pending = db.get_pending_orders()
    
    if not pending:
        text = "✅ Нет ожидающих оплат"
        await callback.message.edit_text(text, reply_markup=admin_menu_kb())
    else:
        text = f"💰 Ожидают подтверждения ({len(pending)}):\n\n"
        for order in pending[:5]:  # Показываем первые 5
            text += f"📝 ORDER{order['id']}\n"
            text += f"👤 User ID: {order['user_id']}\n"
            text += f"💵 Сумма: {order['amount']} ₽\n"
            text += f"{'─' * 30}\n"
        
        await callback.message.edit_text(text, reply_markup=admin_menu_kb())
    
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_"))
async def confirm_payment(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    order_id = int(callback.data.split("_")[1])
    order = db.get_order(order_id)
    
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    # Получение ключа
    key = db.get_next_available_key()
    if not key:
        await callback.answer("❌ Нет доступных ключей!", show_alert=True)
        return
    
    # Подтверждение заказа
    db.confirm_order(order_id, key['id'])
    
    # Отправка ключа пользователю
    try:
        await bot.send_message(
            order['user_id'],
            f"✅ Оплата подтверждена!\n\n"
            f"🔑 Ваш ключ: `{key['key_value']}`\n"
            f"📅 Дата покупки: {order['created_at']}\n\n"
            f"Спасибо за покупку! 🎉",
            parse_mode="Markdown"
        )
        
        await callback.message.edit_text(
            f"✅ Заказ ORDER{order_id} подтверждён\n"
            f"🔑 Ключ выдан пользователю"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки ключа: {e}")
        await callback.answer("⚠️ Ошибка отправки ключа пользователю", show_alert=True)
    
    await callback.answer("✅ Оплата подтверждена")


@router.callback_query(F.data.startswith("reject_"))
async def reject_payment(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    order_id = int(callback.data.split("_")[1])
    db.update_order_status(order_id, 'rejected')
    
    order = db.get_order(order_id)
    
    try:
        await bot.send_message(
            order['user_id'],
            "❌ К сожалению, ваша оплата не подтверждена.\n\n"
            "Если вы уверены, что оплатили, свяжитесь с поддержкой."
        )
    except:
        pass
    
    await callback.message.edit_text(f"❌ Заказ ORDER{order_id} отклонён")
    await callback.answer("Заказ отклонён")


@router.callback_query(F.data == "admin_keys")
async def admin_keys(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    text = """
🔑 Управление ключами

Для добавления ключей используйте команду:
/addkey XXXX-XXXX-XXXX-XXXX

Для добавления нескольких ключей:
/addkeys 10 - сгенерирует 10 ключей

Для просмотра всех ключей:
/listkeys
"""
    
    await callback.message.edit_text(text, reply_markup=admin_menu_kb())
    await callback.answer()


@router.message(Command("addkey"))
async def add_key(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /addkey XXXX-XXXX-XXXX-XXXX")
        return
    
    key_value = args[1].strip()
    if db.add_key(key_value):
        await message.answer(f"✅ Ключ {key_value} добавлен")
    else:
        await message.answer("❌ Ключ уже существует или ошибка")


@router.message(Command("addkeys"))
async def add_keys(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = message.text.split()
    count = int(args[1]) if len(args) > 1 else 1
    
    added = 0
    for _ in range(count):
        key_value = key_gen.generate()
        if db.add_key(key_value):
            added += 1
    
    await message.answer(f"✅ Добавлено {added} ключей")


@router.message(Command("listkeys"))
async def list_keys(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    keys = db.get_all_keys()
    
    text = f"🔑 Всего ключей: {len(keys)}\n\n"
    for key in keys[:20]:
        status = "✅" if key['is_used'] == 0 else "❌"
        text += f"{status} {key['key_value']}\n"
    
    if len(keys) > 20:
        text += f"\n... и ещё {len(keys) - 20}"
    
    await message.answer(text)


# ============= ЗАПУСК БОТА =============

async def main():
    db.init_db()
    dp.include_router(router)
    
    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())