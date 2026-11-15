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

# --- 1. إعداد الاتصال بقاعدة البيانات السحابية (Supabase) ---
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# --- إعداد نموذج Gemini بأمان تام عبر متغير البيئة في Render ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Init Error: {e}")

# --- الصلاحيات والإداريين ---
OWNER_ID = 1329113404        # آيدي المالك (أنت)
ADMIN_ID = 1110343074        # آيدي المشرف المضاف

# كلمة السر الخاصة بفتح لوحة الإدارة
SECRET_ADMIN_KEY = "mpol90mpol90@M7"

def get_db():
    if not DATABASE_URL:
        return None
    return psycopg2.connect(DATABASE_URL, connect_timeout=5)

def init_db():
    if not DATABASE_URL:
        return
    try:
        conn = get_db()
        if not conn:
            return
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

# --- 2. دوال التعامل مع قاعدة البيانات والاحصائيات ---
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

def get_bot_stats():
    try:
        conn = get_db()
        if not conn: return 0, 0, 0
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM user_logs;")
        users_count = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM user_logs;")
        interactions_count = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM materials;")
        materials_count = cursor.fetchone()[0] or 0
        
        cursor.close()
        conn.close()
        return users_count, interactions_count, materials_count
    except Exception as e:
        logging.error(f"Error getting stats: {e}")
        return 0, 0, 0

# --- 3. خادم السيرفر لـ Render ---
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

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
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
    "schedules": "الجداول الدراسية"
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

