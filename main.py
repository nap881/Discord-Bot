import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
import cubescrambler
from cubescrambler import scrambler222, scrambler333, scrambler444, scrambler555
from cube_preview import render_cube_2d
from wca_calc import calculate_ao, parse_time, format_time
from room import rooms, create_room, find_player_room

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

CUBE_MAP = {
    "22": ("2x2", 2, scrambler222.get_WCA_scramble),
    "33": ("3x3", 3, scrambler333.get_WCA_scramble),
    "44": ("4x4", 4, scrambler444.get_random_state_scramble),
    "55": ("5x5", 5, scrambler555.get_WCA_scramble),
}

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

    code, room = find_player_room(message.channel.id, message.author.id)
    if room and not message.content.startswith("!"):
        text = message.content.strip()
        ok, result = room.submit_time(message.author.id, text)
        if ok:
            await message.add_reaction("\u2705")
            if room.all_submitted():
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
                    await message.channel.send(embed=embed)
                    del rooms[code]
                else:
                    scramble = room.scrambles[room.current_round]
                    cube_name, size, _ = CUBE_MAP[room.cube_type]
                    img_buffer = render_cube_2d(scramble, size=size)
                    file = discord.File(img_buffer, filename="scramble.png")
                    embed = discord.Embed(
                        title=f"Room {code} — Round {room.current_round + 1}/{room.rounds}",
                        description=f"**Round {room.current_round} Results:**\n{result_text}\n\n**Next Scramble:**\n```\n{scramble}\n```",
                        color=discord.Color.blue()
                    )
                    embed.set_image(url="attachment://scramble.png")
                    await message.channel.send(file=file, embed=embed)

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

@bot.command(name="room")
async def cmd_room(ctx, cube: str = None, rounds: int = None):
    if cube is None or rounds is None:
        await ctx.send("Usage: `!room <cube> <rounds>` (e.g. `!room 33 5`)")
        return
    if cube not in CUBE_MAP:
        await ctx.send("Invalid cube type. Use `22`, `33`, `44`, or `55`.")
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
    room = rooms[code]
    if room.state != "waiting":
        await ctx.send("This room has already started.")
        return
    if ctx.author.id in room.players:
        await ctx.send("You are already in this room.")
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

    if len(target_room.players) < 2:
        await ctx.send("You need at least 2 players to start.")
        return

    target_room.start()
    scramble = target_room.scrambles[0]
    cube_name, size, _ = CUBE_MAP[target_room.cube_type]
    img_buffer = render_cube_2d(scramble, size=size)
    file = discord.File(img_buffer, filename="scramble.png")

    player_list = ", ".join(target_room.players.values())
    embed = discord.Embed(
        title=f"Room {target_code} — Round 1/{target_room.rounds}",
        description=f"**Players:** {player_list}\n\n**Scramble:**\n```\n{scramble}\n```\n\nType your time in chat (e.g. `12.34`, `1:05.23`, `DNF`)",
        color=discord.Color.green()
    )
    embed.set_image(url="attachment://scramble.png")
    await ctx.send(file=file, embed=embed)

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

    finished = target_room.advance_round()
    results = target_room.round_results(target_room.current_round - 1)
    result_text = "\n".join(results)

    if finished:
        lb = target_room.leaderboard()
        avg_type = "Mean" if target_room.rounds < 5 else "Average"
        lb_lines = [
            f"{'>' if i == 0 else ' '} **{i+1}.** {name} — {format_time(avg)}"
            for i, (uid, name, avg) in enumerate(lb)
        ]
        embed = discord.Embed(
            title=f"Room {target_code} — Final Results",
            description=f"**Round {target_room.current_round} Results:**\n{result_text}\n\n**Leaderboard ({avg_type}):**\n" + "\n".join(lb_lines),
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)
        del rooms[target_code]
    else:
        scramble = target_room.scrambles[target_room.current_round]
        cube_name, size, _ = CUBE_MAP[target_room.cube_type]
        img_buffer = render_cube_2d(scramble, size=size)
        file = discord.File(img_buffer, filename="scramble.png")
        embed = discord.Embed(
            title=f"Room {target_code} — Round {target_room.current_round + 1}/{target_room.rounds}",
            description=f"**Round {target_room.current_round} Results:**\n{result_text}\n\n**Next Scramble:**\n```\n{scramble}\n```\n\nType your time in chat",
            color=discord.Color.blue()
        )
        embed.set_image(url="attachment://scramble.png")
        await ctx.send(file=file, embed=embed)

bot.run(token, log_handler=handler, log_level=logging.DEBUG)
