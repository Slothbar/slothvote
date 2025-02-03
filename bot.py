import os
import logging
import requests
from telegram import Update, Poll
from telegram.ext import Application, CommandHandler, CallbackContext

# Load environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Your BotFather token
HEDERA_API_KEY = os.getenv("HEDERA_API_KEY")  # Your Hedera API Key (Personal Access Token)
HEDERA_ACCOUNT_ID = os.getenv("HEDERA_RECEIVING_ACCOUNT")  # Wallet receiving payments
SLOTH_AMOUNT = 10  # Amount required per vote in $SLOTH
PAID_USERS = {}  # Dictionary to track who has paid
USER_WALLETS = {}  # Stores user Telegram ID and their Hedera wallet

# Configure logging
logging.basicConfig(level=logging.INFO)

# Hedera Mirror Node API URL
HEDERA_MIRROR_NODE_URL = "https://mainnet-public.mirrornode.hedera.com/api/v1/transactions"

async def start(update: Update, context: CallbackContext):
    """Welcome message for the bot."""
    await update.message.reply_text(
        "Welcome to SlothVoteBot! 🦥\n"
        "To participate in polls, you must send a payment in $SLOTH.\n"
        "First, register your sending wallet with /register.\n"
        "Then use /vote to get payment instructions and /verify after sending payment."
    )

async def register(update: Update, context: CallbackContext):
    """Register the user's sending wallet address."""
    user_id = update.message.from_user.id
    args = context.args

    if not args:
        await update.message.reply_text("⚠️ Please provide your Hedera wallet address after /register. Example:\n/register 0.0.123456")
        return

    wallet_address = args[0]
    USER_WALLETS[user_id] = wallet_address  # Save the user's wallet address

    await update.message.reply_text(f"✅ Your wallet `{wallet_address}` has been registered!\nNow send `{SLOTH_AMOUNT} $SLOTH` and use /verify.")

async def vote(update: Update, context: CallbackContext):
    """Handles voting access requests."""
    user_id = update.message.from_user.id

    if user_id not in USER_WALLETS:
        await update.message.reply_text("⚠️ You must first register your wallet using /register before voting!")
        return

    if user_id in PAID_USERS:
        await update.message.reply_text("✅ You've already paid! You can participate in the poll.")
    else:
        await update.message.reply_text(
            f"To vote, send `{SLOTH_AMOUNT} $SLOTH` to the following address:\n\n"
            f"🦥 **{HEDERA_ACCOUNT_ID}**\n\n"
            "Once you've made the payment, use /verify to confirm your transaction."
        )

async def verify(update: Update, context: CallbackContext):
    """Verify if the user has sent the required amount of $SLOTH from their registered wallet."""
    user_id = update.message.from_user.id

    if user_id in PAID_USERS:
        await update.message.reply_text("✅ You've already paid! You can participate in the poll.")
        return

    if user_id not in USER_WALLETS:
        await update.message.reply_text("⚠️ You must first register your wallet using /register before verifying payment!")
        return

    sender_wallet = USER_WALLETS[user_id]  # Get the user's registered wallet

    # Call Hedera Mirror Node to check transactions
    response = requests.get(
        HEDERA_MIRROR_NODE_URL,
        headers={"x-api-key": HEDERA_API_KEY},
        params={"account.id": sender_wallet, "limit": 10}  # Check transactions from sender's wallet
    )

    if response.status_code != 200:
        await update.message.reply_text("⚠️ Error checking transactions. Please try again later.")
        return

    data = response.json()
    
    # Scan recent transactions to see if the user paid the required amount
    for transaction in data.get("transactions", []):
        amount = sum(t["amount"] for t in transaction.get("transfers", []) if t["account"] == HEDERA_ACCOUNT_ID)

        if amount >= SLOTH_AMOUNT:
            PAID_USERS[user_id] = True  # Mark user as paid
            await update.message.reply_text("✅ Payment verified! You can now participate in the poll.")
            return

    await update.message.reply_text("⚠️ No valid payment found from your registered wallet. Make sure you sent the correct amount.")

async def create_poll(update: Update, context: CallbackContext):
    """Admin command to create a new poll."""
    user_id = update.message.from_user.id
    if user_id not in PAID_USERS:
        await update.message.reply_text("⚠️ You must pay before creating a poll!")
        return

    # Define the poll options
    question = "Should we burn some $SLOTH tokens?"
    options = ["Yes", "No"]
    
    await update.message.reply_poll(
        question=question,
        options=options,
        is_anonymous=False  # Ensures fair voting
    )

async def reset(update: Update, context: CallbackContext):
    """Admin command to reset the paid users list (for a new poll)."""
    global PAID_USERS
    PAID_USERS = {}  # Clear the paid users list
    await update.message.reply_text("✅ Paid users reset. New poll payments required.")

# Set up the bot
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("vote", vote))
    application.add_handler(CommandHandler("verify", verify))
    application.add_handler(CommandHandler("create_poll", create_poll))
    application.add_handler(CommandHandler("reset", reset))

    application.run_polling()

if __name__ == "__main__":
    main()
