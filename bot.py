import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import aiohttp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Telegram Bot Token and Group Invite Link from environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_INVITE_LINK = os.getenv("GROUP_INVITE_LINK")
SLOTHBAR_TOKEN_ID = os.getenv("SLOTHBAR_TOKEN_ID")

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_hedera_wallet(wallet_address):
    """Query Hedera Mirror Nodes to check Slothbar token balance."""
    url = f"https://mainnet-public.mirrornode.hedera.com/api/v1/accounts/{wallet_address}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                for token in data.get("tokens", []):
                    if token["token_id"] == SLOTHBAR_TOKEN_ID and int(token["balance"]) > 0:
                        return True
    return False

async def start(update: Update, context: CallbackContext):
    """Handles the /start command."""
    await update.message.reply_text("Welcome! Please enter your Hedera wallet address to verify your Slothbar holdings.")

async def handle_wallet(update: Update, context: CallbackContext):
    """Handles the user's wallet address input."""
    wallet_address = update.message.text.strip()
    await update.message.reply_text("Checking your wallet for Slothbar holdings... Please wait.")
    
    is_valid = await check_hedera_wallet(wallet_address)
    if is_valid:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Voting Group", url=GROUP_INVITE_LINK)]
        ])
        await update.message.reply_text("You are verified! Click below to join the voting group.", reply_markup=keyboard)
    else:
        await update.message.reply_text("Sorry, you don't have the required Slothbar tokens.")
    
    # Reset interaction
    await asyncio.sleep(2)
    await update.message.reply_text("You can try again by sending your wallet address.")

def main():
    """Start the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet))

    # Run bot
    application.run_polling()

if __name__ == "__main__":
    main()
