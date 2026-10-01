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

    if user_current_section.get(user_id) == "ai_assistant":
        try:
            # Show "typing..." to the user for better UX
            await context.bot.send_chat_action(chat_id=user_id, action="typing")
            
            # Run OpenAI call in a separate thread to prevent blocking the whole bot
            def get_ai_response():
                response = client.chat.completions.create(
                    model="openai/gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a highly intelligent academic assistant for Al Falah Academy Senior 27 students. Be concise and helpful."},
                        {"role": "user", "content": text}
                    ],
                    timeout=25
                )
                return response.choices[0].message.content

            ai_reply = await asyncio.to_thread(get_ai_response)
            await update.message.reply_text(ai_reply)
        except Exception as e:
            logging.error(f"AI Error: {e}")
            await update.message.reply_text("⚠️ System busy. Please try again in a few seconds!")
        return

    await update.message.reply_text("Please use /start to access the main menu.")

def main():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN not found!")
        return

    # High-performance settings
    application = (
        ApplicationBuilder()
        .token(8469933821:AAFStidpfrR9zq18pn1m8jFEYzRqmusz3z8)
        .concurrent_updates(True) # Crucial for handling thousands of users
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.AUDIO, handle_incoming_files))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_messages))

    print("🚀 Bot started with High-Efficiency Mode...")
    application.run_polling(drop_pending_updates=True)

if name == 'main':
    main()
