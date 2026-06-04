
from pyrogram import Client, filters
from pyrogram.types import ChatMemberUpdated
from pyrogram.enums import ChatMemberStatus
import config
from database import users_col

@Client.on_chat_member_updated()
async def join_notification(client: Client, update: ChatMemberUpdated):
    # Check if the update is from our specific channel
    if update.chat.id != config.CHANNEL_ID:
        return
    
    # Check if a user joined (previous status was not member, new status is member)
    if (not update.old_chat_member or update.old_chat_member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]) \
       and update.new_chat_member.status == ChatMemberStatus.MEMBER:
        
        user_id = update.new_chat_member.user.id
        
        # Check if user already exists in database (meaning they have interacted with the bot before)
        user = await users_col.find_one({"user_id": user_id})
        
        if user:
            try:
                msg_text = (
                    "**Thank you for joining the channel. Now you are ready to use the bot**\n\n"
                    "**Happy Detecting! 🔍**"
                )
                await client.send_message(user_id, msg_text)
            except Exception as e:
                # User might have blocked the bot or other issues
                print(f"Error sending join notification: {e}")
