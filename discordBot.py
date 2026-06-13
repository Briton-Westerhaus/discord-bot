import sys
import json
import asyncio
import discord

sys.path.append('/var/scripts/local-llm')
from chat import chat

sys.path.append('/var/scripts/assistant')
from gmail import search_emails_by_subject, get_email_content

GMAIL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "gmail_search",
            "description": "Search Gmail for emails by subject, sender, or keywords. Returns a list of matching emails with metadata including message IDs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "The subject or keywords to search for"}
                },
                "required": ["subject"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_email_content",
            "description": "Read the full content of a specific email by message ID. Use after gmail_search to read an email in detail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "The message ID from gmail_search results"}
                },
                "required": ["message_id"]
            }
        }
    }
]

GMAIL_TOOL_FUNCTIONS = {
    "gmail_search": search_emails_by_subject,
    "get_email_content": get_email_content
}

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
        reply = await loop.run_in_executor(None, chat, str(message.author.id), messages, None, daily_context, additional_tools=GMAIL_TOOLS, additional_tool_functions=GMAIL_TOOL_FUNCTIONS) #TODO: Filter tools for user id

    for chunk in split_message(reply):
        await message.channel.send(chunk)

bot.run(config["discord_token"])
