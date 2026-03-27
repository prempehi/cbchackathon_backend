import os
from typing import List, Optional
from google.cloud import firestore
# Ensure you have your models imported correctly
from models import Hospital, HospitalStatus, WardType

class FirestoreService:
    def __init__(self):
        self.project_id = os.getenv("FIREBASE_PROJECT_ID")
        # Use the APP_ID from .env to satisfy Architecture §4.1
        self.app_id = os.getenv("APP_ID", "gehg-app") 
        
        self.db = firestore.AsyncClient(project=self.project_id)
        
        # Updated to use the dynamic app_id
        self.base_path = f"artifacts/{self.app_id}/public/data/hospitals"

    async def get_available_hospitals(self) -> List[dict]:
        """
        Fetches hospitals with GREEN or YELLOW status.
        """
        # Using .value ensures we send strings to Firestore, not Enum objects
        allowed_statuses = [HospitalStatus.GREEN.value, HospitalStatus.YELLOW.value]
        
        query = self.db.collection(self.base_path).where(
            "status", "in", allowed_statuses
        )
        docs = await query.get()
        return [doc.to_dict() for doc in docs]

    async def update_hospital_summary(self, hospital_id: str, data: dict):
        """
        Updates top-level hospital info. 
        Enforces Security Rule #1: only status, last_updated, total_capacity.
        """
        allowed_keys = {'status', 'last_updated', 'total_capacity'}
        filtered_data = {k: v for k, v in data.items() if k in allowed_keys}
        filtered_data["last_updated"] = firestore.SERVER_TIMESTAMP

        doc_ref = self.db.collection(self.base_path).document(hospital_id)
        await doc_ref.update(filtered_data)

    async def update_ward_capacity(self, hospital_id: str, ward_type: WardType, new_beds: int):
        """
        Updates bed counts in the /wards sub-collection.
        Matches Security Rule #2 for ward access.
        """
        ward_ref = (
            self.db.collection(self.base_path)
            .document(hospital_id)
            .collection("wards")
            .document(ward_type.value)
        )
        
        await ward_ref.update({
            "beds_available": new_beds,
            "last_updated": firestore.SERVER_TIMESTAMP
        })

# Global instance
db_service = FirestoreService()