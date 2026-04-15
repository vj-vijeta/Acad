import pandas as pd
import googlemaps
import json
import os

GOOGLE_MAPS_KEY = "AIzaSyCaP5Qxqh7UP2wSFQt0u8lQg4TM5Vj6dMM"
CACHE_FILE = "geocoding_cache.json"
DATA_FILES = [
    "Supporting data-13th March 2026.xlsx - 2024.csv",
    "Supporting data-13th March 2026.xlsx - 2025.csv",
    "Supporting data-13th March 2026.xlsx - 2026.csv"
]

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=4)

def pre_geocode():
    cache = load_cache()
    all_locations = set()
    
    print("Collecting locations from CSVs...")
    for file in DATA_FILES:
        if os.path.exists(file):
            df = pd.read_csv(file)
            df.columns = df.columns.str.strip()
            if 'School Name' in df.columns and 'City' in df.columns and 'State' in df.columns:
                unique_locs = df[['School Name', 'City', 'State']].dropna().drop_duplicates()
                for _, row in unique_locs.iterrows():
                    all_locations.add(f"{row['School Name']}, {row['City']}, {row['State']}, India")
        else:
            print(f"File not found: {file}")

    print(f"Total unique school locations found: {len(all_locations)}")
    
    gmaps = googlemaps.Client(key=GOOGLE_MAPS_KEY)
    count = 0
    new_geocoded = 0
    
    for addr in all_locations:
        count += 1
        if addr in cache:
            continue
        
        try:
            print(f"[{count}/{len(all_locations)}] Geocoding: {addr}...")
            result = gmaps.geocode(addr)
            if result:
                location = result[0]['geometry']['location']
                cache[addr] = {'lat': location['lat'], 'lon': location['lng']}
                new_geocoded += 1
                if new_geocoded % 10 == 0:
                    save_cache(cache)
        except Exception as e:
            print(f"Error geocoding {addr}: {e}")

    save_cache(cache)
    print(f"Geocoding complete. Added {new_geocoded} new locations to cache.")

if __name__ == "__main__":
    pre_geocode()
