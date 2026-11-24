import os
import logging
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from google import genai
from google.genai import types
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
import db_manager

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

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

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

PUZZLE_CHOICES = [
    app_commands.Choice(name="3x3", value="33"),
    app_commands.Choice(name="2x2", value="22"),
    app_commands.Choice(name="4x4", value="44"),
    app_commands.Choice(name="5x5", value="55"),
    app_commands.Choice(name="6x6", value="66"),
    app_commands.Choice(name="7x7", value="77"),
    app_commands.Choice(name="Pyraminx", value="pyra"),
    app_commands.Choice(name="Megaminx", value="mega"),
    app_commands.Choice(name="Skewb", value="skewb"),
    app_commands.Choice(name="Square-1", value="sq1"),
    app_commands.Choice(name="Clock", value="clock"),
]

async def reply_embed_file(target, embed, file=None):
    if isinstance(target, discord.Interaction):
        if not target.response.is_done():
            if file:
                await target.response.send_message(embed=embed, file=file)
            else:
                await target.response.send_message(embed=embed)
        else:
            if file:
                await target.followup.send(embed=embed, file=file)
            else:
                await target.followup.send(embed=embed)
    else:
        if file:
            await target.send(embed=embed, file=file)
        else:
            await target.send(embed=embed)

async def reply_text(target, text: str, ephemeral: bool = False):
    if isinstance(target, discord.Interaction):
        if not target.response.is_done():
            await target.response.send_message(text, ephemeral=ephemeral)
        else:
            await target.followup.send(text, ephemeral=ephemeral)
    else:
        await target.send(text)

