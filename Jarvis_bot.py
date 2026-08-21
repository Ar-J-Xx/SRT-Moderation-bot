import os
import re
import json
import discord
from discord.ext import commands
from dotenv import load_dotenv
import aiohttp
import datetime

# ---------------- TOKEN & CONFIG ----------------
load_dotenv()
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise SystemExit(
        "ERROR: No TOKEN found. Make sure a .env file exists in this exact "
        f"folder ({os.path.dirname(os.path.abspath(__file__))}) with a line "
        "like: TOKEN=your_jarvis_bot_token_here"
    )

OWNER_ID_RAW = os.getenv("OWNER_ID", "")
if not OWNER_ID_RAW.strip().isdigit():
    raise SystemExit(
        "ERROR: OWNER_ID must be set in .env to your Discord user ID (numbers only)."
    )
OWNER_ID = int(OWNER_ID_RAW.strip())

# URL of the moderation bot's status/API server, so Jarvis can fetch mod
# history over the web instead of needing direct file access. Once the
# moderation bot is on Replit, this is its webview URL, e.g.:
# MODERATION_API_URL=https://srt-moderator.yourusername.repl.co
MODERATION_API_URL = os.getenv("MODERATION_API_URL", "http://localhost:8080")

_srt_bot_ids_raw = os.getenv("SRT_BOT_IDS", "")
SRT_BOT_IDS = [int(x.strip()) for x in _srt_bot_ids_raw.split(",") if x.strip().isdigit()]

# ---------------- 🧠 MEMORY SYSTEM ----------------
MEMORY_FILE = "jarvis_memory.json"

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)

def save_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

memory = load_memory()

# ---------------- INTENTS ----------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!!jarvis-unused!!", intents=intents)

def is_owner(message: discord.Message) -> bool:
    return message.author.id == OWNER_ID

# ---------------- EVENTS ----------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print(f"Jarvis is online — locked to owner ID {OWNER_ID}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if not is_owner(message):
        return

    content = message.content.strip()
    lowered = content.lower()

    # ---- Protocol: test all bots ----
    if lowered == "protocol test all bots":
        await handle_test_all_bots(message)
        return

    # ---- 🔥 BRICK JARVIS LINE ----
    if re.search(r"jarvis.*i('?m| am) brick", lowered):
        await message.channel.send("Yes sir, you are indeed Brick.")
        return

    # ---- 🧠 SEEING THIS RIGHT LINE ----
    if re.search(r"jarvis.*i('?m| am) seeing this right", lowered):
        await message.channel.send("Yes sir, you are seeing this right.")
        return

    # ---- 📡 TELL THIS INDIVIDUAL ----
    if re.search(r"jarvis,?\s+tell this individual\s+", lowered):
        msg = re.split(r"jarvis,?\s+tell this individual\s+", content, flags=re.IGNORECASE)[1]
        await message.channel.send(f"📡 Transmission to individual: {msg}")
        return

    # ---- 🧠 WHAT CAN JARVIS DO ----
    if re.search(r"jarvis\s+tell me what you can do", lowered):
        await message.channel.send(
            "🧠 I am Jarvis.\n\n"
            "I can:\n"
            "• Run system protocols\n"
            "• Test all SRT bots\n"
            "• Pull up user files\n"
            "• Send transmissions\n"
            "• Remember identities\n"
            "• Broadcast messages\n"
            "• Monitor server status\n"
            "• Use shortcut commands\n\n"
            "Awaiting instruction, sir."
        )
        return

    # ---- 🧠 MEMORY: remember ----
    if re.search(r"jarvis remember (.+)", lowered):
        value = re.split(r"jarvis remember ", content, flags=re.IGNORECASE)[1]
        memory[str(message.author.id)] = value
        save_memory(memory)
        await message.channel.send(f"🧠 Memory saved: {value}")
        return

    # ---- 🧠 MEMORY: who am i ----
    if lowered == "jarvis who am i":
        value = memory.get(str(message.author.id), "No memory found.")
        await message.channel.send(f"🧠 You are: {value}")
        return

    # ---- 📡 BROADCAST ----
    if re.search(r"jarvis broadcast ", lowered):
        msg = re.split(r"jarvis broadcast ", content, flags=re.IGNORECASE)[1]
        for channel in message.guild.text_channels:
            try:
                await channel.send(f"📡 Broadcast: {msg}")
            except:
                pass
        return

    # ---- 👁️ SERVER STATUS ----
    if lowered == "jarvis status report":
        online = sum(1 for m in message.guild.members if str(m.status) == "online")
        total = len(message.guild.members)

        await message.channel.send(
            f"👁️ Server Status:\nOnline Users: {online}\nTotal Members: {total}"
        )
        return

    # ---- ⚡ ALIASES ----
    if lowered == "jp":
        await message.channel.send("Pong.")
        return

    if lowered == "jt":
        await handle_test_all_bots(message)
        return

    # ---- 📊 DASHBOARD ----
    if lowered == "jarvis dashboard":
        await message.channel.send(
            "🧠 JARVIS CONTROL PANEL\n\n"
            "Commands:\n"
            "- protocol test all bots\n"
            "- jarvis pull up files about @user\n"
            "- jarvis when did @user join\n"
            "- jarvis remember <text>\n"
            "- jarvis who am i\n"
            "- jarvis broadcast <msg>\n"
            "- jarvis status report\n"
            "- jt / jp\n"
        )
        return

    # ---- FILES SYSTEM ----
    match = re.match(r"^jarvis,?\s+pull up (the )?files? (on|about|for)\s+", lowered)
    if match and message.mentions:
        await handle_pull_files(message, message.mentions[0])
        return

    # ---- QUICK JOIN DATE LOOKUP ----
    join_match = re.match(r"^jarvis,?\s+when did\s+", lowered)
    if join_match and message.mentions:
        await handle_join_dates(message, message.mentions[0])
        return

    await bot.process_commands(message)

