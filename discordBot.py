import sys
import os
import json
import asyncio
import discord

sys.path.append('/var/scripts/local-llm')
from chat import chat_with_artifacts
from generate_image import generate_image

sys.path.append('/var/scripts/assistant')
from gmail import search_emails_by_subject, get_email_content
from gkeep import list_notes, get_note, create_note, update_note, add_list_item, check_list_item, add_label, remove_label, delete_note

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

IMAGE_GENERATION_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_image",
        "description": "Generate an image based on a text prompt using Stable Diffusion. The image will be automatically sent as an attachment. Do not include the file path or markdown image syntax in your response.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The text prompt to generate the image from"}
            },
            "required": ["prompt"]
        }
    }
}

IMAGE_GENERATION_TOOL_FUNCTIONS = {
    "generate_image": generate_image
}

GKEEP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_notes",
            "description": "List Google Keep notes, optionally filtered by search query or label.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Free-text search string to filter notes by title or body."},
                    "label": {"type": "string", "description": "Return only notes with this label name."},
                    "archived": {"type": "boolean", "description": "Include archived notes. Default false."},
                    "trashed": {"type": "boolean", "description": "Include trashed notes. Default false."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_note",
            "description": "Retrieve a single Google Keep note by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "string", "description": "The unique ID of the note."},
                },
                "required": ["note_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_note",
            "description": "Create a new Google Keep note or checklist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Note title."},
                    "text": {"type": "string", "description": "Note body text (for regular notes)."},
                    "list_items": {"type": "array", "items": {"type": "string"}, "description": "If provided, creates a checklist with these items."},
                    "labels": {"type": "array", "items": {"type": "string"}, "description": "Label names to attach."},
                    "pinned": {"type": "boolean", "description": "Whether to pin the note."},
                    "color": {"type": "string", "description": "Color name: Red, Blue, Yellow, Green, Teal, Gray, or White."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_note",
            "description": "Update the title, text, pin state, archive state, or color of a Google Keep note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "string", "description": "The unique ID of the note to update."},
                    "title": {"type": "string", "description": "New title."},
                    "text": {"type": "string", "description": "New body text (regular notes only)."},
                    "pinned": {"type": "boolean", "description": "Set pin state."},
                    "archived": {"type": "boolean", "description": "Set archived state."},
                    "color": {"type": "string", "description": "New color name."},
                },
                "required": ["note_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_list_item",
            "description": "Add an item to an existing Google Keep checklist note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "string", "description": "The unique ID of the list note."},
                    "text": {"type": "string", "description": "Text content of the new list item."},
                    "checked": {"type": "boolean", "description": "Whether the item starts checked. Default false."},
                },
                "required": ["note_id", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_list_item",
            "description": "Check or uncheck a specific item in a Google Keep checklist note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "string", "description": "The unique ID of the list note."},
                    "item_id": {"type": "string", "description": "The unique ID of the list item."},
                    "checked": {"type": "boolean", "description": "True to check, False to uncheck. Default true."},
                },
                "required": ["note_id", "item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_label",
            "description": "Add a label to a Google Keep note, creating the label if it doesn't exist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "string", "description": "The unique ID of the note."},
                    "label_name": {"type": "string", "description": "Name of the label to add."},
                },
                "required": ["note_id", "label_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_label",
            "description": "Remove a label from a Google Keep note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "string", "description": "The unique ID of the note."},
                    "label_name": {"type": "string", "description": "Name of the label to remove."},
                },
                "required": ["note_id", "label_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_note",
            "description": "Move a Google Keep note to trash.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "string", "description": "The unique ID of the note to trash."},
                },
                "required": ["note_id"],
            },
        },
    },
]

GKEEP_TOOL_FUNCTIONS = {
    "list_notes": list_notes,
    "get_note": get_note,
    "create_note": create_note,
    "update_note": update_note,
    "add_list_item": add_list_item,
    "check_list_item": check_list_item,
    "add_label": add_label,
    "remove_label": remove_label,
    "delete_note": delete_note,
}


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(SCRIPT_DIR, "config.json")) as f:
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
        result = await loop.run_in_executor(None, chat_with_artifacts, str(message.author.id), messages, None, daily_context, GMAIL_TOOLS + [IMAGE_GENERATION_TOOL] + GKEEP_TOOLS, {**GMAIL_TOOL_FUNCTIONS, **IMAGE_GENERATION_TOOL_FUNCTIONS, **GKEEP_TOOL_FUNCTIONS}) #TODO: Filter tools for user id

    reply = result.get("reply", "")
    for artifact in result.get("artifacts", []):
        if artifact["type"] == "image":
            await message.channel.send(file=discord.File(artifact["path"]))

    for chunk in split_message(reply):
        await message.channel.send(chunk)

bot.run(config["discord_token"])
