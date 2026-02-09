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

# Use a distinct name for the Flask app to avoid shadowing the Telegram
# Application object later named `telegram_app`.
flask_app = Flask(__name__)


@flask_app.route("/")
def home():
    return "Bot is alive"


def run_web():
    flask_app.run(
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

TOKEN = "8218945392:AAFI4b2_Yo9wXhQJFCL63vw8FHpOeefkHPU"
ADMIN_ID = 5599766250

# =====================================================
# 🧩 MANUAL GROUP IDS (ADD ALL GROUP IDS HERE)
# =====================================================

GROUP_IDS = [-1002236012208, -1002417345407, -1002330831798, -1001882254820, -1002295951659, -1002350372764, -1002408686476, -1002458796542, -1002459378218, -1001787331133, -1001797945922, -1001843610820, -1002052681893, -1002126246859, -1001509387207, -1001738062150, -1001587346978, -1001829615017, -1002083172621, -1002411884866, -1001567747819, -1002254648501, -1003366623406, -1002283304339, -4557532425, -1001637428890, -1002299671203, -1002568461287, -1002538473462]

# =====================================================
# ⚙️ AUTO BROADCAST SETTINGS (IN-MEMORY, NO JSON)

config = {
    "auto_msg_id": None,
    "from_chat_id": None,
    "is_active": False,
    "interval_mins": 1,   # default 1 minute
    "night_start": 23,
    "night_end": 7
}

# How many parallel staggered jobs to create
JOB_COUNT = 5
# Per-job runtime tracking
config.setdefault("jobs", {})

# Developer notes — How to create new jobs
# Option A — Use the built-in staggered auto jobs:
#   set JOB_COUNT = N and use /autoon to create jobs named auto_broadcast_1..N
# Option B — Create a custom job:
#   define async def my_job(context): ... and schedule with:
#     telegram_app.job_queue.run_repeating(my_job, interval=..., first=..., name='my_job')
#   remove with job.schedule_removal() or get by name via job_queue.get_jobs_by_name('my_job')
#
# Naming and tracking:
# - Built-in jobs use names `auto_broadcast_<n>`; pick unique names for custom jobs.
# - To track a custom job in `config['jobs']`, add an entry after scheduling.

# =====================================================
# 🛡 HELPERS

def is_admin(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ADMIN_ID


def night_mode() -> bool:
    hour = datetime.now().hour
    ns = config["night_start"]
    ne = config["night_end"]

    if ns > ne:  # example: 23 to 7
        return hour >= ns or hour <= (ne - 1)
    else:
        return ns <= hour < ne

# =====================================================
# 🔁 AUTO BROADCAST JOB
# =====================================================

# =====================================================
# 🔁 AUTO BROADCAST JOB (Modified with Logging)
# =====================================================

async def auto_broadcast_job(context: ContextTypes.DEFAULT_TYPE):
    # Timing check ke liye log
    now = datetime.now()
    hour = now.hour
    # Determine job name if available
    job_name = None
    try:
        job_name = context.job.name if getattr(context, 'job', None) else None
    except Exception:
        job_name = None

    print(f"🔁 Auto job triggered at: {now.strftime('%Y-%m-%d %H:%M:%S')} | job={job_name} | Night Start: {config['night_start']}, Night End: {config['night_end']}")

    if not config["is_active"]:
        print("⏸ Auto broadcast OFF, skipping")
        if job_name:
            config["jobs"].setdefault(job_name, {})
            config["jobs"][job_name]["last_run"] = now.isoformat()
            config["jobs"][job_name]["last_status"] = "skipped:global-off"
        return

    if not config["auto_msg_id"]:
        print("⚠️ No auto message set")
        if job_name:
            config["jobs"].setdefault(job_name, {})
            config["jobs"][job_name]["last_run"] = now.isoformat()
            config["jobs"][job_name]["last_status"] = "skipped:no-msg"
        return

    is_night = night_mode()
    print(f"📊 Current hour: {hour} | Night Mode: {is_night}")
    
    if is_night:
        print("🌙 Night mode active, skipping")
        if job_name:
            config["jobs"].setdefault(job_name, {})
            config["jobs"][job_name]["last_run"] = now.isoformat()
            config["jobs"][job_name]["last_status"] = "skipped:night"
        return

    print(f"📤 Sending message to {len(GROUP_IDS)} groups...")
    # record start
    if job_name:
        config["jobs"].setdefault(job_name, {})
        config["jobs"][job_name]["last_run"] = now.isoformat()
        config["jobs"][job_name]["last_status"] = "running"
    for gid in GROUP_IDS:
        try:
            await context.bot.copy_message(
                chat_id=gid,
                from_chat_id=config["from_chat_id"],
                message_id=config["auto_msg_id"]
            )
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"❌ Failed for {gid}: {e}")

    # after sending, try to record next run time if available
    if job_name:
        try:
            job_list = context.application.job_queue.get_jobs_by_name(job_name)
            if job_list:
                job = job_list[0]
                next_rt = getattr(job, 'next_run_time', getattr(job, 'next_t', None))
                config["jobs"][job_name]["next_run"] = next_rt.isoformat() if next_rt else None
                # store interval if present
                interval = getattr(job, 'interval', None)
                config["jobs"][job_name]["interval_secs"] = interval if interval else config.get("interval_mins", 0) * 60
        except Exception:
            pass

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

    # 1. State update
    config["is_active"] = True

    # 2. CLEAR PREVIOUS JOBS (Safety check to prevent overlap)
    job_base = 'auto_broadcast'
    for i in range(1, JOB_COUNT + 1):
        name = f"{job_base}_{i}"
        current_jobs = context.application.job_queue.get_jobs_by_name(name)
        for job in current_jobs:
            job.schedule_removal()
            print(f"Log: Cleaning up existing job '{name}' before turning ON.")

    # 3. FRESH START — create JOB_COUNT repeating jobs staggered across the interval
    interval_secs = config["interval_mins"] * 60
    for i in range(1, JOB_COUNT + 1):
        # stagger by distributing starts across the interval; add small base offset
        first = 10 + int((i - 1) * (interval_secs / JOB_COUNT))
        name = f"{job_base}_{i}"
        context.application.job_queue.run_repeating(
            auto_broadcast_job,
            interval=interval_secs,
            first=first,
            name=name
        )
        # initialize tracking record
        config["jobs"].setdefault(name, {})
        config["jobs"][name]["interval_secs"] = interval_secs
        config["jobs"][name]["next_run"] = None
        config["jobs"][name]["last_run"] = None
        config["jobs"][name]["last_status"] = "scheduled"

    print(f"Log: Scheduled {JOB_COUNT} staggered jobs every {config['interval_mins']} minute(s). Next run in ~10s for job 1.")

    await update.message.reply_text(
        f"▶️ **Auto Broadcast: ON**\n"
        f"⏱ Interval: {config['interval_mins']} min\n"
        f"🔄 Naya timer fresh start kar diya gaya hai."
    )
    print(f"Log: Auto broadcast turned ON and timer synchronized.")

async def autooff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    config["is_active"] = False
    # Remove all staggered jobs
    job_base = 'auto_broadcast'
    for i in range(1, JOB_COUNT + 1):
        name = f"{job_base}_{i}"
        current_jobs = context.application.job_queue.get_jobs_by_name(name)
        for job in current_jobs:
            job.schedule_removal()
            print(f"Log: Removed job '{name}' on autooff.")

        # mark stopped in tracking
        config["jobs"].setdefault(name, {})
        config["jobs"][name]["last_status"] = "stopped"

    await update.message.reply_text("⏸ Auto broadcast OFF and timers cleared.")


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    try:
        # 1. Nayi values store karein
        new_interval = int(context.args[0])
        config["interval_mins"] = new_interval
        config["night_start"] = int(context.args[1])
        config["night_end"] = int(context.args[2])

        # 2. CLEAR ALL PREVIOUS JOBS (Timing Fix)
        job_base = 'auto_broadcast'
        for i in range(1, JOB_COUNT + 1):
            name = f"{job_base}_{i}"
            current_jobs = context.application.job_queue.get_jobs_by_name(name)
            for job in current_jobs:
                job.schedule_removal()
                print(f"Log: Old job '{name}' removed to prevent overlap.")

        # START FRESH JOBS — staggered across one interval
        interval_secs = config["interval_mins"] * 60
        for i in range(1, JOB_COUNT + 1):
            # start times distributed within the next full interval
            first = int((i / JOB_COUNT) * interval_secs)
            name = f"{job_base}_{i}"
            context.application.job_queue.run_repeating(
                auto_broadcast_job,
                interval=interval_secs,
                first=first,
                name=name
            )
            # initialize tracking record
            config["jobs"].setdefault(name, {})
            config["jobs"][name]["interval_secs"] = interval_secs
            config["jobs"][name]["next_run"] = None
            config["jobs"][name]["last_run"] = None
            config["jobs"][name]["last_status"] = "scheduled"

        print(f"Log: Scheduled {JOB_COUNT} staggered jobs every {config['interval_mins']} minute(s). Next run in ~{config['interval_mins']}min window.")

        await update.message.reply_text(
            f"⚙️ **Settings Synced!**\n"
            f"⏱ Interval: {config['interval_mins']} min\n"
            f"🌙 Night: {config['night_start']} to {config['night_end']}\n"
            f"\nPurane saare timers clear kar diye gaye hain."
        )
        print(f"Log: New stable timer set for {config['interval_mins']} minutes.")

    except (IndexError, ValueError):
        await update.message.reply_text("❌ Usage: `/settings 56 23 7`")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    
    job_base = 'auto_broadcast'

    lines = []
    lines.append("📊 **Current Bot Status**")
    lines.append("━━━━━━━━━━━━━━━")
    lines.append(f"✅ Auto-Send: {'ON' if config['is_active'] else 'OFF'}")
    lines.append(f"⏱ Interval (mins): {config['interval_mins']}")
    lines.append(f"🌙 Night: {config['night_start']} to {config['night_end']}")
    lines.append(f"✉️ Message Set: {'YES' if config['auto_msg_id'] else 'NO'}")
    lines.append("")
    lines.append("🔁 Jobs:")

    for i in range(1, JOB_COUNT + 1):
        name = f"{job_base}_{i}"
        jobs = context.application.job_queue.get_jobs_by_name(name)
        exists = len(jobs) > 0
        next_run = None
        interval_secs = None
        if exists:
            job = jobs[0]
            next_run = getattr(job, 'next_run_time', getattr(job, 'next_t', None))
            interval_secs = getattr(job, 'interval', None)

        record = config.get("jobs", {}).get(name, {})
        last_run = record.get("last_run")
        last_status = record.get("last_status", "-")
        # prefer job object next_run if present
        next_run_str = next_run.isoformat() if next_run else (record.get("next_run") or "N/A")
        interval_str = f"{int(interval_secs)}s" if interval_secs else (f"{int(record.get('interval_secs',0))}s" if record.get('interval_secs') else "N/A")

        lines.append(f"• {name}: {'RUNNING' if exists else 'NOT RUNNING'}")
        lines.append(f"  - Next run: {next_run_str}")
        lines.append(f"  - Interval: {interval_str}")
        lines.append(f"  - Last run: {last_run or 'Never'}")
        lines.append(f"  - Last status: {last_status}")

    msg = "\n".join(lines)
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
    # Create Telegram Application instance and keep it separate from Flask
    telegram_app = Application.builder().token(TOKEN).build()

    print("✅ Bot connected to Telegram")

    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(CommandHandler("setauto", setauto))
    telegram_app.add_handler(CommandHandler("autoon", autoon))
    telegram_app.add_handler(CommandHandler("autooff", autooff))
    telegram_app.add_handler(CommandHandler("settings", settings))
    telegram_app.add_handler(CommandHandler("status", status))

    telegram_app.add_handler(CommandHandler("broadcast", broadcast))
    telegram_app.add_handler(CommandHandler("pin", pin))
    telegram_app.add_handler(CommandHandler("unpinall", unpinall))
    telegram_app.add_handler(CommandHandler("info", info))
    telegram_app.add_handler(CommandHandler("stats", stats))

    print(f"📌 Total groups loaded: {len(GROUP_IDS)}")
    print(f"📌 Group IDs: {GROUP_IDS}")

    # Initial staggered jobs so they can be managed individually
    job_base = 'auto_broadcast'
    interval_secs = config["interval_mins"] * 60
    for i in range(1, JOB_COUNT + 1):
        first = 10 + int((i - 1) * (interval_secs / JOB_COUNT))
        name = f"{job_base}_{i}"
        telegram_app.job_queue.run_repeating(
            auto_broadcast_job,
            interval=interval_secs,
            first=first,
            name=name
        )
        # initialize tracking record in case main starts jobs
        config["jobs"].setdefault(name, {})
        config["jobs"][name]["interval_secs"] = interval_secs
        config["jobs"][name]["next_run"] = None
        config["jobs"][name]["last_run"] = None
        config["jobs"][name]["last_status"] = "scheduled"

    print("🤖 Bot is running...")
    telegram_app.run_polling(drop_pending_updates=True)


# 🔥🔥🔥 YAHAN LIKHNA HAI — FILE KE BILKUL END ME 🔥🔥🔥
if __name__ == "__main__":
    main()


