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

client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

material_files = {
    "islamic": [],
    "arabic": [],
    "math": [],
    "english": [],
    "chemistry": [],
    "biology": [],
    "physics": [],
    "ai_assistant": []
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    
    keyboard = [
        [InlineKeyboardButton("التربية الإسلامية", callback_data="islamic"), InlineKeyboardButton("اللغة العربية", callback_data="arabic")],
        [InlineKeyboardButton("الرياضيات", callback_data="math"), InlineKeyboardButton("اللغة الإنجليزية", callback_data="english")],
        [InlineKeyboardButton("الكيمياء", callback_data="chemistry"), InlineKeyboardButton("الأحياء", callback_data="biology")],
        [InlineKeyboardButton("الفيزياء", callback_data="physics")],
        [InlineKeyboardButton("المساعد الذكي 🤖", callback_data="ai_assistant")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"أهلاً بك يا {user_name} في بوت أكاديمية الفلاح (Seniors 27)! 🎓\n"
        "أنا جاهز لمساعدتك في استرجاع الملفات الدراسية والإجابة على أسئلتك الأكاديمية طوال الـ 24 ساعة.\n\n"
        "اختر المادة أو القسم المطلوب من القائمة أدناه:\n\n"
        "✨ **Strongest Batch 27?**\n"
        "🎓 Senior27 | Al Falah Academy | MBZ 🇦🇪"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "ai_assistant":
        await query.message.reply_text("مرحباً بك في قسم **المساعد الذكي**. أرسل لي أي سؤال أكاديمي وسأقوم بمساعدتك فوراً!")
        return

    files_list = material_files.get(data, [])
    if not files_list:
        await query.message.reply_text("عذراً، لا توجد ملفات مرفوعة في هذا القسم حتى الآن. ترقبها قريباً! 📚")
        return

    response_text = f"📂 **قائمة ملفات قسم ({data.upper()})**:\n\n"
    for idx, f_item in enumerate(files_list, 1):
        response_text += f"{idx}. {f_item['title']}\n"
    
    response_text += "\nلتحميل أي ملف، أرسل رقمه أو اضغط عليه مباشرة."
    await query.message.reply_text(response_text, parse_mode="Markdown")

async def handle_channel_or_admin_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post or update.message
    if not message:
        return

    chat_id = message.chat_id
    if message.document or message.video or message.audio:
        caption = message.caption or "ملف تعليمي بدون عنوان"
        file_id = message.document.file_id if message.document else (message.video.file_id if message.video else message.audio.file_id)
        
        assigned_category = "math"
        lower_cap = caption.lower()
        if "اسلام" in lower_cap or "islamic" in lower_cap:
            assigned_category = "islamic"
        elif "عرب" in lower_cap or "arabic" in lower_cap:
            assigned_category = "arabic"
        elif "رياضيات" in lower_cap or "math" in lower_cap:
            assigned_category = "math"
        elif "إنجليز" in lower_cap or "english" in lower_cap:
            assigned_category = "english"
        elif "كيمياء" in lower_cap or "chem" in lower_cap:
            assigned_category = "chemistry"
        elif "أحياء" in lower_cap or "bio" in lower_cap:
            assigned_category = "biology"
        elif "فيزياء" in lower_cap or "phys" in lower_cap:
            assigned_category = "physics"

        material_files[assigned_category].append({
            "title": caption,
            "file_id": file_id
        })

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ تم سحب الملف بنجاح وإضافته إلى قسم ({assigned_category}) في البوت الأساسي!"
        )

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("استلمت رسالتك. استخدم الأمر /start لعرض قائمة المواد الدراسية.")

def main():
    if not TELEGRAM_TOKEN:
        print("خطأ: لم يتم العثور على TELEGRAM_TOKEN في متغيرات البيئة!")
        return

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.AUDIO, handle_channel_or_admin_files))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_messages))

    print("تم بدء تشغيل البوت المطور بنجاح والاستماع للطلبات...")
    
    # التشغيل الآمن المتوافق مع حلقة الأحداث
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            application.run_polling()
        else:
            asyncio.set_event_loop(loop)
            application.run_polling()
    except Exception:
        application.run_polling()

if __name__ == '__main__':
    main()
