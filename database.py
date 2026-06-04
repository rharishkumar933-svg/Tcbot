
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import config

client = AsyncIOMotorClient(config.MONGO_URI)
db = client['truecaller_bot']

users_col = db['users']
stats_col = db['stats']
settings_col = db['settings']
ads_col = db['ads']
callapp_col = db['callapp_accounts']

async def get_user(user_id):
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "join_date": datetime.now(),
            "search_count_today": 0,
            "total_searches": 0,
            "last_search_date": datetime.now().date().isoformat(),
            "last_ad_view_date": None,
            "is_banned": False
        }
        await users_col.insert_one(user)
    
    # Reset daily limit if it's a new day
    today = datetime.now().date().isoformat()
    if user.get("last_search_date") != today:
        await users_col.update_one(
            {"user_id": user_id},
            {"$set": {"search_count_today": 0, "last_search_date": today}}
        )
        user["search_count_today"] = 0
        
    return user

async def increment_search(user_id):
    await users_col.update_one(
        {"user_id": user_id},
        {"$inc": {"search_count_today": 1, "total_searches": 1}}
    )
    await stats_col.update_one(
        {"_id": "global_stats"},
        {"$inc": {"total_searches": 1}},
        upsert=True
    )

async def set_ads_viewed(user_id):
    today = datetime.now().date().isoformat()
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"last_ad_view_date": today}}
    )
    # Increment total global ad views
    await stats_col.update_one(
        {"_id": "global_stats"},
        {"$inc": {"total_ads_viewed": 1}},
        upsert=True
    )

async def get_stats():
    total_users = await users_col.count_documents({})
    today = datetime.now().date().isoformat()
    new_users_today = await users_col.count_documents({"join_date": {"$gte": datetime.combine(datetime.now().date(), datetime.min.time())}})
    global_stats = await stats_col.find_one({"_id": "global_stats"}) or {"total_searches": 0, "total_ads_viewed": 0}
    
    return {
        "total_users": total_users,
        "new_users_today": new_users_today,
        "total_searches": global_stats.get("total_searches", 0),
        "total_ads_viewed": global_stats.get("total_ads_viewed", 0)
    }

# --- Ads Management ---

async def add_ad(title, chat_id, message_id):
    await ads_col.insert_one({
        "title": title,
        "chat_id": chat_id,
        "message_id": message_id
    })

async def get_all_ads():
    return await ads_col.find({}).to_list(length=100)

async def get_ad(ad_id):
    from bson.objectid import ObjectId
    return await ads_col.find_one({"_id": ObjectId(ad_id)})

async def delete_ad(ad_id):
    from bson.objectid import ObjectId
    await ads_col.delete_one({"_id": ObjectId(ad_id)})

async def get_random_ad():
    count = await ads_col.count_documents({})
    if count == 0:
        return None
    import random
    cursor = ads_col.find({}).skip(random.randint(0, count - 1)).limit(1)
    ads = await cursor.to_list(length=1)
    return ads[0] if ads else None

async def ads_enabled():
    settings = await settings_col.find_one({"_id": "ads_settings"})
    return settings.get("ads_enabled", True) if settings else True

async def toggle_ads(enabled):
    await settings_col.update_one({"_id": "ads_settings"}, {"$set": {"ads_enabled": enabled}}, upsert=True)

async def get_ad_timer():
    settings = await settings_col.find_one({"_id": "ads_settings"})
    return settings.get("ad_timer", 0) if settings else 0

async def set_ad_timer(seconds):
    await settings_col.update_one({"_id": "ads_settings"}, {"$set": {"ad_timer": seconds}}, upsert=True)

# --- Ban Management ---

async def ban_user(user_id):
    await users_col.update_one({"user_id": user_id}, {"$set": {"is_banned": True}}, upsert=True)

async def unban_user(user_id):
    await users_col.update_one({"user_id": user_id}, {"$set": {"is_banned": False}}, upsert=True)

async def is_banned(user_id):
    user = await users_col.find_one({"user_id": user_id})
    return user.get("is_banned", False) if user else False

# --- Forcesub Management ---

async def forcesub_enabled():
    settings = await settings_col.find_one({"_id": "forcesub_settings"})
    return settings.get("forcesub_enabled", True) if settings else True

async def toggle_forcesub(enabled):
    await settings_col.update_one({"_id": "forcesub_settings"}, {"$set": {"forcesub_enabled": enabled}}, upsert=True)

# --- CallApp Account Management ---

async def add_callapp_account(params):
    # Check if already exists based on myp and tk
    existing = await callapp_col.find_one({"myp": params["myp"], "tk": params["tk"]})
    if existing:
        return False, "Account already exists."
    
    account = {
        "myp": params["myp"],
        "ibs": params["ibs"],
        "cid": params["cid"],
        "tk": params["tk"],
        "cvc": params["cvc"],
        "request_count": 0,
        "last_used": None,
        "added_at": datetime.now()
    }
    await callapp_col.insert_one(account)
    return True, "Account added successfully."

async def get_all_callapp_accounts():
    return await callapp_col.find({}).sort("added_at", 1).to_list(length=1000)

async def delete_callapp_account(account_id):
    from bson.objectid import ObjectId
    try:
        await callapp_col.delete_one({"_id": ObjectId(account_id)})
        return True
    except:
        return False

async def get_next_callapp_account():
    # find_one_and_update is atomic. It finds the oldest used account 
    # and updates its last_used timestamp instantly so the next 
    # request will pick a different account.
    account = await callapp_col.find_one_and_update(
        filter={},
        sort=[("last_used", 1)],
        update={"$set": {"last_used": datetime.now()}},
        return_document=True
    )
    return account

async def increment_callapp_request(account_id):
    # We only increment the counter here since last_used was 
    # already updated atomically in get_next_callapp_account.
    await callapp_col.update_one(
        {"_id": account_id},
        {"$inc": {"request_count": 1}}
    )
