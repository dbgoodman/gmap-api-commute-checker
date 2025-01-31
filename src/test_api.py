import os
from dotenv import load_dotenv
import googlemaps

# Load environment variables
load_dotenv()

# Initialize Google Maps client
gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))

def test_geocode():
    try:
        # Try a simple geocoding request
        result = gmaps.geocode("San Francisco, CA")
        print("Geocoding test result:", result)
    except Exception as e:
        print(f"Error during geocoding test: {e}")

def test_distance_matrix():
    try:
        # Try a simple distance matrix request
        result = gmaps.distance_matrix(
            origins=["San Francisco, CA"],
            destinations=["Oakland, CA"],
            mode="driving"
        )
        print("\nDistance Matrix test result:", result)
    except Exception as e:
        print(f"Error during distance matrix test: {e}")

if __name__ == "__main__":
    print(f"Using API key: {os.getenv('GOOGLE_MAPS_API_KEY')}")
    print("\nTesting Geocoding API...")
    test_geocode()
    print("\nTesting Distance Matrix API...")
    test_distance_matrix() 