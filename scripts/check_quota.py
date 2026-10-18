import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("LLM_API_KEY", "").strip("\"'")
base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")

models = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]

print("=== Checking Real Groq Rate Limits via Headers ===")
for model in models:
    try:
        r = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "accept-encoding": "identity"
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 5
            },
            timeout=10
        )
        print(f"\nModel: {model} (HTTP {r.status_code})")
        rl_headers = {k: v for k, v in r.headers.items() if "ratelimit" in k.lower()}
        if rl_headers:
            for k, v in sorted(rl_headers.items()):
                print(f"  {k}: {v}")
        else:
            if r.status_code == 429:
                err = r.json().get("error", {})
                print(f"  Rate limited: {err.get('message', r.text)[:160]}")
    except Exception as e:
        print(f"Error checking {model}: {e}")
