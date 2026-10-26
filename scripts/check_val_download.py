import gdown
import os

os.makedirs("data/raw", exist_ok=True)
# Let's test downloading multimodal_validate.tsv or multimodal_test_public.tsv
# ID for multimodal_validate.tsv: 1Z99QrwpthioZQY2U6HElmnx8jazf7-Kv
# ID for multimodal_test_public.tsv: 1p9EewIKVcFbipVRLZNGYc2JbSC7A0SWv

print("Attempting to download validation file to inspect...")
output_path = "data/raw/multimodal_validate.tsv"
try:
    gdown.download(id="1Z99QrwpthioZQY2U6HElmnx8jazf7-Kv", output=output_path, quiet=False)
    if os.path.exists(output_path):
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"Downloaded multimodal_validate.tsv: {size_mb:.2f} MB")
except Exception as e:
    print(f"Error downloading: {e}")
