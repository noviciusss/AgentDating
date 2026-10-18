import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm import call_llm, parse_llm_json
from app.prompts import DATE_SCORING_TEMPLATE

async def main():
    sys.stdout.reconfigure(encoding='utf-8')
    system_prompt = "You privately evaluate this date for Diksha Arora.\nProfile: {'name': 'Diksha Arora', 'summary': 'Career coach'}\nDate transcript:\nYou: Hi! Great to meet you.\nThem: Hey Diksha! Loving this conversation."
    user_prompt = DATE_SCORING_TEMPLATE.format(name="Diksha Arora")
    
    print("Testing scoring with qwen/qwen3.8-27b...")
    resp, model = await call_llm(system_prompt, user_prompt, model="qwen/qwen3.8-27b", max_tokens=250, json_mode=True, return_model=True)
    print("Model:", model)
    print("Parsed JSON:", parse_llm_json(resp))

if __name__ == "__main__":
    asyncio.run(main())
