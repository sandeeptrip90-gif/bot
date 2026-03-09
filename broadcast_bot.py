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
import os

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is alive and running!"

def run_web():
    # Render port automatically handle karega
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

def start_web():
    """Is function ko main() ke andar call karna hai"""
    t = Thread(target=run_web)
    t.daemon = True
    t.start()
    


# startup message (emoji removed to avoid encoding issues during import)
print("Bot file loaded successfully")

# =====================================================
# 🔐 BASIC CONFIG
# =====================================================

TOKEN = os.getenv("TOKEN")
# Purana ADMIN_ID hata kar ye paste karein
raw_admins = os.getenv("ADMIN_IDS", os.getenv("ADMIN_ID", "0"))
ADMIN_IDS = [int(id.strip()) for id in raw_admins.split(",") if id.strip().isdigit()]

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
JOB_COUNT = 10

# Per-job storage template: jobs are keyed `job_1`..`job_5`.
# Each job stores scheduling info and a rotating message pool.
# time: "HH:MM" string in IST when the job should run daily.
# pool: list of {from_chat_id, message_id} entries for round-robin.
# pool_index: next index to use from the pool.
# is_active: whether the job is enabled.
# last_run/next_run/last_status for diagnostics.
config.setdefault("jobs", {})
for i in range(1, JOB_COUNT + 1):
    name = f"job_{i}"
    config["jobs"].setdefault(name, {
        "time": None,
        "pool": [],
        "pool_index": 0,
        "is_active": False,
        "last_run": None,
        "next_run": None,
        "last_status": "stopped"
    })

# =====================================================
# Time helpers (IST)
def get_ist_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def format_time_12h(hhmm: str) -> str:
    """Convert a 24‑hour "HH:MM" string to 12‑hour format with AM/PM."""
    try:
        hh, mm = map(int, hhmm.split(":"))
    except Exception:
        return hhmm
    suffix = "AM" if hh < 12 else "PM"
    hour = hh % 12
    if hour == 0:
        hour = 12
    return f"{hour:02d}:{mm:02d} {suffix}"


def schedule_daily_job(context, job_name: str, hh: int, mm: int):
    """Schedule `auto_broadcast_job` to run every day at HH:MM IST.

    We compute the delay from now (in IST) to the next occurrence and then
    schedule a repeating job with an interval of 86400 seconds.
    """
    now = get_ist_now()
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    first_delay = (target - now).total_seconds()
    # remove any existing job with same name before scheduling
    for j in context.application.job_queue.get_jobs_by_name(job_name):
        j.schedule_removal()
    context.application.job_queue.run_repeating(
        auto_broadcast_job,
        interval=86400,
        first=first_delay,
        name=job_name,
    )

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

# Is function ko replace karein
def is_admin(update: Update) -> bool:
    # Ab ye check karega ki user_id ADMIN_IDS ki list mein hai ya nahi
    return update.effective_user and update.effective_user.id in ADMIN_IDS


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

