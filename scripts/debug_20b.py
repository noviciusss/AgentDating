import asyncio
import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("LLM_API_KEY", "").strip("\"'")
base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")

r = requests.post(
    f"{base_url}/chat/completions",
    headers={"Authorization": f"Bearer {api_key}", "accept-encoding": "identity"},
    json={
        "model": "openai/gpt-oss-20b",
        "messages": [
            {"role": "user", "content": "Say hello!"}
        ],
        "max_tokens": 100
    }
)
print("Status:", r.status_code)
print("Body:", r.text)
