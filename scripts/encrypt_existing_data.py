"""
Скрипт для шифрования существующих данных в БД.

Этот скрипт:
1. Подключается к БД
2. Находит все записи с незашифрованными данными
3. Шифрует их с помощью ENCRYPTION_KEY
4. Сохраняет обратно в БД

ВАЖНО: Запускайте этот скрипт только ОДИН РАЗ после установки ENCRYPTION_KEY!
Повторный запуск приведет к двойному шифрованию и потере данных!

Usage:
    python scripts/encrypt_existing_data.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from server.models import UserProfile
from utils.encryption import encrypt_field, is_encryption_enabled
from config import DATABASE_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def encrypt_existing_profiles():
    """
    Шифрует все существующие профили пользователей.
    """
    if not is_encryption_enabled():
        logger.error("❌ ENCRYPTION_KEY не установлен! Установите его в .env файле перед запуском.")
        return False
    
    logger.info("🔐 Начало шифрования существующих данных...")
    
    # Создаем подключение к БД
    engine = create_async_engine(DATABASE_URL)
    async_session = async_sessionmaker(engine)
    
    try:
        async with async_session() as session:
            # Получаем все профили
            result = await session.execute(select(UserProfile))
            profiles = result.scalars().all()
            
            if not profiles:
                logger.info("✅ Нет профилей для шифрования")
                return True
            
            logger.info(f"📊 Найдено {len(profiles)} профилей для обработки")
            
            encrypted_count = 0
            skipped_count = 0
            error_count = 0
            
            for profile in profiles:
                try:
                    # Проверяем, нужно ли шифровать
                    # Если _encrypted_name уже выглядит как encrypted (начинается с gAAAAA), пропускаем
                    raw_name = profile._encrypted_name
                    
                    if raw_name and raw_name.startswith('gAAAAA'):
                        # Уже зашифровано (Fernet токены начинаются с gAAAAA в base64)
                        logger.debug(f"⏭️  User {profile.user_id}: уже зашифровано, пропускаем")
                        skipped_count += 1
                        continue
                    
                    if not raw_name:
                        # Нет данных для шифрования
                        skipped_count += 1
                        continue
                    
                    # Шифруем plaintext данные
                    logger.info(f"🔒 Шифрование данных для user {profile.user_id}")
                    profile._encrypted_name = encrypt_field(raw_name)
                    encrypted_count += 1
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка при шифровании user {profile.user_id}: {e}")
                    error_count += 1
                    continue
            
            # Сохраняем изменения
            if encrypted_count > 0:
                await session.commit()
                logger.info(f"✅ Изменения сохранены в БД")
            
            # Статистика
            logger.info(f"\n📈 Статистика:")
            logger.info(f"   Всего профилей: {len(profiles)}")
            logger.info(f"   Зашифровано: {encrypted_count}")
            logger.info(f"   Пропущено: {skipped_count}")
            logger.info(f"   Ошибок: {error_count}")
            
            if error_count > 0:
                logger.warning(f"⚠️  Обнаружены ошибки! Проверьте логи выше.")
                return False
            
            logger.info(f"✅ Шифрование завершено успешно!")
            return True
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        return False
    finally:
        await engine.dispose()


async def verify_encryption():
    """
    Проверяет, что шифрование работает корректно.
    """
    logger.info("\n🔍 Проверка корректности шифрования...")
    
    engine = create_async_engine(DATABASE_URL)
    async_session = async_sessionmaker(engine)
    
    try:
        async with async_session() as session:
            # Получаем несколько профилей для проверки
            result = await session.execute(select(UserProfile).limit(5))
            profiles = result.scalars().all()
            
            if not profiles:
                logger.info("✅ Нет профилей для проверки")
                return True
            
            all_ok = True
            for profile in profiles:
                try:
                    # Проверяем, что name расшифровывается корректно
                    decrypted_name = profile.name
                    encrypted_raw = profile._encrypted_name
                    
                    logger.info(f"User {profile.user_id}:")
                    logger.info(f"  Зашифровано: {encrypted_raw[:50]}..." if encrypted_raw else "  Нет данных")
                    logger.info(f"  Расшифровано: {decrypted_name}")
                    
                    if encrypted_raw and not encrypted_raw.startswith('gAAAAA'):
                        logger.warning(f"⚠️  User {profile.user_id}: данные не похожи на зашифрованные!")
                        all_ok = False
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка проверки user {profile.user_id}: {e}")
                    all_ok = False
            
            if all_ok:
                logger.info("✅ Проверка прошла успешно!")
            else:
                logger.warning("⚠️  Обнаружены проблемы при проверке")
            
            return all_ok
            
    except Exception as e:
        logger.error(f"❌ Ошибка проверки: {e}", exc_info=True)
        return False
    finally:
        await engine.dispose()


async def main():
    """
    Главная функция.
    """
    import sys
    
    logger.info("=" * 70)
    logger.info("🔐 Скрипт шифрования существующих данных")
    logger.info("=" * 70)
    
    # Предупреждение
    logger.warning("\n⚠️  ВНИМАНИЕ:")
    logger.warning("   Этот скрипт изменит все существующие данные в БД!")
    logger.warning("   Рекомендуется сделать backup перед запуском.")
    logger.warning("   Повторный запуск может привести к двойному шифрованию!\n")
    
    # Проверяем флаг --force
    if '--force' not in sys.argv:
        try:
            response = input("Продолжить? (yes/no): ")
            if response.lower() != 'yes':
                logger.info("❌ Отменено пользователем")
                return
        except EOFError:
            logger.error("❌ Невозможно прочитать ответ. Используйте флаг --force")
            return
    else:
        logger.info("✅ Запуск с флагом --force, пропускаем подтверждение")
    
    # Проверяем ENCRYPTION_KEY
    if not is_encryption_enabled():
        logger.error("\n❌ ENCRYPTION_KEY не установлен!")
        logger.error("   Установите его в .env файле:")
        logger.error("   python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
        return
    
    # Шифруем данные
    success = await encrypt_existing_profiles()
    
    if not success:
        logger.error("\n❌ Шифрование завершилось с ошибками")
        return
    
    # Проверяем результат
    verification_ok = await verify_encryption()
    
    if verification_ok:
        logger.info("\n" + "=" * 70)
        logger.info("✅ Шифрование и проверка завершены успешно!")
        logger.info("=" * 70)
    else:
        logger.error("\n" + "=" * 70)
        logger.error("❌ Обнаружены проблемы. Проверьте логи.")
        logger.error("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
