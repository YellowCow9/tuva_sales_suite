import pandas as pd
from sentence_transformers import SentenceTransformer
import pickle
import os

def generate_grant_embeddings():
    # 1. Load your clean data
    csv_path = 'data/open_opportunities_deep.csv'
    if not os.path.exists(csv_path):
        print("Error: data/open_opportunities_deep.csv not found!")
        return

    df = pd.read_csv(csv_path)
    # Ensure there are no empty descriptions which can crash the model
    df['description'] = df['description'].fillna('No description provided')

    # 2. Load the Model 
    # This will download about 100MB of weights to your local cache
    print("Downloading/Loading SentenceTransformer model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # 3. Create the Embeddings
    # We turn each 'description' into a 384-dimensional vector
    print(f"Generating embeddings for {len(df)} grants. This may take a minute...")
    descriptions = df['description'].tolist()
    embeddings = model.encode(descriptions, show_progress_bar=True)

    # 4. Save the math for the plane
    # We save as a Pickle file (.pkl) which is a binary format for Python objects
    output_path = 'data/grant_embeddings.pkl'
    with open(output_path, 'wb') as f:
        pickle.dump(embeddings, f)

    print(f"SUCCESS: {len(embeddings)} embeddings saved to {output_path}")

if __name__ == "__main__":
    generate_grant_embeddings()