async def clearpool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Specific Job ka pool delete karne ke liye (Usage: /clearpool 1)"""
    if not is_admin(update):
        return

    try:
        job_id = int(context.args[0])
        if job_id < 1 or job_id > JOB_COUNT:
            raise ValueError
    except (IndexError, ValueError):
        return await update.message.reply_text("❌ Usage: `/clearpool <id>` (Example: /clearpool 1)", parse_mode="Markdown")

    name = f"job_{job_id}"
    if name in config["jobs"]:
        config["jobs"][name]["pool"] = []
        config["jobs"][name]["pool_index"] = 0
        # Agar pool khali ho jaye toh job ko pause karna safe rehta hai
        config["jobs"][name]["is_active"] = False
        
        # Timer bhi hata dete hain taaki empty pool error na aaye
        for j in context.application.job_queue.get_jobs_by_name(name):
            j.schedule_removal()

        await update.message.reply_text(f"🗑️ **Job {job_id} ka pool clear kar diya gaya hai.**\nAb ye job inactive hai.")
    else:
        await update.message.reply_text("❌ Invalid Job ID.")

async def resetallpools(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saare 5 jobs ke pools ko ek saath saaf karne ke liye"""
    if not is_admin(update):
        return

    for i in range(1, JOB_COUNT + 1):
        name = f"job_{i}"
        config["jobs"][name]["pool"] = []
        config["jobs"][name]["pool_index"] = 0
        config["jobs"][name]["is_active"] = False
        
        for j in context.application.job_queue.get_jobs_by_name(name):
            j.schedule_removal()

    await update.message.reply_text("🚨 **All Pools Cleared!**\nSaare jobs reset ho gaye hain aur automation band kar di gayi hai.")

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
    # job-specific logic: pick next entry from the rotation pool
    record = config.get("jobs", {}).get(job_name)
    if not record:
        print(f"⚠️ No config record for {job_name}, skipping")
        return

    if not record.get("is_active"):
        print(f"⏸ {job_name} is inactive, skipping")
        record["last_run"] = now.isoformat()
        record["last_status"] = "skipped:inactive"
        return

    pool = record.get("pool", [])
    if not pool:
        print(f"⚠️ {job_name} has empty pool, skipping")
        record["last_run"] = now.isoformat()
        record["last_status"] = "skipped:no-pool"
        return

    # select next message from pool (round‑robin)
    idx = record.get("pool_index", 0) % len(pool)
    entry = pool[idx]
    record["pool_index"] = (idx + 1) % len(pool)

    # prepare broadcast parameters
    from_chat = entry.get("from_chat_id")
    msg_id = entry.get("message_id")
    if not from_chat or not msg_id:
        print(f"⚠️ {job_name} pool entry invalid, skipping")
        record["last_run"] = now.isoformat()
        record["last_status"] = "skipped:bad-entry"
        return

    is_night = night_mode()
    print(f"📊 Current IST hour: {hour} | Night Mode: {is_night}")
    if is_night:
        print(f"🌙 {job_name} skipped due to night mode")
        record["last_run"] = now.isoformat()
        record["last_status"] = "skipped:night"
        return

    print(f"📤 {job_name}: Sending message to {len(GROUP_IDS)} groups... (using pool index {idx})")
    record["last_run"] = now.isoformat()
    record["last_status"] = "running"

    for gid in GROUP_IDS:
        try:
            await context.bot.copy_message(
                chat_id=gid,
                from_chat_id=from_chat,
                message_id=msg_id
            )
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"❌ Failed for {gid}: {e}")

    # update next run and keep schedule time
    try:
        job_list = context.application.job_queue.get_jobs_by_name(job_name)
        if job_list:
            job = job_list[0]
            next_rt = getattr(job, 'next_run_time', getattr(job, 'next_t', None))
            record["next_run"] = next_rt.isoformat() if next_rt else None
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
        "👑 **Hanuman - ADMIN CONTROL PANEL**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        "🔄 **AUTOMATION (JOB SYSTEM)**\n"
        "• `/setjob <id> <time/mins>`\n"
        "  - *Daily (IST):* Reply to msg + `/setjob 1 08:30`\n"
        "  - *Interval:* Reply to msg + `/setjob 1 45` (mins)\n"
        "• `/stopjob <id>` - Pause a specific job\n"
        "• `/autoon` - Resume all configured jobs\n"
        "• `/stopall` - Global kill-switch for all timers\n"
        "• `/status` - Check active timers & message pool\n\n"

        "🚫 **SECURITY & ANTI-SPAM**\n"
        "• `/block <user_id>` - Auto-delete user's messages\n"
        "• `/unblock <user_id>` - Remove user from blacklist\n\n"

        "🗑️ **POOL MANAGEMENT**\n"
        "• `/clearpool <id>` - Delete messages of Job <id>\n"
        "• `/resetallpools` - Wipe all 5 job pools clean\n\n"
        
        "📢 **BROADCAST & ENGAGEMENT**\n"
        "• `/broadcast` - Reply to msg to send in all groups\n"
        "• `/pin` - Send and pin message everywhere\n"
        "• `/unpinall` - Remove pins from all groups\n\n"
        
        "🏢 **GROUP MANAGEMENT**\n"
        "• `/info` - List all groups with member count & links\n"
        "• `/stats` - Total group count summary\n"
        "• `/setgname <name>` - Update all group titles\n"
        "• `/setgdesc <text>` - Update all descriptions\n"
        "• `/setgpic` - Reply to photo to change all DPs\n\n"
        
        "⚙️ **SYSTEM SETTINGS**\n"
        "• `/settings <start> <end>` - Night mode (e.g., `23 7`)\n"
        "  - *Use `0 0` to disable Night Mode*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *Note: Use IST (Indian Standard Time) for all scheduling.*"
    )

    await update.message.reply_text(text, parse_mode="Markdown")


