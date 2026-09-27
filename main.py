"""
FastAPI Server
API + WebSocket + Static Files + Telegram Bot + Userbot
"""

import os
import uuid
import shutil
import asyncio
from datetime import datetime, date
from typing import Optional
from contextlib import asynccontextmanager

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

from bot import bot as tg_bot, dp as tg_dp


# ==================== LIFESPAN ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Server ishga tushmoqda...")

    await db.connect()
    start_scheduler()

    try:
        await userbot.start()
    except Exception as e:
        print(f"⚠️ Userbot ishga tushmadi: {e}")

    async def run_bot():
        try:
            print("🤖 Bot ishga tushdi...")
            await tg_dp.start_polling(tg_bot)
        except Exception as e:
            print(f"❌ Bot xatosi: {e}")

    bot_task = asyncio.create_task(run_bot())

    print("🚀 Server tayyor!")
    yield

    print("🛑 Server to'xtamoqda...")
    bot_task.cancel()
    try:
        await bot_task
    except asyncio.CancelledError:
        pass

    try:
        await tg_bot.session.close()
    except Exception:
        pass

    try:
        await userbot.stop()
    except Exception:
        pass

    await db.close()
    print("👋 Server to'xtadi")


# ==================== APP SETUP ====================

app = FastAPI(title="Sevgi Bot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(config.UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ==================== MODELLAR ====================

class VerifyRequest(BaseModel):
    misol: str = ""
    javob: str


class SendMessageRequest(BaseModel):
    to_chat: int
    matn: Optional[str] = None
    rasm_url: Optional[str] = None
    ovoz_url: Optional[str] = None
    ovoz_davomiyligi: Optional[int] = None
    stiker_id: Optional[str] = None
    xabar_turi: str = "text"
    reply_to_id: Optional[int] = None


class EditMessageRequest(BaseModel):
    msg_id: int
    yangi_matn: str


class SearchRequest(BaseModel):
    username: str


class ReactionRequest(BaseModel):
    msg_id: int
    emoji: str


class ProfileUpdateRequest(BaseModel):
    ism: Optional[str] = None
    familya: Optional[str] = None
    tugilgan_kun: Optional[str] = None
    bio: Optional[str] = None


# ==================== AUTH DEPENDENCY ====================

async def get_current_user(authorization: str = Header(None)):
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


# ==================== ASOSIY ====================

@app.get("/")
async def root():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return JSONResponse(status_code=404, content={"xato": "index.html topilmadi"})


@app.get("/health")
async def health():
    return {"status": "ok", "vaqt": datetime.now().isoformat()}


# ==================== AUTH ====================

@app.post("/api/auth/verify")
async def verify_parol(data: VerifyRequest, request: Request):
    """Faqat parol tekshirish"""
    try:
        javob = data.javob.strip()

        if "." in javob:
            qismlar = javob.split(".")
            if len(qismlar) != 2:
                return {"success": False, "xato": "Format xato"}
            parol = qismlar[1].strip()
        else:
            parol = javob

        if not parol.isdigit() or len(parol) != 5:
            return {"success": False, "xato": "5 xonalik parol kiriting"}

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

        # ⚡ Eski sessionlarni tozalash
        await db.clear_user_sessions(topilgan)

        token = create_token(topilgan)
        await db.save_session(token, topilgan, request.client.host if request.client else None)

        return {"success": True, "token": token, "chat_id": topilgan}

    except Exception as e:
        print(f"❌ verify_parol xatosi: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "xato": f"Server xatosi: {str(e)}"}


@app.post("/api/auth/logout")
async def logout(authorization: str = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        await db.delete_session(token)
    return {"success": True}


# ==================== PROFIL ====================

@app.get("/api/profile")
async def get_profile(user=Depends(get_current_user)):
    return {
        "chat_id": user['chat_id'],
        "ism": user['ism'],
        "familya": user['familya'],
        "username": user['username'],
        "telefon": user['telefon'],
        "profil_rasm": user['profil_rasm'],
        "tungi_rejim": user['tungi_rejim'],
        "tugilgan_kun": user['tugilgan_kun'].isoformat() if user['tugilgan_kun'] else None,
        "bio": user['bio'],
        "online": user['online'],
        "oxirgi_faollik": user['oxirgi_faollik'].isoformat() if user['oxirgi_faollik'] else None,
        "sana": user['sana'].isoformat() if user['sana'] else None
    }


@app.put("/api/profile")
async def update_profile(data: ProfileUpdateRequest, user=Depends(get_current_user)):
    """Profilni yangilash"""
    try:
        tugilgan_kun = None
        if data.tugilgan_kun:
            try:
                tugilgan_kun = datetime.strptime(data.tugilgan_kun, "%Y-%m-%d").date()
            except ValueError:
                return {"success": False, "xato": "Sana formati YYYY-MM-DD bo'lishi kerak"}

        await db.update_profile(
            user['chat_id'],
            ism=data.ism,
            familya=data.familya,
            tugilgan_kun=tugilgan_kun,
            bio=data.bio
        )
        return {"success": True}
    except Exception as e:
        return {"success": False, "xato": str(e)}


@app.post("/api/profile/photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    """Profil rasm yuklash"""
    try:
        ext = os.path.splitext(file.filename)[1].lower() if file.filename else ".jpg"
        if ext not in config.ALLOWED_EXTENSIONS:
            return {"success": False, "xato": f"Faqat rasm: {', '.join(config.ALLOWED_EXTENSIONS)}"}

        # ⚡ Fayl hajmi tekshirish
        contents = await file.read()
        if len(contents) > config.MAX_PHOTO_SIZE:
            mb = config.MAX_PHOTO_SIZE // 1024 // 1024
            return {"success": False, "xato": f"Rasm juda katta (maks {mb} MB)"}

        filename = f"profile_{user['chat_id']}_{uuid.uuid4().hex[:8]}{ext}"
        filepath = os.path.join(config.UPLOAD_DIR, filename)

        os.makedirs(config.UPLOAD_DIR, exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(contents)

        url = f"/static/uploads/{filename}"
        await db.update_profil_rasm(user['chat_id'], url)

        return {"success": True, "url": url}

    except Exception as e:
        print(f"❌ upload_profile_photo xatosi: {e}")
        return {"success": False, "xato": str(e)}


@app.post("/api/profile/tungi-rejim")
async def toggle_tungi_rejim(user=Depends(get_current_user)):
    yangi = not user['tungi_rejim']
    await db.update_tungi_rejim(user['chat_id'], yangi)
    return {"success": True, "tungi_rejim": yangi}


@app.post("/api/profile/online")
async def set_online(user=Depends(get_current_user)):
    await db.set_online(user['chat_id'], True)
    return {"success": True}


@app.post("/api/profile/offline")
async def set_offline(user=Depends(get_current_user)):
    await db.set_online(user['chat_id'], False)
    return {"success": True}


# ==================== QIDIRUV ====================

@app.post("/api/search")
async def search_user(data: SearchRequest, user=Depends(get_current_user)):
    topilgan = await db.get_user_by_username(data.username)

    if not topilgan:
        return {"success": False, "xato": "Topilmadi"}

    if topilgan['chat_id'] == user['chat_id']:
        return {"success": False, "xato": "O'zingizni qidirdingiz"}

    if topilgan['maxfiylik']:
        return {"success": False, "xato": "Foydalanuvchi maxfiy"}

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
            "online": topilgan['online'],
            "oxirgi_faollik": topilgan['oxirgi_faollik'].isoformat()
                if topilgan['oxirgi_faollik'] else None
        }
    }


# ==================== CHAT ====================

@app.get("/api/chats")
async def get_chats(user=Depends(get_current_user)):
    async with db.pool.acquire() as conn:
        chats = await conn.fetch("""
            SELECT DISTINCT
                CASE 
                    WHEN from_chat = $1 THEN to_chat
                    ELSE from_chat
                END AS chat_id
            FROM messages
            WHERE (from_chat = $1 OR to_chat = $1) AND ochirilgan = FALSE
        """, user['chat_id'])

    natija = []
    for c in chats:
        u = await db.get_user(c['chat_id'])
        if not u or u['maxfiylik']:
            continue

        async with db.pool.acquire() as conn:
            last = await conn.fetchrow("""
                SELECT * FROM messages
                WHERE ((from_chat = $1 AND to_chat = $2)
                    OR (from_chat = $2 AND to_chat = $1))
                  AND ochirilgan = FALSE
                ORDER BY vaqt DESC LIMIT 1
            """, user['chat_id'], c['chat_id'])

        unread = await db.get_unread_count(c['chat_id'], user['chat_id'])

        natija.append({
            "chat_id": u['chat_id'],
            "ism": u['ism'],
            "familya": u['familya'],
            "username": u['username'],
            "profil_rasm": u['profil_rasm'],
            "online": u['online'],
            "oxirgi_faollik": u['oxirgi_faollik'].isoformat() if u['oxirgi_faollik'] else None,
            "oxirgi_xabar": last['matn'] if last else "",
            "oxirgi_vaqt": last['vaqt'].isoformat() if last else None,
            "oxirgi_xabar_turi": last['xabar_turi'] if last else 'text',
            "kurilgan": last['kurilgan'] if last else True,
            "unread_count": unread
        })

    natija.sort(key=lambda x: x['oxirgi_vaqt'] or "", reverse=True)
    return {"chats": natija}


@app.get("/api/messages/{chat_id}")
async def get_messages(
    chat_id: int,
    limit: int = 50,
    offset: int = 0,
    user=Depends(get_current_user)
):
    await db.mark_as_read(chat_id, user['chat_id'])
    xabarlar = await db.get_messages(user['chat_id'], chat_id, limit, offset)

    msg_ids = [m['id'] for m in xabarlar]
    reactions_map = await db.get_reactions_for_messages(msg_ids)

    # Reply ma'lumotlarini olish
    reply_ids = [m['reply_to_id'] for m in xabarlar if m['reply_to_id']]
    reply_map = {}
    if reply_ids:
        async with db.pool.acquire() as conn:
            replies = await conn.fetch(
                "SELECT id, matn, from_chat, xabar_turi FROM messages WHERE id = ANY($1)",
                reply_ids
            )
            for r in replies:
                reply_map[r['id']] = r

    return {
        "messages": [{
            "id": m['id'],
            "from_chat": m['from_chat'],
            "to_chat": m['to_chat'],
            "matn": m['matn'],
            "rasm_url": m['rasm_url'],
            "ovoz_url": m['ovoz_url'],
            "ovoz_davomiyligi": m['ovoz_davomiyligi'],
            "stiker_id": m['stiker_id'],
            "xabar_turi": m['xabar_turi'],
            "tahrirlangan": m['tahrirlangan'],
            "kurilgan": m['kurilgan'],
            "vaqt": m['vaqt'].isoformat(),
            "ozimniki": m['from_chat'] == user['chat_id'],
            "reactions": reactions_map.get(m['id'], []),
            "reply_to": ({
                "id": m['reply_to_id'],
                "text": reply_map.get(m['reply_to_id'], {}).get('matn', ''),
                "xabar_turi": reply_map.get(m['reply_to_id'], {}).get('xabar_turi', 'text'),
                "ozimniki": reply_map.get(m['reply_to_id'], {}).get('from_chat') == user['chat_id']
            } if m['reply_to_id'] and m['reply_to_id'] in reply_map else None)
        } for m in xabarlar]
    }


@app.post("/api/messages/send")
async def send_message(
    data: SendMessageRequest,
    user=Depends(get_current_user)
):
    if await db.is_blocked(data.to_chat, user['chat_id']):
        raise HTTPException(403, "Siz bloklangansiz")

    qabul = await db.get_user(data.to_chat)
    if not qabul or qabul['maxfiylik']:
        raise HTTPException(404, "Foydalanuvchi mavjud emas")

    result = await db.add_message(
        user['chat_id'],
        data.to_chat,
        data.matn,
        data.rasm_url,
        data.stiker_id,
        data.xabar_turi,
        data.ovoz_url,
        data.ovoz_davomiyligi,
        data.reply_to_id
    )

    # Reply ma'lumoti
    reply_data = None
    if data.reply_to_id:
        reply_msg = await db.get_message_by_id(data.reply_to_id)
        if reply_msg:
            reply_data = {
                "id": reply_msg['id'],
                "text": reply_msg['matn'] or '',
                "xabar_turi": reply_msg['xabar_turi'],
                "ozimniki": reply_msg['from_chat'] == data.to_chat
            }

    await manager.send_to(data.to_chat, {
        "type": "new_message",
        "message": {
            "id": result['id'],
            "from_chat": user['chat_id'],
            "to_chat": data.to_chat,
            "matn": data.matn,
            "rasm_url": data.rasm_url,
            "ovoz_url": data.ovoz_url,
            "ovoz_davomiyligi": data.ovoz_davomiyligi,
            "stiker_id": data.stiker_id,
            "xabar_turi": data.xabar_turi,
            "vaqt": datetime.now().isoformat(),
            "ozimniki": False,
            "kurilgan": False,
            "reactions": [],
            "reply_to": reply_data
        }
    })

    return {"success": True, "id": result['id']}


@app.post("/api/messages/upload")
async def upload_message_file(
    file: UploadFile = File(...),
    turi: str = Form("image"),
    user=Depends(get_current_user)
):
    """Rasm yoki ovoz yuklash"""
    try:
        ext = os.path.splitext(file.filename)[1].lower() if file.filename else ".bin"
        
        if turi == "image":
            if ext not in config.ALLOWED_EXTENSIONS:
                return {"success": False, "xato": "Faqat rasm fayllari"}
            prefix = "img"
        elif turi == "voice":
            prefix = "voice"
            if not ext or ext == ".bin":
                ext = ".webm"
        else:
            prefix = "file"
        
        contents = await file.read()
        if len(contents) > config.MAX_PHOTO_SIZE * 2:
            return {"success": False, "xato": "Fayl juda katta"}

        filename = f"{prefix}_{user['chat_id']}_{uuid.uuid4().hex[:8]}{ext}"
        filepath = os.path.join(config.UPLOAD_DIR, filename)

        os.makedirs(config.UPLOAD_DIR, exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(contents)

        url = f"/static/uploads/{filename}"
        return {"success": True, "url": url}

    except Exception as e:
        print(f"❌ upload xatosi: {e}")
        return {"success": False, "xato": str(e)}


@app.delete("/api/messages/{msg_id}")
async def delete_message(msg_id: int, user=Depends(get_current_user)):
    result = await db.delete_message(msg_id, user['chat_id'])
    if not result:
        raise HTTPException(404, "Xabar topilmadi")

    try:
        await userbot.delete_messages(result['to_chat'], [msg_id])
    except Exception:
        pass

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
    result = await db.edit_message(msg_id, user['chat_id'], data.yangi_matn)
    if not result:
        raise HTTPException(404, "Xabar topilmadi")

    await manager.send_to(result['to_chat'], {
        "type": "message_edited",
        "msg_id": msg_id,
        "yangi_matn": data.yangi_matn
    })

    return {"success": True}


# ==================== REACTIONS ====================

@app.post("/api/messages/react")
async def add_reaction(data: ReactionRequest, user=Depends(get_current_user)):
    await db.add_reaction(data.msg_id, user['chat_id'], data.emoji)
    reactions = await db.get_reactions(data.msg_id)
    
    msg = await db.get_message_by_id(data.msg_id)
    
    if msg:
        target = msg['from_chat'] if msg['from_chat'] != user['chat_id'] else msg['to_chat']
        await manager.send_to(target, {
            "type": "reaction_added",
            "msg_id": data.msg_id,
            "emoji": data.emoji,
            "chat_id": user['chat_id'],
            "reactions": [{"emoji": r['emoji'], "count": r['count']} for r in reactions]
        })
    
    return {
        "success": True,
        "reactions": [{"emoji": r['emoji'], "count": r['count']} for r in reactions]
    }


@app.delete("/api/messages/react")
async def remove_reaction(msg_id: int, emoji: str, user=Depends(get_current_user)):
    await db.remove_reaction(msg_id, user['chat_id'], emoji)
    reactions = await db.get_reactions(msg_id)
    
    msg = await db.get_message_by_id(msg_id)
    
    if msg:
        target = msg['from_chat'] if msg['from_chat'] != user['chat_id'] else msg['to_chat']
        await manager.send_to(target, {
            "type": "reaction_removed",
            "msg_id": msg_id,
            "emoji": emoji,
            "reactions": [{"emoji": r['emoji'], "count": r['count']} for r in reactions]
        })
    
    return {
        "success": True,
        "reactions": [{"emoji": r['emoji'], "count": r['count']} for r in reactions]
    }


# ==================== RASMLAR ====================

@app.get("/api/photos")
async def get_photos(user=Depends(get_current_user)):
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
    try:
        mavjud = await db.get_photos(user['chat_id'])
        if len(mavjud) >= config.MAX_PHOTOS_PER_USER:
            return {"success": False, "xato": f"Limit: {config.MAX_PHOTOS_PER_USER} ta rasm"}

        ext = os.path.splitext(file.filename)[1].lower() if file.filename else ".jpg"
        if ext not in config.ALLOWED_EXTENSIONS:
            return {"success": False, "xato": "Faqat rasm fayllari"}

        contents = await file.read()
        if len(contents) > config.MAX_PHOTO_SIZE:
            return {"success": False, "xato": "Rasm juda katta"}

        filename = f"photo_{user['chat_id']}_{uuid.uuid4().hex[:8]}{ext}"
        filepath = os.path.join(config.UPLOAD_DIR, filename)

        os.makedirs(config.UPLOAD_DIR, exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(contents)

        url = f"/static/uploads/{filename}"
        result = await db.add_photo(user['chat_id'], url, nom)

        return {"success": True, "id": result['id'], "url": url}
    except Exception as e:
        return {"success": False, "xato": str(e)}


@app.delete("/api/photos/{photo_id}")
async def delete_photo(photo_id: int, user=Depends(get_current_user)):
    result = await db.delete_photo(photo_id, user['chat_id'])
    if not result:
        raise HTTPException(404, "Rasm topilmadi")

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
    await db.block_user(user['chat_id'], chat_id)
    return {"success": True}


@app.delete("/api/block/{chat_id}")
async def unblock_user(chat_id: int, user=Depends(get_current_user)):
    await db.unblock_user(user['chat_id'], chat_id)
    return {"success": True}


@app.get("/api/blocked")
async def get_blocked(user=Depends(get_current_user)):
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
    ifoda = data.get("ifoda", "")
    natija, xato = hisobla(ifoda)
    if xato:
        return {"success": False, "xato": xato}
    return {"success": True, "natija": natija}


# ==================== WEBSOCKET ====================

class ConnectionManager:
    def __init__(self):
        self.connections: dict[int, list[WebSocket]] = {}

    async def connect(self, chat_id: int, websocket: WebSocket):
        await websocket.accept()
        
        # Eski WS larni yopish
        if chat_id in self.connections:
            old_list = self.connections[chat_id][:]
            self.connections[chat_id] = []
            for old_ws in old_list:
                try:
                    await old_ws.close(code=1000)
                except Exception:
                    pass
        
        if chat_id not in self.connections:
            self.connections[chat_id] = []
        self.connections[chat_id].append(websocket)
        print(f"🔌 WebSocket ulandi: {chat_id}")
        
        try:
            await db.set_online(chat_id, True)
            await self.broadcast_online(chat_id, True)
        except Exception as e:
            print(f"⚠️ Online xato: {e}")

    def disconnect(self, chat_id: int, websocket: WebSocket):
        if chat_id in self.connections:
            if websocket in self.connections[chat_id]:
                self.connections[chat_id].remove(websocket)
            if not self.connections[chat_id]:
                del self.connections[chat_id]
        print(f"🔌 WebSocket uzildi: {chat_id}")

    async def send_to(self, chat_id: int, data: dict):
        if chat_id not in self.connections:
            return
        for ws in self.connections[chat_id][:]:
            try:
                await ws.send_json(data)
            except Exception:
                if ws in self.connections.get(chat_id, []):
                    self.connections[chat_id].remove(ws)

    async def broadcast_online(self, chat_id: int, online: bool):
        try:
            async with db.pool.acquire() as conn:
                chats = await conn.fetch("""
                    SELECT DISTINCT
                        CASE WHEN from_chat = $1 THEN to_chat ELSE from_chat END AS cid
                    FROM messages
                    WHERE (from_chat = $1 OR to_chat = $1) AND ochirilgan = FALSE
                """, chat_id)
            
            for c in chats:
                await self.send_to(c['cid'], {
                    "type": "user_status",
                    "chat_id": chat_id,
                    "online": online,
                    "oxirgi_faollik": datetime.now().isoformat() if not online else None
                })
        except Exception:
            pass


manager = ConnectionManager()


@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
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
                await manager.send_to(data["to_chat"], {
                    "type": "typing",
                    "from_chat": chat_id
                })
            elif turi == "stop_typing":
                await manager.send_to(data["to_chat"], {
                    "type": "stop_typing",
                    "from_chat": chat_id
                })
            elif turi == "read":
                await db.mark_as_read(data["from_chat"], chat_id)
                await manager.send_to(data["from_chat"], {
                    "type": "read",
                    "by_chat": chat_id
                })
            elif turi == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(chat_id, websocket)
        try:
            await db.set_online(chat_id, False)
            await manager.broadcast_online(chat_id, False)
        except Exception:
            pass
    except Exception as e:
        print(f"❌ WebSocket xato: {e}")
        manager.disconnect(chat_id, websocket)


# ==================== RUN ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=False)
