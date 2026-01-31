import os
import asyncio
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- FLASK WEB SERVER (For Render) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and managing groups!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.daemon = True
    t.start()

# --- CONFIGURATION ---

TOKEN = os.environ.get('TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
# Your list of Group IDs
GROUP_IDS = [-1002236012208, -1002417345407, -1002330831798, -1001882254820, -1002295951659, -1002350372764, -1002408686476, -1002458796542, -1002459378218, -1001787331133, -1001797945922, -1001843610820, -1002052681893, -1002126246859, -1001509387207, -1001738062150, -1001587346978, -1001829615017, -1002083172621, -1002411884866, -1001567747819, -1002254648501, -1003366623406, -1002283304339, -4557532425, -1001637428890, -1002299671203, -1002568461287, -1002538473462 ]

# --- HELPER: ADMIN CHECK ---
def is_admin(update: Update):
    return update.effective_user.id == ADMIN_ID

# User-Set Settings (Default values)
config = {
    "auto_msg_id": None,
    "from_chat_id": None,
    "is_active": False,
    "interval_mins": 120,    # Default 2 hours
    "night_start": 23,       # 11 PM
    "night_end": 7           # 7 AM
}

# --- HELPERS ---
def is_admin(update: Update):
    return update.effective_user.id == ADMIN_ID

# --- THE DYNAMIC JOB ---
async def dynamic_broadcast_job(context: ContextTypes.DEFAULT_TYPE):
    if not config["is_active"] or config["auto_msg_id"] is None:
        return

    now = datetime.now().hour
    # Night Mode Logic
    if config["night_start"] > config["night_end"]:
        if now >= config["night_start"] or now < config["night_end"]:
            print("Night mode: Sleeping...")
            return
    else:
        if config["night_start"] <= now < config["night_end"]:
            print("Night mode: Sleeping...")
            return

    for chat_id in GROUP_IDS:
        try:
            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=config["from_chat_id"],
                message_id=config["auto_msg_id"]
            )
            await asyncio.sleep(0.1)
        except: continue

# --- COMMANDS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    msg = (
        "🛠 **Pro Admin Panel**\n\n"
        "🔧 `/settings 120 23 7` -> Set (Mins, Night Start, Night End)\n"
        "📝 `/setauto` -> (Reply to msg) Set repeat message\n"
        "▶️ `/autoon` -> Start Auto-Sender\n"
        "⏸ `/autooff` -> Stop Auto-Sender\n"
        "📊 `/status` -> See current settings"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def set_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    try:
        config["interval_mins"] = int(context.args[0])
        config["night_start"] = int(context.args[1])
        config["night_end"] = int(context.args[2])
        
        # Reschedule Job
        jobs = context.job_queue.get_jobs_by_name('broadcast_job')
        for job in jobs: job.schedule_removal()
        
        context.job_queue.run_repeating(
            dynamic_broadcast_job, 
            interval=config["interval_mins"] * 60, 
            first=10, 
            name='broadcast_job'
        )
        await update.message.reply_text(f"⚙️ Updated! Every {config['interval_mins']}m. Night: {config['night_start']} to {config['night_end']}")
    except:
        await update.message.reply_text("❌ Use: `/settings <mins> <night_start> <night_end>`")

async def set_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update) or not update.message.reply_to_message:
        return await update.message.reply_text("❌ Reply to a message with /setauto")
    config["auto_msg_id"] = update.message.reply_to_message.message_id
    config["from_chat_id"] = update.message.chat_id
    config["is_active"] = True
    await update.message.reply_text("✅ Auto-message set and ACTIVATED!")

async def auto_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    config["is_active"] = True
    await update.message.reply_text("▶️ Auto-broadcast is now ON.")

async def auto_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    config["is_active"] = False
    await update.message.reply_text("⏸ Auto-broadcast is now OFF.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    state = "ACTIVE" if config["is_active"] else "STOPPED"
    await update.message.reply_text(f"📊 **Status:** {state}\nTimer: {config['interval_mins']}m\nNight: {config['night_start']}-{config['night_end']}")


# --- COMMANDS BROADCAST ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    menu = (
        "🛠 **Broadcast & Management Bot**\n\n"
        "📢 `/broadcast` - (Reply to msg) Send to all groups\n"
        "📌 `/pin` - (Reply to msg) Send and pin in all\n"
        "📍 `/unpinall` - Clear ALL pins in all groups\n"
        "✏️ `/setname <name>` - Rename all groups\n"
        "📊 `/info` - Show titles and member counts\n"
        "🚪 `/leaveall` - Bot leaves all groups\n"
        "📈 `/stats` - Count total groups in list"
    )
    await update.message.reply_text(menu, parse_mode='Markdown')

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Reply to a message with /broadcast")
        return
    
    reply_msg = update.message.reply_to_message
    msg = await update.message.reply_text(f"🚀 Broadcasting...")
    
    success = 0
    for chat_id in GROUP_IDS:
        try:
            await context.bot.copy_message(chat_id=chat_id, from_chat_id=reply_msg.chat_id, message_id=reply_msg.message_id)
            success += 1
            await asyncio.sleep(0.1)
        except Exception: continue
    await msg.edit_text(f"✅ Sent to {success}/{len(GROUP_IDS)} groups.")