# ================= AUTO CONTROLS =================

# =====================================================
# 🚫 BLACKLIST SYSTEM (Auto-Delete Specific User)
# =====================================================

# Blacklisted User IDs ki list (Isse aap /block command se update kar payenge)
config.setdefault("blacklist", [])

async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User ko blacklist mein daalne ke liye (Usage: /block 12345678)"""
    if not is_admin(update): return
    try:
        target_id = int(context.args[0])
        if target_id not in config["blacklist"]:
            config["blacklist"].append(target_id)
            await update.message.reply_text(f"🚫 User `{target_id}` ko blacklist kar diya gaya hai. Ab iske saare messages auto-delete honge.", parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ Ye user pehle se blacklisted hai.")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Usage: `/block <user_id>`", parse_mode="Markdown")

async def unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User ko blacklist se hatane ke liye (Usage: /unblock 12345678)"""
    if not is_admin(update): return
    try:
        target_id = int(context.args[0])
        if target_id in config["blacklist"]:
            config["blacklist"].remove(target_id)
            await update.message.reply_text(f"✅ User `{target_id}` ko whitelist kar diya gaya hai.", parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ Ye user blacklist mein nahi hai.")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Usage: `/unblock <user_id>`", parse_mode="Markdown")

# --- MAIN LOGIC (Ye har message ko check karega) ---
async def delete_spammer_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Agar message kisi blacklisted user ka hai, toh delete karein"""
    if not update.effective_user: return
    
    user_id = update.effective_user.id
    if user_id in config.get("blacklist", []):
        try:
            await update.message.delete()
            print(f"🗑️ Deleted message from blacklisted user: {user_id}")
        except Exception as e:
            print(f"❌ Delete failed (Bot might not be admin): {e}")

async def setjob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Reply to a message when using /setjob <id> <time/mins>")

    try:
        args = context.args
        job_id = int(args[0])
        input_val = args[1]
        
        if job_id < 1 or job_id > JOB_COUNT:
            return await update.message.reply_text(f"❌ Job id must be 1-{JOB_COUNT}")

        name = f"job_{job_id}"
        rec = config["jobs"][name]
        
        # Add to message pool
        rec["pool"].append({
            "from_chat_id": update.message.chat_id,
            "message_id": update.message.reply_to_message.message_id
        })

        # Check if input is HH:MM or Minutes
        if ":" in input_val:
            # FIXED DAILY TIME (IST)
            hh, mm = map(int, input_val.split(":"))
            schedule_daily_job(context, name, hh, mm)
            rec["time"] = f"{hh:02d}:{mm:02d}"
            mode_text = f"daily at {format_time_12h(rec['time'])} IST"
        else:
            # REPEATING INTERVAL (Minutes)
            mins = int(input_val)
            # Purane jobs delete karein
            for j in context.application.job_queue.get_jobs_by_name(name):
                j.schedule_removal()
            # Naya interval job lagayein
            context.application.job_queue.run_repeating(
                auto_broadcast_job,
                interval=mins * 60,
                first=10, 
                name=name
            )
            rec["time"] = f"every {mins}m"
            mode_text = f"every {mins} minutes"

        rec["is_active"] = True
        pool_len = len(rec["pool"])
        await update.message.reply_text(
            f"✅ **Job {job_id} Set!**\n• Mode: {mode_text}\n• Pool Size: {pool_len} messages", 
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text("❌ Usage:\nFixed: `/setjob 1 08:00` (IST)\nRepeating: `/setjob 1 30` (Minutes)")


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

    msg = (
        f"⏹ **Job {job_id} stopped**\n"
        f"• Timer removed (pool preserved)\n"
        f"• {stopped} active task(s) killed"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")



async def autoon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    config["is_active"] = True
    resumed_jobs = []

    for i in range(1, JOB_COUNT + 1):
        name = f"job_{i}"
        rec = config["jobs"].get(name)
        
        # Check if job has time and messages in pool
        if rec and rec.get("time") and rec.get("pool"):
            time_str = rec["time"]
            try:
                if ":" in time_str:
                    hh, mm = map(int, time_str.split(":"))
                    schedule_daily_job(context, name, hh, mm)
                else:
                    # For interval jobs like "every 30m"
                    mins = int(time_str.replace("every ", "").replace("m", ""))
                    context.application.job_queue.run_repeating(
                        auto_broadcast_job, interval=mins*60, first=10, name=name
                    )
                
                rec["is_active"] = True
                resumed_jobs.append(f"Job {i}")
            except Exception as e:
                print(f"Error resuming {name}: {e}")

    if resumed_jobs:
        msg = f"▶️ **Auto Broadcast Resumed!**\nActive: {', '.join(resumed_jobs)}"
    else:
        msg = "⚠️ **No jobs to resume.**\nPehle `/setjob` use karke timing aur message set karein."
    
    await update.message.reply_text(msg, parse_mode="Markdown")

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
    """Show status of all jobs with schedule, next run time, and IST clock."""
    if not is_admin(update): return
    ist = get_ist_now()

    lines = []
    lines.append("📊 **BOT STATUS** (All times IST)")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🕒 Current Time: {ist.strftime('%Y-%m-%d %H:%M:%S IST')}")
    lines.append(f"🌙 Night Mode: {config['night_start']:02d}:00 → {config['night_end']:02d}:00")
    lines.append(f"🔴 Global Status: {'ACTIVE' if config.get('is_active', False) else 'INACTIVE'}")
    lines.append("")
    lines.append("**JOB STATUS (1-10):**")

    # Humne JOB_COUNT ko 10 tak support karne ke liye loop chalaya hai
    for i in range(1, JOB_COUNT + 1):
        name = f"job_{i}"
        jobs = context.application.job_queue.get_jobs_by_name(name)
        running = len(jobs) > 0

        record = config.get("jobs", {}).get(name, {})
        time_str = record.get("time") or "?"
        pool = record.get("pool", [])
        pool_len = len(pool)

        status_icon = "▶️" if running else "⏸"
        
        # --- Logic for Display Time ---
        if "every" in str(time_str):
            display_time = f"**{time_str}**"
        elif time_str != "?":
            display_time = f"**{format_time_12h(time_str)} IST** daily"
        else:
            display_time = "**Not Set**"

        # --- Line for each Job ---
        lines.append(f"{status_icon} **Job {i}**: {display_time} | Pool: {pool_len}")

        # Agar job active hai toh next run time dikhao
        if running:
            job = jobs[0]
            nr = getattr(job, 'next_run_time', getattr(job, 'next_t', None))
            if nr:
                # Local IST format mein convert karke dikhane ke liye
                next_run_ist = nr + timedelta(hours=5, minutes=30)
                lines.append(f"     ⏭ Next run: `{next_run_ist.strftime('%H:%M:%S')}`")
        
        if pool_len == 0 and running:
            lines.append(f"    ⚠️ Warning: Pool is empty!")

    msg = "\n".join(lines)
    await update.message.reply_text(msg, parse_mode='Markdown')

# =====================================================
# 🛠 GROUP MANAGEMENT COMMANDS
# =====================================================

async def setgname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sabhhi groups ka naam ek saath badle (Usage: /setgname Naya Naam)"""
    if not is_admin(update): return
    
    new_name = " ".join(context.args)
    if not new_name:
        return await update.message.reply_text("❌ Usage: `/setgname My New Group Name`", parse_mode="Markdown")

    success = 0
    for gid in GROUP_IDS:
        try:
            await context.bot.set_chat_title(chat_id=gid, title=new_name)
            success += 1
            await asyncio.sleep(0.5) # Anti-flood delay
        except Exception as e:
            print(f"❌ Name change failed for {gid}: {e}")

    await update.message.reply_text(f"✅ {success} groups ka naam badal diya gaya.")


