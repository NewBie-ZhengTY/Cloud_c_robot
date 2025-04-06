import os
import redis
import openai
import logging
from telegram import Update
from openai import OpenAI
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# 加载环境变量
load_dotenv()

# OpenAI 配置（兼容 API2D）
openai.api_key = os.getenv("OPENAI_API_KEY")
openai.api_base = "https://api.api2d.net/v1"  # 这是重点

# 配置 Redis
r = redis.from_url(os.getenv("REDIS_URL"))

# 设置最大聊天历史长度（防止过长的对话历史）
MAX_HISTORY_LEN = 2000  # 字符数限制


# 处理消息的函数
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_input = update.message.text

    # 从 Redis 获取用户聊天历史
    chat_history = r.get(user_id)
    if chat_history:
        chat_history = chat_history.decode() + f"\nUser: {user_input}"
    else:
        chat_history = f"User: {user_input}"

    # 如果历史太长，截断
    if len(chat_history) > MAX_HISTORY_LEN:
        chat_history = chat_history[-MAX_HISTORY_LEN:]

    # 新的接口
    response = openai.completions.create(
        model="gpt-3.5-turbo",  # 付费模型
        messages=[
            {"role": "system", "content": "你是一个友好的聊天机器人"},
            {"role": "user", "content": chat_history}
        ]
    )

    reply = response['choices'][0]['message']['content']

    # 更新 Redis 中的聊天历史（保留历史）
    chat_history += f"\nBot: {reply}"
    r.set(user_id, chat_history, ex=3600)  # 设置“记忆”保存时长：1小时

    await update.message.reply_text(reply)


# 启动命令处理
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("你好，我是 ChatGPT Telegram 机器人。请发送消息给我！")


# 主函数
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 配置 Telegram bot
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    # 注册命令和消息处理器
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    # 启动 bot 进行消息轮询
    app.run_polling()