async def do_scramble(target, user_display_name: str, cube_name: str, size, scramble_fn, count: int = 1):
    if count < 1:
        await reply_text(target, "Please specify at least 1 scramble.")
        return
    if count > 12:
        await reply_text(target, "You can generate at most 12 scrambles at a time.")
        return

    if isinstance(target, discord.Interaction) and not target.response.is_done():
        await target.response.defer()

    if count == 1:
        scramble = await asyncio.to_thread(scramble_fn)
        embed = discord.Embed(
            title=f"{cube_name} Scramble",
            description=f"```\n{scramble}\n```",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Requested by {user_display_name}")

        img_buffer = await asyncio.to_thread(render_preview, scramble, cube_name, size=size)
        if img_buffer:
            file = discord.File(img_buffer, filename="scramble.png")
            embed.set_image(url="attachment://scramble.png")
            await reply_embed_file(target, embed, file=file)
        else:
            await reply_embed_file(target, embed)
    else:
        scrambles = await asyncio.to_thread(lambda: [scramble_fn() for _ in range(count)])
        lines = [f"{i}. {sc}" for i, sc in enumerate(scrambles, 1)]
        content = "```\n" + "\n\n".join(lines) + "\n```"

        embed = discord.Embed(
            title=f"{count} {cube_name} Scrambles",
            description=content,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Requested by {user_display_name}")
        await reply_embed_file(target, embed)

async def do_ao_calc(target, user_display_name: str, raw_times: str, count: int):
    if isinstance(target, discord.Interaction) and not target.response.is_done():
        await target.response.defer()
    if not raw_times.strip():
        await reply_text(target, f"Please provide {count} times separated by spaces (e.g. 12.34 11.50 9.80 16.20 DNF).")
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
        embed.set_footer(text=f"Calculated for {user_display_name}")
        await reply_embed_file(target, embed)
    except ValueError as e:
        await reply_text(target, str(e))
    except Exception as e:
        await reply_text(target, f"Error calculating Ao{count}: {e}")

async def do_ao_auto(target, user_display_name: str, raw_times: str):
    tokens = raw_times.replace(",", " ").replace(";", " ").split()
    if len(tokens) == 5:
        await do_ao_calc(target, user_display_name, raw_times, 5)
    elif len(tokens) == 12:
        await do_ao_calc(target, user_display_name, raw_times, 12)
    elif not tokens:
        await reply_text(target, "Please provide 5 or 12 times (e.g. 10.2 11.4 9.8 12.1 10.5).")
    else:
        await reply_text(target, f"Provided {len(tokens)} times. Please provide either **5** times for Ao5 or **12** times for Ao12.")

async def advance_room(channel, code, room):
    finished = room.advance_round()
    round_idx = room.current_round - 1
    scramble = room.scrambles[round_idx]

    # Record solves in JSON database for PBs & Global averages
    for uid, name in room.players.items():
        t = room.times[uid][round_idx]
        await db_manager.record_solve(uid, name, room.cube_type, t, scramble)

    results = room.round_results(round_idx)
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
            description=f"**Round {room.current_round} Results:**\n{result_text}\n\n**Next Scramble:**\n```\n{scramble}\n```\n\nUse `/submit <time>` to enter your time.",
            color=discord.Color.blue()
        )
        img_buffer = await asyncio.to_thread(render_preview, scramble, room.cube_type, size=size)
        if img_buffer:
            file = discord.File(img_buffer, filename="scramble.png")
            embed.set_image(url="attachment://scramble.png")
            await channel.send(file=file, embed=embed)
        else:
            await channel.send(embed=embed)

async def do_room_create(target, user_id: int, user_name: str, channel_id: int, cube: str, rounds: int):
    if isinstance(target, discord.Interaction) and not target.response.is_done():
        await target.response.defer()

    existing_code, existing_room = get_user_room(user_id)
    if existing_room is not None:
        role = "hosting" if existing_room.host_id == user_id else "attending"
        await reply_text(target, f"You are already {role} Room `{existing_code}`. You cannot create a new room.")
        return

    if cube is None or rounds is None:
        await reply_text(target, "Usage: `create <puzzle> <rounds>` (e.g. `33 5`)\nPuzzles: `22`, `33`, `44`, `55`, `66`, `77`, `pyra`, `mega`, `skewb`, `sq1`, `clock`")
        return
    cube = cube.lower()
    if cube not in CUBE_MAP:
        await reply_text(target, "Invalid puzzle. Choose from: `22`, `33`, `44`, `55`, `66`, `77`, `pyra`, `mega`, `skewb`, `sq1`, `clock`.")
        return
    if rounds < 1 or rounds > 50:
        await reply_text(target, "Rounds must be between 1 and 50.")
        return

    cube_name, size, scramble_fn = CUBE_MAP[cube]
    code = await asyncio.to_thread(create_room, user_id, channel_id, cube, rounds, scramble_fn)
    room = rooms[code]
    room.add_player(user_id, user_name)

    embed = discord.Embed(
        title=f"Room Created — {cube_name}",
        description=f"**Room Code:** `{code}`\n**Rounds:** {rounds}\n**Host:** {user_name}\n\nPlayers can join with `!join {code}` or `/join {code}`\nHost starts with `!start` or `/start`",
        color=discord.Color.purple()
    )
    await reply_embed_file(target, embed)

async def do_room_join(target, user_id: int, user_name: str, code: str):
    if isinstance(target, discord.Interaction) and not target.response.is_done():
        await target.response.defer()

    if code is None:
        await reply_text(target, "Usage: `join <code>` (e.g. `123456`)")
        return
    if code not in rooms:
        await reply_text(target, "Room not found.")
        return

    existing_code, existing_room = get_user_room(user_id)
    if existing_room is not None:
        if existing_code == code:
            await reply_text(target, "You are already in this room.")
        else:
            role = "hosting" if existing_room.host_id == user_id else "attending"
            await reply_text(target, f"You are already {role} Room `{existing_code}`. You must leave it before joining another.")
        return

    room = rooms[code]
    if room.state != "waiting":
        await reply_text(target, "This room has already started.")
        return

    room.add_player(user_id, user_name)
    player_list = "\n".join(f"- {name}" for name in room.players.values())
    cube_name = CUBE_MAP[room.cube_type][0]

    embed = discord.Embed(
        title=f"{user_name} joined Room {code}",
        description=f"**{cube_name}** — {room.rounds} rounds\n\n**Players ({len(room.players)}):**\n{player_list}",
        color=discord.Color.purple()
    )
    await reply_embed_file(target, embed)

async def do_room_start(target, user_id: int, channel):
    if isinstance(target, discord.Interaction) and not target.response.is_done():
        await target.response.defer()

    target_room = None
    target_code = None
    for code, room in rooms.items():
        if room.host_id == user_id and room.channel_id == channel.id and room.state == "waiting":
            target_room = room
            target_code = code
            break

    if target_room is None:
        await reply_text(target, "You don't have a room to start in this channel.")
        return

    target_room.start()
    scramble = target_room.scrambles[0]
    cube_name, size, _ = CUBE_MAP[target_room.cube_type]
    player_list = ", ".join(target_room.players.values())
    embed = discord.Embed(
        title=f"Room {target_code} — Round 1/{target_room.rounds}",
        description=f"**Players:** {player_list}\n\n**Scramble:**\n```\n{scramble}\n```\n\nUse `/submit <time>` to enter your time.",
        color=discord.Color.green()
    )
    img_buffer = await asyncio.to_thread(render_preview, scramble, target_room.cube_type, size=size)
    if img_buffer:
        file = discord.File(img_buffer, filename="scramble.png")
        embed.set_image(url="attachment://scramble.png")
        await reply_embed_file(target, embed, file=file)
    else:
        await reply_embed_file(target, embed)

async def do_room_next(target, user_id: int, channel):
    target_room = None
    target_code = None
    for code, room in rooms.items():
        if room.host_id == user_id and room.channel_id == channel.id and room.state == "active":
            target_room = room
            target_code = code
            break

    if target_room is None:
        await reply_text(target, "You don't have an active room in this channel.")
        return

    if isinstance(target, discord.Interaction):
        await target.response.send_message("Advancing to next round...", ephemeral=True)
    await advance_room(channel, target_code, target_room)

async def do_room_leave(target, user_id: int, user_name: str, channel):
    if isinstance(target, discord.Interaction) and not target.response.is_done():
        await target.response.defer()

    target_code, target_room = get_user_room(user_id)
    if target_room is None:
        await reply_text(target, "You are not currently in any room.")
        return

    if target_room.host_id == user_id:
        del rooms[target_code]
        await reply_text(target, f"Room `{target_code}` has been disbanded by the host.")
    else:
        target_room.remove_player(user_id)
        await reply_text(target, f"{user_name} has left Room `{target_code}`.")
        if len(target_room.players) == 0:
            del rooms[target_code]
            if isinstance(target, discord.Interaction):
                await channel.send(f"No players left in Room `{target_code}`. Room has been disbanded.")
            else:
                await target.send(f"No players left in Room `{target_code}`. Room has been disbanded.")
        elif target_room.state == "active" and target_room.all_submitted():
            room_channel = bot.get_channel(target_room.channel_id) or channel
            await advance_room(room_channel, target_code, target_room)

async def do_room_list(target):
    if isinstance(target, discord.Interaction) and not target.response.is_done():
        await target.response.defer()

    if not rooms:
        await reply_text(target, "No active rooms right now.")
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
    await reply_embed_file(target, embed)

def build_help_embed():
    embed = discord.Embed(
        title="Speedcubing Bot Commands",
        description="All commands can be used with either `!` or `/` (slash command):",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="Scrambles",
        value=(
            "`!22` or `/22 [n]` — 2x2x2 Cube\n"
            "`!33` or `/33 [n]` — 3x3x3 Cube\n"
            "`!44` or `/44 [n]` — 4x4x4 Cube\n"
            "`!55` or `/55 [n]` — 5x5x5 Cube\n"
            "`!66` or `/66 [n]` — 6x6x6 Cube\n"
            "`!77` or `/77 [n]` — 7x7x7 Cube\n"
            "`!pyra` or `/pyra [n]` — Pyraminx\n"
            "`!mega` or `/mega [n]` — Megaminx\n"
            "`!skewb` or `/skewb [n]` — Skewb\n"
            "`!sq1` or `/sq1 [n]` — Square-1\n"
            "`!clock` or `/clock [n]` — Clock\n"
            "*(Optional [n] generates 1–12 scrambles. Single scrambles include image preview.)*"
        ),
        inline=False
    )
    embed.add_field(
        name="WCA Averages",
        value=(
            "`!ao5` or `/ao5 <5 times>` — Calculate Ao5\n"
            "`!ao12` or `/ao12 <12 times>` — Calculate Ao12\n"
            "`!ao` or `/ao <5 or 12 times>` — Auto-detect Ao5 / Ao12\n"
            "*(Supports DNF/DNS and mm:ss.xx format)*"
        ),
        inline=False
    )
    embed.add_field(
        name="Multiplayer Rooms",
        value=(
            "`!create` (or `/create`, `/room`) `<puzzle> <rounds>` — Create a room (e.g. `33 5`)\n"
            "`!join` or `/join <code>` — Join a room by 6-digit code\n"
            "`!start` or `/start` — Host starts the room\n"
            "`!next` or `/next` — Host skips to next round (missing times become DNF)\n"
            "`!leave` or `/leave` — Leave room (host leaves to disband)\n"
            "`!rooms` or `/rooms` — List all active rooms\n"
            "`/submit <time>` — Privately enter your solve time during rounds"
        ),
        inline=False
    )
    embed.add_field(
        name="Statistics",
        value=(
            "`!stat <puzzle>` or `/stat <puzzle>` (or `!stats`, `/stats`) — Display your personal PB single, global average, and solve count\n"
            "*(Puzzles: `22`, `33`, `44`, `55`, `66`, `77`, `pyra`, `mega`, `skewb`, `sq1`, `clock`)*"
        ),
        inline=False
    )
    embed.add_field(
        name="AI Assistant",
        value="Mention the bot (`@Speedcubing Bot <your question>`) to ask any speedcubing questions!",
        inline=False
    )
    embed.set_footer(text="Speedcubing Bot")
    return embed

async def do_help(target):
    if isinstance(target, discord.Interaction) and not target.response.is_done():
        await target.response.defer()
    embed = build_help_embed()
    await reply_embed_file(target, embed)

async def do_stat(target, user, puzzle: str):
    if isinstance(target, discord.Interaction) and not target.response.is_done():
        await target.response.defer()

    if not puzzle:
        await reply_text(target, "Please specify a puzzle name (e.g. `!stat 33` or `/stat 33`).\nPuzzles: `22`, `33`, `44`, `55`, `66`, `77`, `pyra`, `mega`, `skewb`, `sq1`, `clock`")
        return

    norm_puzzle = db_manager.normalize_puzzle(puzzle)
    if norm_puzzle not in db_manager.PUZZLE_NAMES:
        await reply_text(target, f"Unknown puzzle '{puzzle}'. Choose from: `22`, `33`, `44`, `55`, `66`, `77`, `pyra`, `mega`, `skewb`, `sq1`, `clock`.")
        return

    puzzle_name = db_manager.PUZZLE_NAMES[norm_puzzle]
    user_data = await db_manager.get_user_puzzle_stats(user.id, norm_puzzle)

    if not user_data or user_data["total_solves"] == 0:
        await reply_text(target, f"No solves recorded for **{user.display_name}** on **{puzzle_name}** yet. Complete a room round with `!create {norm_puzzle} <rounds>` to start tracking!")
        return

    pb_str = format_time(user_data['pb_single']) if user_data['pb_single'] is not None else "DNF"
    avg_str = format_time(user_data['global_average']) if user_data['global_average'] is not None else "N/A"
    dnf_count = user_data["total_solves"] - user_data["valid_solves"]

    embed = discord.Embed(
        title=f"{user.display_name}'s {puzzle_name} Statistics",
        color=discord.Color.blue()
    )
    embed.add_field(name="PB Single", value=f"**{pb_str}**", inline=True)
    embed.add_field(name="Global Average", value=f"**{avg_str}**", inline=True)
    embed.add_field(name="Total Solves", value=f"{user_data['total_solves']} ({user_data['valid_solves']} valid, {dnf_count} DNF)", inline=True)

    if user_data.get("pb_single_scramble"):
        embed.add_field(name="PB Scramble", value=f"```{user_data['pb_single_scramble']}```", inline=False)
    if user_data.get("pb_single_date"):
        embed.set_footer(text=f"PB achieved on {user_data['pb_single_date']}")

    await reply_embed_file(target, embed)

@bot.event
async def on_ready():
    for guild in bot.guilds:
        try:
            bot.tree.clear_commands(guild=guild)
            await bot.tree.sync(guild=guild)
        except Exception as e:
            print(f"Error clearing guild commands: {e}")
    try:
        await bot.tree.sync()
    except Exception as e:
        print(f"Error syncing global commands: {e}")
    print(f"Bot is ready as {bot.user.name}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if (bot.user in message.mentions or isinstance(message.channel, discord.DMChannel)) and not message.mention_everyone and not message.content.startswith("!"):
        prompt = message.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()

        if not prompt:
            await message.reply("How can I help you?")
            return

        load_dotenv(os.path.join(os.path.dirname(__file__), '.env'), override=True)
        key = os.getenv("GEMINI_API_KEY")
        if not key or not key.strip():
            return

        client = genai.Client(api_key=key.strip())
        async with message.channel.typing():
            try:
                response = await client.aio.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction="You are a helpful speedcubing discord assistant. Keep answers concise. Never generate your own scrambles or calculate WCA averages yourself—always prompt the user to use the bot's built-in commands and !help. Never hallucinate/mention any command that you don't know."
                    )
                )
                reply_text_content = response.text or ""
                for i in range(0, len(reply_text_content), 2000):
                    await message.reply(reply_text_content[i:i+2000])
            except Exception as e:
                print(f"Bot error: {e}")
                await message.reply(f"Error: `{e}`")
        return

    if message.content.lower() in ["hello", "hi", "sup"]:
        await message.channel.send(f"Hello {message.author.mention}!")

    await bot.process_commands(message)


