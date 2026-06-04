
import asyncio
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant
from pyrogram.enums import ChatMemberStatus
import config
from datetime import datetime
from database import get_user, increment_search, ads_enabled, set_ads_viewed, get_random_ad, get_next_callapp_account, increment_callapp_request, get_ad_timer, forcesub_enabled
import re
import phonenumbers
from phonenumbers import geocoder, carrier as ph_carrier, timezone, number_type
import pycountry
import time

def get_country_flag(iso):
    return ''.join(chr(127397 + ord(c)) for c in iso.upper()) if iso else ""

async def fetch_eyecon(session, number_digits):
    try:
        params = {
            "cli": number_digits,
            "lang": "en",
            "is_callerid": "true",
            "is_ic": "true",
            "cv": config.EYECON_CV,
            "requestApi": "URLConnection",
            "source": "OnBoardingView"
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
            "accept": "application/json",
            "e-auth-v": config.EYECON_AUTH_V,
            "e-auth": config.EYECON_AUTH,
            "e-auth-c": config.EYECON_AUTH_C,
            "e-auth-k": config.EYECON_AUTH_K,
            "accept-charset": "UTF-8",
            "content-type": "application/x-www-form-urlencoded; charset=utf-8",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip"
        }
        async with session.get("https://api.eyecon-app.com/app/getnames.jsp", params=params, headers=headers, timeout=10) as r:
            if r.status == 200:
                data = await r.json()
                if isinstance(data, list) and data:
                    return data[0].get("name", "")
    except Exception:
        pass
    return ""

async def fetch_callapp(session, number_digits, acc=None):
    try:
        if acc:
            params = {
                "cpn": f"+{number_digits}",
                "myp": acc["myp"],
                "ibs": acc["ibs"],
                "cid": acc["cid"],
                "tk": acc["tk"],
                "cvc": acc["cvc"]
            }
        else:
            params = {
                "cpn": f"+{number_digits}",
                "myp": config.CALLAPP_MYP,
                "ibs": config.CALLAPP_IBS,
                "cid": config.CALLAPP_CID,
                "tk": config.CALLAPP_TK,
                "cvc": config.CALLAPP_CVC
            }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip"
        }
        async with session.get("https://s.callapp.com/callapp-server/csrch", params=params, headers=headers, timeout=10) as r:
            if r.status == 200:
                data = await r.json()
                return data.get("name", "")
    except Exception:
        pass
    return ""

async def fetch_payrup(session, number_digits):
    try:
        # Payrup uses last 10 digits for Indian numbers usually
        num = number_digits[-10:]
        async with session.post("https://api.payrup.com/api/prepaid/lookup", json={"phoneNumber": num}, headers={"Content-Type": "application/json"}, timeout=10) as r:
            if r.status == 200:
                data = await r.json()
                if data.get("status") and data.get("result"):
                    return data["result"].get("operator", ""), data["result"].get("circle", "")
    except Exception:
        pass
    return "", ""

async def is_subscribed(client, user_id):
    if not config.CHANNEL_ID:
        return True
    if not await forcesub_enabled():
        return True
    try:
        member = await client.get_chat_member(config.CHANNEL_ID, user_id)
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except UserNotParticipant:
        return False
    except Exception:
        return True # Default to True if error to avoid blocking users unnecessarily


