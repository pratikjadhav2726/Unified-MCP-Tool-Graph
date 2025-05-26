"""
Provides functionality to retrieve tool information from a Neo4j graph database
using vector similarity search.

This module relies on environment variables for Neo4j connection details:
- NEO4J_URI: The URI for the Neo4j instance.
- NEO4J_USER: The username for Neo4j authentication.
- NEO4J_PASSWORD: The password for Neo4j authentication.
"""

from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Neo4j driver
# This driver instance is used to connect to and interact with the Neo4j database.
# Connection parameters (URI, user, password) are fetched from environment variables.
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

# Retrieval function
def retrieve_top_k_tools(embedding: list[float], top_k: int = 3) -> list[dict]:
    """
    Retrieves the top K tools from the Neo4j database based on the similarity
    of their embeddings to the provided query embedding.

    The function queries a vector index named 'tool_vector_index'.

    Args:
        embedding: A list of floats representing the query embedding.
        top_k: The number of top similar tools to retrieve. Defaults to 3.

    Returns:
        A list of dictionaries, where each dictionary represents a tool
        and contains the following keys:
        - 'tool_name': Name of the tool.
        - 'tool_description': Description of the tool.
        - 'input_parameters': Input parameters of the tool.
        - 'required_parameters': Required parameters for the tool.
        - 'vendor_name': Name of the vendor who provides the tool.
        - 'vendor_repository_url': Repository URL of the vendor.
        - 'score': The similarity score between the tool's embedding and the query embedding.
                 Higher scores indicate greater similarity.
        The list is ordered by score in descending order.
    """
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
                score
            ORDER BY score DESC
            """,
            embedding=embedding,
            topK=top_k
        )
        return [record.data() for record in result]