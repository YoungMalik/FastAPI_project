from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import random
import string
from typing import Optional
from . import models, schemas, auth
from .database import engine, get_db
from .cashe import (
    get_cached_url, set_cached_url, delete_cached_url,
    get_cached_stats, set_cached_stats, delete_cached_stats
)
import os
from dotenv import load_dotenv

load_dotenv()

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="URL Shortener API")


def generate_short_code(length: int = 6) -> str:
    """Сгенерировать случайный короткий код"""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


@app.post("/register", response_model=schemas.User)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Регистрация нового пользователя"""
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(get_db)
):
    """Получение токена доступа"""
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/links/shorten", response_model=schemas.Link)
def create_short_link(
        link: schemas.LinkCreate,
        db: Session = Depends(get_db),
        current_user: Optional[models.User] = Depends(auth.get_current_active_user)
):
    """Создание короткой ссылки"""
    # Проверка уникальности пользовательского алиаса
    if link.custom_alias:
        existing_link = db.query(models.Link).filter(
            models.Link.custom_alias == link.custom_alias
        ).first()
        if existing_link:
            raise HTTPException(status_code=400, detail="Пользовательский алиас уже существует")
        short_code = link.custom_alias
    else:
        short_code = generate_short_code()
        while db.query(models.Link).filter(models.Link.short_code == short_code).first():
            short_code = generate_short_code()

    # Установка срока действия по умолчанию
    if not link.expires_at:
        default_days = int(os.getenv("DEFAULT_LINK_EXPIRY_DAYS", "30"))
        link.expires_at = datetime.utcnow() + timedelta(days=default_days)

    db_link = models.Link(
        original_url=str(link.original_url),
        short_code=short_code,
        custom_alias=link.custom_alias,
        expires_at=link.expires_at,
        user_id=current_user.id if current_user else None
    )
    db.add(db_link)
    db.commit()
    db.refresh(db_link)

    # Кэширование URL
    set_cached_url(short_code, str(link.original_url))
    return db_link


@app.get("/{short_code}")
async def redirect_to_url(
        short_code: str,
        request: Request,
        db: Session = Depends(get_db)
):
    """Перенаправление на оригинальный URL"""
    # Попытка получить из кэша
    cached_url = get_cached_url(short_code)
    if cached_url:
        link = db.query(models.Link).filter(models.Link.short_code == short_code).first()
        if link and (not link.expires_at or link.expires_at > datetime.utcnow()):
            link.last_accessed = datetime.utcnow()
            link.access_count += 1
            db.commit()
            return RedirectResponse(url=cached_url)

    # Если нет в кэше, получаем из базы данных
    link = db.query(models.Link).filter(models.Link.short_code == short_code).first()
    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    if link.expires_at and link.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Ссылка истекла")

    link.last_accessed = datetime.utcnow()
    link.access_count += 1
    db.commit()

    # Кэширование URL
    set_cached_url(short_code, str(link.original_url))
    return RedirectResponse(url=str(link.original_url))


@app.get("/links/{short_code}/stats", response_model=schemas.LinkStats)
def get_link_stats(short_code: str, db: Session = Depends(get_db)):
    """Получение статистики по ссылке"""
    # Попытка получить из кэша
    cached_stats = get_cached_stats(short_code)
    if cached_stats:
        return cached_stats

    link = db.query(models.Link).filter(models.Link.short_code == short_code).first()
    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    stats = schemas.LinkStats(
        original_url=link.original_url,
        created_at=link.created_at,
        last_accessed=link.last_accessed,
        access_count=link.access_count,
        expires_at=link.expires_at
    )

    # Кэширование статистики
    set_cached_stats(short_code, stats.dict())
    return stats


@app.delete("/links/{short_code}")
def delete_link(
        short_code: str,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    """Удаление ссылки"""
    link = db.query(models.Link).filter(models.Link.short_code == short_code).first()
    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    if link.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    db.delete(link)
    db.commit()

    # Очистка кэша
    delete_cached_url(short_code)
    delete_cached_stats(short_code)
    return {"message": "Ссылка успешно удалена"}


@app.put("/links/{short_code}", response_model=schemas.Link)
def update_link(
        short_code: str,
        link_update: schemas.LinkCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    """Обновление ссылки"""
    link = db.query(models.Link).filter(models.Link.short_code == short_code).first()
    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    if link.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    # Обновление полей
    link.original_url = str(link_update.original_url)
    if link_update.expires_at:
        link.expires_at = link_update.expires_at

    db.commit()
    db.refresh(link)

    # Обновление кэша
    set_cached_url(short_code, str(link_update.original_url))
    return link


@app.get("/links/search")
def search_link(
        original_url: str,
        db: Session = Depends(get_db)
):
    """Поиск ссылки по оригинальному URL"""
    link = db.query(models.Link).filter(models.Link.original_url == original_url).first()
    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")
    return link