# Telegram Reminder Bot с ИИ

Telegram-бот-напоминалка с искусственным интеллектом на Python для Vercel.

## Технологии

- **Python 3.11+**
- **aiogram 3.x** - Telegram Bot API
- **Mistral AI** - распознавание напоминаний
- **Vercel** - serverless хостинг
- **Webhook** архитектура (не polling)

## Структура проекта

```
BotReminder/
├── api/
│   └── webhook.py       # Serverless функция для Vercel
├── requirements.txt     # Python зависимости
├── vercel.json         # Конфигурация Vercel
├── .env.example        # Пример переменных окружения
└── README.md           # Эта инструкция
```

## Быстрый старт

### 1. Получите Telegram Bot Token

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Скопируйте токен

### 2. Клонируйте репозиторий

```bash
git clone https://github.com/nazarn1xyy/BotReminder.git
cd BotReminder
```

### 3. Деплой на Vercel

#### Вариант А: Через Vercel Dashboard (рекомендуется)

1. Зайдите на [vercel.com](https://vercel.com)
2. Нажмите **Add New** → **Project**
3. Импортируйте Git репозиторий `https://github.com/nazarn1xyy/BotReminder.git`
4. Vercel автоматически определит Python проект
5. Добавьте переменные окружения:
   - `BOT_TOKEN` - ваш Telegram Bot Token
   - `MISTRAL_API_KEY` - `7eMrGygzAbBjIhIuFXDEYqrMaxpyuHh5`
   - `WEBHOOK_SECRET` - `my_secret_webhook_key`
6. Нажмите **Deploy**
7. Скопируйте URL проекта (например: `https://bot-reminder-xxx.vercel.app`)

#### Вариант Б: Через Vercel CLI

```bash
# Установите Vercel CLI
npm i -g vercel

# Войдите в аккаунт
vercel login

# Деплой
vercel

# После деплоя для продакшена
vercel --prod
```

### 4. Установите Webhook

После деплоя нужно установить webhook для Telegram.

**Способ 1: Через curl**

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://ваш-домен.vercel.app/api/webhook"}'
```

**Способ 2: Через браузер**

Откройте в браузере:
```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://ваш-домен.vercel.app/api/webhook
```

**Проверка webhook:**

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

### 5. Настройте Cron для напоминаний

Для отправки напоминаний нужно периодически вызывать endpoint `/api/cron`.

#### Вариант А: Vercel Cron Jobs

Добавьте в `vercel.json`:

```json
{
  "crons": [
    {
      "path": "/api/cron",
      "schedule": "*/5 * * * *"
    }
  ]
}
```

#### Вариант Б: Внешний cron-сервис

Используйте [cron-job.org](https://cron-job.org) или [EasyCron](https://easycron.com):

- URL: `https://ваш-домен.vercel.app/api/cron`
- Интервал: каждые 5 минут (`*/5 * * * *`)

#### Вариант В: GitHub Actions

Создайте `.github/workflows/cron.yml`:

```yaml
name: Reminder Cron
on:
  schedule:
    - cron: '*/5 * * * *'
jobs:
  cron:
    runs-on: ubuntu-latest
    steps:
      - name: Call cron endpoint
        run: curl https://ваш-домен.vercel.app/api/cron
```

## Использование

### Команды бота

- `/start` - запуск бота
- `/help` - помощь
- `/list` - список напоминаний
- `/today` - задачи на сегодня
- `/settings` - настройки

### Примеры использования

Просто напишите боту обычным текстом:

```
стрижка завтра в 15:00
```

```
встреча 3 июня в 10:00
```

```
купить молоко сегодня в 18:00
```

Бот распознает через Mistral AI:
- Дату
- Время
- Название события
- Категорию
- Приоритет

Если информации не хватает, бот уточнит.

## Функционал

✅ **Распознавание через ИИ** - Mistral AI понимает естественный язык  
✅ **Напоминания** - за 2 часа, 30 минут и в момент события  
✅ **Категории** - личное, работа, учёба, здоровье, финансы, важное, другое  
✅ **Приоритеты** - обычное, важное, срочное  
✅ **Повторяющиеся** - daily, weekly, monthly, yearly  
✅ **Inline-кнопки** - удобное управление  
✅ **FSM** - уточнение недостающей информации  
✅ **Webhook** - работает на serverless  

## Архитектура

### Почему webhook, а не polling?

**Polling** (постоянный опрос):
- ❌ Не работает на serverless
- ❌ Требует постоянный процесс
- ❌ Больше нагрузка

**Webhook** (Telegram отправляет обновления):
- ✅ Работает на serverless
- ✅ Нет постоянного процесса
- ✅ Меньше нагрузка
- ✅ Быстрее отклик

### Хранение данных

⚠️ **Важно:** Текущая версия использует in-memory хранилище (глобальные переменные Python). Данные сохраняются между запросами в рамках одного инстанса, но могут теряться при cold start.

**Для продакшена рекомендуется использовать внешнюю БД:**

1. **Supabase PostgreSQL** (бесплатно)
   - [supabase.com](https://supabase.com)
   - Managed PostgreSQL

2. **Neon PostgreSQL** (бесплатно)
   - [neon.tech](https://neon.tech)
   - Serverless PostgreSQL

3. **Turso SQLite** (бесплатно)
   - [turso.tech](https://turso.tech)
   - Managed SQLite в облаке

4. **Upstash Redis** (бесплатно)
   - [upstash.com](https://upstash.com)
   - Serverless Redis

## Endpoints

- `GET /api/webhook` - проверка работы бота
- `POST /api/webhook` - прием обновлений от Telegram
- `GET /api/cron` - проверка и отправка напоминаний

## Переменные окружения

Настройте в Vercel Dashboard → Settings → Environment Variables:

```env
BOT_TOKEN=your_telegram_bot_token_here
MISTRAL_API_KEY=7eMrGygzAbBjIhIuFXDEYqrMaxpyuHh5
WEBHOOK_SECRET=my_secret_webhook_key
```

## Troubleshooting

### Бот не отвечает

1. Проверьте webhook:
```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

2. Проверьте логи в Vercel Dashboard → Deployments → Functions

3. Убедитесь, что `BOT_TOKEN` правильный

### Напоминания не приходят

1. Проверьте cron:
```bash
curl https://ваш-домен.vercel.app/api/cron
```

2. Убедитесь, что cron настроен (Vercel Cron Jobs или внешний сервис)

3. Проверьте часовой пояс (по умолчанию `Europe/Chisinau`)

### Mistral API не работает

1. Проверьте `MISTRAL_API_KEY`
2. Проверьте квоту на [console.mistral.ai](https://console.mistral.ai)
3. Попробуйте формат: `стрижка 2026-06-03 15:00`

## Разработка

### Локальное тестирование

```bash
# Установите зависимости
pip install -r requirements.txt

# Установите Vercel CLI
npm i -g vercel

# Запустите локально
vercel dev
```

### Структура кода

- `api/webhook.py` - основной код бота
  - Обработчики команд (`/start`, `/help`, `/list`, `/today`)
  - Обработчики callback-кнопок
  - Интеграция с Mistral AI
  - Cron для напоминаний
  - Serverless handler для Vercel

## Лицензия

MIT

## Автор

[@nazarn1xyy](https://github.com/nazarn1xyy)

## Поддержка

Если возникли проблемы, создайте [Issue](https://github.com/nazarn1xyy/BotReminder/issues)
