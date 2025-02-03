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

# Configure logging
logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: CallbackContext):
    """Welcome message for the bot."""
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

async def verify(update: Update, context: CallbackContext):
    """Verify if the user has sent the required amount of $SLOTH from their registered wallet."""
    user_id = update.message.from_user.id

    if ACTIVE_POLL is None:
        await update.message.reply_text("⚠️ There is no active poll right now. Please wait for the next poll before verifying payment.")
        return

    if user_id in PAID_USERS:
        await update.message.reply_text("✅ You've already paid! You will now receive the poll.")
        await send_poll(update, context)
        return

    if user_id not in USER_WALLETS:
        await update.message.reply_text("⚠️ You must first register your wallet using `/register` before verifying payment!")
        return

    sender_wallet = USER_WALLETS[user_id]

    response = requests.get(
        f"https://mainnet-public.mirrornode.hedera.com/api/v1/transactions?account.id={sender_wallet}&limit=50"
    )

    if response.status_code != 200:
        await update.message.reply_text("⚠️ Error checking transactions. Please try again later.")
        return

    data = response.json()

    for transaction in data.get("transactions", []):
        transfers = transaction.get("transfers", [])
        token_transfers = transaction.get("token_transfers", [])

        for transfer in transfers:
            if transfer["account"] == HEDERA_ACCOUNT_ID and abs(transfer["amount"]) >= SLOTH_AMOUNT:
                PAID_USERS[user_id] = True
                await update.message.reply_text("✅ Payment verified! Here is your poll:")
                await send_poll(update, context)
                return

        for token_transfer in token_transfers:
            if token_transfer["token_id"] == SLOTH_TOKEN_ID and token_transfer["account"] == HEDERA_ACCOUNT_ID and abs(token_transfer["amount"]) >= SLOTH_AMOUNT:
                PAID_USERS[user_id] = True
                await update.message.reply_text("✅ Payment verified! Here is your poll:")
                await send_poll(update, context)
                return

    await update.message.reply_text("⚠️ No valid payment found from your registered wallet. Make sure you sent the correct amount.")

async def send_poll(update: Update, context: CallbackContext):
    """Automatically sends the current poll to verified users."""
    user_id = update.message.from_user.id

    if user_id in VOTED_USERS:
        await update.message.reply_text("⚠️ You have already voted! Duplicate votes are not allowed.")
        return

    if not ACTIVE_POLL:
        await update.message.reply_text("⚠️ No active poll available.")
        return

    poll_message = await update.message.reply_poll(
        question=ACTIVE_POLL["question"],
        options=ACTIVE_POLL["options"],
        is_anonymous=False
    )

    VOTED_USERS.add(user_id)
    await update.message.reply_text("✅ Your vote has been counted!")

async def create_poll(update: Update, context: CallbackContext):
    """Admin command to create a new poll dynamically."""
    global ACTIVE_POLL

    args = " ".join(context.args)
    if not args or "|" not in args:
        await update.message.reply_text("⚠️ Use `/create_poll question | option1 | option2 | option3`.")
        return

    parts = args.split("|")
    question = parts[0].strip()
    options = [opt.strip() for opt in parts[1:]]

    if len(options) < 2:
        await update.message.reply_text("⚠️ You must provide at least two options for the poll.")
        return

    ACTIVE_POLL = {"question": question, "options": options}
    await update.message.reply_text("✅ Poll created! Users will receive this poll upon payment verification.")

async def reset(update: Update, context: CallbackContext):
    """Admin command to reset the paid users list and votes (for a new poll)."""
    global PAID_USERS, VOTED_USERS, ACTIVE_POLL
    PAID_USERS = {}
    VOTED_USERS = set()
    ACTIVE_POLL = None
    await update.message.reply_text("✅ All payments, votes, and polls have been reset. A new poll can now be created.")

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(ChatMemberHandler(welcome_new_user, ChatMemberHandler.CHAT_MEMBER))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("verify", verify))
    application.add_handler(CommandHandler("create_poll", create_poll))
    application.add_handler(CommandHandler("reset", reset))

    application.run_polling()

if __name__ == "__main__":
    main()
