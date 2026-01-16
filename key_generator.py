import random
import string


class KeyGenerator:
    """Генератор уникальных ключей"""
    
    def __init__(self, format_pattern='XXXX-XXXX-XXXX-XXXX'):
        """
        Инициализация генератора
        
        Args:
            format_pattern: Шаблон ключа, где X заменяется на случайный символ
        """
        self.format_pattern = format_pattern
        self.charset = string.ascii_uppercase + string.digits  # A-Z, 0-9
    
    def generate(self):
        """
        Генерация одного ключа по заданному шаблону
        
        Returns:
            str: Сгенерированный ключ
        """
        key = ''
        for char in self.format_pattern:
            if char == 'X':
                key += random.choice(self.charset)
            else:
                key += char
        return key
    
    def generate_batch(self, count):
        """
        Генерация пакета уникальных ключей
        
        Args:
            count: Количество ключей для генерации
            
        Returns:
            list: Список уникальных ключей
        """
        keys = set()
        while len(keys) < count:
            keys.add(self.generate())
        return list(keys)
    
    def validate_format(self, key):
        """
        Проверка ключа на соответствие формату
        
        Args:
            key: Ключ для проверки
            
        Returns:
            bool: True если ключ соответствует формату
        """
        if len(key) != len(self.format_pattern):
            return False
        
        for i, char in enumerate(self.format_pattern):
            if char == 'X':
                if key[i] not in self.charset:
                    return False
            else:
                if key[i] != char:
                    return False
        
        return True


# Альтернативный генератор с использованием UUID
class UUIDKeyGenerator:
    """Генератор ключей на основе UUID"""
    
    @staticmethod
    def generate():
        """
        Генерация ключа на основе UUID4
        
        Returns:
            str: Ключ в формате XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
        """
        import uuid
        return str(uuid.uuid4()).upper()
    
    @staticmethod
    def generate_short():
        """
        Генерация короткого ключа (16 символов)
        
        Returns:
            str: Короткий ключ
        """
        import uuid
        return str(uuid.uuid4()).replace('-', '').upper()[:16]


# Генератор читаемых ключей (без похожих символов)
class ReadableKeyGenerator:
    """Генератор читаемых ключей без похожих символов"""
    
    def __init__(self):
        # Исключаем похожие символы: 0/O, 1/I/L, 2/Z, 5/S, 8/B
        self.charset = 'ACDEFGHJKLMNPQRTUVWXY34679'
    
    def generate(self, length=16, separator='-', group_size=4):
        """
        Генерация читаемого ключа
        
        Args:
            length: Общая длина ключа (без разделителей)
            separator: Разделитель групп
            group_size: Размер группы символов
            
        Returns:
            str: Сгенерированный ключ
        """
        key = ''.join(random.choice(self.charset) for _ in range(length))
        
        # Группировка с разделителем
        if separator and group_size > 0:
            groups = [key[i:i+group_size] for i in range(0, len(key), group_size)]
            key = separator.join(groups)
        
        return key