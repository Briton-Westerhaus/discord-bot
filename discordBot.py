import json
import asyncio
import time
import requests
import discord
import ollama
from collections import deque

with open("config.json") as f:
    config = json.load(f)

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current date and time. Use this proactively whenever the current date or time is relevant to answering accurately — including questions about upcoming events, whether something has happened yet, how recent something is, scheduling, or anything time-sensitive.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information. Use this tool liberally and proactively — whenever answering a question that involves current events, recent releases, prices, people, places, sports, weather, news, events, or anything where information may have changed or where you are not completely certain of the answer. When in doubt, search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"}
                },
                "required": ["query"]
            }
        }
    }
]

def web_search(query):
    headers = {"X-Subscription-Token": config["brave_search_api_key"]}
    response = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": 3},
        headers=headers
    )
    results = response.json().get("web", {}).get("results", [])
    return "\n".join(f"{r['title']}: {r['description']}" for r in results)

tool_functions = {
    "get_current_time": lambda: time.ctime(),
    "web_search": web_search,
}

def llm_chat(user_input: str) -> str:
    messages = [{"role": "user", "content": user_input}]
    with open("/var/scripts/assistant/daily_summary.md") as file:
        daily_context = file.read()
    if daily_context:
        messages.insert(0, {"role": "system", "content": f"Here is some relevant context for today's summary:\n\n{daily_context}"})

    if config.get("system_prompt"):
        messages.insert(0, {"role": "system", "content": config["system_prompt"]})

    response = ollama.chat(model=config["model"], messages=messages, tools=tools, options={"num_ctx": 32768})

    while response["message"].get("tool_calls"):
        messages.append(response["message"])
        for tool_call in response["message"]["tool_calls"]:
            name = tool_call.function.name
            args = tool_call.function.arguments
            result = tool_functions[name](**args)
            messages.append({"role": "tool", "name": name, "content": str(result)})
        response = ollama.chat(model=config["model"], messages=messages, tools=tools, options={"num_ctx": 32768})

    reply = response["message"]["content"]
    return reply

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

    async with message.channel.typing():
        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(None, llm_chat, message.content)

    for chunk in split_message(reply):
        await message.channel.send(chunk)

bot.run(config["discord_token"])
