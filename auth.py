"""
Autentifikatsiya: JWT, parol hash
"""

from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from config import config

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_parol(parol: str) -> str:
    """Parolni hash qilish"""
    return pwd_context.hash(parol)


def tekshir_parol(parol: str, hash_: str) -> bool:
    """Parolni tekshirish"""
    try:
        return pwd_context.verify(parol, hash_)
    except Exception:
        return False


def create_token(chat_id: int) -> str:
    """JWT token yaratish"""
    expire = datetime.utcnow() + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
    payload = {
        "chat_id": chat_id,
        "exp": expire
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def verify_token(token: str):
    """JWT tokenni tekshirish"""
    try:
        payload = jwt.decode(
            token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM]
        )
        return payload.get("chat_id")
    except JWTError:
        return None