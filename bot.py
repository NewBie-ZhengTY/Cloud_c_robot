import os
import redis
import logging
from telegram import Update
from dotenv import load_dotenv
from openai import OpenAI
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# 加载环境变量
load_dotenv()

# OpenAI 配置（兼容 API2D）
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.api2d.net/v1"
)

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
        chat_history = chat_history.decode()
    else:
        chat_history = ""

    # 构建 messages 格式（GPT 聊天格式）
    messages = []

    # 解析历史记录为 Chat messages
    for line in chat_history.strip().split("\n"):
        if line.startswith("User:"):
            messages.append({"role": "user", "content": line[5:].strip()})
        elif line.startswith("Bot:"):
            messages.append({"role": "assistant", "content": line[4:].strip()})

    # 加入当前用户输入
    messages.append({"role": "user", "content": user_input})

    # 新接口调用 ChatCompletion
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=100
    )

    reply = response.choices[0].message.content.strip()

    # 更新 Redis 聊天历史
    new_history = chat_history + f"\nUser: {user_input}\nBot: {reply}"
    if len(new_history) > MAX_HISTORY_LEN:
        new_history = new_history[-MAX_HISTORY_LEN:]
    r.set(user_id, new_history, ex=3600)

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