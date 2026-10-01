import os
import logging
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from openai import OpenAI

# --- Render Health Check Server ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and running smoothly!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

Thread(target=run_server, daemon=True).start()

# --- Logging Configuration ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Constants & Config ---
TELEGRAM_TOKEN = "7722709943:AAElgU53pL_J3j5W16hE6R7U4G-Qv2b3yK8"
OPENAI_API_KEY = "49e5a536511d1949725661ddcba811ff00aef292257942bd4701b3161e16cb7c"
TARGET_CHANNEL_ID = -1004332814800

client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# --- Data Storage (Thread-Safe Structure) ---
material_files = defaultdict(list)
user_current_section = {}
pending_files = {}

SECTION_NAMES = {
    "islamic": "Islamic Education",
    "arabic": "Arabic Language",
    "math": "Mathematics",
    "english": "English Language",
    "chemistry": "Chemistry",
    "biology": "Biology",
    "physics": "Physics",
    "duas": "Supplications & Azkar",
    "schedules": "Study Schedules"
}

DUAS_LIST = (
    "✨ **10 Beautiful Supplications & Azkar** ✨\n\n"
    "1. رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً وَفِي الْآخِرَةِ حَسَنَةً وَقِنَا عَذَابَ النَّارِ.\n"
    "2. لَا إِلَهَ إِلَّا أَنْتَ سُبْحَانَكَ إِنِّي كُنْتُ مِنَ الظَّالِمِينَ.\n"
    "3. اللَّهُمَّ إِنَّكَ عَفُوٌّ كَرِيمٌ تُحِبُّ الْعَفْوَ فَاعْفُ عَنِّي.\n"
    "4. يَا حَيُّ يَا قَيُّومُ بِرَحْمَتِكَ أَسْتَغِيثُ، أَصْلِحْ لِي شَأْنِي كُلَّهُ.\n"
    "5. رَبِّ اشْرَحْ لِي صَدْرِي وَيَسِّرْ لِي أَمْرِي.\n"
    "6. اللَّهُمَّ لَا سَهْلَ إِلَّا مَا جَعَلْتَهُ سَهْلاً، وَأَنْتَ تَجْعَلُ الْحَزْنَ إِذَا شِئْتَ سَهْلاً.\n"
    "7. حَسْبِي اللَّهُ لَا إِلَهَ إِلَّا هُوَ عَلَيْهِ تَوَكَّلْتُ وَهُوَ رَبُّ الْعَرْشِ الْعَظِيمِ.\n"
    "8. اللَّهُمَّ إِنِّى أَسْأَلُكَ عِلْماً نَافِعاً، وَرِزْقاً طَيِّباً، وَعَمَلاً مُتَقَبَّلاً.\n"
    "9. سُبْحَانَ اللَّهِ وَبِحَمْدِهِ، سُبْحَانَ اللَّهِ الْعَظِيمِ.\n"
    "10. أَسْتَغْفِرُ اللَّهَ الْعَظِيمَ وَأَتُوبُ إِلَيْهِ."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    
    keyboard = [
        [InlineKeyboardButton("Islamic ☪️", callback_data="sec_islamic"), InlineKeyboardButton("Arabic 📚", callback_data="sec_arabic")],
        [InlineKeyboardButton("Math 📐", callback_data="sec_math"), InlineKeyboardButton("English 🔤", callback_data="sec_english")],
        [InlineKeyboardButton("Chemistry 🧪", callback_data="sec_chemistry"), InlineKeyboardButton("Biology 🧬", callback_data="sec_biology")],
        [InlineKeyboardButton("Physics ⚡", callback_data="sec_physics"), InlineKeyboardButton("Duas 🤲", callback_data="sec_duas")],
        [InlineKeyboardButton("Schedules 📅", callback_data="sec_schedules"), InlineKeyboardButton("AI Assistant 🤖", callback_data="sec_ai_assistant")],
        [InlineKeyboardButton("✨ Senior 27 Status", callback_data="batch_badge")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"Welcome {user_name} to your final school year!\n"
        f"🎓 **Senior 27 | Al Falah Academy | MBZ** 🇦🇪"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "batch_badge":
        await query.message.reply_text("🎓 Senior 27 | Al Falah Academy | MBZ 🇦🇪")
        return

    if data.startswith("sec_"):
        sec_key = data.replace("sec_", "")
        
        if sec_key == "ai_assistant":
            user_current_section[user_id] = "ai_assistant"
            await query.message.reply_text(
                "🤖 **AI Assistant Mode Active**\n\n"
                "You can now ask me any academic or general question, and I will help you immediately! (Type your question directly)"
            )
            return

        if sec_key == "duas":
            await query.message.reply_text(DUAS_LIST, parse_mode="Markdown")
            return

        user_current_section[user_id] = sec_key
        files_list = material_files.get(sec_key, [])
        
        if not files_list:
            await query.message.reply_text(f"No files uploaded in ({SECTION_NAMES.get(sec_key, sec_key)}) yet. 📚")
            return

        response_text = f"📂 **Files in {SECTION_NAMES.get(sec_key, sec_key)}**:\n\n"
        for idx, f_item in enumerate(files_list, 1):
            response_text += f"{idx}. {f_item['title']}\n"
        
        response_text += "\nTo download a file, send its number."
        await query.message.reply_text(response_text, parse_mode="Markdown")
        return

    if data.startswith("assign_"):
        parts = data.split("_", 2)
        target_sec = parts[1]
        file_token = parts[2]

        file_data = pending_files.get(file_token)
        if not file_data:
            await query.message.edit_text("❌ Request expired or file already saved.")
            return

        material_files[target_sec].append({
            "title": file_data["title"],
            "file_id": file_data["file_id"]
        })
        del pending_files[file_token]

        await query.message.edit_text(
            f"✅ **File Saved Successfully!**\n"
            f"📌 Title: {file_data['title']}\n"
            f"📂 Section: {SECTION_NAMES.get(target_sec, target_sec)}"
        )
        return

async def handle_incoming_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post or update.message
    if not message: return

    if message.document or message.video or message.audio:
        caption = message.caption or (message.document.file_name if message.document else "Educational File")
        file_id = message.document.file_id if message.document else (message.video.file_id if message.video else message.audio.file_id)
        
        file_token = str(len(pending_files) + 1000)
        pending_files[file_token] = {"title": caption, "file_id": file_id}

        keyboard = [
            [InlineKeyboardButton("Math 📐", callback_data=f"assign_math_{file_token}"), InlineKeyboardButton("Arabic 📚", callback_data=f"assign_arabic_{file_token}")],
            [InlineKeyboardButton("English 🔤", callback_data=f"assign_english_{file_token}"), InlineKeyboardButton("Physics ⚡", callback_data=f"assign_physics_{file_token}")],
            [InlineKeyboardButton("Chemistry 🧪", callback_data=f"assign_chemistry_{file_token}"), InlineKeyboardButton("Biology 🧬", callback_data=f"assign_biology_{file_token}")],
            [InlineKeyboardButton("Islamic ☪️", callback_data=f"assign_islamic_{file_token}"), InlineKeyboardButton("Duas 🤲", callback_data=f"assign_duas_{file_token}")],
            [InlineKeyboardButton("Schedules 📅", callback_data=f"assign_schedules_{file_token}")]
        ]
        await message.reply_text(
            f"📥 **File Received:** {caption}\n\nPlease categorize this file:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.message.from_user.id

    if text.isdigit():
        current_sec = user_current_section.get(user_id)
        if current_sec and current_sec in material_files:
            file_index = int(text) - 1
            files_list = material_files[current_sec]
            if 0 <= file_index < len(files_list):
                target_file = files_list[file_index]
                await update.message.reply_document(
                    document=target_file['file_id'],
                    caption=f"📄 {target_file['title']}\n\n🎓 Senior 27 | Al Falah Academy | MBZ 🇦🇪"
                )
                return

    if user_current_section.get(user_id) == "ai_assistant":
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            def call_ai():
                response = client.chat.completions.create(
                    model="openai/gpt-4o-mini",
                    messages=[
                        {
                            "role": "system", 
                            "content": (
                                "You are an advanced, helpful academic AI assistant for 'Senior 27' students at Al Falah Academy, MBZ. "
                                "Provide clear, accurate, and concise answers to help students with their studies."
                            )
                        },
                        {"role": "user", "content": text}
                    ],
                    temperature=0.7,
                    max_tokens=1000,
                    timeout=30
                )
                return response.choices[0].message.content

            ai_reply = await asyncio.to_thread(call_ai)
            await update.message.reply_text(ai_reply)
            
        except Exception as e:
            logging.error(f"AI Error for user {user_id}: {e}")
            await update.message.reply_text("⚠️ The AI service is currently experiencing high load. Please try again in a few moments!")
        return

    await update.message.reply_text("Please use /start to open the main menu.")

def main():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN not found!")
        return

    # إنشاء التطبيق مع تحسينات الأداء والتعامل مع الضغط العالي
    application = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .concurrent_updates(True)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.AUDIO, handle_incoming_files))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_messages))

    print("🚀 Bot started successfully with High-Performance & Concurrency Mode...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
