import pandas as pd
from sentence_transformers import SentenceTransformer
import pickle
import os


def generate_grant_embeddings():
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    root_dir    = os.path.dirname(os.path.dirname(script_dir))
    csv_path    = os.path.join(root_dir, "data", "similar_grants", "open_opportunities_deep.csv")
    output_path = os.path.join(root_dir, "data", "similar_grants", "grant_embeddings.pkl")

    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found. Run find_open_grants.py first.")
        return

    df = pd.read_csv(csv_path)
    df["description"] = df["description"].fillna("No description provided")

    print("Loading SentenceTransformer model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    print(f"Generating embeddings for {len(df)} grants...")
    embeddings = model.encode(df["description"].tolist(), show_progress_bar=True)

    with open(output_path, "wb") as f:
        pickle.dump(embeddings, f)

    print(f"SUCCESS: {len(embeddings)} embeddings saved to {output_path}")


if __name__ == "__main__":
    generate_grant_embeddings()
