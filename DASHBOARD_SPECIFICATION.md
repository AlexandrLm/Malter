# 📊 Dashboard Specification - EvolveAI Analytics

> Техническая спецификация для разработки web-дашборда аналитики EvolveAI

---

## 📋 Содержание

- [Обзор проекта](#-обзор-проекта)
- [Технические требования](#-технические-требования)
- [Архитектура](#-архитектура)
- [API Endpoints](#-api-endpoints)
- [Структура данных](#-структура-данных)
- [UI/UX Компоненты](#-uiux-компоненты)
- [Аутентификация](#-аутентификация)
- [Примеры использования API](#-примеры-использования-api)
- [Deployment](#-deployment)

---

## 🎯 Обзор проекта

### Назначение:
Web-дашборд для визуализации и анализа метрик Telegram бота EvolveAI.

### Целевая аудитория:
- Администраторы проекта
- Product менеджеры
- Data аналитики
- DevOps инженеры

### Ключевые функции:
1. **Real-time метрики** - DAU, MAU, active sessions
2. **User analytics** - распределение по уровням, подпискам, географии
3. **Revenue tracking** - MRR, ARR, churn rate, LTV
4. **Performance monitoring** - API latency, DB queries, error rates
5. **Funnel analysis** - конверсия между уровнями отношений
6. **Cohort analysis** - retention по когортам
7. **Feature usage** - использование AI функций, TTS, памяти

---

## 🛠 Технические требования

### Рекомендуемый стек:

#### Frontend:
```javascript
// Core
React 18+ или Next.js 14+
TypeScript 5+

// UI Libraries
- Material-UI (MUI) 5+ или Ant Design 5+
- TailwindCSS 3+ (опционально)

// Charts & Visualization
- Recharts 2.x (рекомендуется)
- Chart.js 4.x (альтернатива)
- D3.js 7.x (для сложных визуализаций)

// Data Fetching
- React Query (TanStack Query) 5+
- Axios 1.x
- SWR (альтернатива React Query)

// State Management
- Zustand (легковесный)
- Redux Toolkit (для сложных случаев)
- Context API (для простых случаев)

// Routing
- React Router 6+
- Next.js App Router (если Next.js)

// Date Handling
- date-fns 3+ или Day.js 1.x

// Tables
- TanStack Table 8+
- AG-Grid (для больших датасетов)
```

#### Backend Integration:
```
- Base URL: http://api:8000 (production: https://api.yourdomain.com)
- Authentication: JWT Bearer Token
- Content-Type: application/json
- Rate Limiting: учитывать лимиты (10-20 req/min)
```

#### Дополнительно:
```javascript
// Real-time updates (опционально)
- Socket.io
- Server-Sent Events (SSE)

// Export/PDF
- jsPDF
- html2canvas

// Internationalization (если нужно)
- react-i18next
```

---

## 🏗 Архитектура

### Структура проекта:

```
dashboard/
├── src/
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   └── Layout.tsx
│   │   ├── charts/
│   │   │   ├── OverviewChart.tsx
│   │   │   ├── RevenueChart.tsx
│   │   │   ├── FunnelChart.tsx
│   │   │   ├── CohortTable.tsx
│   │   │   └── ActivityHeatmap.tsx
│   │   ├── cards/
│   │   │   ├── MetricCard.tsx
│   │   │   ├── StatCard.tsx
│   │   │   └── TrendCard.tsx
│   │   └── common/
│   │       ├── DateRangePicker.tsx
│   │       ├── LoadingSpinner.tsx
│   │       └── ErrorBoundary.tsx
│   ├── pages/
│   │   ├── Dashboard.tsx          # Главная страница
│   │   ├── Users.tsx               # Аналитика пользователей
│   │   ├── Revenue.tsx             # Revenue метрики
│   │   ├── Messages.tsx            # Аналитика сообщений
│   │   ├── Features.tsx            # Использование функций
│   │   ├── Cohorts.tsx             # Когортный анализ
│   │   ├── Funnel.tsx              # Воронка конверсии
│   │   ├── Performance.tsx         # Технические метрики
│   │   └── Login.tsx               # Страница входа
│   ├── services/
│   │   ├── api.ts                  # API client
│   │   ├── auth.ts                 # Authentication
│   │   └── websocket.ts            # WebSocket (если нужно)
│   ├── hooks/
│   │   ├── useAnalytics.ts         # Custom hooks для API
│   │   ├── useAuth.ts
│   │   └── useWebSocket.ts
│   ├── types/
│   │   ├── analytics.ts            # TypeScript типы
│   │   ├── api.ts
│   │   └── user.ts
│   ├── utils/
│   │   ├── formatters.ts           # Форматирование данных
│   │   ├── validators.ts
│   │   └── constants.ts
│   ├── store/                      # State management
│   │   ├── authSlice.ts
│   │   └── settingsSlice.ts
│   ├── App.tsx
│   └── main.tsx
├── public/
├── package.json
├── tsconfig.json
└── vite.config.ts (или next.config.js)
```

### Навигация дашборда:

```
Dashboard Layout:
├── 📊 Overview (главная)
├── 👥 Users
│   ├── Demographics
│   ├── Relationship Levels
│   └── Activity Patterns
├── 💰 Revenue
│   ├── Subscriptions
│   ├── Churn Analysis
│   └── LTV Calculator
├── 💬 Messages
│   ├── Volume Trends
│   ├── Peak Hours
│   └── Response Times
├── 🔧 Features
│   ├── AI Tools Usage
│   ├── TTS Statistics
│   └── Memory Facts
├── 📈 Analytics
│   ├── Cohort Analysis
│   ├── Funnel Analysis
│   └── Retention
└── ⚙️ Performance
    ├── API Metrics
    ├── DB Performance
    └── Error Tracking
```

---

## 📡 API Endpoints

### Base Configuration:

```typescript
// services/api.ts
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor для добавления JWT токена
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Interceptor для обработки ошибок
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Redirect to login
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
```

### 1. Authentication:

#### POST `/auth`
**Описание:** Получение JWT токена для доступа к API

**Request:**
```typescript
interface AuthRequest {
  user_id: number;
}

const response = await apiClient.post('/auth', {
  user_id: 123456789
});
```

**Response:**
```typescript
interface AuthResponse {
  access_token: string;
  token_type: string;
}

// Example:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Использование:**
```typescript
// Сохранение токена
localStorage.setItem('authToken', response.data.access_token);

// Token expires in 60 minutes (настраивается в config.py)
// Рекомендуется реализовать refresh механизм
```

---

### 2. Health Checks:

#### GET `/health`
**Описание:** Проверка работоспособности API (liveness probe)

**Response:**
```typescript
interface HealthResponse {
  status: string;
}

// Example:
{
  "status": "ok"
}
```

#### GET `/ready`
**Описание:** Полная проверка готовности всех сервисов (readiness probe)

**Response:**
```typescript
interface ReadyResponse {
  database: {
    status: string;
    message: string;
  };
  redis: {
    status: string;
    message: string;
    circuit_breaker?: {
      state: string;
      failure_count: number;
    };
  };
  gemini: {
    status: string;
    message: string;
    circuit_breaker?: {
      state: string;
      failure_count: number;
      total_calls: number;
      total_blocked: number;
      success_rate: number;
    };
  };
  overall: string;
}

// Example:
{
  "database": {
    "status": "healthy",
    "message": "Connected"
  },
  "redis": {
    "status": "healthy",
    "message": "Connected, Circuit Breaker: CLOSED",
    "circuit_breaker": {
      "state": "CLOSED",
      "failure_count": 0
    }
  },
  "gemini": {
    "status": "healthy",
    "message": "Client initialized, Circuit Breaker: CLOSED",
    "circuit_breaker": {
      "state": "CLOSED",
      "failure_count": 0,
      "total_calls": 1543,
      "total_blocked": 2,
      "success_rate": 99.87
    }
  },
  "overall": "healthy"
}
```

**Использование:**
```typescript
// Для индикатора статуса сервисов в хедере дашборда
const { data } = await apiClient.get('/ready');
const isHealthy = data.overall === 'healthy';
```

---

### 3. Analytics Endpoints:

#### GET `/admin/analytics/overview`
**Описание:** Общая статистика использования

**Rate Limit:** 10 req/min

**Response:**
```typescript
interface OverviewStats {
  users: {
    total: number;
    active_today: number;  // DAU
    active_month: number;  // MAU
    premium: number;
    new_today: number;
    new_week: number;
    new_month: number;
  };
  messages: {
    total: number;
    today: number;
    week: number;
    month: number;
    avg_per_user: number;
  };
  engagement: {
    dau_mau_ratio: number;  // DAU/MAU ratio (%)
    avg_session_length: number;  // в минутах
    avg_messages_per_session: number;
  };
  revenue: {
    mrr: number;  // Monthly Recurring Revenue
    arr: number;  // Annual Recurring Revenue
    active_subscriptions: number;
  };
}

// Example:
{
  "users": {
    "total": 15234,
    "active_today": 1543,
    "active_month": 8765,
    "premium": 456,
    "new_today": 87,
    "new_week": 543,
    "new_month": 2341
  },
  "messages": {
    "total": 345678,
    "today": 4321,
    "week": 32145,
    "month": 123456,
    "avg_per_user": 22.7
  },
  "engagement": {
    "dau_mau_ratio": 17.6,
    "avg_session_length": 8.5,
    "avg_messages_per_session": 6.3
  },
  "revenue": {
    "mrr": 45600.00,
    "arr": 547200.00,
    "active_subscriptions": 456
  }
}
```

**Визуализация:**
- Metric Cards с числами и трендами (↑↓)
- Line chart для DAU/MAU тренда
- Gauge chart для DAU/MAU ratio

---

#### GET `/admin/analytics/users`
**Описание:** Детальная статистика пользователей

**Rate Limit:** 10 req/min

**Response:**
```typescript
interface UsersStats {
  by_relationship_level: Array<{
    level: string;
    count: number;
    percentage: number;
  }>;
  by_subscription: {
    free: number;
    premium: number;
    trial: number;
  };
  top_active: Array<{
    user_id: number;
    name: string;
    message_count: number;
    relationship_level: string;
    last_active: string;
  }>;
  new_users: Array<{
    user_id: number;
    name: string;
    created_at: string;
    message_count: number;
  }>;
}

// Example:
{
  "by_relationship_level": [
    { "level": "Незнакомец", "count": 8543, "percentage": 56.1 },
    { "level": "Знакомый", "count": 4321, "percentage": 28.4 },
    { "level": "Друг", "count": 1876, "percentage": 12.3 },
    { "level": "Близкий друг", "count": 432, "percentage": 2.8 },
    { "level": "Intimate", "count": 62, "percentage": 0.4 }
  ],
  "by_subscription": {
    "free": 14778,
    "premium": 456,
    "trial": 0
  },
  "top_active": [
    {
      "user_id": 123456,
      "name": "Иван",
      "message_count": 543,
      "relationship_level": "Близкий друг",
      "last_active": "2025-10-05T12:34:56Z"
    }
    // ... еще 9 пользователей
  ],
  "new_users": [
    {
      "user_id": 234567,
      "name": "Мария",
      "created_at": "2025-10-05T10:00:00Z",
      "message_count": 12
    }
    // ... еще пользователи
  ]
}
```

**Визуализация:**
- Pie chart для распределения по уровням
- Bar chart для подписок (free/premium)
- Table для топ активных пользователей
- Timeline для новых пользователей

---

#### GET `/admin/analytics/messages?days=7`
**Описание:** Статистика сообщений за период

**Query Parameters:**
- `days` (integer, default: 7) - количество дней для анализа

**Rate Limit:** 10 req/min

**Response:**
```typescript
interface MessagesStats {
  by_day: Array<{
    date: string;
    user_messages: number;
    model_messages: number;
    total: number;
  }>;
  by_hour: Array<{
    hour: number;
    count: number;
    avg_response_time: number;  // в секундах
  }>;
  message_types: {
    text: number;
    voice: number;
    image: number;
  };
  avg_length: {
    user: number;  // средняя длина сообщения пользователя (символы)
    model: number;
  };
  response_times: {
    avg: number;  // в секундах
    p50: number;
    p95: number;
    p99: number;
  };
}

// Example:
{
  "by_day": [
    {
      "date": "2025-10-01",
      "user_messages": 1234,
      "model_messages": 1234,
      "total": 2468
    },
    // ... остальные дни
  ],
  "by_hour": [
    { "hour": 0, "count": 45, "avg_response_time": 2.3 },
    { "hour": 1, "count": 23, "avg_response_time": 1.9 },
    // ... 24 часа
  ],
  "message_types": {
    "text": 8765,
    "voice": 234,
    "image": 123
  },
  "avg_length": {
    "user": 67,
    "model": 234
  },
  "response_times": {
    "avg": 2.4,
    "p50": 1.8,
    "p95": 5.6,
    "p99": 12.3
  }
}
```

**Визуализация:**
- Line chart для трендов по дням
- Heatmap для активности по часам
- Donut chart для типов сообщений
- Bar chart для response times (percentiles)

---

#### GET `/admin/analytics/revenue`
**Описание:** Статистика доходов и подписок

**Rate Limit:** 10 req/min

**Response:**
```typescript
interface RevenueStats {
  subscriptions: {
    active: number;
    new_month: number;
    expiring_week: number;
    expiring_month: number;
  };
  revenue: {
    mrr: number;  // Monthly Recurring Revenue
    arr: number;  // Annual Recurring Revenue
    total_lifetime: number;
  };
  churn: {
    rate: number;  // процент оттока
    count_month: number;
  };
  ltv: {
    avg: number;  // Lifetime Value
    median: number;
  };
  by_duration: Array<{
    duration_days: number;
    count: number;
    revenue: number;
  }>;
  revenue_trend: Array<{
    date: string;
    revenue: number;
    new_subscriptions: number;
    churned: number;
  }>;
}

// Example:
{
  "subscriptions": {
    "active": 456,
    "new_month": 87,
    "expiring_week": 23,
    "expiring_month": 76
  },
  "revenue": {
    "mrr": 45600.00,
    "arr": 547200.00,
    "total_lifetime": 1234567.89
  },
  "churn": {
    "rate": 5.4,
    "count_month": 34
  },
  "ltv": {
    "avg": 2345.67,
    "median": 1890.00
  },
  "by_duration": [
    { "duration_days": 30, "count": 345, "revenue": 34500.00 },
    { "duration_days": 90, "count": 89, "revenue": 26700.00 },
    { "duration_days": 365, "count": 22, "revenue": 79200.00 }
  ],
  "revenue_trend": [
    {
      "date": "2025-10-01",
      "revenue": 45000.00,
      "new_subscriptions": 87,
      "churned": 34
    }
    // ... последние 30 дней
  ]
}
```

**Визуализация:**
- KPI Cards для MRR, ARR, Churn Rate
- Area chart для revenue trend
- Funnel chart для conversion
- Bar chart для subscription durations
- Gauge для churn rate (с цветовыми зонами)

---

#### GET `/admin/analytics/features`
**Описание:** Статистика использования функций

**Rate Limit:** 10 req/min

**Response:**
```typescript
interface FeaturesStats {
  memory: {
    total_facts: number;
    users_with_memory: number;
    avg_facts_per_user: number;
  };
  memory_by_category: Array<{
    category: string;
    count: number;
    percentage: number;
  }>;
  summaries: {
    total: number;
    avg_per_user: number;
  };
  tts_usage: {
    total_generated: number;
    users_using: number;
    avg_per_session: number;
  };
  image_analysis: {
    total_images: number;
    users_sent: number;
  };
}

// Example:
{
  "memory": {
    "total_facts": 3456,
    "users_with_memory": 1234,
    "avg_facts_per_user": 2.8
  },
  "memory_by_category": [
    { "category": "interests", "count": 876, "percentage": 25.3 },
    { "category": "family", "count": 654, "percentage": 18.9 },
    { "category": "work", "count": 543, "percentage": 15.7 },
    { "category": "goals", "count": 432, "percentage": 12.5 },
    { "category": "other", "count": 951, "percentage": 27.6 }
  ],
  "summaries": {
    "total": 5678,
    "avg_per_user": 4.6
  },
  "tts_usage": {
    "total_generated": 2345,
    "users_using": 456,
    "avg_per_session": 3.2
  },
  "image_analysis": {
    "total_images": 876,
    "users_sent": 234
  }
}
```

**Визуализация:**
- Metric Cards для основных показателей
- Horizontal Bar chart для категорий памяти
- Donut chart для распределения функций
- Trend line для TTS usage over time

---

#### GET `/admin/analytics/cohort?days=30`
**Описание:** Когортный анализ retention

**Query Parameters:**
- `days` (integer, default: 30) - глубина анализа

**Rate Limit:** 10 req/min

**Response:**
```typescript
interface CohortStats {
  cohorts: Array<{
    cohort_date: string;
    size: number;
    retention: {
      day_1: number;
      day_7: number;
      day_14: number;
      day_30: number;
    };
  }>;
  avg_retention: {
    day_1: number;
    day_7: number;
    day_14: number;
    day_30: number;
  };
}

// Example:
{
  "cohorts": [
    {
      "cohort_date": "2025-09-01",
      "size": 234,
      "retention": {
        "day_1": 67.5,
        "day_7": 34.2,
        "day_14": 23.1,
        "day_30": 15.4
      }
    },
    {
      "cohort_date": "2025-09-02",
      "size": 198,
      "retention": {
        "day_1": 71.2,
        "day_7": 38.4,
        "day_14": 25.8,
        "day_30": 17.2
      }
    }
    // ... остальные когорты
  ],
  "avg_retention": {
    "day_1": 68.7,
    "day_7": 36.5,
    "day_14": 24.3,
    "day_30": 16.8
  }
}
```

**Визуализация:**
- Cohort Table (heatmap) - цветовое кодирование retention rates
- Line chart для сравнения retention разных когорт
- KPI Cards для средних retention rates

**Пример таблицы:**
```
Cohort      Size    Day 1   Day 7   Day 14  Day 30
2025-09-01  234     67.5%   34.2%   23.1%   15.4%
2025-09-02  198     71.2%   38.4%   25.8%   17.2%
...
```

---

#### GET `/admin/analytics/funnel`
**Описание:** Воронка конверсии по уровням отношений

**Rate Limit:** 10 req/min

**Response:**
```typescript
interface FunnelStats {
  levels: Array<{
    level: string;
    users: number;
    conversion_rate: number;  // % от предыдущего уровня
  }>;
  bottleneck: {
    level: string;
    drop_rate: number;
  };
  avg_time_to_next_level: {
    [level: string]: number;  // в днях
  };
  conversion_to_final: number;  // % достигших финального уровня
}

// Example:
{
  "levels": [
    {
      "level": "Незнакомец",
      "users": 15234,
      "conversion_rate": 100.0
    },
    {
      "level": "Знакомый",
      "users": 6691,
      "conversion_rate": 43.9
    },
    {
      "level": "Друг",
      "users": 2676,
      "conversion_rate": 40.0
    },
    {
      "level": "Близкий друг",
      "users": 535,
      "conversion_rate": 20.0
    },
    {
      "level": "Intimate",
      "users": 64,
      "conversion_rate": 11.9
    }
  ],
  "bottleneck": {
    "level": "Друг -> Близкий друг",
    "drop_rate": 80.0
  },
  "avg_time_to_next_level": {
    "Незнакомец -> Знакомый": 3.5,
    "Знакомый -> Друг": 7.8,
    "Друг -> Близкий друг": 14.2,
    "Близкий друг -> Intimate": 21.6
  },
  "conversion_to_final": 0.42
}
```

**Визуализация:**
- Funnel Chart (классическая воронка)
- Sankey Diagram для flow между уровнями
- Bar chart для average time to next level
- Alert badge для bottleneck

---

#### GET `/admin/analytics/activity`
**Описание:** Паттерны активности пользователей

**Rate Limit:** 10 req/min

**Response:**
```typescript
interface ActivityStats {
  by_day_of_week: Array<{
    day: string;
    messages: number;
    active_users: number;
  }>;
  by_hour: Array<{
    hour: number;
    messages: number;
    active_users: number;
  }>;
  peak_hours: Array<{
    hour: number;
    messages: number;
  }>;
  slow_hours: Array<{
    hour: number;
    messages: number;
  }>;
  avg_session_length: number;  // в минутах
}

// Example:
{
  "by_day_of_week": [
    { "day": "Monday", "messages": 4321, "active_users": 1234 },
    { "day": "Tuesday", "messages": 4567, "active_users": 1345 },
    { "day": "Wednesday", "messages": 4890, "active_users": 1456 },
    { "day": "Thursday", "messages": 5123, "active_users": 1523 },
    { "day": "Friday", "messages": 5678, "active_users": 1678 },
    { "day": "Saturday", "messages": 6543, "active_users": 1890 },
    { "day": "Sunday", "messages": 5987, "active_users": 1765 }
  ],
  "by_hour": [
    { "hour": 0, "messages": 123, "active_users": 45 },
    { "hour": 1, "messages": 89, "active_users": 32 },
    // ... 24 часа
  ],
  "peak_hours": [
    { "hour": 20, "messages": 876 },
    { "hour": 21, "messages": 834 },
    { "hour": 19, "messages": 765 }
  ],
  "slow_hours": [
    { "hour": 4, "messages": 34 },
    { "hour": 3, "messages": 45 },
    { "hour": 5, "messages": 56 }
  ],
  "avg_session_length": 8.5
}
```

**Визуализация:**
- Bar chart для активности по дням недели
- Heatmap (24x7) для activity patterns
- Line chart для hourly distribution
- Highlight badges для peak/slow hours

---

#### GET `/admin/analytics/tools?days=7`
**Описание:** Использование AI Tools за период

**Query Parameters:**
- `days` (integer, default: 7)

**Rate Limit:** 10 req/min

**Response:**
```typescript
interface ToolsStats {
  memory_facts_by_day: Array<{
    date: string;
    new_facts: number;
    unique_users: number;
  }>;
  top_categories: Array<{
    category: string;
    count: number;
    growth: number;  // % изменение за период
  }>;
  power_users: Array<{
    user_id: number;
    name: string;
    facts_count: number;
    categories_used: number;
  }>;
  tts_trend: Array<{
    date: string;
    generated: number;
    unique_users: number;
  }>;
}

// Example:
{
  "memory_facts_by_day": [
    {
      "date": "2025-10-01",
      "new_facts": 87,
      "unique_users": 34
    }
    // ... последние N дней
  ],
  "top_categories": [
    { "category": "interests", "count": 234, "growth": 12.5 },
    { "category": "family", "count": 187, "growth": 8.3 },
    { "category": "work", "count": 156, "growth": -2.1 },
    { "category": "goals", "count": 134, "growth": 15.7 },
    { "category": "other", "count": 289, "growth": 5.4 }
  ],
  "power_users": [
    {
      "user_id": 123456,
      "name": "Иван",
      "facts_count": 45,
      "categories_used": 8
    }
    // ... топ 10
  ],
  "tts_trend": [
    {
      "date": "2025-10-01",
      "generated": 76,
      "unique_users": 23
    }
    // ... последние N дней
  ]
}
```

**Визуализация:**
- Line chart для trends (memory facts, TTS)
- Bar chart для top categories
- Table для power users
- Multi-line chart для сравнения разных features

---

### 4. Performance Endpoints:

#### GET `/admin/db_metrics`
**Описание:** Метрики производительности базы данных

**Rate Limit:** 10 req/min

**Response:**
```typescript
interface DBMetrics {
  total_queries: number;
  slow_queries: number;  // > 1 second
  average_query_time: string;
  slow_query_percent: string;
  queries: Array<{
    query: string;
    duration: string;
    timestamp: string;
  }>;
}

// Example:
{
  "total_queries": 15234,
  "slow_queries": 12,
  "average_query_time": "0.023s",
  "slow_query_percent": "0.08%",
  "queries": [
    {
      "query": "SELECT * FROM chat_history WHERE user_id = $1 ORDER BY...",
      "duration": "1.234s",
      "timestamp": "2025-10-05 12:34:56"
    }
    // ... последние slow queries (макс 20)
  ]
}
```

**Визуализация:**
- KPI Cards для метрик
- Table для slow queries
- Line chart для query time over time
- Alert если slow_query_percent > 1%

---

#### GET `/admin/cache_stats`
**Описание:** Статистика Redis кэша

**Rate Limit:** 10 req/min

**Response:**
```typescript
interface CacheStats {
  memory: {
    used_mb: number;
    max_mb: number;
    percentage: number;
  };
  keys: {
    total: number;
    expired: number;
  };
  hit_rate: number;  // percentage
  operations: {
    hits: number;
    misses: number;
    total: number;
  };
  connections: {
    active: number;
    max: number;
  };
}

// Example:
{
  "memory": {
    "used_mb": 45.6,
    "max_mb": 512.0,
    "percentage": 8.9
  },
  "keys": {
    "total": 1234,
    "expired": 45
  },
  "hit_rate": 87.5,
  "operations": {
    "hits": 8765,
    "misses": 1234,
    "total": 9999
  },
  "connections": {
    "active": 12,
    "max": 50
  }
}
```

**Визуализация:**
- Progress bars для memory и connections
- Donut chart для hit/miss ratio
- KPI Card для hit rate
- Line chart для hit rate over time

---

#### GET `/admin/scheduler_status`
**Описание:** Статус фоновых задач

**Rate Limit:** 10 req/min

**Response:**
```typescript
interface SchedulerStatus {
  running: boolean;
  jobs: Array<{
    id: string;
    name: string;
    next_run: string;
    status: string;
    last_run?: string;
    last_result?: string;
  }>;
}

// Example:
{
  "running": true,
  "jobs": [
    {
      "id": "cleanup_messages",
      "name": "Очистка старых сообщений",
      "next_run": "2025-10-06 03:00:00 UTC",
      "status": "scheduled",
      "last_run": "2025-10-05 03:00:00 UTC",
      "last_result": "success"
    },
    {
      "id": "check_subscriptions",
      "name": "Проверка подписок",
      "next_run": "2025-10-05 14:00:00 UTC",
      "status": "scheduled",
      "last_run": "2025-10-05 13:00:00 UTC",
      "last_result": "success"
    },
    {
      "id": "cache_metrics",
      "name": "Метрики кэша",
      "next_run": "2025-10-05 13:15:00 UTC",
      "status": "scheduled"
    }
  ]
}
```

**Визуализация:**
- Status Badge (running/stopped)
- Table для jobs с цветовым статусом
- Countdown для next_run

---

### 5. Admin Actions:

#### POST `/admin/cleanup_chat_history`
**Описание:** Ручной запуск очистки старой истории чата

**Rate Limit:** 1 req/hour (КРИТИЧНО!)

**Request:**
```typescript
interface CleanupRequest {
  days_to_keep?: number;  // default: 30
}

const response = await apiClient.post('/admin/cleanup_chat_history', {
  days_to_keep: 30
});
```

**Response:**
```typescript
interface CleanupResponse {
  deleted_count: number;
  days_kept: number;
}

// Example:
{
  "deleted_count": 12345,
  "days_kept": 30
}
```

**UI Требования:**
- Кнопка должна требовать подтверждения (confirmation modal)
- Показывать warning о необратимости операции
- Disable на 60 минут после выполнения

---

## 📊 Структура данных

### TypeScript типы для frontend:

```typescript
// types/analytics.ts

export interface DateRange {
  start: string;  // ISO 8601
  end: string;
}

export interface MetricCard {
  value: number | string;
  label: string;
  trend?: {
    value: number;
    direction: 'up' | 'down' | 'neutral';
  };
  icon?: string;
}

export interface ChartDataPoint {
  x: string | number;
  y: number;
  label?: string;
}

export interface TimeSeriesData {
  date: string;
  [key: string]: number | string;
}

export interface User {
  user_id: number;
  name: string;
  relationship_level: string;
  subscription_plan: string;
  message_count: number;
  created_at: string;
  last_active: string;
}

export interface Subscription {
  id: number;
  user_id: number;
  plan: string;
  status: 'active' | 'expired' | 'cancelled';
  created_at: string;
  expires_at: string;
  amount: number;
}

// Добавьте остальные типы из Response интерфейсов выше
```

---

## 🎨 UI/UX Компоненты

### Рекомендуемые компоненты:

#### 1. Layout Components:

```typescript
// Layout.tsx
<Layout>
  <Sidebar>
    <Logo />
    <Navigation />
    <UserMenu />
  </Sidebar>
  <MainContent>
    <Header>
      <Breadcrumbs />
      <ServiceStatus />
      <DateRangePicker />
    </Header>
    <PageContent>
      {children}
    </PageContent>
  </MainContent>
</Layout>
```

#### 2. Dashboard Page:

```typescript
// pages/Dashboard.tsx
<Dashboard>
  <Grid container spacing={3}>
    {/* Row 1: Key Metrics */}
    <Grid item xs={12} md={3}>
      <MetricCard
        title="DAU"
        value={data.users.active_today}
        trend={{ value: 5.2, direction: 'up' }}
        icon={<PeopleIcon />}
      />
    </Grid>
    <Grid item xs={12} md={3}>
      <MetricCard
        title="MAU"
        value={data.users.active_month}
        trend={{ value: 12.3, direction: 'up' }}
      />
    </Grid>
    <Grid item xs={12} md={3}>
      <MetricCard
        title="MRR"
        value={`$${data.revenue.mrr}`}
        trend={{ value: 8.4, direction: 'up' }}
      />
    </Grid>
    <Grid item xs={12} md={3}>
      <MetricCard
        title="Churn Rate"
        value={`${data.churn.rate}%`}
        trend={{ value: -2.1, direction: 'down' }}
        color="error"
      />
    </Grid>

    {/* Row 2: Charts */}
    <Grid item xs={12} md={8}>
      <Card>
        <CardHeader title="User Activity" />
        <CardContent>
          <LineChart data={activityData} />
        </CardContent>
      </Card>
    </Grid>
    <Grid item xs={12} md={4}>
      <Card>
        <CardHeader title="Subscription Split" />
        <CardContent>
          <PieChart data={subscriptionData} />
        </CardContent>
      </Card>
    </Grid>

    {/* Row 3: Tables */}
    <Grid item xs={12} md={6}>
      <Card>
        <CardHeader title="Top Active Users" />
        <CardContent>
          <UserTable data={topUsers} />
        </CardContent>
      </Card>
    </Grid>
    <Grid item xs={12} md={6}>
      <Card>
        <CardHeader title="Recent Subscriptions" />
        <CardContent>
          <SubscriptionTable data={recentSubs} />
        </CardContent>
      </Card>
    </Grid>
  </Grid>
</Dashboard>
```

#### 3. Charts Examples:

```typescript
// Recharts Line Chart
<ResponsiveContainer width="100%" height={300}>
  <LineChart data={data}>
    <CartesianGrid strokeDasharray="3 3" />
    <XAxis dataKey="date" />
    <YAxis />
    <Tooltip />
    <Legend />
    <Line 
      type="monotone" 
      dataKey="dau" 
      stroke="#8884d8" 
      name="DAU"
    />
    <Line 
      type="monotone" 
      dataKey="mau" 
      stroke="#82ca9d" 
      name="MAU"
    />
  </LineChart>
</ResponsiveContainer>

// Pie Chart
<ResponsiveContainer width="100%" height={300}>
  <PieChart>
    <Pie
      data={data}
      dataKey="value"
      nameKey="name"
      cx="50%"
      cy="50%"
      outerRadius={100}
      label
    >
      {data.map((entry, index) => (
        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
      ))}
    </Pie>
    <Tooltip />
    <Legend />
  </PieChart>
</ResponsiveContainer>

// Funnel Chart
<ResponsiveContainer width="100%" height={400}>
  <BarChart
    data={funnelData}
    layout="vertical"
  >
    <CartesianGrid strokeDasharray="3 3" />
    <XAxis type="number" />
    <YAxis dataKey="level" type="category" />
    <Tooltip />
    <Bar dataKey="users" fill="#8884d8">
      <LabelList dataKey="conversion_rate" position="right" />
    </Bar>
  </BarChart>
</ResponsiveContainer>

// Heatmap (Activity)
<HeatMap
  xLabels={hours}
  yLabels={days}
  data={heatmapData}
  cellRender={(value) => (
    <div style={{ backgroundColor: getColor(value) }}>
      {value}
    </div>
  )}
/>
```

#### 4. Date Range Picker:

```typescript
// components/DateRangePicker.tsx
<DateRangePicker
  startDate={startDate}
  endDate={endDate}
  onChange={(range) => {
    setStartDate(range.start);
    setEndDate(range.end);
  }}
  presets={[
    { label: 'Last 7 days', value: 7 },
    { label: 'Last 30 days', value: 30 },
    { label: 'Last 90 days', value: 90 },
    { label: 'Custom', value: 'custom' }
  ]}
/>
```

#### 5. Service Status Indicator:

```typescript
// components/ServiceStatus.tsx
<ServiceStatus>
  <Tooltip title="API Status">
    <Chip
      icon={<CircleIcon />}
      label="API"
      color={apiStatus === 'healthy' ? 'success' : 'error'}
      size="small"
    />
  </Tooltip>
  <Tooltip title="Database Status">
    <Chip
      icon={<DatabaseIcon />}
      label="DB"
      color={dbStatus === 'healthy' ? 'success' : 'error'}
      size="small"
    />
  </Tooltip>
  <Tooltip title="Redis Status">
    <Chip
      icon={<CacheIcon />}
      label="Redis"
      color={redisStatus === 'healthy' ? 'success' : 'warning'}
      size="small"
    />
  </Tooltip>
</ServiceStatus>
```

---

## 🔐 Аутентификация

### Workflow:

```typescript
// 1. Login Page
const handleLogin = async (userId: number) => {
  try {
    const { data } = await apiClient.post('/auth', { user_id: userId });
    
    // Сохранение токена
    localStorage.setItem('authToken', data.access_token);
    localStorage.setItem('userId', userId.toString());
    
    // Редирект на дашборд
    navigate('/dashboard');
  } catch (error) {
    showError('Authentication failed');
  }
};

// 2. Protected Routes
const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem('authToken');
  
  if (!token) {
    return <Navigate to="/login" />;
  }
  
  return children;
};

// 3. Auto Logout on Token Expiry
useEffect(() => {
  const checkTokenExpiry = () => {
    const token = localStorage.getItem('authToken');
    if (token) {
      const decoded = jwtDecode(token);
      const now = Date.now() / 1000;
      
      if (decoded.exp < now) {
        // Token expired
        localStorage.removeItem('authToken');
        navigate('/login');
      }
    }
  };
  
  // Проверка каждую минуту
  const interval = setInterval(checkTokenExpiry, 60000);
  return () => clearInterval(interval);
}, []);

// 4. Refresh Token (опционально)
// Если реализуете refresh механизм на backend
const refreshToken = async () => {
  const { data } = await apiClient.post('/auth/refresh');
  localStorage.setItem('authToken', data.access_token);
};
```

### Security Best Practices:

1. **HTTPS Only** - в production используйте только HTTPS
2. **Secure Storage** - рассмотрите использование httpOnly cookies вместо localStorage
3. **CSRF Protection** - если используете cookies
4. **Rate Limiting** - обрабатывайте 429 ошибки
5. **Token Rotation** - реализуйте refresh tokens для длительных сессий

---

## 🧪 Примеры использования API

### React Query Hooks:

```typescript
// hooks/useAnalytics.ts
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../services/api';

export const useOverviewStats = () => {
  return useQuery({
    queryKey: ['analytics', 'overview'],
    queryFn: async () => {
      const { data } = await apiClient.get('/admin/analytics/overview');
      return data;
    },
    refetchInterval: 60000, // Обновление каждую минуту
    staleTime: 30000, // Данные свежие 30 секунд
  });
};

export const useUsersStats = () => {
  return useQuery({
    queryKey: ['analytics', 'users'],
    queryFn: async () => {
      const { data } = await apiClient.get('/admin/analytics/users');
      return data;
    },
    refetchInterval: 300000, // 5 минут
  });
};

export const useMessagesStats = (days: number = 7) => {
  return useQuery({
    queryKey: ['analytics', 'messages', days],
    queryFn: async () => {
      const { data } = await apiClient.get(`/admin/analytics/messages?days=${days}`);
      return data;
    },
    enabled: days > 0, // Запускать только если days задан
  });
};

export const useRevenueStats = () => {
  return useQuery({
    queryKey: ['analytics', 'revenue'],
    queryFn: async () => {
      const { data } = await apiClient.get('/admin/analytics/revenue');
      return data;
    },
    refetchInterval: 300000,
  });
};

// Мутация для cleanup
export const useCleanupChatHistory = () => {
  return useMutation({
    mutationFn: async (daysToKeep: number) => {
      const { data } = await apiClient.post('/admin/cleanup_chat_history', {
        days_to_keep: daysToKeep
      });
      return data;
    },
    onSuccess: () => {
      toast.success('Chat history cleaned successfully');
    },
    onError: (error) => {
      toast.error('Failed to cleanup chat history');
    }
  });
};
```

### Component Usage:

```typescript
// pages/Dashboard.tsx
import { useOverviewStats, useUsersStats } from '../hooks/useAnalytics';

const Dashboard = () => {
  const { data: overview, isLoading, error } = useOverviewStats();
  const { data: users } = useUsersStats();
  
  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;
  
  return (
    <Grid container spacing={3}>
      <Grid item xs={12} md={3}>
        <MetricCard
          title="DAU"
          value={overview?.users.active_today}
          trend={{
            value: calculateTrend(overview),
            direction: 'up'
          }}
        />
      </Grid>
      {/* ... остальные компоненты */}
    </Grid>
  );
};
```

### Error Handling:

```typescript
// utils/errorHandler.ts
export const handleApiError = (error: any) => {
  if (error.response) {
    // Сервер ответил с ошибкой
    const status = error.response.status;
    const message = error.response.data?.detail || 'Unknown error';
    
    switch (status) {
      case 401:
        // Redirect to login
        window.location.href = '/login';
        return 'Authentication required';
      case 403:
        return 'Access forbidden';
      case 429:
        return 'Too many requests. Please try again later.';
      case 500:
        return 'Server error. Please try again.';
      default:
        return message;
    }
  } else if (error.request) {
    // Запрос был отправлен, но ответа нет
    return 'Network error. Please check your connection.';
  } else {
    // Что-то пошло не так при настройке запроса
    return error.message;
  }
};
```

---

## 🚀 Deployment

### Development:

```bash
# 1. Install dependencies
npm install

# 2. Create .env.local
cat > .env.local << EOF
REACT_APP_API_URL=http://localhost:8000
EOF

# 3. Start dev server
npm run dev
```

### Production Build:

```bash
# 1. Build
npm run build

# 2. Preview
npm run preview

# 3. Deploy (example with Vercel)
vercel --prod
```

### Docker Deployment:

```dockerfile
# Dockerfile
FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

```nginx
# nginx.conf
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # API Proxy (опционально)
    location /api/ {
        proxy_pass http://api:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Environment Variables:

```bash
# .env.production
REACT_APP_API_URL=https://api.yourdomain.com
REACT_APP_ENV=production
REACT_APP_VERSION=1.0.0
```

---

## 📈 Performance Optimization

### Best Practices:

1. **Code Splitting:**
```typescript
// Lazy loading pages
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Users = lazy(() => import('./pages/Users'));
const Revenue = lazy(() => import('./pages/Revenue'));
```

2. **Memoization:**
```typescript
// Memoize expensive calculations
const chartData = useMemo(() => {
  return processChartData(rawData);
}, [rawData]);

// Memoize components
const MemoizedChart = memo(LineChart);
```

3. **Debounce/Throttle:**
```typescript
// Debounce search input
const debouncedSearch = useMemo(
  () => debounce((value) => fetchData(value), 500),
  []
);
```

4. **Virtual Scrolling:**
```typescript
// Для больших таблиц используйте react-window
import { FixedSizeList } from 'react-window';
```

5. **Image Optimization:**
```typescript
// Lazy load images
<img 
  src={imageUrl} 
  loading="lazy" 
  alt="Chart"
/>
```

---

## 🧪 Testing

### Unit Tests:

```typescript
// components/__tests__/MetricCard.test.tsx
import { render, screen } from '@testing-library/react';
import MetricCard from '../MetricCard';

describe('MetricCard', () => {
  it('renders metric value', () => {
    render(<MetricCard title="DAU" value={1234} />);
    expect(screen.getByText('1234')).toBeInTheDocument();
  });
  
  it('renders trend indicator', () => {
    render(
      <MetricCard 
        title="DAU" 
        value={1234}
        trend={{ value: 5.2, direction: 'up' }}
      />
    );
    expect(screen.getByText('+5.2%')).toBeInTheDocument();
  });
});
```

### Integration Tests:

```typescript
// hooks/__tests__/useAnalytics.test.tsx
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useOverviewStats } from '../useAnalytics';

const queryClient = new QueryClient();
const wrapper = ({ children }) => (
  <QueryClientProvider client={queryClient}>
    {children}
  </QueryClientProvider>
);

describe('useOverviewStats', () => {
  it('fetches overview stats', async () => {
    const { result } = renderHook(() => useOverviewStats(), { wrapper });
    
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    
    expect(result.current.data).toHaveProperty('users');
    expect(result.current.data).toHaveProperty('messages');
  });
});
```

---

## 📚 Дополнительные ресурсы

### Документация Backend:
- [README.md](./README.md) - общее описание проекта
- [ANALYTICS_GUIDE.md](./ANALYTICS_GUIDE.md) - детальное описание аналитики
- [API Documentation](http://localhost:8000/docs) - Swagger UI

### UI Libraries Documentation:
- [Material-UI](https://mui.com/)
- [Recharts](https://recharts.org/)
- [React Query](https://tanstack.com/query/latest)
- [React Router](https://reactrouter.com/)

### Design Inspiration:
- [Google Analytics Dashboard](https://analytics.google.com/)
- [Mixpanel Dashboard](https://mixpanel.com/)
- [Amplitude Dashboard](https://amplitude.com/)

---

## 🤝 Поддержка

При возникновении вопросов:
1. Проверьте документацию API: `http://localhost:8000/docs`
2. Проверьте health check: `http://localhost:8000/ready`
3. Просмотрите логи API: `docker-compose logs -f api`

---

<div align="center">
  <strong>Dashboard Specification v1.0</strong>
  <br>
  <em>Updated: 2025-10-05</em>
</div>
