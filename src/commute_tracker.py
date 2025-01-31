import os
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv
import googlemaps
import argparse
import pytz

# Load environment variables
load_dotenv()

# Initialize Google Maps client
gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))
WORK_ADDRESS = os.getenv('WORK_ADDRESS')

def get_next_weekday(d):
    """Get the next weekday (Monday-Friday) from a given date"""
    while d.weekday() > 4:  # 5 is Saturday, 6 is Sunday
        d += timedelta(days=1)
    return d

def get_commute_time(origin, destination, target_time=None, is_arrival=False):
    """
    Get the commute time between two addresses with time ranges
    target_time: datetime object for when you want to depart/arrive
    is_arrival: if True, target_time is arrival time; if False, it's departure time
    """
    try:
        # Ensure we're using Eastern Time
        eastern = pytz.timezone('America/New_York')
        if target_time.tzinfo is None:
            target_time = eastern.localize(target_time)

        if is_arrival:
            departure_time = target_time - timedelta(minutes=45)
        else:
            departure_time = target_time

        params = {
            'origins': [origin],
            'destinations': [destination],
            'mode': "driving",
            'departure_time': departure_time,
            'traffic_model': "pessimistic",
            'alternatives': True  # Request alternative routes
        }

        # Get times for all possible routes
        result = gmaps.directions(
            origin,
            destination,
            departure_time=departure_time,
            alternatives=True
        )

        if not result:
            raise Exception("No routes found")

        # Extract durations from all routes
        durations = []
        for route in result:
            duration_in_traffic = route['legs'][0]['duration_in_traffic']['value'] / 60
            durations.append(duration_in_traffic)

        # Calculate statistics from all routes
        optimistic_mins = min(durations)
        pessimistic_mins = max(durations)
        average_mins = sum(durations) / len(durations)
        
        # Get distance from the first route
        distance_miles = result[0]['legs'][0]['distance']['value'] / 1609.34

        return optimistic_mins, average_mins, pessimistic_mins, distance_miles
    except Exception as e:
        print(f"Error getting commute time for {origin} to {destination}: {e}")
        return None, None, None, None

def analyze_commutes(addresses_df):
    """Analyze commutes for all addresses"""
    # Use Eastern Time
    eastern = pytz.timezone('America/New_York')
    next_weekday = get_next_weekday(datetime.now(eastern).date() + timedelta(days=1))
    
    # Set specific times for morning and evening commutes
    morning_departure = eastern.localize(
        datetime.combine(next_weekday, datetime.strptime("8:15", "%H:%M").time())
    )
    evening_departure = eastern.localize(
        datetime.combine(next_weekday, datetime.strptime("17:00", "%H:%M").time())
    )

    results = []
    
    for idx, row in addresses_df.iterrows():
        home_address = row['address']
        print(f"Analyzing commute for: {home_address}")

        # Morning commute (to work)
        morning_opt, morning_avg, morning_pess, morning_dist = get_commute_time(
            home_address, WORK_ADDRESS, morning_departure, False)

        # Evening commute (to home)
        evening_opt, evening_avg, evening_pess, evening_dist = get_commute_time(
            WORK_ADDRESS, home_address, evening_departure, True)

        if all(v is not None for v in [morning_opt, morning_avg, morning_pess, evening_opt, evening_avg, evening_pess]):
            results.append({
                'Address': home_address,
                'Distance (miles)': f"{morning_dist:.1f}",
                'Morning Avg (min)': f"{morning_avg:.0f}",
                'Morning Range': f"{morning_opt:.0f}-{morning_pess:.0f}",
                'Evening Avg (min)': f"{evening_avg:.0f}",
                'Evening Range': f"{evening_opt:.0f}-{evening_pess:.0f}",
                'Total Daily (min)': f"{(morning_avg + evening_avg):.0f}",
                '_sort': morning_avg + evening_avg  # Hidden column for sorting
            })

    return pd.DataFrame(results)

def main():
    parser = argparse.ArgumentParser(description='Analyze commute times for multiple addresses')
    parser.add_argument('--addresses', default='addresses.csv', help='Path to CSV file with addresses')
    parser.add_argument('--output', default='commute_analysis.csv', help='Output CSV file name')
    args = parser.parse_args()

    if not WORK_ADDRESS:
        print("Error: WORK_ADDRESS not found in .env file")
        return

    # Read addresses from CSV
    try:
        addresses_df = pd.read_csv(args.addresses)
        if 'address' not in addresses_df.columns:
            raise ValueError("CSV must contain an 'address' column")
    except Exception as e:
        print(f"Error reading addresses CSV: {e}")
        return

    # Analyze commutes
    results_df = analyze_commutes(addresses_df)

    # Sort by total daily commute time
    results_df = results_df.sort_values('_sort')
    results_df = results_df.drop('_sort', axis=1)  # Remove sorting column

    # Save to CSV
    results_df.to_csv(args.output, index=False)
    
    # Print formatted results
    print("\nCommute Analysis Results:")
    print("-" * 120)
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    print(results_df.to_string())
    print(f"\nResults saved to {args.output}")

if __name__ == "__main__":
    main() 