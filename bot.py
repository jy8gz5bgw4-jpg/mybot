import asyncio
import logging
import sqlite3
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, 
CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8760920369:AAHaP9fo3vpZ2Oo5ZchDRyIX97UC6HNbIrM"
MAIN_CHANNEL = "@ELVINPODPISKA"

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect("subscriptions.db")
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        channel_link TEXT,
        tokens INTEGER DEFAULT 0,
        subscribers_needed INTEGER DEFAULT 0,
        subscribers_received INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user INTEGER,
        to_user INTEGER,
        done INTEGER DEFAULT 0
    )""")
    conn.commit()
    conn.close()

init_db()

# ========== ГЛАВНОЕ МЕНЮ ==========
async def main_menu(message, context):
    keyboard = [
        [InlineKeyboardButton("📢 Накрутить подписчиков", 
callback_data="get_subscribers")],
        [InlineKeyboardButton("💰 Баланс токенов", 
callback_data="balance")],
        [InlineKeyboardButton("📋 Выполнить задание", 
callback_data="do_task")],
        [InlineKeyboardButton("🆘 Поддержка", callback_data="support")]
    ]
    text = (
        "🤖 *Бот для взаимной подписки на Telegram-каналы*\n\n"
        "Здесь ты можешь накрутить подписчиков, выполняя задания.\n"
        "1 задание = 1 токен. 1 токен = 1 подписчик.\n\n"
        "⚠️ При попытке скама — проверка в течение 3 часов и бан."
    )
    await message.reply_text(text, 
reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ========== СТАРТ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    try:
        member = await context.bot.get_chat_member(MAIN_CHANNEL, user_id)
        if member.status in ["member", "administrator", "creator"]:
            await update.message.reply_text("✅ Подписка подтверждена!")
            await asyncio.sleep(1)
            await main_menu(update.message, context)
        else:
            await update.message.reply_text(
                f"❌ Ты не подписан на канал {MAIN_CHANNEL}.\nПодпишись и 
нажми /start снова."
            )
    except Exception as e:
        logger.error(f"Start error: {e}")
        await update.message.reply_text("⚠️ Ошибка проверки. Добавь бота в 
админы канала.")

# ========== КНОПКИ ==========
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    conn = sqlite3.connect("subscriptions.db")
    cur = conn.cursor()
    cur.execute("SELECT tokens, channel_link FROM users WHERE user_id = 
?", (user_id,))
    row = cur.fetchone()
    conn.close()

    if data == "balance":
        tokens = row[0] if row else 0
        await query.edit_message_text(f"💰 Твой баланс: *{tokens} 
токенов*", parse_mode="Markdown")
        return

    if data == "support":
        await query.edit_message_text(
            "🆘 *Поддержка*\n\nПо вопросам пиши: @elvin_support\nИли в 
канал: @ELVINPODPISKA"
        )
        return

    if data == "get_subscribers":
        if not row or not row[1]:
            await query.edit_message_text("❌ Сначала добавь свой канал 
через кнопку 'Выполнить задание'.")
            return
        if row[0] < 1:
            await query.edit_message_text("❌ Недостаточно токенов. 
Выполни задания, чтобы получить токены.")
            return
        await query.edit_message_text(f"💰 У тебя {row[0]} токенов. Напиши 
*число* — сколько подписчиков накрутить.")
        context.user_data["waiting_for_amount"] = True
        return

    if data == "do_task":
        if row and row[1]:
            await give_task(query, context, user_id)
        else:
            await query.edit_message_text(
                "📌 Вставь ссылку на свой Telegram-канал (t.me/... или 
t.me/joinchat/...)\nТолько 1 канал на аккаунт!"
            )
            context.user_data["waiting_for_link"] = True

# ========== ВСТАВКА ССЫЛКИ ==========
async def handle_message(update: Update, context: 
ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if context.user_data.get("waiting_for_link"):
        conn = sqlite3.connect("subscriptions.db")
        cur = conn.cursor()
        cur.execute("SELECT channel_link FROM users WHERE user_id = ?", 
(user_id,))
        if cur.fetchone():
            await update.message.reply_text("❌ Ты уже добавил канал. 
Можно только один.")
            conn.close()
            return
        cur.execute("INSERT OR REPLACE INTO users (user_id, channel_link, 
tokens) VALUES (?, ?, COALESCE((SELECT tokens FROM users WHERE user_id = 
?), 0))", (user_id, text, user_id))
        conn.commit()
        conn.close()
        context.user_data["waiting_for_link"] = False
        await update.message.reply_text("✅ Ссылка сохранена! Теперь 
выполняй задания для получения токенов.")
        await main_menu(update.message, context)
        return

    if context.user_data.get("waiting_for_amount"):
        try:
            amount = int(text)
            conn = sqlite3.connect("subscriptions.db")
            cur = conn.cursor()
            cur.execute("SELECT tokens FROM users WHERE user_id = ?", 
(user_id,))
            row = cur.fetchone()
            if not row or row[0] < amount:
                await update.message.reply_text("❌ Недостаточно 
токенов.")
                conn.close()
                return
            new_tokens = row[0] - amount
            cur.execute("UPDATE users SET tokens = ?, subscribers_needed = 
? WHERE user_id = ?", (new_tokens, amount, user_id))
            conn.commit()
            conn.close()
            context.user_data["waiting_for_amount"] = False
            await update.message.reply_text(f"✅ Ты поставил в очередь на 
{amount} подписчиков. Они придут автоматически.")
        except ValueError:
            await update.message.reply_text("❌ Введи число.")

# ========== ВЫДАЧА ЗАДАНИЯ ==========
async def give_task(query, context, user_id):
    conn = sqlite3.connect("subscriptions.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id, channel_link FROM users WHERE 
channel_link IS NOT NULL AND user_id != ? AND subscribers_received < 
subscribers_needed", (user_id,))
    others = cur.fetchall()
    if not others:
        await query.edit_message_text("❌ Нет активных каналов для 
подписки. Попробуй позже.")
        conn.close()
        return
    target = random.choice(others)
    target_id, link = target
    await query.edit_message_text(
        f"📌 Подпишись на этот канал:\n{link}\n\n⚠️ При попытке скама — 
проверка в течение 3 часов и бан.\nПосле подписки жди 20 секунд — 
засчитается 1 токен."
    )
    await asyncio.sleep(20)
    conn2 = sqlite3.connect("subscriptions.db")
    cur2 = conn2.cursor()
    cur2.execute("INSERT INTO tasks (from_user, to_user, done) VALUES (?, 
?, 1)", (user_id, target_id))
    cur2.execute("UPDATE users SET tokens = tokens + 1 WHERE user_id = ?", 
(user_id,))
    cur2.execute("UPDATE users SET subscribers_received = 
subscribers_received + 1 WHERE user_id = ?", (target_id,))
    conn2.commit()
    conn2.close()
    await query.edit_message_text("✅ +1 токен! Можешь продолжить 
выполнять задания.")

# ========== ЗАПУСК ==========
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, 
handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
