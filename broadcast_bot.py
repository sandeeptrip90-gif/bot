import asyncio
import os
from datetime import datetime, timedelta
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
    "night_start": 23,
    "night_end": 7
}

# How many independent jobs to support
JOB_COUNT = 5

# Per-job storage template: jobs are keyed `job_1`..`job_5`.
# Each job stores: message_id, from_chat_id, interval_mins, is_active, last_run, next_run, last_status
config.setdefault("jobs", {})
for i in range(1, JOB_COUNT + 1):
    name = f"job_{i}"
    config["jobs"].setdefault(name, {
        "message_id": None,
        "from_chat_id": None,
        "interval_mins": None,
        "is_active": False,
        "last_run": None,
        "next_run": None,
        "last_status": "stopped"
    })

# =====================================================
# Time helpers (IST)
def get_ist_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

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
    # Use IST for all night checks
    ist = get_ist_now()
    hour = ist.hour
    ns = config["night_start"]
    ne = config["night_end"]

    # Disabled if both set to 0
    if ns == 0 and ne == 0:
        return False

    if ns > ne:  # crosses midnight, e.g., 23 -> 7
        return hour >= ns or hour < ne
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
    ist = get_ist_now()
    now = ist
    hour = now.hour
    # Determine job name if available
    job_name = None
    try:
        job_name = context.job.name if getattr(context, 'job', None) else None
    except Exception:
        job_name = None

    print(f"🔁 Auto job triggered (IST) at: {now.strftime('%Y-%m-%d %H:%M:%S')} | job={job_name} | Night Start: {config['night_start']}, Night End: {config['night_end']}")
    # job-specific logic: use message stored for this job
    record = config.get("jobs", {}).get(job_name)
    if not record:
        print(f"⚠️ No config record for {job_name}, skipping")
        return

    # check active and message
    if not record.get("is_active"):
        print(f"⏸ {job_name} is inactive, skipping")
        record["last_run"] = now.isoformat()
        record["last_status"] = "skipped:inactive"
        return

    if not record.get("message_id") or not record.get("from_chat_id"):
        print(f"⚠️ {job_name} has no message configured, skipping")
        record["last_run"] = now.isoformat()
        record["last_status"] = "skipped:no-msg"
        return

    is_night = night_mode()
    print(f"📊 Current IST hour: {hour} | Night Mode: {is_night}")
    if is_night:
        print(f"🌙 {job_name} skipped due to night mode")
        record["last_run"] = now.isoformat()
        record["last_status"] = "skipped:night"
        return

    print(f"📤 {job_name}: Sending message to {len(GROUP_IDS)} groups...")
    record["last_run"] = now.isoformat()
    record["last_status"] = "running"

    for gid in GROUP_IDS:
        try:
            await context.bot.copy_message(
                chat_id=gid,
                from_chat_id=record.get("from_chat_id"),
                message_id=record.get("message_id")
            )
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"❌ Failed for {gid}: {e}")

    # update next run if job object available
    try:
        job_list = context.application.job_queue.get_jobs_by_name(job_name)
        if job_list:
            job = job_list[0]
            next_rt = getattr(job, 'next_run_time', getattr(job, 'next_t', None))
            record["next_run"] = next_rt.isoformat() if next_rt else None
            interval = getattr(job, 'interval', None)
            if interval:
                record["interval_mins"] = int(interval / 60)
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


async def setjob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Reply to a message when using /setjob <id> <mins>")
    try:
        job_id = int(context.args[0])
        mins = int(context.args[1])
    except Exception:
        return await update.message.reply_text("❌ Usage: /setjob <id> <mins> (id 1..5)")

    if job_id < 1 or job_id > JOB_COUNT:
        return await update.message.reply_text(f"❌ Job id must be between 1 and {JOB_COUNT}")

    name = f"job_{job_id}"
    # store message
    config["jobs"][name]["message_id"] = update.message.reply_to_message.message_id
    config["jobs"][name]["from_chat_id"] = update.message.chat_id
    config["jobs"][name]["interval_mins"] = mins
    config["jobs"][name]["is_active"] = True
    config["jobs"][name]["last_status"] = "scheduled"

    # remove existing job if any
    existing = context.application.job_queue.get_jobs_by_name(name)
    for j in existing:
        j.schedule_removal()

    # schedule repeating job
    interval_secs = mins * 60
    context.application.job_queue.run_repeating(
        auto_broadcast_job,
        interval=interval_secs,
        first=10,
        name=name
    )

    await update.message.reply_text(f"✅ Job {job_id} set: every {mins} minute(s). Will use the replied message.")


