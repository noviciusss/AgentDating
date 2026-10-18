import os
import traceback
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
api_key = os.getenv("LLM_API_KEY", "").strip("\"'")
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=api_key,
    default_headers={"accept-encoding": "identity"}
)

try:
    print("Testing qwen/qwen3.8-27b with accept-encoding: identity ...")
    resp = client.chat.completions.create(
        model="qwen/qwen3.8-27b",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=10
    )
    print("SUCCESS! Response:", resp.choices[0].message.content)
except Exception as e:
    traceback.print_exc()