# ---------------- PROTOCOL HANDLERS ----------------

async def handle_test_all_bots(message: discord.Message):
    if not SRT_BOT_IDS:
        await message.channel.send("⚠️ No bots configured.")
        return

    guild = message.guild
    if guild is None:
        return

    lines = []
    for bot_id in SRT_BOT_IDS:
        member = guild.get_member(bot_id)
        if not member:
            continue

        lines.append(f"{member.display_name} — {member.status}")

    await message.channel.send("\n".join(lines))

async def fetch_mod_history(user_id: int):
    """Fetches this user's moderation history from the moderation bot's API.
    Returns (mod_log_list, error_message). error_message is None on success."""
    url = f"{MODERATION_API_URL.rstrip('/')}/modlog/{user_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return [], f"Moderation bot API returned status {resp.status}"
                data = await resp.json()
                return data.get("mod_log", []), None
    except (aiohttp.ClientError, Exception) as e:
        return [], f"Couldn't reach moderation bot API: {e}"

async def handle_pull_files(message: discord.Message, target: discord.Member):
    guild = message.guild
    if guild is None:
        await message.channel.send("❌ This only works inside a server, not DMs.")
        return

    account_created = target.created_at.strftime("%B %d, %Y")
    server_joined = target.joined_at.strftime("%B %d, %Y") if target.joined_at else "Unknown"

    mod_history_raw, api_error = await fetch_mod_history(target.id)
    mod_history = [(e["action"], e["reason"], e["date"]) for e in mod_history_raw]

    embed = discord.Embed(title=f"📁 File: {target.display_name}", color=0x3498db)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Discord account created", value=account_created, inline=True)
    embed.add_field(name="Joined this server", value=server_joined, inline=True)
    embed.add_field(
        name="Current roles",
        value=", ".join(r.name for r in target.roles if r.name != "@everyone") or "None",
        inline=False,
    )

    if api_error:
        embed.add_field(name="Moderation history", value=f"⚠️ Couldn't read history: {api_error}", inline=False)
    elif not mod_history:
        embed.add_field(name="Moderation history", value="✅ Clean record — nothing on file.", inline=False)
    else:
        lines = []
        for action, reason, date in mod_history[:10]:
            date_short = date.split(".")[0] if date else "Unknown time"
            lines.append(f"• **{action.upper()}** — {reason} _( {date_short} )_")
        if len(mod_history) > 10:
            lines.append(f"...and {len(mod_history) - 10} more action(s).")
        embed.add_field(
            name=f"Moderation history ({len(mod_history)} action(s))",
            value="\n".join(lines),
            inline=False,
        )

    await message.channel.send(embed=embed)

async def handle_join_dates(message: discord.Message, target: discord.Member):
    account_created = target.created_at.strftime("%B %d, %Y at %I:%M %p UTC")
    server_joined = (
        target.joined_at.strftime("%B %d, %Y at %I:%M %p UTC")
        if target.joined_at else "Unknown"
    )
    await message.channel.send(
        f"📅 **{target.display_name}**\n"
        f"• Discord account created: {account_created}\n"
        f"• Joined this server: {server_joined}"
    )

# ---------------- RUN BOT ----------------
bot.run(TOKEN)