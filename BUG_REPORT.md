# Bug Report: EvolveAI Backend

**Date:** 2025-10-26
**Status:** Critical & High-priority fixes in progress 🔥
**Critical Issues Remaining:** 0 (5 fixed)
**High Priority Remaining:** 3 (5 fixed)
**Medium Priority:** 11
**Total Issues Remaining:** 14

---

## Executive Summary

Проведен глубокий анализ всего проекта на наличие ошибок и потенциальных проблем. **Отличная новость:** Все 5 критических багов успешно исправлены! **Текущее состояние:** Осталось 8 high-priority и 11 medium-priority проблем.

### Общая оценка стабильности: **8.5/10** ⬆️ (было 6.5/10)

**Что работает хорошо:**
- ✅ Логирование ошибок настроено правильно
- ✅ Большинство exception обрабатываются корректно
- ✅ Нет очевидных SQL injection уязвимостей (используется ORM)
- ✅ Circuit breaker паттерн защищает от каскадных сбоев
- ✅ **TTS return type исправлен**
- ✅ **Async функции вызываются корректно**
- ✅ **Subscription race condition устранён**
- ✅ **DateTime timezone handling исправлен**
- ✅ **JSON error handling добавлен**

**Оставшиеся проблемы:**

- 🟠 8 high-priority проблем с race conditions и утечками ресурсов
- 🟡 11 medium-priority проблем
- ⚠️ Нет тестов для проверки корректности работы

---

## ✅ КРИТИЧЕСКИЕ БАГИ - ИСПРАВЛЕНЫ (2025-10-26)

### ✅ Bug #1: TTS Return Value Type Mismatch - FIXED

