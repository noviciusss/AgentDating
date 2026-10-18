import os
from dotenv import load_dotenv
from apify_client import ApifyClient

load_dotenv()
token = os.getenv("APIFY_TOKEN", "").strip("\"'")
print(f"Connecting to Apify with token prefix: {token[:12]}...")

try:
    client = ApifyClient(token)
    user = client.user().get()
    print("Apify connection successful!")
    print(f"User: {user.get('username') or user.get('id')}")
    print(f"Email: {user.get('email')}")
except Exception as e:
    print("Apify error:", e)
