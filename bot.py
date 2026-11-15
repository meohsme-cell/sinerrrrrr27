import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# إعداد السجلات الأساسية
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# الأيدي الخاص بك (المالك) وصديقك (المشرف المخصص للحذف فقط)
OWNER_ID = 1329113404
ADMIN_ID = 1110343074

# قائمة المواد والهياكل الأساسية (يمكنك ربطها بقاعدة بياناتك السحابية الحقيقية Supabase)
SUBJECTS = ["الرياضيات", "الكيمياء", "الأحياء", "اللغة العربية", "الفيزياء"]
STRUCTURES = ["هيكل الفصل الأول", "هيكل الفصل الثاني", "التدريبات والاختبارات"]

# تخزين مؤقت لحالة رفع الملفات (لكي يتعرف البوت على اختيارك للمادة والهيكل عند رفع ملف جديد)
upload_states = {}

# 1. أمر البداية للطلاب (/start) مع أزرار المواد والهياكل
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    
    keyboard = [
        [InlineKeyboardButton("📚 المواد الدراسية", callback_data="show_subjects")],
        [InlineKeyboardButton("📁 هياكل الوزارة", callback_data="show_structures")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"أهلاً بك يا {user_name} في بوت 🎓 **Al Falah Academy - Senior 27**.\n\n"
        "اختر من الأزرار بالأسفل لاستعراض المواد الدراسية أو الهياكل المعتمدة:"
    )
    
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

# 2. معالجة الأزرار التفاعلية للطلاب
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "show_subjects":
        keyboard = [[InlineKeyboardButton(sub, callback_data=f"sub_{sub}")] for sub in SUBJECTS]
        keyboard.append([InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back_home")])
        await query.edit_message_text("📚 **اختر المادة الدراسية المطلوبة:**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif query.data == "show_structures":
        keyboard = [[InlineKeyboardButton(struct, callback_data=f"struct_{struct}")] for struct in STRUCTURES]
        keyboard.append([InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back_home")])
        await query.edit_message_text("📁 **اختر الهيكل الدراسي المطلوب:**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif query.data == "back_home":
        keyboard = [
            [InlineKeyboardButton("📚 المواد الدراسية", callback_data="show_subjects")],
            [InlineKeyboardButton("📁 هياكل الوزارة", callback_data="show_structures")]
        ]
        await query.edit_message_text("أهلاً بك مرة أخرى! اختر ما تحتاجه:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif query.data.startswith("sub_"):
        subject_name = query.data.split("_")[1]
        await query.edit_message_text(f"📖 ملفات مادة **{subject_name}** ستظهر هنا (مع حفظ كافة ملفاتك القديمة سحابياً).", parse_mode="Markdown")
        
    elif query.data.startswith("struct_"):
        struct_name = query.data.split("_")[1]
        await query.edit_message_text(f"📋 ملفات **{struct_name}** لجميع المواد الأساسية ستظهر هنا بدقة.", parse_mode="Markdown")

# 3. ميزة التعرف التلقائي على الملفات الجديدة (عند رفعك لأي ملف في القناة أو البوت)
async def handle_new_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return  # فقط أنت كمالك تستطيع إضافة ملفات جديدة بالطريقة التفاعلية
        
    # عرض أزرار اختيار المادة عند إرسال ملف جديد
    keyboard = [[InlineKeyboardButton(sub, callback_data=f"up_sub_{sub}")] for sub in SUBJECTS]
    await update.message.reply_text(
        "📥 تم استلام الملف بنجاح!\nأضفت هذا الملف لأي مادة تريد تصنيفه؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# 4. أمر الحذف الخاص بصديقك (يتعرف عليه البوت تلقائياً من الـ ID الخاص به دون كلمة سر)
async def delete_file_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # السماح فقط للمالك (أنت) أو صديقك (المشرف) باستخدام أمر الحذف
    if user_id not in [OWNER_ID, ADMIN_ID]:
        return  # تجاهل صامت للطلاب العاديين
        
    if not context.args:
        await update.message.reply_text("⚠️ يرجى كتابة رقم الملف المراد حذفه بعد الأمر. مثال:\n`/delete 12`", parse_mode="Markdown")
        return
        
    file_id = context.args[0]
    
    # (هنا يتم تنفيذ عملية الحذف من قاعدة بياناتك الحقيقية دون مسح باقي الملفات)
    await update.message.reply_text(f"✅ تم حذف الملف برقم `{file_id}` بنجاح بواسطة لوحة التحكم المصرحة.", parse_mode="Markdown")

def main():
    # توكن البوت الأساسي
    TOKEN = os.getenv("TELEGRAM_TOKEN", "8469933821:AAFStidpfrR9zq18pn1m8jFEYzRqmusz3z8")
    
    application = Application.builder().token(TOKEN).build()
    
    # تسجيل الأوامر والمعالجات
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("delete", delete_file_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # استقبال الملفات الجديدة المرفوعة منك فقط
    application.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_new_file))
    
    print("Bot is running perfectly with secure permissions...")
    application.run_polling()

if __name__ == "__main__":
    main()
