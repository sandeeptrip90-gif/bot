import os
import json
import asyncio
import logging
from datetime import datetime
from threading import Thread
from flask import Flask

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, ChatMemberHandler 
from telegram.error import Forbidden, RetryAfter

# ================= LOGGING =================
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= FLASK =================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

Thread(target=run_web, daemon=True).start()

# ================= CONFIG =================
TOKEN = os.environ.get('TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
CONFIG_FILE = "config.json"

DEFAULT = {
    "groups": [],
    "auto_msg_id": None,
    "from_chat_id": None,
    "interval": 120,
    "night_start": 23,
    "night_end": 7,
    "active": False
}

def load():
    if not os.path.exists(CONFIG_FILE):
        save(DEFAULT)
    return json.load(open(CONFIG_FILE))

def save(data):
    json.dump(data, open(CONFIG_FILE, "w"), indent=2)

config = load()
JOB_NAME = "auto_broadcast_job"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== FLASK (UPTIME ROBOT) ==================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

Thread(target=run_web, daemon=True).start()

# ================== CONFIG ==================
DEFAULT_CONFIG = {
    "groups": [],
    "auto_msg_id": None,
    "from_chat_id": None,
    "interval": 120,
    "night_start": 23,
    "night_end": 7,
    "active": False
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

config = load_config()

# ================== HELPERS ==================
def is_admin(update: Update):
    return update.effective_user and update.effective_user.id == ADMIN_ID

def night_mode():
    hour = datetime.now().hour
    ns, ne = config["night_start"], config["night_end"]
    return (hour >= ns or hour < ne) if ns > ne else (ns <= hour < ne)

# ================== AUTO GROUP TRACKER ==================
async def track_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat:
        return

    # ✅ ONLY allow groups & supergroups
    if chat.type not in ("group", "supergroup"):
        return

    new_status = update.my_chat_member.new_chat_member.status

    if new_status in ("member", "administrator"):
        if chat.id not in config["groups"]:
            config["groups"].append(chat.id)
            save_config(config)

    elif new_status in ("left", "kicked"):
        if chat.id in config["groups"]:
            config["groups"].remove(chat.id)
            save_config(config)

# ================== AUTO JOB ==================
async def auto_job(context: ContextTypes.DEFAULT_TYPE):
    if not config["active"] or not config["auto_msg_id"]:
        return

    if night_mode():
        logger.info("Night mode active")
        return

    logger.info("AUTO JOB RUNNING")

    for gid in config["groups"]:
        try:
            # 🔒 SAFETY: skip non-group chats (private / channels)
            chat = await context.bot.get_chat(gid)
            if chat.type not in ("group", "supergroup"):
                logger.warning(f"Skipping non-group chat: {gid}")
                continue

            await context.bot.copy_message(
                chat_id=gid,
                from_chat_id=config["from_chat_id"],
                message_id=config["auto_msg_id"]
            )

            await asyncio.sleep(0.5)

        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)

        except Exception as e:
            logger.warning(f"Auto failed {gid}: {e}")


# ================== JOB RESTART ==================
async def restart_auto_job(application: Application):
    jq = application.job_queue
    if not jq:
        return

    for job in jq.get_jobs_by_name(JOB_NAME):
        job.schedule_removal()

    jq.run_repeating(
        auto_job,
        interval=config["interval"] * 60,
        first=5,
        name=JOB_NAME
    )

# ================== COMMANDS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    await update.message.reply_text(
        "🛠 ADMIN PANEL\n\n"
        "/setauto (reply)\n"
        "/autoon /autooff\n"
        "/settings <mins> <night_start> <night_end>\n"
        "/status\n\n"
        "/broadcast (reply)\n"
        "/stats"
    )

async def setauto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update) or not update.message.reply_to_message:
        return await update.message.reply_text("Reply to a message")

    config["auto_msg_id"] = update.message.reply_to_message.message_id
    config["from_chat_id"] = update.message.chat_id
    config["active"] = True
    save_config(config)

    await restart_auto_job(context.application)
    await update.message.reply_text("✅ Auto message set")

async def autoon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    config["active"] = True
    save_config(config)
    await restart_auto_job(context.application)
    await update.message.reply_text("▶️ Auto ON")

async def autooff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    config["active"] = False
    save_config(config)
    await update.message.reply_text("⏸ Auto OFF")

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    try:
        config["interval"] = int(context.args[0])
        config["night_start"] = int(context.args[1])
        config["night_end"] = int(context.args[2])
        save_config(config)
        await restart_auto_job(context.application)
        await update.message.reply_text("⚙️ Settings updated")
    except:
        await update.message.reply_text("Usage: /settings 1 0 0")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    await update.message.reply_text(
        f"Active: {config['active']}\n"
        f"Groups: {len(config['groups'])}\n"
        f"Interval: {config['interval']} min\n"
        f"Night: {config['night_start']} → {config['night_end']}"
    )

