"""add encryption to userprofile

Revision ID: add_encryption_001
Revises: 17e44996472c
Create Date: 2025-01-07

Изменяет колонку name в user_profiles для поддержки зашифрованных данных.
Увеличивает размер колонки до 500 символов для хранения encrypted data.

ВАЖНО: Запустите эту миграцию только после установки ENCRYPTION_KEY в .env!
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g9h8i7j6k5l4'
down_revision: Union[str, None] = 'f8a3c9d1e2b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema для поддержки шифрования.
    
    1. Изменяет размер колонки name до 500 символов
    2. Существующие данные остаются в plaintext (расшифровываются корректно если ENCRYPTION_KEY не установлен)
    
    ВАЖНО: После этой миграции необходимо:
    1. Установить ENCRYPTION_KEY в .env
    2. Запустить скрипт миграции данных (scripts/encrypt_existing_data.py)
    """
    # Увеличиваем размер колонки name для зашифрованных данных
    op.alter_column('user_profiles', 'name',
               existing_type=sa.String(),
               type_=sa.String(length=500),
               existing_nullable=True)
    
    print("✅ Миграция успешна. Колонка 'name' увеличена до 500 символов.")
    print("⚠️  СЛЕДУЮЩИЕ ШАГИ:")
    print("   1. Установите ENCRYPTION_KEY в .env файл")
    print("   2. Перезапустите приложение для проверки")
    print("   3. Запустите scripts/encrypt_existing_data.py для шифрования существующих данных")


def downgrade() -> None:
    """
    Downgrade schema.
    
    Возвращает колонку name к исходному размеру.
    ВНИМАНИЕ: Зашифрованные данные будут обрезаны!
    """
    op.alter_column('user_profiles', 'name',
               existing_type=sa.String(length=500),
               type_=sa.String(),
               existing_nullable=True)
    
    print("⚠️  Downgrade выполнен. Колонка 'name' вернулась к исходному размеру.")
    print("⚠️  ВНИМАНИЕ: Зашифрованные данные могут быть обрезаны!")
