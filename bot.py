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

# الأيدي الخاص بك (المالك) وصديقك (المشرف المخصص للحذف)
OWNER_ID = 1329113404
ADMIN_ID = 1110343074  # أيدي صديقك المشرف المخصص للحذف فقط
SECRET_ADMIN_KEY = "mpol90mpol90@123"  # كلمة السر الخاصة بك كمالك للبوت

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

# --- 2. دوال التعامل مع قاعدة البيانات ---
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
            content = f"📌 [محتوى آخر]"
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

# --- 5. أوامر البوت والتفاعل الأساسي ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await log_activity(update, context)
    user_id = update.effective_user.id if update.effective_user else 0
    user_name = update.effective_user.first_name if update.effective_user and update.effective_user.first_name else "طالب"
    
    # التحقق مما إذا أرسل المالك كلمة السر ضمن الأمر أو الرسالة
    if user_id == OWNER_ID and context.args and context.args[0] == SECRET_ADMIN_KEY:
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, full_name, msg_type, content, timestamp FROM user_logs ORDER BY timestamp DESC LIMIT 20")
            logs = cursor.fetchall()
            cursor.close()
            conn.close()
            
            logs_text = "📊 **لوحة تحكم المالك وسجلات التفاعلات الأخيرة:**\n\n"
            for log in logs:
                logs_text += f"👤 {log[2]} (@{log[1]} - ID: `{log[0]}`)\n💬 النوع: {log[3]} | المحتوى: {log[4]}\n⏰ {log[5]}\n-------------------\n"
            await update.message.reply_text(logs_text[:4000], parse_mode="Markdown")
            return
        except Exception as e:
            await update.message.reply_text(f"خطأ في جلب السجلات: {e}")
            return

    keyboard = [
        [InlineKeyboardButton("التربية الإسلامية", callback_data="sec_islamic"), InlineKeyboardButton("اللغة العربية", callback_data="sec_arabic")],
        [InlineKeyboardButton("الرياضيات", callback_data="sec_math"), InlineKeyboardButton("اللغة الإنجليزية", callback_data="sec_english")],
        [InlineKeyboardButton("الكيمياء", callback_data="sec_chemistry"), InlineKeyboardButton("الأحياء", callback_data="sec_biology")],
        [InlineKeyboardButton("الفيزياء", callback_data="sec_physics"), InlineKeyboardButton("أدعية وأذكار 🤲", callback_data="sec_duas")],
        [InlineKeyboardButton("الجداول 📅", callback_data="sec_schedules"), InlineKeyboardButton("📁 الهياكل الدراسية", callback_data="sec_structures")],
        [InlineKeyboardButton("✨ Senior 27 | Al Falah Academy | MBZ", callback_data="batch_badge")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"أهلاً بك يا {user_name} في بوت الصف الثاني عشر المتقدم!\n"
        "🎓 Senior 27 | Al Falah Academy | MBZ 🇦🇪\n\n"
        "اختر المادة الدراسية أو قسم الهياكل من الأزرار أدناه:"
    )

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

# أمر الحذف المخصص لصديقك أو لك
async def delete_material_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await log_activity(update, context)
    user_id = update.effective_user.id if update.effective_user else 0
    
    # السماح فقط للمالك أو لصديقك المشرف بالحذف واستعراض الملفات مع أرقامها
    if user_id not in [OWNER_ID, ADMIN_ID]:
        return

    # إذا أرسل أمر /delete بدون رقم الملف، نعرض له قائمة بجميع الملفات وأرقامها مصنفة حسب المواد
    if not context.args:
        text = "📋 **قائمة جميع الملفات والمواد المسجلة في البوت:**\n\n"
        for sec_key, sec_title in SECTION_NAMES.items():
            items = get_materials_from_db(sec_key)
            if items:
                text += f"📂 **{sec_title}**:\n"
                for item in items:
                    text += f"  - رقم الملف (`{item['id']}`): {item['title']}\n"
                text += "\n"
        text += "⚠️ لحذف أي ملف، أرسل الأمر هكذا متبوعاً برقم الملف:\n`/delete [رقم_الملف]`"
        await update.message.reply_text(text, parse_mode="Markdown")
        return

    try:
        file_id = int(context.args[0])
        success = delete_material_from_db(file_id)
        if success:
            await update.message.reply_text(f"✅ تم حذف الملف برقم `{file_id}` بنجاح تام.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"⚠️ لم يتم العثور على ملف برقم `{file_id}`.", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("⚠️ يرجى كتابة رقم صحيح للملف بعد الأمر.")

# معالجة الضغط على الأزرار والأقسام (بما فيها الهياكل)
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
            
        sec_title = SECTION_NAMES.get(sec_key, "المادة")
        items = get_materials_from_db(sec_key)
        
        if not items:
            await query.message.reply_text(f"📁 قسم **{sec_title}** لا توجد فيه ملفات مرفوعة حالياً.", parse_mode="Markdown")
            return
            
        for item in items:
            try:
                if item["file_id"]:
                    await context.bot.send_document(chat_id=query.message.chat_id, document=item["file_id"], caption=item["title"])
            except Exception as e:
                logging.error(f"Error sending file: {e}")

# معالجة رسائل رفع الملفات (إذا أرسلت أنت كمالك ملفاً جديداً)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await log_activity(update, context)
    user_id = update.
