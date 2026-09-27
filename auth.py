"""
Autentifikatsiya: JWT, parol hash
passlib o'rniga to'g'ridan-to'g'ri bcrypt
"""

import bcrypt
from jose import jwt, JWTError
from datetime import datetime, timedelta
from config import config


def hash_parol(parol: str) -> str:
    """Parolni hash qilish"""
    # Parolni bytes ga aylantirish, 72 baytdan qisqartirish
    parol_bytes = parol.encode('utf-8')[:72]
    # Salt generatsiya qilish
    salt = bcrypt.gensalt()
    # Hash qilish
    hashed = bcrypt.hashpw(parol_bytes, salt)
    return hashed.decode('utf-8')


def tekshir_parol(parol: str, hash_: str) -> bool:
    """Parolni tekshirish"""
    try:
        parol_bytes = parol.encode('utf-8')[:72]
        hash_bytes = hash_.encode('utf-8')
        return bcrypt.checkpw(parol_bytes, hash_bytes)
    except Exception as e:
        print(f"❌ Parol tekshirishda xato: {e}")
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