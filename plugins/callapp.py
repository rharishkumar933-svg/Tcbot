from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import config
from database import add_callapp_account, get_all_callapp_accounts, delete_callapp_account
import urllib.parse as urlparse
import re

def is_admin(user_id):
    return user_id in config.ADMINS

@Client.on_message(filters.command("callapp") & filters.private)
async def callapp_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) == 1:
        help_text = (
            "**CallApp Account Management**\n\n"
            "Commands:\n"
            "• `/callapp add <url>` - Add a new CallApp account via URL\n"
            "• `/callapp list` - List and manage added accounts\n"
            "• `/callapp del <id>` - Delete an account by ID\n"
        )
        await message.reply_text(help_text)
        return

    subcommand = args[1].lower()

    if subcommand == "add":
        if len(args) < 3:
            return await message.reply_text("❌ Please provide a CallApp search URL.\nExample: `/callapp add https://s.callapp.com/...`")
        
        url = args[2]
        parsed = urlparse.urlparse(url)
        params = urlparse.parse_qs(parsed.query)
        
        required = ["myp", "ibs", "cid", "tk", "cvc"]
        extracted = {}
        for r in required:
            val = params.get(r)
            if not val:
                return await message.reply_text(f"❌ Missing parameter in URL: `{r}`")
            extracted[r] = val[0]
        
        success, msg = await add_callapp_account(extracted)
        if success:
            await message.reply_text(f"✅ **Account Added!**\n\n**MYP:** `{extracted['myp']}`\n**TK:** `{extracted['tk']}`")
        else:
            await message.reply_text(f"❌ {msg}")

    elif subcommand == "list":
        await send_callapp_list(message)

    elif subcommand == "del":
        if len(args) < 3:
            return await message.reply_text("❌ Please provide the account ID to delete.")
        
        acc_id = args[2]
        success = await delete_callapp_account(acc_id)
        if success:
            await message.reply_text("✅ Account deleted successfully.")
            await send_callapp_list(message)
        else:
            await message.reply_text("❌ Failed to delete account. Check the ID.")

async def send_callapp_list(message, page=1):
    accounts = await get_all_callapp_accounts()
    if not accounts:
        text = "❌ No CallApp accounts found."
        if isinstance(message, CallbackQuery):
            await message.edit_message_text(text)
        else:
            await message.reply_text(text)
        return

    total_pages = (len(accounts) + 4) // 5
    page = max(1, min(page, total_pages))
    
    start = (page - 1) * 5
    end = start + 5
    current_accounts = accounts[start:end]

    text = f"**Total CallApp Accounts: {len(accounts)}**\n"
    text += f"Page: {page}/{total_pages}\n\n"

    buttons = []
    for acc in current_accounts:
        acc_id = str(acc['_id'])
        myp = acc['myp']
        # Masking myp
        masked_myp = myp
            
        requests = acc.get('request_count', 0)
        text += f"📍 **MYP:** `{masked_myp}`\n"
        text += f"📊 **Requests:** `{requests}`\n"
        text += f"🆔 ID: `{acc_id}`\n\n"
        
        buttons.append([
            InlineKeyboardButton(f"❌ Delete {masked_myp}", callback_data=f"ca_del_{acc_id}_{page}")
        ])

    nav_btns = []
    if page > 1:
        nav_btns.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"ca_page_{page-1}"))
    if page < total_pages:
        nav_btns.append(InlineKeyboardButton("Next ➡️", callback_data=f"ca_page_{page+1}"))
    
    if nav_btns:
        buttons.append(nav_btns)

    markup = InlineKeyboardMarkup(buttons)
    
    if isinstance(message, Message):
        await message.reply_text(text, reply_markup=markup)
    else:
        await message.edit_message_text(text, reply_markup=markup)

@Client.on_callback_query(filters.regex(r"^ca_"))
async def callapp_callback(client: Client, callback_query: CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        return await callback_query.answer("You are not authorized.", show_alert=True)

    data = callback_query.data
    
    if data.startswith("ca_page_"):
        page = int(data.split("_")[2])
        await send_callapp_list(callback_query, page)
    
    elif data.startswith("ca_del_"):
        # Format: ca_del_ID_PAGE
        parts = data.split("_")
        acc_id = parts[2]
        page = int(parts[3])
        
        # Show confirmation
        buttons = [
            [
                InlineKeyboardButton("✅ Confirm Delete", callback_data=f"ca_cdel_{acc_id}_{page}"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"ca_page_{page}")
            ]
        ]
        text = f"⚠️ **Are you sure you want to delete this account?**\n`ID: {acc_id}`"
        await callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("ca_cdel_"):
        parts = data.split("_")
        acc_id = parts[2]
        page = int(parts[3])
        
        success = await delete_callapp_account(acc_id)
        if success:
            await callback_query.answer("Account deleted.")
            await send_callapp_list(callback_query, page)
        else:
            await callback_query.answer("Failed to delete account.", show_alert=True)
