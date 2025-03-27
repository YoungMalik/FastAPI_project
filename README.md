# URL Shortener Service

Сервис для создания коротких ссылок с использованием FastAPI, PostgreSQL и Redis.

## Описание

Этот сервис позволяет создавать короткие ссылки из длинных URL-адресов. Основные возможности:
- Создание коротких ссылок
- Автоматическое перенаправление
- Статистика переходов
- Пользовательская авторизация
- Кэширование для оптимизации производительности
- Настраиваемое время жизни ссылок

## Технологии

- FastAPI
- PostgreSQL
- Redis
- Docker
- Docker Compose
- SQLAlchemy
- Pydantic
- JWT Authentication

## API Endpoints

### Аутентификация

#### Регистрация пользователя
```http
POST /register
Content-Type: application/json

{
    "email": "user@example.com",
    "password": "your_password"
}
```

#### Получение токена доступа
```http
POST /token
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=your_password
```

### Ссылки

#### Создание короткой ссылки
```http
POST /links/shorten
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{
    "original_url": "https://example.com/very/long/url",
    "custom_alias": "my-custom-link",  // опционально
    "expires_at": "2024-04-27T09:33:05.982Z"  // опционально
}
```

#### Получение статистики по ссылке
```http
GET /links/{short_code}/stats
```

#### Обновление ссылки
```http
PUT /links/{short_code}
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{
    "original_url": "https://example.com/new/url",
    "expires_at": "2024-05-27T09:33:05.982Z"
}
```

#### Удаление ссылки
```http
DELETE /links/{short_code}
Authorization: Bearer YOUR_ACCESS_TOKEN
```

#### Переход по короткой ссылке
```http
GET /{short_code}
```

## Структура базы данных

### Таблица users
- id (Integer, Primary Key)
- email (String, Unique)
- hashed_password (String)
- is_active (Boolean)
- created_at (DateTime)

### Таблица links
- id (Integer, Primary Key)
- original_url (String)
- short_code (String, Unique)
- custom_alias (String, Unique, Nullable)
- created_at (DateTime)
- expires_at (DateTime, Nullable)
- last_accessed (DateTime, Nullable)
- access_count (Integer)
- user_id (Integer, Foreign Key)

## Установка и запуск

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd <repository-name>
```

2. Создайте файл .env в корневой директории проекта:
```env
DATABASE_URL=postgresql://postgres:postgres@db:5432/url_shortener
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DEFAULT_LINK_EXPIRY_DAYS=30
```

3. Запустите приложение с помощью Docker Compose:
```bash
docker-compose up --build
```

Сервис будет доступен по адресу: http://localhost:8080

## API Документация

После запуска сервиса, документация API доступна по следующим адресам:
- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc

## Примеры использования

### 1. Регистрация пользователя
```bash
curl -X POST "http://localhost:8080/register" \
-H "Content-Type: application/json" \
-d '{
    "email": "user@example.com",
    "password": "your_password"
}'
```

### 2. Получение токена
```bash
curl -X POST "http://localhost:8080/token" \
-H "Content-Type: application/x-www-form-urlencoded" \
-d "username=user@example.com&password=your_password"
```

### 3. Создание короткой ссылки
```bash
curl -X POST "http://localhost:8080/links/shorten" \
-H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
-H "Content-Type: application/json" \
-d '{
    "original_url": "https://example.com/very/long/url"
}'
```

### 4. Проверка статистики
```bash
curl -X GET "http://localhost:8080/links/{short_code}/stats"
```

## Особенности реализации

- Использование Redis для кэширования URL и статистики
- JWT аутентификация для защиты API
- Автоматическое обновление статистики при переходах
- Поддержка пользовательских алиасов
- Настраиваемое время жизни ссылок
- Логирование всех операций

## Требования

- Docker
- Docker Compose
- Python 3.9+
- PostgreSQL 15
- Redis 7 
