# Commute Analysis Visualizer

A Python tool for analyzing and visualizing commute routes using Google Maps API, focusing on combined driving and transit journeys.

## Features

> **Note:** The transit analysis feature is currently a work in progress.

- Visualizes commute routes on an interactive map
- Calculates driving time to transit stations
- Analyzes transit time to final destination
- Generates detailed HTML and PDF reports
- Supports multiple route analysis

## Prerequisites

- Python 3.7+
- Google Maps API key

## Installation

1. Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/commute-analysis
cd commute-analysis
```

2. Install required packages:

```bash

pip install -r requirements.txt

```
## Environment Variables

This project uses environment variables for configuration. To get started:

```bash
cp .env.example .env
```

| Variable | Description |
|----------|-------------|
| `GOOGLE_MAPS_API_KEY` | Your Google Maps API key |
| `WORK_ADDRESS` | Your workplace address |
| `PREFERRED_STATION` | Your preferred train station (optional) |
| `FINAL_DESTINATION` | Your final destination address |
| `FALLBACK_STATIONS` | Backup train stations (optional) |
| `MORNING_ARRIVAL` | Target arrival time (format: HH:MM) |
| `EVENING_ARRIVAL` | Target departure time (format: HH:MM) |


```
GOOGLE_MAPS_API_KEY=your_api_key_here
```

## Usage

1. Prepare your input CSV file with addresses (see `addresses_template.csv` for format)

2. Run the analysis:

```bash
python src/transit_analyzer.py --input addresses.csv
```
3. Generate visualizations:

```bash
python src/visualize_commutes.py
```

This will create an interactive HTML map and a detailed PDF report in the `output` directory.

## Output

- Interactive HTML map showing all roustes
- PDF report with detailed analysis
- CSV file with computed transit times and distances

## License

MIT License