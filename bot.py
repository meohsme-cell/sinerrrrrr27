import os
import logging
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

# سيرفر خفيف للحفاظ على نشاط البورت في Render
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
    user_id = update.effective_user.id if update.effective_user else 0
    if user_id not in [OWNER_ID, ADMIN_ID]: return

    if not context.args:
        text = "📋 **قائمة كافة الملفات المسجلة وأرقامها (للحذف):**\n\n"
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
            
        for item in items:
            try:
                if item["file_id"]:
                    await context.bot.send_document(chat_id=query.message.chat_id, document=item["file_id"], caption=item["title"])
            except: pass

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else 0
    
    if user_id == OWNER_ID and update.message and update.message.text == SECRET_ADMIN_KEY:
        await start(update, context)
        return

    if user_id == OWNER_ID and update.message and (update.message.document or update.message.photo):
        msg = update.message
        file_id = msg.document.file_id if msg.document else msg.photo[-1].file_id
        title = msg.caption or (msg.document.file_name if msg.document else "ملف دراسي")
        pending_files[user_id] = {"file_id": file_id, "title": title}
        
        keyboard = [
            [InlineKeyboardButton("📁 رياضيات", callback_data="up_math"), InlineKeyboardButton("📁 كيمياء", callback_data="up_chemistry")],
            [InlineKeyboardButton("📁 أحياء", callback_data="up_biology"), InlineKeyboardButton("📁 إنجليزي", callback_data="up_english")],
            [InlineKeyboardButton("📁 إسلامية", callback_data="up_islamic"), InlineKeyboardButton("📁 عربي", callback_data="up_arabic")],
            [InlineKeyboardButton("📁 فيزياء", callback_data="up_physics"), InlineKeyboardButton("📁 الجداول", callback_data="up_schedules")],
            [InlineKeyboardButton("📑 هيكل رياضيات", callback_data="up_struct_math"), InlineKeyboardButton("📑 هيكل كيمياء", callback_data="up_struct_chemistry")],
            [InlineKeyboardButton("📑 هيكل أحياء", callback_data="up_struct_biology"), InlineKeyboardButton("📑 هيكل إنجليزي", callback_data="up_struct_english")],
            [InlineKeyboardButton("📑 هيكل إسلامية", callback_data="up_struct_islamic"), InlineKeyboardButton("📑 هيكل عربية", callback_data="up_struct_arabic")],
            [InlineKeyboardButton("📑 هيكل فيزياء", callback_data="up_struct_physics")]
        ]
        await msg.reply_text("🎯 **تم استلام الملف بنجاح!**\nاختر القسم المناسب أو الهيكل لتخزين هذا الملف فيه مباشرة:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

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
            sec_title = SECTION_NAMES.get(sec_key, sec_key)
            await query.message.edit_text(f"✅ **تم حفظ الملف بنجاح في قسم ({sec_title})!**", parse_mode="Markdown")
            pending_files.pop(OWNER_ID, None)
        else:
            await query.message.edit_text("⚠️ انتهت صلاحية الملف، أرسله مرة أخرى من فضلك.")

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token: return
    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("delete", delete_material_command))
    application.add_handler(CallbackQueryHandler(handle_upload_selection, pattern="^up_"))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    print("Bot is starting polling smoothly...")
    # يتأكد من إلغاء أي ويب هوك قديم والبدء فوراً دون أخطاء
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
