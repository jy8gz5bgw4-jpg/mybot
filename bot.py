import asyncio
import logging
import sqlite3
import random
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, 
CallbackQueryHandler, MessageHandler, filters, ContextTypes

import nest_asyncio
nest_asyncio.apply()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8760920369:AAHaP9fo3vpZ2Oo5ZchDRyIX97UC6HNbIrM"

def init_db():
    conn = sqlite3.connect("subscriptions.db")
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        channel_link TEXT,
        subscribed_count INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user INTEGER,
        to_user INTEGER,
        done INTEGER DEFAULT 0
    )""")
    conn.commit()
    conn.close()

init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📢 Telegram", 
callback_data="telegram")]]
    await update.message.reply_text(
        "Привет! Нажми 'Telegram' для участия.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "telegram":
        conn = sqlite3.connect("subscriptions.db")
        cur = conn.cursor()
        cur.execute("SELECT channel_link FROM users WHERE user_id = ?", 
(user_id,))
        row = cur.fetchone()

        if row and row[0]:
            cur.execute("SELECT user_id, channel_link FROM users WHERE 
channel_link IS NOT NULL AND user_id != ?", (user_id,))
            others = cur.fetchall()
            if others:
                cur.execute("SELECT to_user FROM actions WHERE from_user = 
? AND done = 1", (user_id,))
                done_list = [r[0] for r in cur.fetchall()]
                available = [o for o in others if o[0] not in done_list]
                if available:
                    target = random.choice(available)
                    await query.edit_message_text(
                        f"📌 Подпишись на этот 
канал:\n{target[1]}\n\nПосле подписки нажми 'Проверить'.",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("⏳ Проверить (20 сек)", 
callback_data=f"wait_{target[0]}")]
                        ])
                    )
                else:
                    await query.edit_message_text("Нет новых каналов. 
Попробуй позже.")
            else:
                await query.edit_message_text("Пока нет других каналов. 
Вставь свою ссылку.")
        else:
            await query.edit_message_text("Вставь ссылку на свой 
Telegram-канал (t.me/... или t.me/joinchat/...)")
            context.user_data["waiting_link"] = True
        conn.close()

async def handle_message(update: Update, context: 
ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if context.user_data.get("waiting_link"):
        conn = sqlite3.connect("subscriptions.db")
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO users (user_id, channel_link) 
VALUES (?, ?)", (user_id, text))
        conn.commit()
        conn.close()
        context.user_data["waiting_link"] = False
        await update.message.reply_text("Ссылка сохранена! Нажми /start и 
выбери Telegram.")

async def wait_and_confirm(update: Update, context: 
ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    target_id = int(query.data.split("_")[1])

    await query.edit_message_text("⏳ Жди 20 секунд... Подписка 
засчитывается автоматически.")
    await asyncio.sleep(20)

    conn = sqlite3.connect("subscriptions.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO actions (from_user, to_user, done) VALUES (?, 
?, 1)", (user_id, target_id))
    cur.execute("UPDATE users SET subscribed_count = subscribed_count + 1 
WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    await query.edit_message_text("✅ Подписка засчитана! Нажми /start, 
чтобы продолжить.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, 
handle_message))
    app.add_handler(CallbackQueryHandler(wait_and_confirm, 
pattern="wait_"))
    app.run_polling()

if __name__ == "__main__":
    main()
