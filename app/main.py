from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
import os
import logging
import json
import string
import random

from . import models, schemas, auth, database, cashe
from .cashe import get_cached_url, set_cached_url, get_cached_stats, set_cached_stats, delete_cached_url, \
    delete_cached_stats, datetime_handler

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


# Вспомогательные функции (перенесены из utils.py)
def generate_short_code(length: int = 6) -> str:
    """Генерирует случайный короткий код из букв и цифр."""
    characters = string.ascii_letters + string.digits  # a-z, A-Z, 0-9
    return ''.join(random.choice(characters) for _ in range(length))


# Зависимость для получения сессии базы данных
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Эндпоинт для создания короткой ссылки
@app.post("/links/shorten", response_model=schemas.LinkResponse)
def create_short_link(
        link: schemas.LinkCreate,
        db: Session = Depends(get_db),
        current_user: Optional[models.User] = Depends(auth.get_current_active_user)
):
    try:
        logger.info(
            f"Received request to shorten URL: {link.original_url}, custom_alias: {link.custom_alias}, expires_at: {link.expires_at}")

        if link.custom_alias:
            existing_link = db.query(models.Link).filter(
                models.Link.custom_alias == link.custom_alias
            ).first()
            if existing_link:
                logger.error(f"Custom alias {link.custom_alias} already exists")
                raise HTTPException(status_code=400, detail="Пользовательский алиас уже существует")
            short_code = link.custom_alias
        else:
            short_code = generate_short_code()
            while db.query(models.Link).filter(models.Link.short_code == short_code).first():
                short_code = generate_short_code()
            logger.info(f"Generated short code: {short_code}")

        if not link.expires_at:
            default_days = int(os.getenv("DEFAULT_LINK_EXPIRY_DAYS", "30"))
            link.expires_at = datetime.utcnow() + timedelta(days=default_days)
            logger.info(f"Set default expiration: {link.expires_at}")
        elif link.expires_at.replace(tzinfo=None) <= datetime.utcnow():
            logger.error(f"Expiration date {link.expires_at} is in the past")
            raise HTTPException(status_code=400, detail="Дата истечения должна быть в будущем")

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
        logger.info(f"Created link with short_code: {short_code}, user_id: {db_link.user_id}")

        set_cached_url(short_code, str(link.original_url))
        logger.info(f"Cached URL for {short_code}")

        return schemas.LinkResponse(
            id=db_link.id,
            original_url=db_link.original_url,
            short_code=db_link.short_code,
            custom_alias=db_link.custom_alias,
            created_at=db_link.created_at,
            last_accessed=db_link.last_accessed,
            access_count=db_link.access_count,
            user_id=db_link.user_id,
            expires_at=db_link.expires_at
        )
    except HTTPException as e:
        logger.error(f"HTTP error in create_short_link: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_short_link: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Эндпоинт для перенаправления по короткой ссылке
@app.get("/{short_code}")
async def redirect_to_url(
        short_code: str,
        request: Request,
        db: Session = Depends(get_db)
):
    try:
        logger.info(f"Received redirect request for short_code: {short_code}")

        # Проверяем кэш
        cached_url = get_cached_url(short_code)
        logger.info(f"Cache check result for {short_code}: {cached_url}")

        # Проверяем базу данных
        link = db.query(models.Link).filter(models.Link.short_code == short_code).first()
        if not link:
            logger.error(f"Link {short_code} not found in database")
            raise HTTPException(status_code=404, detail="Ссылка не найдена")
        logger.info(f"Found link in database: {link.original_url}, current access_count: {link.access_count}")

        # Проверяем срок действия
        if link.expires_at and link.expires_at.replace(tzinfo=None) < datetime.utcnow():
            logger.warning(f"Link {short_code} has expired at {link.expires_at}")
            delete_cached_url(short_code)
            delete_cached_stats(short_code)
            logger.info(f"Cleared cache for expired link {short_code}")
            raise HTTPException(status_code=410, detail="Ссылка истекла")

        # Обновляем статистику
        try:
            link.last_accessed = datetime.utcnow()
            link.access_count += 1
            db.commit()
            logger.info(f"Successfully updated stats for {short_code}: access_count={link.access_count}, last_accessed={link.last_accessed}")
        except Exception as e:
            logger.error(f"Error updating stats: {str(e)}")
            db.rollback()
            raise

        # Если URL нет в кэше, добавляем его
        if not cached_url:
            set_cached_url(short_code, str(link.original_url))
            logger.info(f"Cached URL for {short_code}")

        return RedirectResponse(url=str(link.original_url))
    except HTTPException as e:
        logger.error(f"HTTP error in redirect_to_url: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in redirect_to_url: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Остальные эндпоинты (регистрация, авторизация, статистика и т.д.)
@app.post("/register", response_model=schemas.UserResponse)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    logger.info(f"Received registration request for email: {user.email}")
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        logger.error(f"Email {user.email} already registered")
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    logger.info(f"Successfully registered user: {user.email}")
    return schemas.UserResponse(
        id=db_user.id,
        email=db_user.email,
        is_active=db_user.is_active,
        created_at=db_user.created_at
    )


@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(get_db)
):
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


@app.get("/links/{short_code}/stats", response_model=schemas.LinkStats)
def get_link_stats(short_code: str, db: Session = Depends(get_db)):
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

    set_cached_stats(short_code, stats.dict())
    return stats


@app.put("/links/{short_code}", response_model=schemas.LinkResponse)
def update_link(
        short_code: str,
        link_update: schemas.LinkUpdate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    link = db.query(models.Link).filter(models.Link.short_code == short_code).first()
    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")
    if link.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет прав для обновления этой ссылки")

    if link_update.original_url:
        link.original_url = str(link_update.original_url)
    if link_update.expires_at:
        if link_update.expires_at.replace(tzinfo=None) <= datetime.utcnow():
            raise HTTPException(status_code=400, detail="Дата истечения должна быть в будущем")
        link.expires_at = link_update.expires_at

    db.commit()
    db.refresh(link)

    delete_cached_url(short_code)
    delete_cached_stats(short_code)
    set_cached_url(short_code, str(link.original_url))

    return schemas.LinkResponse(
        id=link.id,
        original_url=link.original_url,
        short_code=link.short_code,
        custom_alias=link.custom_alias,
        created_at=link.created_at,
        last_accessed=link.last_accessed,
        access_count=link.access_count,
        user_id=link.user_id,
        expires_at=link.expires_at
    )


@app.delete("/links/{short_code}")
def delete_link(
        short_code: str,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_active_user)
):
    link = db.query(models.Link).filter(models.Link.short_code == short_code).first()
    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")
    if link.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет прав для удаления этой ссылки")

    db.delete(link)
    db.commit()

    delete_cached_url(short_code)
    delete_cached_stats(short_code)

    return {"message": "Ссылка успешно удалена"}
