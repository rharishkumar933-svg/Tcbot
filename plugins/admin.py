
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import config
from database import get_stats, add_ad, get_all_ads, get_ad, delete_ad, toggle_ads, ads_enabled, get_ad_timer, set_ad_timer, db, toggle_forcesub, forcesub_enabled
import asyncio

@Client.on_message(filters.command("stats") & filters.user(config.ADMINS))
async def stats_cmd(client: Client, message: Message):
    args = message.text.split()
    
    # Check for specific user stats
    if len(args) > 1:
        try:
            target_user_id = int(args[1])
            user_data = await db['users'].find_one({"user_id": target_user_id})
            
            if not user_data:
                return await message.reply_text(f"**❌ User `{target_user_id}` not found in database.**")
            
            status = "Banned 🚫" if user_data.get("is_banned") else "Active ✅"
            text = (
                f"👤 **User Statistics: `{target_user_id}`**\n\n"
                f"**Joined:** `{user_data.get('join_date')}`\n"
                f"**Status:** `{status}`\n"
                f"**Searches Today:** `{user_data.get('search_count_today', 0)}`\n"
                f"**Total Searches:** `{user_data.get('total_searches', 0)}`\n"
                f"**Last Search:** `{user_data.get('last_search_date', 'N/A')}`\n"
                f"**Last Ad View:** `{user_data.get('last_ad_view_date', 'Never')}`"
            )
            return await message.reply_text(text)
        except ValueError:
            return await message.reply_text("**❌ Invalid User ID format. Use numerals only.**")

    # Default Global Stats
    stats = await get_stats()
    text = (
        "📊 **Global Bot Statistics**\n\n"
        f"**Total Users:** `{stats['total_users']}`\n"
        f"**New Users Today:** `{stats['new_users_today']}`\n"
        f"**Total Searches:** `{stats['total_searches']}`\n"
        f"**Total Ad Views:** `{stats['total_ads_viewed']}`\n\n"
        "**Usage:**\n"
        "• `/stats` - Global stats\n"
        "• `/stats userid` - User stats\n"
        "• `/ban userid` - Ban a user\n"
        "• `/unban userid` - Unban a user"
    )
    await message.reply_text(text)

