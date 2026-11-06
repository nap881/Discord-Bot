import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
import cubescrambler
from cubescrambler import scrambler333
from cube_preview import render_cube_2d

scrambler333.file_list = [
    cubescrambler.MATHLIB_SRC,
    cubescrambler.SCRAMBLE_SRC,
    cubescrambler.CROSS_SRC,
    cubescrambler.SCRAMBLE_333_SRC,
]

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

    if message.content.lower() in ["hello", "hi", "sup"]:
        await message.channel.send(f"Hello {message.author.mention}!")

    await bot.process_commands(message)

@bot.command()
async def test(ctx):
    await ctx.send('this is a test')

@bot.command(name="33")
async def scramble_33(ctx):
    scramble = scrambler333.get_WCA_scramble()

    img_buffer = render_cube_2d(scramble)
    file = discord.File(img_buffer, filename="scramble.png")

    embed = discord.Embed(
        title="3x3 Scramble",
        description=f"```\n{scramble}\n```",
        color=discord.Color.blue()
    )
    embed.set_image(url="attachment://scramble.png")
    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
    await ctx.send(file=file, embed=embed)

bot.run(token, log_handler=handler, log_level=logging.DEBUG)
