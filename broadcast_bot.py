import asyncio
import os
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes
)
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive"

def run_web():
    app.run(
        host="0.0.0.0",
        port=8080,
        debug=False,
        use_reloader=False
    )

def start_web():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()



print("🚀 Bot file loaded successfully")

# =====================================================
# 🔐 BASIC CONFIG
# =====================================================

TOKEN = os.environ.get('TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))

# =====================================================
# 🧩 MANUAL GROUP IDS (ADD ALL GROUP IDS HERE)
# =====================================================

GROUP_IDS = [-1002236012208, -1002417345407, -1002330831798, -1001882254820, -1002295951659, -1002350372764, -1002408686476, -1002458796542, -1002459378218, -1001787331133, -1001797945922, -1001843610820, -1002052681893, -1002126246859, -1001509387207, -1001738062150, -1001587346978, -1001829615017, -1002083172621, -1002411884866, -1001567747819, -1002254648501, -1003366623406, -1002283304339, -4557532425, -1001637428890, -1002299671203, -1002568461287, -1002538473462]

# =====================================================
# ⚙️ AUTO BROADCAST SETTINGS (IN-MEMORY, NO JSON)
# =====================================================

config = {
    "auto_msg_id": None,
    "from_chat_id": None,
    "is_active": False,
    "interval_mins": 1,   # default 1 minute
    "night_start": 23,
    "night_end": 7
}

# =====================================================
# 🛡 HELPERS
# =====================================================

def is_admin(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ADMIN_ID


def night_mode() -> bool:
    hour = datetime.now().hour
    ns = config["night_start"]
    ne = config["night_end"]

    if ns > ne:  # example: 23 to 7
        return hour >= ns or hour < ne
    else:
        return ns <= hour < ne

# =====================================================
# 🔁 AUTO BROADCAST JOB
# =====================================================

async def auto_broadcast_job(context: ContextTypes.DEFAULT_TYPE):
    print("🔁 Auto job triggered")

    if not config["is_active"]:
        print("⏸ Auto broadcast OFF, skipping")
        return

    if not config["auto_msg_id"]:
        print("⚠️ No auto message set")
        return

    if night_mode():
        print("🌙 Night mode active, skipping")
        return

    for gid in GROUP_IDS:
        try:
            print(f"📤 Sending message to group {gid}")
            await context.bot.copy_message(
                chat_id=gid,
                from_chat_id=config["from_chat_id"],
                message_id=config["auto_msg_id"]
            )
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"❌ Failed for {gid}: {e}")

# =====================================================
# 🛠 COMMANDS
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await help_command(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    text = (
        "🛠 **BOT HELP MENU**\n\n"
        "♻️ **Auto Broadcast**\n"
        "/setauto – Reply to a message to set auto message\n"
        "/autoon – Turn auto broadcast ON\n"
        "/autooff – Turn auto broadcast OFF\n"
        "/settings <mins> <nightstart> <nightend>\n"
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
        "• Groups are MANUALLY added in code\n"
        "• Bot must be admin in groups\n"
        "• Supports text, photo, video, voice, files\n"
        "• Night mode respected automatically"
    )

    await update.message.reply_text(text, parse_mode="Markdown")


# ================= AUTO CONTROLS =================

async def setauto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    print("📝 /setauto command used")

    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Reply to a message.")

    config["auto_msg_id"] = update.message.reply_to_message.message_id
    config["from_chat_id"] = update.message.chat_id
    config["is_active"] = True

    print("✅ Auto message configured")

    await update.message.reply_text("✅ Auto message set & activated.")



async def autoon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    config["is_active"] = True
    await update.message.reply_text("▶️ Auto broadcast ON.")


async def autooff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    config["is_active"] = False
    await update.message.reply_text("⏸ Auto broadcast OFF.")


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    try:
        # 1. Nayi values set karein
        config["interval_mins"] = int(context.args[0])
        config["night_start"] = int(context.args[1])
        config["night_end"] = int(context.args[2])

        # 2. Purane saare jobs ko 'name' se dhund kar hatayein
        current_jobs = context.job_queue.get_jobs_by_name('auto_broadcast')
        for job in current_jobs:
            job.schedule_removal()

        # 3. Naya job start karein (Interval fix)
        context.job_queue.run_repeating(
            auto_broadcast_job,
            interval=config["interval_mins"] * 60,
            first=10, # 10 seconds baad pehla message jayega
            name='auto_broadcast' # Name dena zaroori hai track karne ke liye
        )

        await update.message.reply_text(
            f"⚙️ **Settings Updated!**\n"
            f"⏱ Ab har {config['interval_mins']} minute mein message jayega.\n"
            f"🌙 Night Mode: {config['night_start']} se {config['night_end']} tak."
        )
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Usage: `/settings 56 23 7` (Minutes NightStart NightEnd)")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    
    active_jobs = context.job_queue.get_jobs_by_name('auto_broadcast')
    job_status = "RUNNING" if active_jobs else "STOPPED/NOT SET"
    
    msg = (
        f"📊 **Current Bot Status**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✅ Auto-Send: {'ON' if config['is_active'] else 'OFF'}\n"
        f"⏱ Interval: {config['interval_mins']} min\n"
        f"🌙 Night: {config['night_start']} to {config['night_end']}\n"
        f"🤖 Job Queue: {job_status}\n"
        f"✉️ Message Set: {'YES' if config['auto_msg_id'] else 'NO'}"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

# ================= MANUAL BROADCAST =================

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Reply to a message.")

    sent = 0
    for gid in GROUP_IDS:
        try:
            await context.bot.copy_message(
                gid,
                update.message.reply_to_message.chat_id,
                update.message.reply_to_message.message_id
            )
            sent += 1
            await asyncio.sleep(0.5)
        except Exception:
            pass

    await update.message.reply_text(f"✅ Sent to {sent} groups.")


async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Reply to a message.")

    success = 0
    for gid in GROUP_IDS:
        try:
            msg = await context.bot.copy_message(
                gid,
                update.message.reply_to_message.chat_id,
                update.message.reply_to_message.message_id
            )
            await context.bot.pin_chat_message(gid, msg.message_id)
            success += 1
            await asyncio.sleep(0.5)
        except Exception:
            pass

    await update.message.reply_text(f"📌 Pinned in {success} groups.")


async def unpinall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    done = 0
    for gid in GROUP_IDS:
        try:
            await context.bot.unpin_all_chat_messages(gid)
            done += 1
            await asyncio.sleep(0.3)
        except Exception:
            pass

    await update.message.reply_text(f"🧹 Unpinned in {done} groups.")


async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    text = "📊 Group Info\n\n"
    for gid in GROUP_IDS:
        try:
            chat = await context.bot.get_chat(gid)
            members = await context.bot.get_chat_member_count(gid)
            text += f"• {chat.title}: {members}\n"
        except Exception:
            text += f"• {gid}: ❌\n"

    await update.message.reply_text(text)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text(f"📊 Total groups: {len(GROUP_IDS)}")

# =====================================================
# 🚀 MAIN
# =====================================================

def main():

    start_web()
    print("🌐 Web server started")

    print("⚙️ Initializing bot...")

    app = Application.builder().token(TOKEN).build()

    print("✅ Bot connected to Telegram")

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("setauto", setauto))
    app.add_handler(CommandHandler("autoon", autoon))
    app.add_handler(CommandHandler("autooff", autooff))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("status", status))

    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("pin", pin))
    app.add_handler(CommandHandler("unpinall", unpinall))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("stats", stats))

    print(f"📌 Total groups loaded: {len(GROUP_IDS)}")
    print(f"📌 Group IDs: {GROUP_IDS}")

    app.job_queue.run_repeating(
        auto_broadcast_job,
        interval=config["interval_mins"] * 60,
        first=10
    )

    print("🤖 Bot is running...")
    app.run_polling(drop_pending_updates=True)


# 🔥🔥🔥 YAHAN LIKHNA HAI — FILE KE BILKUL END ME 🔥🔥🔥
if __name__ == "__main__":
    main()


