import os
import logging
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# إعداد التسجيل (Logging) لمتابعة الأخطاء
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# خادم وهمي لإبقاء الاستضافة نشطة ودعم طلبات UptimeRobot (GET & HEAD)
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

# تشغيل الخادم الوهمي في خلفية الكود
Thread(target=run_server, daemon=True).start()

# دالة الأمر /start
async def start(update, context):
    await update.message.reply_text("أهلاً بك! البوت يعمل الآن بشكل دائم 24/7 🚀")

# دالة الرد على الرسائل العادية
async def handle_message(update, context):
    text = update.message.text
    await update.message.reply_text(f"أرسلت لي: {text}")

def main():
    # استدعاء التوكن من متغيرات البيئة في الاستضافة
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    
    if not TOKEN:
        logger.error("لم يتم العثور على التوكن! تأكد من إضافته في متغيرات البيئة.")
        return

    # بناء تطبيق البوت
    application = Application.builder().token(TOKEN).build()

    # إضافة الأوامر والمعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # بدء تشغيل البوت بطريقة الـ Polling
    logger.info("Starting bot polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