@Client.on_message(filters.command("ban") & filters.user(config.ADMINS))
async def ban_cmd(client: Client, message: Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.reply_text("**Usage: `/ban userid`**")
    
    try:
        user_id = int(args[1])
        await db['users'].update_one({"user_id": user_id}, {"$set": {"is_banned": True}}, upsert=True)
        await message.reply_text(f"**✅ User `{user_id}` has been banned.**")
    except ValueError:
        await message.reply_text("**❌ Invalid User ID.**")

@Client.on_message(filters.command("unban") & filters.user(config.ADMINS))
async def unban_cmd(client: Client, message: Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.reply_text("**Usage: `/unban userid`**")
    
    try:
        user_id = int(args[1])
        await db['users'].update_one({"user_id": user_id}, {"$set": {"is_banned": False}}, upsert=True)
        await message.reply_text(f"**✅ User `{user_id}` has been unbanned.**")
    except ValueError:
        await message.reply_text("**❌ Invalid User ID.**")

@Client.on_message(filters.command("forcesub") & filters.user(config.ADMINS))
async def forcesub_cmd(client: Client, message: Message):
    args = message.text.split()
    if len(args) < 2:
        enabled = await forcesub_enabled()
        status = "ON" if enabled else "OFF"
        return await message.reply_text(
            f"**Forcesub Status: `{status}`**\n\n"
            "**Usage:**\n"
            "• `/forcesub on` - Enable Forcesub\n"
            "• `/forcesub off` - Disable Forcesub"
        )
    
    cmd = args[1].lower()
    if cmd == "on":
        await toggle_forcesub(True)
        await message.reply_text("**✅ Forcesub enabled.**")
    elif cmd == "off":
        await toggle_forcesub(False)
        await message.reply_text("**✅ Forcesub disabled.**")
    else:
        await message.reply_text("**❌ Invalid command. Use `/forcesub on` or `/forcesub off`**")

@Client.on_message(filters.command("broadcast") & filters.user(config.ADMINS))
async def broadcast_cmd(client: Client, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to a message to broadcast it.")
    
    msg = message.reply_to_message
    users = db['users'].find({})
    total = await db['users'].count_documents({})
    done = 0
    failed = 0
    
    status_msg = await message.reply_text(f"🚀 Broadcasting to {total} users...")
    
    async for user in users:
        try:
            # Using .copy() as requested for broadcast
            await msg.copy(user['user_id'])
            done += 1
        except Exception:
            failed += 1
        
        if (done + failed) % 50 == 0:
            await status_msg.edit_text(f"🚀 Broadcasting... {done}/{total} done.")
            await asyncio.sleep(1)
            
    await status_msg.edit_text(f"✅ Broadcast Complete!\n\nDone: {done}\nFailed: {failed}")

# --- Ads Management ---

@Client.on_message(filters.command("ads") & filters.user(config.ADMINS))
async def ads_manage_cmd(client: Client, message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        enabled = await ads_enabled()
        timer = await get_ad_timer()
        status = "ON" if enabled else "OFF"
        timer_status = f"{timer}s" if timer > 0 else "OFF"
        return await message.reply_text(
            f"**Ads Status: `{status}`**\n"
            f"**Auto-Delete Timer: `{timer_status}`**\n\n"
            "**Commands:**\n"
            "• `/ads on` - Enable Ads\n"
            "• `/ads off` - Disable Ads\n"
            "• `/ads set title` - Reply to a message to set as Ad\n"
            "• `/ads timer on` - Enable auto-delete (default 60s)\n"
            "• `/ads timer off` - Disable auto-delete\n"
            "• `/ads timer <seconds>` - Set auto-delete time\n"
            "• `/adslist` - List, view and remove ads.\n\n"
            "**Example:**\n"
            "1. Send your advertisement (text, image, or video).\n"
            "2. Reply to that message with: `/ads set Premium Search`"
        )

    cmd = args[1].lower()
    
    if cmd == "on":
        await toggle_ads(True)
        await message.reply_text("Ads enabled.")
    elif cmd == "off":
        await toggle_ads(False)
        await message.reply_text("Ads disabled.")
    elif cmd == "set":
        if not message.reply_to_message:
            return await message.reply_text("Reply to a message to set it as an ad.")
        if len(args) < 3:
            return await message.reply_text("Usage: `/ads set <title>` (reply to an ad message)")
        
        title = args[2]
        chat_id = message.chat.id
        message_id = message.reply_to_message.id
        
        await add_ad(title, chat_id, message_id)
        await message.reply_text(f"✅ Ad '{title}' added successfully!")
    elif cmd == "timer":
        if len(args) < 3:
            return await message.reply_text(
                "**Ads Auto-Delete Timer**\n\n"
                "Usage:\n"
                "• `/ads timer on` - Enable (60s)\n"
                "• `/ads timer off` - Disable\n"
                "• `/ads timer <seconds>` - Set custom time\n\n"
                "**Example:** `/ads timer 30`"
            )
        
        val = args[2].lower()
        if val == "on":
            await set_ad_timer(60) # Default 60s
            await message.reply_text("✅ Auto-delete enabled (60 seconds).")
        elif val == "off":
            await set_ad_timer(0)
            await message.reply_text("✅ Auto-delete disabled.")
        elif val.isdigit():
            seconds = int(val)
            await set_ad_timer(seconds)
            await message.reply_text(f"✅ Auto-delete set to {seconds} seconds.")
        else:
            await message.reply_text("❌ Invalid value. Use `on`, `off` or a number.")

@Client.on_message(filters.command("adslist") & filters.user(config.ADMINS))
async def ads_list_cmd(client: Client, message: Message):
    ads = await get_all_ads()
    if not ads:
        return await message.reply_text("No ads added yet.")
    
    buttons = []
    for ad in ads:
        buttons.append([InlineKeyboardButton(ad['title'], callback_data=f"ad_manage_{ad['_id']}")])
    
    await message.reply_text("🎯 **Ads List**\nSelect an ad to manage:", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^ad_manage_"))
async def ad_manage_cb(client: Client, cb: CallbackQuery):
    ad_id = cb.data.split("_")[2]
    ad = await get_ad(ad_id)
    if not ad:
        return await cb.answer("Ad not found!", show_alert=True)
    
    text = f"Manage Ad: **{ad['title']}**"
    buttons = [
        [
            InlineKeyboardButton("👁 View Ad", callback_data=f"ad_view_{ad_id}"),
            InlineKeyboardButton("🗑 Remove Ad", callback_data=f"ad_delete_{ad_id}")
        ],
        [InlineKeyboardButton("⬅️ Back to List", callback_data="ad_list_back")]
    ]
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^ad_view_"))
async def ad_view_cb(client: Client, cb: CallbackQuery):
    ad_id = cb.data.split("_")[2]
    ad = await get_ad(ad_id)
    if not ad:
        return await cb.answer("Ad not found!", show_alert=True)
    
    try:
        # Send ad to admin using .copy()
        await client.copy_message(cb.from_user.id, ad['chat_id'], ad['message_id'])
        await cb.answer("Ad sent to you!")
    except Exception as e:
        await cb.answer(f"Error: {e}", show_alert=True)

@Client.on_callback_query(filters.regex(r"^ad_delete_"))
async def ad_delete_cb(client: Client, cb: CallbackQuery):
    ad_id = cb.data.split("_")[2]
    await delete_ad(ad_id)
    await cb.answer("Ad deleted!", show_alert=True)
    await ads_list_cmd(client, cb.message) # Refresh list

@Client.on_callback_query(filters.regex(r"^ad_list_back"))
async def ad_list_back_cb(client: Client, cb: CallbackQuery):
    await ads_list_cmd(client, cb.message)
