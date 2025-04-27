from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Neo4j driver
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

# Retrieval function
def retrieve_top_k_tools(embedding, top_k=3):
    with driver.session() as session:
        result = session.run(
            """
            WITH $embedding AS queryEmbedding
            CALL db.index.vector.queryNodes('tool_vector_index', $topK, queryEmbedding)
            YIELD node, score
            MATCH (node)-[:BELONGS_TO_VENDOR]->(vendor:Vendor)
            RETURN 
                node.name AS tool_name,
                node.description AS tool_description,
                node.input_parameters AS input_parameters,
                node.required_parameters AS required_parameters,
                vendor.name AS vendor_name,
                vendor.repository_url AS vendor_repository_url,
                vendor.required_env_keys AS vendor_required_env_keys,
                score
            ORDER BY score DESC
            """,
            embedding=embedding,
            topK=top_k
        )
        return [record.data() for record in result]