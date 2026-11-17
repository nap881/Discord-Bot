import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
import dukpy
import cubescrambler
from cubescrambler import (
    scrambler222,
    scrambler333,
    scrambler444,
    scrambler555,
    scrambler666,
    scrambler777,
    pyraminxScrambler,
    skewbScrambler,
    squareOneScrambler,
    clockScrambler,
)
from cube_preview import render_cube_2d, render_preview
from wca_calc import calculate_ao, parse_time, format_time
from room import rooms, create_room, find_player_room, get_user_room

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

def get_megaminx_scramble():
    return dukpy.evaljs([cubescrambler.MATHLIB_SRC, cubescrambler.SCRAMBLE_SRC, cubescrambler.UTIL_SCRAMBLE_SRC], scrambleType='wcamega', n=70).strip()

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
token = os.getenv("DISCORD_TOKEN")

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

CUBE_MAP = {
    "22": ("2x2", 2, scrambler222.get_WCA_scramble),
    "222": ("2x2", 2, scrambler222.get_WCA_scramble),
    "33": ("3x3", 3, scrambler333.get_WCA_scramble),
    "333": ("3x3", 3, scrambler333.get_WCA_scramble),
    "44": ("4x4", 4, scrambler444.get_random_state_scramble),
    "444": ("4x4", 4, scrambler444.get_random_state_scramble),
    "55": ("5x5", 5, scrambler555.get_WCA_scramble),
    "555": ("5x5", 5, scrambler555.get_WCA_scramble),
    "66": ("6x6", 6, scrambler666.get_WCA_scramble),
    "666": ("6x6", 6, scrambler666.get_WCA_scramble),
    "77": ("7x7", 7, scrambler777.get_WCA_scramble),
    "777": ("7x7", 7, scrambler777.get_WCA_scramble),
    "pyra": ("Pyraminx", None, pyraminxScrambler.get_WCA_scramble),
    "pyraminx": ("Pyraminx", None, pyraminxScrambler.get_WCA_scramble),
    "mega": ("Megaminx", None, get_megaminx_scramble),
    "megaminx": ("Megaminx", None, get_megaminx_scramble),
    "skewb": ("Skewb", None, skewbScrambler.get_WCA_scramble),
    "sq1": ("Square-1", None, squareOneScrambler.get_WCA_scramble),
    "square1": ("Square-1", None, squareOneScrambler.get_WCA_scramble),
    "clock": ("Clock", None, clockScrambler.get_WCA_scramble),
}

