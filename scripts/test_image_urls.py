import pandas as pd
import urllib.request
import os

df = pd.read_csv("data/raw/multimodal_train.tsv", sep="\t", nrows=20)
print("Testing URL downloads...")
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

success = 0
for idx, row in df.iterrows():
    url = str(row['image_url'])
    item_id = row['id']
    if url.startswith('http'):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read()
                print(f"Success [{item_id}]: {len(data)} bytes from {url[:50]}...")
                success += 1
                if success >= 5:
                    break
        except Exception as e:
            print(f"Failed [{item_id}]: {e}")
