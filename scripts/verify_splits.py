import pandas as pd

train_df = pd.read_csv("data/raw/multimodal_train.tsv", sep="\t")
val_df = pd.read_csv("data/raw/multimodal_validate.tsv", sep="\t")
test_df = pd.read_csv("data/raw/multimodal_test_public.tsv", sep="\t")

print(f"Train rows: {len(train_df)}")
print(f"Val rows: {len(val_df)}")
print(f"Test rows: {len(test_df)}")

# Check ID overlap
train_ids = set(train_df['id'].dropna())
val_ids = set(val_df['id'].dropna())
test_ids = set(test_df['id'].dropna())

print(f"Overlap train-val: {len(train_ids.intersection(val_ids))}")
print(f"Overlap train-test: {len(train_ids.intersection(test_ids))}")
print(f"Overlap val-test: {len(val_ids.intersection(test_ids))}")

# Check clean_title nulls
print("Train null clean_title:", train_df['clean_title'].isna().sum())
print("Val null clean_title:", val_df['clean_title'].isna().sum())
print("Test null clean_title:", test_df['clean_title'].isna().sum())

# Check image_url nulls
print("Train null image_url:", train_df['image_url'].isna().sum())
print("Val null image_url:", val_df['image_url'].isna().sum())
print("Test null image_url:", test_df['image_url'].isna().sum())
