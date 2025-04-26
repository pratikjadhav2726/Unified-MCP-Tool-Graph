from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

def retrieve_top_k_tools(embedding, top_k=3):
    with driver.session() as session:
        result = session.run(
            """
            WITH $embedding AS queryEmbedding
            CALL db.index.vector.queryNodes('tool_vector_index', $topK, queryEmbedding)
            YIELD node, score
            RETURN node.name AS tool_name,
                   node.description AS tool_description,
                   node.vendor_github AS vendor_github,
                   node.required_env_keys AS required_env_keys,
                   node.mcp_server_url AS vendor_mcp_url
            ORDER BY score DESC
            """,
            embedding=embedding,
            topK=top_k
        )
        return [record.data() for record in result]