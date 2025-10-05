# Analytics Dashboard - Руководство пользователя

## 📊 Обзор

Analytics Dashboard предоставляет детальную статистику использования бота EvolveAI, помогая принимать решения на основе данных.

**9 аналитических endpoints:**

**Базовые:**
- `/admin/analytics/overview` - Общая статистика
- `/admin/analytics/users` - Статистика пользователей
- `/admin/analytics/messages` - Статистика сообщений
- `/admin/analytics/revenue` - Статистика подписок
- `/admin/analytics/features` - Использование функций

**Продвинутые:**
- `/admin/analytics/cohort` - Когортный анализ (retention)
- `/admin/analytics/funnel` - Воронка уровней отношений
- `/admin/analytics/activity` - Паттерны активности
- `/admin/analytics/tools` - Детальная статистика AI Tools

**Все endpoints:**
- ✅ Требуют JWT авторизацию
- ✅ Кэшируются на 5-10 минут
- ✅ Rate limit: 10 запросов/минуту
- ⚠️ Нужны права администратора (TODO)

---

## 🎯 1. Overview - Общая статистика

### Endpoint
```
GET /admin/analytics/overview
```

### Что показывает
- **Пользователи:** total, active (7d), DAU, premium, conversion rate
- **Сообщения:** total, за 24ч, среднее на пользователя
- **Engagement:** средний уровень отношений, retention 7d

### Пример запроса
```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8000/admin/analytics/overview
```

### Пример ответа
```json
{
  "analytics": {
    "users": {
      "total": 1250,
      "active_7d": 456,
      "dau": 127,
      "premium": 89,
      "conversion_rate": 7.12
    },
    "messages": {
      "total": 45230,
      "last_24h": 2341,
      "avg_per_user": 36.18
    },
    "engagement": {
      "avg_relationship_level": 4.8,
      "retention_7d": 36.48
    },
    "timestamp": "2025-01-05T19:30:00Z"
  }
}
```

### Ключевые метрики
- **DAU** (Daily Active Users) - пользователи за 24 часа
- **Conversion rate** - процент premium пользователей
- **Retention 7d** - активных из общего числа

---

## 👥 2. Users - Статистика пользователей

### Endpoint
```
GET /admin/analytics/users
```

### Что показывает
- Распределение по уровням отношений (1-14)
- Распределение по подпискам (free/premium)
- Топ-10 активных пользователей
- Новые пользователи за 7 дней
- Пользователи с долговременной памятью

### Пример ответа
```json
{
  "analytics": {
    "levels_distribution": {
      "level_1": 234,
      "level_2": 189,
      "level_3": 145,
      "level_4": 98,
      "level_5": 67
    },
    "subscription_distribution": {
      "free": 1161,
      "premium": 89
    },
    "top_users": [
      {"user_id": 12345, "messages": 1234},
      {"user_id": 67890, "messages": 987}
    ],
    "new_users_7d": 73,
    "users_with_memory": 456
  }
}
```

### Зачем нужно
- Понять на каких уровнях "застревают" пользователи
- Найти power users для feedback
- Отследить рост новых пользователей

---

## 💬 3. Messages - Статистика сообщений

### Endpoint
```
GET /admin/analytics/messages?days=7
```

### Параметры
- `days` (опционально) - количество дней для анализа (по умолчанию 7)

### Что показывает
- Сообщения по дням (тренд)
- Сообщения по часам (пиковая нагрузка)
- Соотношение user/model сообщений
- Средняя длина сообщений пользователя

### Пример ответа
```json
{
  "analytics": {
    "period_days": 7,
    "total_messages": 15340,
    "messages_by_day": {
      "2025-01-01": 2134,
      "2025-01-02": 2456,
      "2025-01-03": 2198
    },
    "messages_by_hour": {
      "0": 234,
      "1": 189,
      "12": 892,
      "18": 1245,
      "21": 998
    },
    "role_distribution": {
      "user": 7670,
      "model": 7670
    },
    "avg_user_message_length": 87.45
  }
}
```

### Зачем нужно
- **Пиковая нагрузка:** знать когда масштабировать
- **Тренд:** растет ли использование
- **Длина сообщений:** оптимизация промптов

---

## 💰 4. Revenue - Статистика подписок

### Endpoint
```
GET /admin/analytics/revenue
```

