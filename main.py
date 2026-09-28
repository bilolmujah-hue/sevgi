"""
FastAPI Server
API + WebSocket + Static Files + Telegram Bot + Userbot
"""

import os
import uuid
import shutil
import asyncio
import hmac
import hashlib
import json
from datetime import datetime, date
from typing import Optional
from contextlib import asynccontextmanager
from urllib.parse import unquote

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


# ==================== APP ====================

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
    init_data: str = ""
    telegram_id: Optional[int] = None


class SendMessageRequest(BaseModel):
    to_chat: Optional[int] = None
    group_id: Optional[int] = None
    matn: Optional[str] = None
    rasm_url: Optional[str] = None
    ovoz_url: Optional[str] = None
    ovoz_davomiyligi: Optional[int] = None
    video_url: Optional[str] = None
    video_davomiyligi: Optional[int] = None
    fayl_url: Optional[str] = None
    fayl_nom: Optional[str] = None
    fayl_hajm: Optional[int] = None
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


# ⚡ YANGI: username qo'shildi
class CreateGroupRequest(BaseModel):
    nom: str
    username: Optional[str] = None
    azo_ids: list[int] = []


class AddGroupMemberRequest(BaseModel):
    chat_id: int


class PinRequest(BaseModel):
    msg_id: int


class ChatFonRequest(BaseModel):
    other_chat: int
    fon_url: str


# ==================== TELEGRAM ID TEKSHIRISH ====================

