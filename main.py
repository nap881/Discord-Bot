from IPython.core import inputtransformer2
import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
token = os.getenv("DISCORD_TOKEN")

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot is ready as {bot.user.name}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.lower() == "hello" or "Hi" or "sup":
        await message.channel.send(f"Hello {message.author.mention}!")

    await bot.process_commands(message)


bot.run(token, log_handler=handler, log_level=logging.DEBUG)