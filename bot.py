import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# إعداد السجلات
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# بيانات المشرفين وكلمة السر السرية
ADMIN_PASSWORD = "mpol90mpol90@M7"
OWNER_ID = 1329113404
ADMIN_ID = 1110343074

# تخزين مؤقت لجلسات المشرفين المعتمدين
admin_sessions = set()

# (ملاحظة: حافظ على دالتك الأصلية لجلب الملفات وعرضها للطلاب عبر /start كما كانت تماماً)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ضع هنا كود /start الأصلي الخاص بك الذي يجلب الملفات من قاعدة البيانات
    # مثال توضيحي:
    user_name = update.effective_user.first_name
    await update.message.reply_text(f"أهلاً بك يا {user_name} في بوت Al Falah Academy - Senior 27. البوت يعمل بكامل ملفاته الدراسية!")

# أمر الإدارة المحمي بكلمة السر
async def admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # التحقق من إدخال كلمة السر الصحيحة
    if not context.args or context.args[0] != ADMIN_PASSWORD:
        return  # تجاهل صامت إذا كانت كلمة السر خاطئة لكي لا ينتبه الطلاب
        
    if user_id in [OWNER_ID, ADMIN_ID]:
        admin_sessions.add(user_id)
        panel_text = (
            "📊 لوحة تحكم وإحصائيات البوت السحابية (الإدارة):\n\n"
            "للحذف السريع لأي ملف، أرسل أولاً:\n"
            "`/files` لعرض قائمة الملفات وأرقامها، ثم أرسل:\n"
            "`/delete [رقم_الملف]`"
        )
        await update.message.reply_text(panel_text, parse_mode="Markdown")
    else:
        await update.message.reply_text("عذراً، ليس لديك صلاحية.")

# أمر عرض الملفات للمشرفين لمعرفة أرقامها للحذف
async def list_files_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admin_sessions and user_id not in [OWNER_ID, ADMIN_ID]:
        return
        
    # (هنا يتم جلب الملفات من قاعدة البيانات الخاصة بك وعرضها مع أرقامها ID)
    await update.message.reply_text("📋 (قائمة الملفات الحقيقية من قاعدة بياناتك تظهر هنا مع أرقامها لتسهيل الحذف لصديقك)")

# أمر الحذف
async def delete_file_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admin_sessions and user_id not in [OWNER_ID, ADMIN_ID]:
        return
        
    if not context.args:
        await update.message.reply_text("⚠️ يرجى كتابة رقم الملف بعد الأمر. مثال: `/delete 5`", parse_mode="Markdown")
        return
        
    file_id = context.args[0]
    # (هنا يوضع كود الحذف الأصلي من قاعدة البيانات الخاصة بك باستخدام الـ file_id)
    await update.message.reply_text(f"✅ تم حذف الملف برقم {file_id} بنجاح.")

def main():
    TOKEN = os.getenv("TELEGRAM_TOKEN", "8469933821:AAFStidpfrR9zq18pn1m8jFEYzRqmusz3z8")
    application = Application.builder().token(TOKEN).build()
    
    # تسجيل الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_login))
    application.add_handler(CommandHandler("files", list_files_admin))
    application.add_handler(CommandHandler("delete", delete_file_admin))
    
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
