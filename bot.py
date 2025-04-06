import os
import redis
import logging
from telegram import Update
from dotenv import load_dotenv
from openai import OpenAI
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# 加载环境变量
load_dotenv()

# 配置日志记录
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenAI 配置（兼容 API2D）
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://oa.api2d.net"
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
    try:
        chat_history = r.get(user_id)
        if chat_history:
            chat_history = chat_history.decode()
        else:
            chat_history = ""  # 如果没有历史记录，初始化为空字符串
    except Exception as e:
        logger.error(f"Redis 获取历史记录失败: {e}")
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
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=100
        )
        # 输出 API 响应日志
        logger.info(f"OpenAI Response: {response}")
        reply = response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"OpenAI 请求失败: {e}")
        reply = "发生了错误，请稍后再试。"

    # 更新 Redis 聊天历史
    try:
        new_history = chat_history + f"\nUser: {user_input}\nBot: {reply}"
        # 截断历史，确保最大长度不超过设置值
        if len(new_history) > MAX_HISTORY_LEN:
            new_history = new_history[-MAX_HISTORY_LEN:]
        r.set(user_id, new_history, ex=3600)  # 设置缓存过期时间为1小时
    except Exception as e:
        logger.error(f"Redis 更新历史失败: {e}")

    # 发送回复
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