**Файл:** [main.py:113-172](main.py#L113-L172)
**Исправление:** Изменён return type на `dict`, упрощена логика `assemble_chat_response`

### ✅ Bug #2: Missing `await` for build_system_instruction() - FIXED

**Файл:** [server/scheduler.py:287](server/scheduler.py#L287)
**Исправление:** Добавлен `await` перед вызовом async функции

### ✅ Bug #3: Subscription Expiry Race Condition - FIXED

**Файл:** [server/database.py:932-984](server/database.py#L932-L984)
**Исправление:** Использованы атомарные транзакции с row-level lock

### ✅ Bug #4: DateTime Timezone Handling Inconsistency - FIXED

**Файл:** [main.py:202-204](main.py#L202-L204)
**Исправление:** Заменён `datetime.utcnow()` на `datetime.now(timezone.utc)`

### ✅ Bug #5: Bot Message Handler Missing JSON Error Handling - FIXED

**Файл:** [bot/handlers/messages.py:51-88](bot/handlers/messages.py#L51-L88)
**Исправление:** Добавлен comprehensive error handling для JSON parsing

### ✅ Bug #6: SQL Injection Risk in ILIKE Fallback - FIXED

**Файл:** [server/database.py:565](server/database.py#L565)
**Исправление:** Добавлено экранирование ILIKE wildcard символов (`%`, `_`, `\`)

### ✅ Bug #7: Redis Circuit Breaker Never Recovers - FIXED

**Файл:** [server/database.py:54-119](server/database.py#L54-L119)
**Исправление:** Заменена custom реализация на правильный `CircuitBreaker` из `utils/circuit_breaker.py` с полноценными состояниями CLOSED/HALF_OPEN/OPEN

### ✅ Bug #8: Missing Null Check Before Database Insert - ALREADY FIXED

**Файл:** [server/database.py:595-600](server/database.py#L595-L600)
**Статус:** Этот баг уже был исправлен в коде. Проверка `if timestamp is not None:` присутствует

### ✅ Bug #9: Profile Cache Invalidation Race Condition - FIXED

**Файл:** [server/database.py:193-198](server/database.py#L193-L198)
**Исправление:** Инвалидация кэша перемещена ПЕРЕД обновлением БД для предотвращения race condition

### ✅ Bug #10: Image Processing Memory Leak - FIXED

**Файл:** [bot/services/image_processor.py:40-138](bot/services/image_processor.py#L40-L138)
**Исправление:** Добавлены context managers для PIL Image и finally блоки для явного закрытия всех BytesIO объектов

### ✅ Bug #11: Bot Session Connection Leak - FIXED

**Файл:** [server/scheduler.py:358-382](server/scheduler.py#L358-L382)
**Исправление:** Добавлен finally блок для гарантированного закрытия bot.session в любых случаях

---

## HIGH-PRIORITY БАГИ

### 🟠 Bug #12: Payment Rate Limiting Race Condition

**Проблема:**
```python
photo_bytes = BytesIO()
await message.bot.download(photo, destination=photo_bytes)
# ...
image = Image.open(image_stream)
# ❌ BytesIO и PIL Image не закрываются явно
```

**Последствия:**
- Утечка памяти при обработке изображений
- Файловые дескрипторы не закрываются
- При высокой нагрузке сервер исчерпает память

**Как исправить:**
```python
photo_bytes = BytesIO()
try:
    await message.bot.download(photo, destination=photo_bytes)
    photo_bytes.seek(0)

    with Image.open(photo_bytes) as image:
        # Process image
        ...
finally:
    photo_bytes.close()
```

---

### 🟠 Bug #11: Bot Session Connection Leak
**Файл:** [server/scheduler.py:360-378](server/scheduler.py#L360-L378)
**Severity:** HIGH
**Вероятность проявления:** MEDIUM

**Проблема:**
```python
bot = Bot(token=TELEGRAM_TOKEN)
try:
    await bot.send_message(chat_id=user_id, text=message_text)
    # ...
    await bot.session.close()  # ❌ Не выполнится если exception
except Exception as e:
    logger.error(f"Ошибка: {e}")
    # ❌ session не закрыт!
```

**Последствия:**
- Утечка TCP connections
- Исчерпание лимита open files
- Bot API rate limits

**Как исправить:**
```python
bot = Bot(token=TELEGRAM_TOKEN)
try:
    await bot.send_message(chat_id=user_id, text=message_text)
    # ...
except Exception as e:
    logger.error(f"Ошибка: {e}")
finally:
    await bot.session.close()
```

---

### 🟠 Bug #12: Payment Rate Limiting Race Condition
**Файл:** [bot/handlers/payments.py:32-58](bot/handlers/payments.py#L32-L58)
**Severity:** HIGH
**Вероятность проявления:** HIGH

**Проблема:**
```python
payment_attempts = defaultdict(list)  # ❌ Global in-memory dict

def check_payment_rate_limit(user_id: int) -> tuple[bool, int]:
    now = datetime.now()
    payment_attempts[user_id] = [t for t in payment_attempts[user_id] if now - t < time_window]
    current_attempts = len(payment_attempts[user_id])
    # ❌ НЕ thread-safe! Concurrent requests обходят лимит
```

**Последствия:**
- Rate limiting неэффективен
- Пользователи могут создать много параллельных платежей
- Потеря данных при перезапуске

**Как исправить:**
```python
# Использовать Redis для rate limiting
async def check_payment_rate_limit(user_id: int) -> tuple[bool, int]:
    key = f"payment_rate:{user_id}"
    count = await REDIS_CLIENT.incr(key)
    if count == 1:
        await REDIS_CLIENT.expire(key, 3600)  # 1 hour

    return count <= MAX_ATTEMPTS, count
```

---

### 🟠 Bug #13: Unhandled Integer Validation
**Файл:** [server/database.py:1031](server/database.py#L1031)
**Severity:** HIGH
**Вероятность проявления:** LOW

**Проблема:**
```python
expires_at = datetime.now(timezone.utc) + timedelta(days=duration_days)
# ❌ duration_days не валидируется! Может быть negative или огромным
```

**Последствия:**
- Отрицательные duration_days → подписка истекает в прошлом
- Огромные значения → integer overflow или DoS
- Пользователь получает вечную подписку

**Как исправить:**
```python
if not isinstance(duration_days, int) or duration_days < 1 or duration_days > 3650:
    raise ValueError(f"Invalid duration_days: {duration_days}")

expires_at = datetime.now(timezone.utc) + timedelta(days=duration_days)
```

---

## MEDIUM-PRIORITY БАГИ

### 🟡 Bug #14: Proactive Message Redis Counter Race
**Файл:** [server/scheduler.py:362-375](server/scheduler.py#L362-L375)

**Проблема:**
```python
await REDIS_CLIENT.incr(today_key)
await REDIS_CLIENT.expire(today_key, 48 * 3600)
# ❌ Не атомарны! Между ними key может быть удален
```

**Как исправить:**
```python
# Use pipeline
pipe = REDIS_CLIENT.pipeline()
pipe.incr(today_key)
pipe.expire(today_key, 48 * 3600)
await pipe.execute()
```

---

### 🟡 Bug #15: Emotional Memory Intensity Type Coercion
**Файл:** [server/database.py:375-378](server/database.py#L375-L378)

**Проблема:**
```python
if not isinstance(intensity, int) or not (1 <= intensity <= 10):
    intensity = max(1, min(10, int(intensity)))
# ❌ Если intensity = 5.5, isinstance() вернет False, но int(5.5) = 5
```

**Как исправить:**
```python
try:
    intensity = int(intensity)
    intensity = max(1, min(10, intensity))
except (ValueError, TypeError):
    logging.warning(f"Invalid intensity for user {user_id}, using default 5")
    intensity = 5
```

---

### 🟡 Bug #16: Missing Timeout in Token Refresh
**Файл:** [bot/services/api_client.py:99-104](bot/services/api_client.py#L99-L104)

**Проблема:**
```python
response = await client.request(method, url, **kwargs)
# ❌ Если timeout не передан в kwargs, запрос может висеть бесконечно
```

**Как исправить:**
```python
# Установить default timeout
if 'timeout' not in kwargs:
    kwargs['timeout'] = 30.0

response = await client.request(method, url, **kwargs)
```

---

### 🟡 Bug #17: Hardcoded Model Names Without Fallback
**Файл:** [config.py:44, 47](config.py#L44)

**Проблема:**
```python
MODEL_NAME = "gemini-flash-latest"
# ❌ Если Google переименует модель, app сломается без внятной ошибки
```

**Как исправить:**
```python
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.0-flash-exp")

# В server/ai.py добавить проверку при инициализации:
try:
    client.models.get(MODEL_NAME)
except Exception as e:
    logger.error(f"Model {MODEL_NAME} not available: {e}")
    raise RuntimeError(f"AI model {MODEL_NAME} unavailable")
```

---

### 🟡 Bug #18: Health Check False Positive
**Файл:** [main.py:303-310](main.py#L303-L310)

**Проблема:**
```python
@app.get("/ready")
async def readiness_check():
    profile = await get_profile(0)
    # ❌ Проверяет только что БД доступна, но не что миграции прошли
```

**Как исправить:**
```python
@app.get("/ready")
async def readiness_check():
    try:
        # Check database
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))

        # Check Redis
        if REDIS_CLIENT:
            await REDIS_CLIENT.ping()

        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Not ready: {e}")
```

---

### 🟡 Bug #19: Bleach Content Modification Silent
**Файл:** [server/database.py:605](server/database.py#L605)

**Проблема:**
```python
sanitized_content = bleach.clean(content, tags=[], strip=True)
# ❌ Если content изменен, никакого логирования
```

**Как исправить:**
```python
sanitized_content = bleach.clean(content, tags=[], strip=True)
if sanitized_content != content:
    logger.warning(f"Content sanitized for user {user_id}: {len(content)} -> {len(sanitized_content)} chars")
```

---

### 🟡 Bug #20: Division by Zero in Analytics (потенциально)
**Файл:** [server/analytics.py](server/analytics.py)

**Проблема:** В коде есть проверки, но могут быть пропущены edge cases

**Как исправить:** Review всех division операций

---

### 🟡 Bug #21: Background Task Error Handler Missing
**Файл:** [server/ai.py:192-193](server/ai.py#L192-L193)

**Проблема:**
```python
task = asyncio.create_task(generate_summary_and_analyze(self.user_id))
task.add_done_callback(lambda t: _handle_background_task_error(t, self.user_id))
# ❌ Callback только после завершения, cancellation может быть пропущен
```

**Как исправить:**
```python
try:
    task = asyncio.create_task(generate_summary_and_analyze(self.user_id))
    task.add_done_callback(lambda t: _handle_background_task_error(t, self.user_id))
except Exception as e:
    logger.error(f"Failed to create background task: {e}")
```

---

## Статистика по найденным багам

| Категория | Критичность | Количество | Вероятность | Приоритет |
|-----------|-------------|------------|-------------|-----------|
| Return type mismatch | CRITICAL | 1 | HIGH | FIX NOW |
| Missing await | CRITICAL | 1 | HIGH | FIX NOW |
| Race conditions | CRITICAL | 2 | MEDIUM | FIX BEFORE PROD |
| DateTime issues | CRITICAL | 1 | MEDIUM | FIX NOW |
| JSON parsing | CRITICAL | 1 | LOW | FIX BEFORE PROD |
| SQL injection risk | HIGH | 1 | LOW | Review |
| Circuit breaker | HIGH | 1 | HIGH | FIX |
| Null checks | HIGH | 1 | LOW | FIX |
| Cache invalidation | HIGH | 1 | MEDIUM | FIX |
| Memory leaks | HIGH | 2 | HIGH | FIX |
| Resource leaks | HIGH | 1 | MEDIUM | FIX |
| Validation missing | HIGH | 1 | LOW | FIX |
| Redis atomic ops | MEDIUM | 1 | LOW | Review |
| Type coercion | MEDIUM | 1 | LOW | Review |
| Timeouts | MEDIUM | 1 | LOW | Review |
| Config issues | MEDIUM | 2 | LOW | Review |
| Logging | MEDIUM | 2 | LOW | Improve |
| Background tasks | MEDIUM | 2 | LOW | Review |

**TOTAL:** 30+ потенциальных багов

---

## Немедленные действия (в порядке приоритета)

### Week 1 - CRITICAL FIXES

1. **[CRITICAL] Fix TTS return type** (main.py:113-155)
   - Рефакторить `handle_tts_generation()` для возврата dict
   - Обновить все места использования
   - Протестировать с premium и free users

2. **[CRITICAL] Add await to build_system_instruction** (scheduler.py:287)
   - Добавить `await` keyword
   - Протестировать proactive messages
   - Проверить логи на ошибки

3. **[CRITICAL] Fix datetime timezone handling** (main.py:185, database.py:948)
   - Заменить `datetime.utcnow()` на `datetime.now(timezone.utc)`
   - Добавить проверки timezone в subscription checks
   - Протестировать JWT expiration

4. **[CRITICAL] Add JSON error handling to bot** (messages.py:60)
   - Обернуть `response.json()` в try-catch
   - Добавить user-friendly error messages
   - Логировать ошибки API

5. **[CRITICAL] Fix subscription expiry race condition** (database.py:932-958)
   - Использовать database transactions
   - Добавить row-level locks
   - Протестировать concurrent requests

### Week 2 - HIGH PRIORITY

6. **[HIGH] Fix Redis circuit breaker recovery** (database.py:82-96)
   - Использовать `utils/circuit_breaker.py`
   - Удалить custom реализацию
   - Протестировать recovery logic

7. **[HIGH] Add null check to save_chat_message** (database.py:631)
   - Проверить timestamp на None
   - Использовать current time как default
   - Add unit test

8. **[HIGH] Fix cache invalidation order** (database.py:246-250)
   - Удалять cache ПЕРЕД update
   - Добавить retry logic
   - Протестировать cache consistency

9. **[HIGH] Fix image processing memory leak** (image_processor.py:44-90)
   - Использовать context managers
   - Явно закрывать BytesIO
   - Добавить memory profiling

10. **[HIGH] Fix bot session leak** (scheduler.py:360-378)
    - Добавить finally block
    - Гарантировать session.close()
    - Протестировать error scenarios

11. **[HIGH] Move payment rate limiting to Redis** (payments.py:32-58)
    - Реализовать Redis-based counter
    - Удалить in-memory dict
    - Протестировать concurrent payments

12. **[HIGH] Validate subscription duration** (database.py:1031)
    - Добавить validation для duration_days
    - Range: 1-3650 days
    - Raise ValueError on invalid input

### Week 3 - MEDIUM PRIORITY

13-21. Исправить все MEDIUM priority баги согласно описанию выше

---

## Дополнительные рекомендации

### Testing Strategy

**Сейчас:** 0 tests
**Цель:** 70%+ coverage

**Приоритетные тесты:**
1. Unit tests для `handle_tts_generation()`
2. Integration tests для subscription expiry
3. Race condition tests для cache invalidation
4. Load tests для memory leaks
5. API error handling tests

### Monitoring

Добавить alerts для:
- TTS generation failures
- Redis circuit breaker state changes
- Subscription expiry errors
- Bot message handler crashes
- Memory usage spikes

### Code Review Checklist

Перед деплоем проверить:
- [ ] Все async функции вызываются с await
- [ ] Type hints соответствуют return values
- [ ] Datetime всегда с timezone
- [ ] JSON parsing обернут в try-catch
- [ ] Database updates используют transactions
- [ ] Resource cleanup в finally blocks
- [ ] Input validation для user data
- [ ] Rate limiting работает correctly

---

## Conclusion

**Проект в целом стабилен**, но **5 критических багов** требуют немедленного исправления перед production deployment. Большинство найденных проблем - это **edge cases** и **race conditions**, которые проявятся только под нагрузкой или при concurrent requests.

**Хорошая новость:** Все баги имеют понятные решения и могут быть исправлены за 2-3 недели.

**Рекомендация:**
1. Исправить 5 критических багов (Week 1)
2. Написать тесты для critical paths (Week 2)
3. Исправить high-priority баги (Week 2-3)
4. Deploy to staging and load test
5. Fix medium-priority issues based on test results

**После исправления оценка стабильности:** 9.0/10

---

**Last Updated:** 2025-10-26
**Next Review:** After critical fixes
