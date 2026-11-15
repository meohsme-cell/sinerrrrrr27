import os
import logging
import psycopg2
from google import genai
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# --- إعداد الاتصال بقاعدة البيانات ---
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Init Error: {e}")

OWNER_ID = 1329113404
ADMIN_ID = 1110343074
SECRET_ADMIN_KEY = "mpol90mpol90@123"

def get_db():
    if not DATABASE_URL:
        return None
    return psycopg2.connect(DATABASE_URL, connect_timeout=5)

def init_db():
    if not DATABASE_URL:
        return
    try:
        conn = get_db()
        if not conn: return
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS materials (
                id SERIAL PRIMARY KEY,
                section TEXT,
                title TEXT,
                file_id TEXT
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_logs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                username TEXT,
                full_name TEXT,
                msg_type TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error initializing database: {e}")

try:
    init_db()
except Exception as e:
    print(f"Database Init Error: {e}")

def add_material_to_db(section, title, file_id):
    sec = section.strip().lower()
    try:
        conn = get_db()
        if not conn: return
        cursor = conn.cursor()
        cursor.execute("INSERT INTO materials (section, title, file_id) VALUES (%s, %s, %s)", (sec, title, file_id))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logging.error(f"Error adding material: {e}")

def get_materials_from_db(section):
    sec = section.strip().lower()
    try:
        conn = get_db()
        if not conn: return []
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, file_id FROM materials WHERE section = %s", (sec,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [{"id": row[0], "title": row[1], "file_id": row[2]} for row in rows]
    except Exception as e:
        logging.error(f"Error getting materials: {e}")
        return []

def delete_material_from_db(file_id):
    try:
        conn = get_db()
        if not conn: return False
        cursor = conn.cursor()
        cursor.execute("DELETE FROM materials WHERE id = %s", (file_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        cursor.close()
        conn.close()
        return deleted
    except Exception as e:
        logging.error(f"Error deleting material: {e}")
        return False

# --- سيرفر Render الحفاظ على الاتصال ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

Thread(target=run_server, daemon=True).start()

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
pending_files = {}

SECTION_NAMES = {
    "islamic": "التربية الإسلامية",
    "arabic": "اللغة العربية",
    "math": "الرياضيات",
    "english": "اللغة الإنجليزية",
    "chemistry": "الكيمياء",
    "biology": "الأحياء",
    "physics": "الفيزياء",
    "duas": "أدعية وأذكار",
    "schedules": "الجداول الدراسية",
    "structures": "الهياكل الدراسية"
}

DUAS_LIST = (
    "✨ 10 أذكار وأدعية مباركة ✨\n\n"
    "1. رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً وَفِي الْآخِرَةِ حَسَنَةً وَقِنَا عَذَابَ النَّارِ.\n"
    "2. لَا إِلَهَ إِلَّا أَنْتَ سُبْحَانَكَ إِنِّي كُنْتُ مِنَ الظَّالِمِينَ.\n"
    "3. اللَّهُمَّ إِنَّكَ عَفُوٌّ كَرِيمٌ تُحِبُّ الْعَفْوَ فَاعْفُ عَنِّي.\n"
    "4. يَا حَيُّ يَا قَيُّومُ بِرَحْمَتِكَ أَسْتَغِيثُ، أَصْلِحْ لِي شَأْنِي كُلَّهُ.\n"
    "5. رَبِّ اشْرَحْ لِي صَدْرِي وَيَسِّرْ لِي أَمْرِي.\n"
    "6. اللَّهُمَّ لَا سَهْلَ إِلَّا مَا جَعَلْتَهُ سَهْلاً، وَأَنْتَ تَجْعَلُ الْحَزْنَ إِذَا شِئْتَ سَهْلاً.\n"
    "7. حَسْبِي اللَّهُ لَا إِلَهَ إِلَّا هُوَ عَلَيْهِ تَوَكَّلْتُ وَهُوَ رَبُّ الْعَرْشِ الْعَظِيمِ.\n"
    "8. اللَّهُمَّ إِنِّى أَسْأَلُكَ عِلْماً نَافِعاً، وَرِزْقاً طَيِّباً، وَعَمَلاً مُتَقَبَّلاً.\n"
    "9. سُبْحَانَ اللَّهِ وَبِحَمْدِهِ، سُبْحَانَ اللَّهِ الْعَظِيمِ.\n"
    "10. أَسْتَغْفِرُ اللَّهَ الْعَظِيمَ وَأَتُوبُ إِلَيْهِ."
)

async def log_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not DATABASE_URL: return
    user_id = user.id
    username = user.username or "بدون_معرف"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "بدون اسم"
    content, msg_type = "", "unknown"
    if update.message:
        if update.message.text:
            msg_type, content = "text", update.message.text
        elif update.message.document:
            msg_type, content = "document", f"📁 [ملف: {update.message.document.file_name or 'مستند'}]"
        elif update.message.photo:
            msg_type, content = "photo", "📷 [صورة]"
    elif update.callback_query:
        msg_type, content = "button_click", f"🔘 زر: {update.callback_query.data}"
    try:
        conn = get_db()
        if conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO user_logs (user_id, username, full_name, msg_type, content) VALUES (%s, %s, %s, %s, %s)", (user_id, username, full_name, msg_type, content))
            conn.commit()
            cursor.close()
            conn.close()
    except Exception as e:
        logging.error(f"Error logging: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await log_activity(update, context)
    user_id = update.effective_user.id if update.effective_user else 0
    
    # لوحة تحكم المالك بكلمة السر القديمة
    if user_id == OWNER_ID and context.args and context.args[0] == SECRET_ADMIN_KEY:
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, full_name, msg_type, content, timestamp FROM user_logs ORDER BY timestamp DESC LIMIT 20")
            logs = cursor.fetchall()
            cursor.close()
            conn.close()
            logs_text = "📊 **سجلات التفاعلات الأخيرة للبوت:**\n\n"
            for log in logs:
                logs_text += f"👤 {log[2]} (@{log[1]} - ID: `{log[0]}`)\n💬 {log[3]}: {log[4]}\n⏰ {log[5]}\n-------------------\n"
            await update.message.reply_text(logs_text[:4000], parse_mode="Markdown")
            return
        except Exception as e:
            await update.message.reply_text(f"خطأ: {e}")
            return

    # الأزرار الأصلية تماماً مع إضافة زر الهياكل فقط
    keyboard = [
        [InlineKeyboardButton("رياضيات", callback_data="sec_math"), InlineKeyboardButton("كيمياء", callback_data="sec_chemistry")],
        [InlineKeyboardButton("أحياء", callback_data="sec_biology"), InlineKeyboardButton("إنجليزي", callback_data="sec_english")],
        [InlineKeyboardButton("إسلامية", callback_data="sec_islamic"), InlineKeyboardButton("عربي", callback_data="sec_arabic")],
        [InlineKeyboardButton("فيزياء", callback_data="sec_physics"), InlineKeyboardButton("أدعية وأذكار", callback_data="sec_duas")],
        [InlineKeyboardButton("الجداول الدراسية", callback_data="sec_schedules"), InlineKeyboardButton("الهياكل الدراسية", callback_data="sec_structures")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # الرد بنفس شكل البوت القديم تماماً بدون أي إضافات مزعجة
    await update.message.reply_text("أهلاً بك! استخدم القائمة الرئيسية لتصفح مواد الصف الثاني عشر المتقدم 🎓", reply_markup=reply_markup)

# أمر حذف الملفات لصديقك أو لك
async def delete_material_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await log_activity(update, context)
    user_id = update.effective_user.id if update.effective_user else 0
    if user_id not in [OWNER_ID, ADMIN_ID]:
        return

    if not context.args:
        text = "📋 **قائمة الملفات المسجلة وأرقامها:**\n\n"
        for sec_key, sec_title in SECTION_NAMES.items():
            items = get_materials_from_db(sec_key)
            if items:
                text += f"📂 **{sec_title}**:\n"
                for item in items:
                    text += f"  - رقم (`{item['id']}`): {item['title']}\n"
                text += "\n"
        text += "⚠️ للحذف أرسل هكذا:\n`/delete [رقم_الملف]`"
        await update.message.reply_text(text, parse_mode="Markdown")
        return

    try:
        file_id = int(context.args[0])
        if delete_material_from_db(file_id):
            await update.message.reply_text(f"✅ تم حذف الملف رقم `{file_id}` بنجاح.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"⚠️ لم يتم العثور على الملف رقم `{file_id}`.")
    except ValueError:
        await update.message.reply_text("⚠️ يرجى كتابة رقم صحيح بعد الأمر.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await log_activity(update, context)
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("sec_"):
        sec_key = data.replace("sec_", "")
        if sec_key == "duas":
            await query.message.reply_text(DUAS_LIST)
            return
            
        items = get_materials_from_db(sec_key)
        if not items:
            await query.message.reply_text("📁 لا توجد ملفات مرفوعة في هذا القسم حالياً.")
            return
            
        for item in items:
            try:
                if item["file_id"]:
                    await context.bot.send_document(chat_id=query.message.chat_id, document=item["file_id"], caption=item["title"])
            except Exception as e:
                logging.error(f"Error sending file: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await log_activity(update, context)
    user_id = update.effective_user.id if update.effective_user else 0
    
    if user_id == OWNER_ID and update.message and update.message.text == SECRET_ADMIN_KEY:
        await start(update, context)
        return

    if user_id == OWNER_ID and update.message and (update.message.document or update.message.photo):
        msg = update.message
        file_id = msg.document.file_id if msg.document else msg.photo[-1].file_id
        title = msg.caption or (msg.document.file_name if msg.document else "ملف")
        pending_files[user_id] = {"file_id": file_id, "title": title}
        
        keyboard = [
            [InlineKeyboardButton("رياضيات", callback_data="up_math"), InlineKeyboardButton("كيمياء", callback_data="up_chemistry")],
            [InlineKeyboardButton("أحياء", callback_data="up_biology"), InlineKeyboardButton("إنجليزي", callback_data="up_english")],
            [InlineKeyboardButton("إسلامية", callback_data="up_islamic"), InlineKeyboardButton("عربي", callback_data="up_arabic")],
            [InlineKeyboardButton("فيزياء", callback_data="up_physics"), InlineKeyboardButton("الهياكل الدراسية", callback_data="up_structures")]
        ]
        await msg.reply_text("📁 اختر القسم المناسب لإضافة الملف:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if update.message and update.message.text and gemini_client:
        try:
            response = gemini_client.models.generate_content(model="gemini-2.5-flash", contents=update.message.text)
            if response and response.text:
                await update.message.reply_text(response.text)
        except Exception as e:
            logging.error(f"Gemini Error: {e}")

async def handle_upload_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != OWNER_ID: return
    data = query.data
    if data.startswith("up_"):
        sec_key = data.replace("up_", "")
        file_info = pending_files.get(OWNER_ID)
        if file_info:
            add_material_to_db(sec_key, file_info["title"], file_info["file_id"])
            await query.message.edit_text("✅ تم حفظ الملف في القسم بنجاح!")
            pending_files.pop(OWNER_ID, None)

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token: return
    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("delete", delete_material_command))
    application.add_handler(CallbackQueryHandler(handle_upload_selection, pattern="^up_"))
    application.add_handler(CallbackQueryHandler(handle_callback, pattern="^sec_"))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