async def setgdesc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sabhi groups ka description badle (Usage: /setgdesc Nayi Jankari)"""
    if not is_admin(update): return
    
    new_desc = " ".join(context.args)
    if not new_desc:
        return await update.message.reply_text("❌ Usage: `/setgdesc Naya Description Text`", parse_mode="Markdown")

    success = 0
    for gid in GROUP_IDS:
        try:
            await context.bot.set_chat_description(chat_id=gid, description=new_desc)
            success += 1
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"❌ Description change failed for {gid}: {e}")

    await update.message.reply_text(f"✅ {success} groups ka description update ho gaya.")


async def setgpic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sabhi groups ki profile pic badle (Usage: Reply to a Photo with /setgpic)"""
    if not is_admin(update): return
    
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        return await update.message.reply_text("❌ Kisi Photo par reply karke `/setgpic` likhein.")

    # Get the best quality photo
    photo_file = await update.message.reply_to_message.photo[-1].get_file()
    # Download locally temporarily
    temp_path = "temp_pic.jpg"
    await photo_file.download_to_drive(temp_path)

    success = 0
    for gid in GROUP_IDS:
        try:
            with open(temp_path, 'rb') as photo:
                await context.bot.set_chat_photo(chat_id=gid, photo=photo)
            success += 1
            await asyncio.sleep(1.0) # Photo upload takes time, higher delay
        except Exception as e:
            print(f"❌ Photo change failed for {gid}: {e}")

    # Remove temporary file
    if os.path.exists(temp_path):
        os.remove(temp_path)

    await update.message.reply_text(f"✅ {success} groups ki DP badal di gayi.")

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

    status_msg = await update.message.reply_text("🔄 Groups ki jaankari fetch ho rahi hai, please wait...")
    
    text = "📂 **Hanuman - GROUP DIRECTORY**\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    success_count = 0
    for index, gid in enumerate(GROUP_IDS, start=1):
        try:
            chat = await context.bot.get_chat(gid)
            members = await context.bot.get_chat_member_count(gid)
            
            # Link fetch karne ki koshish (Bot admin hona chahiye)
            link = chat.invite_link
            if not link:
                try:
                    link = await context.bot.export_chat_invite_link(gid)
                except Exception:
                    link = "Link Unavailable"

            # Professional formatting
            text += f"{index:02d}. **{chat.title}**\n"
            text += f"   👥 Members: `{members}`\n"
            text += f"   🔗 [Join Group]({link})\n\n"
            success_count += 1
            
            # Anti-flood delay
            await asyncio.sleep(0.2)
        except Exception as e:
            text += f"{index:02d}. ❌ ID: `{gid}`\n   Status: Access Denied/Not Admin\n\n"

    text += "━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"✅ **Total Active Groups:** {success_count}/{len(GROUP_IDS)}\n"
    text += f"🕒 **Last Updated:** {get_ist_now().strftime('%H:%M:%S')} IST"

    # Purane status message ko delete karke final report bhejna
    await status_msg.delete()
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text(f"📊 Total groups: {len(GROUP_IDS)}")