async def stopjob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    try:
        job_id = int(context.args[0])
    except Exception:
        return await update.message.reply_text("❌ Usage: /stopjob <id>")
    if job_id < 1 or job_id > JOB_COUNT:
        return await update.message.reply_text(f"❌ Job id must be between 1 and {JOB_COUNT}")

    name = f"job_{job_id}"
    current_jobs = context.application.job_queue.get_jobs_by_name(name)
    for j in current_jobs:
        j.schedule_removal()
    # mark inactive
    config["jobs"][name]["is_active"] = False
    config["jobs"][name]["last_status"] = "stopped"

    await update.message.reply_text(f"⏹ Job {job_id} stopped and removed.")



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

    # 3. FRESH START — schedule any configured jobs (per-job intervals)
    for i in range(1, JOB_COUNT + 1):
        name = f"job_{i}"
        rec = config["jobs"].get(name)
        if rec and rec.get("is_active") and rec.get("interval_mins"):
            interval_secs = int(rec["interval_mins"]) * 60
            # remove existing
            for j in context.application.job_queue.get_jobs_by_name(name):
                j.schedule_removal()
            context.application.job_queue.run_repeating(
                auto_broadcast_job,
                interval=interval_secs,
                first=10,
                name=name
            )

    await update.message.reply_text("▶️ Auto broadcast: started configured jobs.")
    print("Log: Auto broadcast jobs started where configured.")

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
    if not is_admin(update):
        return
    try:
        # expect two args: night_start night_end (hours 0-23), both 0 disables night mode
        ns = int(context.args[0])
        ne = int(context.args[1])
        if not (0 <= ns <= 23 and 0 <= ne <= 23):
            raise ValueError
        config["night_start"] = ns
        config["night_end"] = ne
        await update.message.reply_text(f"⚙️ Night mode set: {ns}:00 to {ne}:00 (IST).")
        print(f"Log: Night settings updated to {ns} -> {ne} (IST)")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Usage: /settings <night_start_hour> <night_end_hour>  (0-23), use 0 0 to disable")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    ist = get_ist_now()

    lines = []
    lines.append("📊 **Current Bot Status (IST)**")
    lines.append("━━━━━━━━━━━━━━━")
    lines.append(f"🕒 Current IST time: {ist.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"🌙 Night: {config['night_start']} to {config['night_end']} (0 0 = disabled)")
    lines.append("")
    lines.append("🔁 Jobs:")

    for i in range(1, JOB_COUNT + 1):
        name = f"job_{i}"
        jobs = context.application.job_queue.get_jobs_by_name(name)
        exists = len(jobs) > 0

        record = config.get("jobs", {}).get(name, {})
        last_run = record.get("last_run")
        last_status = record.get("last_status", "-")
        interval_mins = record.get("interval_mins")
        msg_id = record.get("message_id")

        next_run_str = "N/A"
        if exists:
            job = jobs[0]
            nr = getattr(job, 'next_run_time', getattr(job, 'next_t', None))
            next_run_str = nr.isoformat() if nr else "N/A"

        lines.append(f"• Job {i}: {'RUNNING' if exists else 'NOT RUNNING'}")
        lines.append(f"  - Interval: {interval_mins or 'N/A'} min")
        lines.append(f"  - Next run: {next_run_str}")
        lines.append(f"  - Last run: {last_run or 'Never'}")
        lines.append(f"  - Last status: {last_status}")
        lines.append(f"  - Msg: {msg_id or 'None'}")

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
    telegram_app.add_handler(CommandHandler("setjob", setjob))
    telegram_app.add_handler(CommandHandler("stopjob", stopjob))
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


