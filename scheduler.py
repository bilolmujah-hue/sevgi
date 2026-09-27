"""
APScheduler - Cron joblar
Avtomatik ochish (blok, maxfiylik)
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

from database import db
from config import config

scheduler = AsyncIOScheduler()


async def check_vaqt_blok():
    """Vaqt blok tugagan foydalanuvchilarni ochish"""
    try:
        async with db.pool.acquire() as conn:
            result = await conn.execute("""
                                        UPDATE users
                                        SET blok_vaqt = NULL,
                                            blok_son  = NULL,
                                            blok_soat = NULL
                                        WHERE blok_vaqt IS NOT NULL
                                          AND blok_vaqt < NOW()
                                        """)
            # Agar biror narsa o'zgargan bo'lsa
            if result and result != "UPDATE 0":
                print(f"🔓 Bloklar ochildi: {datetime.now()}")
    except Exception as e:
        print(f"❌ Blok tekshirishda xato: {e}")


async def check_maxfiylik():
    """Maxfiylik muddati tugaganlarni ochish"""
    try:
        async with db.pool.acquire() as conn:
            result = await conn.execute(f"""
                UPDATE users 
                SET maxfiylik = FALSE, maxfiylik_vaqt = NULL
                WHERE maxfiylik = TRUE 
                  AND maxfiylik_vaqt < NOW() - INTERVAL '{config.MAXFIYLIK_KUN} days'
            """)
            if result and result != "UPDATE 0":
                print(f"🕵️ Maxfiylik ochildi: {datetime.now()}")
    except Exception as e:
        print(f"❌ Maxfiylik tekshirishda xato: {e}")


async def cleanup_old_sessions():
    """Eskirgan JWT sessionlarni tozalash"""
    try:
        async with db.pool.acquire() as conn:
            result = await conn.execute(f"""
                DELETE FROM sessions 
                WHERE vaqt < NOW() - INTERVAL '{config.JWT_EXPIRE_MINUTES} minutes'
            """)
    except Exception as e:
        print(f"❌ Session tozalashda xato: {e}")


def start_scheduler():
    """Schedulerni ishga tushirish"""
    # Har daqiqada blokni tekshirish
    scheduler.add_job(
        check_vaqt_blok,
        'interval',
        minutes=1,
        id='check_vaqt_blok'
    )

    # Har daqiqada maxfiylikni tekshirish
    scheduler.add_job(
        check_maxfiylik,
        'interval',
        minutes=1,
        id='check_maxfiylik'
    )

    # Har 5 daqiqada eski sessionlarni tozalash
    scheduler.add_job(
        cleanup_old_sessions,
        'interval',
        minutes=5,
        id='cleanup_sessions'
    )

    scheduler.start()
    print("✅ Scheduler ishga tushdi")


def stop_scheduler():
    """Schedulerni to'xtatish"""
    if scheduler.running:
        scheduler.shutdown()
        print("⏹️ Scheduler to'xtatildi")