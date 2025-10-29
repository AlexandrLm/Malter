# API Architecture Overview

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL SERVICES                             │
├─────────────────────────────────────────────────────────────────────┤
│  • Telegram Bot API      • Google Gemini API      • Payment Systems  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                 ┌─────────────▼──────────────┐
                 │   TELEGRAM BOT SERVICE     │
                 │   (aiogram, polling mode)  │
                 └─────────────┬──────────────┘
                               │ HTTP/REST with JWT
                 ┌─────────────▼──────────────────────────┐
                 │     FastAPI REST API (main.py)         │
                 │     Port: 8000 (Gunicorn 4 workers)    │
                 │                                         │
    ┌────────────┼────────────┬──────────────┬───────────┬─────────┐
    │            │            │              │           │         │
    ▼            ▼            ▼              ▼           ▼         ▼
  ┌──────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  ┌──────────┐ ┌────┐
  │Health│  │  Auth    │  │  Chat    │  │Profile │  │ Premium  │ │Admin│
  │ Probe│  │   JWT    │  │ Message  │  │ & User │  │ & Sub    │ │Ops │
  └──────┘  └──────────┘  └──────────┘  └────────┘  └──────────┘ └────┘
                                                                       │
                                                          ┌────────────┴─────────┐
                                                          ▼                      ▼
                                                    ┌───────────────────────┐  ┌──────────┐
                                                    │    Analytics (8 EP)   │  │ Internal │
                                                    └───────────────────────┘  └──────────┘
                 ┌──────────────────────────────────────────────────────┐
                 │              HELPER LAYER                            │
    ┌────────────┴────────────────────────────────────────────┬────────┘
    │                                                         │
    ▼                                                         ▼
┌─────────────────┐                              ┌──────────────────────┐
│  api_helpers.py │                              │ api_schemas.py       │
│                 │                              │                      │
│ • JWT creation  │                              │ • Pydantic models    │
│ • Verification  │                              │ • Request validation │
│ • TTS handling  │                              │ • Response schemas   │
│ • Rate limiting │                              │ • Auto OpenAPI docs  │
└────────┬────────┘                              └──────────────────────┘
         │
         │ Authorization & Validation
         ▼
    ┌────────────────────────────────────┐
    │   Database Layer (database.py)     │
    │                                    │
    │ • CRUD operations                 │
    │ • Transaction management          │
    │ • Connection pooling (asyncpg)    │
    │ • Circuit breaker for Redis       │
    └──────────────┬─────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌────────┐    ┌────────┐    ┌─────────┐
│PostgreS│    │Redis   │    │ Circuit │
│  QL    │    │ Cache  │    │ Breaker │
│ 15.7   │    │  7.2   │    │ (Gemini)│
└────────┘    └────────┘    └─────────┘
    │              │
    │ Stores:      │ Caches:
    │ • Users      │ • Profiles
    │ • Chat       │ • Sessions
    │ • Memory     │ • Tokens
    │ • Summary    │ • State
    └──────────────┘