# --- 4. تسجيل التفاعلات ---
async def log_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not DATABASE_URL:
        return

    user_id = user.id
    username = user.username or "بدون_معرف"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "بدون اسم"

    content = ""
    msg_type = "unknown"

    if update.message:
        msg = update.message
        if msg.text:
            msg_type = "text"
            content = msg.text
        elif msg.document:
            msg_type = "document"
            content = f"📁 [ملف: {msg.document.file_name or 'مستند'}] {msg.caption or ''}"
        elif msg.photo:
            msg_type = "photo"
            content = f"📷 [صورة] {msg.caption or ''}"
        else:
            msg_type = "other"
            content = "📌 [محتوى آخر]"
    elif update.callback_query:
        msg_type = "button_click"
        content = f"🔘 ضغط زر: {update.callback_query.data}"

    try:
        conn = get_db()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_logs (user_id, username, full_name, msg_type, content)
                VALUES (%s, %s, %s, %s, %s)
            ''', (user_id, username, full_name, msg_type, content))
            conn.commit()
            cursor.close()
            conn.close()
    except Exception as e:
        logging.error(f"Error saving log: {e}")

# --- 5. أمر البدء العادي (للجميع) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await log_activity(update, context)
    user_name = update.effective_user.first_name if update.effective_user and update.effective_user.first_name else "طالب"
    
    keyboard = [
        [InlineKeyboardButton("التربية الإسلامية", callback_data="sec_islamic"), InlineKeyboardButton("اللغة العربية", callback_data="sec_arabic")],
        [InlineKeyboardButton("الرياضيات", callback_data="sec_math"), InlineKeyboardButton("اللغة الإنجليزية", callback_data="sec_english")],
        [InlineKeyboardButton("الكيمياء", callback_data="sec_chemistry"), InlineKeyboardButton("الأحياء", callback_data="sec_biology")],
        [InlineKeyboardButton("الفيزياء", callback_data="sec_physics"), InlineKeyboardButton("أدعية وأذكار 🤲", callback_data="sec_duas")],
        [InlineKeyboardButton("الجداول 📅", callback_data="sec_schedules")],
        [InlineKeyboardButton("✨ Senior 27 | Al Falah Academy | MBZ", callback_data="batch_badge")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"أهلاً بك يا {user_name} في بوت الصف الثاني عشر المتقدم!\n"
        "🎓 Senior 27 | Al Falah Academy | MBZ 🇦🇪\n\n"
        "اختر المادة الدراسية التي تريدها من الأزرار أدناه:"
    )

    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    elif update.callback_query:
        try:
            await update.callback_query.message.edit_text(welcome_text, reply_markup=reply_markup)
        except Exception:
            await update.callback_query.message.reply_text(welcome_text, reply_markup=reply_markup)

# --- 6. أمر التحقق بكلمة السر للإدارة (/admin كلمة_السر) ---
async def admin_login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID and user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ عذراً، هذا الأمر غير متاح لك.")
        return

    if not context.args or context.args[0] != SECRET_ADMIN_KEY:
        await update.message.reply_text("❌ كلمة السر غير صحيحة أو ناقصة.\nالاستخدام الصحيح:\n`/admin mpol90mpol90@M7`", parse_mode="Markdown")
        return

    users_count, interactions_count, materials_count = get_bot_stats()
    stats_text = (
        "📊 **لوحة تحكم وإحصائيات البوت السحابية (الإدارة):**\n\n"
        f"👥 **عدد المستخدمين:** {users_count}\n"
        f"💬 **إجمالي التفاعلات:** {interactions_count}\n"
        f"📚 **إجمالي الملفات المخزنة:** {materials_count}\n\n"
        "🗑️ لحذف أي ملف خاطئ، استخدم الأمر متبوعاً برقم الـ ID:\n"
        "`/delete [رقم_الملف]`"
    )
    await update.message.reply_text(stats_text, parse_mode="Markdown")

# --- 7. أمر الحذف الخاص بالإدارة ---
async def delete_material(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID and user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ عذراً، هذا الأمر مخصص للإدارة فقط.")
        return

    if not context.args:
        all_materials_text = "🗑️ **قائمة الملفات المخزنة للحذف:**\n\n"
        total_count = 0
        for sec_key in SECTION_NAMES.keys():
            items = get_materials_from_db(sec_key)
            for item in items:
                all_materials_text += f"🆔 `{item['id']}` | {SECTION_NAMES[sec_key]}: {item['title']}\n"
                total_count += 1

        if total_count == 0:
            await update.message.reply_text("📭 لا توجد أي ملفات مخزنة في البوت حالياً.")
            return

        all_materials_text += f"\n📌 للاستخدام، اكتب الأمر متبوعاً برقم الملف:\n`/delete [رقم_الملف]`"
        
        if len(all_materials_text) > 4000:
            await update.message.reply_text("القائمة طويلة جداً، يرجى كتابة الأمر مع رقم الملف مباشرة، مثال: `/delete 5`")
        else:
            await update.message.reply_text(all_materials_text, parse_mode="Markdown")
        return

    try:
        file_id_to_delete = int(context.args[0])
        success = delete_material_from_db(file_id_to_delete)
        if success:
            await update.message.reply_text(f"✅ تم حذف الملف برقم `ID: {file_id_to_delete}` بنجاح دون المساس بباقي الملفات.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ لم يتم العثور على ملف بهذا الرقم (`ID: {file_id_to_delete}`).")
    except ValueError:
        await update.message.reply_text("⚠️ يرجى كتابة رقم صحيح بعد الأمر. مثال: `/delete 12`")

# --- معالجة الأزرار والتفاعل مع الأقسام ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await log_activity(update, context)
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "sec_duas":
        keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back_home")]]
        await query.message.edit_text(DUAS_LIST, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "back_home" or data == "batch_badge":
        user_name = query.from_user.first_name if query.from_user else "طالب"
        keyboard = [
            [InlineKeyboardButton("التربية الإسلامية", callback_data="sec_islamic"), InlineKeyboardButton("اللغة العربية", callback_data="sec_arabic")],
            [InlineKeyboardButton("الرياضيات", callback_data="sec_math"), InlineKeyboardButton("اللغة الإنجليزية", callback_data="sec_english")],
            [InlineKeyboardButton("الكيمياء", callback_data="sec_chemistry"), InlineKeyboardButton("الأحياء", callback_data="sec_biology")],
            [InlineKeyboardButton("الفيزياء", callback_data="sec_physics"), InlineKeyboardButton("أدعية وأذكار 🤲", callback_data="sec_duas")],
            [InlineKeyboardButton("الجداول 📅", callback_data="sec_schedules")],
            [InlineKeyboardButton("✨ Senior 27 | Al Falah Academy | MBZ", callback_data="batch_badge")]
        ]
        welcome_text = (
            f"أهلاً بك يا {user_name} في بوت الصف الثاني عشر المتقدم!\n"
            "🎓 Senior 27 | Al Falah Academy | MBZ 🇦🇪\n\n"
            "اختر المادة الدراسية التي تريدها من الأزرار أدناه:"
        )
        await query.message.edit_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("sec_"):
        sec_key = data.replace("sec_", "")
        if sec_key in SECTION_NAMES:
            sec_name = SECTION_NAMES[sec_key]
            materials = get_materials_from_db(sec_key)

            if not materials:
                text = f"📂 **قائمة ملفات قسم ({sec_name}):**\n\nعذراً، لا توجد ملفات مرفوعة في هذا القسم حالياً."
            else:
                text = f"📂 **قائمة ملفات قسم ({sec_name}):**\nاضغط على الملف لتنزيله فوراً:\n"
                for m in materials:
                    text += f"\n• {m['title']}"

            keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back_home")]]
            
            try:
                await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            except Exception:
                await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

            if materials:
                for m in materials:
                    try:
                        await context.bot.send_document(chat_id=query.message.chat_id, document=m['file_id'], caption=m['title'])
                    except Exception as e:
                        logging.error(f"Error sending file {m['file_id']}: {e}")

# --- استقبال الملفات من الإدارة لرفعها ---
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await log_activity(update, context)
    user_id = update.effective_user.id
    if user_id != OWNER_ID and user_id != ADMIN_ID:
        return

    message = update.message
    if not message.document:
        return

    file_id = message.document.file_id
    file_name = message.document.file_name or "ملف بدون اسم"
    pending_files[user_id] = {"file_id": file_id, "title": file_name}

    keyboard = [
        [InlineKeyboardButton("التربية الإسلامية", callback_data="up_islamic"), InlineKeyboardButton("اللغة العربية", callback_data="up_arabic")],
        [InlineKeyboardButton("الرياضيات", callback_data="up_math"), InlineKeyboardButton("اللغة الإنجليزية", callback_data="up_english")],
        [InlineKeyboardButton("الكيمياء", callback_data="up_chemistry"), InlineKeyboardButton("الأحياء", callback_data="up_biology")],
        [InlineKeyboardButton("الفيزياء", callback_data="up_physics"), InlineKeyboardButton("أدعية وأذكار", callback_data="up_duas")],
        [InlineKeyboardButton("الجداول الدراسية", callback_data="up_schedules")]
    ]
    await message.reply_text(f"📁 تم استلام الملف: `{file_name}`\n\nالرجاء اختيار القسم الذي تريد رفع الملف إليه:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def upload_section_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id != OWNER_ID and user_id != ADMIN_ID:
        return

    data = query.data
    if data.startswith("up_"):
        sec_key = data.replace("up_", "")
        if user_id in pending_files:
            file_info = pending_files.pop(user_id)
            add_material_to_db(sec_key, file_info["title"], file_info["file_id"])
            sec_display = SECTION_NAMES.get(sec_key, sec_key)
            await query.message.edit_text(f"✅ تم بنجاح حفظ الملف ({file_info['title']}) في قسم ({sec_display})!")
        else:
            await query.message.edit_text("⚠️ انتهت صلاحية العملية أو لم يتم العثور على الملف. أرسل الملف من جديد.")

# --- استقبال رسائل النص ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await log_activity(update, context)
    text = update.message.text
    if not text:
        return

    if gemini_client:
        try:
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=text,
            )
            if response and response.text:
                await update.message.reply_text(response.text)
                return
        except Exception as e:
            logging.error(f"Gemini Error: {e}")

    await update.message.reply_text("أهلاً بك! استخدم القائمة الرئيسية لتصفح مواد الصف الثاني عشر المتقدم 🎓")

# --- دالة تشغيل البوت الرئيسية ---
def main():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN is missing!")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # تسجيل الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_login_command))
    app.add_handler(CommandHandler("delete", delete_material))

    # تسجيل التفاعلات
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(upload_section_callback, pattern="^up_"))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is up and running smoothly...")
    app.run_polling()

if __name__ == "__main__":
    main()
