# TODO: Bug Fixes for EvolveAI

**Created:** 2025-10-26
**Priority:** HIGH
**Estimated Time:** 3 weeks
**Impact:** Production Readiness

---

## 📋 Overview

This TODO list contains all bug fixes identified in the comprehensive code analysis. Bugs are organized by priority (CRITICAL → HIGH → MEDIUM) and estimated time to fix.

**Total Issues:** 30+
- **CRITICAL:** 5 bugs (must fix before production)
- **HIGH:** 8 bugs (fix before scaling)
- **MEDIUM:** 11+ bugs (fix for quality)

---

## 🔴 CRITICAL PRIORITY - Week 1 (MUST FIX IMMEDIATELY)

### ✅ Bug #1: Fix TTS Return Type Mismatch
**File:** [main.py:113-155, 430](main.py#L113-L155)
**Estimated Time:** 2 hours
**Difficulty:** Medium
**Impact:** Voice messages broken for premium users

**Tasks:**
- [ ] Refactor `handle_tts_generation()` to return dict instead of tuple
- [ ] Update function signature: `-> dict[str, str | None]`
- [ ] Change line 148: `return {"text": text_to_speak, "voice_data": voice_message_data}`
- [ ] Change line 128: `return {"text": clean_text, "voice_data": None}`
- [ ] Change line 155: `return {"text": response_text, "voice_data": None}`
- [ ] Update line 430 to unpack dict: `result = await handle_tts_generation(...)`
- [ ] Update line 430: `response_text = result["text"]`
- [ ] Update line 430: `voice_message_data = result.get("voice_data")`
- [ ] Simplify `assemble_chat_response()` (lines 157-173) to accept plain values
- [ ] Test with premium user (voice should be generated)
- [ ] Test with free user (voice marker should be stripped)
- [ ] Add unit tests for all three return scenarios

**Code to implement:**
```python
# New signature:
async def handle_tts_generation(user_id: int, response_text: str) -> dict[str, str | None]:
    """
    Returns:
        dict with keys:
            - "text": str - cleaned text to display
            - "voice_data": str | None - base64 encoded voice or None
    """
    # ... existing logic ...
    if has_voice_marker:
        if not is_premium:
            clean_text = strip_voice_markers(response_text)
            return {"text": clean_text, "voice_data": None}
        else:
            # ... TTS generation ...
            if success:
                return {"text": text_to_speak, "voice_data": voice_message_data}
            else:
                clean_text = strip_voice_markers(response_text)
                return {"text": clean_text, "voice_data": None}

    return {"text": response_text, "voice_data": None}

# Usage at line 430:
result = await handle_tts_generation(user_id, response_text)
response_text = result["text"]
voice_message_data = result.get("voice_data")
```

---

### ✅ Bug #2: Add Missing `await` for build_system_instruction()
**File:** [server/scheduler.py:287](server/scheduler.py#L287)
**Estimated Time:** 5 minutes
**Difficulty:** Easy
**Impact:** Proactive messages completely broken

**Tasks:**
- [ ] Open [server/scheduler.py](server/scheduler.py#L287)
- [ ] Change line 287 from: `system_instruction = build_system_instruction(profile, latest_summary)`
- [ ] To: `system_instruction = await build_system_instruction(profile, latest_summary)`
- [ ] Save file
- [ ] Test proactive messages job
- [ ] Check logs for successful message generation
- [ ] Verify no "system_instruction must be string" errors

**Code change:**
```python
# Line 287 - BEFORE:
system_instruction = build_system_instruction(profile, latest_summary)

# Line 287 - AFTER:
system_instruction = await build_system_instruction(profile, latest_summary)
```

---

### ✅ Bug #3: Fix DateTime Timezone Handling
**Files:**
- [main.py:185](main.py#L185)
- [server/database.py:948](server/database.py#L948)

**Estimated Time:** 1 hour
**Difficulty:** Easy
**Impact:** JWT tokens expire incorrectly, subscription timing issues

**Tasks:**
- [ ] Replace `datetime.utcnow()` with `datetime.now(timezone.utc)` in main.py:185
- [ ] Add import at top of main.py: `from datetime import datetime, timedelta, timezone`
- [ ] Fix subscription expiry check in database.py:948
- [ ] Add timezone conversion helper function
- [ ] Search codebase for all `datetime.utcnow()` usage: `rg "datetime\.utcnow"`
- [ ] Replace all occurrences with `datetime.now(timezone.utc)`
- [ ] Test JWT token generation and expiration
- [ ] Test subscription expiry check with timezone-aware datetimes
- [ ] Add unit tests for timezone handling

**Code changes:**
```python
# main.py:185 - BEFORE:
expire = datetime.utcnow() + timedelta(minutes=15)

# main.py:185 - AFTER:
from datetime import datetime, timedelta, timezone
expire = datetime.now(timezone.utc) + timedelta(minutes=15)

# database.py:948 - BEFORE:
if profile.subscription_expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):

# database.py:948 - AFTER:
expires_aware = (
    profile.subscription_expires.replace(tzinfo=timezone.utc)
    if profile.subscription_expires.tzinfo is None
    else profile.subscription_expires
)
if expires_aware < datetime.now(timezone.utc):
```

---

### ✅ Bug #4: Add JSON Error Handling in Bot Message Handler
**File:** [bot/handlers/messages.py:60](bot/handlers/messages.py#L60)
**Estimated Time:** 30 minutes
**Difficulty:** Easy
**Impact:** Bot crashes on API errors

**Tasks:**
- [ ] Open [bot/handlers/messages.py](bot/handlers/messages.py#L60)
- [ ] Wrap lines 57-61 in try-except block
- [ ] Add import: `import json`
- [ ] Add import: `import httpx`
- [ ] Handle `httpx.HTTPStatusError`
- [ ] Handle `json.JSONDecodeError`
- [ ] Add user-friendly error messages
- [ ] Log errors with full context
- [ ] Test with simulated API errors
- [ ] Test with invalid JSON responses

**Code to implement:**
```python
# Around line 57-61 in messages.py
try:
    response = await make_api_request(
        method="POST",
        endpoint="/chat",
        json=request_data,
        timeout=180.0
    )
    response.raise_for_status()
    data = response.json()
    await send_response(message, data)

except httpx.HTTPStatusError as e:
    logger.error(
        f"API HTTP error for user {message.from_user.id}: "
        f"status={e.response.status_code}, body={e.response.text[:200]}"
    )
    await message.answer(
        "Прости, что-то пошло не так на сервере... 😔 Попробуй написать чуть позже?"
    )

except json.JSONDecodeError as e:
    logger.error(
        f"Invalid JSON from API for user {message.from_user.id}: {e}"
    )
    await message.answer(
        "Ой, у меня голова кругом... Дай мне минутку, окей? 😵"
    )

except Exception as e:
    logger.error(
        f"Unexpected error in message handler for user {message.from_user.id}: {e}",
        exc_info=True
    )
    await message.answer(
        "Что-то совсем странное произошло... Попробуй ещё раз? 🤔"
    )
```

---

### ✅ Bug #5: Fix Subscription Expiry Race Condition
**File:** [server/database.py:932-958](server/database.py#L932-L958)
**Estimated Time:** 2 hours
**Difficulty:** Hard
**Impact:** Concurrent requests cause subscription inconsistency

**Tasks:**
- [ ] Refactor `check_subscription_expiry()` to use atomic transaction
- [ ] Add `with_for_update()` for row-level locking
- [ ] Remove separate `get_profile()` call
- [ ] Combine check and update in single transaction
- [ ] Test with concurrent requests (use pytest-asyncio)
- [ ] Verify no duplicate updates
- [ ] Check cache invalidation still works
- [ ] Add integration test with 10+ concurrent calls
- [ ] Measure performance impact of row locking

**Code to implement:**
```python
async def check_subscription_expiry(user_id: int) -> bool:
    """
    Проверяет и обновляет истекшую подписку атомарно.

    Returns:
        True если подписка была обновлена (истекла)
        False если подписка активна или не существует
    """
    async with async_session_factory() as session:
        async with session.begin():
            # Получаем профиль с row-level lock
            result = await session.execute(
                select(UserProfile)
                .where(UserProfile.user_id == user_id)
                .with_for_update()  # ✅ Блокирует строку до конца транзакции
            )
            profile = result.scalar_one_or_none()

            if not profile or not profile.subscription_expires:
                return False

            # Проверяем expiry
            expires_aware = (
                profile.subscription_expires.replace(tzinfo=timezone.utc)
                if profile.subscription_expires.tzinfo is None
                else profile.subscription_expires
            )

            if expires_aware < datetime.now(timezone.utc):
                # Подписка истекла - обновляем в той же транзакции
                profile.subscription_plan = 'free'
                profile.subscription_expires = None
                await session.commit()

                # Инвалидируем кэш после commit
                cache_key = get_profile_cache_key(user_id)
                await _safe_redis_delete(cache_key)

                logging.info(f"Subscription expired for user {user_id}, downgraded to free")
                return True

            return False
```

---

## 🟠 HIGH PRIORITY - Week 2 (Fix Before Scaling)

### ✅ Bug #6: Fix SQL Injection Risk in ILIKE Fallback
**File:** [server/database.py:567](server/database.py#L567)
**Estimated Time:** 30 minutes
**Difficulty:** Easy
**Impact:** Security vulnerability

**Tasks:**
- [ ] Open [server/database.py](server/database.py#L567)
- [ ] Escape ILIKE wildcards (%, _) in sanitized_query
- [ ] Create helper function `escape_ilike_pattern()`
- [ ] Apply escaping before line 567
- [ ] Test with queries containing %, _, \
- [ ] Add unit tests for edge cases
- [ ] Document security measure

**Code to implement:**
```python
def escape_ilike_pattern(text: str) -> str:
    """Escape ILIKE/LIKE wildcards to prevent injection."""
    return text.replace('\\', '\\\\').replace('%', r'\%').replace('_', r'\_')

# Line 567 - BEFORE:
LongTermMemory.fact.ilike(f"%{sanitized_query}%")

# Line 567 - AFTER:
escaped_query = escape_ilike_pattern(sanitized_query)
LongTermMemory.fact.ilike(f"%{escaped_query}%")
```

---

### ✅ Bug #7: Replace Custom Redis Circuit Breaker
**File:** [server/database.py:82-96](server/database.py#L82-L96)
**Estimated Time:** 1 hour
**Difficulty:** Medium
**Impact:** Redis never recovers from failures

**Tasks:**
- [ ] Remove `RedisCircuitBreaker` class definition (lines 64-120)
- [ ] Import existing CircuitBreaker from utils
- [ ] Replace instantiation at line 122
- [ ] Update all `redis_circuit_breaker.can_attempt()` calls
- [ ] Update all `redis_circuit_breaker.record_success/failure()` calls
- [ ] Test Redis recovery after failures
- [ ] Verify HALF_OPEN state works correctly
- [ ] Add monitoring for circuit breaker state changes

**Code to implement:**
```python
# Remove lines 64-120 (custom RedisCircuitBreaker class)

# Add import at top:
from utils.circuit_breaker import CircuitBreaker

# Replace line 122:
redis_circuit_breaker = CircuitBreaker(
    name="redis",
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=Exception,
    success_threshold=2
)

# Usage stays the same - CircuitBreaker has same interface
```

---

### ✅ Bug #8: Add Null Check in save_chat_message()
**File:** [server/database.py:631-632](server/database.py#L631-L632)
**Estimated Time:** 15 minutes
**Difficulty:** Easy
**Impact:** Crashes when timestamp is None

**Tasks:**
- [ ] Add null check before line 631
- [ ] Use `datetime.now()` as default if timestamp is None
- [ ] Update function docstring to document behavior
- [ ] Test with `timestamp=None`
- [ ] Test with timezone-aware and naive datetimes
- [ ] Add unit test

**Code to implement:**
```python
# Line 620-632 - BEFORE:
async def save_chat_message(
    user_id: int,
    role: str,
    content: str,
    timestamp: datetime | None = None
):
    # ...
    naive_timestamp = timestamp.replace(tzinfo=None) if timestamp.tzinfo else timestamp

# Line 620-632 - AFTER:
async def save_chat_message(
    user_id: int,
    role: str,
    content: str,
    timestamp: datetime | None = None
):
    # ...
    if timestamp is None:
        naive_timestamp = datetime.now()
    elif timestamp.tzinfo is not None:
        naive_timestamp = timestamp.replace(tzinfo=None)
    else:
        naive_timestamp = timestamp
```

---

### ✅ Bug #9: Fix Cache Invalidation Order
**File:** [server/database.py:246-250](server/database.py#L246-L250)
**Estimated Time:** 30 minutes
**Difficulty:** Easy
**Impact:** Users see stale profile data

**Tasks:**
- [ ] Move cache deletion BEFORE database update
- [ ] Add retry logic for cache deletion
- [ ] Log if cache deletion fails
- [ ] Test cache consistency after updates
- [ ] Verify premium activation is immediate
- [ ] Add integration test

**Code to implement:**
```python
# Around lines 246-250 - BEFORE:
await create_or_update_profile(user_id, update_data)
cache_key = get_profile_cache_key(user_id)
deleted = await _safe_redis_delete(cache_key)

# Around lines 246-250 - AFTER:
# Delete cache BEFORE updating DB to prevent stale reads
cache_key = get_profile_cache_key(user_id)
deleted = await _safe_redis_delete(cache_key)
if not deleted:
    logging.warning(f"Failed to invalidate cache for user {user_id} before update")

await create_or_update_profile(user_id, update_data)
```

---

### ✅ Bug #10: Fix Image Processing Memory Leak
**File:** [bot/services/image_processor.py:44-90](bot/services/image_processor.py#L44-L90)
**Estimated Time:** 45 minutes
**Difficulty:** Medium
**Impact:** Memory leaks under high load

**Tasks:**
- [ ] Wrap BytesIO objects in try-finally
- [ ] Use context managers for PIL Images
- [ ] Add explicit `.close()` calls
- [ ] Test memory usage before/after
- [ ] Use memory profiler to verify fix
- [ ] Add cleanup in error paths
- [ ] Document resource management

**Code to implement:**
```python
# Around lines 44-90 - refactor to:
async def process_image_message(message: Message) -> str | None:
    """Process image with proper resource cleanup."""
    photo_bytes = BytesIO()

    try:
        photo = message.photo[-1]
        await message.bot.download(photo, destination=photo_bytes)
        photo_bytes.seek(0)

        raw_data = photo_bytes.read()

        # Validate size
        size_mb = len(raw_data) / (1024 * 1024)
        if size_mb > MAX_IMAGE_SIZE_MB:
            await message.answer(f"Изображение слишком большое ({size_mb:.1f} MB)...")
            return None

        # Process with PIL
        image_stream = BytesIO(raw_data)
        try:
            with Image.open(image_stream) as image:
                # Convert to RGB if needed
                if image.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    if image.mode == 'P':
                        image = image.convert('RGBA')
                    if image.mode == 'RGBA':
                        background.paste(image, mask=image.split()[-1])
                        image = background

                # Save to bytes
                output_bytes = BytesIO()
                try:
                    image.save(output_bytes, format='JPEG', quality=85)
                    output_bytes.seek(0)
                    return base64.b64encode(output_bytes.read()).decode('utf-8')
                finally:
                    output_bytes.close()

        finally:
            image_stream.close()

    except Exception as e:
        logger.error(f"Error processing image: {e}", exc_info=True)
        return None
    finally:
        photo_bytes.close()
```

---

### ✅ Bug #11: Fix Bot Session Connection Leak
**File:** [server/scheduler.py:360-378](server/scheduler.py#L360-L378)
**Estimated Time:** 15 minutes
**Difficulty:** Easy
**Impact:** TCP connection leaks

**Tasks:**
- [ ] Add finally block to ensure session cleanup
- [ ] Move `bot.session.close()` to finally
- [ ] Test with simulated exceptions
- [ ] Verify connections are closed in error cases
- [ ] Check for other Bot instances without cleanup
- [ ] Add logging for cleanup

**Code to implement:**
```python
# Around lines 360-378 - BEFORE:
bot = Bot(token=TELEGRAM_TOKEN)
try:
    await bot.send_message(chat_id=user_id, text=message_text)
    # ...
    await bot.session.close()
except Exception as e:
    logger.error(f"Ошибка: {e}")

# Around lines 360-378 - AFTER:
bot = Bot(token=TELEGRAM_TOKEN)
try:
    await bot.send_message(chat_id=user_id, text=message_text)
    # ... rest of logic ...
except Exception as e:
    logger.error(f"Ошибка отправки проактивного сообщения user {user_id}: {e}", exc_info=True)
finally:
    try:
        await bot.session.close()
        logger.debug(f"Bot session closed for user {user_id}")
    except Exception as close_error:
        logger.error(f"Error closing bot session: {close_error}")
```

---

### ✅ Bug #12: Move Payment Rate Limiting to Redis
**File:** [bot/handlers/payments.py:32-58](bot/handlers/payments.py#L32-L58)
**Estimated Time:** 1 hour
**Difficulty:** Medium
**Impact:** Rate limiting ineffective

**Tasks:**
- [ ] Remove global `payment_attempts` dict
- [ ] Implement Redis-based counter with INCR
- [ ] Use Redis EXPIRE for time window
- [ ] Make function async
- [ ] Update all call sites to await
- [ ] Test concurrent payment attempts
- [ ] Verify rate limit works after restart
- [ ] Add monitoring for rate limit hits

**Code to implement:**
```python
# Remove lines 32-33:
# payment_attempts = defaultdict(list)
# MAX_ATTEMPTS = 3

# Replace check_payment_rate_limit function:
async def check_payment_rate_limit(user_id: int) -> tuple[bool, int]:
    """
    Check payment rate limit using Redis.

    Returns:
        (is_allowed, current_attempts)
    """
    from config import REDIS_CLIENT

    if not REDIS_CLIENT:
        # Fallback if Redis unavailable
        return True, 0

    MAX_ATTEMPTS = 3
    TIME_WINDOW = 3600  # 1 hour

    key = f"payment_rate:{user_id}"

    try:
        # Atomic increment
        current = await REDIS_CLIENT.incr(key)

        if current == 1:
            # First attempt, set expiry
            await REDIS_CLIENT.expire(key, TIME_WINDOW)

        is_allowed = current <= MAX_ATTEMPTS
        return is_allowed, current

    except Exception as e:
        logger.error(f"Redis error in payment rate limit: {e}")
        # Fail open on Redis errors
        return True, 0

# Update all call sites from sync to async:
# BEFORE: is_allowed, attempts = check_payment_rate_limit(user_id)
# AFTER:  is_allowed, attempts = await check_payment_rate_limit(user_id)
```

---

### ✅ Bug #13: Validate Subscription Duration
**File:** [server/database.py:1031](server/database.py#L1031)
**Estimated Time:** 20 minutes
**Difficulty:** Easy
**Impact:** Invalid subscriptions can be created

**Tasks:**
- [ ] Add validation before line 1031
- [ ] Check duration_days is int
- [ ] Check duration_days range (1-3650)
- [ ] Raise ValueError on invalid input
- [ ] Update API endpoint to handle ValueError
- [ ] Test with negative values
- [ ] Test with huge values
- [ ] Add API documentation

**Code to implement:**
```python
# Before line 1031:
async def activate_premium_subscription(
    user_id: int,
    duration_days: int,
    payment_id: str | None = None
) -> bool:
    # Add validation
    if not isinstance(duration_days, int):
        raise ValueError(f"duration_days must be int, got {type(duration_days)}")

    if duration_days < 1 or duration_days > 3650:  # Max ~10 years
        raise ValueError(
            f"duration_days must be between 1 and 3650, got {duration_days}"
        )

    # Rest of function...
    expires_at = datetime.now(timezone.utc) + timedelta(days=duration_days)
```

---

## 🟡 MEDIUM PRIORITY - Week 3 (Quality Improvements)

### ✅ Bug #14: Make Redis Counter Operations Atomic
**File:** [server/scheduler.py:362-375](server/scheduler.py#L362-L375)
**Estimated Time:** 30 minutes
**Difficulty:** Easy

**Tasks:**
- [ ] Use Redis pipeline for atomic operations
- [ ] Combine INCR and EXPIRE in one pipeline
- [ ] Test key expiration works correctly
- [ ] Verify counter accuracy
- [ ] Add error handling for pipeline failures

**Code:**
```python
# Lines 362-375 - BEFORE:
await REDIS_CLIENT.incr(today_key)
await REDIS_CLIENT.expire(today_key, 48 * 3600)

# Lines 362-375 - AFTER:
pipe = REDIS_CLIENT.pipeline()
pipe.incr(today_key)
pipe.expire(today_key, 48 * 3600)
await pipe.execute()
```

---

### ✅ Bug #15: Fix Emotional Memory Intensity Type Coercion
**File:** [server/database.py:375-378](server/database.py#L375-L378)
**Estimated Time:** 20 minutes
**Difficulty:** Easy

**Tasks:**
- [ ] Improve type checking and conversion
- [ ] Handle float, string, invalid types
- [ ] Use default value on error
- [ ] Add logging for invalid inputs
- [ ] Test with various input types

**Code:**
```python
# Lines 375-378 - replace with:
try:
    intensity = int(intensity)
    intensity = max(1, min(10, intensity))
except (ValueError, TypeError):
    logging.warning(
        f"Invalid intensity '{intensity}' for user {user_id}, using default 5"
    )
    intensity = 5
```

---

### ✅ Bug #16: Add Default Timeout to API Client
**File:** [bot/services/api_client.py:99-104](bot/services/api_client.py#L99-L104)
**Estimated Time:** 15 minutes
**Difficulty:** Easy

**Tasks:**
- [ ] Add default timeout if not specified
- [ ] Set reasonable default (30s)
- [ ] Document timeout parameter
- [ ] Test with various timeout values

**Code:**
```python
# Around line 99-104:
async def make_api_request(..., **kwargs):
    # Add default timeout
    if 'timeout' not in kwargs:
        kwargs['timeout'] = 30.0

    response = await client.request(method, url, **kwargs)
    return response
```

---

### ✅ Bug #17: Add Model Name Validation
**File:** [config.py:44, 47](config.py#L44)
**Estimated Time:** 30 minutes
**Difficulty:** Medium

**Tasks:**
- [ ] Add model availability check at startup
- [ ] Provide clear error message if model unavailable
- [ ] Add fallback model list
- [ ] Document supported models
- [ ] Test with invalid model name

**Code:**
```python
# In config.py after GEMINI_CLIENT initialization:
try:
    # Verify model is available
    model_info = GEMINI_CLIENT.models.get(MODEL_NAME)
    logger.info(f"✅ Using AI model: {MODEL_NAME}")
except Exception as e:
    logger.error(f"❌ Model {MODEL_NAME} not available: {e}")
    logger.error("Available models: gemini-2.0-flash-exp, gemini-1.5-flash, gemini-1.5-pro")
    raise RuntimeError(f"AI model '{MODEL_NAME}' is unavailable. Check MODEL_NAME in .env")
```

---

### ✅ Bug #18: Improve Health Check
**File:** [main.py:303-310](main.py#L303-L310)
**Estimated Time:** 30 minutes
**Difficulty:** Easy

**Tasks:**
- [ ] Replace `get_profile(0)` with `SELECT 1`
- [ ] Add Redis ping check
- [ ] Check all critical dependencies
- [ ] Return detailed status
- [ ] Document health check endpoints

**Code:**
```python
@app.get("/ready", status_code=200)
async def readiness_check():
    """Check if all dependencies are ready."""
    try:
        # Check database
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))

        # Check Redis (optional)
        redis_status = "unavailable"
        if REDIS_CLIENT:
            try:
                await REDIS_CLIENT.ping()
                redis_status = "connected"
            except:
                redis_status = "disconnected"

        return {
            "status": "ready",
            "database": "connected",
            "redis": redis_status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service not ready: {str(e)}"
        )
```

---

### ✅ Bug #19: Add Logging for Content Sanitization
**File:** [server/database.py:605](server/database.py#L605)
**Estimated Time:** 10 minutes
**Difficulty:** Easy

**Tasks:**
- [ ] Log when content is modified by bleach
- [ ] Include character count change
- [ ] Use DEBUG level to avoid spam
- [ ] Test with HTML content

**Code:**
```python
# Around line 605:
sanitized_content = bleach.clean(content, tags=[], strip=True)
if sanitized_content != content:
    logger.debug(
        f"Content sanitized for user {user_id}: "
        f"{len(content)} -> {len(sanitized_content)} chars"
    )
```

---

### ✅ Bug #20: Add Division by Zero Guards in Analytics
**File:** [server/analytics.py](server/analytics.py)
**Estimated Time:** 1 hour
**Difficulty:** Easy

**Tasks:**
- [ ] Review all division operations
- [ ] Add zero checks before division
- [ ] Add time calculation sanity checks
- [ ] Test with edge cases (empty data)
- [ ] Document safe defaults

---

### ✅ Bug #21: Improve Background Task Error Handling
**File:** [server/ai.py:192-193](server/ai.py#L192-L193)
**Estimated Time:** 20 minutes
**Difficulty:** Easy

**Tasks:**
- [ ] Wrap task creation in try-catch
- [ ] Log creation failures
- [ ] Handle task cancellation properly
- [ ] Test with failing tasks

**Code:**
```python
# Around line 192-193:
try:
    task = asyncio.create_task(generate_summary_and_analyze(self.user_id))
    task.add_done_callback(lambda t: _handle_background_task_error(t, self.user_id))
except Exception as e:
    logger.error(f"Failed to create summarization task for user {self.user_id}: {e}")
```

---

### ✅ Bug #22: Add Image Format Validation
**File:** [bot/services/image_processor.py:72-81](bot/services/image_processor.py#L72-81)
**Estimated Time:** 30 minutes
**Difficulty:** Easy

**Tasks:**
- [ ] Validate image format before processing
- [ ] Add explicit error handling for PIL operations
- [ ] Check for corrupted images
- [ ] Test with malformed files
- [ ] Add user-friendly error messages

---

### ✅ Bug #23: Handle Empty Chat History
**File:** [server/database.py:290](server/database.py#L290)
**Estimated Time:** 15 minutes
**Difficulty:** Easy

**Tasks:**
- [ ] Check if history is empty before sending to AI
- [ ] Add minimum message requirement
- [ ] Provide default response for empty history
- [ ] Log when history is empty

---

### ✅ Bug #24: Add Message Counter Overflow Protection
**File:** [server/database.py:615-620](server/database.py#L615-L620)
**Estimated Time:** 20 minutes
**Difficulty:** Easy

**Tasks:**
- [ ] Add max value check for daily_message_count
- [ ] Reset on overflow
- [ ] Log unusual counter values
- [ ] Document counter limits

---

## 📊 Progress Tracking

### Week 1 Status: 0/5 Complete
- [ ] Bug #1: TTS Return Type
- [ ] Bug #2: Missing await
- [ ] Bug #3: DateTime timezone
- [ ] Bug #4: JSON error handling
- [ ] Bug #5: Subscription race condition

### Week 2 Status: 0/8 Complete
- [ ] Bug #6: SQL injection risk
- [ ] Bug #7: Circuit breaker
- [ ] Bug #8: Null check
- [ ] Bug #9: Cache invalidation
- [ ] Bug #10: Memory leak
- [ ] Bug #11: Connection leak
- [ ] Bug #12: Payment rate limiting
- [ ] Bug #13: Duration validation

### Week 3 Status: 0/11+ Complete
- [ ] Bug #14: Redis atomic ops
- [ ] Bug #15: Type coercion
- [ ] Bug #16: API timeout
- [ ] Bug #17: Model validation
- [ ] Bug #18: Health check
- [ ] Bug #19: Sanitization logging
- [ ] Bug #20: Division guards
- [ ] Bug #21: Background tasks
- [ ] Bug #22: Image validation
- [ ] Bug #23: Empty history
- [ ] Bug #24: Counter overflow

---

## 🧪 Testing Checklist

After each bug fix, verify:
- [ ] Unit tests pass (if exist)
- [ ] Integration tests pass (if exist)
- [ ] Manual testing completed
- [ ] No new errors in logs
- [ ] Performance not degraded
- [ ] Documentation updated

---

## 📝 Notes for Next Session

**Quick Wins (< 30 min):**
1. Bug #2: Missing await (5 min)
2. Bug #8: Null check (15 min)
3. Bug #16: API timeout (15 min)
4. Bug #19: Logging (10 min)

**Start with these for quick progress!**

**Most Important:**
- Bug #2 (proactive messages broken)
- Bug #5 (subscription race condition)
- Bug #10 (memory leak under load)

**Can Wait:**
- Bugs #20-24 (edge cases, unlikely to occur)

---

## 📈 Expected Outcomes

**After Week 1 (CRITICAL fixes):**
- ✅ Voice messages work correctly
- ✅ Proactive messages functional
- ✅ No timezone issues
- ✅ Bot handles API errors gracefully
- ✅ Subscriptions work correctly under load

**Stability Score:** 6.5/10 → 8.0/10

**After Week 2 (HIGH priority fixes):**
- ✅ No memory/connection leaks
- ✅ Security vulnerabilities patched
- ✅ Redis recovery works
- ✅ Payment system reliable

**Stability Score:** 8.0/10 → 8.7/10

**After Week 3 (MEDIUM priority fixes):**
- ✅ All edge cases handled
- ✅ Robust error handling everywhere
- ✅ Production-ready quality

**Stability Score:** 8.7/10 → 9.2/10

---

## 🚀 Ready to Start?

1. Open this file in next session
2. Start with Bug #2 (5 minutes, high impact)
3. Mark completed items with `[x]`
4. Move to next bug
5. Test after each fix
6. Commit after each completed bug

**Good luck! 💪**

---

**Last Updated:** 2025-10-26
**Next Review:** After Week 1 completion
