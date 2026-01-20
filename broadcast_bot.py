import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- CONFIGURATION ---
TOKEN = ''  # Put your key here
ADMIN_ID =            # Put your personal Telegram User ID here
# List of Group IDs where the bot is an admin
GROUP_IDS = [-1002236012208] 

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Security check
    if update.effective_user.id != ADMIN_ID:
        return

    # 2. Check if you are replying to a message
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Error: Please REPLY to the file/message you want to broadcast with the command /broadcast")
        return

    reply_msg = update.message.reply_to_message
    await update.message.reply_text(f"🚀 Broadcasting to {len(GROUP_IDS)} groups...")

    count = 0
    for chat_id in GROUP_IDS:
        try:
            # copy_message works for EVERYTHING: photos, videos, docs, audio, stickers, etc.
            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=reply_msg.chat_id,
                message_id=reply_msg.message_id
            )
            count += 1
            # Anti-spam delay: 30 messages per second is the limit
            await asyncio.sleep(0.1) 
        except Exception as e:
            print(f"Failed to send to {chat_id}: {e}")

    await update.message.reply_text(f"✅ Broadcast complete! Successfully sent to {count} groups.")

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    
    # Listen for the /broadcast command
    app.add_handler(CommandHandler("broadcast", broadcast))
    
    print("Bot is running... Ready to broadcast any file type.")

    app.run_polling()