@bot.command()
async def test(ctx):
    await ctx.send('this is a test')

@bot.command(name="22", aliases=["222"])
async def scramble_22(ctx, count: int = 1):
    await do_scramble(ctx, ctx.author.display_name, "2x2", 2, scrambler222.get_WCA_scramble, count)

@bot.command(name="33", aliases=["333"])
async def scramble_33(ctx, count: int = 1):
    await do_scramble(ctx, ctx.author.display_name, "3x3", 3, scrambler333.get_WCA_scramble, count)

@bot.command(name="44", aliases=["444"])
async def scramble_44(ctx, count: int = 1):
    await do_scramble(ctx, ctx.author.display_name, "4x4", 4, scrambler444.get_random_state_scramble, count)

@bot.command(name="55", aliases=["555"])
async def scramble_55(ctx, count: int = 1):
    await do_scramble(ctx, ctx.author.display_name, "5x5", 5, scrambler555.get_WCA_scramble, count)

@bot.command(name="66", aliases=["666"])
async def scramble_66(ctx, count: int = 1):
    await do_scramble(ctx, ctx.author.display_name, "6x6", 6, scrambler666.get_WCA_scramble, count)

@bot.command(name="77", aliases=["777"])
async def scramble_77(ctx, count: int = 1):
    await do_scramble(ctx, ctx.author.display_name, "7x7", 7, scrambler777.get_WCA_scramble, count)