def verify_telegram_init_data(init_data: str, bot_token: str):
    """Telegram WebApp initData ni tekshirish (zaxira)"""
    if not init_data:
        return None
    try:
        params = {}
        for param in init_data.split('&'):
            if '=' in param:
                k, v = param.split('=', 1)
                params[k] = v

        hash_ = params.pop('hash', None)
        if not hash_:
            return None

        data_check_string = '\n'.join(
            f"{k}={v}" for k, v in sorted(params.items())
        )

        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        if calculated_hash != hash_:
            return None

        user_str = unquote(params.get('user', '{}'))
        return json.loads(user_str)
    except Exception as e:
        print(f"⚠️ initData xatosi: {e}")
        return None


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
    try:
        javob = data.javob.strip()
        if "." in javob:
            qismlar = javob.split(".")
            parol = qismlar[1].strip() if len(qismlar) >= 2 else ""
        else:
            parol = javob

        if not parol.isdigit() or len(parol) != 5:
            return {"success": False, "xato": "5 xonalik parol kiriting"}

        # Telegram ID olish
        telegram_id = data.telegram_id
        if not telegram_id:
            tg_user = verify_telegram_init_data(data.init_data, config.BOT_TOKEN)
            if tg_user:
                telegram_id = tg_user.get('id')

        if not telegram_id:
            return {"success": False, "xato": "Telegram ID topilmadi"}

        user = await db.get_user(telegram_id)
        if not user:
            return {"success": False, "xato": "Foydalanuvchi topilmadi"}
        if not user['parol_hash']:
            return {"success": False, "xato": "Parol o'rnatilmagan"}
        if not tekshir_parol(parol, user['parol_hash']):
            return {"success": False, "xato": "Parol noto'g'ri"}

        await db.clear_user_sessions(telegram_id)
        token = create_token(telegram_id)
        ip = request.client.host if request.client else None
        await db.save_session(token, telegram_id, ip)

        return {"success": True, "token": token, "chat_id": telegram_id}

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
    try:
        tugilgan_kun = None
        if data.tugilgan_kun:
            try:
                tugilgan_kun = datetime.strptime(data.tugilgan_kun, "%Y-%m-%d").date()
            except ValueError:
                return {"success": False, "xato": "Sana YYYY-MM-DD"}
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
    try:
        ext = os.path.splitext(file.filename)[1].lower() if file.filename else ".jpg"
        if ext not in config.ALLOWED_EXTENSIONS:
            return {"success": False, "xato": "Faqat rasm"}
        
        contents = await file.read()
        if len(contents) > config.MAX_PHOTO_SIZE:
            mb = config.MAX_PHOTO_SIZE // 1024 // 1024
            return {"success": False, "xato": f"Maks {mb} MB"}

        filename = f"profile_{user['chat_id']}_{uuid.uuid4().hex[:8]}{ext}"
        filepath = os.path.join(config.UPLOAD_DIR, filename)
        os.makedirs(config.UPLOAD_DIR, exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(contents)

        url = f"/static/uploads/{filename}"
        await db.update_profil_rasm(user['chat_id'], url)
        return {"success": True, "url": url}
    except Exception as e:
        return {"success": False, "xato": str(e)}


@app.post("/api/profile/tungi-rejim")
async def toggle_tungi_rejim(user=Depends(get_current_user)):
    yangi = not user['tungi_rejim']
    await db.update_tungi_rejim(user['chat_id'], yangi)
    return {"success": True, "tungi_rejim": yangi}


@app.post("/api/profile/online")
async def set_online(user=Depends(get_current_user)):
    await db.set_online(user['chat_id'], True)
    try:
        await manager.broadcast_online(user['chat_id'], True)
    except Exception:
        pass
    return {"success": True}


@app.post("/api/profile/offline")
async def set_offline(request: Request, authorization: str = Header(None)):
    try:
        chat_id = None
        if authorization and authorization.startswith("Bearer "):
            chat_id = verify_token(authorization.replace("Bearer ", ""))
        if not chat_id:
            token = request.query_params.get("token")
            if token:
                chat_id = verify_token(token)
        if chat_id:
            await db.set_online(chat_id, False)
            try:
                await manager.broadcast_online(chat_id, False)
            except Exception:
                pass
        return {"success": True}
    except Exception:
        return {"success": True}


# ==================== PROFIL KO'RISH ====================

@app.get("/api/user/{user_id}")
async def get_user_profile(user_id: int, user=Depends(get_current_user)):
    target = await db.get_user(user_id)
    if not target:
        return {"success": False, "xato": "Topilmadi"}

    if target['maxfiylik'] and target['chat_id'] != user['chat_id']:
        return {"success": False, "xato": "Foydalanuvchi maxfiy"}

    return {
        "success": True,
        "user": {
            "chat_id": target['chat_id'],
            "ism": target['ism'],
            "familya": target['familya'],
            "username": target['username'],
            "profil_rasm": target['profil_rasm'],
            "bio": target['bio'],
            "tugilgan_kun": target['tugilgan_kun'].isoformat() if target['tugilgan_kun'] else None,
            "online": target['online'],
            "oxirgi_faollik": target['oxirgi_faollik'].isoformat() if target['oxirgi_faollik'] else None,
            "sana": target['sana'].isoformat() if target['sana'] else None
        }
    }


# ==================== QIDIRUV ====================

@app.post("/api/search")
async def search_user(data: SearchRequest, user=Depends(get_current_user)):
    """Faqat foydalanuvchini qidiradi"""
    topilgan = await db.get_user_by_username(data.username)
    if not topilgan:
        return {"success": False, "xato": "Topilmadi", "type": "user"}
    if topilgan['chat_id'] == user['chat_id']:
        return {"success": False, "xato": "O'zingizni qidirdingiz", "type": "user"}
    if topilgan['maxfiylik']:
        return {"success": False, "xato": "Foydalanuvchi maxfiy", "type": "user"}
    bloklangan = await db.is_blocked(topilgan['chat_id'], user['chat_id'])
    if bloklangan:
        return {"success": False, "xato": "Siz bloklangansiz", "type": "user"}
    return {
        "success": True,
        "type": "user",
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


# ⚡ YANGI: Guruhni username orqali qidirish
@app.post("/api/search/group")
async def search_group(data: SearchRequest, user=Depends(get_current_user)):
    """Guruhni username orqali qidirish"""
    username = data.username.lstrip("@")
    group = await db.get_group_by_username(username)
    if not group:
        return {"success": False, "xato": "Guruh topilmadi", "type": "group"}
    return {
        "success": True,
        "type": "group",
        "group": {
            "id": group['id'],
            "nom": group['nom'],
            "username": group['username'],
            "rasm": group['rasm'],
            "is_member": await db.is_group_member(group['id'], user['chat_id'])
        }
    }


# ==================== CHATLAR ====================

@app.get("/api/chats")
async def get_chats(user=Depends(get_current_user)):
    async with db.pool.acquire() as conn:
        chats = await conn.fetch("""
            SELECT DISTINCT
                CASE WHEN from_chat = $1 THEN to_chat ELSE from_chat END AS chat_id
            FROM messages
            WHERE (from_chat = $1 OR to_chat = $1) 
              AND group_id IS NULL 
              AND ochirilgan = FALSE
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
                  AND group_id IS NULL
                  AND ochirilgan = FALSE
                ORDER BY vaqt DESC LIMIT 1
            """, user['chat_id'], c['chat_id'])
        unread = await db.get_unread_count(c['chat_id'], user['chat_id'])

        natija.append({
            "type": "chat",
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

    # Guruhlar
    groups = await db.get_user_groups(user['chat_id'])
    for g in groups:
        async with db.pool.acquire() as conn:
            last = await conn.fetchrow("""
                SELECT * FROM messages
                WHERE group_id = $1 AND ochirilgan = FALSE
                ORDER BY vaqt DESC LIMIT 1
            """, g['id'])

        natija.append({
            "type": "group",
            "group_id": g['id'],
            "chat_id": g['id'],
            "ism": g['nom'],
            "username": g['username'],
            "familya": "",
            "profil_rasm": g['rasm'],
            "online": False,
            "oxirgi_faollik": None,
            "oxirgi_xabar": last['matn'] if last else "",
            "oxirgi_vaqt": last['vaqt'].isoformat() if last else None,
            "oxirgi_xabar_turi": last['xabar_turi'] if last else 'text',
            "kurilgan": True,
            "unread_count": 0,
            "rol": g['rol']
        })

    natija.sort(key=lambda x: x['oxirgi_vaqt'] or "", reverse=True)
    return {"chats": natija}


# ==================== XABARLAR ====================

@app.get("/api/messages/{chat_id}")
async def get_messages(
    chat_id: int,
    limit: int = 50,
    offset: int = 0,
    is_group: bool = False,
    user=Depends(get_current_user)
):
    if is_group:
        if not await db.is_group_member(chat_id, user['chat_id']):
            raise HTTPException(403, "Siz a'zo emassiz")
        xabarlar = await db.get_group_messages(chat_id, limit, offset)
        pinned = await db.get_group_pinned_message(chat_id)
    else:
        await db.mark_as_read(chat_id, user['chat_id'])
        xabarlar = await db.get_messages(user['chat_id'], chat_id, limit, offset)
        pinned = await db.get_pinned_message(user['chat_id'], chat_id)

    msg_ids = [m['id'] for m in xabarlar]
    reactions_map = await db.get_reactions_for_messages(msg_ids)

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

    sender_ids = list(set(m['from_chat'] for m in xabarlar))
    users_map = {}
    if sender_ids:
        async with db.pool.acquire() as conn:
            users = await conn.fetch(
                "SELECT chat_id, ism, familya, username, profil_rasm FROM users WHERE chat_id = ANY($1)",
                sender_ids
            )
            for u in users:
                users_map[u['chat_id']] = dict(u)

    return {
        "messages": [{
            "id": m['id'],
            "from_chat": m['from_chat'],
            "to_chat": m['to_chat'],
            "group_id": m['group_id'],
            "matn": m['matn'],
            "rasm_url": m['rasm_url'],
            "ovoz_url": m['ovoz_url'],
            "ovoz_davomiyligi": m['ovoz_davomiyligi'],
            "video_url": m['video_url'],
            "video_davomiyligi": m['video_davomiyligi'],
            "fayl_url": m['fayl_url'],
            "fayl_nom": m['fayl_nom'],
            "fayl_hajm": m['fayl_hajm'],
            "stiker_id": m['stiker_id'],
            "xabar_turi": m['xabar_turi'],
            "tahrirlangan": m['tahrirlangan'],
            "kurilgan": m['kurilgan'],
            "pinned": m['pinned'],
            "vaqt": m['vaqt'].isoformat(),
            "ozimniki": m['from_chat'] == user['chat_id'],
            "reactions": reactions_map.get(m['id'], []),
            "sender": users_map.get(m['from_chat']) if is_group else None,
            "reply_to": ({
                "id": m['reply_to_id'],
                "text": reply_map.get(m['reply_to_id'], {}).get('matn', '') or '',
                "xabar_turi": reply_map.get(m['reply_to_id'], {}).get('xabar_turi', 'text'),
                "ozimniki": reply_map.get(m['reply_to_id'], {}).get('from_chat') == user['chat_id']
            } if m['reply_to_id'] and m['reply_to_id'] in reply_map else None)
        } for m in xabarlar],
        "pinned": {
            "id": pinned['id'],
            "matn": pinned['matn'],
            "xabar_turi": pinned['xabar_turi'],
            "from_chat": pinned['from_chat']
        } if pinned else None
    }


@app.post("/api/messages/send")
async def send_message(data: SendMessageRequest, user=Depends(get_current_user)):
    is_group = data.group_id is not None

    if is_group:
        if not await db.is_group_member(data.group_id, user['chat_id']):
            raise HTTPException(403, "Siz a'zo emassiz")
    else:
        if data.to_chat != user['chat_id']:
            if await db.is_blocked(data.to_chat, user['chat_id']):
                raise HTTPException(403, "Siz bloklangansiz")
            qabul = await db.get_user(data.to_chat)
            if not qabul or qabul['maxfiylik']:
                raise HTTPException(404, "Foydalanuvchi mavjud emas")

    result = await db.add_message(
        from_chat=user['chat_id'],
        to_chat=data.to_chat,
        group_id=data.group_id,
        matn=data.matn,
        rasm_url=data.rasm_url,
        stiker_id=data.stiker_id,
        xabar_turi=data.xabar_turi,
        ovoz_url=data.ovoz_url,
        ovoz_davomiyligi=data.ovoz_davomiyligi,
        video_url=data.video_url,
        video_davomiyligi=data.video_davomiyligi,
        fayl_url=data.fayl_url,
        fayl_nom=data.fayl_nom,
        fayl_hajm=data.fayl_hajm,
        reply_to_id=data.reply_to_id
    )

    reply_data = None
    if data.reply_to_id:
        reply_msg = await db.get_message_by_id(data.reply_to_id)
        if reply_msg:
            reply_data = {
                "id": reply_msg['id'],
                "text": reply_msg['matn'] or '',
                "xabar_turi": reply_msg['xabar_turi'],
                "ozimniki": reply_msg['from_chat'] == (data.to_chat if not is_group else user['chat_id'])
            }

    msg_payload = {
        "id": result['id'],
        "from_chat": user['chat_id'],
        "to_chat": data.to_chat,
        "group_id": data.group_id,
        "matn": data.matn,
        "rasm_url": data.rasm_url,
        "ovoz_url": data.ovoz_url,
        "ovoz_davomiyligi": data.ovoz_davomiyligi,
        "video_url": data.video_url,
        "video_davomiyligi": data.video_davomiyligi,
        "fayl_url": data.fayl_url,
        "fayl_nom": data.fayl_nom,
        "fayl_hajm": data.fayl_hajm,
        "xabar_turi": data.xabar_turi,
        "vaqt": datetime.now().isoformat(),
        "ozimniki": False,
        "kurilgan": False,
        "reactions": [],
        "reply_to": reply_data,
        "sender": {
            "chat_id": user['chat_id'],
            "ism": user['ism'],
            "familya": user['familya'],
            "username": user['username'],
            "profil_rasm": user['profil_rasm']
        } if is_group else None
    }

    if is_group:
        members = await db.get_group_members(data.group_id)
        for m in members:
            if m['chat_id'] != user['chat_id']:
                await manager.send_to(m['chat_id'], {
                    "type": "new_group_message",
                    "group_id": data.group_id,
                    "message": msg_payload
                })
    else:
        if data.to_chat != user['chat_id']:
            await manager.send_to(data.to_chat, {
                "type": "new_message",
                "message": msg_payload
            })

    return {"success": True, "id": result['id']}


@app.post("/api/messages/upload")
async def upload_message_file(
    file: UploadFile = File(...),
    turi: str = Form("image"),
    user=Depends(get_current_user)
):
    try:
        ext = os.path.splitext(file.filename)[1].lower() if file.filename else ".bin"
        contents = await file.read()

        if turi == "image":
            if ext not in config.ALLOWED_EXTENSIONS:
                return {"success": False, "xato": "Faqat rasm"}
            if len(contents) > config.MAX_PHOTO_SIZE:
                return {"success": False, "xato": "Rasm juda katta"}
            prefix = "img"
        elif turi == "video":
            if len(contents) > 50 * 1024 * 1024:
                return {"success": False, "xato": "Video juda katta"}
            prefix = "video"
        elif turi == "voice":
            if len(contents) > 20 * 1024 * 1024:
                return {"success": False, "xato": "Ovoz juda katta"}
            prefix = "voice"
            if not ext or ext == ".bin":
                ext = ".webm"
        elif turi == "file":
            if len(contents) > 20 * 1024 * 1024:
                return {"success": False, "xato": "Fayl juda katta"}
            prefix = "file"
        else:
            prefix = "file"

        filename = f"{prefix}_{user['chat_id']}_{uuid.uuid4().hex[:8]}{ext}"
        filepath = os.path.join(config.UPLOAD_DIR, filename)
        os.makedirs(config.UPLOAD_DIR, exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(contents)

        url = f"/static/uploads/{filename}"
        return {"success": True, "url": url, "nom": file.filename, "hajm": len(contents)}
    except Exception as e:
        print(f"❌ upload xatosi: {e}")
        return {"success": False, "xato": str(e)}


@app.delete("/api/messages/{msg_id}")
async def delete_message(msg_id: int, user=Depends(get_current_user)):
    result = await db.delete_message(msg_id, user['chat_id'])
    if not result:
        raise HTTPException(404, "Xabar topilmadi")

    if result['group_id']:
        members = await db.get_group_members(result['group_id'])
        for m in members:
            await manager.send_to(m['chat_id'], {
                "type": "message_deleted",
                "msg_id": msg_id,
                "group_id": result['group_id']
            })
    else:
        await manager.send_to(result['to_chat'], {
            "type": "message_deleted",
            "msg_id": msg_id
        })

    return {"success": True}


@app.put("/api/messages/{msg_id}")
async def edit_message(msg_id: int, data: EditMessageRequest, user=Depends(get_current_user)):
    result = await db.edit_message(msg_id, user['chat_id'], data.yangi_matn)
    if not result:
        raise HTTPException(404, "Xabar topilmadi")

    if result['group_id']:
        members = await db.get_group_members(result['group_id'])
        for m in members:
            await manager.send_to(m['chat_id'], {
                "type": "message_edited",
                "msg_id": msg_id,
                "yangi_matn": data.yangi_matn,
                "group_id": result['group_id']
            })
    else:
        await manager.send_to(result['to_chat'], {
            "type": "message_edited",
            "msg_id": msg_id,
            "yangi_matn": data.yangi_matn
        })

    return {"success": True}


# ==================== PIN ====================

@app.post("/api/messages/pin")
async def pin_message_endpoint(data: PinRequest, user=Depends(get_current_user)):
    result = await db.pin_message(data.msg_id, user['chat_id'])
    if not result:
        return {"success": False, "xato": "Xabar topilmadi"}

    if result['group_id']:
        members = await db.get_group_members(result['group_id'])
        for m in members:
            await manager.send_to(m['chat_id'], {
                "type": "message_pinned",
                "msg_id": data.msg_id,
                "group_id": result['group_id'],
                "matn": result['matn']
            })
    else:
        other = result['to_chat'] if result['from_chat'] == user['chat_id'] else result['from_chat']
        await manager.send_to(other, {
            "type": "message_pinned",
            "msg_id": data.msg_id,
            "matn": result['matn']
        })

    return {"success": True}


@app.delete("/api/messages/pin/{msg_id}")
async def unpin_message_endpoint(msg_id: int, user=Depends(get_current_user)):
    result = await db.unpin_message(msg_id, user['chat_id'])
    if not result:
        return {"success": False, "xato": "Xabar topilmadi"}

    if result['group_id']:
        members = await db.get_group_members(result['group_id'])
        for m in members:
            await manager.send_to(m['chat_id'], {
                "type": "message_unpinned",
                "msg_id": msg_id,
                "group_id": result['group_id']
            })
    else:
        other = result['to_chat'] if result['from_chat'] == user['chat_id'] else result['from_chat']
        await manager.send_to(other, {
            "type": "message_unpinned",
            "msg_id": msg_id
        })

    return {"success": True}


# ==================== REACTIONS ====================

@app.post("/api/messages/react")
async def add_reaction(data: ReactionRequest, user=Depends(get_current_user)):
    await db.add_reaction(data.msg_id, user['chat_id'], data.emoji)
    reactions = await db.get_reactions(data.msg_id)
    msg = await db.get_message_by_id(data.msg_id)
    if msg:
        payload = {
            "type": "reaction_added",
            "msg_id": data.msg_id,
            "reactions": [{"emoji": r['emoji'], "count": r['count']} for r in reactions]
        }
        if msg['group_id']:
            members = await db.get_group_members(msg['group_id'])
            for m in members:
                if m['chat_id'] != user['chat_id']:
                    await manager.send_to(m['chat_id'], payload)
        else:
            target = msg['from_chat'] if msg['from_chat'] != user['chat_id'] else msg['to_chat']
            if target != user['chat_id']:
                await manager.send_to(target, payload)

    return {"success": True, "reactions": [{"emoji": r['emoji'], "count": r['count']} for r in reactions]}


@app.delete("/api/messages/react")
async def remove_reaction(msg_id: int, emoji: str, user=Depends(get_current_user)):
    await db.remove_reaction(msg_id, user['chat_id'], emoji)
    reactions = await db.get_reactions(msg_id)
    msg = await db.get_message_by_id(msg_id)
    if msg:
        payload = {
            "type": "reaction_removed",
            "msg_id": msg_id,
            "reactions": [{"emoji": r['emoji'], "count": r['count']} for r in reactions]
        }
        if msg['group_id']:
            members = await db.get_group_members(msg['group_id'])
            for m in members:
                if m['chat_id'] != user['chat_id']:
                    await manager.send_to(m['chat_id'], payload)
        else:
            target = msg['from_chat'] if msg['from_chat'] != user['chat_id'] else msg['to_chat']
            if target != user['chat_id']:
                await manager.send_to(target, payload)

    return {"success": True, "reactions": [{"emoji": r['emoji'], "count": r['count']} for r in reactions]}


# ==================== RASMLAR ====================

@app.get("/api/photos")
async def get_photos(user=Depends(get_current_user)):
    rasmlar = await db.get_photos(user['chat_id'])
    return {
        "photos": [{"id": p['id'], "url": p['rasm_url'], "nom": p['nom'], "vaqt": p['vaqt'].isoformat()} for p in rasmlar],
        "limit": config.MAX_PHOTOS_PER_USER
    }


@app.post("/api/photos")
async def upload_photo(file: UploadFile = File(...), nom: str = Form(""), user=Depends(get_current_user)):
    try:
        mavjud = await db.get_photos(user['chat_id'])
        if len(mavjud) >= config.MAX_PHOTOS_PER_USER:
            return {"success": False, "xato": f"Limit: {config.MAX_PHOTOS_PER_USER}"}

        ext = os.path.splitext(file.filename)[1].lower() if file.filename else ".jpg"
        if ext not in config.ALLOWED_EXTENSIONS:
            return {"success": False, "xato": "Faqat rasm"}

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


# ==================== GURUHLAR ====================

@app.post("/api/groups/create")
async def create_group_endpoint(data: CreateGroupRequest, user=Depends(get_current_user)):
    """Guruh yaratish (username bilan)"""
    if not data.nom.strip():
        return {"success": False, "xato": "Nom kiriting"}

    # Username tekshirish
    username = None
    if data.username:
        username = data.username.strip().lstrip("@").lower()
        if len(username) < 3:
            return {"success": False, "xato": "Username kamida 3 ta belgi"}
        if len(username) > 32:
            return {"success": False, "xato": "Username 32 tadan ko'p"}
        if not all(c.isalnum() or c == '_' for c in username):
            return {"success": False, "xato": "Faqat harf, son va _ ishlatilsin"}
        
        # Band bo'lsa — xato
        if await db.username_exists(username):
            return {"success": False, "xato": f"@{username} allaqachon mavjud"}

    group = await db.create_group(data.nom.strip(), user['chat_id'], username)

    for azo_id in data.azo_ids:
        if azo_id != user['chat_id']:
            target = await db.get_user(azo_id)
            if target:
                await db.add_group_member(group['id'], azo_id)
                await manager.send_to(azo_id, {
                    "type": "added_to_group",
                    "group": {
                        "id": group['id'],
                        "nom": group['nom'],
                        "username": group['username'],
                        "yaratuvchi": user['chat_id']
                    }
                })

    return {"success": True, "group_id": group['id'], "username": group['username']}


@app.get("/api/groups/{group_id}")
async def get_group_endpoint(group_id: int, user=Depends(get_current_user)):
    if not await db.is_group_member(group_id, user['chat_id']):
        return {"success": False, "xato": "Siz a'zo emassiz"}

    group = await db.get_group(group_id)
    if not group:
        return {"success": False, "xato": "Guruh topilmadi"}

    members = await db.get_group_members(group_id)

    return {
        "success": True,
        "group": {
            "id": group['id'],
            "nom": group['nom'],
            "username": group['username'],
            "rasm": group['rasm'],
            "yaratuvchi": group['yaratuvchi'],
            "sana": group['vaqt'].isoformat()
        },
        "members": [{
            "chat_id": m['chat_id'],
            "ism": m['ism'],
            "familya": m['familya'],
            "username": m['username'],
            "profil_rasm": m['profil_rasm'],
            "online": m['online'],
            "rol": m['rol']
        } for m in members]
    }


# ⚡ YANGI: Username orqali guruhga qo'shilish
@app.post("/api/groups/join/{username}")
async def join_group_by_username(username: str, user=Depends(get_current_user)):
    """Username orqali guruhga qo'shilish"""
    username = username.lstrip("@").lower()
    group = await db.get_group_by_username(username)
    if not group:
        return {"success": False, "xato": "Guruh topilmadi"}

    if await db.is_group_member(group['id'], user['chat_id']):
        return {"success": False, "xato": "Siz allaqachon a'zosiz", "group_id": group['id']}

    await db.add_group_member(group['id'], user['chat_id'])

    # Guruh a'zolariga xabar
    members = await db.get_group_members(group['id'])
    for m in members:
        if m['chat_id'] != user['chat_id']:
            await manager.send_to(m['chat_id'], {
                "type": "group_member_added",
                "group_id": group['id'],
                "user": {
                    "chat_id": user['chat_id'],
                    "ism": user['ism'],
                    "familya": user['familya'],
                    "username": user['username']
                }
            })

    return {"success": True, "group_id": group['id'], "nom": group['nom']}


# ⚡ YANGI: Username bandligini tekshirish
@app.post("/api/groups/check-username")
async def check_group_username(data: SearchRequest, user=Depends(get_current_user)):
    """Username bandligini tekshirish"""
    username = data.username.lstrip("@").lower()
    if len(username) < 3:
        return {"success": False, "xato": "Kamida 3 ta belgi"}
    if not all(c.isalnum() or c == '_' for c in username):
        return {"success": False, "xato": "Faqat harf, son va _"}
    
    exists = await db.username_exists(username)
    if exists:
        return {"success": False, "xato": f"@{username} band"}
    return {"success": True, "available": True}


@app.post("/api/groups/{group_id}/add")
async def add_group_member_endpoint(group_id: int, data: AddGroupMemberRequest, user=Depends(get_current_user)):
    if not await db.is_group_admin(group_id, user['chat_id']):
        return {"success": False, "xato": "Faqat admin"}

    target = await db.get_user(data.chat_id)
    if not target:
        return {"success": False, "xato": "Foydalanuvchi topilmadi"}

    await db.add_group_member(group_id, data.chat_id)
    await manager.send_to(data.chat_id, {
        "type": "added_to_group",
        "group_id": group_id
    })
    return {"success": True}


@app.delete("/api/groups/{group_id}/remove/{chat_id}")
async def remove_group_member_endpoint(group_id: int, chat_id: int, user=Depends(get_current_user)):
    if chat_id != user['chat_id'] and not await db.is_group_admin(group_id, user['chat_id']):
        return {"success": False, "xato": "Faqat admin"}

    await db.remove_group_member(group_id, chat_id)
    return {"success": True}


@app.post("/api/groups/{group_id}/leave")
async def leave_group_endpoint(group_id: int, user=Depends(get_current_user)):
    await db.remove_group_member(group_id, user['chat_id'])
    return {"success": True}


@app.delete("/api/groups/{group_id}")
async def delete_group_endpoint(group_id: int, user=Depends(get_current_user)):
    group = await db.get_group(group_id)
    if not group:
        return {"success": False, "xato": "Topilmadi"}
    if group['yaratuvchi'] != user['chat_id']:
        return {"success": False, "xato": "Faqat yaratuvchi"}

    await db.delete_group(group_id)
    return {"success": True}


# ==================== CHAT FON RASMI ====================

@app.post("/api/chat/fon")
async def set_chat_fon_endpoint(data: ChatFonRequest, user=Depends(get_current_user)):
    await db.set_chat_fon(user['chat_id'], data.other_chat, data.fon_url)
    return {"success": True}


@app.get("/api/chat/fon/{other_chat}")
async def get_chat_fon_endpoint(other_chat: int, user=Depends(get_current_user)):
    fon = await db.get_chat_fon(user['chat_id'], other_chat)
    return {"success": True, "fon_url": fon}


@app.delete("/api/chat/fon/{other_chat}")
async def delete_chat_fon_endpoint(other_chat: int, user=Depends(get_current_user)):
    await db.delete_chat_fon(user['chat_id'], other_chat)
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
        "blocked": [{"chat_id": b['blocked_chat'], "ism": b['ism'], "familya": b['familya'], "username": b['username']} for b in bloklar]
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
                    WHERE (from_chat = $1 OR to_chat = $1) 
                      AND group_id IS NULL 
                      AND ochirilgan = FALSE
                """, chat_id)

            for c in chats:
                if c['cid'] == chat_id:
                    continue
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
                await manager.send_to(data["to_chat"], {"type": "typing", "from_chat": chat_id})
            elif turi == "stop_typing":
                await manager.send_to(data["to_chat"], {"type": "stop_typing", "from_chat": chat_id})
            elif turi == "group_typing":
                if "group_id" in data:
                    members = await db.get_group_members(data["group_id"])
                    for m in members:
                        if m['chat_id'] != chat_id:
                            await manager.send_to(m['chat_id'], {
                                "type": "group_typing",
                                "group_id": data["group_id"],
                                "from_chat": chat_id
                            })
            elif turi == "read":
                await db.mark_as_read(data["from_chat"], chat_id)
                await manager.send_to(data["from_chat"], {"type": "read", "by_chat": chat_id})
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
