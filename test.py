import asyncio
import os
from dotenv import load_dotenv

# 1. Load the .env file FIRST
load_dotenv()

# 2. Tell Google where your key file is
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "serviceAccountKey.json"

# 3. NOW import the service
from database import db_service

async def test():
    try:
        hospitals = await db_service.get_available_hospitals()
        print(f"✅ Success! Found {len(hospitals)} hospitals.")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())