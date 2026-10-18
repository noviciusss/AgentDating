import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm import call_llm_with_messages

async def main():
    messages = [
        {"role": "system", "content": "You are Diksha Arora on a friendly first date. Speak in first person, 1-2 sentences."},
        {"role": "user", "content": "Hi Diksha, great to meet you! How's your week been?"}
    ]
    resp, model = await call_llm_with_messages(messages, model="openai/gpt-oss-20b", return_model=True)
    print(f"Model used: {model}")
    print(f"Response: {resp}")

if __name__ == "__main__":
    asyncio.run(main())
