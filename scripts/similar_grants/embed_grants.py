import pandas as pd
from sentence_transformers import SentenceTransformer
import pickle
import os

def generate_grant_embeddings():
    
    # 1. Load clean data
    csv_path = 'data/similar_grants/open_opportunities_deep.csv'
    if not os.path.exists(csv_path):
        print("Error: data/similar_grants/open_opportunities_deep.csv not found!")
        return

    df = pd.read_csv(csv_path)

    # Make sure there's no empty descriptions
    df['description'] = df['description'].fillna('No description provided')

    # Load embedding model (about 100MB weights to local cache)
    print("Downloading/Loading SentenceTransformer model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Create embeddings — transform into 384 dimension vector
    print(f"Generating embeddings for {len(df)} grants. This may take a minute...")
    descriptions = df['description'].tolist()
    embeddings = model.encode(descriptions, show_progress_bar=True)

    # Save the embeddings
    output_path = 'data/similar_grants/grant_embeddings.pkl'
    with open(output_path, 'wb') as f:
        pickle.dump(embeddings, f)

    print(f"SUCCESS: {len(embeddings)} embeddings saved to {output_path}")

if __name__ == "__main__":
    generate_grant_embeddings()