"""
FastAPI Server
API + WebSocket + Static Files
"""

import os
import uuid
import shutil
from datetime import datetime
from typing import Optional

from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect,
    UploadFile, File, Form, HTTPException,
    Depends, Header, Request
)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import config
from database import db
from auth import (
    hash_parol, tekshir_parol,
    create_token, verify_token
)
from calculator import hisobla
from userbot import userbot
from scheduler import start_scheduler

# ==================== APP SETUP ====================

app = FastAPI(title="Sevgi Bot API")

# CORS (Netlify uchun)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
os.makedirs(config.UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ==================== STARTUP / SHUTDOWN ====================

@app.on_event("startup")
async def startup():
    """Server ishga tushganda"""
    await db.connect()
    start_scheduler()
    try:
        await userbot.start()
    except Exception as e:
        print(f"⚠️ Userbot ishga tushmadi: {e}")
    print("🚀 Server tayyor!")


@app.on_event("shutdown")
async def shutdown():
    """Server to'xtaganda"""
    await userbot.stop()
    await db.close()


# ==================== PYDANTIC MODELLAR ====================

class VerifyRequest(BaseModel):
    misol: str
    javob: str


class SendMessageRequest(BaseModel):
    to_chat: int
    matn: Optional[str] = None
    rasm_url: Optional[str] = None
    stiker_id: Optional[str] = None
    xabar_turi: str = "text"


class EditMessageRequest(BaseModel):
    msg_id: int
    yangi_matn: str


class SearchRequest(BaseModel):
    username: str


# ==================== AUTH DEPENDENCY ====================

async def get_current_user(authorization: str = Header(None)):
    """JWT token orqali foydalanuvchini olish"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token yo'q")

    token = authorization.replace("Bearer ", "")
    chat_id = verify_token(token)

    if not chat_id:
        raise HTTPException(status_code=401, detail="Token yaroqsiz")

    user = await db.get_user(chat_id)
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")

    return user


# ==================== ASOSIY SAHIFA ====================

@app.get("/")
async def root():
    """Web App HTML"""
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    """Server holati"""
    return {"status": "ok", "vaqt": datetime.now().isoformat()}


# ==================== AUTH ====================

@app.post("/api/auth/verify")
async def verify_parol(data: VerifyRequest, request: Request):
    """
    Kalkulyator natijasi + parol tekshirish
    Format: "26.11100" -> javob=26, parol=11100
    """
    # Javobni ajratish
    qismlar = data.javob.split(".")
    if len(qismlar) != 2:
        return {"success": False, "xato": "Format: javob.parol"}

    misol_javob = qismlar[0].strip()
    parol = qismlar[1].strip()

    # Misolni hisoblash
    togr_javob, xato = hisobla(data.misol)
    if xato:
        return {"success": False, "xato": "Misol xato"}

    # Javob to'g'rimi?
    if str(togr_javob) != misol_javob:
        return {"success": False, "xato": "Javob noto'g'ri"}

    # Parolni qidirish (barcha foydalanuvchilar orasidan)
    # ⚠️ Bu yerda username orqali emas, parol orqali tekshirish kerak
    # Lekin bu xavfsiz emas - bir xil parol ko'p odamda bo'lishi mumkin
    # Shuning uchun bu yerda faqat parolni tekshiramiz

    # Foydalanuvchini topish (kelajakda: login/parol tizimi)
    # Hozircha: parolni barcha userlarda tekshiramiz
    async with db.pool.acquire() as conn:
        users = await conn.fetch(
            "SELECT chat_id, parol_hash FROM users WHERE parol_hash IS NOT NULL"
        )

    topilgan = None
    for u in users:
        if tekshir_parol(parol, u['parol_hash']):
            topilgan = u['chat_id']
            break

    if not topilgan:
        return {"success": False, "xato": "Parol noto'g'ri"}

    # JWT token yaratish
    token = create_token(topilgan)
    await db.save_session(token, topilgan, request.client.host)

    return {"success": True, "token": token, "chat_id": topilgan}


@app.post("/api/auth/logout")
async def logout(authorization: str = Header(None)):
    """Chiqish"""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        await db.delete_session(token)
    return {"success": True}


# ==================== PROFIL ====================

@app.get("/api/profile")
async def get_profile(user=Depends(get_current_user)):
    """Profil ma'lumotlari"""
    return {
        "chat_id": user['chat_id'],
        "ism": user['ism'],
        "familya": user['familya'],
        "username": user['username'],
        "telefon": user['telefon'],
        "profil_rasm": user['profil_rasm'],
        "tungi_rejim": user['tungi_rejim'],
        "sana": user['sana'].isoformat() if user['sana'] else None
    }


@app.post("/api/profile/photo")
async def upload_profile_photo(
        file: UploadFile = File(...),
        user=Depends(get_current_user)
):
    """Profil rasm yuklash"""
    # Fayl tekshirish
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Faqat rasm fayllari")

    # Saqlash
    filename = f"profile_{user['chat_id']}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(config.UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # DB yangilash
    url = f"/static/uploads/{filename}"
    await db.update_profil_rasm(user['chat_id'], url)

    return {"success": True, "url": url}


@app.post("/api/profile/tungi-rejim")
async def toggle_tungi_rejim(user=Depends(get_current_user)):
    """Tungi rejimni almashtirish"""
    yangi = not user['tungi_rejim']
    await db.update_tungi_rejim(user['chat_id'], yangi)
    return {"success": True, "tungi_rejim": yangi}


# ==================== QIDIRUV ====================

@app.post("/api/search")
async def search_user(data: SearchRequest, user=Depends(get_current_user)):
    """Username orqali qidirish"""
    topilgan = await db.get_user_by_username(data.username)

    if not topilgan:
        return {"success": False, "xato": "Topilmadi"}

    if topilgan['chat_id'] == user['chat_id']:
        return {"success": False, "xato": "O'zingizni qidirdingiz"}

    # Maxfiylikni tekshirish
    if topilgan['maxfiylik']:
        return {"success": False, "xato": "Foydalanuvchi maxfiy"}

    # Bloklanganmi?
    bloklangan = await db.is_blocked(topilgan['chat_id'], user['chat_id'])
    if bloklangan:
        return {"success": False, "xato": "Siz bloklangansiz"}

    return {
        "success": True,
        "user": {
            "chat_id": topilgan['chat_id'],
            "ism": topilgan['ism'],
            "familya": topilgan['familya'],
            "username": topilgan['username'],
            "profil_rasm": topilgan['profil_rasm'],
            "oxirgi_faollik": topilgan['oxirgi_faollik'].isoformat()
            if topilgan['oxirgi_faollik'] else None
        }
    }


# ==================== CHAT ====================

@app.get("/api/chats")
async def get_chats(user=Depends(get_current_user)):
    """Chat ro'yxati (oxirgi xabar yuborilganlar)"""
    async with db.pool.acquire() as conn:
        chats = await conn.fetch("""
                                 SELECT DISTINCT CASE
                                                     WHEN from_chat = $1 THEN to_chat
                                                     ELSE from_chat
                                                     END AS chat_id
                                 FROM messages
                                 WHERE (from_chat = $1 OR to_chat = $1)
                                   AND ochirilgan = FALSE
                                 ORDER BY chat_id
                                 """, user['chat_id'])

    natija = []
    for c in chats:
        u = await db.get_user(c['chat_id'])
        if not u or u['maxfiylik']:
            continue

        # Oxirgi xabar
        async with db.pool.acquire() as conn:
            last = await conn.fetchrow("""
                                       SELECT *
                                       FROM messages
                                       WHERE (from_chat = $1 AND to_chat = $2)
                                          OR (from_chat = $2 AND to_chat = $1)
                                           AND ochirilgan = FALSE
                                       ORDER BY vaqt DESC LIMIT 1
                                       """, user['chat_id'], c['chat_id'])

        natija.append({
            "chat_id": u['chat_id'],
            "ism": u['ism'],
            "familya": u['familya'],
            "username": u['username'],
            "profil_rasm": u['profil_rasm'],
            "oxirgi_xabar": last['matn'] if last else "",
            "oxirgi_vaqt": last['vaqt'].isoformat() if last else None,
            "kurilgan": last['kurilgan'] if last else True
        })

    # Oxirgi vaqt bo'yicha tartiblash
    natija.sort(key=lambda x: x['oxirgi_vaqt'] or "", reverse=True)
    return {"chats": natija}


@app.get("/api/messages/{chat_id}")
async def get_messages(
        chat_id: int,
        limit: int = 50,
        offset: int = 0,
        user=Depends(get_current_user)
):
    """Chatdagi xabarlar"""
    # O'qilgan deb belgilash
    await db.mark_as_read(chat_id, user['chat_id'])

    xabarlar = await db.get_messages(user['chat_id'], chat_id, limit, offset)

    return {
        "messages": [{
            "id": m['id'],
            "from_chat": m['from_chat'],
            "to_chat": m['to_chat'],
            "matn": m['matn'],
            "rasm_url": m['rasm_url'],
            "stiker_id": m['stiker_id'],
            "xabar_turi": m['xabar_turi'],
            "tahrirlangan": m['tahrirlangan'],
            "kurilgan": m['kurilgan'],
            "vaqt": m['vaqt'].isoformat(),
            "ozimniki": m['from_chat'] == user['chat_id']
        } for m in xabarlar]
    }


@app.post("/api/messages/send")
async def send_message(
        data: SendMessageRequest,
        user=Depends(get_current_user)
):
    """Xabar yuborish"""
    # Bloklanganmi?
    if await db.is_blocked(data.to_chat, user['chat_id']):
        raise HTTPException(403, "Siz bloklangansiz")

    # Maxfiylikni tekshirish
    qabul = await db.get_user(data.to_chat)
    if not qabul or qabul['maxfiylik']:
        raise HTTPException(404, "Foydalanuvchi mavjud emas")

    # Saqlash
    result = await db.add_message(
        user['chat_id'],
        data.to_chat,
        data.matn,
        data.rasm_url,
        data.stiker_id,
        data.xabar_turi
    )

    # WebSocket orqali yuborish
    await manager.send_to(data.to_chat, {
        "type": "new_message",
        "message": {
            "id": result['id'],
            "from_chat": user['chat_id'],
            "to_chat": data.to_chat,
            "matn": data.matn,
            "rasm_url": data.rasm_url,
            "stiker_id": data.stiker_id,
            "xabar_turi": data.xabar_turi,
            "vaqt": datetime.now().isoformat(),
            "ozimniki": False
        }
    })

    return {"success": True, "id": result['id']}


@app.delete("/api/messages/{msg_id}")
async def delete_message(msg_id: int, user=Depends(get_current_user)):
    """Xabarni o'chirish"""
    result = await db.delete_message(msg_id, user['chat_id'])
    if not result:
        raise HTTPException(404, "Xabar topilmadi")

    # Userbot orqali Telegramdan ham o'chirish
    try:
        await userbot.delete_messages(result['to_chat'], [msg_id])
    except Exception:
        pass

    # WebSocket orqali xabar berish
    await manager.send_to(result['to_chat'], {
        "type": "message_deleted",
        "msg_id": msg_id
    })

    return {"success": True}


@app.put("/api/messages/{msg_id}")
async def edit_message(
        msg_id: int,
        data: EditMessageRequest,
        user=Depends(get_current_user)
):
    """Xabarni tahrirlash"""
    result = await db.edit_message(msg_id, user['chat_id'], data.yangi_matn)
    if not result:
        raise HTTPException(404, "Xabar topilmadi")

    await manager.send_to(result['to_chat'], {
        "type": "message_edited",
        "msg_id": msg_id,
        "yangi_matn": data.yangi_matn
    })

    return {"success": True}


# ==================== RASMLAR ====================

@app.get("/api/photos")
async def get_photos(user=Depends(get_current_user)):
    """Foydalanuvchi rasmlarini olish"""
    rasmlar = await db.get_photos(user['chat_id'])
    return {
        "photos": [{
            "id": p['id'],
            "url": p['rasm_url'],
            "nom": p['nom'],
            "vaqt": p['vaqt'].isoformat()
        } for p in rasmlar],
        "limit": config.MAX_PHOTOS_PER_USER
    }


@app.post("/api/photos")
async def upload_photo(
        file: UploadFile = File(...),
        nom: str = Form(""),
        user=Depends(get_current_user)
):
    """Rasm yuklash (20 ta limit)"""
    # Limitni tekshirish
    mavjud = await db.get_photos(user['chat_id'])
    if len(mavjud) >= config.MAX_PHOTOS_PER_USER:
        raise HTTPException(400, f"Limit: {config.MAX_PHOTOS_PER_USER} ta rasm")

    # Fayl tekshirish
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Faqat rasm fayllari")

    # Saqlash
    filename = f"photo_{user['chat_id']}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(config.UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    url = f"/static/uploads/{filename}"
    result = await db.add_photo(user['chat_id'], url, nom)

    return {"success": True, "id": result['id'], "url": url}


@app.delete("/api/photos/{photo_id}")
async def delete_photo(photo_id: int, user=Depends(get_current_user)):
    """Rasmni o'chirish"""
    result = await db.delete_photo(photo_id, user['chat_id'])
    if not result:
        raise HTTPException(404, "Rasm topilmadi")

    # Faylni o'chirish
    try:
        filepath = result['rasm_url'].replace("/static/", "static/")
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception:
        pass

    return {"success": True}


# ==================== BLOKLAR ====================

@app.post("/api/block/{chat_id}")
async def block_user(chat_id: int, user=Depends(get_current_user)):
    """Foydalanuvchini bloklash"""
    await db.block_user(user['chat_id'], chat_id)
    return {"success": True}


@app.delete("/api/block/{chat_id}")
async def unblock_user(chat_id: int, user=Depends(get_current_user)):
    """Blokdan chiqarish"""
    await db.unblock_user(user['chat_id'], chat_id)
    return {"success": True}


@app.get("/api/blocked")
async def get_blocked(user=Depends(get_current_user)):
    """Bloklanganlar ro'yxati"""
    bloklar = await db.get_blocked_list(user['chat_id'])
    return {
        "blocked": [{
            "chat_id": b['blocked_chat'],
            "ism": b['ism'],
            "familya": b['familya'],
            "username": b['username']
        } for b in bloklar]
    }


# ==================== KALKULYATOR ====================

@app.post("/api/calculate")
async def calculate(data: dict):
    """Kalkulyator API"""
    ifoda = data.get("ifoda", "")
    natija, xato = hisobla(ifoda)

    if xato:
        return {"success": False, "xato": xato}

    return {"success": True, "natija": natija}


# ==================== WEBSOCKET ====================

class ConnectionManager:
    """WebSocket ulanishlar boshqaruvi"""

    def __init__(self):
        self.connections: dict[int, list[WebSocket]] = {}

    async def connect(self, chat_id: int, websocket: WebSocket):
        await websocket.accept()
        if chat_id not in self.connections:
            self.connections[chat_id] = []
        self.connections[chat_id].append(websocket)
        print(f"🔌 WebSocket ulandi: {chat_id}")

    def disconnect(self, chat_id: int, websocket: WebSocket):
        if chat_id in self.connections:
            if websocket in self.connections[chat_id]:
                self.connections[chat_id].remove(websocket)
            if not self.connections[chat_id]:
                del self.connections[chat_id]
        print(f"🔌 WebSocket uzildi: {chat_id}")

    async def send_to(self, chat_id: int, data: dict):
        """Foydalanuvchiga xabar yuborish"""
        if chat_id not in self.connections:
            return

        for ws in self.connections[chat_id][:]:
            try:
                await ws.send_json(data)
            except Exception:
                self.connections[chat_id].remove(ws)


manager = ConnectionManager()


@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """WebSocket ulanish"""
    chat_id = verify_token(token)
    if not chat_id:
        await websocket.close(code=4001)
        return

    await manager.connect(chat_id, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            turi = data.get("type")

            if turi == "typing":
                # "Yozayapti..." ni qabul qiluvchiga yuborish
                await manager.send_to(data["to_chat"], {
                    "type": "typing",
                    "from_chat": chat_id
                })

            elif turi == "read":
                # O'qilgan deb belgilash
                await db.mark_as_read(data["from_chat"], chat_id)
                await manager.send_to(data["from_chat"], {
                    "type": "read",
                    "by_chat": chat_id
                })

            elif turi == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(chat_id, websocket)
    except Exception as e:
        print(f"❌ WebSocket xato: {e}")
        manager.disconnect(chat_id, websocket)


# ==================== RUN ====================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False
    )