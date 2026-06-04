
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import config
from database import get_user

@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    
    # Handle deep links
    if message.command and len(message.command) > 1:
        if message.command[1] == "tc":
            tc_text = (
                "**📜 Terms and Conditions**\n\n"
                "1. This bot is for educational purposes only.\n"
                "2. We do not store any of your search data or personal information.\n"
                "3. Use this bot responsibly and do not use it for any illegal activities.\n"
                "4. By using this bot, you agree to these terms.\n"
                "5. We do follow Telegram and Government rules.\n"
                "6. TrueCallerBot is not affiliated with, sponsored by, endorsed by, or operated by Truecaller or any other caller-ID company. The name “TrueCallerBot” does not imply any partnership, endorsement, or approval from Truecaller. We operate independently and obtain lookup data from licensed third-party providers as described in this Policy.\n"
                "7. Lookups use licensed third-party providers. When you request a lookup, we transmit the submitted phone number to those providers. Their data practices are governed by their own privacy policies. Payment processing is handled by third-party payment processors, and their handling of payment data is governed by their policies.\n\n"
                "**To avoid getting banned, please follow the rules!**"
            )
            buttons = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_start")]])
            return await message.reply_text(tc_text, reply_markup=buttons)

    welcome_text = (
        f"**Hello {message.from_user.first_name} 👋**\n\n"
        "**Send me any phone number in international format to get its information.**\n\n"
        "**Ex: `+911234567890`**"
    )

    bot = await client.get_me()
    tc_url = f"https://t.me/{bot.username}?start=tc"

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 Updates", url=config.CHANNEL_LINK),
            InlineKeyboardButton("📜 T&C", url=tc_url)
        ]
    ])
    
    await message.reply_text(welcome_text, reply_markup=buttons)

@Client.on_callback_query(filters.regex("^more_info$"))
async def more_info_cb(client: Client, cb: CallbackQuery):
    more_text = (
        "**Welcome to TrueCaller Bot! 🤖📞**\n\n"
        "**Get ready to take control of your phone calls like never before. "
        "Simply send me any phone number, and I'll swiftly fetch you detailed information about the caller. "
        "Discover their name, carrier, and location.**\n\n"
        "**Remember, your privacy is our priority. We don't store any personal information, "
        "ensuring a secure and anonymous experience.**\n\n"
        "**To get started, just send me a phone number and let's unveil the mystery behind those unknown calls! 🔎**"
    )
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⬅️ Back", callback_data="back_start"),
            InlineKeyboardButton("📢 Updates", url=config.CHANNEL_LINK)
        ]
    ])
    
    await cb.message.edit_text(more_text, reply_markup=buttons)

@Client.on_callback_query(filters.regex("^back_start$"))
async def back_start_cb(client: Client, cb: CallbackQuery):
    welcome_text = (
        f"**Hello {cb.from_user.first_name} 👋**\n\n"
        "**Send me any phone number in international format to get its information.**\n\n"
        "**Ex: `+911234567890`**"
    )

    bot = await client.get_me()
    tc_url = f"https://t.me/{bot.username}?start=tc"

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 Updates", url=config.CHANNEL_LINK),
            InlineKeyboardButton("📜 T&C", url=tc_url)
        ]
    ])
    
    await cb.message.edit_text(welcome_text, reply_markup=buttons)
