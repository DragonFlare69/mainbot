import json
import os
import random
import string
import time
from datetime import datetime, timedelta
import asyncio
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ConversationHandler,
    filters,
)
import pytz

logging.getLogger("httpx").setLevel(logging.WARNING)

TOKEN = "7599940827:AAFXTVWfMk6KQUei0D6T_BsHYIQ_iS-D1UU"  # Replace this with your actual bot token
ADMIN_ID = 5479920814

DATA_FILE = "data.json"
BACKUP_FILE = "backup_data.json"
MAX_CHANNELS = 150
INVITE_EXPIRY_SECONDS = 300
RENEW_THRESHOLD_SECONDS = 10

ADD_CHANNEL = 1
DEL_CHANNEL = 2
DEL_ALL_CONFIRM = 3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def atomic_save(file_path, data):
    try:
        temp_path = file_path + ".tmp"
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=4)
        os.replace(temp_path, file_path)
    except Exception as e:
        logger.error(f"❌ Failed to save {file_path}: {e}")

def load_data():
    try:
        if not os.path.exists(DATA_FILE):
            return {}
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Failed to load data.json: {e}")
        if os.path.exists(BACKUP_FILE):
            try:
                with open(BACKUP_FILE, "r") as f:
                    return json.load(f)
            except Exception as e2:
                logger.error(f"❌ Failed to load backup: {e2}")
        return {}

def save_data(data):
    atomic_save(DATA_FILE, data)

def backup_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                content = f.read()
            with open(BACKUP_FILE + ".tmp", "w") as f:
                f.write(content)
            os.replace(BACKUP_FILE + ".tmp", BACKUP_FILE)
            logger.info("✅ Backup created.")
    except Exception as e:
        logger.error(f"❌ Failed to backup data: {e}")

async def periodic_backup():
    while True:
        await asyncio.sleep(3600)
        backup_data()

def generate_code(length=8, existing_codes=None):
    while True:
        code = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
        if existing_codes is None or code not in existing_codes:
            return code