### Что показывает
- Активные premium подписки
- Новые подписки за 7 дней
- Истекающие подписки (в течение 7 дней)
- MRR (Monthly Recurring Revenue)
- ARR (Annual Recurring Revenue)
- Churn rate и Retention rate

### Пример ответа
```json
{
  "analytics": {
    "active_subscriptions": 89,
    "new_subscriptions_7d": 12,
    "expiring_soon_7d": 8,
    "expired_last_month": 5,
    "avg_subscription_days": 28.7,
    "revenue": {
      "mrr": 26611,
      "currency": "RUB",
      "projected_arr": 319332
    },
    "metrics": {
      "churn_rate": 5.32,
      "retention_rate": 94.68
    }
  }
}
```

### Ключевые метрики
- **MRR** - месячный recurring доход (active_subs × avg_price)
- **ARR** - годовой projected (MRR × 12)
- **Churn rate** - процент отказов
- **Retention** - процент удержания (100 - churn)

### Средняя цена подписки
По умолчанию: **299 RUB/месяц** (настраивается в `analytics.py`)

---

## 🔧 5. Features - Использование функций

### Endpoint
```
GET /admin/analytics/features
```

### Что показывает
- Всего фактов в долговременной памяти
- Пользователей использующих память
- Память по категориям (preferences, family, work, etc.)
- Количество созданных сводок (показатель длинных диалогов)

### Пример ответа
```json
{
  "analytics": {
    "memory": {
      "total_facts": 2340,
      "users_using": 456,
      "by_category": {
        "preferences": 890,
        "family": 456,
        "work": 234,
        "hobbies": 189,
        "memories": 345
      }
    },
    "summaries": {
      "total": 234
    }
  }
}
```

### Зачем нужно
- Понять популярность функций
- Оптимизировать промпты для памяти
- Понять глубину диалогов (summaries)

---

## 🚀 Использование в коде

### Python пример
```python
import httpx

# Получить JWT токен
auth_response = httpx.post(
    "http://localhost:8000/auth",
    json={"user_id": ADMIN_USER_ID}
)
token = auth_response.json()["access_token"]

# Получить статистику
headers = {"Authorization": f"Bearer {token}"}

# Overview
overview = httpx.get(
    "http://localhost:8000/admin/analytics/overview",
    headers=headers
).json()

print(f"DAU: {overview['analytics']['users']['dau']}")
print(f"MRR: {overview['analytics']['users']['premium'] * 299} RUB")
```

### JavaScript пример
```javascript
// Получить токен
const authRes = await fetch('http://localhost:8000/auth', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({user_id: ADMIN_USER_ID})
});
const {access_token} = await authRes.json();

// Получить статистику
const analytics = await fetch(
  'http://localhost:8000/admin/analytics/overview',
  {headers: {'Authorization': `Bearer ${access_token}`}}
).json();

console.log('Total users:', analytics.analytics.users.total);
```

---

## 📈 Кэширование

Все аналитические запросы кэшируются:
- **Overview, Users, Messages, Features:** 5 минут
- **Revenue:** 10 минут

**Инвалидация кэша:**
```python
from utils.cache import invalidate_pattern

# Очистить весь кэш аналитики
await invalidate_pattern("analytics_*")

# Очистить конкретный кэш
await invalidate_pattern("analytics_overview*")
```

---

## ⚠️ Важные замечания

### Безопасность
- **TODO:** Все endpoints требуют проверки прав администратора
- Сейчас достаточно валидного JWT токена
- Нужно добавить role-based access control

### Производительность
- Тяжелые запросы кэшируются
- Лимит: 10 запросов/минуту
- Используйте агрегацию на стороне клиента

### Точность данных
- Данные актуальны с учетом TTL кэша
- Для real-time используйте Prometheus метрики
- Для исторических данных добавьте партиционирование

---

## 🎨 Dashboard UI (опционально)

Можно создать простой dashboard с помощью:
- **Grafana** - готовые дашборды для Prometheus
- **Streamlit** - быстрый Python UI
- **React Admin** - полноценная админка
- **Custom HTML** - простая страница с графиками

### Пример с Chart.js
```html
<canvas id="userChart"></canvas>
<script>
fetch('/admin/analytics/users', {
  headers: {'Authorization': 'Bearer ' + token}
})
.then(r => r.json())
.then(data => {
  new Chart(document.getElementById('userChart'), {
    type: 'bar',
    data: {
      labels: Object.keys(data.analytics.levels_distribution),
      datasets: [{
        label: 'Users by Level',
        data: Object.values(data.analytics.levels_distribution)
      }]
    }
  });
});
</script>
```

