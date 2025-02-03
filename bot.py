import os
import logging
import requests
from telegram import Update, Poll
from telegram.ext import Application, CommandHandler, PollHandler, CallbackContext

# Load environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Your BotFather token
HEDERA_ACCOUNT_ID = os.getenv("HEDERA_RECEIVING_ACCOUNT")  # Wallet receiving payments
SLOTH_AMOUNT = 10  # Amount required per vote in $SLOTH
SLOTH_TOKEN_ID = os.getenv("SLOTH_TOKEN_ID")  # Your $SLOTH Token ID (if HTS)
PAID_USERS = {}  # Tracks paid users
USER_WALLETS = {}  # Stores user Telegram ID & registered wallet
ACTIVE_POLL_ID = None  # Stores the active poll ID if a poll exists

# Configure logging
logging.basicConfig(level=logging.INFO)

# Hedera Mirror Node API (Public)
HEDERA_MIRROR_NODE_URL = "https://mainnet-public.mirrornode.hedera.com/api/v1/transactions"

async def start(update: Update, context: CallbackContext):
    """Welcome message for the bot."""
    await update.message.reply_text(
        "🦥 Welcome to SlothVoteBot! 🦥\n\n"
        "To participate in voting, follow these steps:\n"
        "1️⃣ **Register your sending wallet** → `/register 0.0.123456`\n"
        "2️⃣ **Send 10 $SLOTH** to our wallet (use `/vote` for details)\n"
        "3️⃣ **Verify your payment** → `/verify`\n"
        "4️⃣ **Check active polls** → `/poll_status`\n\n"
        "Once verified, you'll be able to participate in the poll!"
    )

async def register(update: Update, context: CallbackContext):
    """Register the user's sending wallet address."""
    user_id = update.message.from_user.id
    args = context.args

    if not args:
        await update.message.reply_text("⚠️ Please provide your Hedera wallet address after `/register`. Example:\n/register 0.0.123456")
        return

    wallet_address = args[0]

    # Validate wallet address format
    if not wallet_address.startswith("0.0.") or not wallet_address.replace("0.0.", "").isdigit():
        await update.message.reply_text("⚠️ Invalid wallet address format! Use a valid Hedera account ID like `0.0.123456`.")
        return

    USER_WALLETS[user_id] = wallet_address  # Save the user's wallet address

    await update.message.reply_text(f"✅ Your wallet `{wallet_address}` has been registered!\nNow send `{SLOTH_AMOUNT} $SLOTH` to `{HEDERA_ACCOUNT_ID}` and use `/verify`.")

async def vote(update: Update, context: CallbackContext):
    """Handles voting access requests and provides payment info."""
    user_id = update.message.from_user.id

    if user_id not in USER_WALLETS:
        await update.message.reply_text("⚠️ You must first register your wallet using `/register` before voting!")
        return

    if user_id in PAID_USERS:
        await update.message.reply_text("✅ You've already paid! You can participate in the poll.")
    else:
        await update.message.reply_text(
            f"💰 **Payment Required**\n\n"
            f"To vote, send `{SLOTH_AMOUNT} $SLOTH` to the following address:\n\n"
            f"🦥 **{HEDERA_ACCOUNT_ID}**\n\n"
            "📌 Once you've made the payment, use `/verify` to confirm your transaction."
        )

async def verify(update: Update, context: CallbackContext):
    """Verify if the user has sent the required amount of $SLOTH from their registered wallet and if a poll exists."""
    user_id = update.message.from_user.id

    if ACTIVE_POLL_ID is None:
        await update.message.reply_text("⚠️ There is no active poll right now. Please wait for the next poll before verifying payment.")
        return

    if user_id in PAID_USERS:
        await update.message.reply_text("✅ You've already paid! You can participate in the poll.")
        return

    if user_id not in USER_WALLETS:
        await update.message.reply_text("⚠️ You must first register your wallet using `/register` before verifying payment!")
        return

    sender_wallet = USER_WALLETS[user_id]  # Get the user's registered wallet

    # Call Hedera's **Public Mirror Node API** (No API Key required)
    response = requests.get(
        f"https://mainnet-public.mirrornode.hedera.com/api/v1/transactions?account.id={sender_wallet}&limit=50"
    )

    if response.status_code != 200:
        await update.message.reply_text("⚠️ Error checking transactions. Please try again later.")
        return

    data = response.json()

    # Scan recent transactions to see if the user paid the required amount
    for transaction in data.get("transactions", []):
        transfers = transaction.get("transfers", [])
        token_transfers = transaction.get("token_transfers", [])

        # Check HBAR transfers
        for transfer in transfers:
            if transfer["account"] == HEDERA_ACCOUNT_ID and abs(transfer["amount"]) >= SLOTH_AMOUNT:
                PAID_USERS[user_id] = True  # Mark user as paid
                await update.message.reply_text("✅ Payment verified! You can now participate in the poll.")
                return

        # Check HTS Token Transfers (for $SLOTH as a token)
        for token_transfer in token_transfers:
            if token_transfer["token_id"] == SLOTH_TOKEN_ID and token_transfer["account"] == HEDERA_ACCOUNT_ID and abs(token_transfer["amount"]) >= SLOTH_AMOUNT:
                PAID_USERS[user_id] = True  # Mark user as paid
                await update.message.reply_text("✅ Payment verified! You can now participate in the poll.")
                return

    await update.message.reply_text("⚠️ No valid payment found from your registered wallet. Make sure you sent the correct amount.")

async def create_poll(update: Update, context: CallbackContext):
    """Admin command to create a new poll and track it."""
    global ACTIVE_POLL_ID
    if ACTIVE_POLL_ID is not None:
        await update.message.reply_text("⚠️ A poll is already active! You cannot create a new one until the current poll ends.")
        return

    question = "Should we burn some $SLOTH tokens?"
    options = ["Yes", "No"]

    poll_message = await update.message.reply_poll(
        question=question,
        options=options,
        is_anonymous=False  # Ensures fair voting
    )
    ACTIVE_POLL_ID = poll_message.poll.id  # Track poll ID
    await update.message.reply_text("✅ Poll created! Users can now verify payments and vote.")

async def poll_status(update: Update, context: CallbackContext):
    """Check if a poll is currently active."""
    if ACTIVE_POLL_ID:
        await update.message.reply_text("✅ There is an active poll! Users who have paid can now vote.")
    else:
        await update.message.reply_text("⚠️ There is no active poll at the moment.")

# Set up the bot
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("vote", vote))
    application.add_handler(CommandHandler("verify", verify))
    application.add_handler(CommandHandler("create_poll", create_poll))
    application.add_handler(CommandHandler("poll_status", poll_status))

    application.run_polling()

if __name__ == "__main__":
    main()
