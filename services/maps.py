import os
import googlemaps
from typing import List
from models import HospitalRecommendation

# Initialize Google Maps client
gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))

async def add_real_travel_times(user_location: str, recommendations: List[HospitalRecommendation], simulation_mode: bool = False):
    """
    Updates the top 2 recommendations with real ETAs from Google Maps.
    """
    if not recommendations:
        return recommendations

    # Requirement 4: Use mock logic if X-Simulation-Mode is true
    if simulation_mode:
        for rec in recommendations[:2]:
            rec.reasoning += " (SIMULATED ETA)"
        return recommendations

    # Get hospital names for the destinations
    destinations = [rec.hospital_name for rec in recommendations[:2]]
    
    try:
        matrix = gmaps.distance_matrix(
            origins=user_location,
            destinations=destinations,
            mode="driving",
            departure_time="now" 
        )

        for i, rec in enumerate(recommendations[:2]):
            element = matrix['rows'][0]['elements'][i]
            if element['status'] == 'OK':
                rec.eta_minutes = round(element['duration_in_traffic']['value'] / 60)
                rec.distance_km = round(element['distance']['value'] / 1000, 1)
    except Exception as e:
        print(f"Maps API Error: {e}. Falling back to AI estimates.")
    
    return recommendations