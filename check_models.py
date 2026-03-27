import os
from google import genai
from dotenv import load_dotenv

# Load your .env file
load_dotenv()

# Initialize the modern Stateless Client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("--- Available Models (google-genai SDK) ---")
try:
    # List all models
    for m in client.models.list():
        # FIX: Use 'supported_actions' instead of 'supported_generation_methods'
        if "generateContent" in m.supported_actions:
            print(f"ID: {m.name} | Display Name: {m.display_name}")
            
except Exception as e:
    print(f"❌ Error connecting to Gemini API: {e}")