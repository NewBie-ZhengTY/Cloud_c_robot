import os
import openai
import logging
from telegram import Update
from openai import OpenAI
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
print("OpenAI Key:", os.getenv("OPENAI_API_KEY"))
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    # response = client.chat.completions.create(...)  # 先注释掉
    reply = f"你说的是：{user_input}\n（ChatGPT暂时不可用）"
    await update.message.reply_text(reply)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("你好，我是 ChatGPT Telegram 机器人。请发送消息给我！")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
