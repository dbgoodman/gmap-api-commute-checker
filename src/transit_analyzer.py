import os
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv
import googlemaps
import pytz
from typing import Dict, List, Tuple, Optional
import argparse
import logging
from dataclasses import dataclass

# Load environment variables
load_dotenv()

@dataclass
class TransitConfig:
    """Configuration for transit analysis"""
    google_maps_key: str
    preferred_station: str
    final_destination: str
    fallback_stations: List[str]
    morning_arrival: str  # Format: "HH:MM"
    evening_arrival: str  # Format: "HH:MM"
    
    @classmethod
    def from_env(cls) -> 'TransitConfig':
        """Create config from environment variables"""
        # Required settings
        google_maps_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if not google_maps_key:
            raise ValueError("GOOGLE_MAPS_API_KEY must be set in .env file")
            
        # Optional settings with defaults
        preferred_station = os.getenv('PREFERRED_STATION', '')
        final_destination = os.getenv('FINAL_DESTINATION', '3400 Civic Center Boulevard, Philadelphia, PA 19104')
        fallback_stations_str = os.getenv('FALLBACK_STATIONS', '')
        morning_arrival = os.getenv('MORNING_ARRIVAL', '09:00')
        evening_arrival = os.getenv('EVENING_ARRIVAL', '17:30')
        
        # Validate time formats
        for time_str in [morning_arrival, evening_arrival]:
            try:
                datetime.strptime(time_str, '%H:%M')
            except ValueError:
                raise ValueError(f"Invalid time format: {time_str}. Use HH:MM format (24-hour)")
        
        return cls(
            google_maps_key=google_maps_key,
            preferred_station=preferred_station,
            final_destination=final_destination,
            fallback_stations=fallback_stations_str.split(',') if fallback_stations_str else [],
            morning_arrival=morning_arrival,
            evening_arrival=evening_arrival
        )

