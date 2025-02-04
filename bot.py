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
    """Send a welcome message, but only visible to the user who triggered it."""
    user = update.message.from_user  # Get user details

    await update.message.reply_text(
        f"🦥 Welcome, {user.first_name}! 🦥\n\n"
        "To participate in voting, follow these steps:\n"
        "1️⃣ **Register your sending wallet** → `/register 0.0.123456`\n"
        "2️⃣ **Send 10 $SLOTH** to our wallet (use `/vote` for details)\n"
        "3️⃣ **Verify your payment** → `/verify`\n"
        "4️⃣ **Check active polls** → `/poll_status`\n\n"
        "Once verified, you will receive the active poll!",
        reply_to_message_id=update.message.message_id  # ✅ Private reply
    )

async def register(update: Update, context: CallbackContext):
    """Register user's sending wallet (only visible to them)."""
    user = update.message.from_user  # Get user details
    args = context.args

    if not args:
        await update.message.reply_text(
            "⚠️ Please provide your Hedera wallet address after `/register`.\nExample: `/register 0.0.1234567`",
            reply_to_message_id=update.message.message_id  # ✅ Private reply
        )
        return

    wallet_address = args[0]

    if not wallet_address.startswith("0.0.") or not wallet_address.replace("0.0.", "").isdigit():
        await update.message.reply_text(
            "⚠️ Invalid wallet address format! Use a valid Hedera account ID like `0.0.1234567`.",
            reply_to_message_id=update.message.message_id  # ✅ Private reply
        )
        return

    USER_WALLETS[user.id] = wallet_address  # Store the wallet

    await update.message.reply_text(
        f"✅ Your wallet has been registered!\n"
        f"Now send `{SLOTH_AMOUNT} $SLOTH` to `{HEDERA_ACCOUNT_ID}` and use `/verify`.",
        reply_to_message_id=update.message.message_id  # ✅ Private reply
    )

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("begin", begin))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("verify", verify))
    application.add_handler(CommandHandler("create_poll", create_poll))
    application.add_handler(PollHandler(poll_handler))

    application.run_polling()

if __name__ == "__main__":
    main()
