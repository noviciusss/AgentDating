import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("LLM_API_KEY", "").strip("\"'")
base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")

print(f"Connecting to {base_url}/models ...")
try:
    r = requests.get(f"{base_url}/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
    print("Status code:", r.status_code)
    if r.status_code == 200:
        models = [m["id"] for m in r.json().get("data", [])]
        print(f"Success! {len(models)} models available:")
        for m in sorted(models):
            print(" -", m)
    else:
        print("Error:", r.text)
except Exception as e:
    print("Request failed:", e)
