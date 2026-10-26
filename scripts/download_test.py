import gdown
import os

os.makedirs("data/raw", exist_ok=True)
# Download multimodal_test_public.tsv
output_test = "data/raw/multimodal_test_public.tsv"
if not os.path.exists(output_test):
    print("Downloading multimodal_test_public.tsv...")
    gdown.download(id="1p9EewIKVcFbipVRLZNGYc2JbSC7A0SWv", output=output_test, quiet=False)
    if os.path.exists(output_test):
        print(f"Downloaded multimodal_test_public.tsv: {os.path.getsize(output_test) / (1024*1024):.2f} MB")
else:
    print(f"multimodal_test_public.tsv already exists: {os.path.getsize(output_test) / (1024*1024):.2f} MB")
