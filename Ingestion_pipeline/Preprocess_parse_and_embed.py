import json
from sentence_transformers import SentenceTransformer
import numpy as np

# Load your updated JSON file
with open('Data/Glama/all_servers.json', 'r') as file:
    mcp_servers = json.load(file)

# Load lightweight local embedding model
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

tools_data = []

# Loop over each server in the list
for server in mcp_servers['data']:
        # server = server_entry.get('server', {})
        vendor_id = server.get('id')
        vendor_name = server.get('name')
        vendor_description = server.get('description', '')
        vendor_repo = server.get('repository', {}).get('url', '')
        
        tools = server.get('tools', [])
        
        # Some servers have no tools (empty list) — handle that
        if not tools:
            continue
        
        for tool in tools:
            tool_name = tool.get('name')
            tool_description = tool.get('description', '')
            
            input_schema = tool.get('inputSchema', {})
            properties = list(input_schema.get('properties', {}).keys())
            required_fields = input_schema.get('required', [])
            
            # Handle embedding
            if tool_description:
                embedding = model.encode(tool_description)
            else:
                embedding = np.zeros((384,), dtype=float)
            
            tool_record = {
                'vendor_id': vendor_id,
                'vendor_name': vendor_name,
                'vendor_description': vendor_description,
                'vendor_repo': vendor_repo,
                'tool_name': tool_name,
                'tool_description': tool_description,
                'tool_embedding': embedding.tolist(),  # Convert numpy array to list
                'tool_parameters': properties,
                'tool_required_parameters': required_fields
            }
            
            tools_data.append(tool_record)

# Save parsed output
with open('parsed_tools_with_embeddings.json', 'w') as outfile:
    json.dump(tools_data, outfile, indent=2)

print(f"Parsed and embedded {len(tools_data)} tools successfully!")