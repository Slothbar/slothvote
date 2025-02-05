import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import aiohttp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Telegram Bot Token and Group Invite Link from environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_INVITE_LINK = os.getenv("GROUP_INVITE_LINK")
SLOTHBAR_TOKEN_ID = os.getenv("SLOTHBAR_TOKEN_ID")

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

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

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    """Handles the /start command."""
    await message.answer("Welcome! Please enter your Hedera wallet address to verify your Slothbar holdings.")

@dp.message_handler()
async def handle_wallet(message: types.Message):
    """Handles the user's wallet address input."""
    wallet_address = message.text.strip()
    await message.answer("Checking your wallet for Slothbar holdings... Please wait.")
    
    is_valid = await check_hedera_wallet(wallet_address)
    if is_valid:
        keyboard = InlineKeyboardMarkup().add(
            InlineKeyboardButton("Join Voting Group", url=GROUP_INVITE_LINK)
        )
        await message.answer("You are verified! Click below to join the voting group.", reply_markup=keyboard)
    else:
        await message.answer("Sorry, you don't have the required Slothbar tokens.")
    
    # Reset interaction
    await asyncio.sleep(2)
    await message.answer("You can try again by sending your wallet address.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