async def handle_scramble_command(ctx, cube_name: str, size, scramble_fn, count: int = 1):
    if count < 1:
        await ctx.send("Please specify at least 1 scramble.")
        return
    if count > 12:
        await ctx.send("You can generate at most 12 scrambles at a time.")
        return

    if count == 1:
        scramble = scramble_fn()
        embed = discord.Embed(
            title=f"{cube_name} Scramble",
            description=f"```\n{scramble}\n```",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")

        img_buffer = render_preview(scramble, cube_name, size=size)
        if img_buffer:
            file = discord.File(img_buffer, filename="scramble.png")
            embed.set_image(url="attachment://scramble.png")
            await ctx.send(file=file, embed=embed)
        else:
            await ctx.send(embed=embed)
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

async def advance_room(channel, code, room):
    finished = room.advance_round()
    results = room.round_results(room.current_round - 1)
    result_text = "\n".join(results)

    if finished:
        lb = room.leaderboard()
        avg_type = "Mean" if room.rounds < 5 else "Average"
        lb_lines = [
            f"{'>' if i == 0 else ' '} **{i+1}.** {name} — {format_time(avg)}"
            for i, (uid, name, avg) in enumerate(lb)
        ]
        embed = discord.Embed(
            title=f"Room {code} — Final Results",
            description=f"**Round {room.current_round} Results:**\n{result_text}\n\n**Leaderboard ({avg_type}):**\n" + "\n".join(lb_lines),
            color=discord.Color.gold()
        )
        await channel.send(embed=embed)
        if code in rooms:
            del rooms[code]
    else:
        scramble = room.scrambles[room.current_round]
        cube_name, size, _ = CUBE_MAP[room.cube_type]
        embed = discord.Embed(
            title=f"Room {code} — Round {room.current_round + 1}/{room.rounds}",
            description=f"**Round {room.current_round} Results:**\n{result_text}\n\n**Next Scramble:**\n```\n{scramble}\n```\n\nType your time in chat",
            color=discord.Color.blue()
        )
        img_buffer = render_preview(scramble, room.cube_type, size=size)
        if img_buffer:
            file = discord.File(img_buffer, filename="scramble.png")
            embed.set_image(url="attachment://scramble.png")
            await channel.send(file=file, embed=embed)
        else:
            await channel.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.lower() in ["hello", "hi", "sup"]:
        await message.channel.send(f"Hello {message.author.mention}!")

    code, room = find_player_room(message.channel.id, message.author.id)
    if room and not message.content.startswith("!"):
        text = message.content.strip()
        ok, result = room.submit_time(message.author.id, text)
        if ok:
            await message.add_reaction("\u2705")
            if room.all_submitted():
                await advance_room(message.channel, code, room)

    await bot.process_commands(message)

@bot.command()
async def test(ctx):
    await ctx.send('this is a test')

@bot.command(name="22", aliases=["222"])
async def scramble_22(ctx, count: int = 1):
    await handle_scramble_command(ctx, "2x2", 2, scrambler222.get_WCA_scramble, count)

@bot.command(name="33", aliases=["333"])
async def scramble_33(ctx, count: int = 1):
    await handle_scramble_command(ctx, "3x3", 3, scrambler333.get_WCA_scramble, count)

@bot.command(name="44", aliases=["444"])
async def scramble_44(ctx, count: int = 1):
    await handle_scramble_command(ctx, "4x4", 4, scrambler444.get_random_state_scramble, count)

@bot.command(name="55", aliases=["555"])
async def scramble_55(ctx, count: int = 1):
    await handle_scramble_command(ctx, "5x5", 5, scrambler555.get_WCA_scramble, count)

@bot.command(name="66", aliases=["666"])
async def scramble_66(ctx, count: int = 1):
    await handle_scramble_command(ctx, "6x6", 6, scrambler666.get_WCA_scramble, count)

@bot.command(name="77", aliases=["777"])
async def scramble_77(ctx, count: int = 1):
    await handle_scramble_command(ctx, "7x7", 7, scrambler777.get_WCA_scramble, count)

@bot.command(name="pyra", aliases=["pyraminx"])
async def scramble_pyra(ctx, count: int = 1):
    await handle_scramble_command(ctx, "Pyraminx", None, pyraminxScrambler.get_WCA_scramble, count)

@bot.command(name="mega", aliases=["megaminx"])
async def scramble_mega(ctx, count: int = 1):
    await handle_scramble_command(ctx, "Megaminx", None, get_megaminx_scramble, count)

@bot.command(name="skewb")
async def scramble_skewb(ctx, count: int = 1):
    await handle_scramble_command(ctx, "Skewb", None, skewbScrambler.get_WCA_scramble, count)

@bot.command(name="sq1", aliases=["square1"])
async def scramble_sq1(ctx, count: int = 1):
    await handle_scramble_command(ctx, "Square-1", None, squareOneScrambler.get_WCA_scramble, count)

@bot.command(name="clock")
async def scramble_clock(ctx, count: int = 1):
    await handle_scramble_command(ctx, "Clock", None, clockScrambler.get_WCA_scramble, count)

@scramble_22.error
@scramble_33.error
@scramble_44.error
@scramble_55.error
@scramble_66.error
@scramble_77.error
@scramble_pyra.error
@scramble_mega.error
@scramble_skewb.error
@scramble_sq1.error
@scramble_clock.error
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

@bot.command(name="room", aliases=["create"])
async def cmd_room(ctx, cube: str = None, rounds: int = None):
    existing_code, existing_room = get_user_room(ctx.author.id)
    if existing_room is not None:
        role = "hosting" if existing_room.host_id == ctx.author.id else "attending"
        await ctx.send(f"You are already {role} Room `{existing_code}`. You cannot create a new room.")
        return

    if cube is None or rounds is None:
        await ctx.send("Usage: `!room <puzzle> <rounds>` (e.g. `!room 33 5`)\nPuzzles: `22`, `33`, `44`, `55`, `66`, `77`, `pyra`, `mega`, `skewb`, `sq1`, `clock`")
        return
    cube = cube.lower()
    if cube not in CUBE_MAP:
        await ctx.send("Invalid puzzle. Choose from: `22`, `33`, `44`, `55`, `66`, `77`, `pyra`, `mega`, `skewb`, `sq1`, `clock`.")
        return
    if rounds < 1 or rounds > 50:
        await ctx.send("Rounds must be between 1 and 50.")
        return

    cube_name, size, scramble_fn = CUBE_MAP[cube]
    code = create_room(ctx.author.id, ctx.channel.id, cube, rounds, scramble_fn)
    room = rooms[code]
    room.add_player(ctx.author.id, ctx.author.display_name)

    embed = discord.Embed(
        title=f"Room Created — {cube_name}",
        description=f"**Room Code:** `{code}`\n**Rounds:** {rounds}\n**Host:** {ctx.author.display_name}\n\nPlayers can join with `!join {code}`\nHost starts with `!start`",
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed)

@bot.command(name="join")
async def cmd_join(ctx, code: str = None):
    if code is None:
        await ctx.send("Usage: `!join <code>` (e.g. `!join 123456`)")
        return
    if code not in rooms:
        await ctx.send("Room not found.")
        return

    existing_code, existing_room = get_user_room(ctx.author.id)
    if existing_room is not None:
        if existing_code == code:
            await ctx.send("You are already in this room.")
        else:
            role = "hosting" if existing_room.host_id == ctx.author.id else "attending"
            await ctx.send(f"You are already {role} Room `{existing_code}`. You must leave it before joining another.")
        return

    room = rooms[code]
    if room.state != "waiting":
        await ctx.send("This room has already started.")
        return

    room.add_player(ctx.author.id, ctx.author.display_name)
    player_list = "\n".join(f"- {name}" for name in room.players.values())
    cube_name = CUBE_MAP[room.cube_type][0]

    embed = discord.Embed(
        title=f"{ctx.author.display_name} joined Room {code}",
        description=f"**{cube_name}** — {room.rounds} rounds\n\n**Players ({len(room.players)}):**\n{player_list}",
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed)

@bot.command(name="start")
async def cmd_start(ctx):
    target_room = None
    target_code = None
    for code, room in rooms.items():
        if room.host_id == ctx.author.id and room.channel_id == ctx.channel.id and room.state == "waiting":
            target_room = room
            target_code = code
            break

    if target_room is None:
        await ctx.send("You don't have a room to start in this channel.")
        return

    target_room.start()
    scramble = target_room.scrambles[0]
    cube_name, size, _ = CUBE_MAP[target_room.cube_type]
    player_list = ", ".join(target_room.players.values())
    embed = discord.Embed(
        title=f"Room {target_code} — Round 1/{target_room.rounds}",
        description=f"**Players:** {player_list}\n\n**Scramble:**\n```\n{scramble}\n```\n\nType your time in chat (e.g. `12.34`, `1:05.23`, `DNF`)",
        color=discord.Color.green()
    )
    img_buffer = render_preview(scramble, target_room.cube_type, size=size)
    if img_buffer:
        file = discord.File(img_buffer, filename="scramble.png")
        embed.set_image(url="attachment://scramble.png")
        await ctx.send(file=file, embed=embed)
    else:
        await ctx.send(embed=embed)

@bot.command(name="next")
async def cmd_next(ctx):
    target_room = None
    target_code = None
    for code, room in rooms.items():
        if room.host_id == ctx.author.id and room.channel_id == ctx.channel.id and room.state == "active":
            target_room = room
            target_code = code
            break

    if target_room is None:
        await ctx.send("You don't have an active room in this channel.")
        return

    await advance_room(ctx.channel, target_code, target_room)

@bot.command(name="leave")
async def cmd_leave(ctx):
    target_code, target_room = get_user_room(ctx.author.id)
    if target_room is None:
        await ctx.send("You are not currently in any room.")
        return

    if target_room.host_id == ctx.author.id:
        del rooms[target_code]
        await ctx.send(f"Room `{target_code}` has been disbanded by the host.")
    else:
        target_room.remove_player(ctx.author.id)
        await ctx.send(f"{ctx.author.display_name} has left Room `{target_code}`.")
        if len(target_room.players) == 0:
            del rooms[target_code]
            await ctx.send(f"No players left in Room `{target_code}`. Room has been disbanded.")
        elif target_room.state == "active" and target_room.all_submitted():
            channel = bot.get_channel(target_room.channel_id) or ctx.channel
            await advance_room(channel, target_code, target_room)

@bot.command(name="rooms")
async def cmd_rooms(ctx):
    if not rooms:
        await ctx.send("No active rooms right now.")
        return

    embed = discord.Embed(
        title="Active Rooms",
        color=discord.Color.blue()
    )
    for code, room in rooms.items():
        cube_name = CUBE_MAP[room.cube_type][0]
        status = f"Round {room.current_round + 1}/{room.rounds}" if room.state == "active" else "Waiting for players"
        player_names = ", ".join(room.players.values())
        embed.add_field(
            name=f"Room {code} ({cube_name})",
            value=f"**Status:** {status}\n**Players ({len(room.players)}):** {player_names}",
            inline=False
        )
    await ctx.send(embed=embed)

bot.run(token, log_handler=handler, log_level=logging.DEBUG)
