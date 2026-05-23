# DEONATS — Financial OS
## Industrial Brutalism · CLI-First · PWA

---

## Структура проекта

```
deonats/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app, CORS, роутер
│   │   ├── api/
│   │   │   └── routes.py              # Все CLI-эндпоинты
│   │   ├── db/
│   │   │   └── session.py             # SQLAlchemy engine + get_db()
│   │   ├── models/
│   │   │   └── models.py              # User, Transaction, Debt, Goal, Benchmark,
│   │   │                              # CategoryLimit, SystemLog
│   │   ├── services/
│   │   │   └── security.py            # Master Password, хеш bcrypt, блокировка
│   │   └── engines/
│   │       ├── kernel_panic.py        # KernelPanicEngine — лимиты, блокировка
│   │       └── penalty.py             # PenaltyEngine — штраф за досрочный вывод
│   └── requirements.txt
│
└── frontend/
    ├── public/
    │   ├── manifest.json              # PWA манифест
    │   └── sw.js                      # Service Worker (offline-first)
    └── src/
        ├── components/
        │   └── DeonatsTerminal.jsx    # Главный терминал (React)
        └── i18n/
            └── translations.json      # RU/EN словарь
```

---

## API эндпоинты

| Метод | URL | CLI-команда | Описание |
|-------|-----|-------------|----------|
| POST | /api/v1/auth/login | `login [user] [pass]` | Аутентификация, блокировка после 3 попыток |
| POST | /api/v1/transaction/add | `add [сумма] [тип] [кат]` | Добавить транзакцию + KernelPanicEngine |
| GET | /api/v1/status/{uid} | `check-status` | Статус ядра, категории, логи |
| POST | /api/v1/debt/repay | `repay-debt [id] [сумма]` | Погасить долг |
| POST | /api/v1/goal/add | `goal-add [назв] [сумма] [дата]` | Создать цель |
| POST | /api/v1/goal/deposit | `goal-deposit [id] [сумма]` | Пополнить цель |
| POST | /api/v1/goal/withdraw | `goal-withdraw [id] [сумма]` | Вывести (+ PenaltyEngine) |
| GET | /api/v1/goal/status/{uid} | `goal-status` | Список целей с прогрессом |

---

## Движки (Engines)

### KernelPanicEngine
- Проверяет трату до записи транзакции
- При превышении 100% лимита: `is_blocked = True` в `category_limits`
- Предупреждение при ≥80%
- Пишет в `system_logs` с уровнями INFO / WARN / CRITICAL

### PenaltyEngine
- Вызывается при `goal-withdraw` до deadline
- Штраф: **15%** от суммы вывода
- Устанавливает `goal.status = 'violated'`
- Логирует в `system_logs`

### SecurityService
- Пароли: bcrypt через `passlib`
- Блокировка: `failed_attempts >= 3` → `is_locked = True`
- Разблокировка: эндпоинт `/admin/unlock` (отдельный роутер)

---

## База данных (PostgreSQL)

```
users               — настройки, тема, язык, блокировка
transactions        — все финансовые операции
debts               — виртуальные долги
goals               — цели с deadline и penalty
benchmarks          — пользовательские KPI
category_limits     — лимиты по категориям + флаг блокировки
system_logs         — журнал ядра (KernelPanic, Auth, Penalty)
```

---

## Запуск

```bash
# Backend
cd backend
pip install -r requirements.txt
DATABASE_URL=postgresql://user:pass@localhost/deonats uvicorn app.main:app --reload

# Frontend
cd frontend
npx create-react-app . --template cra-template-pwa
# Скопировать DeonatsTerminal.jsx в src/components/
npm start
```

---

## Цветовая палитра

| Токен | Dark | Light | Назначение |
|-------|------|-------|------------|
| `--bg` | `#0A0A0A` | `#E5E5E5` | Фон |
| `--gold` | `#C9A84C` | `#8B6914` | Акцент, промпт |
| `--panic` | `#FF3333` | `#CC0000` | KernelPanic |
| `--warn` | `#FF9900` | `#BB6600` | Предупреждение |
| `--ok` | `#33CC77` | `#006633` | Успех |
| `--dim` | `#555555` | `#777777` | Подсказки |
