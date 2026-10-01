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

# هيكلة تخزين الملفات لكل مادة لتتبعها بدقة
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

# لتتبع القسم الحالي الذي يتصفحه كل مستخدم (لمعرفة الملف عند إرسال الرقم)
user_current_section = {}

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
    user_id = query.from_user.id

    if data == "ai_assistant":
        user_current_section[user_id] = "ai_assistant"
        await query.message.reply_text("مرحباً بك في قسم **المساعد الذكي**. أرسل لي أي سؤال أكاديمي وسأقوم بمساعدتك فوراً!")
        return

    # حفظ القسم الذي يتصفحه المستخدم حالياً
    user_current_section[user_id] = data

    files_list = material_files.get(data, [])
    if not files_list:
        await query.message.reply_text("عذراً، لا توجد ملفات مرفوعة في هذا القسم حتى الآن. ترقبها قريباً! 📚")
        return

    section_names = {
        "islamic": "التربية الإسلامية",
        "arabic": "اللغة العربية",
        "math": "الرياضيات",
        "english": "اللغة الإنجليزية",
        "chemistry": "الكيمياء",
        "biology": "الأحياء",
        "physics": "الفيزياء"
    }

    response_text = f"📂 **قائمة ملفات قسم ({section_names.get(data, data)})**:\n\n"
    for idx, f_item in enumerate(files_list, 1):
        response_text += f"{idx}. {f_item['title']}\n"
    
    response_text += "\nلتحميل أي ملف، أرسل رقمه مباشرة في العرض."
    await query.message.reply_text(response_text, parse_mode="Markdown")

async def handle_channel_or_admin_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post or update.message
    if not message:
        return

    chat_id = message.chat_id
    if message.document or message.video or message.audio:
        caption = message.caption or message.document.file_name if message.document else "ملف تعليمي بدون عنوان"
        file_id = message.document.file_id if message.document else (message.video.file_id if message.video else message.audio.file_id)
        
        # تصنيف دقيق جداً بناءً على الكلمات المفتاحية في الوصف أو اسم الملف
        lower_cap = caption.lower()
        assigned_category = None

        if any(w in lower_cap for w in ["اسلام", "إسلام", "islam", "ديني", "قرآن", "شرعي"]):
            assigned_category = "islamic"
        elif any(w in lower_cap for w in ["عرب", "arabic", "لغة عربية", "نحو", "بلاغة", "مقدمة"]):
            assigned_category = "arabic"
        elif any(w in lower_cap for w in ["رياضيات", "math", "رياضيات", "جبر", "هندسة", "حساب"]):
            assigned_category = "math"
        elif any(w in lower_cap for w in ["إنجليز", "انجلير", "english", "eng"]):
            assigned_category = "english"
        elif any(w in lower_cap for w in ["كيمياء", "chem", "كيميا"]):
            assigned_category = "chemistry"
        elif any(w in lower_cap for w in ["أحياء", "احياء", "bio", "biology"]):
            assigned_category = "biology"
        elif any(w in lower_cap for w in ["فيزياء", "فيزيا", "phys", "physics"]):
            assigned_category = "physics"
        else:
            assigned_category = "math" # افتراضي إن لم يجد كلمة مفتاحية واضحة

        material_files[assigned_category].append({
            "title": caption,
            "file_id": file_id
        })

        section_names = {
            "islamic": "التربية الإسلامية",
            "arabic": "اللغة العربية",
            "math": "الرياضيات",
            "english": "اللغة الإنجليزية",
            "chemistry": "الكيمياء",
            "biology": "الأحياء",
            "physics": "الفيزياء"
        }

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ تم سحب الملف بنجاح وإضافته إلى قسم ({section_names.get(assigned_category, assigned_category)}) في البوت الأساسي!"
        )

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.message.from_user.id

    # التحقق إذا كان المستخدم كتب رقماً للتحميل وكان داخل قسم معين
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
                await update.message.reply_text("❌ الرقم الذي أرسلته غير موجود في القائمة. تأكد من الرقم الصحيح.")
                return

    # إذا كان في قسم المساعد الذكي
    if user_current_section.get(user_id) == "ai_assistant":
        try:
            response = client.chat.completions.create(
                model="openai/gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "أنت مساعد أكاديمي ذكي لطلاب أكاديمية الفلاح دفعة 27."},
                    {"role": "user", "content": text}
                ]
            )
            ai_reply = response.choices[0].message.content
            await update.message.reply_text(ai_reply)
        except Exception as e:
            await update.message.reply_text("عذراً، حدث خطأ أثناء الاتصال بالمساعد الذكي. حاول مرة أخرى لاحقاً.")
        return

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
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    application.run_polling(close_loop=False)

if __name__ == '__main__':
    main()
