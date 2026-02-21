import pandas as pd
from sentence_transformers import SentenceTransformer, util
import pickle
import os
import argparse
import torch

def get_tuva_readiness_score(description):
    desc_low = description.lower()
    reasons = []

    # Check 'data plumbing' requirements
    dms_keywords = ["data management", "sharing plan", "data sharing", "repository", "curation", "harmonization"]
    if any(word in desc_low for word in dms_keywords):
        reasons.append("Explicitly asks for data sharing/curation requirements.")

    # Check reproducibility need
    repro_keywords = ["reproducibility", "rigor", "validation", "standardization", "interoperable"]
    if any(word in desc_low for word in repro_keywords):
        reasons.append("Explicitly asks for reproducible data.")

    # Check if AI/ML component requested
    ai_keywords = ["ai ", "artificial intelligence", "machine learning", "predictive knowledge", "modeling", "computational tools"]
    if any(term in desc_low for term in ["predictive modeling", "machine learning", "neural", "ai usage"]):
        reasons.append("Requests AI/ML component.")

    return reasons

def run_strategic_advisory(prof_name):
    prof_name = prof_name.lower().replace(" ", "_")

    script_dir = os.path.dirname(os.path.abspath(__file__)) 
    root_dir = os.path.dirname(os.path.dirname(script_dir))
    data_dir = os.path.join(root_dir, 'data', 'similar_grants')
    embed_path = os.path.join(data_dir, 'grant_embeddings.pkl')
    csv_path = os.path.join(data_dir, 'open_opportunities_deep.csv')
    prof_folder = os.path.join(data_dir, 'profiles', prof_name)

    with open(embed_path, 'rb') as f:
        grant_embeddings = pickle.load(f)
    grant_embeddings = torch.from_numpy(grant_embeddings).to('cpu') if not torch.is_tensor(grant_embeddings) else grant_embeddings.to('cpu')
    df_grants = pd.read_csv(csv_path)
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Collect and mean-embed
    abstract_files = [f for f in os.listdir(prof_folder) if f.lower().endswith('.txt')]
    all_vectors = []
    for filename in sorted(abstract_files):
        with open(os.path.join(prof_folder, filename), 'r', encoding='utf-8') as f:
            text = f.read().strip()
            if text:
                all_vectors.append(model.encode(text, convert_to_tensor=True).to('cpu'))
    
    combined_vec = torch.mean(torch.stack(all_vectors), dim=0)
    scores = util.cos_sim(combined_vec, grant_embeddings)[0]
    df_grants['match_score'] = scores.tolist()
    
    top_matches = df_grants.sort_values(by='match_score', ascending=False).head(3)

    print(f"\n" + "="*60)
    print(f"STRATEGIC TUVA REPORT: {prof_name.upper()}")
    print("="*60)

    for i, (idx, row) in enumerate(top_matches.iterrows(), 1):
        print(f"\nRANK #{i} | Score: {row['match_score']:.4f}")
        print(f"GRANT: {row['title']}")
        
        # If applicable, list why Tuva is extra useful for these grants
        reasons = get_tuva_readiness_score(row['description'])
        if reasons:
            print(f"Tuva could be especially helpful here!")
            for reason in reasons:
                print(f"  - {reason}")

        print(f"ID: {row['opp_id']}")
        print("-" * 40)

if __name__ == "__main__":
    run_strategic_advisory("Shannon Quinn")