@bot.command(name="pyra", aliases=["pyraminx"])
async def scramble_pyra(ctx, count: int = 1):
    await do_scramble(ctx, ctx.author.display_name, "Pyraminx", None, pyraminxScrambler.get_WCA_scramble, count)

@bot.command(name="mega", aliases=["megaminx"])
async def scramble_mega(ctx, count: int = 1):
    await do_scramble(ctx, ctx.author.display_name, "Megaminx", None, get_megaminx_scramble, count)

@bot.command(name="skewb")
async def scramble_skewb(ctx, count: int = 1):
    await do_scramble(ctx, ctx.author.display_name, "Skewb", None, skewbScrambler.get_WCA_scramble, count)

@bot.command(name="sq1", aliases=["square1"])
async def scramble_sq1(ctx, count: int = 1):
    await do_scramble(ctx, ctx.author.display_name, "Square-1", None, squareOneScrambler.get_WCA_scramble, count)

@bot.command(name="clock")
async def scramble_clock(ctx, count: int = 1):
    await do_scramble(ctx, ctx.author.display_name, "Clock", None, clockScrambler.get_WCA_scramble, count)

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

@bot.command(name="ao5")
async def cmd_ao5(ctx, *, times: str = ""):
    await do_ao_calc(ctx, ctx.author.display_name, times, 5)

