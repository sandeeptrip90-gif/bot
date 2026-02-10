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
        "♻️ **Multi-Job Auto Broadcast** (5 Independent Jobs)\n"
        "/setjob <id> <mins> – Reply to a message to set Job <id> (1-5) with interval <mins>.\n"
        "/stopjob <id> – Stop and remove Job <id>.\n"
        "/stopall – Stop all 5 jobs & disable auto broadcast.\n"
        "/autooff – Alias for /stopall (kills all timers).\n"
        "/settings <night_start> <night_end> – Set night hours (IST 0-23, use 0 0 to disable).\n"
        "/status – Show all 5 jobs, intervals, last/next run, current IST time.\n\n"
        "📢 **Manual Broadcast & Manage**\n"
        "/broadcast – Reply to send message to all groups\n"
        "/pin – Reply to send & pin message in all groups\n"
        "/unpinall – Remove all pinned messages\n"
        "/info – Show group names & member count\n"
        "/stats – Show total groups\n\n"
        "⏱ **Timing (IST)**\n"
        "• All times are Indian Standard Time (UTC+5:30)\n"
        "• Jobs skip during night mode\n"
        "• Use /settings 0 0 to disable night mode\n\n"
        "🤖 **Notes**\n"
        "• 5 independent jobs, each with own message & interval\n"
        "• Bot must be admin in groups\n"
        "• Supports text, photo, video, voice, files"
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
        args = context.args
        if not args or len(args) < 2:
            raise IndexError
        job_id = int(args[0])
        mins = int(args[1])
        
        if mins <= 0:
            raise ValueError("Interval must be positive")
    except (IndexError, ValueError):
        return await update.message.reply_text("❌ Usage: /setjob <id> <mins> (id: 1-5, mins: positive integer)")

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

    msg = f"✅ **Job {job_id} configured:**\n• Interval: {mins} min\n• Message: {update.message.reply_to_message.message_id}\n• Status: Running\n\nUse /status to monitor."
    await update.message.reply_text(msg, parse_mode="Markdown")


async def stopjob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    try:
        job_id = int(context.args[0])
    except (IndexError, ValueError):
        return await update.message.reply_text("❌ Usage: /stopjob <id> (id: 1-5)")
    
    if job_id < 1 or job_id > JOB_COUNT:
        return await update.message.reply_text(f"❌ Job id must be between 1 and {JOB_COUNT}")

    name = f"job_{job_id}"
    current_jobs = context.application.job_queue.get_jobs_by_name(name)
    stopped = len(current_jobs)
    
    for j in current_jobs:
        j.schedule_removal()
    
    # mark inactive
    config["jobs"][name]["is_active"] = False
    config["jobs"][name]["last_status"] = "stopped"

    msg = f"⏹ **Job {job_id} stopped**\n• Timer removed\n• {stopped} active task(s) killed"
    await update.message.reply_text(msg, parse_mode="Markdown")



async def autoon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    # Resume all configured jobs
    config["is_active"] = True

    # Schedule any configured jobs (per-job intervals)
    for i in range(1, JOB_COUNT + 1):
        name = f"job_{i}"
        rec = config["jobs"].get(name)
        if rec and rec.get("interval_mins") and rec.get("message_id"):
            # Only resume if has interval and message
            interval_secs = int(rec["interval_mins"]) * 60
            # remove existing to avoid duplicates
            for j in context.application.job_queue.get_jobs_by_name(name):
                j.schedule_removal()
            # Schedule the job
            context.application.job_queue.run_repeating(
                auto_broadcast_job,
                interval=interval_secs,
                first=10,
                name=name
            )
            rec["is_active"] = True
            print(f"Log: Resumed job '{name}' with interval {rec['interval_mins']} mins")

    await update.message.reply_text("▶️ Auto broadcast: resumed configured jobs.")
    print("Log: Auto broadcast jobs resumed.")

