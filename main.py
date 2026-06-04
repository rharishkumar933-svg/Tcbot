
from pyrogram import Client, filters
import config

app = Client(
    "truecaller_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    plugins=dict(root="plugins"),
    in_memory=True
)

if __name__ == "__main__":
    print("Bot started...")
    app.run()
