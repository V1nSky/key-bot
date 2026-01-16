import sqlite3
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path='bot_database.db'):
        self.db_path = db_path
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Инициализация базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица ключей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_value TEXT UNIQUE NOT NULL,
                is_used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица заказов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                status TEXT DEFAULT 'created',
                key_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id),
                FOREIGN KEY (key_id) REFERENCES keys(id)
            )
        ''')
        
        # Таблица покупок (история)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                order_id INTEGER NOT NULL,
                key_id INTEGER NOT NULL,
                purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id),
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (key_id) REFERENCES keys(id)
            )
        ''')
        
        # Таблица логов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")
    
    # ============= ПОЛЬЗОВАТЕЛИ =============
    
    def add_user(self, telegram_id, username):
        """Добавление пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)',
                (telegram_id, username)
            )
            conn.commit()
            conn.close()
            self.log_action(telegram_id, 'user_registered', f'Username: {username}')
        except Exception as e:
            logger.error(f"Ошибка добавления пользователя: {e}")
    
    def get_user(self, telegram_id):
        """Получение пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    
    # ============= КЛЮЧИ =============
    
    def add_key(self, key_value):
        """Добавление ключа"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO keys (key_value) VALUES (?)', (key_value,))
            conn.commit()
            key_id = cursor.lastrowid
            conn.close()
            self.log_action(None, 'key_added', f'Key: {key_value}')
            return key_id
        except sqlite3.IntegrityError:
            logger.warning(f"Ключ {key_value} уже существует")
            return None
        except Exception as e:
            logger.error(f"Ошибка добавления ключа: {e}")
            return None
    
    def get_next_available_key(self):
        """Получение следующего свободного ключа"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM keys WHERE is_used = 0 ORDER BY id LIMIT 1'
        )
        key = cursor.fetchone()
        conn.close()
        return dict(key) if key else None
    
    def mark_key_as_used(self, key_id):
        """Пометить ключ как использованный"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE keys SET is_used = 1 WHERE id = ?', (key_id,))
        conn.commit()
        conn.close()
    
    def get_available_keys_count(self):
        """Количество доступных ключей"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM keys WHERE is_used = 0')
        count = cursor.fetchone()['count']
        conn.close()
        return count
    
    def get_all_keys(self):
        """Получение всех ключей"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM keys ORDER BY id DESC')
        keys = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return keys
    
    # ============= ЗАКАЗЫ =============
    
    def create_order(self, user_id, amount):
        """Создание заказа"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO orders (user_id, amount, status) VALUES (?, ?, ?)',
            (user_id, amount, 'created')
        )
        order_id = cursor.lastrowid
        conn.commit()
        conn.close()
        self.log_action(user_id, 'order_created', f'Order ID: {order_id}, Amount: {amount}')
        return order_id
    
    def get_order(self, order_id):
        """Получение заказа"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        order = cursor.fetchone()
        conn.close()
        return dict(order) if order else None
    
    def update_order_status(self, order_id, status):
        """Обновление статуса заказа"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE orders SET status = ? WHERE id = ?',
            (status, order_id)
        )
        conn.commit()
        conn.close()
        self.log_action(None, 'order_status_updated', f'Order ID: {order_id}, Status: {status}')
    
    def confirm_order(self, order_id, key_id):
        """Подтверждение заказа и выдача ключа"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Получаем информацию о заказе
            cursor.execute('SELECT user_id FROM orders WHERE id = ?', (order_id,))
            order = cursor.fetchone()
            if not order:
                return False
            
            user_id = order['user_id']
            
            # Обновляем заказ
            cursor.execute(
                '''UPDATE orders 
                   SET status = ?, key_id = ?, confirmed_at = CURRENT_TIMESTAMP 
                   WHERE id = ?''',
                ('confirmed', key_id, order_id)
            )
            
            # Помечаем ключ как использованный
            cursor.execute('UPDATE keys SET is_used = 1 WHERE id = ?', (key_id,))
            
            # Добавляем запись в покупки
            cursor.execute(
                'INSERT INTO purchases (user_id, order_id, key_id) VALUES (?, ?, ?)',
                (user_id, order_id, key_id)
            )
            
            conn.commit()
            conn.close()
            
            self.log_action(user_id, 'order_confirmed', f'Order ID: {order_id}, Key ID: {key_id}')
            return True
        except Exception as e:
            logger.error(f"Ошибка подтверждения заказа: {e}")
            return False
    
    def get_pending_orders(self):
        """Получение заказов в ожидании"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC',
            ('pending',)
        )
        orders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return orders
    
    # ============= ПОКУПКИ =============
    
    def get_user_purchases(self, user_id):
        """Получение покупок пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, k.key_value 
            FROM purchases p
            JOIN keys k ON p.key_id = k.id
            WHERE p.user_id = ?
            ORDER BY p.purchase_date DESC
        ''', (user_id,))
        purchases = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return purchases
    
    # ============= СТАТИСТИКА =============
    
    def get_statistics(self):
        """Получение статистики"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Всего пользователей
        cursor.execute('SELECT COUNT(*) as count FROM users')
        total_users = cursor.fetchone()['count']
        
        # Всего продаж
        cursor.execute('SELECT COUNT(*) as count FROM orders WHERE status = ?', ('confirmed',))
        total_sales = cursor.fetchone()['count']
        
        # Общая сумма
        cursor.execute('SELECT SUM(amount) as total FROM orders WHERE status = ?', ('confirmed',))
        total_revenue = cursor.fetchone()['total'] or 0
        
        # Доступно ключей
        cursor.execute('SELECT COUNT(*) as count FROM keys WHERE is_used = 0')
        available_keys = cursor.fetchone()['count']
        
        # Ожидают подтверждения
        cursor.execute('SELECT COUNT(*) as count FROM orders WHERE status = ?', ('pending',))
        pending_orders = cursor.fetchone()['count']
        
        conn.close()
        
        return {
            'total_users': total_users,
            'total_sales': total_sales,
            'total_revenue': total_revenue,
            'available_keys': available_keys,
            'pending_orders': pending_orders
        }
    
    # ============= ЛОГИ =============
    
    def log_action(self, user_id, action, details=''):
        """Логирование действий"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO logs (user_id, action, details) VALUES (?, ?, ?)',
                (user_id, action, details)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Ошибка логирования: {e}")