#--BROADCAST---------
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update) or not update.message.reply_to_message:
        return

    sent = 0
    for gid in config["groups"]:
        try:
            chat = await context.bot.get_chat(gid)
            if chat.type not in ("group", "supergroup"):
                continue

            await context.bot.copy_message(
                chat_id=gid,
                from_chat_id=update.message.reply_to_message.chat_id,
                message_id=update.message.reply_to_message.message_id
            )
            sent += 1
            await asyncio.sleep(0.5)

        except Exception as e:
            logger.warning(f"Broadcast failed {gid}: {e}")

    await update.message.reply_text(f"✅ Broadcast sent to {sent} groups")


#---PINNED---------

async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update) or not update.message.reply_to_message:
        return

    success = 0
    for gid in config["groups"]:
        try:
            chat = await context.bot.get_chat(gid)
            if chat.type not in ("group", "supergroup"):
                continue

            msg = await context.bot.copy_message(
                chat_id=gid,
                from_chat_id=update.message.reply_to_message.chat_id,
                message_id=update.message.reply_to_message.message_id
            )

            await context.bot.pin_chat_message(
                chat_id=gid,
                message_id=msg.message_id,
                disable_notification=True
            )

            success += 1
            await asyncio.sleep(0.5)

        except Exception as e:
            logger.warning(f"Pin failed {gid}: {e}")

    await update.message.reply_text(f"📌 Pinned in {success} groups")

#-----UNPINNED---------

async def unpinall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    done = 0
    for gid in config["groups"]:
        try:
            chat = await context.bot.get_chat(gid)
            if chat.type not in ("group", "supergroup"):
                continue

            await context.bot.unpin_all_chat_messages(chat_id=gid)
            done += 1
            await asyncio.sleep(0.3)

        except Exception as e:
            logger.warning(f"Unpin failed {gid}: {e}")

    await update.message.reply_text(f"🧹 Unpinned all messages in {done} groups")


#-----INFO-------

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    text = "📊 Group Info\n\n"
    for gid in config["groups"]:
        try:
            chat = await context.bot.get_chat(gid)
            if chat.type not in ("group", "supergroup"):
                continue

            members = await context.bot.get_chat_member_count(gid)
            text += f"• {chat.title}: {members}\n"

        except Exception as e:
            text += f"• {gid}: ❌\n"

    await update.message.reply_text(text)

#----STATS-------

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text(
        f"📊 Total groups: {len(config['groups'])}"
    )


#-----HELP------

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    help_text = (
        "🛠 **BOT HELP MENU**\n\n"

        "♻️ **Auto Broadcast**\n"
        "/setauto – Reply to a message to set auto message\n"
        "/autoon – Turn auto broadcast ON\n"
        "/autooff – Turn auto broadcast OFF\n"
        "/settings <mins> <night_start> <night_end>\n"
        "  Example: /settings 1 0 0\n"
        "/status – Show auto broadcast status\n\n"

        "📢 **Manual Broadcast & Manage**\n"
        "/broadcast – Reply to send message to all groups\n"
        "/pin – Reply to send & pin message in all groups\n"
        "/unpinall – Remove all pinned messages\n"
        "/info – Show group names & member count\n\n"

        "📊 **Stats & Info**\n"
        "/stats – Total number of groups\n\n"

        "🤖 **Notes**\n"
        "• Bot auto-detects groups\n"
        "• Bot must be admin in groups\n"
        "• Supports text, photo, video, voice, files\n"
        "• Night mode respected automatically"
    )

    await update.message.reply_text(help_text, parse_mode="Markdown")


# ================== MAIN ==================
def main():
    application = Application.builder().token(TOKEN).build()

    # 🔹 AUTO GROUP DETECTION
    application.add_handler(
        ChatMemberHandler(track_groups, ChatMemberHandler.MY_CHAT_MEMBER)
    )

    # 🔹 COMMAND HANDLERS (REGISTER ONCE ONLY)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setauto", setauto))
    application.add_handler(CommandHandler("autoon", autoon))
    application.add_handler(CommandHandler("autooff", autooff))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CommandHandler("status", status))

    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("pin", pin))
    application.add_handler(CommandHandler("unpinall", unpinall))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(CommandHandler("stats", stats))

    # 🔹 AUTO JOB START (JobQueue)
    if application.job_queue:
        application.job_queue.run_repeating(
            auto_job,
            interval=config["interval"] * 60,
            first=10,
            name=JOB_NAME
        )

    # 🔹 START BOT
    application.run_polling(
        drop_pending_updates=True,
        close_loop=False
    )


if __name__ == "__main__":
    main()
