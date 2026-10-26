from transformers import AutoTokenizer, AutoModel
import torch

model_name = "sentence-transformers/all-MiniLM-L6-v2"
print(f"Testing AutoTokenizer and AutoModel for {model_name}...")
try:
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    print("Successfully loaded tokenizer and model!")
    inputs = tokenizer(["Breaking: Real news headline here", "Another test headline"], padding=True, truncation=True, return_tensors="pt")
    with torch.no_grad():
        out = model(**inputs)
        # Mean pooling
        embeddings = out.last_hidden_state.mean(dim=1)
        print("Embedding shape:", embeddings.shape)
except Exception as e:
    print("Error loading model:", e)
