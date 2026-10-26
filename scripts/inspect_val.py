import pandas as pd

df = pd.read_csv("data/raw/multimodal_validate.tsv", sep="\t", nrows=10)
print("Columns:", list(df.columns))
print("Sample row:")
print(df.iloc[0].to_dict())

# Count total rows
full_df = pd.read_csv("data/raw/multimodal_validate.tsv", sep="\t")
print(f"Total rows in multimodal_validate.tsv: {len(full_df)}")
print("2_way_label distribution:")
print(full_df['2_way_label'].value_counts().to_dict())
print("3_way_label distribution:")
print(full_df['3_way_label'].value_counts().to_dict())
print("6_way_label distribution:")
print(full_df['6_way_label'].value_counts().to_dict())
print("hasImage value counts:")
print(full_df['hasImage'].value_counts().to_dict())