@bot.command(name="ao12")
async def cmd_ao12(ctx, *, times: str = ""):
    await do_ao_calc(ctx, ctx.author.display_name, times, 12)

@bot.command(name="ao")
async def cmd_ao(ctx, *, times: str = ""):
    await do_ao_auto(ctx, ctx.author.display_name, times)

@bot.command(name="room", aliases=["create"])
async def cmd_room(ctx, cube: str = None, rounds: int = None):
    await do_room_create(ctx, ctx.author.id, ctx.author.display_name, ctx.channel.id, cube, rounds)

@bot.command(name="join")
async def cmd_join(ctx, code: str = None):
    await do_room_join(ctx, ctx.author.id, ctx.author.display_name, code)

@bot.command(name="start")
async def cmd_start(ctx):
    await do_room_start(ctx, ctx.author.id, ctx.channel)

@bot.command(name="next")
async def cmd_next(ctx):
    await do_room_next(ctx, ctx.author.id, ctx.channel)

@bot.command(name="leave")
async def cmd_leave(ctx):
    await do_room_leave(ctx, ctx.author.id, ctx.author.display_name, ctx.channel)

@bot.command(name="rooms")
async def cmd_rooms(ctx):
    await do_room_list(ctx)

@bot.command(name="help")
async def cmd_help(ctx):
    await do_help(ctx)

