import json
import os
import subprocess
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError(
        "OPENAI_API_KEY is not set. Add it to your environment or to a .env file."
    )

client = OpenAI(api_key=api_key)

print("=== Uruchamianie Agenta OpenAI + Entire ===")

def run_powershell(command: str) -> str:
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            check=False
        )
        return res.stdout if res.returncode == 0 else f"Error: {res.stderr}"
    except Exception as err:
        return str(err)

tools = [
    {
        "type": "function",
        "function": {
            "name": "run_powershell",
            "description": "Wykonuje polecenia git lub systemowe.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Polecenie do uruchomienia (np. 'git status')"
                    }
                },
                "required": ["command"]
            }
        }
    }
]

def run_agent(task_prompt: str):
    system_prompt = (
        "Jestes asystentem programistycznym w repozytorium Git z Entire.io. "
        "Wykonuj polecenia za pomoca powloki powershell i analizuj stan projektu."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task_prompt}
    ]

    print(f"Zadanie: {task_prompt}\n" + "-" * 50)

    for step in range(5):
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            print(f"\nOdpowiedz agenta:\n{msg.content}")
            break

        for call in msg.tool_calls:
            args = json.loads(call.function.arguments)
            cmd = args.get("command")
            print(f"-> [Krok {step + 1}] Uruchamiam: {cmd}")

            result = run_powershell(cmd)

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": result
            })

if __name__ == "__main__":
    run_agent("Stwórz plik README.md z któtkim opisem projektu 'Slavs and Ottoman'")
