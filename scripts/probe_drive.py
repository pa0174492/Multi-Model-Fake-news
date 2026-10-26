import urllib.request
import re
import json

url = 'https://drive.google.com/drive/folders/1jU7qgDqU1je9Y0PMKJ_f31yXRo5uWGFm'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

try:
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
        print(f"HTML response length: {len(html)}")
        # Look for file names ending with .tsv or folder names
        tsv_matches = set(re.findall(r'[\w\-]+(?:train|val|test|comments|fakeddit)[\w\.\-]*\.tsv', html, re.IGNORECASE))
        print("Found TSVs in HTML:", tsv_matches)
        
        # Look for Google Drive IDs
        all_ids = set(re.findall(r'["\']([a-zA-Z0-9_-]{28,35})["\']', html))
        print(f"Found {len(all_ids)} potential IDs")
except Exception as e:
    print(f"Error checking Google Drive folder: {e}")
