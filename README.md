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

3. Create a `.env` file in the project root and add your Google Maps API key:


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