async def get_or_create_invite(context, channel_id, current_time):
    data = load_data()
    details = data.get(channel_id)
    if not details:
        logger.warning(f"⚠️ Channel {channel_id} not found in data.json.")
        return None, 0

    invite_info = details.get("invite_info", {})
    link = invite_info.get("link")
    expiry = invite_info.get("expiry", 0)

    if link and current_time < expiry and expiry - current_time > RENEW_THRESHOLD_SECONDS:
        return link, expiry

    try:
        new_invite = await context.bot.create_chat_invite_link(
            chat_id=int(channel_id),
            expire_date=current_time + INVITE_EXPIRY_SECONDS,
            creates_join_request=True
        )
        invite_link = new_invite.invite_link
        expiry = current_time + INVITE_EXPIRY_SECONDS
        details["invite_info"] = {"link": invite_link, "expiry": expiry}
        save_data(data)
        return invite_link, expiry
    except Exception as e:
        logger.error(f"❌ Error creating invite for {channel_id}: {e}")
        return None, 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.effective_user.is_bot:
        return

    args = context.args
    data = load_data()

    if args:
        code = args[0]
        for channel_id, details in data.items():
            if details.get("code") == code:
                current_time = int(time.time())
                invite_link, expiry = await get_or_create_invite(context, channel_id, current_time)
                if invite_link:
                    keyboard = [[InlineKeyboardButton("🔔 Request to Join", url=invite_link)]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text("Here is your link! Click below 👇", reply_markup=reply_markup)
                else:
                    await update.message.reply_text("❗ Failed to create invite link. Ensure the bot is admin with invite permissions.")
                return
        await update.message.reply_text("⚠️ Invalid code or channel not found.")
    else:
        if user_id != ADMIN_ID:
            await update.message.reply_text("🚫 You are not authorized to use this bot. Please buy your own bot from - @Zenxuuh")
        else:
            await update.message.reply_text("👑 Welcome, Admin! Use /help to see available commands.")

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 You are not authorized to use this bot. Please buy your own bot from - @Zenxuuh")
        return ConversationHandler.END

    if context.user_data.get("state") is not None:
        await update.message.reply_text("⚠️ You're already in a command. Please /cancel it before starting a new one.")
        return ConversationHandler.END

    context.user_data["state"] = "add"
    await update.message.reply_text("📅 Send me the channel UID (must start with '-100').")
    return ADD_CHANNEL

async def receive_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_id = update.message.text.strip()
    data = load_data()

    if not channel_id.startswith("-100") or not channel_id[1:].isdigit():
        await update.message.reply_text("❗ Invalid ID. Format must be -100 followed by digits.")
        context.user_data.pop("state", None)
        return ConversationHandler.END

    if len(data) >= MAX_CHANNELS:
        await update.message.reply_text("❗ You have reached the maximum channel limit (150).")
        context.user_data.pop("state", None)
        return ConversationHandler.END

    if channel_id in data:
        await update.message.reply_text("⚠️ Channel already exists.")
        context.user_data.pop("state", None)
        return ConversationHandler.END

    existing_codes = {info["code"] for info in data.values()}
    code = generate_code(existing_codes=existing_codes)
    data[channel_id] = {
        "code": code,
        "invite_info": {}
    }
    save_data(data)

    bot_username = context.bot.username or (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={code}"
    await update.message.reply_text(f"✅ Channel added!\n\nUnique link: {referral_link}")
    context.user_data.pop("state", None)
    return ConversationHandler.END

async def delete_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 You are not authorized to use this bot.")
        return ConversationHandler.END

    if context.user_data.get("state") is not None:
        await update.message.reply_text("⚠️ You're already in a command. Please /cancel it before starting a new one.")
        return ConversationHandler.END

    context.user_data["state"] = "delete"
    await update.message.reply_text("🗑️ Please send the Channel UID you want to delete.")
    return DEL_CHANNEL

async def confirm_delete_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_id = update.message.text.strip()
    data = load_data()

    if channel_id in data:
        del data[channel_id]
        save_data(data)
        await update.message.reply_text("✅ Channel has been deleted.")
    else:
        await update.message.reply_text("⚠️ Channel not found.")

    context.user_data.pop("state", None)
    return ConversationHandler.END

async def delete_all_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 You are not authorized to use this bot.")
        return ConversationHandler.END

    if context.user_data.get("state") is not None:
        await update.message.reply_text("⚠️ You're already in a command. Please /cancel it before starting a new one.")
        return ConversationHandler.END

    data = load_data()
    if not data:
        await update.message.reply_text("⚠️ No channels to delete.")
        return ConversationHandler.END

    context.user_data["state"] = "delall"
    await update.message.reply_text("⚠️ Are you sure you want to delete all channels? Type 'yes' to confirm.")
    return DEL_ALL_CONFIRM

async def confirm_delete_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower().strip() == "yes":
        save_data({})
        await update.message.reply_text("🧹 All channels have been deleted.")
    else:
        await update.message.reply_text("❌ Operation cancelled.")
    context.user_data.pop("state", None)
    return ConversationHandler.END

async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 You are not authorized to use this bot.")
        return

    data = load_data()
    if not data:
        await update.message.reply_text("⚠️ No channels added yet.")
        return

    bot_username = context.bot.username or (await context.bot.get_me()).username
    lines = []
    for channel_id, details in data.items():
        code = details.get("code")
        link = f"https://t.me/{bot_username}?start={code}"
        lines.append(f"• Channel ID: `{channel_id}`\n  Link: {link}\n")

    message = "📋 *Channels List:*\n\n"
    chunk = message
    for line in lines:
        if len(chunk) + len(line) >= 4000:
            await update.message.reply_text(chunk, parse_mode="Markdown")
            chunk = message
        chunk += line
    if chunk.strip() != message.strip():
        await update.message.reply_text(chunk, parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("state", None)
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 You are not authorized to use this bot.")
        return

    help_text = (
        "*🛠 Admin Commands:*\n\n"
        "➕ /add – Add a new channel\n"
        "➖ /del – Delete a specific channel\n"
        "🗑️ /delall – Delete all channels\n"
        "📋 /list – List all channels\n"
        "❌ /cancel – Cancel the current action\n"
        "ℹ️ /help – Show this help menu"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

def main():
    app = Application.builder().token(TOKEN).build()

    async def startup(_: Application):
        await app.bot.delete_webhook(drop_pending_updates=True)
        asyncio.create_task(periodic_backup())

    app.post_init = startup

    add_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add_channel)],
        states={ADD_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_channel_id)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    delete_handler = ConversationHandler(
        entry_points=[CommandHandler("del", delete_channel)],
        states={DEL_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete_channel)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    delall_handler = ConversationHandler(
        entry_points=[CommandHandler("delall", delete_all_channels)],
        states={DEL_ALL_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete_all)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(add_handler)
    app.add_handler(delete_handler)
    app.add_handler(delall_handler)
    app.add_handler(CommandHandler("list", list_channels))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))

    logger.info("🚀 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
