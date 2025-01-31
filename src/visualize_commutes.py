import argparse
import folium
from folium import plugins
import pandas as pd
import webbrowser
import os
from datetime import datetime
import pdfkit
from jinja2 import Template
import googlemaps
from dotenv import load_dotenv
import polyline  # Add this for decoding Google's polyline format
import logging

# Load environment variables and initialize Google Maps client
load_dotenv()
gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))

def decode_polyline(polyline_str):
    """Decode Google's polyline format into list of coordinates"""
    return polyline.decode(polyline_str)

def create_commute_map(transit_data: pd.DataFrame, output_file: str = "commute_analysis.html"):
    """Create an interactive map with all commute routes"""
    
    # Create a map centered on Philadelphia
    m = folium.Map(
        location=[39.9526, -75.1652],
        zoom_start=11,
        tiles="cartodbpositron"
    )
    
    # Add destination station marker (Penn Medicine or final destination)
    for _, row in transit_data.iterrows():
        dest_result = gmaps.geocode(row['destination_station'])
        if dest_result:
            dest_lat = dest_result[0]['geometry']['location']['lat']
            dest_lng = dest_result[0]['geometry']['location']['lng']
            folium.Marker(
                [dest_lat, dest_lng],
                popup=f"Destination: {row['destination_station']}",
                icon=folium.Icon(color='red', icon='info-sign')
            ).add_to(m)
            break  # Only need to add destination marker once
    
    # Add markers and routes for each home address
    for _, row in transit_data.iterrows():
        try:
            # Get coordinates for home address
            home_result = gmaps.geocode(row['home_address'])
            if not home_result:
                logging.warning(f"Could not geocode home address: {row['home_address']}")
                continue
                
            home_lat = home_result[0]['geometry']['location']['lat']
            home_lng = home_result[0]['geometry']['location']['lng']
            
            # Add home marker
            folium.Marker(
                [home_lat, home_lng],
                popup=f"Home: {row['home_address']}<br>"
                      f"Total time: {row['total_time_mins']} min",
                icon=folium.Icon(color='green', icon='home')
            ).add_to(m)
            
            # Handle station coordinates
            if 'Amtrak' in row['station_name']:
                # Special handling for Amtrak stations
                station_query = f"{row['station_name']}, {row['station_address']}"
            else:
                station_query = f"SEPTA {row['station_name']}"
            
            station_result = gmaps.geocode(station_query)
            if not station_result:
                logging.warning(f"Could not geocode station: {station_query}")
                continue
                
            station_lat = station_result[0]['geometry']['location']['lat']
            station_lng = station_result[0]['geometry']['location']['lng']
            
            # Add station marker
            folium.Marker(
                [station_lat, station_lng],
                popup=f"Station: {row['station_name']}<br>"
                      f"Drive: {row['drive_time_mins']} min<br>"
                      f"Transit: {row['transit_time_mins']} min",
                icon=folium.Icon(color='blue', icon='train')
            ).add_to(m)
            
            # Draw driving route
            driving_route = gmaps.directions(
                row['home_address'],
                f"{station_lat},{station_lng}",  # Use exact coordinates
                mode="driving"
            )
            
            if driving_route:
                driving_coords = decode_polyline(driving_route[0]['overview_polyline']['points'])
                folium.PolyLine(
                    driving_coords,
                    weight=2,
                    color='orange',
                    opacity=0.8,
                    popup=f"Drive: {row['drive_time_mins']} min"
                ).add_to(m)
            
            # Draw transit route
            transit_route = gmaps.directions(
                f"{station_lat},{station_lng}",  # Use exact coordinates
                row['destination_station'],
                mode="transit",
                transit_mode=["rail"]
            )
            
            if transit_route:
                transit_coords = decode_polyline(transit_route[0]['overview_polyline']['points'])
                folium.PolyLine(
                    transit_coords,
                    weight=2,
                    color='blue',
                    opacity=0.8,
                    popup=f"Transit: {row['transit_time_mins']} min"
                ).add_to(m)
                
        except Exception as e:
            logging.error(f"Error processing route visualization: {e}")
            continue
    
    # Save the map
    m.save(output_file)
    
    # Create PDF with map and table
    create_pdf_report(output_file, transit_data)

