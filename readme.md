# FBref Wages Scraper

A Python script to scrape player wages data from FBref.com for major European football leagues. It uses DrissionPage for browser automation and CloudflareBypasser to handle Cloudflare protections.

## Features

- Scrapes weekly and annual wages in GBP, EUR, and USD.
- Supports multiple leagues: Premier League, Bundesliga, La Liga, Ligue 1, Serie A.
- Handles seasons from specified start years to 2025.
- Resumes scraping from where it left off using CSV progress tracking.
- Outputs data to a CSV file with proper encoding for Excel compatibility.

## Requirements

- Python 3.x
- DrissionPage
- CloudflareBypasser (custom module, assumed to be in the same directory)

Install dependencies:

```bash
pip install DrissionPage
```

## Configuration

Edit the `LEAGUES` dictionary in `fbref.py` to adjust league IDs, slugs, and season ranges.

Adjust delays and limits in the CONFIG section:

- `DELAY_BETWEEN_PAGES`: Tuple for random delay between page loads (seconds).
- `DELAY_BETWEEN_TEAMS`: Tuple for random delay between team scrapes (seconds).
- `MAX_TEAMS_PER_SEASON`: Maximum teams to scrape per season.

## Usage

Run the script:

```bash
python fbref.py
```

The script will scrape data and save it to `wages_data.csv`. It handles interruptions gracefully and resumes progress.

## Output

CSV fields include: Season, League, Team, Player, Player link, Player ID, Nation, Position, Age, Weekly/Annual Wages in £/€/$, Notes.

## Notes

- Ensure CloudflareBypasser is properly configured for bypassing protections.
- Scraping may be subject to FBref's terms of service; use responsibly.
- For 2025 seasons, URLs are formatted differently.

## Troubleshooting

- If wages show missing £/€, the script uses innerHTML parsing to handle encoding issues.
- Check console output for errors or warnings.