---

## 📚 См. также

- [SCALABILITY_IMPROVEMENTS.md](SCALABILITY_IMPROVEMENTS.md) - Производительность
- [README.md](README.md) - Общая документация
- [Prometheus Metrics](http://localhost:8000/metrics) - Real-time метрики

---

---

## 🔥 6. Cohort - Когортный анализ

### Endpoint
```
GET /admin/analytics/cohort?days=30
```

### Что показывает
- Retention по дням регистрации (Day 1, Day 7)
- Средний retention по всем когортам
- Качество аудитории

### Пример ответа
```json
{
  "analytics": {
    "period_days": 30,
    "cohorts": {
      "2025-01-01": {
        "cohort_size": 45,
        "day_1_active": 32,
        "day_1_retention": 71.11,
        "day_7_active": 18,
        "day_7_retention": 40.0
      }
    },
    "average_retention": {
      "day_1": 68.5,
      "day_7": 35.2
    }
  }
}
```

### Зачем нужно
- Понять качество пользователей по датам
- Сравнить cohorts (например, после маркетинговой кампании)
- Оптимизировать onboarding

---

## 🎯 7. Funnel - Воронка уровней

### Endpoint
```
GET /admin/analytics/funnel
```

### Что показывает
- Conversion rates между уровнями (1→2→3...)
- Bottleneck detection (где застревают)
- Средний уровень достижения
- % conversion до финального уровня 14

### Пример ответа
```json
{
  "analytics": {
    "funnel": {
      "level_1": {
        "users": 1250,
        "conversion_from_previous": 100,
        "conversion_from_start": 100
      },
      "level_2": {
        "users": 890,
        "conversion_from_previous": 71.2,
        "conversion_from_start": 71.2
      },
      "level_5": {
        "users": 234,
        "conversion_from_previous": 58.5,
        "conversion_from_start": 18.72
      }
    },
    "insights": {
      "total_users": 1250,
      "avg_level_reached": 4.8,
      "bottleneck_level": 8,
      "bottleneck_dropoff": 67.3,
      "level_14_conversion": 2.4
    }
  }
}
```

### Зачем нужно
- Найти проблемные уровни (bottleneck)
- Оптимизировать промпты для проблемных переходов
- Понять % достигающих premium уровней

---

## 📅 8. Activity - Паттерны активности

### Endpoint
```
GET /admin/analytics/activity
```

### Что показывает
- Активность по дням недели (Mon-Sun)
- Пиковые и медленные часы
- Средняя длина сессии (минуты)

### Пример ответа
```json
{
  "analytics": {
    "by_weekday": {
      "Monday": {
        "messages": 2134,
        "active_users": 345,
        "avg_messages_per_user": 6.18
      },
      "Friday": {
        "messages": 2897,
        "active_users": 412,
        "avg_messages_per_user": 7.03
      }
    },
    "peak_hour": 21,
    "slowest_hour": 5,
    "avg_session_minutes": 23.45
  }
}
```

### Зачем нужно
- **Планирование maintenance** - делать в slowest_hour
- **Маркетинг** - отправлять уведомления в peak_hour
- **Масштабирование** - знать когда нужны ресурсы

---

## 🛠️ 9. Tools - Детальная статистика функций

### Endpoint
```
GET /admin/analytics/tools?days=7
```

### Что показывает
- Новые факты памяти по дням
- Топ-5 категорий памяти
- Power users (>5 фактов)

### Пример ответа
```json
{
  "analytics": {
    "period_days": 7,
    "memory": {
      "new_facts_by_day": {
        "2025-01-01": 45,
        "2025-01-02": 67
      },
      "top_categories": {
        "preferences": 234,
        "family": 189,
        "work": 145
      },
      "power_users": 89
    }
  }
}
```

### Зачем нужно
- Понять популярность функций
- Оптимизировать промпты для save_memory
- Найти power users для feedback

---

## 🔜 Roadmap

**Планируется добавить:**
- [ ] Экспорт данных в CSV/JSON
- [ ] Сравнение периодов (week-over-week)
- [x] Когортный анализ ✅
- [x] Funnel analysis (уровни 1→7→14) ✅
- [ ] Предиктивная аналитика (churn prediction)
- [ ] Alerting при аномалиях
- [x] Паттерны активности ✅
- [x] Детальная статистика Tools ✅
