# 🚀 Инструкция по применению исправлений безопасности

> **Важно:** Следуйте инструкциям в точности, иначе возможна потеря данных!

---

## 📋 Что было исправлено

1. ✅ **Шифрование чувствительных данных в БД** (поле `name`)
2. ✅ **Защита платежной системы** (rate limiting, валидация, аудит)
3. ✅ **Усиление JWT_SECRET** (валидация длины и энтропии)

---

## 🔧 Шаг 1: Генерация ключей безопасности

### 1.1. Генерируем ENCRYPTION_KEY

```bash
# Linux/macOS
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Windows PowerShell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Сохраните вывод! Пример: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx=`

### 1.2. Проверяем JWT_SECRET

Убедитесь, что JWT_SECRET в `.env` >= 32 символа. Если нет, сгенерируйте новый:

```bash
# Linux/macOS/Git Bash
openssl rand -hex 32

# Windows PowerShell
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## ✏️ Шаг 2: Обновляем .env файл

Откройте `.env` и добавьте/обновите:

```env
# Encryption Key (НОВОЕ!)
ENCRYPTION_KEY=ВАШ_СГЕНЕРИРОВАННЫЙ_КЛЮЧ_ИЗ_ШАГА_1.1

# JWT Secret (проверьте длину >= 32)
JWT_SECRET=ваш_существующий_или_новый_jwt_secret_минимум_32_символа
```

**⚠️ КРИТИЧЕСКИ ВАЖНО:**
- Сохраните копию ENCRYPTION_KEY в защищенном месте (1Password, Bitwarden, etc.)
- При потере ENCRYPTION_KEY все зашифрованные данные будут потеряны НАВСЕГДА!
- Никогда не коммитьте .env в git!

---

## 🐳 Шаг 3: Пересборка и запуск Docker контейнеров

```bash
# Переходим в директорию проекта
cd C:\Users\alex\Desktop\Malter

# Останавливаем контейнеры (если запущены)
docker-compose down

# Пересобираем с новыми зависимостями
docker-compose build

# Запускаем (миграции применятся автоматически)
docker-compose up -d

# Проверяем логи миграции
docker-compose logs migration
```

Ожидаемый вывод миграции:
```
migration | INFO:alembic.runtime.migration:Context impl PostgresqlImpl.
migration | INFO:alembic.runtime.migration:Will assume transactional DDL.
migration | INFO:alembic.runtime.migration:Running upgrade f8a3c9d1e2b5 -> g9h8i7j6k5l4, add encryption to userprofile
migration | ✅ Миграция успешна. Колонка 'name' увеличена до 500 символов.
```

---

## 🔐 Шаг 4: Шифрование существующих данных

⚠️ **ВНИМАНИЕ:** Этот шаг выполняется **ТОЛЬКО ОДИН РАЗ**!

### 4.1. Создаем backup БД (на всякий случай)

```bash
# Подключаемся к контейнеру БД
docker-compose exec db bash

# Создаем backup
pg_dump -U myuser malterdb > /tmp/backup_before_encryption.sql

# Выходим
exit

# Копируем backup на хост
docker cp malter-db-1:/tmp/backup_before_encryption.sql ./backups/
```

### 4.2. Запускаем скрипт шифрования

```bash
# Заходим в контейнер API
docker-compose exec api bash

# Запускаем скрипт
python scripts/encrypt_existing_data.py
```

Скрипт спросит подтверждение. Введите `yes`.

Ожидаемый вывод:
```
🔐 Начало шифрования существующих данных...
📊 Найдено X профилей для обработки
🔒 Шифрование данных для user 123456789
✅ Изменения сохранены в БД

📈 Статистика:
   Всего профилей: X
   Зашифровано: X
   Пропущено: 0
   Ошибок: 0

✅ Шифрование завершено успешно!

🔍 Проверка корректности шифрования...
User 123456789:
  Зашифровано: gAAAAABl...
  Расшифровано: Имя
✅ Проверка прошла успешно!
```

---

## ✅ Шаг 5: Проверка работоспособности

### 5.1. Проверяем логи

```bash
# Логи API
docker-compose logs api | tail -50

