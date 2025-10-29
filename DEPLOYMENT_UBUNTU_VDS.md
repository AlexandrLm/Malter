# 🚀 Установка на Ubuntu VDS - Полное руководство

## 📋 Содержание

- [Этап 1: Подготовка VDS](#этап-1-подготовка-vds-установка-docker)
- [Этап 2: Клонирование проекта](#этап-2-клонирование-проекта)
- [Этап 3: Создание .env файла](#этап-3-создание-и-настройка-env-файла)
- [Этап 4: Запуск сервисов](#этап-4-запуск-всех-сервисов)
- [Этап 5: Проверка работоспособности](#этап-5-проверка-работоспособности)
- [Открытие доступа из интернета](#-открытие-доступа-к-api-из-интернета)
- [Команды управления](#-частые-команды-управления-на-vds)
- [Автозапуск](#-создание-автозапуска-docker-compose)
- [Безопасность для продакшена](#-дополнительная-безопасность-для-продакшена)

---

## Этап 1: Подготовка VDS (Установка Docker)

### Подключение к VDS

```bash
# Подключиться к VDS по SSH
ssh root@ваш_ip_vds
# или
ssh user@ваш_ip_vds
```

### Обновление системы

```bash
# 1. Обновить систему
sudo apt update && sudo apt upgrade -y

# 2. Установить необходимые пакеты
sudo apt install -y
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git
```

### Установка Docker

```bash
# 3. Добавить Docker GPG ключ
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# 4. Добавить Docker репозиторий
echo \
  "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 5. Установить Docker и Docker Compose
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 6. Проверить версии
docker --version
docker compose version
```

### Настройка Docker

```bash
# 7. Запустить Docker демон и включить автозапуск
sudo systemctl start docker
sudo systemctl enable docker

# 8. Добавить текущего пользователя в группу docker (чтобы не писать sudo)
sudo usermod -aG docker $USER

# Выход и повторный вход для применения изменений
exit
ssh user@ваш_ip_vds

# или просто выполнить:
newgrp docker
```

---

## Этап 2: Клонирование проекта

```bash
# Выбрать рабочую директорию (примеры)
cd /home/user  # или /opt, или /root - на ваш выбор

# Клонировать проект
git clone https://github.com/yourusername/evolveai.git
cd evolveai

# Убедиться что вы на нужной ветке
git status
git branch -a
git checkout main  # если нужна основная ветка
```

---

## Этап 3: Создание и настройка .env файла

### Создание файла

```bash
# Создать .env из примера
cp .env.example .env

# Отредактировать .env
nano .env
# или vi .env
```

### Содержимое .env файла

Вставьте эту конфигурацию в .env файл:

```env
# ===== TELEGRAM =====
TELEGRAM_BOT_TOKEN="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"

# ===== GOOGLE AI =====
GOOGLE_API_KEY="AIza..."

# ===== DATABASE =====
POSTGRES_USER=malter_user
POSTGRES_PASSWORD=your_secure_password_here_min_32_chars_!@#$%^&
POSTGRES_DB=malterdb
DB_HOST=db
DB_PORT=5432

# ===== SECURITY - ОБЯЗАТЕЛЬНО СГЕНЕРИРУЙТЕ! =====
JWT_SECRET=generate_with_openssl_rand_hex_32_min_32_chars_here
ENCRYPTION_KEY=generate_with_python_fernet_here_base64_encoded

# ===== REDIS =====
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
CACHE_TTL_SECONDS=600

# ===== API =====
HTTPX_TIMEOUT=180
HTTPX_CONNECT_TIMEOUT=10

# ===== LOGGING =====
LOG_LEVEL=INFO
```

### Как получить значения для .env

#### TELEGRAM_BOT_TOKEN

```
1. Напишите боту @BotFather в Telegram
2. Команда: /start
3. /newbot
4. Следуйте инструкциям, получите токен вида:
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

#### GOOGLE_API_KEY

```
1. Перейти: https://aistudio.google.com/app/apikey
2. Нажать "Create API Key"
3. Скопировать ключ
```

#### Генерируем безопасные ключи (на локальной машине)

```bash
# JWT_SECRET - используйте openssl или генератор

# Способ 1 (если есть openssl):
openssl rand -hex 32

# Способ 2 (Python - если есть Python):
python -c "import secrets; print(secrets.token_hex(32))"

# ENCRYPTION_KEY - генерируем через Python:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Или используйте онлайн генератор:
# - https://www.random.org/cgi-bin/randbytes?nbytes=32&format=h (для JWT)
# - https://asecuritysite.com/encryption/fernet (для ENCRYPTION_KEY)
```

### Сохранение файла

```bash
# Если используете nano:
# Нажмите Ctrl+S для сохранения
# Нажмите Ctrl+X для выхода

# Если используете vi/vim:
# Нажмите ESC и введите :wq для сохранения и выхода
```

---

## Этап 4: Запуск всех сервисов

### Запуск Docker Compose

```bash
# Убедиться что находимся в директории проекта
pwd
# Должно вывести: /home/user/evolveai (или ваш путь)

# Запустить все контейнеры в фоне (-d = detached mode)
docker compose up -d

# Посмотреть статус контейнеров
docker compose ps

# Ожидаем пока все станут "healthy" (может занять 1-2 минуты)
# Смотрим логи чтобы увидеть прогресс
docker compose logs -f

# Когда видите "Application startup complete" - нажимаете Ctrl+C
```

### Что будет запущено

После выполнения `docker compose up -d` будут запущены 5 сервисов:

1. **api** - FastAPI REST API (4 Gunicorn workers)
2. **bot** - Telegram Bot (aiogram)
3. **db** - PostgreSQL 15.7
4. **redis** - Redis 7.2
5. **migration** - Alembic миграции (одноразовый)

---

## Этап 5: Проверка работоспособности

### Проверки

```bash
# 1. Проверить здоровье API
curl http://localhost:8000/health

# Должен вывести:
# {"status":"ok"}

# 2. Проверить готовность всех зависимостей
curl http://localhost:8000/ready

# Должен вывести что-то вроде:
# {"status":"ready","database":{"status":"healthy"},...}

# 3. Проверить статус контейнеров
docker compose ps

# Все должны быть "Up" и "healthy"
```

### Если что-то не работает

```bash
# Посмотреть логи всех сервисов
docker compose logs -f

# Логи конкретного сервиса
docker compose logs -f api
docker compose logs -f bot
docker compose logs -f db
docker compose logs -f redis
docker compose logs -f migration
```

---

## 📊 Открытие доступа к API из интернета

### Настройка firewall

```bash
# 1. Открыть порт 8000 в firewall (если он установлен)
sudo ufw allow 8000
sudo ufw status

# 2. Если UFW не включен, включить его
sudo ufw enable
```

### Проверка доступности

```bash
# На вашем компьютере проверить доступность
curl http://ваш_vds_ip:8000/health

# Открыть документацию API в браузере
# http://ваш_vds_ip:8000/docs
```

---

## 🔧 Частые команды управления на VDS

### Просмотр логов

```bash
# Просмотр логов в реальном времени
docker compose logs -f

# Логи конкретного контейнера
docker compose logs -f api
docker compose logs -f bot
docker compose logs -f db
docker compose logs -f redis

# Последние 100 строк логов
docker compose logs -f --tail=100

# Логи за последние 10 минут
docker compose logs -f --since=10m
```

### Управление контейнерами

```bash
# Остановить все контейнеры
docker compose down

# Остановить конкретный контейнер
docker compose stop api

# Запустить конкретный контейнер
docker compose start api

# Перезапустить конкретный сервис
docker compose restart api
docker compose restart bot

# Полная переборка (если что-то сломалось)
docker compose down -v
docker compose up -d

# Посмотреть ресурсы (CPU, RAM)
docker stats

# Посмотреть размер контейнеров
docker compose ps -s
```

### Доступ внутрь контейнеров

```bash
# Войти в контейнер API
docker compose exec api bash

# Войти в контейнер БД
docker compose exec db bash

# Подключиться к PostgreSQL
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB

# Подключиться к Redis
docker compose exec redis redis-cli

# Выполнить команду в контейнере
docker compose exec api curl http://localhost:8000/health
```

### Очистка

```bash
# Удалить все stopped контейнеры
docker container prune

# Удалить неиспользуемые volumes
docker volume prune

# Полная очистка (осторожно!)
docker compose down -v
```

---

## 💾 Создание автозапуска Docker Compose

Чтобы приложение автоматически стартовало после перезагрузки VDS:

### Создание systemd сервиса

```bash
# Создать systemd сервис
sudo nano /etc/systemd/system/evolveai.service
```

### Содержимое файла

```ini
[Unit]
Description=EvolveAI Docker Compose Application
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/user/evolveai
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
User=user

[Install]
WantedBy=multi-user.target
```

**⚠️ ОБЯЗАТЕЛЬНО измените:**

- `WorkingDirectory=/home/user/evolveai` - на ваш путь к проекту
- `User=user` - на вашего пользователя

### Активирование

```bash
# Перезагрузить systemd
sudo systemctl daemon-reload

# Включить автозапуск
sudo systemctl enable evolveai.service

# Проверить статус
sudo systemctl status evolveai.service

# Вручную запустить
sudo systemctl start evolveai.service

# Вручную остановить
sudo systemctl stop evolveai.service

# Перезагрузить VDS и убедиться что всё запустилось
sudo reboot
```

---

## 🔐 Дополнительная безопасность для продакшена

### Установка Nginx как reverse proxy

```bash
# 1. Установить Nginx
sudo apt install -y nginx

# 2. Создать конфигурацию
sudo nano /etc/nginx/sites-available/evolveai
```

### Пример конфигурации Nginx

```nginx
upstream evolveai {
    server localhost:8000;
}

server {
    listen 80;
    server_name ваш_домен.com;

    location / {
        proxy_pass http://evolveai;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Активирование конфигурации

```bash
# Создать символическую ссылку
sudo ln -s /etc/nginx/sites-available/evolveai /etc/nginx/sites-enabled/

# Проверить синтаксис
sudo nginx -t

# Перезагрузить Nginx
sudo systemctl restart nginx
```

### Установка SSL (Let's Encrypt)

```bash
# 1. Установить Certbot
sudo apt install -y certbot python3-certbot-nginx

# 2. Получить сертификат
sudo certbot --nginx -d ваш_домен.com

# 3. Сертификаты будут обновляться автоматически
sudo certbot renew --dry-run
```

### Скрытие порта 8000 (дополнительная безопасность)

```bash
# Если Nginx слушает на 80/443, закройте порт 8000 в firewall
sudo ufw delete allow 8000
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
```

---

## 📊 Мониторинг приложения

### Проверка метрик

```bash
# Метрики Prometheus
curl http://localhost:8000/metrics

# Метрики БД
curl http://localhost:8000/admin/db_metrics

# Статус scheduler
curl http://localhost:8000/admin/scheduler_status

# Статистика кэша
curl http://localhost:8000/admin/cache_stats
```

### Мониторинг ресурсов

```bash
# Просмотр использования памяти и CPU контейнерами
docker stats

# Просмотр использования дискового пространства
df -h
docker system df

# Проверка логов на ошибки
docker compose logs -f | grep ERROR
```

---

## 💾 Резервное копирование

### Резервная копия базы данных

```bash
# Создать резервную копию PostgreSQL
docker compose exec db pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup_$(date +%Y%m%d_%H%M%S).sql

# Восстановить из резервной копии
docker compose exec -T db psql -U $POSTGRES_USER $POSTGRES_DB < backup_20250101_120000.sql
```

### Резервная копия volumes

```bash
# Создать резервную копию всех volumes
docker run --rm -v evolveai_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz /data

# Восстановить volumes
docker run --rm -v evolveai_postgres_data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres_backup.tar.gz -C /
```

---

## 🛠 Решение проблем

### Docker не запускается

```bash
# Проверить статус Docker
sudo systemctl status docker

# Перезагрузить Docker
sudo systemctl restart docker

# Посмотреть логи Docker
sudo journalctl -u docker -f
```

### Контейнеры падают при старте

```bash
# Посмотреть полные логи
docker compose logs

# Проверить что .env файл существует
ls -la .env

# Проверить что переменные окружения установлены
docker compose config | grep POSTGRES_PASSWORD
```

### Нет доступа к API

```bash
# Проверить что контейнер запущен
docker compose ps

# Проверить что порт слушается
netstat -tuln | grep 8000
# или
ss -tuln | grep 8000

# Проверить правила firewall
sudo ufw status
```

### Redis не подключается

```bash
# Проверить статус Redis
docker compose ps redis

# Проверить доступность Redis
docker compose exec redis redis-cli ping

# Перезагрузить Redis
docker compose restart redis
```

### БД не готова при старте

```bash
# Проверить логи миграций
docker compose logs migration

# Проверить логи БД
docker compose logs db

# Если проблема - перестроить с чистой БД
docker compose down -v
docker compose up -d
```

---

## 📚 Дополнительные команды

### Обновление приложения

```bash
# Обновить код из репозитория
git pull origin main

# Перестроить контейнеры с новым кодом
docker compose down
docker compose up -d --build

# или (без остановки других сервисов)
docker compose up -d --build api bot
```

### Просмотр конфигурации

```bash
# Посмотреть полную конфигурацию Docker Compose с переменными
docker compose config

# Посмотреть только переменные окружения
docker compose config | grep -A 100 "environment:"
```

### Проверка портов

```bash
# Посмотреть какие порты слушают контейнеры
docker compose ps

# Проверить что порт открыт на сервере
telnet localhost 8000
# или
nc -zv localhost 8000
```

---

## ✅ Чек-лист для полного развертывания

- [ ] SSH доступ к VDS работает
- [ ] Docker и Docker Compose установлены
- [ ] Проект клонирован в правильную директорию
- [ ] .env файл создан и заполнен всеми параметрами
- [ ] TELEGRAM_BOT_TOKEN получен от @BotFather
- [ ] GOOGLE_API_KEY получен с aistudio.google.com
- [ ] JWT_SECRET и ENCRYPTION_KEY сгенерированы
- [ ] `docker compose up -d` выполнен успешно
- [ ] `docker compose ps` показывает все контейнеры как "Up" и "healthy"
- [ ] `curl http://localhost:8000/health` возвращает OK
- [ ] Firewall настроен на открытие портов 80/443/8000
- [ ] Проект доступен по IP VDS в браузере
- [ ] Автозапуск настроен (systemd сервис)
- [ ] Резервные копии БД создаются регулярно

---

## 📞 Полезные ссылки

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/reference/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Let&#39;s Encrypt](https://letsencrypt.org/)

---

**Последнее обновление:** 2025-10-30

**Для вопросов и помощи обратитесь к документации проекта или создайте issue в репозитории.**