def create_pdf_report(map_file: str, transit_data: pd.DataFrame):
    """Create a PDF report with the map and commute analysis table"""
    
    html_template = """
    <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                table { border-collapse: collapse; width: 100%; margin: 20px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                h1, h2 { color: #333; }
                .summary { margin: 20px 0; }
            </style>
        </head>
        <body>
            <h1>Commute Analysis Report</h1>
            <h2>Generated on {{ date }}</h2>
            
            <div class="summary">
                <h3>Summary</h3>
                <p>Number of routes analyzed: {{ num_routes }}</p>
                <p>Average total commute time: {{ "%.1f"|format(avg_time) }} minutes</p>
                <p>Shortest commute: {{ "%.1f"|format(min_time) }} minutes</p>
                <p>Longest commute: {{ "%.1f"|format(max_time) }} minutes</p>
            </div>
            
            <div style="height: 600px;">
                {{ map_html }}
            </div>
            
            <h2>Detailed Commute Analysis</h2>
            {{ table_html }}
        </body>
    </html>
    """
    
    # Read the map HTML
    with open(map_file, 'r') as f:
        map_html = f.read()
    
    # Calculate summary statistics
    summary_stats = {
        'num_routes': len(transit_data),
        'avg_time': transit_data['total_time_mins'].mean(),
        'min_time': transit_data['total_time_mins'].min(),
        'max_time': transit_data['total_time_mins'].max()
    }
    
    # Define desired columns in order of preference
    desired_columns = [
        'home_address',
        'station_name',
        'destination_station',
        'drive_time_mins',
        'drive_distance_miles',
        'transit_time_mins',
        'walk_time_mins',
        'walk_distance_miles',
        'total_time_mins',
        'transfers'
    ]
    
    # Filter for columns that actually exist in the DataFrame
    available_columns = [col for col in desired_columns if col in transit_data.columns]
    
    # Create display DataFrame with available columns
    display_df = transit_data[available_columns].copy()
    
    # Create the table HTML
    table_html = display_df.to_html(classes='dataframe', index=False)
    
    # Render the template
    template = Template(html_template)
    html_content = template.render(
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        map_html=map_html,
        table_html=table_html,
        **summary_stats
    )
    
    # Save as PDF
    pdf_file = map_file.replace('.html', '.pdf')
    try:
        pdfkit.from_string(html_content, pdf_file)
        print(f"PDF report saved as {pdf_file}")
    except Exception as e:
        print(f"Error creating PDF: {e}")
        print("HTML report still available at", map_file)

def create_html_report(map_file: str, transit_data: pd.DataFrame):
    """Create an HTML report with map and analysis"""
    
    html_template = """
    <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                table { border-collapse: collapse; width: 100%; margin: 20px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                h1, h2 { color: #333; }
                .summary { margin: 20px 0; }
                .map-container { height: 600px; margin: 20px 0; }
            </style>
        </head>
        <body>
            <h1>Commute Analysis Report</h1>
            <h2>Generated on {{ date }}</h2>
            
            <div class="summary">
                <h3>Summary</h3>
                <p>Number of routes analyzed: {{ num_routes }}</p>
                <p>Average total commute time: {{ "%.1f"|format(avg_time) }} minutes</p>
                <p>Shortest commute: {{ "%.1f"|format(min_time) }} minutes</p>
                <p>Longest commute: {{ "%.1f"|format(max_time) }} minutes</p>
            </div>
            
            <div class="map-container">
                {{ map_html }}
            </div>
            
            <h2>Detailed Commute Analysis</h2>
            {{ table_html }}
        </body>
    </html>
    """
    
    # Read the map HTML
    with open(map_file, 'r') as f:
        map_html = f.read()
    
    # Calculate summary statistics
    summary_stats = {
        'num_routes': len(transit_data),
        'avg_time': transit_data['total_time_mins'].mean(),
        'min_time': transit_data['total_time_mins'].min(),
        'max_time': transit_data['total_time_mins'].max()
    }
    
    # Define desired columns in order of preference
    desired_columns = [
        'home_address',
        'station_name',
        'destination_station',
        'drive_time_mins',
        'drive_distance_miles',
        'transit_time_mins',
        'walk_time_mins',
        'walk_distance_miles',
        'total_time_mins',
        'transfers'
    ]
    
    # Filter for columns that actually exist in the DataFrame
    available_columns = [col for col in desired_columns if col in transit_data.columns]
    
    # Create display DataFrame with available columns
    display_df = transit_data[available_columns].copy()
    
    # Create the table HTML
    table_html = display_df.to_html(classes='dataframe', index=False)
    
    # Render the template
    template = Template(html_template)
    html_content = template.render(
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        map_html=map_html,
        table_html=table_html,
        **summary_stats
    )
    
    # Save as HTML
    html_file = map_file
    try:
        with open(html_file, 'w') as f:
            f.write(html_content)
        print(f"HTML report saved as {html_file}")
        # Open the HTML file in the default browser
        webbrowser.open('file://' + os.path.realpath(html_file))
    except Exception as e:
        print(f"Error creating HTML report: {e}")

def main():
    parser = argparse.ArgumentParser(description='Visualize commute analysis')
    parser.add_argument('--input', default='transit_analysis.csv', help='Input CSV file with commute analysis')
    parser.add_argument('--output', default='commute_analysis.html', help='Output HTML file name')
    args = parser.parse_args()
    
    # Read the transit analysis data
    transit_data = pd.read_csv(args.input)
    
    # Create the visualization and HTML report
    create_commute_map(transit_data, args.output)
    create_html_report(args.output, transit_data)

if __name__ == "__main__":
    main() 