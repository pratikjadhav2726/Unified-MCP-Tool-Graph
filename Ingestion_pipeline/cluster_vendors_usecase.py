import json
import numpy as np
from ollama import Client
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer

# Load data
with open("Data/Glama/all_servers.json", "r") as f:
    mcp_servers = json.load(f)

# Load model
model = SentenceTransformer("all-MiniLM-L6-v2")

# Extract vendor metadata
vendors = []
descriptions = []
vendor_ids = []

for server in mcp_servers['data']:
        vendor_id = server.get("id")
        name = server.get("name")
        desc = server.get("description", "")
        if vendor_id and desc:
            vendors.append({
                "id": vendor_id,
                "name": name,
                "description": desc
            })
            descriptions.append(desc)
            vendor_ids.append(vendor_id)

# Create embeddings
embeddings = model.encode(descriptions)

# Clustering
n_clusters = max(20, min(len(vendors) // 40, 75))
kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
labels = kmeans.fit_predict(embeddings)
centroids = kmeans.cluster_centers_


# Attach cluster_id to each vendor using label index
for i, vendor in enumerate(vendors):
    vendor["cluster_id"] = int(labels[i])

# Generate names using Ollama (Phi4-mini)
ollama_client = Client()
cluster_names = {}

for cluster_id in range(n_clusters):
    cluster_descs = [v["description"] for v in vendors if v["cluster_id"] == cluster_id][:8]
    prompt = (
        "Here are some descriptions of tools/APIs that belong to the same category:\n\n"
        + "\n\n".join(f"- {desc}" for desc in cluster_descs)
        + "\n\nSummarize their common two use cases or functionality. Each use case should be a 3-5 words only. These are to be used by LLM. do not include any other text. Word limit 50 words.\n\n"
    )

    try:
        response = ollama_client.chat(model="phi4-mini", messages=[{"role": "user", "content": prompt}])
        cluster_name = response['message']['content'].strip()
        cluster_names[cluster_id] = cluster_name
    except Exception as e:
        cluster_names[cluster_id] = f"Cluster {cluster_id}"
        print(f"[!] Failed to name cluster {cluster_id}: {e}")



# Multi-label assignment using cosine similarity
threshold = 0.72
multi_label_map = []
similarities = cosine_similarity(embeddings, centroids)

for i, vendor in enumerate(vendors):
    matched_clusters = []
    for cluster_id, sim in enumerate(similarities[i]):
        if sim >= threshold:
            matched_clusters.append({
                "use_case_name": cluster_names.get(cluster_id, f"Cluster {cluster_id}"),
                "cluster_id": cluster_id,
                "similarity": round(float(sim), 4)
            })
    multi_label_map.append({
        "vendor_id": vendor["id"],
        "vendor_name": vendor["name"],
        "description": vendor["description"],
        "use_cases": matched_clusters
    })

# Save multi-label output
with open("multi_label_vendors.json", "w") as f:
    json.dump(multi_label_map, f, indent=2)

print(f"✅ Saved multi-label mappings for {len(multi_label_map)} vendors to multi_label_vendors.json")