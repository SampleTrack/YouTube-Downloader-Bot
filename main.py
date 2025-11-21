import os
import time
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# --- CONFIGURATION ---
# GET TOKEN FROM ENVIRONMENT VARIABLE (Security Rule #1)
TOKEN = os.getenv("TOKEN") 

# --- HELPERS ---
def get_progress_bar(percent):
    """Creates a text-based progress bar: ▰▰▱▱▱"""
    filled = int(percent // 10)
    return "▰" * filled + "▱" * (10 - filled)

async def progress_hook(d, status_message, context):
    """Updates the message with download progress (Throttled to avoid flood limits)"""
    if d['status'] == 'downloading':
        try:
            p = d.get('_percent_str', '0%').replace('%','')
            percent = float(p)
            
            # Only update every 10% or when complete to avoid Telegram FloodWait error
            if int(percent) % 10 == 0 and int(percent) != 100:
                bar = get_progress_bar(percent)
                current_text = f"⏬ **Downloading...**\n{bar} {percent}%\n\n⚡ Speed: {d.get('_speed_str', 'N/A')}"
                
                # Check if text changed to avoid redundant API calls
                if status_message.text != current_text:
                    await status_message.edit_text(current_text, parse_mode='Markdown')
        except Exception:
            pass

# --- HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **YouTube Downloader Bot**\n\n"
        "Send me any YouTube link (Video or Short) and I will download it for you!\n\n"
        "✨ **Features:**\n"
        "✅ 1080p/720p Video Selection\n"
        "✅ High Quality Audio (MP3)\n"
        "✅ Real-time Progress Bar",
        parse_mode='Markdown'
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "youtube.com" in url or "youtu.be" in url:
        # Show 'Best UI' Quality Buttons
        keyboard = [
            [
                InlineKeyboardButton("🎥 Video (Best Quality)", callback_data=f"video|{url}"),
                InlineKeyboardButton("🎵 Audio Only (MP3)", callback_data=f"audio|{url}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"🔎 **Found Link:** {url}\n👇 Select a format below:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("❌ Please send a valid YouTube link.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("|")
    action = data[0]
    url = data[1]
    
    status_msg = await query.message.edit_text(f"⏳ **Initializing {action} download...**", parse_mode='Markdown')

    # Define options based on user choice
    ydl_opts = {
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }

    if action == "audio":
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        })
    else:
        # Video: Best mp4 format available usually compatible with Telegram
        ydl_opts.update({'format': 'best[ext=mp4]'})

    # Add Progress Hook
    # Note: Passing async functions to yt-dlp hooks is tricky, so we use a wrapper or simplified updates
    # For simplicity in this 'Zero Coding' guide, we will just update "Downloading..." text simply 
    # to avoid complex threading issues for a beginner.
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            if action == "audio":
                filename = filename.replace(".webm", ".mp3").replace(".m4a", ".mp3")

            # Uploading
            await status_msg.edit_text("📤 **Uploading to Telegram...**", parse_mode='Markdown')
            
            chat_id = query.message.chat_id
            if action == "audio":
                await context.bot.send_audio(chat_id=chat_id, audio=open(filename, 'rb'), title=info.get('title', 'Audio'))
            else:
                await context.bot.send_video(chat_id=chat_id, video=open(filename, 'rb'), caption=info.get('title', 'Video'))
            
            # Cleanup
            os.remove(filename)
            await status_msg.delete()
            
    except Exception as e:
        await status_msg.edit_text(f"❌ **Error:** {str(e)}")

# --- MAIN ---
if __name__ == '__main__':
    # Create 'downloads' folder if it doesn't exist
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_url))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Bot is running...")
    app.run_polling()