@Client.on_message(filters.text & filters.private & ~filters.me & ~filters.command(["start", "admin", "stats", "broadcast", "ads", "adslist", "forcesub", "ban", "unban"]))
async def search_number(client: Client, message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    
    # Check if banned
    if user.get("is_banned"):
        return await message.reply_text("**❌ You are banned from using this bot!**")
    
    # Check force sub
    if not await is_subscribed(client, user_id):
        join_btn = InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel", url=config.CHANNEL_LINK)]])
        return await message.reply_text(
            "⚠️ **You must join our channel to use this bot! After joining, please send the number again to search.**",
            reply_markup=join_btn
        )

    user = await get_user(user_id)
    
    # Check daily limit
    if user["search_count_today"] >= config.DAILY_LIMIT:
        return await message.reply_text(f"❌ You have reached your daily limit of {config.DAILY_LIMIT} searches!")

    # Clean number
    input_text = message.text.strip().replace(" ", "").replace("(", "").replace(")", "").replace("-", "")
    
    # Remove leading 0 if present
    if input_text.startswith("0") and len(input_text) > 1:
        input_text = input_text[1:]
        
    has_plus = input_text.startswith("+")
    raw_number = input_text.replace("+", "")
    
    if not raw_number.isdigit():
        return await message.reply_text("**⛔️ Invalid number, Please enter valid one.**")

    # Parsing Logic
    if len(raw_number) == 10 and not has_plus:
        full_number = "91" + raw_number
    else:
        full_number = raw_number

    msg = await message.reply_text("🔍 Searching...")

    start_time = time.perf_counter()

    # Fetch Data from various sources
    async with aiohttp.ClientSession() as session:
        # Get next callapp account
        ca_acc = await get_next_callapp_account()
        
        eyecon_task = fetch_eyecon(session, full_number)
        callapp_task = fetch_callapp(session, full_number, ca_acc)
        payrup_task = fetch_payrup(session, full_number)
        
        eyecon_name, callapp_name, payrup_info = await asyncio.gather(eyecon_task, callapp_task, payrup_task)
        
        if ca_acc and callapp_name:
            await increment_callapp_request(ca_acc["_id"])
    
    carrier_payrup, location_payrup = payrup_info

    end_time = time.perf_counter()
    print(f"Function execution time: {end_time - start_time:.4f} seconds")
    
    # Common Phone Info
    country_display = "Unknown"
    timezone_display = ""
    carrier_ph = "Not found"
    location_ph = "Not found"
    
    try:
        parsed_num = phonenumbers.parse("+" + full_number)
        iso = phonenumbers.region_code_for_number(parsed_num)
        if iso:
            c = pycountry.countries.get(alpha_2=iso)
            if c:
                country_display = f"{c.name} {get_country_flag(iso)}"
            
        tz = timezone.time_zones_for_number(parsed_num)
        if tz and tz[0] != "Etc/Unknown":
            timezone_display = tz[0]
            
        carrier_ph = ph_carrier.name_for_number(parsed_num, "en") or "Not found"
        location_ph = geocoder.description_for_number(parsed_num, "en") or "Not found"
    except:
        pass

    # Server 1 is more accurate (Eyecon + Payrup/Phonenumbers)
    server1_name = eyecon_name or "Not found"
    server1_carrier = (carrier_payrup if full_number.startswith("91") else carrier_ph) or "Not found"
    server1_location = (location_payrup if full_number.startswith("91") else location_ph) or "Not found"
    
    # Server 2 (CallApp + Phonenumbers)
    server2_name = callapp_name or "Not found"
    # Old source info was using phonenumbers carrier which is "less accurate" for India
    server2_carrier = carrier_ph 
    server2_location = location_ph

    response_text = (
        f"**Number: `+{full_number}`**\n"
        f"**Country: `{country_display}`**\n\n"
        "**Server 1 :**\n\n"
        f"**Name: `{server1_name}`**\n"
        f"**Carrier: `{server1_carrier}`**\n"
        f"**TimeZone: `{timezone_display}`**\n"
        f"**Location: `{server1_location}`**\n\n"
        "**Server 2 :**\n\n"
        f"**Name: `{server2_name}`**\n"
        f"**Carrier: `{server2_carrier}`**\n"
        f"**Location: `{server2_location}`**\n\n"
        f"**[WhatsApp](https://wa.me/+{full_number}) | [Telegram](https://t.me/+{full_number})**"
    )

    await msg.edit_text(response_text, disable_web_page_preview=True)
    await increment_search(user_id)

    # Show Ads if first search of the day
    today = datetime.now().date().isoformat()
    if user.get("last_ad_view_date") != today:
        if await ads_enabled():
            ad = await get_random_ad()
            if ad:
                try:
                    ad_msg = await client.copy_message(user_id, ad['chat_id'], ad['message_id'])
                    await set_ads_viewed(user_id)
                    
                    # Auto-delete logic
                    timer = await get_ad_timer()
                    if timer > 0:
                        asyncio.create_task(delete_after(ad_msg, timer))
                except Exception:
                    pass

async def delete_after(message: Message, seconds: int):
    await asyncio.sleep(seconds)
    try:
        await message.delete()
    except Exception:
        pass
