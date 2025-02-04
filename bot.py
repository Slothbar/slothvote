import os
import logging
import requests
import time
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
LATEST_POLL_TIMESTAMP = None  # Tracks when the latest poll started

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

async def register(update: Update, context: CallbackContext):
    """Register the user's sending wallet address, mask it in chat, and delete the user's input while confirming registration."""
    user_id = update.message.from_user.id
    args = context.args

    if not args:
        await update.message.reply_text("⚠️ Please provide your Hedera wallet address after `/register`. Example:\n/register 0.0.1234567")
        return

    wallet_address = args[0]

    if not wallet_address.startswith("0.0.") or not wallet_address.replace("0.0.", "").isdigit():
        await update.message.reply_text("⚠️ Invalid wallet address format! Use a valid Hedera account ID like `0.0.1234567`.")
        return

    USER_WALLETS[user_id] = wallet_address  # Store the real wallet

    # Mask the wallet for the group message
    masked_wallet = "X.X.XXXXXXX"

    # 🚨 Delete user's message to hide their input
    try:
        await update.message.delete()
    except Exception as e:
        logging.warning(f"Could not delete message: {e}")

    # ✅ Send a NEW message (instead of replying to deleted one)
    await context.bot.send_message(
        chat_id=update.message.chat_id,
        text=f"✅ Your wallet `{masked_wallet}` has been registered!\n"
             f"Now send `{SLOTH_AMOUNT} $SLOTH` to `{HEDERA_ACCOUNT_ID}` and use `/verify`."
    )
    
async def send_poll(update: Update, context: CallbackContext):
    """Automatically sends the current poll to verified users, including project details."""
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id  # Get the chat ID

    logging.info(f"✅ DEBUG: Sending poll - ACTIVE_POLL: {ACTIVE_POLL}")

    if user_id in VOTED_USERS:
        await context.bot.send_message(chat_id=user_id, text="⚠️ You have already voted! Duplicate votes are not allowed.")
        return

    if not ACTIVE_POLL:
        await context.bot.send_message(chat_id=user_id, text="⚠️ No active poll available.")
        return

    if ACTIVE_POLL_INFO:
        await context.bot.send_message(chat_id=user_id, text=f"📝 **Poll Details:**\n{ACTIVE_POLL_INFO}")

    try:
        poll_message = await context.bot.send_poll(
            chat_id=user_id,  # Send poll directly to user
            question=ACTIVE_POLL["question"],
            options=ACTIVE_POLL["options"],
            is_anonymous=False
        )
        VOTED_USERS.add(user_id)
        await context.bot.send_message(chat_id=user_id, text="✅ Your vote has been counted!")

    except Exception as e:
        logging.error(f"❌ ERROR sending poll: {e}")
        await context.bot.send_message(chat_id=user_id, text="⚠️ Error sending poll. Please contact an admin.")

async def verify(update: Update, context: CallbackContext):
    """Verify if the user has sent the required amount of $SLOTH from their registered wallet."""
    global ACTIVE_POLL, LATEST_POLL_TIMESTAMP

    user_id = update.message.from_user.id

    logging.info(f"✅ DEBUG: Checking verification - ACTIVE_POLL: {ACTIVE_POLL}")  # Log current poll

    if not ACTIVE_POLL:
        await update.message.reply_text("⚠️ There is no active poll right now. Please wait for the next poll before verifying payment.")
        return

    if user_id in PAID_USERS:
        await update.message.reply_text("✅ You've already paid for this poll! You will now receive the poll.")
        await send_poll(update, context)
        return

    if user_id not in USER_WALLETS:
        await update.message.reply_text("⚠️ You must first register your wallet using `/register` before verifying payment!")
        return

    sender_wallet = USER_WALLETS[user_id]

    # Fetch last 100 transactions
    response = requests.get(
        f"https://mainnet-public.mirrornode.hedera.com/api/v1/transactions?account.id={sender_wallet}&limit=100"
    )

    if response.status_code != 200:
        await update.message.reply_text("⚠️ Error checking transactions. Please try again later.")
        return

    data = response.json()
    found_payment = False  

    logging.info(f"✅ DEBUG: Latest Poll Timestamp: {LATEST_POLL_TIMESTAMP}")

    for transaction in data.get("transactions", []):
        transaction_timestamp = float(transaction["consensus_timestamp"])
        logging.info(f"✅ DEBUG: Transaction Timestamp: {transaction_timestamp}")

        if LATEST_POLL_TIMESTAMP and transaction_timestamp < LATEST_POLL_TIMESTAMP:
            logging.info(f"✅ DEBUG: Skipping transaction {transaction['transaction_id']} (too old)")
            continue

        for transfer in transaction.get("transfers", []):
            if transfer["account"] == HEDERA_ACCOUNT_ID and abs(transfer["amount"]) >= SLOTH_AMOUNT:
                found_payment = True

        for transfer in transaction.get("token_transfers", []):
            if transfer["token_id"] == SLOTH_TOKEN_ID and transfer["account"] == HEDERA_ACCOUNT_ID:
                found_payment = True

        if found_payment:
            PAID_USERS[user_id] = True
            await send_poll(update, context)
            return

    await update.message.reply_text("⚠️ No valid payment found from your registered wallet for this poll. Make sure you sent the correct amount and try again.")

async def create_poll(update: Update, context: CallbackContext):
    """Admin command to create a new poll dynamically with optional project info."""
    global ACTIVE_POLL, ACTIVE_POLL_INFO, LATEST_POLL_TIMESTAMP

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

    # Fetch the latest timestamp for accurate tracking
    response = requests.get("https://mainnet-public.mirrornode.hedera.com/api/v1/transactions?limit=1")
    if response.status_code == 200:
        latest_transaction = response.json().get("transactions", [{}])[0]
        LATEST_POLL_TIMESTAMP = float(latest_transaction.get("consensus_timestamp", time.time()))
    else:
        LATEST_POLL_TIMESTAMP = time.time()  # Fallback if API fails

    ACTIVE_POLL = {"question": question, "options": options}
    ACTIVE_POLL_INFO = project_info if project_info else None  

    logging.info(f"✅ DEBUG: Active poll set -> {ACTIVE_POLL}")  # Confirm poll is stored
    await update.message.reply_text("✅ Poll created! Users will receive this poll upon payment verification.")

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("begin", begin))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("verify", verify))
    application.add_handler(CommandHandler("create_poll", create_poll))

    application.run_polling()

if __name__ == "__main__":
    main()
