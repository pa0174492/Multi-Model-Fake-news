import pandas as pd

df = pd.read_csv("data/raw/multimodal_validate.tsv", sep="\t")
print("Crosstab 2_way vs 6_way:")
print(pd.crosstab(df['2_way_label'], df['6_way_label']))

print("\nCrosstab 2_way vs 3_way:")
print(pd.crosstab(df['2_way_label'], df['3_way_label']))

print("\nCrosstab 3_way vs 6_way:")
print(pd.crosstab(df['3_way_label'], df['6_way_label']))

print("\nSubreddits for 2_way_label == 1 (top 5):")
print(df[df['2_way_label'] == 1]['subreddit'].value_counts().head(5))

print("\nSubreddits for 2_way_label == 0 (top 5):")
print(df[df['2_way_label'] == 0]['subreddit'].value_counts().head(5))
