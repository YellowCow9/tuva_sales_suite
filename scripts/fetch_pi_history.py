import requests
import os

def fetch_pi_data(pi_name):
    pi_id = pi_name.lower().replace(' ', '_')
    folder_path = f"data/profiles/{pi_id}"
    os.makedirs(folder_path, exist_ok=True)
    
    # 1. TRY NIH REPORTER (For R01 leads)
    nih_url = "https://api.reporter.nih.gov/v2/projects/search"
    nih_payload = {
        "criteria": {"pi_names": [{"any_name": pi_name}]},
        "include_fields": ["ProjectTitle", "AbstractText"],
        "limit": 5
    }
    
    print(f"Checking NIH for {pi_name}...")
    nih_res = requests.post(nih_url, json=nih_payload).json()
    projects = nih_res.get('results', [])

    # 2. TRY NSF API (If NIH is empty)
    if not projects:
        print(f"No NIH projects found. Checking NSF...")
        name_parts = pi_name.split()
        first, last = name_parts[0], name_parts[-1]
        nsf_url = f"https://www.research.gov/awardapi-service/v1/awards.json?piFirstName={first}&piLastName={last}&printFields=id,title,abstractText"
        nsf_res = requests.get(nsf_url).json()
        projects = nsf_res.get('response', {}).get('award', [])
        
        for i, proj in enumerate(projects):
            with open(os.path.join(folder_path, f"nsf_award_{i}.txt"), 'w') as f:
                f.write(f"Title: {proj.get('title')}\n\n{proj.get('abstractText', 'No abstract')}")

    # 3. PLAN C: SEMANTIC SCHOLAR (If both Gov APIs fail)
    if not projects:
        print(f"No Federal awards found. Falling back to Semantic Scholar for {pi_name}...")
        # Search for author to get their S2ID
        s2_search_url = f"https://api.semanticscholar.org/graph/v1/author/search?query={pi_name}&fields=name,papers.title,papers.abstract,papers.year"
        s2_res = requests.get(s2_search_url).json()
        
        authors = s2_res.get('data', [])
        if authors:
            # We take the first author result and their 5 most recent papers
            top_author = authors[0]
            papers = sorted(top_author.get('papers', []), key=lambda x: x.get('year', 0), reverse=True)[:5]
            
            for i, paper in enumerate(papers):
                if paper.get('abstract'):
                    with open(os.path.join(folder_path, f"paper_abstract_{i}.txt"), 'w') as f:
                        f.write(f"Title: {paper.get('title')}\n\n{paper.get('abstract')}")
            print(f"✅ Found {len(papers)} recent paper abstracts on Semantic Scholar.")
            return

    # SAVE NIH RESULTS (If found in Step 1)
    if projects and not os.listdir(folder_path): # Only if NSF wasn't already saved
        for i, proj in enumerate(projects):
            with open(os.path.join(folder_path, f"nih_abstract_{i}.txt"), 'w') as f:
                f.write(f"Title: {proj.get('project_title')}\n\n{proj.get('abstract_text')}")
    
    if not projects and not os.listdir(folder_path):
        print(f"Total failure: {pi_name} has no recent Federal awards or Public abstracts.")

if __name__ == "__main__":
    fetch_pi_data("Shannon Quinn")