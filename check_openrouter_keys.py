# check_openrouter_keys.py
import json
import os
import urllib.request
import urllib.error

URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openrouter/free"  # change if needed

def check_key(name: str, key: str) -> None:
    if not key:
        print(f"{name}: MISSING")
        return

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 5,
        "temperature": 0,
    }

    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "OpenRouter Key Check",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            text = body["choices"][0]["message"]["content"]
            print(f"{name}: WORKING (status={resp.status}, reply={text!r})")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")
        if e.code == 401:
            print(f"{name}: INVALID KEY (401)")
        elif e.code == 429:
            print(f"{name}: RATE LIMITED (429)")
        else:
            print(f"{name}: HTTP {e.code} -> {err[:300]}")
    except Exception as e:
        print(f"{name}: ERROR -> {e}")

if __name__ == "__main__":
    check_key("OPENROUTER_API_KEY_PLANNER", os.getenv("OPENROUTER_API_KEY_PLANNER", ""))
    check_key("OPENROUTER_API_KEY_GENERAL", os.getenv("OPENROUTER_API_KEY_GENERAL", ""))