def setup_logging(verbose: bool, debug: bool) -> None:
    """Configure logging based on verbosity and debug flags"""
    # Set up file handler (always at DEBUG level for troubleshooting)
    file_handler = logging.FileHandler('route_details.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    # Set up console handler (level based on flags)
    console_handler = logging.StreamHandler()
    if debug:
        console_handler.setLevel(logging.DEBUG)
    elif verbose:
        console_handler.setLevel(logging.INFO)
    else:
        console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything, let handlers filter
    root_logger.handlers = []  # Clear any existing handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

class TransitAnalyzer:
    def __init__(self, config: TransitConfig):
        self.config = config
        self.gmaps = googlemaps.Client(key=config.google_maps_key)
        self.eastern = pytz.timezone('America/New_York')
    
    def find_nearby_stations(self, address: str, radius_meters: int = 3000) -> List[Dict]:
        """Find train stations near an address"""
        try:
            location = self.gmaps.geocode(address)[0]['geometry']['location']
            
            stations = self.gmaps.places_nearby(
                location=location,
                radius=radius_meters,
                keyword='train station',
                type='train_station'
            )
            
            logging.info(f"\nFound stations near {address}:")
            for station in stations.get('results', []):
                logging.info(f"- {station['name']} ({station['vicinity']})")
                
            return stations.get('results', [])
        except Exception as e:
            logging.error(f"Error finding stations near {address}: {e}")
            return []
    
    def get_drive_time_to_station(self, home: str, station: Dict, departure_time: datetime) -> Tuple[Optional[float], Optional[float]]:
        """Get driving time to station"""
        try:
            result = self.gmaps.directions(
                home,
                f"{station['geometry']['location']['lat']},{station['geometry']['location']['lng']}",
                mode="driving",
                departure_time=departure_time
            )
            
            if result:
                duration_mins = result[0]['legs'][0]['duration_in_traffic']['value'] / 60
                distance_miles = result[0]['legs'][0]['distance']['value'] / 1609.34
                return duration_mins, distance_miles
            return None, None
        except Exception as e:
            logging.error(f"Error getting drive time to station: {e}")
            return None, None

    def get_walking_details(self, route: Dict) -> Tuple[float, float]:
        """Extract final walking segment details from route"""
        try:
            steps = route['steps']
            
            # Find the last transit step
            last_transit_index = -1
            for i, step in enumerate(steps):
                if step['travel_mode'] == 'TRANSIT':
                    last_transit_index = i
            
            if last_transit_index == -1:
                logging.debug("No transit steps found in route")
                return 0.0, 0.0
            
            # Only look at walking segments after the last transit
            final_walk_time = 0
            final_walk_distance = 0
            
            logging.debug(f"Processing steps after final transit (index {last_transit_index})")
            for step in steps[last_transit_index + 1:]:
                if step['travel_mode'] == 'WALKING':
                    duration_mins = step['duration']['value'] / 60
                    distance_miles = step['distance']['value'] / 1609.34
                    final_walk_time += duration_mins
                    final_walk_distance += distance_miles
                    logging.debug(f"Final walking segment:")
                    logging.debug(f"  Duration: {duration_mins:.1f} min")
                    logging.debug(f"  Distance: {distance_miles:.2f} miles")
                    logging.debug(f"  Instructions: {step.get('html_instructions', 'No instructions')}")
            
            logging.debug(f"Total final walk: {final_walk_time:.1f} min, distance: {final_walk_distance:.2f} miles")
            return final_walk_time, final_walk_distance
            
        except Exception as e:
            logging.error(f"Error getting walking details: {e}")
            logging.error(f"Route structure: {route.keys()}")
            return 0.0, 0.0

    def get_transit_details(self, station: Dict, arrival_time: datetime, destination: str) -> Optional[Dict]:
        """Get transit journey details from station to destination"""
        try:
            station_location = f"{station['geometry']['location']['lat']},{station['geometry']['location']['lng']}"
            
            # For evening commute, swap origin and destination
            if destination == station_location:  # Evening commute
                origin = self.config.final_destination
                dest = station_location
                logging.debug(f"\nAnalyzing evening route from {origin} to {dest}")
            else:  # Morning commute
                origin = station_location
                dest = destination
                logging.debug(f"\nAnalyzing morning route from {origin} to {dest}")
            
            result = self.gmaps.directions(
                origin,
                dest,
                mode="transit",
                arrival_time=arrival_time,
                alternatives=True,
                transit_mode=["rail"]
            )
            
            if not result:
                logging.debug(f"No routes found")
                return None

            valid_routes = []
            for i, route in enumerate(result):
                steps = route['legs'][0]['steps']
                logging.debug(f"\nRoute {i+1}:")
                
                # Log each step in the route
                has_valid_rail = False
                for step in steps:
                    if step['travel_mode'] == 'TRANSIT':
                        transit_details = step.get('transit_details', {})
                        line = transit_details.get('line', {}).get('name', 'Unknown')
                        vehicle = transit_details.get('line', {}).get('vehicle', {}).get('name', 'Unknown')
                        departure = transit_details.get('departure_stop', {}).get('name', 'Unknown')
                        arrival = transit_details.get('arrival_stop', {}).get('name', 'Unknown')
                        logging.debug(f"  Transit: {line} ({vehicle}) from {departure} to {arrival}")
                        
                        # Check if this is a valid rail line for Penn Medicine
                        if any(valid_line in line for valid_line in [
                            'Paoli/Thorndale Line',
                            'Media/Wawa Line',
                            'Airport Line',
                            'Wilmington/Newark Line'
                        ]):
                            has_valid_rail = True
                    elif step['travel_mode'] == 'WALKING':
                        distance = step['distance']['value']
                        duration = step['duration']['value'] / 60
                        logging.debug(f"  Walk: {distance}m ({duration:.1f} min)")
                
                if not has_valid_rail:
                    logging.debug("  Rejected: No valid rail connection to Penn Medicine")
                    continue
                    
                # Get all steps by type
                transit_steps = [step for step in steps if step['travel_mode'] == 'TRANSIT']
                walking_steps = [step for step in steps if step['travel_mode'] == 'WALKING']
                
                # Calculate times
                transit_time = sum(step['duration']['value'] / 60 for step in transit_steps)
                final_walk = walking_steps[-1] if walking_steps else None
                walk_time = final_walk['duration']['value'] / 60 if final_walk else 0
                walk_distance = final_walk['distance']['value'] / 1609.34 if final_walk else 0
                
                logging.debug(f"  Valid route found: {transit_time:.1f} min transit + {walk_time:.1f} min walk")
                valid_routes.append({
                    'route': route['legs'][0],
                    'transfers': len(transit_steps) - 1,
                    'duration_mins': transit_time,
                    'walk_time_mins': walk_time,
                    'walk_distance_miles': walk_distance,
                    'arrival_time': route['legs'][0]['arrival_time']['text'],
                    'departure_time': route['legs'][0]['departure_time']['text'],
                    'destination_station': transit_steps[-1]['transit_details']['arrival_stop']['name']
                })

            if valid_routes:
                best_route = min(valid_routes, key=lambda x: x['duration_mins'] + x['walk_time_mins'])
                logging.debug(f"\nSelected best route: {best_route['duration_mins']:.1f} min transit + {best_route['walk_time_mins']:.1f} min walk")
                return best_route
                
            return None
        except Exception as e:
            logging.error(f"Error getting transit details: {e}")
            return None

    def calculate_distance(self, point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
        """Calculate distance between two lat/lng points in kilometers"""
        from math import sin, cos, sqrt, atan2, radians
        
        R = 6371  # Earth's radius in kilometers
        
        lat1, lon1 = radians(point1[0]), radians(point1[1])
        lat2, lon2 = radians(point2[0]), radians(point2[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c

    def analyze_commute(self, home_address: str, is_morning: bool = True, verbose: bool = False) -> Optional[Dict]:
        """Analyze complete commute including drive to station and transit"""
        next_weekday = datetime.now(self.eastern).date() + timedelta(days=1)
        
        # Always find stations near home address
        logging.debug(f"\nSearching for stations near {home_address}")
        stations = self.find_nearby_stations(home_address)
        if not stations:
            logging.debug("No stations found near address")
            return None
        
        all_options = []
        
        for station in stations:
            station_location = f"{station['geometry']['location']['lat']},{station['geometry']['location']['lng']}"
            logging.debug(f"\nAnalyzing {'morning' if is_morning else 'evening'} commute using {station['name']}")
            
            # For morning: home -> station -> Penn Medicine
            # For evening: Penn Medicine -> same station -> home
            if is_morning:
                origin = station_location
                destination = self.config.final_destination
                arrival_time = self.eastern.localize(
                    datetime.combine(next_weekday, datetime.strptime(self.config.morning_arrival, "%H:%M").time())
                )
                logging.debug(f"Morning route: {station['name']} -> {destination}")
            else:
                origin = self.config.final_destination
                destination = station_location  # Return to same station
                arrival_time = self.eastern.localize(
                    datetime.combine(next_weekday, datetime.strptime(self.config.evening_arrival, "%H:%M").time())
                )
                logging.debug(f"Evening route: {self.config.final_destination} -> {station['name']}")
            
            logging.debug(f"Target arrival time: {arrival_time}")
            
            transit_details = self.get_transit_details(station, arrival_time, destination)  # Added destination parameter
            if not transit_details:
                logging.debug(f"No valid transit routes found for {station['name']}")
                continue
            
            try:
                departure_time_str = transit_details['departure_time'].replace('\u202f', ' ').strip()
                station_arrival_time = datetime.strptime(departure_time_str, '%I:%M %p').time()
                station_arrival_datetime = self.eastern.localize(
                    datetime.combine(next_weekday, station_arrival_time)
                )
            except ValueError as e:
                logging.error(f"Error parsing time '{transit_details['departure_time']}': {e}")
                continue
            
            drive_time, drive_distance = self.get_drive_time_to_station(
                home_address, 
                station, 
                station_arrival_datetime
            )
            
            if drive_time is None:
                continue
            
            total_time = drive_time + transit_details['duration_mins'] + transit_details['walk_time_mins']
            
            # Extract destination station from last transit step
            dest_station = None
            for step in transit_details['route']['steps']:
                if step['travel_mode'] == 'TRANSIT':
                    dest_station = step['transit_details']['arrival_stop']['name']
            
            all_options.append({
                'home_address': home_address,
                'station_name': station['name'],
                'station_address': station['vicinity'],
                'destination_station': dest_station,
                'drive_time_mins': round(drive_time, 1),
                'drive_distance_miles': round(drive_distance, 1),
                'transit_time_mins': round(transit_details['duration_mins'], 1),
                'walk_time_mins': round(transit_details['walk_time_mins'], 1),
                'walk_distance_miles': round(transit_details['walk_distance_miles'], 2),
                'total_time_mins': round(total_time, 1),
                'transfers': transit_details['transfers'],
                'arrival_time': transit_details['arrival_time'].replace('\u202f', ' ').strip(),
                'departure_time': f"Leave home at {(station_arrival_datetime - timedelta(minutes=drive_time)).strftime('%I:%M %p')}",
                'commute_type': 'Morning' if is_morning else 'Evening'
            })
        
        if all_options:
            return min(all_options, key=lambda x: (x['transfers'], x['total_time_mins']))
        
        return None

def main():
    parser = argparse.ArgumentParser(description='Analyze transit commute options.')
    parser.add_argument('--input', default='addresses.csv', help='Input CSV file with addresses')
    parser.add_argument('--output', default='transit_analysis.csv', help='Output CSV file')
    parser.add_argument('--verbose', action='store_true', help='Print detailed output')
    parser.add_argument('--debug', action='store_true', help='Print debug information')
    args = parser.parse_args()

    setup_logging(args.verbose, args.debug)

    try:
        # Load config from environment
        config = TransitConfig.from_env()
        
        addresses_df = pd.read_csv(args.input)
        analyzer = TransitAnalyzer(config)
        
        all_results = []
        
        for _, row in addresses_df.iterrows():
            print(f"\nAnalyzing commutes for: {row['address']}")
            
            morning_details = analyzer.analyze_commute(row['address'], is_morning=True, verbose=args.verbose)
            if morning_details:
                all_results.append(morning_details)
                
            evening_details = analyzer.analyze_commute(row['address'], is_morning=False, verbose=args.verbose)
            if evening_details:
                all_results.append(evening_details)

        if all_results:
            results_df = pd.DataFrame(all_results)
            # Sort by address and commute type (Morning first, then Evening)
            results_df = results_df.sort_values(['home_address', 'commute_type'])
            
            results_df.to_csv(args.output, index=False)
            print(f"\nResults saved to {args.output}")
            print(f"Detailed log saved to route_details.log")
            
            if args.verbose or args.debug:
                pd.set_option('display.max_columns', None)
                pd.set_option('display.width', None)
                print("\nTransit Commute Analysis:")
                print("-" * 100)
                print(results_df.to_string())
        else:
            print("No valid transit routes found.")
            
    except Exception as e:
        logging.error(f"Error running transit analysis: {e}")
        raise

if __name__ == "__main__":
    main() 