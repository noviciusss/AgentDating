import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("LLM_API_KEY", "").strip("\"'")
base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")

r = requests.get(f"{base_url}/models", headers={"Authorization": f"Bearer {api_key}"})
if r.status_code == 200:
    for m in r.json().get("data", []):
        mid = m["id"]
        if any(x in mid.lower() for x in ["llama", "qwen", "gpt", "mixtral", "gemma"]):
            print(f"- {mid}")
else:
    print(r.status_code, r.text)
