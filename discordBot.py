import sys
sys.path.append('/var/scripts/local-llm')  # or wherever chat.py lives

import json
import asyncio
import discord
import ollama
from chat import chat

with open("config.json") as f:
    config = json.load(f)

def split_message(text: str, limit: int = 2000) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks


intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id: {bot.user.id})")

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return
    if not isinstance(message.channel, discord.DMChannel):
        return
    if not message.content.strip():
        return

    with open("/var/scripts/assistant/daily_summary.md") as file:
        daily_context = file.read()

    history = []
    async for msg in message.channel.history(limit=10, oldest_first=False):
        if msg.id == message.id:
            continue
        if msg.author == bot.user:
            history.append({"role": "assistant", "content": msg.content})
        else:
            history.append({"role": "user", "content": msg.content})

    messages = list(reversed(history))
    messages.append({"role": "user", "content": message.content})

    async with message.channel.typing():
        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(None, chat, str(message.author.id), messages, None, daily_context)

    for chunk in split_message(reply):
        await message.channel.send(chunk)

bot.run(config["discord_token"])
