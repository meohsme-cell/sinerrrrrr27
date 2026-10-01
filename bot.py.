import logging
import asyncio
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from openai import OpenAI

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = "8469933821:AAFStidpfrR9zq18pn1m8jFEYzRqmusz3z8"
OPENROUTER_API_KEY = "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"

# قاعدة بيانات متطورة لتخزين الملفات بالرقم والـ file_id الحقيقي لإرساله لاحقاً
# كل مادة ستكون عبارة عن قاموس أو قائمة تحتوي على: {"id": "1", "title": "...", "file_id": "...", "url": "..."}
DATABASE_FILES = {
    "math": [],
    "arabic": [],
    "chemistry": [],
    "biology": [],
    "islamic": [],
    "english": []
}

USER_CHAT_HISTORY = {}

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("📐 الرياضيات", callback_data="math"),
            InlineKeyboardButton("📖 اللغة العربية", callback_data="arabic"),
        ],
        [
            InlineKeyboardButton("🧪 الكيمياء", callback_data="chemistry"),
            InlineKeyboardButton("🧬 الأحياء", callback_data="biology"),
        ],
        [
            InlineKeyboardButton("☪️ التربية الإسلامية", callback_data="islamic"),
            InlineKeyboardButton("🔤 اللغة الإنجليزية", callback_data="english"),
        ],
        [
            InlineKeyboardButton("📁 بنك الملفات والبحث بالرقم", callback_data="files_bank"),
        ],
        [
            InlineKeyboardButton("⏰ العد التنازلي للامتحانات", callback_data="countdown"),
            InlineKeyboardButton("🎯 تدريب واختبار سريع", callback_data="quiz_start"),
        ],
        [
            InlineKeyboardButton("🔍 المتحدث الذكي", callback_data="general_search"),
        ],
        [
            InlineKeyboardButton("💪 من أقوى دفعة 27؟", callback_data="strongest_batch"),
        ],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_text = "Seniors 27 🔥\nأهلاً بك يا بطل. اختر القسم المناسب أو أرسل رقم الملف المطلوب للحصول عليه فوراً:"

    try:
        if update.message:
            await update.message.reply_text(welcome_text, reply_markup=reply_markup)
        elif update.callback_query:
            query = update.callback_query
            await query.answer()
            await query.edit_message_text(text=welcome_text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in start: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    back_keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_home")]]
    reply_markup = InlineKeyboardMarkup(back_keyboard)

    if data in ["math", "arabic", "chemistry", "biology", "islamic", "english"]:
        subject_names = {
            "math": "الرياضيات 📐",
            "arabic": "اللغة العربية 📖",
            "chemistry": "الكيمياء 🧪",
            "biology": "الأحياء 🧬",
            "islamic": "التربية الإسلامية ☪️",
            "english": "اللغة الإنجليزية 🔤"
        }
        
        files_list = DATABASE_FILES.get(data, [])
        
        if not files_list:
            text = f"📁 قسم {subject_names[data]}:\n\nعذراً، لم يتم رفع أي ملفات لهذه المادة حتى الآن.\n(قم برفع ملف في القناة المخصصة مع كتابة رقمه واسمه ليظهر هنا تلقائياً)."
        else:
            text = f"📁 ملفات ومراجعات قسم {subject_names[data]}:\n\n"
            for item in files_list:
                text += f"🔹 رقم الملف: ({item['id']})\n📌 الوصف: {item['title']}\n🔗 رابط المعاينة: {item['url']}\n-------------------\n"
            text += "\n💡 للحصول على الملف مباشرة، أرسل رقمه هنا في المحادثة!"
                
        await query.edit_message_text(text=text, reply_markup=reply_markup, disable_web_page_preview=True)

    elif data == "files_bank":
        bank_keyboard = [
            [InlineKeyboardButton("📐 الرياضيات", callback_data="math"), InlineKeyboardButton("📖 اللغة العربية", callback_data="arabic")],
            [InlineKeyboardButton("🧪 الكيمياء", callback_data="chemistry"), InlineKeyboardButton("🧬 الأحياء", callback_data="biology")],
            [InlineKeyboardButton("☪️ الإسلامية", callback_data="islamic"), InlineKeyboardButton("🔤 الإنجليزية", callback_data="english")],
            [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_home")]
        ]
        await query.edit_message_text(
            text="📁 بنك الملفات:\n\nاختر المادة لعرض الملفات وأرقامها:",
            reply_markup=InlineKeyboardMarkup(bank_keyboard)
        )

    elif data == "countdown":
        target_date = datetime(2026, 6, 15)
        today = datetime.now()
        remaining_days = (target_date - today).days
        if remaining_days < 0:
            remaining_days = 0
        await query.edit_message_text(text=f"⏰ متبقي {remaining_days} يوماً على الامتحانات!", reply_markup=reply_markup)

    elif data == "quiz_start":
        await query.edit_message_text(text="🎯 أرسل سؤالاً أو طلباً لاختبارك وسأقوم بتقييمك فوراً.", reply_markup=reply_markup)

    elif data == "general_search":
        await query.edit_message_text(text="🔍 المتحدث الذكي جاهز. اكتب سؤالك الآن في المحادثة وسأجيبك فوراً وبدون تأخير!", reply_markup=reply_markup)

    elif data == "strongest_batch":
        await query.edit_message_text(text="🔥 Seniors 27, Al Falah Academy, MBZ 🇦🇪", reply_markup=reply_markup)

async def back_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

# دالة سحب الملفات وتصنيفها تلقائياً من القناة الثانية أو القروب بناءً على الكلام ورقم الملف
async def handle_group_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    # التأكد من أن الرسالة من قناة أو قروب
    if message.chat.type not in ["channel", "group", "supergroup"]:
        return

    # جلب رابط المنشور إذا توفر
    if message.chat.username:
        post_url = f"https://t.me/{message.chat.username}/{message.message_id}"
    else:
        post_url = f"https://t.me/c/{str(message.chat.id).replace('-100', '')}/{message.message_id}"

    caption = message.caption or message.text or ""
    full_text = caption.lower()

    # تحديد المادة المطلوبة بناءً على الكلمات المفتاحية في الوصف
    detected_subject = None
    subject_name_ar = ""

    if "رياضيات" in full_text or "math" in full_text:
        detected_subject = "math"
        subject_name_ar = "الرياضيات 📐"
    elif "أحياء" in full_text or "biology" in full_text or "حياء" in full_text:
        detected_subject = "biology"
        subject_name_ar = "الأحياء 🧬"
    elif "عربي" in full_text or "لغة عربية" in full_text or "عربى" in full_text:
        detected_subject = "arabic"
        subject_name_ar = "اللغة العربية 📖"
    elif "كيمياء" in full_text or "chemistry" in full_text:
        detected_subject = "chemistry"
        subject_name_ar = "الكيمياء 🧪"
    elif "إسلامية" in full_text or "تربية إسلامية" in full_text or "دين" in full_text:
        detected_subject = "islamic"
        subject_name_ar = "التربية الإسلامية ☪️"
    elif "إنجليزية" in full_text or "english" in full_text or "انجليزي" in full_text:
        detected_subject = "english"
        subject_name_ar = "اللغة الإنجليزية 🔤"

    # استخراج رقم الملف من النص (البحث عن أي رقم موجود في الرسالة مثل 1 أو 2)
    import re
    numbers_found = re.findall(r'\d+', full_text)
    file_number = numbers_found[0] if numbers_found else "1" # افتراضي 1 إذا لم يكتب رقم

    if detected_subject and message.document:
        file_id = message.document.file_id
        file_info = {
            "id": file_number,
            "title": caption if caption else "ملف تعليمي",
            "file_id": file_id,
            "url": post_url
        }
        
        # التأكد من عدم تكرار نفس الرقم أو تحديثه
        DATABASE_FILES[detected_subject] = [f for f in DATABASE_FILES[detected_subject] if f["id"] != file_number]
        DATABASE_FILES[detected_subject].append(file_info)
        
        # الرد داخل القناة لتأكيد الحفظ
        try:
            await message.reply_text(
                f"✅ تم تخزين الملف بنجاح!\n📌 القسم: {subject_name_ar}\n🔢 رقم الملف: {file_number}"
            )
        except Exception:
            pass

# معالج رسائل الخاص (للذكاء الاصطناعي أو إرسال الملفات بالرقم)
async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private":
        return
    
    user_text = update.message.text
    if not user_text:
        return
    
    clean_text = user_text.strip().lower()
    
    # 1. فحص إذا كان الطالب أرسل رقماً للبحث عن ملف وإرساله فوراً
    if clean_text.isdigit():
        target_id = clean_text
        found_file = None
        for subj, files in DATABASE_FILES.items():
            for f in files:
                if f["id"] == target_id:
                    found_file = f
                    break
            if found_file:
                break
        
        if found_file:
            await update.message.reply_document(
                document=found_file["file_id"],
                caption=f"📁 الملف المطلوب (رقم {target_id}):\n{found_file['title']}"
            )
            return
        else:
            await update.message.reply_text(f"❌ عذراً، لا يوجد ملف مسجل بهذا الرقم ({target_id}). تأكد من الرقم من قائمة المواد.")
            return

    # الأوامر السريعة الأخرى
    if "من اقوى دفعه 27" in clean_text or "من أقوى دفعة 27" in clean_text or "أقوى دفعة 27" in clean_text:
        await update.message.reply_text("🔥 Seniors 27, Al Falah Academy, MBZ 🇦🇪")
        return

    user_id = update.message.from_user.id
    if user_id not in USER_CHAT_HISTORY:
        USER_CHAT_HISTORY[user_id] = []

    USER_CHAT_HISTORY[user_id].append({"role": "user", "content": user_text})
    if len(USER_CHAT_HISTORY[user_id]) > 6:
        USER_CHAT_HISTORY[user_id].pop(0)

    await update.message.chat.send_action(action="typing")

    system_prompt = {
        "role": "system", 
        "content": (
            "أنت مساعد أكاديمي خبير ومحترف لطلاب الثانوية العامة في دولة الإمارات. "
            "أجب بدقة متناهية، وبسرعة ووضوح تام، وبدون أي مقدمات طويلة أو هاشتاقات أو رموز معقدة."
        )
    }

    messages_payload = [system_prompt] + USER_CHAT_HISTORY[user_id]

    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="google/gemini-2.0-flash-001",
                messages=messages_payload,
                temperature=0.4,
                max_tokens=1200,
                timeout=20
            )
            ai_reply = response.choices[0].message.content
            USER_CHAT_HISTORY[user_id].append({"role": "assistant", "content": ai_reply})
            await update.message.reply_text(ai_reply)
            return
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                await update.message.reply_text("عذراً، حدث ضغط مفاجئ، أعد إرسال سؤالك وسأجيبك فوراً.")
            else:
                await asyncio.sleep(1)

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).concurrent_updates(True).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(back_home, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(math|arabic|chemistry|biology|islamic|english|files_bank|countdown|quiz_start|general_search|strongest_batch)$"))
    
    # معالجة الملفات الواردة من القنوات والقروبات المربوطة
    app.add_handler(MessageHandler(filters.Document.ALL & (~filters.ChatType.PRIVATE), handle_group_files))
    # معالجة رسائل الخاص (للبحث بالأرقام أو المحادثة الذكية)
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND) & filters.ChatType.PRIVATE, handle_ai_chat))

    print("البوت يعمل الآن مع نظام ربط القنوات وإرسال الملفات بالأرقام بنجاح! 🚀")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
