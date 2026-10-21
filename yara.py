
from pathlib import Path
import json
import urllib.request

# Project files
BASE_DIR = Path(__file__).parent
PROMPT_FILE = BASE_DIR / "yara's_prompt.txt"

# Ollama configuration
API_URL = "http://localhost:11434/api/chat"
MODEL = "dolphin3"

# Load Yara's personality
SYSTEM_PROMPT = PROMPT_FILE.read_text(encoding="utf-8")

# Start a conversation
print("Yara's personality loaded.")
print("Connecting to Dolphin...")
print("Type /quit to leave.\n")

messages = []

while True:
    user_input = input("Gi: ").strip()

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
        reply = ""

        print("\nYara: ", end="", flush=True)

        with urllib.request.urlopen(request, timeout=300) as response:
            for line in response:
                if not line.strip():
                    continue

                chunk = json.loads(line.decode("utf-8"))

                if "error" in chunk:
                    raise RuntimeError(chunk["error"])

                token = chunk.get("message", {}).get("content", "")
                print(token, end="", flush=True)
                reply += token

        print("\n")

        messages.append({
            "role": "assistant",
            "content": reply
        })

    except Exception as error:
        print(f"\nConnection error: {error}\n")
        messages.pop()
