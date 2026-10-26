import gdown
import os

os.makedirs("data/raw", exist_ok=True)
output_train = "data/raw/multimodal_train.tsv"
if not os.path.exists(output_train):
    print("Downloading multimodal_train.tsv...")
    gdown.download(id="1XsOkD3yhxgWu8URMes0S9LVSwuFJ4pT6", output=output_train, quiet=False)
    if os.path.exists(output_train):
        print(f"Downloaded multimodal_train.tsv: {os.path.getsize(output_train) / (1024*1024):.2f} MB")
else:
    print(f"multimodal_train.tsv already exists: {os.path.getsize(output_train) / (1024*1024):.2f} MB")
