import json
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

# Load multi-label vendors
with open("Ingestion_pipeline/multi_label_vendors.json", "r") as f:
    vendors = json.load(f)

# Neo4j connection
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

# Insert query for vendor and use case relationship
def insert_vendor_usecase(tx, vendor, use_case):
    tx.run("""
        MERGE (v:Vendor {id: $vendor_id})
        SET v.name = $vendor_name, v.description = $vendor_description

        MERGE (u:UseCase {cluster_id: $cluster_id})
        SET u.name = $use_case_name

        MERGE (v)-[:BELONGS_TO_USECASE {similarity: $similarity}]->(u)
    """, {
        "vendor_id": vendor["vendor_id"],
        "vendor_name": vendor["vendor_name"],
        "vendor_description": vendor["description"],
        "cluster_id": use_case["cluster_id"],
        "use_case_name": use_case["use_case_name"],
        "similarity": use_case["similarity"]
    })

# Ingest into Neo4j
with driver.session() as session:
    for vendor in vendors:
        for use_case in vendor.get("use_cases", []):
            session.write_transaction(insert_vendor_usecase, vendor, use_case)

print(f"✅ Inserted {len(vendors)} vendors and use case relationships into Neo4j.")
driver.close()