# Логи бота
docker-compose logs bot | tail -50
```

Не должно быть ошибок типа:
- `ModuleNotFoundError: No module named 'utils'`
- `ValueError: ENCRYPTION_KEY не установлен`
- `ValueError: JWT_SECRET слишком короткий`

### 5.2. Проверяем healthcheck

```bash
curl http://localhost:8000/health
```

Ожидаемый ответ:
```json
{
  "database": {"status": "healthy", "message": "Connected"},
  "redis": {"status": "healthy", "message": "Connected, Circuit Breaker: CLOSED"},
  "gemini": {"status": "healthy", "message": "Client initialized"},
  "overall": "healthy"
}
```

### 5.3. Тестируем через Telegram

1. Отправьте боту команду `/start`
2. Проверьте, что бот отвечает
3. Попробуйте команду `/profile` - имя должно отображаться корректно
4. Попробуйте `/buy_premium` - должны работать ограничения (3 попытки/час)

---

## 🔍 Шаг 6: Мониторинг и аудит

### 6.1. Проверяем логи платежей

```bash
docker-compose logs bot | grep "PAYMENT_"
```

Должны видеть логи типа:
```
bot | PAYMENT_SUCCESS: user_id=123, amount=99000, charge_id=...
bot | Premium activated successfully for user 123, duration: 30 days
```

### 6.2. Проверяем security логи

```bash
docker-compose logs bot | grep "SECURITY:"
```

При попытках fraud должны видеть:
```
bot | SECURITY: Payload user_id mismatch! Authenticated: 123, Payload: 456
bot | SECURITY: Price mismatch for user 123! Expected: 99000, Got: 50000
```

---

## 🆘 Возможные проблемы и решения

### Проблема 1: `ModuleNotFoundError: No module named 'utils'`

**Решение:**
```bash
# Проверьте, что файл создан
ls utils/__init__.py

# Если нет - создайте:
touch utils/__init__.py

# Пересоберите контейнеры
docker-compose build
docker-compose up -d
```

### Проблема 2: `ValueError: ENCRYPTION_KEY не установлен`

**Решение:**
```bash
# Проверьте .env файл
cat .env | grep ENCRYPTION_KEY

# Если пустой - добавьте
echo "ENCRYPTION_KEY=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" >> .env

# Перезапустите
docker-compose restart
```

### Проблема 3: Миграция не применяется

**Решение:**
```bash
# Проверьте текущую версию БД
docker-compose exec api alembic current

# Если застряли на старой версии
docker-compose exec api alembic upgrade head

# Проверьте логи
docker-compose logs migration
```

### Проблема 4: "Ошибка расшифровки имени"

**Причина:** Вы поменяли ENCRYPTION_KEY после шифрования данных.

**Решение:**
```bash
# 1. Восстановите старый ENCRYPTION_KEY из backup
# 2. Или восстановите БД из backup
docker-compose exec db psql -U myuser malterdb < /tmp/backup_before_encryption.sql

# 3. Заново запустите шифрование с правильным ключом
```

---

## 📊 Проверочный чеклист

Перед завершением убедитесь:

- [ ] ✅ ENCRYPTION_KEY добавлен в .env и сохранен в защищенном месте
- [ ] ✅ JWT_SECRET >= 32 символа
- [ ] ✅ Миграция g9h8i7j6k5l4 применена успешно
- [ ] ✅ Скрипт encrypt_existing_data.py выполнен один раз
- [ ] ✅ Healthcheck возвращает "healthy"
- [ ] ✅ Бот отвечает в Telegram
- [ ] ✅ /profile показывает расшифрованные данные
- [ ] ✅ /buy_premium работает с rate limiting
- [ ] ✅ Логи не содержат ошибок
- [ ] ✅ Backup БД создан и сохранен

---

## 📚 Дополнительные ресурсы

- Полный аудит безопасности: `PRIVACY_AND_SECURITY_AUDIT.md`
- Сводка исправлений: `SECURITY_IMPROVEMENTS_SUMMARY.md`
- Логирование: `docker-compose logs -f api bot`
- Мониторинг: `http://localhost:8000/metrics` (Prometheus)

---

## 🆘 Поддержка

Если возникли проблемы:

1. Проверьте логи: `docker-compose logs`
2. Проверьте healthcheck: `curl localhost:8000/health`
3. Проверьте `.env` файл на опечатки
4. Восстановите из backup если что-то пошло не так

---

**Статус документа:** v1.0  
**Дата:** 2025-01-07  
**Автор:** AI Security Team
