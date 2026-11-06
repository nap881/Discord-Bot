import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
import cubescrambler
from cubescrambler import scrambler222, scrambler333, scrambler444, scrambler555
from cube_preview import render_cube_2d
from wca_calc import calculate_ao

scrambler333.file_list = [
    cubescrambler.MATHLIB_SRC,
    cubescrambler.SCRAMBLE_SRC,
    cubescrambler.CROSS_SRC,
    cubescrambler.SCRAMBLE_333_SRC,
]

scrambler444.file_list = [
    cubescrambler.MATHLIB_SRC,
    cubescrambler.SCRAMBLE_SRC,
    cubescrambler.CROSS_SRC,
    cubescrambler.MEGA_SCRAMBLE_SRC,
]

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
token = os.getenv("DISCORD_TOKEN")

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

async def handle_scramble_command(ctx, cube_name: str, size: int, scramble_fn, count: int = 1):
    if count < 1:
        await ctx.send("Please specify at least 1 scramble.")
        return
    if count > 12:
        await ctx.send("You can generate at most 12 scrambles at a time.")
        return

    if count == 1:
        scramble = scramble_fn()
        img_buffer = render_cube_2d(scramble, size=size)
        file = discord.File(img_buffer, filename="scramble.png")

        embed = discord.Embed(
            title=f"{cube_name} Scramble",
            description=f"```\n{scramble}\n```",
            color=discord.Color.blue()
        )
        embed.set_image(url="attachment://scramble.png")
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(file=file, embed=embed)
    else:
        scrambles = [scramble_fn() for _ in range(count)]
        lines = [f"{i}. {sc}" for i, sc in enumerate(scrambles, 1)]
        content = "```\n" + "\n\n".join(lines) + "\n```"

        embed = discord.Embed(
            title=f"{count} {cube_name} Scrambles",
            description=content,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)

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

@bot.command(name="22")
async def scramble_22(ctx, count: int = 1):
    await handle_scramble_command(ctx, "2x2", 2, scrambler222.get_WCA_scramble, count)

@bot.command(name="33")
async def scramble_33(ctx, count: int = 1):
    await handle_scramble_command(ctx, "3x3", 3, scrambler333.get_WCA_scramble, count)

@bot.command(name="44")
async def scramble_44(ctx, count: int = 1):
    await handle_scramble_command(ctx, "4x4", 4, scrambler444.get_random_state_scramble, count)

@bot.command(name="55")
async def scramble_55(ctx, count: int = 1):
    await handle_scramble_command(ctx, "5x5", 5, scrambler555.get_WCA_scramble, count)

@scramble_22.error
@scramble_33.error
@scramble_44.error
@scramble_55.error
async def scramble_error(ctx, error):
    if isinstance(error, commands.BadArgument):
        await ctx.send("Please specify a valid number (e.g. `!33` or `!33 5`).")

async def send_ao_result(ctx, raw_times: str, count: int):
    if not raw_times.strip():
        await ctx.send(f"Please provide {count} times separated by spaces (e.g. `!ao{count} 12.34 11.50 9.80 16.20 DNF`).")
        return
    try:
        res = calculate_ao(raw_times, count)
        embed = discord.Embed(
            title=f"Ao{count}: {res['average']}",
            color=discord.Color.green() if res['average'] != "DNF" else discord.Color.red()
        )
        embed.add_field(name="Solves", value="\n".join(res["solves"]), inline=False)
        embed.add_field(name="Best", value=res["best"], inline=True)
        embed.add_field(name="Worst", value=res["worst"], inline=True)
        embed.set_footer(text=f"Calculated for {ctx.author.display_name}")
        await ctx.send(embed=embed)
    except ValueError as e:
        await ctx.send(str(e))
    except Exception as e:
        await ctx.send(f"Error calculating Ao{count}: {e}")

@bot.command(name="ao5")
async def cmd_ao5(ctx, *, times: str = ""):
    await send_ao_result(ctx, times, 5)

@bot.command(name="ao12")
async def cmd_ao12(ctx, *, times: str = ""):
    await send_ao_result(ctx, times, 12)

@bot.command(name="ao")
async def cmd_ao(ctx, *, times: str = ""):
    tokens = times.replace(",", " ").replace(";", " ").split()
    if len(tokens) == 5:
        await send_ao_result(ctx, times, 5)
    elif len(tokens) == 12:
        await send_ao_result(ctx, times, 12)
    elif not tokens:
        await ctx.send("Please provide 5 or 12 times (e.g. `!ao 10.2 11.4 9.8 12.1 10.5`).")
    else:
        await ctx.send(f"Provided {len(tokens)} times. Please provide either **5** times for Ao5 or **12** times for Ao12.")

bot.run(token, log_handler=handler, log_level=logging.DEBUG)