@bot.command(name="stat", aliases=["stats"])
async def cmd_stat(ctx, puzzle: str = None):
    await do_stat(ctx, ctx.author, puzzle)


@bot.tree.command(name="submit", description="Submit your solve time for the current round")
@app_commands.describe(time="Your solve time (e.g. 12.34, 1:05.23, DNF, DNS)")
async def slash_submit(interaction: discord.Interaction, time: str):
    code, room = find_player_room(interaction.channel_id, interaction.user.id)
    if not room:
        code, room = get_user_room(interaction.user.id)

    if not room or room.state != "active":
        await interaction.response.send_message("You are not currently in an active round.", ephemeral=True)
        return

    if interaction.user.id not in room.players:
        await interaction.response.send_message("You are not a participant in this room.", ephemeral=True)
        return

    if room.times[interaction.user.id][room.current_round] is not None:
        await interaction.response.send_message("You already submitted a time for this round.", ephemeral=True)
        return

    ok, result = room.submit_time(interaction.user.id, time)
    if not ok:
        await interaction.response.send_message(result, ephemeral=True)
        return

    await interaction.response.send_message(f"Your time has been recorded: **{result}**", ephemeral=True)

    if room.all_submitted():
        channel = bot.get_channel(room.channel_id) or interaction.channel
        await advance_room(channel, code, room)

