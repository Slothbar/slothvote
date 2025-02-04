import os
import logging
import requests
from telegram import Update, Poll, ChatMemberUpdated
from telegram.ext import (
    Application, CommandHandler, PollHandler, CallbackContext, ChatMemberHandler
)

# Load environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Your BotFather token
HEDERA_ACCOUNT_ID = os.getenv("HEDERA_RECEIVING_ACCOUNT")  # Wallet receiving payments
SLOTH_AMOUNT = 10  # Amount required per vote in $SLOTH
SLOTH_TOKEN_ID = os.getenv("SLOTH_TOKEN_ID")  # Your $SLOTH Token ID (if HTS)
PAID_USERS = {}  # Tracks paid users
USER_WALLETS = {}  # Stores user Telegram ID & registered wallet
VOTED_USERS = set()  # Prevents duplicate votes
ACTIVE_POLL = None  # Stores active poll details
ACTIVE_POLL_INFO = None  # Stores additional poll description

# Configure logging
logging.basicConfig(level=logging.INFO)

async def begin(update: Update, context: CallbackContext):
    """Welcome message for the bot (replaces /start)."""
    await update.message.reply_text(
        "🦥 Welcome to SlothVoteBot! 🦥\n\n"
        "To participate in voting, follow these steps:\n"
        "1️⃣ **Register your sending wallet** → `/register 0.0.123456`\n"
        "2️⃣ **Send 10 $SLOTH** to our wallet (use `/vote` for details)\n"
        "3️⃣ **Verify your payment** → `/verify`\n"
        "4️⃣ **Check active polls** → `/poll_status`\n\n"
        "Once verified, you will receive the active poll!"
    )

async def welcome_new_user(update: Update, context: CallbackContext):
    """Sends a welcome message when a user joins the group."""
    chat_member: ChatMemberUpdated = update.chat_member
    new_user = chat_member.new_chat_member.user

    if chat_member.new_chat_member.status == "member":
        welcome_message = (
            f"👋 **Welcome to SlothBar Voting, {new_user.first_name}!** 🦥\n\n"
            "Here’s how to participate in our voting system:\n"
            "🗳 **User Commands:**\n"
            "🔹 `/register 0.0.xxxxxx` – Link your Hedera wallet\n"
            "🔹 `/vote` – Get payment details\n"
            "🔹 `/verify` – Confirm payment & receive the poll\n"
            "🔹 `/poll_status` – Check if voting is active\n\n"
            "🚀 **Complete these steps to vote in our polls!**"
        )

        await context.bot.send_message(chat_id=chat_member.chat.id, text=welcome_message)

async def register(update: Update, context: CallbackContext):
    """Register the user's sending wallet address."""
    user_id = update.message.from_user.id
    args = context.args

    if not args:
        await update.message.reply_text("⚠️ Please provide your Hedera wallet address after `/register`. Example:\n/register 0.0.123456")
        return

    wallet_address = args[0]

    if not wallet_address.startswith("0.0.") or not wallet_address.replace("0.0.", "").isdigit():
        await update.message.reply_text("⚠️ Invalid wallet address format! Use a valid Hedera account ID like `0.0.123456`.")
        return

    USER_WALLETS[user_id] = wallet_address

    await update.message.reply_text(f"✅ Your wallet `{wallet_address}` has been registered!\nNow send `{SLOTH_AMOUNT} $SLOTH` to `{HEDERA_ACCOUNT_ID}` and use `/verify`.")

async def create_poll(update: Update, context: CallbackContext):
    """Admin command to create a new poll dynamically with optional project info."""
    global ACTIVE_POLL, ACTIVE_POLL_INFO

    args = " ".join(context.args)
    if not args or "|" not in args:
        await update.message.reply_text("⚠️ Use `/create_poll question | option1 | option2 | ... | [Optional: Poll Description]`.")
        return

    parts = args.split("|")
    question = parts[0].strip()
    options = [opt.strip() for opt in parts[1:-1]]
    project_info = parts[-1].strip()

    if len(options) < 2:
        await update.message.reply_text("⚠️ You must provide at least two options for the poll.")
        return

    ACTIVE_POLL = {"question": question, "options": options}
    ACTIVE_POLL_INFO = project_info if project_info else None  # Store project info if provided

    await update.message.reply_text("✅ Poll created! Users will receive this poll upon payment verification.")

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("begin", begin))
    application.add_handler(ChatMemberHandler(welcome_new_user, ChatMemberHandler.CHAT_MEMBER))
    application.add_handler(CommandHandler("register", register))  # ✅ FIXED: Restored /register command
    application.add_handler(CommandHandler("create_poll", create_poll))

    application.run_polling()

if __name__ == "__main__":
    main()