async def broadcast_and_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Reply to a message with /pin")
        return
    
    reply_msg = update.message.reply_to_message
    msg = await update.message.reply_text("🚀 Pinning everywhere...")
    
    success = 0
    for chat_id in GROUP_IDS:
        try:
            sent = await context.bot.copy_message(chat_id=chat_id, from_chat_id=reply_msg.chat_id, message_id=reply_msg.message_id)
            await context.bot.pin_chat_message(chat_id=chat_id, message_id=sent.message_id)
            success += 1
            await asyncio.sleep(0.1)
        except Exception: continue
    await msg.edit_text(f"✅ Pinned in {success} groups.")

async def unpin_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    msg = await update.message.reply_text("🧹 Clearing all pins...")
    
    success = 0
    for chat_id in GROUP_IDS:
        try:
            await context.bot.unpin_all_chat_messages(chat_id=chat_id)
            success += 1
            await asyncio.sleep(0.1)
        except Exception: continue
    await msg.edit_text(f"✅ Unpinned everything in {success} groups.")

async def set_group_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    new_title = " ".join(context.args)
    if not new_title:
        await update.message.reply_text("❌ Usage: `/setname New Name`")
        return
    
    msg = await update.message.reply_text(f"⏳ Renaming to '{new_title}'...")
    success = 0
    for chat_id in GROUP_IDS:
        try:
            await context.bot.set_chat_title(chat_id=chat_id, title=new_title)
            success += 1
            await asyncio.sleep(0.1)
        except Exception: continue
    await msg.edit_text(f"✅ Renamed {success} groups.")

async def get_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    msg = await update.message.reply_text("🔎 Fetching group data...")
    
    report = "📊 **Group Info:**\n"
    for chat_id in GROUP_IDS:
        try:
            chat = await context.bot.get_chat(chat_id)
            count = await context.bot.get_chat_member_count(chat_id)
            report += f"• {chat.title}: {count} members\n"
        except Exception:
            report += f"• ID {chat_id}: ⚠️ Access Denied\n"
        await asyncio.sleep(0.1)
    
    await msg.edit_text(report, parse_mode='Markdown')

async def leave_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    # Basic safety check to prevent accidental trigger
    if "confirm" not in context.args:
        await update.message.reply_text("⚠️ **Warning!** This will make the bot leave ALL groups.\nType `/leaveall confirm` to proceed.")
        return

    msg = await update.message.reply_text("🚪 Leaving all groups...")
    for chat_id in GROUP_IDS:
        try:
            await context.bot.leave_chat(chat_id=chat_id)
            await asyncio.sleep(0.1)
        except Exception: continue
    await msg.edit_text("✅ Bot has left all groups.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    await update.message.reply_text(f"📈 Total groups in current list: {len(GROUP_IDS)}")

# --- MAIN ---
if __name__ == '__main__':
    keep_alive()
    application = Application.builder().token(TOKEN).build()

    # Initialize Job
    application.job_queue.run_repeating(
        dynamic_broadcast_job, 
        interval=config["interval_mins"] * 60, 
        first=10, 
        name='broadcast_job'
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("settings", set_settings))
    application.add_handler(CommandHandler("setauto", set_auto))
    application.add_handler(CommandHandler("autoon", auto_on))
    application.add_handler(CommandHandler("autooff", auto_off))
    application.add_handler(CommandHandler("status", status))

    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("pin", broadcast_and_pin))
    application.add_handler(CommandHandler("unpinall", unpin_all))
    application.add_handler(CommandHandler("setname", set_group_name))
    application.add_handler(CommandHandler("info", get_info))
    application.add_handler(CommandHandler("leaveall", leave_all))
    application.add_handler(CommandHandler("stats", stats))
    
    print("Management Bot is running...")
    application.run_polling()








