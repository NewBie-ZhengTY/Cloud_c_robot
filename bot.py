import os
import redis
import logging
import random
from telegram import Update
from telegram.ext import CommandHandler# 加入兴趣匹配
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes,MessageHandler, filters



# 加载环境变量
load_dotenv()

# 配置日志记录
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MENU = {
    "快餐": ["汉堡", "炸鸡", "薯条"],
    "饮料": ["可乐", "奶茶", "果汁"]
}

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

# 设置用户兴趣
async def set_interest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("请提供你的兴趣，例如：/set_interest 足球")
        return
    interest = context.args[0]
    r.set(f"interest:{user_id}", interest)
    await update.message.reply_text(f"你的兴趣已设置为：{interest}")

# 查找兴趣匹配用户
async def find_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    my_interest = r.get(f"interest:{user_id}")
    if not my_interest:
        await update.message.reply_text("你还没有设置兴趣，请使用 /set_interest 进行设置。")
        return
    my_interest = my_interest.decode()

    matched_users = []
    for key in r.scan_iter("interest:*"):
        other_id = key.decode().split(":")[1]
        if other_id == user_id:
            continue
        if r.get(key).decode() == my_interest:
            matched_users.append(other_id)

    if matched_users:
        reply = f"和你一样喜欢【{my_interest}】的用户有：\n" + "\n".join(matched_users)
    else:
        reply = f"暂时没有和你一样喜欢【{my_interest}】的用户。"

    await update.message.reply_text(reply)

# 开始游戏
async def start_guess_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    target = random.randint(1, 100)
    r.set(f"guessing:{user_id}", target, ex=600)  # 10分钟有效
    await update.message.reply_text("我已经想好了一个 1 到 100 的数字，你来猜吧！")

# 处理猜测
async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    guess = update.message.text.strip()

    if not guess.isdigit():
        return  # 忽略非数字输入

    if not r.exists(f"guessing:{user_id}"):
        return  # 没有在玩游戏

    target = int(r.get(f"guessing:{user_id}"))
    guess = int(guess)

    if guess < target:
        await update.message.reply_text("太小了，再试一次！")
    elif guess > target:
        await update.message.reply_text("太大了，再试一次！")
    else:
        await update.message.reply_text("恭喜你猜对了！")
        r.delete(f"guessing:{user_id}")

# /start 命令处理器
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(text=category, callback_data=f"menu|{category}")]
                for category in MENU]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("欢迎点餐，请选择一个分类：", reply_markup=reply_markup)

# 回调按钮处理器
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("menu|"):
        category = data.split("|")[1]
        items = MENU.get(category, [])
        keyboard = [[InlineKeyboardButton(text=item, callback_data=f"order|{item}")]
                    for item in items]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"您选择的是「{category}」，请选择商品：", reply_markup=reply_markup)

    elif data.startswith("order|"):
        item = data.split("|")[1]
        await query.edit_message_text(f"您的订单是：{item}（模拟下单成功）")

# 主函数
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 配置 Telegram bot
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    # 注册命令和消息处理器
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set_interest", set_interest))  # 新增
    app.add_handler(CommandHandler("find_match", find_match))  # 新增
    app.add_handler(CommandHandler("guess_number", start_guess_game))#猜数游戏
    app.add_handler(CallbackQueryHandler(button_handler))#点外卖操作
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    # 启动 bot 进行消息轮询
    app.run_polling()

