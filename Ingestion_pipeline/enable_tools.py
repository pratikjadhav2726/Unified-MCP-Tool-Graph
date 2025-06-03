"""
Usage:
    python enable_tools.py tool_name1 [tool_name2 ...]

This script sets the `disabled` property to `false` for each specified tool in Neo4j.
"""
import sys
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

def enable_tools(tool_names):
    """
    Sets the `disabled` property to false for each tool in the provided list of tool names.
    Args:
        tool_names (list of str): Names of tools to re-enable in Neo4j.
    """
    with driver.session() as session:
        for name in tool_names:
            session.run(
                """
                MATCH (t:Tool {name: $tool_name})
                SET t.disabled = false
                """,
                tool_name=name
            )
    print(f"Enabled {len(tool_names)} tools.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python enable_tools.py tool_name1 [tool_name2 ...]")
        sys.exit(1)
    enable_tools(sys.argv[1:])
