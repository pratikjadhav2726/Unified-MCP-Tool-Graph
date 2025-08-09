"""
Provides functionality to retrieve tool information from a Neo4j graph database
using vector similarity search.

This module relies on environment variables for Neo4j connection details:
- NEO4J_URI: The URI for the Neo4j instance.
- NEO4J_USER: The username for Neo4j authentication.
- NEO4J_PASSWORD: The password for Neo4j authentication.

If Neo4j is not available, it will fallback to a dummy response.
"""

from neo4j import GraphDatabase
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Initialize Neo4j driver with error handling
driver = None
neo4j_available = False

try:
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USER")
    neo4j_password = os.getenv("NEO4J_PASSWORD")
    
    if neo4j_uri and neo4j_user and neo4j_password:
        driver = GraphDatabase.driver(
            neo4j_uri,
            auth=(neo4j_user, neo4j_password)
        )
        # Test connection
        with driver.session() as session:
            session.run("RETURN 1")
        neo4j_available = True
        logger.info("Neo4j connection established successfully")
    else:
        logger.warning("Neo4j environment variables not set, using fallback mode")
except Exception as e:
    logger.warning(f"Neo4j connection failed: {e}, using fallback mode")
    neo4j_available = False

def get_fallback_tools(top_k: int = 3) -> list[dict]:
    """
    Fallback function that returns dummy tools when Neo4j is not available.
    
    Args:
        top_k: The number of tools to return (limited to available dummy tools)
        
    Returns:
        A list of dummy tool dictionaries
    """
    dummy_tools = [
        {
            "tool_name": "web_search",
            "tool_description": "Search the web for information using a search engine",
            "input_parameters": {"query": "string", "max_results": "integer"},
            "required_parameters": ["query"],
            "vendor_name": "Everything Server",
            "vendor_repository_url": "https://github.com/modelcontextprotocol/servers",
            "score": 0.95
        },
        {
            "tool_name": "read_file",
            "tool_description": "Read the contents of a file from the filesystem",
            "input_parameters": {"path": "string"},
            "required_parameters": ["path"],
            "vendor_name": "Everything Server",
            "vendor_repository_url": "https://github.com/modelcontextprotocol/servers",
            "score": 0.90
        },
        {
            "tool_name": "write_file",
            "tool_description": "Write content to a file on the filesystem",
            "input_parameters": {"path": "string", "content": "string"},
            "required_parameters": ["path", "content"],
            "vendor_name": "Everything Server",
            "vendor_repository_url": "https://github.com/modelcontextprotocol/servers",
            "score": 0.85
        }
    ]
    
    return dummy_tools[:min(top_k, len(dummy_tools))]

# Retrieval function
def retrieve_top_k_tools(embedding: list[float], top_k: int = 3, official_only: bool = False, official_boost: float = 1.2) -> list[dict]:
    """
    Retrieves the top K tools from the Neo4j database based on the similarity
    of their embeddings to the provided query embedding.

    If Neo4j is not available, returns fallback dummy tools.

    The function queries a vector index named 'tool_vector_index'.

    Args:
        embedding: A list of floats representing the query embedding.
        top_k: The number of top similar tools to retrieve. Defaults to 3.
        official_only: If set to True, restricts the results to only official servers.
        official_boost: A boost factor for the similarity score of official servers. Defaults to 1.2.

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
    if not neo4j_available or not driver:
        logger.info("Using fallback tools (Neo4j not available)")
        return get_fallback_tools(top_k)
    
    try:
        with driver.session() as session:
            cypher = """
            WITH $embedding AS queryEmbedding, $officialBoost AS boost
            CALL db.index.vector.queryNodes('tool_vector_index', $topK, queryEmbedding)
            YIELD node, score AS base_score
            MATCH (node)-[:BELONGS_TO_VENDOR]->(vendor:Vendor)
            WHERE (COALESCE(node.disabled, false) = false)
            """
            if official_only:
                cypher += " AND (COALESCE(vendor.is_official, false) = true OR COALESCE(node.is_official, false) = true)"
            cypher += """
            WITH node, vendor, base_score,
                 CASE WHEN (COALESCE(vendor.is_official, false) = true OR COALESCE(node.is_official, false) = true) THEN base_score * boost ELSE base_score END AS score
            RETURN 
                node.name AS tool_name,
                node.description AS tool_description,
                node.input_parameters AS input_parameters,
                node.required_parameters AS required_parameters,
                vendor.name AS vendor_name,
                vendor.repository_url AS vendor_repository_url,
                score
            ORDER BY score DESC
            """
            result = session.run(
                cypher,
                embedding=embedding,
                topK=top_k,
                officialBoost=official_boost
            )
            return [record.data() for record in result]
    except Exception as e:
        logger.error(f"Neo4j query failed: {e}, falling back to dummy tools")
        return get_fallback_tools(top_k)