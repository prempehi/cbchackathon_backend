import asyncio
from dotenv import load_dotenv

# 1. Load env vars so authentication works
load_dotenv()

# 2. Import your database service
from database import db_service

async def run_seed():
    # Sample data mimicking your Ghana hospital setup
    hospitals = [
        {
            "id": "KBTH-001", 
            "name": "Korle-Bu Teaching Hospital", 
            "status": "GREEN", 
            "total_capacity": 500
        },
        {
            "id": "RMAR-002", 
            "name": "Ridge Hospital", 
            "status": "YELLOW", 
            "total_capacity": 300
        },
        {
            "id": "37MH-003", 
            "name": "37 Military Hospital", 
            "status": "RED", 
            "total_capacity": 400
        }
    ]
    
    print(f"🌱 Planting data at: {db_service.base_path}...")
    
    for hospital in hospitals:
        # Create a document for each hospital using its ID
        doc_ref = db_service.db.collection(db_service.base_path).document(hospital["id"])
        await doc_ref.set(hospital)
        print(f"✅ Added: {hospital['name']} ({hospital['status']})")
        
    print("🚀 Database successfully seeded!")

if __name__ == "__main__":
    asyncio.run(run_seed())