@bot.tree.command(name="22", description="Generate 2x2x2 scramble(s)")
@app_commands.describe(count="Number of scrambles (1-12, default 1)")
async def slash_22(interaction: discord.Interaction, count: int = 1):
    await do_scramble(interaction, interaction.user.display_name, "2x2", 2, scrambler222.get_WCA_scramble, count)

@bot.tree.command(name="33", description="Generate 3x3x3 scramble(s)")
@app_commands.describe(count="Number of scrambles (1-12, default 1)")
async def slash_33(interaction: discord.Interaction, count: int = 1):
    await do_scramble(interaction, interaction.user.display_name, "3x3", 3, scrambler333.get_WCA_scramble, count)

@bot.tree.command(name="44", description="Generate 4x4x4 scramble(s)")
@app_commands.describe(count="Number of scrambles (1-12, default 1)")
async def slash_44(interaction: discord.Interaction, count: int = 1):
    await do_scramble(interaction, interaction.user.display_name, "4x4", 4, scrambler444.get_random_state_scramble, count)

@bot.tree.command(name="55", description="Generate 5x5x5 scramble(s)")
@app_commands.describe(count="Number of scrambles (1-12, default 1)")
async def slash_55(interaction: discord.Interaction, count: int = 1):
    await do_scramble(interaction, interaction.user.display_name, "5x5", 5, scrambler555.get_WCA_scramble, count)

@bot.tree.command(name="66", description="Generate 6x6x6 scramble(s)")
@app_commands.describe(count="Number of scrambles (1-12, default 1)")
async def slash_66(interaction: discord.Interaction, count: int = 1):
    await do_scramble(interaction, interaction.user.display_name, "6x6", 6, scrambler666.get_WCA_scramble, count)

@bot.tree.command(name="77", description="Generate 7x7x7 scramble(s)")
@app_commands.describe(count="Number of scrambles (1-12, default 1)")
async def slash_77(interaction: discord.Interaction, count: int = 1):
    await do_scramble(interaction, interaction.user.display_name, "7x7", 7, scrambler777.get_WCA_scramble, count)

@bot.tree.command(name="pyra", description="Generate Pyraminx scramble(s)")
@app_commands.describe(count="Number of scrambles (1-12, default 1)")
async def slash_pyra(interaction: discord.Interaction, count: int = 1):
    await do_scramble(interaction, interaction.user.display_name, "Pyraminx", None, pyraminxScrambler.get_WCA_scramble, count)

@bot.tree.command(name="mega", description="Generate Megaminx scramble(s)")
@app_commands.describe(count="Number of scrambles (1-12, default 1)")
async def slash_mega(interaction: discord.Interaction, count: int = 1):
    await do_scramble(interaction, interaction.user.display_name, "Megaminx", None, get_megaminx_scramble, count)

@bot.tree.command(name="skewb", description="Generate Skewb scramble(s)")
@app_commands.describe(count="Number of scrambles (1-12, default 1)")
async def slash_skewb(interaction: discord.Interaction, count: int = 1):
    await do_scramble(interaction, interaction.user.display_name, "Skewb", None, skewbScrambler.get_WCA_scramble, count)

@bot.tree.command(name="sq1", description="Generate Square-1 scramble(s)")
@app_commands.describe(count="Number of scrambles (1-12, default 1)")
async def slash_sq1(interaction: discord.Interaction, count: int = 1):
    await do_scramble(interaction, interaction.user.display_name, "Square-1", None, squareOneScrambler.get_WCA_scramble, count)

@bot.tree.command(name="clock", description="Generate Clock scramble(s)")
@app_commands.describe(count="Number of scrambles (1-12, default 1)")
async def slash_clock(interaction: discord.Interaction, count: int = 1):
    await do_scramble(interaction, interaction.user.display_name, "Clock", None, clockScrambler.get_WCA_scramble, count)

