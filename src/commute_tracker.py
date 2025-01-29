import os
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
import googlemaps

# Load environment variables
load_dotenv()

# Initialize Google Maps client
gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))

def get_commute_time(origin, destination, departure_time=None):
    """
    Get the commute time between two addresses
    """
    try:
        result = gmaps.distance_matrix(
            origins=[origin],
            destinations=[destination],
            mode="driving",
            departure_time=departure_time,
            traffic_model="best_guess"
        )
        
        if result['rows'][0]['elements'][0]['status'] == 'OK':
            duration = result['rows'][0]['elements'][0]['duration_in_traffic']['text']
            return duration
        return None
    except Exception as e:
        print(f"Error getting commute time: {e}")
        return None

def main():
    # Example addresses (you can later load these from a CSV)
    addresses = [
        {"origin": "123 Main St, City, State",
         "destination": "456 Work Ave, City, State"}
    ]
    
    # Get current time (you can modify this to test different times)
    now = datetime.now()
    
    results = []
    for addr in addresses:
        time = get_commute_time(
            addr["origin"],
            addr["destination"],
            departure_time=now
        )
        results.append({
            "origin": addr["origin"],
            "destination": addr["destination"],
            "commute_time": time,
            "timestamp": now
        })
    
    # Convert to DataFrame and save
    df = pd.DataFrame(results)
    df.to_csv("commute_times.csv", index=False)

if __name__ == "__main__":
    main() 