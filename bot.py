import os
import redis
import logging
import random
from telegram import Update
from telegram.ext import CommandHandler# Add Interest Matching
import os
import logging
import random
import redis
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MENU = {
    "Fast Food": ["Burger", "Fried Chicken", "Fries"],
    "Drinks": ["Coke", "Milk Tea", "Juice"]
}

# OpenAI (API2D compatible)
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://oa.api2d.net"
)

# Configure Redis
r = redis.from_url(os.getenv("REDIS_URL"))

# Set max history length
MAX_HISTORY_LEN = 2000  # character limit

# Handle chat messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_input = update.message.text

    try:
        chat_history = r.get(user_id)
        if chat_history:
            chat_history = chat_history.decode()
        else:
            chat_history = ""
    except Exception as e:
        logger.error(f"Failed to retrieve chat history from Redis: {e}")
        chat_history = ""

    messages = []

    for line in chat_history.strip().split("\n"):
        if line.startswith("User:"):
            messages.append({"role": "user", "content": line[5:].strip()})
        elif line.startswith("Bot:"):
            messages.append({"role": "assistant", "content": line[4:].strip()})

    messages.append({"role": "user", "content": user_input})

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=100
        )
        logger.info(f"OpenAI Response: {response}")
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        reply = "An error occurred. Please try again later."

    try:
        new_history = chat_history + f"\nUser: {user_input}\nBot: {reply}"
        if len(new_history) > MAX_HISTORY_LEN:
            new_history = new_history[-MAX_HISTORY_LEN:]
        r.set(user_id, new_history, ex=3600)  # 1-hour expiration
    except Exception as e:
        logger.error(f"Failed to update Redis chat history: {e}")

    await update.message.reply_text(reply)

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(text=category, callback_data=f"menu|{category}")]
                for category in MENU]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome to the ordering system. Please choose a category:", reply_markup=reply_markup)

# Set user interest
async def set_interest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("Please provide your interest, e.g. /set_interest football")
        return
    interest = context.args[0]
    r.set(f"interest:{user_id}", interest)
    await update.message.reply_text(f"Your interest has been set to: {interest}")

# Find matching users
async def find_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    my_interest = r.get(f"interest:{user_id}")
    if not my_interest:
        await update.message.reply_text("You haven't set your interest yet. Please use /set_interest.")
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
        reply = f"Users who also like 【{my_interest}】:\n" + "\n".join(matched_users)
    else:
        reply = f"No other users share your interest in 【{my_interest}】 yet."

    await update.message.reply_text(reply)

# Start number guessing game
async def start_guess_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    target = random.randint(1, 100)
    r.set(f"guessing:{user_id}", target, ex=600)  # valid for 10 minutes
    await update.message.reply_text("I'm thinking of a number between 1 and 100. Try to guess it!")

# Handle guessing input
async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    guess = update.message.text.strip()

    if not guess.isdigit():
        return

    if not r.exists(f"guessing:{user_id}"):
        return

    target = int(r.get(f"guessing:{user_id}"))
    guess = int(guess)

    if guess < target:
        await update.message.reply_text("Too low! Try again.")
    elif guess > target:
        await update.message.reply_text("Too high! Try again.")
    else:
        await update.message.reply_text("Congratulations! You guessed it!")
        r.delete(f"guessing:{user_id}")

# Handle menu and ordering buttons
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
        await query.edit_message_text(f"You selected category: {category}. Please choose an item:", reply_markup=reply_markup)

    elif data.startswith("order|"):
        item = data.split("|")[1]
        await query.edit_message_text(f"Your order: {item} (Order placed successfully - simulated)")

# Main function
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set_interest", set_interest))
    app.add_handler(CommandHandler("find_match", find_match))
    app.add_handler(CommandHandler("guess_number", start_guess_game))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    app.run_polling()