# =====================================================
# 🚀 MAIN
# =====================================================

def main():
    # 1. Web server start karein (Render ke liye zaroori)
    start_web() 
    print("🌐 Web server started for Render Health Check")

    print("⚙️ Initializing bot...")
    
    # 2. Variable ka naam 'telegram_app' hi rakhein
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
    telegram_app.add_handler(CommandHandler("setgname", setgname))
    telegram_app.add_handler(CommandHandler("setgdesc", setgdesc))
    telegram_app.add_handler(CommandHandler("setgpic", setgpic))

    telegram_app.add_handler(CommandHandler("clearpool", clearpool))
    telegram_app.add_handler(CommandHandler("resetallpools", resetallpools))

    # Admin Commands
    telegram_app.add_handler(CommandHandler("block", block_user))
    telegram_app.add_handler(CommandHandler("unblock", unblock_user))

    # Auto-Delete Handler (Isse sabse niche rakhein)
    from telegram.ext import MessageHandler, filters
    telegram_app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, delete_spammer_message))

    print(f"📌 Total groups loaded: {len(GROUP_IDS)}")
    print(f"📌 Group IDs: {GROUP_IDS}")

    print("🤖 Bot is running...")
    telegram_app.run_polling(drop_pending_updates=True)


# 🔥🔥🔥 YAHAN LIKHNA HAI — FILE KE BILKUL END ME 🔥🔥🔥
if __name__ == "__main__":
    main()