```

---

## 📂 File Organization

```
Malter/
│
├── main.py                          ← Application entry point (122 lines)
│
├── server/
│   ├── __init__.py
│   ├── routes/                      ← API route modules
│   │   ├── __init__.py             ← Route registration
│   │   ├── health.py               ← /health, /ready
│   │   ├── auth.py                 ← /auth
│   │   ├── chat.py                 ← /chat, /chat_history
│   │   ├── profile.py              ← /profile/*
│   │   ├── premium.py              ← /activate_premium
│   │   ├── admin.py                ← /admin/*
│   │   └── analytics.py            ← /admin/analytics/*
│   │
│   ├── api_schemas.py              ← Pydantic models (15+ classes)
│   ├── api_helpers.py              ← JWT, TTS, helpers
│   │
│   ├── database.py                 ← Database access layer
│   ├── models.py                   ← SQLAlchemy ORM models
│   ├── schemas.py                  ← Old schemas (for compatibility)
│   ├── ai.py                       ← Gemini AI integration
│   ├── tts.py                      ← Text-to-speech
│   ├── scheduler.py                ← Background jobs (APScheduler)
│   ├── analytics.py                ← Analytics queries
│   ├── subscription_service.py     ← Premium subscription logic
│   ├── relationship_logic.py       ← Relationship system (14 levels)
│   ├── summarizer.py               ← Chat summarization
│   └── [other modules...]
│
├── bot/
│   ├── __main__.py                 ← Bot entry point
│   ├── bot.py                      ← Aiogram Bot setup
│   ├── handlers/
│   │   ├── commands.py
│   │   ├── messages.py
│   │   ├── payments.py
│   │   ├── profile.py
│   │   └── keyboards.py
│   ├── services/
│   │   ├── api_client.py
│   │   ├── image_processor.py
│   │   ├── geolocation_service.py
│   │   └── response_handler.py
│   └── utils/
│       ├── typing_simulator.py
│       └── validators.py
│
├── utils/
│   ├── cache.py                    ← Redis caching
│   ├── circuit_breaker.py          ← Failure handling
│   ├── encryption.py               ← Fernet encryption
│   ├── db_monitoring.py            ← Slow query tracking
│   └── retry_configs.py            ← Tenacity config
│
├── alembic/                        ← Database migrations
│   ├── env.py
│   ├── script.py.mako
│   ├── alembic.ini
│   └── versions/                   ← 16 migration files
│
├── config.py                       ← Environment configuration
├── prompts.py                      ← AI prompts
├── personality_prompts.py          ← Per-level personality
├── broadcast.py                    ← Broadcast messages
│
├── docker-compose.yml              ← Local development
├── Dockerfile                      ← API image
├── Dockerfile.migration            ← Migration runner
├── requirements.txt                ← Dependencies (102 packages)
│
├── README.md                       ← Main documentation
├── REFACTORING_NOTES.md            ← This refactoring (you are here)
├── ARCHITECTURE.md                 ← Architecture diagrams (this file)
├── PROJECT_ANALYSIS_AND_IMPROVEMENT_PLAN.md
│
└── docs/                           ← Additional documentation
    ├── ANALYTICS_GUIDE.md
    ├── BACKUP_STRATEGY.md
    ├── EMOTIONAL_MEMORY.md
    └── [other docs...]
```

---

## 🔀 Request Flow Diagram

### Chat Message Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Telegram User sends message                                  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │   Telegram Bot (aiogram)    │
         │  - Validate input           │
         │  - Extract metadata         │
         └─────────────┬───────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │   Call /api/v1/auth         │
         │  - Generate JWT token       │
         └─────────────┬───────────────┘
                       │
                       ▼
         ┌─────────────────────────────────────┐
         │   POST /api/v1/chat (JWT)           │
         │ - Message                           │
         │ - Timestamp                         │
         │ - Optional image                    │
         └─────────────┬───────────────────────┘
                       │
         ┌─────────────▼──────────────┐
         │  routes/chat.py            │
         │ ✓ verify_token()           │
         │ ✓ check_message_limits()   │
         └─────────────┬──────────────┘
                       │
         ┌─────────────▼──────────────────┐
         │  server/ai.py                  │
         │ - get_profile()                │
         │ - get_chat_history()           │
         │ - search_long_term_memory()    │
         │ - build_system_prompt()        │
         │ - call_gemini_with_context()   │
         │ - save_chat_message()          │
         └─────────────┬──────────────────┘
                       │
         ┌─────────────▼──────────────────┐
         │  Check for [VOICE] marker      │
         │  & TTS generation              │
         │  (if premium user)             │
         └─────────────┬──────────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │  ChatResponse               │
         │ - response_text             │
         │ - voice_message (if premium)│
         │ - image_base64 (if present) │
         └─────────────┬───────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │   Telegram Bot              │
         │ - Display text              │
         │ - Play voice (if present)   │
         │ - Send image (if present)   │
         └─────────────────────────────┘
```

---

## 🔐 Security Layers

```
┌──────────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                            │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Layer 1: TRANSPORT                                          │
│  ├─ HTTPS/TLS (in production with reverse proxy)            │
│  ├─ Firewall rules                                          │
│  └─ VPC isolation                                           │
│                                                               │
│  Layer 2: AUTHENTICATION                                    │
│  ├─ JWT tokens (HS256 algorithm)                            │
│  ├─ Token expiration (1 hour)                               │
│  ├─ Secret key validation (32+ chars, high entropy)         │
│  └─ Bearer token in Authorization header                    │
│                                                               │
│  Layer 3: AUTHORIZATION                                     │
│  ├─ verify_token() dependency for all protected routes      │
│  ├─ verify_admin() for admin-only routes                    │
│  ├─ User ownership checks (can't access other user data)    │
│  └─ Role-based access control (RBAC)                        │
│                                                               │
│  Layer 4: VALIDATION                                        │
│  ├─ Pydantic models for request validation                  │
│  ├─ Field type checking                                     │
│  ├─ Size limits (max_length)                                │
│  ├─ Range validation (gt=0, ge=1, le=365)                   │
│  └─ XSS protection with bleach sanitization                 │
│                                                               │
│  Layer 5: DATA PROTECTION                                   │
│  ├─ Fernet encryption for sensitive fields (user.name)      │
│  ├─ ENCRYPTION_KEY validation                               │
│  ├─ No plaintext secrets in logs                            │
│  └─ SQL injection protection (ORM + parameterized queries)  │
│                                                               │
│  Layer 6: RATE LIMITING                                     │
│  ├─ IP-based rate limiting (SlowAPI)                        │
│  ├─ Endpoint-specific limits                                │
│  ├─ /auth: 10/minute                                        │
│  ├─ /chat: 10/minute                                        │
│  ├─ /admin/*: 1-10/minute (strict)                          │
│  └─ /admin/cleanup_chat_history: 1/hour                     │
│                                                               │
│  Layer 7: MONITORING                                        │
│  ├─ Request logging with timestamps                         │
│  ├─ Error logging with stack traces                         │
│  ├─ Prometheus metrics                                      │
│  ├─ Database query monitoring (slow queries >1s)            │
│  └─ Circuit breaker monitoring (Gemini, Redis)              │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 📊 Data Flow for Each Endpoint Type

### 1. PUBLIC ENDPOINTS (No auth)

```
Request → validate_input → process → response
  /health         (0ms - instant)
  /ready          (1-5s - checks dependencies)
  /                (instant)
```

### 2. AUTHENTICATED ENDPOINTS (JWT required)

```
Request → verify_token → validate_input → business_logic → response
  /api/v1/chat
  /api/v1/profile/*
  /api/v1/activate_premium
```

**verify_token() flow:**
```
Authorization: Bearer <JWT>
    ↓
Extract token from header
    ↓
Decode with SECRET_KEY (HS256)
    ↓
Check expiration (exp claim)
    ↓
Return user_id
    ↓
401 Unauthorized if invalid
```

### 3. ADMIN ENDPOINTS (Admin JWT required)

```
Request → verify_token → verify_admin → validate_input → business_logic → response
  /api/v1/admin/*
  /api/v1/admin/analytics/*
```

**verify_admin() flow:**
```
1. Call verify_token() ← Get user_id
    ↓
2. Check if user_id in ADMIN_USER_IDS
    ↓
403 Forbidden if not admin
    ↓
Proceed if authorized
```

---

## 🔄 Route Registration

### How Routes Are Set Up

```
main.py
  │
  └─ setup_routes(app)  ← server/routes/__init__.py
      │
      ├─ include_router(health_router)
      │   └─ routes/health.py (GET /, /health, /ready)
      │
      ├─ include_router(auth_router)
      │   └─ routes/auth.py (POST /api/v1/auth)
      │
      ├─ include_router(chat_router)
      │   └─ routes/chat.py (POST /api/v1/chat, GET /api/v1/chat_history)
      │
      ├─ include_router(profile_router)
      │   └─ routes/profile.py (GET/POST/DELETE /api/v1/profile)
      │
      ├─ include_router(premium_router)
      │   └─ routes/premium.py (POST /api/v1/activate_premium)
      │
      ├─ include_router(admin_router)
      │   └─ routes/admin.py (GET/POST /api/v1/admin/*)
      │
      └─ include_router(analytics_router)
          └─ routes/analytics.py (GET /api/v1/admin/analytics/*)
```

---

## 🧩 Dependency Injection

### FastAPI Dependencies

```
Depends(verify_token)
    ↓
verify_token(credentials: HTTPAuthorizationCredentials)
    ├─ Extract Bearer token
    ├─ Decode JWT
    ├─ Verify signature
    ├─ Check expiration
    └─ Return user_id (or raise 401)

Depends(verify_admin)
    ↓
verify_admin(user_id: int = Depends(verify_token))
    ├─ First verify user is authenticated
    ├─ Check ADMIN_USER_IDS
    └─ Return user_id (or raise 403)
```

### Usage in Routes

```python
@router.post("/chat")
async def chat_handler(
    request: Request,                    # Rate limiting
    chat: ChatRequest,                   # Request body validation
    user_id: int = Depends(verify_token) # JWT verification
):
    # user_id is guaranteed valid here
```

---

## 💾 Database Schema Overview

```
┌─────────────────────────────────────────────────────────┐
│ PostgreSQL Database (malterdb)                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  user_profiles                                         │
│  ├─ id (PK)                                            │
│  ├─ user_id (BIGINT, UNIQUE)     ← Telegram user ID   │
│  ├─ name (ENCRYPTED)              ← Fernet encrypted   │
│  ├─ gender, timezone                                  │
│  ├─ relationship_level (1-14)    ← 14-level system   │
│  ├─ relationship_score            ← Points            │
│  ├─ subscription_plan             ← free/premium      │
│  ├─ subscription_expires          ← Expiry date       │
│  ├─ daily_message_count           ← Today's messages  │
│  └─ last_processed_payment_charge_id                  │
│                                                         │
│  chat_history                                         │
│  ├─ id (PK)                                           │
│  ├─ user_id (FK → user_profiles)                      │
│  ├─ role (user/assistant)         ← Message role      │
│  ├─ content (TEXT)                ← Message text      │
│  ├─ timestamp (DateTime TZ)                           │
│  ├─ has_image, image_base64 (optional)               │
│  └─ INDEX: (user_id, timestamp) ← Fast lookups       │
│                                                         │
│  long_term_memory                                     │
│  ├─ id (PK)                                           │
│  ├─ user_id (FK → user_profiles)                      │
│  ├─ fact (TEXT)                   ← Stored fact       │
│  ├─ category (TEXT)               ← Classification   │
│  ├─ intensity (1-10)              ← Importance        │
│  ├─ created_at (DateTime)                            │
│  ├─ search_vector (TSVECTOR)     ← For full-text    │
│  └─ INDEX: (user_id)                                 │
│                                                         │
│  long_term_memory_emotions                            │
│  ├─ id (PK)                                           │
│  ├─ fact_id (FK → long_term_memory)                   │
│  ├─ emotion (joy, sadness, anger, etc.)               │
│  └─ intensity (1-10)                                  │
│                                                         │
│  chat_summaries                                       │
│  ├─ id (PK)                                           │
│  ├─ user_id (FK → user_profiles)                      │
│  ├─ summary_text (TEXT)           ← Summarized text   │
│  ├─ messages_summarized (INT)                         │
│  └─ created_at (DateTime)                             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🔌 External Integrations

```
┌──────────────────────────────────────────────────────────┐
│           EXTERNAL SERVICE INTEGRATIONS                  │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Google Gemini API (google-genai SDK)                  │
│  ├─ Chat generation (text)                             │
│  ├─ Vision analysis (image understanding)              │
│  ├─ Text-to-speech (TTS voice generation)              │
│  ├─ Circuit breaker: 5 failures → 60s timeout          │
│  └─ Used in: server/ai.py, server/tts.py              │
│                                                          │
│  Telegram Bot API (aiogram)                            │
│  ├─ Message polling                                    │
│  ├─ User commands (/start, /help, /profile)           │
│  ├─ Payment pre-checkout and confirmation              │
│  └─ Used in: bot/bot.py, bot/handlers/*               │
│                                                          │
│  Payment Providers (Stripe, YooMoney, etc.)            │
│  ├─ Premium subscription payments                      │
│  ├─ Charge ID validation (prevent duplicates)          │
│  └─ Used in: bot/handlers/payments.py                  │
│                                                          │
│  IP Geolocation API (for TTS timezone)                │
│  ├─ Determine user timezone from IP                    │
│  ├─ Used for TTS voice locale selection                │
│  └─ Used in: bot/services/geolocation_service.py       │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 🎯 API Versioning Strategy

```
Current: /api/v1/*

Future upgrade to v2 would be:
  /api/v2/chat
  /api/v2/profile/*
  /api/v2/admin/*

Benefits:
  ✓ Backward compatibility (v1 can coexist)
  ✓ Easy client migration
  ✓ Clear deprecation path
  ✓ Separate documentation per version

Implementation:
  server/routes_v2/
  ├── __init__.py
  ├── chat.py
  ├── profile.py
  └── ...

Then in main.py:
  setup_routes_v1(app)
  setup_routes_v2(app)
```

---

## 📈 Scalability Path

```
Stage 1: CURRENT (< 10k users)
├─ Single FastAPI instance
├─ PostgreSQL 1 instance
├─ Redis 1 instance
└─ Works with Docker Compose

       ↓ Growth

Stage 2: MEDIUM (10k - 100k users)
├─ 4+ Gunicorn workers (FastAPI)
├─ PostgreSQL master + read replicas
├─ Redis cluster
└─ Load balancer (nginx)

       ↓ Growth

Stage 3: LARGE (> 100k users)
├─ Kubernetes cluster (5+ replicas)
├─ PostgreSQL managed service (AWS RDS, Google Cloud)
├─ Redis managed service (AWS ElastiCache)
├─ Message queue (RabbitMQ, Kafka)
├─ Distributed tracing (Jaeger)
└─ CDN for static files
```

---

## 🔧 Troubleshooting

### Import Errors?
Check `server/routes/__init__.py` - all routers must be imported and registered

### Route Not Found?
Check API version in URL: `/api/v1/endpoint` (not just `/endpoint`)

### Auth Failing?
1. Verify JWT_SECRET is set (32+ chars)
2. Check token expiration (1 hour)
3. Ensure Authorization header format: `Bearer <token>`

### Database Errors?
1. Check PostgreSQL is running
2. Verify DATABASE_URL in config.py
3. Run migrations: `alembic upgrade head`

### Prometheus Metrics Not Found?
Check `/metrics` endpoint - should return Prometheus format

---

This architecture is designed for **production readiness, scalability, and maintainability**.
