import json
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load parsed JSON with embeddings
with open("Ingestion_pipeline/parsed_tools_with_embeddings.json", 'r') as f:
    tools_data = json.load(f)

# Neo4j connection settings
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

# Cypher query templates
CREATE_VENDOR_QUERY = """
MERGE (v:Vendor {id: $vendor_id})
SET v.name = $vendor_name,
    v.description = $vendor_description,
    v.repository_url = $vendor_repo
"""

CREATE_TOOL_QUERY = """
MERGE (t:Tool {name: $tool_name, vendor_id: $vendor_id})
SET t.description = $tool_description,
    t.input_parameters = $tool_parameters,
    t.required_parameters = $tool_required_parameters,
    t.embedding = $tool_embedding
"""

CREATE_RELATIONSHIP_QUERY = """
MATCH (v:Vendor {id: $vendor_id})
MATCH (t:Tool {name: $tool_name, vendor_id: $vendor_id})
MERGE (t)-[:BELONGS_TO_VENDOR]->(v)
"""

# Insert function
def insert_data(tx, record):
    # Insert Vendor
    tx.run(CREATE_VENDOR_QUERY, 
           vendor_id=record['vendor_id'],
           vendor_name=record['vendor_name'],
           vendor_description=record['vendor_description'],
           vendor_repo=record['vendor_repo'])
    
    # Insert Tool
    tx.run(CREATE_TOOL_QUERY,
           tool_name=record['tool_name'],
           tool_description=record['tool_description'],
           tool_parameters=record['tool_parameters'],
           tool_required_parameters=record['tool_required_parameters'],
           tool_embedding=record['tool_embedding'],
           vendor_id=record['vendor_id'])
    
    # Create Relationship
    tx.run(CREATE_RELATIONSHIP_QUERY,
           tool_name=record['tool_name'],
           vendor_id=record['vendor_id'])

# Main function
def main():
    with driver.session() as session:
        for record in tools_data:
            session.write_transaction(insert_data, record)
    print(f"Inserted {len(tools_data)} tools and vendors into Neo4j.")

if __name__ == "__main__":
    main()