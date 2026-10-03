import os
import logging
import asyncio
import psycopg2
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

ADMIN_ID = 1329113404
SECRET_ADMIN_KEY = "mpol90mpol90@555 fl"

def get_db():
    if not DATABASE_URL:
        return None
    # إضافة مهلة زمنية للاتصال 5 ثوانٍ لمنع تعليق البوت
    return psycopg2.connect(DATABASE_URL, connect_timeout=5)

def init_db():
    if not DATABASE_URL:
        print("⚠️ DATABASE_URL غير معرف في متغيرات البيئة!")
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
    if sec in ["arabic", "اللغة العربية", "عربي"]:
        sec = "arabic"
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
    if sec in ["arabic", "اللغة العربية", "عربي"]:
        sec = "arabic"
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

# --- 4. تسجيل الحركات في الخلفية بشكل آمن ---
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
        elif msg.voice:
            msg_type = "voice"
            content = "🎤 [تسجيل صوتي]"
        elif msg.audio:
            msg_type = "audio"
            content = f"🎵 [صوت: {msg.audio.title or 'مقطع'}]"
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

# --- 5. أوامر البوت العامة (قائمة المواد للجميع) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "طالب"
    
    # القائمة الرئيسية تظهر دائماً للجميع (حتى للأدمن)
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
        f"أهلاً بك يا {user_name} في سنتك الدراسية الختامية!\n"
        "🎓 Senior 27 | Al Falah Academy | MBZ 🇦🇪"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "batch_badge":
        await query.message.reply_text("🎓 Senior 27 | Al Falah Academy | MBZ 🇦🇪")
        return

    if data.startswith("sec_"):
        sec_key = data.replace("sec_", "").strip().lower()
        if sec_key in ["arabic", "اللغة العربية", "عربي"]:
            sec_key = "arabic"
        
        if sec_key == "duas":
            await query.message.reply_text(DUAS_LIST)
            return

        files_list = get_materials_from_db(sec_key)
        
        if not files_list:
            await query.message.reply_text(f"عذراً، لا توجد ملفات مرفوعة في قسم ({SECTION_NAMES.get(sec_key, sec_key)}) حتى الآن. 📚")
            return

        keyboard = []
        for f_item in files_list:
            keyboard.append([InlineKeyboardButton(f"📄 {f_item['title']}", callback_data=f"getfile_{f_item['id']}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            f"📂 قائمة ملفات قسم ({SECTION_NAMES.get(sec_key, sec_key)}):\nاضغط على الملف لتنزيله فوراً:",
            reply_markup=reply_markup
        )
        return

    if data.startswith("getfile_"):
        file_id_db = int(data.replace("getfile_", ""))
        try:
            conn = get_db()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT title, file_id FROM materials WHERE id = %s", (file_id_db,))
                row = cursor.fetchone()
                cursor.close()
                conn.close()

                if row:
                    title, file_id = row
                    await query.message.reply_document(
                        document=file_id,
                        caption=f"📄 {title}\n\n🎓 Senior 27 | Al Falah Academy | MBZ 🇦🇪"
                    )
                    return
        except Exception as e:
            logging.error(f"Error fetching file: {e}")

        await query.message.reply_text("❌ عذراً، هذا الملف لم يعد متوفراً.")
        return

    if data.startswith("assign_"):
        parts = data.split("_", 2)
        target_sec = parts[1].strip().lower()
        if target_sec in ["arabic", "اللغة العربية", "عربي"]:
            target_sec = "arabic"
            
        file_token = parts[2]

        file_data = pending_files.get(file_token)
        if not file_data:
            await query.message.edit_text("❌ انتهت صلاحية هذا الطلب أو تم تسجيل الملف مسبقاً.")
            return

        add_material_to_db(target_sec, file_data["title"], file_data["file_id"])
        del pending_files[file_token]

        await query.message.edit_text(
            f"✅ تم حفظ الملف بنجاح في قاعدة البيانات السحابية!\n"
            f"📌 العنوان: {file_data['title']}\n"
            f"📂 القسم: {SECTION_NAMES.get(target_sec, target_sec)}"
        )
        return

async def handle_incoming_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post or update.message
    if not message:
        return

    if message.document or message.video or message.audio:
        caption = message.caption or (message.document.file_name if message.document else "ملف تعليمي بدون عنوان")
        file_id = message.document.file_id if message.document else (message.video.file_id if message.video else message.audio.file_id)
        
        file_token = str(len(pending_files) + 1000)
        pending_files[file_token] = {
            "title": caption,
            "file_id": file_id
        }

        keyboard = [
            [InlineKeyboardButton("الرياضيات 📐", callback_data=f"assign_math_{file_token}"), InlineKeyboardButton("اللغة العربية 📚", callback_data=f"assign_arabic_{file_token}")],
            [InlineKeyboardButton("اللغة الإنجليزية 🔤", callback_data=f"assign_english_{file_token}"), InlineKeyboardButton("الفيزياء ⚡", callback_data=f"assign_physics_{file_token}")],
            [InlineKeyboardButton("الكيمياء 🧪", callback_data=f"assign_chemistry_{file_token}"), InlineKeyboardButton("الأحياء 🧬", callback_data=f"assign_biology_{file_token}")],
            [InlineKeyboardButton("التربية الإسلامية ☪️", callback_data=f"assign_islamic_{file_token}"), InlineKeyboardButton("الجداول الدراسية 📅", callback_data=f"assign_schedules_{file_token}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await message.reply_text(
            f"📥 تم استلام الملف: {caption}\n\n"
            f"رجاءً، اختر القسم المناسب لإضافة هذا الملف إليه:",
            reply_markup=reply_markup
        )

# --- 6. لوحة تحكم المشرف (تظهر فقط عند كتابة /admin أو /stats أو كلمة السر) ---
async def secret_admin_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    text = update.message.text.strip()

    if text == SECRET_ADMIN_KEY and user_id == ADMIN_ID:
        admin_panel = (
            "🔐 مرحباً بك يا مدير البوت!\n\n"
            "إليك الأوامر الخاصة بك فقط:\n\n"
            "📊 /stats - لعرض الإحصائيات وعدد المستخدمين والملفات\n"
            "👥 /users - لعرض قائمة حسابات جميع من استخدم البوت\n"
            "📜 /user_logs ID - لرؤية كل رسائل وتفاعلات شخص معين\n"
            "🗑 /delete - لعرض وتحديد الملفات لحذفها من البوت\n\n"
            "📌 أمثلة: /delete 5 أو /user_logs 1329113404"
        )
        await update.message.reply_text(admin_panel)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    admin_panel = (
        "🔐 لوحة تحكم الأدمن:\n\n"
        "📊 /stats - إحصائيات البوت\n"
        "👥 /users - قائمة المستخدمين\n"
        "📜 /user_logs ID - سجل تفاعلات مستخدم\n"
        "🗑 /delete - حذف ملف من البوت"
    )
    await update.message.reply_text(admin_panel)

async def delete_file_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if context.args:
        try:
            f_id = int(context.args[0])
            if delete_material_from_db(f_id):
                await update.message.reply_text(f"✅ تم حذف الملف رقم ({f_id}) بنجاح.")
            else:
                await update.message.reply_text(f"❌ لم يتم العثور على ملف بالرقم ({f_id}).")
        except ValueError:
            await update.message.reply_text("❌ يرجى إدخال رقم ID صحيح.")
    else:
        try:
            conn = get_db()
            if not conn: return
            cursor = conn.cursor()
            cursor.execute("SELECT id, section, title FROM materials ORDER BY id DESC")
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            if not rows:
                await update.message.reply_text("📂 لا توجد ملفات مخزنة حالياً.")
                return

            msg_text = "🗑 قائمة الملفات المخزنة لحذف أي ملف:\n\n"
            for r in rows:
                sec_display = SECTION_NAMES.get(r[1], r[1])
                msg_text += f"🆔 {r[0]} | {sec_display}: {r[2]}\n"
            
            msg_text += "\n📌 مثال للحذف: /delete 3"
            await update.message.reply_text(msg_text)
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {e}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        conn = get_db()
        if not conn:
            await update.message.reply_text("❌ متعذر الاتصال بقاعدة البيانات حالياً.")
            return
        c = conn.cursor()
        c.execute("SELECT COUNT(DISTINCT user_id) FROM user_logs")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM user_logs")
        total_actions = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM materials")
        total_files = c.fetchone()[0]
        c.close()
        conn.close()

        msg = (
            f"📊 إحصائيات البوت (السحابية الدائمة):\n\n"
            f"👥 عدد المستخدمين: {total_users}\n"
            f"💬 إجمالي التفاعلات: {total_actions}\n"
            f"📚 إجمالي الملفات المخزنة: {total_files}"
        )
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في جلب الإحصائيات: {e}")

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        conn = get_db()
        if not conn: return
        c = conn.cursor()
        c.execute('''
            SELECT user_id, username, full_name, COUNT(*) as interaction_count 
            FROM user_logs 
            GROUP BY user_id, username, full_name
            ORDER BY interaction_count DESC
        ''')
        rows = c.fetchall()
        c.close()
        conn.close()

        if not rows:
            await update.message.reply_text("👥 لا يوجد مستخدمون مسجلون حتى الآن.")
            return

        msg = f"👥 قائمة مستخدمي البوت ({len(rows)}):\n\n"
        for r in rows:
            uid, uname, fname, count = r
            safe_fname = fname if fname else "بدون اسم"
            safe_uname = f"@{uname}" if uname and uname != "بدون_معرف" else "بدون معرف"
            msg += (
                f"👤 الاسم: {safe_fname}\n"
                f"🔗 المعرف: {safe_uname}\n"
                f"🆔 User ID: {uid}\n"
                f"💬 عدد التفاعلات: {count}\n"
                f"-------------------\n"
            )
        
        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ أثناء جلب القائمة: {e}")

async def user_logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("يرجى إدخال ID المستخدم.")
        return

    target_id = context.args[0]
    try:
        conn = get_db()
        if not conn: return
        c = conn.cursor()
        c.execute('''
            SELECT msg_type, content, timestamp 
            FROM user_logs 
            WHERE user_id = %s 
            ORDER BY timestamp DESC LIMIT 20
        ''', (int(target_id),))
        rows = c.fetchall()
        c.close()
        conn.close()

        if not rows:
            await update.message.reply_text(f"لم يتم العثور على أي تفاعلات للمستخدم ({target_id}).")
            return

        msg = f"📜 سجل تفاعلات المستخدم ({target_id}):\n\n"
        for r in rows:
            mtype, content, time = r
            msg += f"⏱ [{time}]\n💬 {content}\n-------------------\n"

        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {e}")

# --- 7. تشغيل البوت ---
def main():
    if not TELEGRAM_TOKEN:
        print("خطأ: لم يتم العثور على TELEGRAM_TOKEN!")
        return

    application = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .concurrent_updates(True)
        .build()
    )

    application.add_handler(MessageHandler(filters.ALL, log_activity), group=-1)
    application.add_handler(CallbackQueryHandler(log_activity), group=-1)

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, secret_admin_auth))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.AUDIO, handle_incoming_files))

    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("delete", delete_file_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("user_logs", user_logs_command))

    print("تم بدء تشغيل البوت المربوط بقاعدة البيانات السحابية...")
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    application.run_polling(close_loop=False)

if __name__ == '__main__':
    main()
