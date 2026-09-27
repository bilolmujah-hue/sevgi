"""
Autentifikatsiya: JWT, parol hash
passlib o'rniga to'g'ridan-to'g'ri bcrypt
"""

import uuid
import bcrypt
from jose import jwt, JWTError
from datetime import datetime, timedelta
from config import config


def hash_parol(parol: str) -> str:
    """Parolni hash qilish"""
    try:
        parol_bytes = parol.encode('utf-8')[:72]
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(parol_bytes, salt)
        return hashed.decode('utf-8')
    except Exception as e:
        print(f"❌ hash_parol xatosi: {e}")
        return ""


def tekshir_parol(parol: str, hash_: str) -> bool:
    """Parolni tekshirish"""
    try:
        if not hash_:
            return False
        parol_bytes = parol.encode('utf-8')[:72]
        hash_bytes = hash_.encode('utf-8')
        return bcrypt.checkpw(parol_bytes, hash_bytes)
    except Exception as e:
        print(f"❌ tekshir_parol xatosi: {e}")
        return False


def create_token(chat_id: int) -> str:
    """JWT token yaratish (unikal — har safar yangi jti)"""
    expire = datetime.utcnow() + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
    payload = {
        "chat_id": chat_id,
        "exp": expire,
        "jti": uuid.uuid4().hex  # ⚡ Har safar unikal
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
    except Exception:
        return None
