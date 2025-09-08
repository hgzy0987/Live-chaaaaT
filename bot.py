import os
import logging
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, db

# ---------------- Load Environment -----------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL")

# ---------------- Logging -----------------
logging.basicConfig(level=logging.INFO)

# ---------------- Firebase Init -----------------
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})

# ---------------- Active Admin Reply Targets -----------------
admin_reply_targets = {}  # admin_id: user_id

# ---------------- Firebase Functions -----------------
def save_user_message(user_id, username, text):
    ref = db.reference(f'chats/{user_id}')
    if not ref.get():
        ref.set({"username": username, "messages": []})
    ref.child("messages").push({"from": "user", "text": text})

def save_admin_message(user_id, text):
    ref = db.reference(f'chats/{user_id}/messages')
    ref.push({"from": "admin", "text": text})

# ---------------- Telegram Bot Handlers -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = user.first_name
    keyboard = [[InlineKeyboardButton("YES", callback_data="yes"),
                 InlineKeyboardButton("NO", callback_data="no")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"প্রিয় গ্রাহক {username} ..!\n"
        "স্বাগতম TRUST BD SUPPORT SERVER 1 BOT এ।\n"
        "আমাদের একজন প্রতিনিধির সাথে যোগাযোগ করতে YES এ ক্লিক করুন অন্যথায় NO এ ক্লিক করুন",
        reply_markup=reply_markup
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()
    username = user.first_name

    if query.data == "no":
        await query.edit_message_text(f"ধন্যবাদ {username}, আমাদের সাথে থাকার জন্য।")
    elif query.data == "yes":
        await query.edit_message_text(f"প্রিয় গ্রাহক {username}, আমাদের সকল প্রতিনিধি এই মূহুর্তে ব্যস্ত রয়েছেন, দয়া করে অপেক্ষা করুন।")
        # Notify admin
        keyboard = [[InlineKeyboardButton("Reply", callback_data=f"reply_{user.id}")]]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"নতুন চ্যাট অনুরোধ: {username}\nUser ID: {user.id}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        save_user_message(user.id, username, "চ্যাট শুরু হয়েছে (YES ক্লিক)")

# ---------------- Admin Reply Button -----------------
async def admin_reply_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin_id = query.from_user.id
    await query.answer()
    if query.data.startswith("reply_"):
        user_id = int(query.data.split("_")[1])
        admin_reply_targets[admin_id] = user_id
        await context.bot.send_message(chat_id=admin_id, text="আপনি এখন মেসেজ লিখুন যা ইউজারকে পাঠাতে চান:")

# ---------------- Admin Typing Handler -----------------
async def admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.effective_user.id
    if admin_id in admin_reply_targets:
        user_id = admin_reply_targets[admin_id]
        await context.bot.send_message(chat_id=user_id, text=f"Admin: {update.message.text}")
        save_admin_message(user_id, update.message.text)
        await update.message.reply_text("মেসেজ ইউজারকে পাঠানো হয়েছে।")
        del admin_reply_targets[admin_id]

# ---------------- Keep Alive Flask -----------------
flask_app = Flask("")

@flask_app.route("/")
def home():
    return "Bot is running!"

def run():
    flask_app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ---------------- Main -----------------
keep_alive()

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button, pattern="^(yes|no)$"))
app.add_handler(CallbackQueryHandler(admin_reply_button, pattern="^reply_"))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), admin_message))

print("Bot is running...")
app.run_polling()
