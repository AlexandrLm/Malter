"""
Утилиты для шифрования чувствительных данных.

Использует Fernet (симметричное шифрование) для защиты персональных данных в БД.
"""

import os
import logging
from cryptography.fernet import Fernet, InvalidToken
from typing import Optional

logger = logging.getLogger(__name__)

# Получаем ключ шифрования из переменных окружения
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

# Инициализируем cipher suite
_cipher_suite: Optional[Fernet] = None

if ENCRYPTION_KEY:
    try:
        _cipher_suite = Fernet(ENCRYPTION_KEY.encode())
        logger.info("Encryption module успешно инициализирован")
    except Exception as e:
        logger.error(f"Ошибка инициализации шифрования: {e}")
        _cipher_suite = None
else:
    logger.warning(
        "ENCRYPTION_KEY не установлен. Шифрование данных отключено. "
        "Для production сгенерируйте ключ: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
    )


def generate_encryption_key() -> str:
    """
    Генерирует новый ключ шифрования.
    
    Returns:
        str: Новый ключ шифрования в base64 формате
    """
    return Fernet.generate_key().decode()


def encrypt_field(value: Optional[str]) -> Optional[str]:
    """
    Шифрует строковое значение для безопасного хранения в БД.
    
    Args:
        value: Значение для шифрования
        
    Returns:
        Зашифрованное значение в base64 или None если value пустой
        
    Raises:
        RuntimeError: Если шифрование не инициализировано
    """
    if value is None or value == "":
        return None
    
    if _cipher_suite is None:
        # В development режиме возвращаем как есть с предупреждением
        logger.warning("Encryption disabled - storing data in plaintext")
        return value
    
    try:
        encrypted = _cipher_suite.encrypt(value.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Ошибка шифрования: {e}", exc_info=True)
        raise RuntimeError(f"Не удалось зашифровать данные: {e}")


def decrypt_field(encrypted_value: Optional[str]) -> Optional[str]:
    """
    Расшифровывает значение из БД.
    
    Args:
        encrypted_value: Зашифрованное значение из БД
        
    Returns:
        Расшифрованное значение или None если encrypted_value пустой
        
    Raises:
        RuntimeError: Если расшифровка не удалась
    """
    if encrypted_value is None or encrypted_value == "":
        return None
    
    if _cipher_suite is None:
        # В development режиме возвращаем как есть
        logger.warning("Encryption disabled - reading plaintext data")
        return encrypted_value
    
    try:
        decrypted = _cipher_suite.decrypt(encrypted_value.encode())
        return decrypted.decode()
    except InvalidToken:
        logger.error(f"Invalid encryption token - data may be corrupted or key changed")
        raise RuntimeError("Не удалось расшифровать данные - неверный ключ или данные повреждены")
    except Exception as e:
        logger.error(f"Ошибка расшифровки: {e}", exc_info=True)
        raise RuntimeError(f"Не удалось расшифровать данные: {e}")


def is_encryption_enabled() -> bool:
    """
    Проверяет, включено ли шифрование.
    
    Returns:
        bool: True если шифрование включено, False иначе
    """
    return _cipher_suite is not None


# Примеры использования и тесты
if __name__ == "__main__":
    # Генерация ключа для .env
    print("Новый ключ шифрования для .env:")
    print(f"ENCRYPTION_KEY={generate_encryption_key()}")
    print("\n⚠️ ВАЖНО: Сохраните этот ключ в .env и НИКОГДА не коммитьте в git!")
    print("⚠️ При смене ключа все зашифрованные данные станут недоступны!\n")
    
    # Тест шифрования (если ключ установлен)
    if is_encryption_enabled():
        test_data = "Алексей"
        encrypted = encrypt_field(test_data)
        decrypted = decrypt_field(encrypted)
        
        print(f"Тест шифрования:")
        print(f"  Исходные данные: {test_data}")
        print(f"  Зашифровано: {encrypted}")
        print(f"  Расшифровано: {decrypted}")
        print(f"  Успех: {test_data == decrypted}")
    else:
        print("Шифрование не включено. Установите ENCRYPTION_KEY для тестирования.")
