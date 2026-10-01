import os
import logging
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from openai import OpenAI

# خادم وهمي لترضية منصة Render
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "49e5a536511d1949725661ddcba811ff00aef292257942bd4701b3161e16cb7c")
TARGET_CHANNEL_ID = -1004332814800

# إعداد عميل OpenAI
client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# هيكلة تخزين الملفات والمواد تشمل الأقسام الجديدة (أدعية وجداول)
material_files = {
    "islamic": [],
    "arabic": [],
    "math": [],
    "english": [],
    "chemistry": [],
    "biology": [],
    "physics": [],
    "duas": [],
    "schedules": [],
    "ai_assistant": []
}

user_current_section = {}
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    
    keyboard = [
        [InlineKeyboardButton("التربية الإسلامية", callback_data="sec_islamic"), InlineKeyboardButton("اللغة العربية", callback_data="sec_arabic")],
        [InlineKeyboardButton("الرياضيات", callback_data="sec_math"), InlineKeyboardButton("اللغة الإنجليزية", callback_data="sec_english")],
        [InlineKeyboardButton("الكيمياء", callback_data="sec_chemistry"), InlineKeyboardButton("الأحياء", callback_data="sec_biology")],
        [InlineKeyboardButton("الفيزياء", callback_data="sec_physics"), InlineKeyboardButton("أدعية وأذكار 🤲", callback_data="sec_duas")],
        [InlineKeyboardButton("الجداول 📅", callback_data="sec_schedules"), InlineKeyboardButton("المساعد الذكي 🤖", callback_data="sec_ai_assistant")],
        [InlineKeyboardButton("✨ أقوى دفعة 27 ؟", callback_data="batch_badge")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # تم تغيير المقدمة كما طلبت تماماً
    welcome_text = (
        f"مرحباً بك يا {user_name} في البوت الرسمي لدفعة 27 (أكاديمية الفلاح)! 🎓\n"
        "بوابتك المتكاملة للوصول إلى كافة الملفات، الجداول الدراسية، والمساعد الذكي بكل سهولة.\n\n"
        "اختر ما تحتاجه من القائمة أدناه:"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    # زر الشعار الثابت
    if data == "batch_badge":
        await query.message.reply_text("🎓 Senior27 | Al Falah Academy | MBZ 🇦🇪")
        return

    # إذا كان الضغط لاختيار قسم لعرض الملفات
    if data.startswith("sec_"):
        sec_key = data.replace("sec_", "")
        
        if sec_key == "ai_assistant":
            user_current_section[user_id] = "ai_assistant"
            await query.message.reply_text("مرحباً بك في قسم **المساعد الذكي** 🤖.\nأرسل لي أي استفسار أو سؤال أكاديمي وسأقوم بالإجابة عليه فوراً!")
            return

        user_current_section[user_id] = sec_key
        files_list = material_files.get(sec_key, [])
        
        if not files_list:
            await query.message.reply_text(f"عذراً، لا توجد ملفات مرفوعة في قسم ({SECTION_NAMES.get(sec_key, sec_key)}) حتى الآن. 📚")
            return

        response_text = f"📂 **قائمة ملفات قسم ({SECTION_NAMES.get(sec_key, sec_key)})**:\n\n"
        for idx, f_item in enumerate(files_list, 1):
            response_text += f"{idx}. {f_item['title']}\n"
        
        response_text += "\nلتحميل أي ملف، أرسل رقمه مباشرة في الشات."
        await query.message.reply_text(response_text, parse_mode="Markdown")
        return

    # إذا كان الضغط لتصنيف ملف جديد أرسله المشرف
    if data.startswith("assign_"):
        parts = data.split("_", 2)
        target_sec = parts[1]
        file_token = parts[2]

        file_data = pending_files.get(file_token)
        if not file_data:
            await query.message.edit_text("❌ انتهت صلاحية هذا الطلب أو تم تسجيل الملف مسبقاً.")
            return

        material_files[target_sec].append({
            "title": file_data["title"],
            "file_id": file_data["file_id"]
        })

        del pending_files[file_token]

        await query.message.edit_text(
            f"✅ **تم حفظ الملف بنجاح!**\n"
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

        # أزرار لتصنيف الملف تشمل الأقسام الدراسية، الأدعية، والجداول
        keyboard = [
            [InlineKeyboardButton("الرياضيات 📐", callback_data=f"assign_math_{file_token}"), InlineKeyboardButton("اللغة العربية 📚", callback_data=f"assign_arabic_{file_token}")],
            [InlineKeyboardButton("اللغة الإنجليزية 🔤", callback_data=f"assign_english_{file_token}"), InlineKeyboardButton("الفيزياء ⚡", callback_data=f"assign_physics_{file_token}")],
            [InlineKeyboardButton("الكيمياء 🧪", callback_data=f"assign_chemistry_{file_token}"), InlineKeyboardButton("الأحياء 🧬", callback_data=f"assign_biology_{file_token}")],
            [InlineKeyboardButton("التربية الإسلامية ☪️", callback_data=f"assign_islamic_{file_token}"), InlineKeyboardButton("أدعية وأذكار 🤲", callback_data=f"assign_duas_{file_token}")],
            [InlineKeyboardButton("الجداول الدراسية 📅", callback_data=f"assign_schedules_{file_token}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await message.reply_text(
            f"📥 **تم استلام الملف:** {caption}\n\n"
            f"رجاءً، اختر القسم المناسب لإضافة هذا الملف إليه:",
            reply_markup=reply_markup
        )

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.message.from_user.id

    # التحقق من إرسال رقم لتحميل ملف من القسم المفتوح
    if text.isdigit():
        current_sec = user_current_section.get(user_id)
        if current_sec and current_sec in material_files:
            file_index = int(text) - 1
            files_list = material_files[current_sec]
            if 0 <= file_index < len(files_list):
                target_file = files_list[file_index]
                await update.message.reply_document(
                    document=target_file['file_id'],
                    caption=f"📄 {target_file['title']}\n\n🎓 Senior27 | Al Falah Academy | MBZ 🇦🇪"
                )
                return
            else:
                await update.message.reply_text("❌ الرقم الذي أرسلته غير موجود في قائمة هذا القسم.")
                return

    # معالجة المساعد الذكي بدون أي أخطاء ومنع تعطل البوت
    if user_current_section.get(user_id) == "ai_assistant":
        try:
            response = client.chat.completions.create(
                model="openai/gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "أنت مساعد أكاديمي ذكي ومفيد جداً لطلاب أكاديمية الفلاح دفعة 27."},
                    {"role": "user", "content": text}
                ],
                timeout=20
            )
            ai_reply = response.choices[0].message.content
            await update.message.reply_text(ai_reply)
        except Exception as e:
            logging.error(f"OpenAI Error: {e}")
            await update.message.reply_text("عذراً، حدث ضغط مؤقت في الخدمة الذكية. أعد إرسال سؤالك وسأجيبك فوراً!")
        return

    await update.message.reply_text("استلمت رسالتك. استخدم الأمر /start لعرض القائمة الرئيسية والمواد الدراسية.")

def main():
    if not TELEGRAM_TOKEN:
        print("خطأ: لم يتم العثور على TELEGRAM_TOKEN في متغيرات البيئة!")
        return

    # إعدادات متقدمة لدعم الأداء العالي والعمل المتزامن لآلاف الطلاب بدون أي تعطل
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

    print("تم بدء تشغيل البوت المطور بنجاح وبأقصى كفاءة...")
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    application.run_polling(close_loop=False)

if __name__ == '__main__':
    main()