async def autooff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop all jobs and disable auto broadcast. This is the global kill command."""
    if not is_admin(update):
        return
    config["is_active"] = False
    
    # Remove all job timers (job_1 to job_5)
    stopped_count = 0
    for i in range(1, JOB_COUNT + 1):
        name = f"job_{i}"
        current_jobs = context.application.job_queue.get_jobs_by_name(name)
        for job in current_jobs:
            job.schedule_removal()
            stopped_count += 1
            print(f"Log: Removed job '{name}' on /autooff (stopall).")

        # mark stopped in tracking
        config["jobs"][name]["is_active"] = False
        config["jobs"][name]["last_status"] = "stopped"

    await update.message.reply_text(f"⏸ All auto timers killed ({stopped_count} jobs stopped). Broadcast disabled.")


async def stopall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias for /autooff - kills all 5 timers and disables auto broadcast."""
    await autooff(update, context)


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    try:
        # expect two args: night_start night_end (hours 0-23), both 0 disables night mode
        args = context.args
        if not args or len(args) < 2:
            raise IndexError
        ns = int(args[0])
        ne = int(args[1])
        if not (0 <= ns <= 23 and 0 <= ne <= 23):
            raise ValueError("Hours must be 0-23")
        config["night_start"] = ns
        config["night_end"] = ne
        
        if ns == 0 and ne == 0:
            msg = "⚙️ **Night Mode Disabled** (all hours enabled)"
        elif ns > ne:
            msg = f"⚙️ **Night Mode Set**: {ns:02d}:00 IST → {ne:02d}:00 IST (crosses midnight)"
        else:
            msg = f"⚙️ **Night Mode Set**: {ns:02d}:00 IST → {ne:02d}:00 IST"
        
        await update.message.reply_text(msg, parse_mode="Markdown")
        print(f"Log: Night settings updated to {ns:02d}:00 → {ne:02d}:00 (IST)")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Usage: /settings <start_hour> <end_hour>\n• Hours: 0-23 (IST)\n• Example: /settings 23 7 (11 PM to 7 AM)\n• Use: /settings 0 0 to disable")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show status of all 5 jobs with schedule, next run time, and IST clock."""
    if not is_admin(update): return
    ist = get_ist_now()

    lines = []
    lines.append("📊 **BOT STATUS** (All times IST)")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🕒 Current Time: {ist.strftime('%Y-%m-%d %H:%M:%S IST')}")
    lines.append(f"🌙 Night Mode: {config['night_start']:02d}:00 → {config['night_end']:02d}:00 (0 0 = disabled)")
    lines.append(f"🔴 Status: {'ACTIVE' if config.get('is_active', False) else 'INACTIVE'}")
    lines.append("")
    lines.append("**JOB STATUS (1-5):**")

    for i in range(1, JOB_COUNT + 1):
        name = f"job_{i}"
        jobs = context.application.job_queue.get_jobs_by_name(name)
        running = len(jobs) > 0

        record = config.get("jobs", {}).get(name, {})
        interval_mins = record.get("interval_mins")
        msg_id = record.get("message_id")
        is_active = record.get("is_active", False)
        last_status = record.get("last_status", "idle")

        # Format next run time more readably
        next_run_str = "N/A"
        if running:
            job = jobs[0]
            nr = getattr(job, 'next_run_time', getattr(job, 'next_t', None))
            if nr:
                try:
                    next_run_str = nr.strftime('%H:%M:%S') if hasattr(nr, 'strftime') else str(nr)[:8]
                except:
                    next_run_str = "N/A"

        status_icon = "▶️" if running else "⏸"
        lines.append(f"{status_icon} **Job {i}**: {'ON' if running else 'OFF'} | {interval_mins or '?'} min | Next: {next_run_str}")
        if msg_id:
            lines.append(f"    Msg ID: {msg_id}")
        else:
            lines.append(f"    ❌ No message set")

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
    telegram_app.add_handler(CommandHandler("setjob", setjob))
    telegram_app.add_handler(CommandHandler("stopjob", stopjob))
    telegram_app.add_handler(CommandHandler("autoon", autoon))
    telegram_app.add_handler(CommandHandler("autooff", autooff))
    telegram_app.add_handler(CommandHandler("stopall", stopall))
    telegram_app.add_handler(CommandHandler("settings", settings))
    telegram_app.add_handler(CommandHandler("status", status))

    telegram_app.add_handler(CommandHandler("broadcast", broadcast))
    telegram_app.add_handler(CommandHandler("pin", pin))
    telegram_app.add_handler(CommandHandler("unpinall", unpinall))
    telegram_app.add_handler(CommandHandler("info", info))
    telegram_app.add_handler(CommandHandler("stats", stats))

    print(f"📌 Total groups loaded: {len(GROUP_IDS)}")
    print(f"📌 Group IDs: {GROUP_IDS}")

    print("🤖 Bot is running...")
    telegram_app.run_polling(drop_pending_updates=True)


# 🔥🔥🔥 YAHAN LIKHNA HAI — FILE KE BILKUL END ME 🔥🔥🔥
if __name__ == "__main__":
    main()


