import pandas as pd
import urllib.request
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
import io

df = pd.read_csv("data/raw/multimodal_train.tsv", sep="\t", nrows=100)
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

def fetch_img(row):
    url = str(row['image_url'])
    item_id = str(row['id'])
    if not url.startswith('http'):
        return False, item_id, "invalid_url"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = resp.read()
            # Validate image can be opened by PIL
            img = Image.open(io.BytesIO(data))
            img.verify()
            return True, item_id, len(data)
    except Exception as e:
        return False, item_id, str(type(e).__name__)

start = time.time()
success = 0
failed = 0
reasons = {}

with ThreadPoolExecutor(max_workers=16) as executor:
    futures = [executor.submit(fetch_img, row) for _, row in df.iterrows()]
    for f in as_completed(futures):
        ok, i_id, res = f.result()
        if ok:
            success += 1
        else:
            failed += 1
            reasons[res] = reasons.get(res, 0) + 1

elapsed = time.time() - start
print(f"Processed {len(df)} URLs in {elapsed:.2f}s ({len(df)/elapsed:.1f} urls/sec)")
print(f"Success: {success}, Failed: {failed}")
print("Failure reasons:", reasons)
