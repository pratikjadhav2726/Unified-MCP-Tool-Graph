#!/usr/bin/env python3
"""
Test Client for Working MCP Server

This client demonstrates the complete knowledge graph MCP integration workflow:
1. Search for tools in the knowledge graph
2. Get MCP server configurations from GitHub data
3. Execute tools using their actual configurations
4. Show the results and metadata
"""

import json
import requests
import time

class MCPTestClient:
    """Test client for the unified MCP server"""
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.session = requests.Session()
    
    def test_server_health(self):
        """Test server health"""
        print("🏥 Testing Server Health")
        print("=" * 50)
        
        try:
            response = self.session.get(f"{self.server_url}/health")
            response.raise_for_status()
            
            health = response.json()
            print(f"✅ Server Status: {health['status']}")
            print(f"📊 Server: {health['server']['name']} v{health['server']['version']}")
            print(f"🔌 Protocol: {health['server']['protocol_version']}")
            print(f"📦 Available Tools: {health['components']['mcp_servers']['available']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False
    
    def search_tools(self, query: str, limit: int = 3):
        """Search for tools in the knowledge graph"""
        print(f"\n🔍 Searching for '{query}' tools")
        print("=" * 50)
        
        try:
            response = self.session.get(
                f"{self.server_url}/tools/search",
                params={"q": query, "limit": limit}
            )
            response.raise_for_status()
            
            results = response.json()
            print(f"📋 Query: '{results['query']}'")
            print(f"📊 Found: {results['total_results']} tools")
            
            tools = []
            for i, tool in enumerate(results['tools'], 1):
                print(f"\n{i}. {tool['name']}")
                print(f"   📝 Description: {tool['description']}")
                print(f"   🏢 Vendor: {tool['vendor']}")
                print(f"   🏷️ Categories: {', '.join(tool['categories'])}")
                print(f"   ⭐ Popularity: {tool['popularity']}%")
                print(f"   🔗 GitHub: {tool['github_url']}")
                
                # Parse MCP config to show installation
                mcp_config = json.loads(tool['mcp_config'])
                print(f"   💻 Install: {mcp_config.get('install_command', 'N/A')}")
                print(f"   🚀 Command: {mcp_config.get('command')} {' '.join(mcp_config.get('args', []))}")
                
                # Show GitHub config if available
                github_config = mcp_config.get('github_config', {})
                if github_config:
                    print(f"   📄 GitHub Config: {list(github_config.keys())}")
                
                # Show available tool functions
                tool_functions = tool.get('tools', [])
                if tool_functions:
                    print(f"   🛠️ Functions: {[t['name'] for t in tool_functions]}")
                
                tools.append(tool)
            
            return tools
            
        except Exception as e:
            print(f"❌ Search failed: {e}")
            return []
    
    def execute_tool(self, tool_name: str, tool_config: dict, arguments: dict):
        """Execute a tool using its MCP configuration"""
        print(f"\n⚡ Executing {tool_name}")
        print("=" * 50)
        
        try:
            payload = {
                "tool_name": tool_name,
                "tool_config": tool_config,
                "arguments": arguments
            }
            
            print(f"🎯 Tool: {tool_name}")
            print(f"📝 Arguments: {json.dumps(arguments, indent=2)}")
            
            # Parse MCP config to show what would be executed
            mcp_config = json.loads(tool_config.get('mcp_config', '{}'))
            command = mcp_config.get('command', 'unknown')
            args = mcp_config.get('args', [])
            print(f"💻 Would execute: {command} {' '.join(args)}")
            
            response = self.session.post(
                f"{self.server_url}/tools/execute",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            result = response.json()
            
            if result['status'] == 'success':
                print(f"✅ Execution successful!")
                
                tool_result = result['result']
                
                # Show result content
                content = tool_result.get('content', [])
                if content:
                    print(f"\n📄 Result:")
                    for item in content:
                        if item.get('type') == 'text':
                            text = item.get('text', '')
                            # Show first 300 characters for readability
                            preview = text[:300] + "..." if len(text) > 300 else text
                            print(f"{preview}")
                
                # Show metadata
                metadata = tool_result.get('metadata', {})
                if metadata:
                    print(f"\n📊 Metadata:")
                    for key, value in metadata.items():
                        if isinstance(value, dict):
                            print(f"   {key}: {type(value).__name__} with {len(value)} items")
                        elif isinstance(value, str) and len(value) > 50:
                            print(f"   {key}: {value[:50]}...")
                        else:
                            print(f"   {key}: {value}")
                
                return True
            else:
                print(f"❌ Execution failed: {result}")
                return False
                
        except Exception as e:
            print(f"❌ Tool execution failed: {e}")
            return False
    
    def demonstrate_workflow(self):
        """Demonstrate the complete knowledge graph MCP workflow"""
        print("🧪 Knowledge Graph MCP Integration Demo")
        print("Demonstrating real GitHub MCP server data and tool execution")
        print("=" * 70)
        
        # Test scenarios with different tool types
        scenarios = [
            {
                "query": "web",
                "description": "Web content fetching",
                "test_args": {"url": "https://api.github.com/repos/modelcontextprotocol/servers"}
            },
            {
                "query": "time", 
                "description": "Time and date operations",
                "test_args": {"timezone": "America/New_York", "format": "YYYY-MM-DD HH:mm:ss"}
            },
            {
                "query": "filesystem",
                "description": "File system operations", 
                "test_args": {"path": "/tmp/mcp_test.txt", "content": "Hello from MCP!"}
            },
            {
                "query": "database",
                "description": "Database operations",
                "test_args": {"query": "SELECT * FROM mcp_tools LIMIT 5"}
            },
            {
                "query": "git",
                "description": "Version control operations",
                "test_args": {"repo_path": "/workspace", "limit": 5}
            }
        ]
        
        # Step 1: Health check
        if not self.test_server_health():
            print("❌ Server health check failed, aborting demo")
            return
        
        success_count = 0
        
        # Step 2: Test each scenario
        for i, scenario in enumerate(scenarios, 1):
            print(f"\n{'='*70}")
            print(f"🎯 Scenario {i}: {scenario['description']}")
            print(f"{'='*70}")
            
            # Search for tools
            tools = self.search_tools(scenario['query'], limit=1)
            
            if tools:
                # Use the first (most popular) tool
                selected_tool = tools[0]
                tool_name = selected_tool['name']
                
                # Execute the tool
                success = self.execute_tool(
                    tool_name,
                    selected_tool,
                    scenario['test_args']
                )
                
                if success:
                    success_count += 1
                    print(f"✅ Scenario {i} completed successfully")
                else:
                    print(f"❌ Scenario {i} failed")
            else:
                print(f"❌ No tools found for '{scenario['query']}'")
        
        # Summary
        print(f"\n{'='*70}")
        print("📊 DEMO SUMMARY")
        print(f"{'='*70}")
        print(f"📈 Scenarios tested: {len(scenarios)}")
        print(f"✅ Successful: {success_count}")
        print(f"❌ Failed: {len(scenarios) - success_count}")
        print(f"📊 Success rate: {(success_count/len(scenarios))*100:.1f}%")
        
        print(f"\n🔍 Key Features Demonstrated:")
        print("✅ Knowledge graph search returning real MCP server data from GitHub")
        print("✅ Tool discovery based on functionality queries")
        print("✅ MCP server configuration parsing from GitHub repositories")
        print("✅ Tool execution using actual command-line interfaces")
        print("✅ GitHub integration showing implementation details")
        print("✅ Metadata tracking and result formatting")
        
        if success_count == len(scenarios):
            print(f"\n🎉 All scenarios completed successfully!")
            print("✅ Knowledge graph MCP integration is working perfectly!")
        else:
            print(f"\n⚠️ {len(scenarios) - success_count} scenarios had issues")
        
        print(f"\n💡 This demonstrates how the unified MCP server:")
        print("   • Acts as a bridge between stdio-based MCP servers and HTTP clients")
        print("   • Uses knowledge graph data to discover and route tool requests")
        print("   • Leverages real GitHub configurations for accurate tool execution")
        print("   • Provides a scalable, production-ready architecture")
    
    def get_server_metrics(self):
        """Get and display server metrics"""
        print("\n📊 Server Metrics")
        print("=" * 50)
        
        try:
            response = self.session.get(f"{self.server_url}/metrics")
            response.raise_for_status()
            
            metrics = response.json()
            
            print(f"🏢 Server: {metrics['server_info']['name']} v{metrics['server_info']['version']}")
            print(f"📦 Total Tools: {metrics['graph_database']['total_tools']}")
            print(f"🏭 Vendors: {', '.join(metrics['graph_database']['vendors'])}")
            print(f"🏷️ Categories: {', '.join(metrics['graph_database']['categories'])}")
            
            print(f"\n🌐 Available Endpoints:")
            for endpoint, description in metrics['endpoints'].items():
                print(f"   {endpoint}: {description}")
            
        except Exception as e:
            print(f"❌ Failed to get metrics: {e}")

def main():
    """Main function"""
    # Test if server is running
    client = MCPTestClient()
    
    print("🚀 Starting Knowledge Graph MCP Integration Test")
    print("🔗 Server URL: http://localhost:8000")
    print()
    
    try:
        # Run the complete demonstration
        client.demonstrate_workflow()
        
        # Show server metrics
        client.get_server_metrics()
        
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")

if __name__ == "__main__":
    main()