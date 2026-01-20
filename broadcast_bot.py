import os
import asyncio
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- FLASK WEB SERVER (To keep Render happy) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web_server():
    # Render provides a PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

# --- TELEGRAM BOT LOGIC ---
TOKEN = os.environ.get('TOKEN')       # Get from Render Env Variables
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0)) 
GROUP_IDS = [-1002236012208] # Update these with your group IDs

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Reply to a message with /broadcast")
        return

    reply_msg = update.message.reply_to_message
    await update.message.reply_text(f"🚀 Broadcasting to {len(GROUP_IDS)} groups...")

    for chat_id in GROUP_IDS:
        try:
            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=reply_msg.chat_id,
                message_id=reply_msg.message_id
            )
            await asyncio.sleep(0.1) 
        except Exception as e:
            print(f"Error in {chat_id}: {e}")

    await update.message.reply_text("✅ Done!")

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    # Start the web server in a separate thread
    keep_alive()
    
    # Start the Telegram Bot
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("broadcast", broadcast))
    
    print("Bot and Web Server are starting...")
    application.run_polling()

