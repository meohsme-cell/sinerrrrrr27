import os
import logging
import psycopg2
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

OWNER_ID = 1329113404
ADMIN_ID = 1110343074
SECRET_ADMIN_KEY = "mpol90mpol90@123"

def get_db():
    if not DATABASE_URL: return None
    return psycopg2.connect(DATABASE_URL, connect_timeout=5)

def init_db():
    if not DATABASE_URL: return
    try:
        conn = get_db()
        if not conn: return
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS materials (id SERIAL PRIMARY KEY, section TEXT, title TEXT, file_id TEXT);''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS user_logs (id SERIAL PRIMARY KEY, user_id BIGINT, username TEXT, full_name TEXT, msg_type TEXT, content TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP);''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS pending_uploads (owner_id BIGINT PRIMARY KEY, file_id TEXT, title TEXT);''')
        conn.commit()
        cursor.close()
        conn.close()
    except: pass

try: init_db()
except: pass

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
    except: return []

def get_material_by_id(mat_id):
    try:
        conn = get_db()
        if not conn: return None
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, file_id FROM materials WHERE id = %s", (mat_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            return {"id": row[0], "title": row[1], "file_id": row[2]}
        return None
    except: return None

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
        logging.error(f"DB Add Error: {e}")

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
    except: return False

def save_pending_to_db(owner_id, file_id, title):
    try:
        conn = get_db()
        if not conn: return
        cursor = conn.cursor()
        cursor.execute("INSERT INTO pending_uploads (owner_id, file_id, title) VALUES (%s, %s, %s) ON CONFLICT (owner_id) DO UPDATE SET file_id = EXCLUDED.file_id, title = EXCLUDED.title", (owner_id, file_id, title))
        conn.commit()
        cursor.close()
        conn.close()
    except: pass

def get_pending_from_db(owner_id):
    try:
        conn = get_db()
        if not conn: return None
        cursor = conn.cursor()
        cursor.execute("SELECT file_id, title FROM pending_uploads WHERE owner_id = %s", (owner_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            return {"file_id": row[0], "title": row[1]}
        return None
    except: return None

def clear_pending_from_db(owner_id):
    try:
        conn = get_db()
        if not conn: return
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pending_uploads WHERE owner_id = %s", (owner_id,))
        conn.commit()
        cursor.close()
        conn.close()
    except: pass

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

SECTION_NAMES = {
    "math": "الرياضيات",
    "chemistry": "الكيمياء",
    "biology": "الأحياء",
    "english": "اللغة الإنجليزية",
    "islamic": "التربية الإسلامية",
    "arabic": "اللغة العربية",
    "physics": "الفيزياء",
    "duas": "أدعية وأذكار",
    "schedules": "الجداول الدراسية",
    "struct_math": "هيكل الرياضيات",
    "struct_chemistry": "هيكل الكيمياء",
    "struct_biology": "هيكل الأحياء",
    "struct_english": "هيكل الإنجليزية",
    "struct_islamic": "هيكل الإسلامية",
    "struct_arabic": "هيكل العربية",
    "struct_physics": "هيكل الفيزياء"
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

async def post_init(application):
    commands = [BotCommand("start", "تشغيل البوت وعرض مواد الصف الثاني عشر 🎓")]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else 0
    
    if user_id == OWNER_ID and context.args and context.args[0] == SECRET_ADMIN_KEY:
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, full_name, msg_type, content, timestamp FROM user_logs ORDER BY timestamp DESC LIMIT 20")
            logs = cursor.fetchall()
            cursor.close()
            conn.close()
            logs_text = "📊 **سجلات التفاعلات الأخيرة:**\n\n"
            for log in logs:
                logs_text += f"👤 {log[2]} (@{log[1]} - ID: `{log[0]}`)\n💬 {log[3]}: {log[4]}\n⏰ {log[5]}\n-------------------\n"
            await update.message.reply_text(logs_text[:4000], parse_mode="Markdown")
            return
        except Exception as e:
            await update.message.reply_text(f"خطأ: {e}")
            return

    keyboard = [
        [InlineKeyboardButton("رياضيات", callback_data="sec_math"), InlineKeyboardButton("كيمياء", callback_data="sec_chemistry")],
        [InlineKeyboardButton("أحياء", callback_data="sec_biology"), InlineKeyboardButton("إنجليزي", callback_data="sec_english")],
        [InlineKeyboardButton("إسلامية", callback_data="sec_islamic"), InlineKeyboardButton("عربي", callback_data="sec_arabic")],
        [InlineKeyboardButton("فيزياء", callback_data="sec_physics"), InlineKeyboardButton("أدعية وأذكار", callback_data="sec_duas")],
        [InlineKeyboardButton("الجداول الدراسية", callback_data="sec_schedules"), InlineKeyboardButton("📁 الهياكل الدراسية", callback_data="open_structures")],
        [InlineKeyboardButton("🎓 Senior27 | Al Falah Academy | MBZ 🇦🇪", callback_data="batch_badge")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "أهلاً بك! استخدم القائمة الرئيسية لتصفح مواد الصف الثاني عشر 🎓",
        reply_markup=reply_markup
    )

async def delete_material_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # إذا لم يكتب رقم بعد الأمر، اعرض له كل الملفات مصنفة حسب الأقسام والمواد
    if not context.args:
        text = "📋 **قائمة كافة الملفات مرتبة حسب الأقسام والمواد (للحذف):**\n\n"
        has_items = False
        
        for sec_key, sec_title in SECTION_NAMES.items():
            items = get_materials_from_db(sec_key)
            if items:
                has_items = True
                text += f"📂 **{sec_title}**:\n"
                for item in items:
                    text += f"   🔹 رقم (`{item['id']}`): {item['title']}\n"
                text += "\n"
        
        if not has_items:
            await update.message.reply_text("📁 قاعدة البيانات فارغة تماماً ولا توجد أي ملفات مرفوعة حتى الآن.")
            return

        text += "⚠️ **طريقة الحذف:** أرسل الأمر متبوعاً برقم الملف هكذا:\n`/delete [رقم_الملف]` (مثال: `/delete 5`)"
        
        # تقسيم الرسالة إذا كانت طويلة لكي لا ترفضها تيليجرام
        if len(text) > 4000:
            for i in range(0, len(text), 4000):
                await update.message.reply_text(text[i:i+4000], parse_mode="Markdown")
        else:
            await update.message.reply_text(text, parse_mode="Markdown")
        return

    # إذا كتب رقم بعد الأمر (مثلاً /delete 3)
    try:
        file_id = int(context.args[0])
        if delete_material_from_db(file_id):
            await update.message.reply_text(f"✅ تم حذف الملف رقم `{file_id}` بنجاح.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"⚠️ لم يتم العثور على الملف رقم `{file_id}`.")
    except ValueError:
        await update.message.reply_text("⚠️ يرجى كتابة رقم صحيح بعد الأمر (مثال: `/delete 1`).", parse_mode="Markdown")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "open_structures":
        struct_keyboard = [
            [InlineKeyboardButton("هيكل رياضيات", callback_data="sec_struct_math"), InlineKeyboardButton("هيكل كيمياء", callback_data="sec_struct_chemistry")],
            [InlineKeyboardButton("هيكل أحياء", callback_data="sec_struct_biology"), InlineKeyboardButton("هيكل إنجليزي", callback_data="sec_struct_english")],
            [InlineKeyboardButton("هيكل إسلامية", callback_data="sec_struct_islamic"), InlineKeyboardButton("هيكل عربية", callback_data="sec_struct_arabic")],
            [InlineKeyboardButton("هيكل فيزياء", callback_data="sec_struct_physics")],
            [InlineKeyboardButton("🔙 عودة للقائمة الرئيسية", callback_data="back_to_main")]
        ]
        await query.message.edit_text("📁 **قسم الهياكل الدراسية**\nاختر المادة لعرض الهياكل الخاصة بها:", reply_markup=InlineKeyboardMarkup(struct_keyboard), parse_mode="Markdown")
        return

    if data == "back_to_main":
        keyboard = [
            [InlineKeyboardButton("رياضيات", callback_data="sec_math"), InlineKeyboardButton("كيمياء", callback_data="sec_chemistry")],
            [InlineKeyboardButton("أحياء", callback_data="sec_biology"), InlineKeyboardButton("إنجليزي", callback_data="sec_english")],
            [InlineKeyboardButton("إسلامية", callback_data="sec_islamic"), InlineKeyboardButton("عربي", callback_data="sec_arabic")],
            [InlineKeyboardButton("فيزياء", callback_data="sec_physics"), InlineKeyboardButton("أدعية وأذكار", callback_data="sec_duas")],
            [InlineKeyboardButton("الجداول الدراسية", callback_data="sec_schedules"), InlineKeyboardButton("📁 الهياكل الدراسية", callback_data="open_structures")],
            [InlineKeyboardButton("🎓 Senior27 | Al Falah Academy | MBZ 🇦🇪", callback_data="batch_badge")]
        ]
        await query.message.edit_text("أهلاً بك! استخدم القائمة الرئيسية لتصفح مواد الصف الثاني عشر 🎓", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("sec_"):
        sec_key = data.replace("sec_", "")
        if sec_key == "duas":
            await query.message.reply_text(DUAS_LIST)
            return
            
        items = get_materials_from_db(sec_key)
        sec_title = SECTION_NAMES.get(sec_key, "القسم")
        if not items:
            await query.message.reply_text(f"📁 قسم **{sec_title}** لا توجد فيه ملفات مرفوعة حالياً.", parse_mode="Markdown")
            return
            
        file_keyboard = []
        for item in items:
            title_short = item["title"] if len(item["title"]) < 40 else item["title"][:37] + "..."
            file_keyboard.append([InlineKeyboardButton(f"📄 {title_short}", callback_data=f"getfile_{item['id']}")])
        
        if sec_key.startswith("struct_"):
            file_keyboard.append([InlineKeyboardButton("🔙 عودة لقسم الهياكل", callback_data="open_structures")])
        else:
            file_keyboard.append([InlineKeyboardButton("🔙 عودة للقائمة الرئيسية", callback_data="back_to_main")])

        await query.message.edit_text(
            f"📂 ملفات قسم **{sec_title}**:\nاختر الملف الذي تريد فتحه وتحميله:",
            reply_markup=InlineKeyboardMarkup(file_keyboard),
            parse_mode="Markdown"
        )
        return

    if data.startswith("getfile_"):
        try:
            mat_id = int(data.replace("getfile_", ""))
            mat = get_material_by_id(mat_id)
            if mat and mat["file_id"]:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=mat["file_id"],
                    caption=f"📄 {mat['title']}"
                )
            else:
                await query.message.reply_text("⚠️ عذراً، هذا الملف غير موجود أو تم حذفه.")
        except:
            await query.message.reply_text("⚠️ حدث خطأ أثناء إرسال الملف.")
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else 0
    
    if user_id == OWNER_ID and update.message and update.message.text == SECRET_ADMIN_KEY:
        await start(update, context)
        return

    if user_id == OWNER_ID and update.message and (update.message.document or update.message.photo):
        msg = update.message
        file_id = msg.document.file_id if msg.document else msg.photo[-1].file_id
        title = msg.caption or (msg.document.file_name if msg.document else "ملف دراسي")
        
        save_pending_to_db(user_id, file