@bot.tree.command(name="ao5", description="Calculate Average of 5 (Ao5)")
@app_commands.describe(times="5 solve times separated by spaces (e.g. 12.34 11.50 9.80 16.20 DNF)")
async def slash_ao5(interaction: discord.Interaction, times: str):
    await do_ao_calc(interaction, interaction.user.display_name, times, 5)

@bot.tree.command(name="ao12", description="Calculate Average of 12 (Ao12)")
@app_commands.describe(times="12 solve times separated by spaces")
async def slash_ao12(interaction: discord.Interaction, times: str):
    await do_ao_calc(interaction, interaction.user.display_name, times, 12)

@bot.tree.command(name="ao", description="Calculate Average of 5 or 12 (auto-detected)")
@app_commands.describe(times="5 or 12 solve times separated by spaces")
async def slash_ao(interaction: discord.Interaction, times: str):
    await do_ao_auto(interaction, interaction.user.display_name, times)

@bot.tree.command(name="create", description="Create a multiplayer speedcubing room")
@app_commands.describe(puzzle="Puzzle to compete on", rounds="Number of rounds (1-50)")
@app_commands.choices(puzzle=PUZZLE_CHOICES)
async def slash_create(interaction: discord.Interaction, puzzle: app_commands.Choice[str], rounds: int):
    await do_room_create(interaction, interaction.user.id, interaction.user.display_name, interaction.channel_id, puzzle.value, rounds)

@bot.tree.command(name="room", description="Create a multiplayer speedcubing room (alias for /create)")
@app_commands.describe(puzzle="Puzzle to compete on", rounds="Number of rounds (1-50)")
@app_commands.choices(puzzle=PUZZLE_CHOICES)
async def slash_room(interaction: discord.Interaction, puzzle: app_commands.Choice[str], rounds: int):
    await do_room_create(interaction, interaction.user.id, interaction.user.display_name, interaction.channel_id, puzzle.value, rounds)

@bot.tree.command(name="join", description="Join an active multiplayer room")
@app_commands.describe(code="6-digit room code")
async def slash_join(interaction: discord.Interaction, code: str):
    await do_room_join(interaction, interaction.user.id, interaction.user.display_name, code)

@bot.tree.command(name="start", description="Start the room (Host only)")
async def slash_start(interaction: discord.Interaction):
    await do_room_start(interaction, interaction.user.id, interaction.channel)

@bot.tree.command(name="next", description="Advance to next round / skip unfinished times (Host only)")
async def slash_next(interaction: discord.Interaction):
    await do_room_next(interaction, interaction.user.id, interaction.channel)

@bot.tree.command(name="leave", description="Leave current room (disbands room if host leaves)")
async def slash_leave(interaction: discord.Interaction):
    await do_room_leave(interaction, interaction.user.id, interaction.user.display_name, interaction.channel)

@bot.tree.command(name="rooms", description="List all active multiplayer rooms")
async def slash_rooms(interaction: discord.Interaction):
    await do_room_list(interaction)

@bot.tree.command(name="help", description="Show all available speedcubing bot commands")
async def slash_help(interaction: discord.Interaction):
    await do_help(interaction)

@bot.tree.command(name="stat", description="Display personal PB, global average, and solve count for a puzzle")
@app_commands.describe(puzzle="Puzzle to display statistics for")
@app_commands.choices(puzzle=PUZZLE_CHOICES)
async def slash_stat(interaction: discord.Interaction, puzzle: app_commands.Choice[str]):
    await do_stat(interaction, interaction.user, puzzle.value)

@bot.tree.command(name="stats", description="Display personal PB, global average, and solve count (alias for /stat)")
@app_commands.describe(puzzle="Puzzle to display statistics for")
@app_commands.choices(puzzle=PUZZLE_CHOICES)
async def slash_stats(interaction: discord.Interaction, puzzle: app_commands.Choice[str]):
    await do_stat(interaction, interaction.user, puzzle.value)

bot.run(token, log_handler=handler, log_level=logging.DEBUG)
