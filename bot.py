import os
import logging
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

# إعدادات السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# جلب توكن تيليجرام من متغيرات البيئة في Render
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# مفتاح الذكاء الاصطناعي
OPENAI_API_KEY = "49e5a536511d1949725661ddcba811ff00aef292257942bd4701b3161e16cb7c"

# تهيئة عميل الذكاء الاصطناعي
client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"أهلاً بك يا {user_name} في بوت أكاديمية الفلاح (Seniors 27)! 🎓\n"
        "أنا جاهز لمساعدتك في استرجاع الملفات الدراسية والإجابة على أسئلتك الأكاديمية طوال الـ 24 ساعة."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("جاري معالجة طلبك أكاديمياً...")

def main():
    if not TELEGRAM_TOKEN:
        print("خطأ: لم يتم العثور على TELEGRAM_TOKEN في متغيرات البيئة!")
        return

    # بناء التطبيق
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("تم بدء تشغيل البوت بنجاح ويقوم بالاستماع الآن...")
    
    # التشغيل اليدوي لحلقة الأحداث لتجنب مشاكل Thread
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    application.run_polling()

if __name__ == '__main__':
    main()
