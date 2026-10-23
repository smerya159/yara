

from pathlib import Path
import json
import os
import urllib.request

# Project files
BASE_DIR = Path(__file__).parent

PROMPT_FILE = BASE_DIR / "yara's_prompt.txt"
LORE_FILE = BASE_DIR / "relationship_lore.txt"
MEMORY_FILE = BASE_DIR / "memory.json"
HISTORY_FILE = BASE_DIR / "conversation_history.json"

# Ollama configuration
API_URL = "http://localhost:11434/api/chat"
MODEL = "dolphin3"

# Keep the latest 10 exchanges (20 messages)
MAX_HISTORY_MESSAGES = 20


def load_text(path):
    """Load a UTF-8 text file."""
    return path.read_text(encoding="utf-8").strip()


def load_memory():
    """Load long-term memory, creating an empty file if needed."""
    default_memory = {
        "facts": [],
        "preferences": [],
        "ongoing_projects": [],
        "commitments": []
    }

    if not MEMORY_FILE.exists():
        save_json(MEMORY_FILE, default_memory)
        return default_memory

    try:
        with MEMORY_FILE.open("r", encoding="utf-8") as file:
            memory = json.load(file)

        # Validate the expected structure.
        if not isinstance(memory, dict):
            raise ValueError("Memory must be a JSON object.")

        for category in default_memory:
            if not isinstance(memory.get(category), list):
                raise ValueError(
                    f"Memory category '{category}' must be a list."
                )

        return memory

    except (json.JSONDecodeError, ValueError) as error:
        raise RuntimeError(
            f"Could not load {MEMORY_FILE.name}: {error}. "
            "Fix the file before starting Yara."
        ) from error


def load_history():
    """Restore recent conversation history."""
    if not HISTORY_FILE.exists():
        return []

    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as file:
            history = json.load(file)

        if not isinstance(history, list):
            raise ValueError("Conversation history must be a list.")

        # Keep only valid user/assistant messages.
        history = [
            message for message in history
            if isinstance(message, dict)
            and message.get("role") in ("user", "assistant")
            and isinstance(message.get("content"), str)
        ]

        # Avoid restoring an assistant reply without its user message.
        history = history[-MAX_HISTORY_MESSAGES:]

        if history and history[0]["role"] == "assistant":
            history = history[1:]

        return history

    except (json.JSONDecodeError, ValueError) as error:
        raise RuntimeError(
            f"Could not load {HISTORY_FILE.name}: {error}. "
            "Restore a valid backup or fix the file before starting Yara."
        ) from error


def save_json(path, data):
    """Write JSON through a temporary file to reduce corruption risk."""
    temp_path = path.with_suffix(path.suffix + ".tmp")

    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")

    os.replace(temp_path, path)


def build_memory_text(memory):
    """Convert structured memory into readable context for Yara."""
    sections = []

    labels = {
        "facts": "Confirmed facts",
        "preferences": "Preferences",
        "ongoing_projects": "Ongoing projects",
        "commitments": "Commitments"
    }

    for category, label in labels.items():
        entries = memory.get(category, [])

        if entries:
            lines = "\n".join(f"- {entry}" for entry in entries)
            sections.append(f"{label}:\n{lines}")

    if not sections:
        return "No long-term memories have been recorded yet."

    return "\n\n".join(sections)


def build_system_prompt():
    """Combine personality, relationship lore, and long-term memory."""
    personality = load_text(PROMPT_FILE)
    lore = load_text(LORE_FILE)
    memory = load_memory()

    return (
        f"{personality}\n\n"
        f"--- RELATIONSHIP LORE ---\n{lore}\n\n"
        f"--- LONG-TERM MEMORY ---\n"
        f"{build_memory_text(memory)}\n\n"
        "Memory accuracy rules:\n"
        "- Treat stored facts as context, not permission to invent details.\n"
        "- Distinguish established lore from specific remembered events.\n"
        "- Do not claim to remember events that are not available in context.\n"
        "- Accept corrections and do not repeat a corrected assumption."
    )


# Load context and restore recent conversation
SYSTEM_PROMPT = build_system_prompt()
messages = load_history()

print("Yara's personality, lore, and memory loaded.")
print(f"Restored {len(messages)} recent messages.")
print("Connecting to Dolphin...")
print("Type /quit to leave.\n")


while True:
    try:
        user_input = input("Gi: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nYara: Until next time.")
        break

    if user_input.lower() == "/quit":
        print("Yara: Until next time.")
        break

    if not user_input:
        continue

    messages.append({
        "role": "user",
        "content": user_input
    })

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *messages
        ],
        "stream": False
    }

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        print("\nYara: ", end="", flush=True)

        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))

        if "error" in result:
            raise RuntimeError(result["error"])

        reply = result.get("message", {}).get("content", "")

        if not reply:
            raise RuntimeError("Ollama returned an empty response.")

        print(reply)
        print()

        messages.append({
            "role": "assistant",
            "content": reply
        })

        # Keep complete recent exchanges.
        messages = messages[-MAX_HISTORY_MESSAGES:]

        # Ensure history begins with a user message.
        if messages and messages[0]["role"] == "assistant":
            messages = messages[1:]

        # Save after each successful exchange.
        save_json(HISTORY_FILE, messages)

    except Exception as error:
        print(f"\nConnection error: {error}\n")

        # Remove the unanswered user message.
        if messages and messages[-1]["role"] == "user":
            messages.pop()
