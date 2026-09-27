"""
Telethon Userbot
Foydalanuvchi xabarlarini o'chirish uchun
"""

import asyncio
from telethon import TelegramClient, events
from telethon.tl.functions.messages import DeleteMessagesRequest

from config import config


class UserBot:
    def __init__(self):
        self.client = TelegramClient(
            config.USERBOT_SESSION,
            config.API_ID,
            config.API_HASH
        )
        self._started = False

    async def start(self):
        """Userbotni ishga tushirish"""
        if self._started:
            return

        await self.client.start(phone=config.USERBOT_PHONE)
        self._started = True

        me = await self.client.get_me()
        print(f"✅ Userbot ishga tushdi: @{me.username or me.first_name}")

    async def delete_messages(self, chat_id: int, message_ids: list):
        """
        Xabarlarni o'chirish
        chat_id - qaysi chatda
        message_ids - o'chirilishi kerak bo'lgan xabar ID lari
        """
        if not self._started:
            await self.start()

        try:
            await self.client.delete_messages(chat_id, message_ids)
            return True
        except Exception as e:
            print(f"❌ Xabar o'chirishda xato: {e}")
            return False

    async def delete_chat_history(self, chat_id: int, limit: int = 100):
        """
        Chat tarixini to'liq o'chirish
        (oxirgi N ta xabarni)
        """
        if not self._started:
            await self.start()

        try:
            await self.client.delete_messages(
                chat_id,
                [m.id async for m in self.client.iter_messages(chat_id, limit=limit)]
            )
            return True
        except Exception as e:
            print(f"❌ Tarixni o'chirishda xato: {e}")
            return False

    async def send_message(self, chat_id: int, matn: str):
        """Xabar yuborish (userbot nomidan)"""
        if not self._started:
            await self.start()

        try:
            await self.client.send_message(chat_id, matn)
            return True
        except Exception as e:
            print(f"❌ Xabar yuborishda xato: {e}")
            return False

    async def get_user_info(self, chat_id: int):
        """Foydalanuvchi ma'lumotlarini olish"""
        if not self._started:
            await self.start()

        try:
            entity = await self.client.get_entity(chat_id)
            return {
                'id': entity.id,
                'username': getattr(entity, 'username', None),
                'first_name': getattr(entity, 'first_name', None),
                'last_name': getattr(entity, 'last_name', None),
                'phone': getattr(entity, 'phone', None),
            }
        except Exception as e:
            print(f"❌ Ma'lumot olishda xato: {e}")
            return None

    async def stop(self):
        """Userbotni to'xtatish"""
        if self._started:
            await self.client.disconnect()
            self._started = False


# Global instance
userbot = UserBot()
