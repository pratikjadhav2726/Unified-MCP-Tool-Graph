#!/usr/bin/env node
/**
 * Node.js Client Example for Unified MCP Gateway
 * 
 * This example demonstrates how to interact with the Unified MCP Gateway
 * using Node.js. It shows various usage patterns including:
 * 
 * - Authentication
 * - Tool discovery
 * - Tool invocation
 * - Error handling
 * - Health monitoring
 * - Dynamic tool retrieval
 */

const axios = require('axios');
const { performance } = require('perf_hooks');

class UnifiedMCPClient {
    /**
     * Node.js client for the Unified MCP Gateway.
     * 
     * This client provides a convenient interface for interacting with
     * the gateway API, including authentication, error handling, and
     * response processing.
     */
    
    constructor(config = {}) {
        this.config = {
            baseURL: 'http://localhost:8000',
            timeout: 30000,
            apiKey: null,
            ...config
        };
        
        // Configure axios instance
        this.client = axios.create({
            baseURL: this.config.baseURL,
            timeout: this.config.timeout,
            headers: {
                'Content-Type': 'application/json',
                ...(this.config.apiKey && { 'Authorization': `Bearer ${this.config.apiKey}` })
            }
        });
        
        // Add response interceptor for error handling
        this.client.interceptors.response.use(
            response => response,
            error => {
                if (error.response) {
                    // Server responded with error status
                    const status = error.response.status;
                    const message = error.response.data?.error || error.message;
                    
                    if (status === 429) {
                        const retryAfter = error.response.headers['retry-after'] || '60';
                        throw new Error(`Rate limited. Retry after ${retryAfter} seconds`);
                    }
                    
                    throw new Error(`HTTP ${status}: ${message}`);
                } else if (error.request) {
                    // Network error
                    throw new Error(`Network error: ${error.message}`);
                } else {
                    // Other error
                    throw new Error(`Request error: ${error.message}`);
                }
            }
        );
        
        console.log(`Connected to gateway at ${this.config.baseURL}`);
    }
    
    /**
     * Get basic gateway information.
     */
    async getInfo() {
        const response = await this.client.get('/');
        return response.data;
    }
    
    /**
     * Get comprehensive health status.
     */
    async healthCheck() {
        const response = await this.client.get('/health');
        return response.data;
    }
    
    /**
     * List all available tools.
     */
    async listTools() {
        const response = await this.client.get('/tools');
        return response.data.tools || [];
    }
    
    /**
     * List all configured servers.
     */
    async listServers() {
        const response = await this.client.get('/servers');
        return response.data.servers || {};
    }
    
    /**
     * Call a specific tool.
     */
    async callTool(toolName, arguments = {}) {
        const response = await this.client.post('/call', {
            tool: toolName,
            arguments: arguments
        });
        return response.data.result;
    }
    
    /**
     * Retrieve relevant tools for a task.
     */
    async retrieveTools(taskDescription, topK = 3, officialOnly = false) {
        const response = await this.client.post('/retrieve-tools', {
            task_description: taskDescription,
            top_k: topK,
            official_only: officialOnly
        });
        return response.data.tools || [];
    }
    
    /**
     * Wait for the gateway to become healthy.
     */
    async waitForHealthy(maxWait = 60, checkInterval = 5) {
        const startTime = performance.now();
        
        while ((performance.now() - startTime) / 1000 < maxWait) {
            try {
                const health = await this.healthCheck();
                if (health.status === 'healthy') {
                    console.log('Gateway is healthy');
                    return true;
                } else {
                    console.log(`Gateway status: ${health.status}`);
                }
            } catch (error) {
                console.warn(`Health check failed: ${error.message}`);
            }
            
            await new Promise(resolve => setTimeout(resolve, checkInterval * 1000));
        }
        
        console.error(`Gateway did not become healthy within ${maxWait} seconds`);
        return false;
    }
}

/**
 * Demonstrate basic gateway usage.
 */
async function demoBasicUsage() {
    console.log('=== Basic Usage Demo ===');
    
    const client = new UnifiedMCPClient({
        baseURL: 'http://localhost:8000',
        // apiKey: 'your-api-key-here'  // Uncomment if authentication is enabled
    });
    
    try {
        // Get gateway info
        const info = await client.getInfo();
        console.log(`Gateway: ${info.name} v${info.version}`);
        
        // Check health
        const health = await client.healthCheck();
        console.log(`Health Status: ${health.status}`);
        console.log(`Total Tools: ${health.metrics.total_tools}`);
        console.log(`Healthy Servers: ${health.metrics.healthy_servers}/${health.metrics.total_servers}`);
        
        // List available tools
        const tools = await client.listTools();
        console.log(`\nAvailable Tools (${tools.length}):`);
        
        tools.slice(0, 5).forEach(tool => {
            const description = tool.description.length > 60 
                ? tool.description.substring(0, 60) + '...'
                : tool.description;
            console.log(`  - ${tool.name}: ${description}`);
        });
        
        if (tools.length > 5) {
            console.log(`  ... and ${tools.length - 5} more tools`);
        }
        
    } catch (error) {
        console.error(`Basic usage demo failed: ${error.message}`);
    }
}

/**
 * Demonstrate tool invocation.
 */
async function demoToolInvocation() {
    console.log('\n=== Tool Invocation Demo ===');
    
    const client = new UnifiedMCPClient();
    
    try {
        // Find a time tool
        const tools = await client.listTools();
        const timeTool = tools.find(tool => tool.name.toLowerCase().includes('time'));
        
        if (timeTool) {
            console.log(`Calling tool: ${timeTool.name}`);
            try {
                const result = await client.callTool(timeTool.name, { timezone: 'UTC' });
                console.log(`Result: ${JSON.stringify(result, null, 2)}`);
            } catch (error) {
                console.log(`Tool call failed: ${error.message}`);
            }
        } else {
            console.log('No time tool found');
        }
        
        // Try calling a non-existent tool
        console.log('\nTrying to call non-existent tool...');
        try {
            await client.callTool('non.existent.tool');
        } catch (error) {
            console.log(`Expected error: ${error.message}`);
        }
        
    } catch (error) {
        console.error(`Tool invocation demo failed: ${error.message}`);
    }
}

/**
 * Demonstrate dynamic tool retrieval.
 */
async function demoToolRetrieval() {
    console.log('\n=== Tool Retrieval Demo ===');
    
    const client = new UnifiedMCPClient();
    
    try {
        // Retrieve tools for web search
        console.log("Retrieving tools for: 'search the web for AI news'");
        const webTools = await client.retrieveTools('search the web for AI news', 3, false);
        
        console.log(`Found ${webTools.length} relevant tools:`);
        webTools.forEach(tool => {
            const description = (tool.tool_description || 'No description').length > 60
                ? (tool.tool_description || 'No description').substring(0, 60) + '...'
                : (tool.tool_description || 'No description');
            console.log(`  - ${tool.tool_name || 'Unknown'}: ${description}`);
        });
        
        // Retrieve tools for file operations
        console.log("\nRetrieving tools for: 'read and process files'");
        const fileTools = await client.retrieveTools('read and process files', 2);
        
        console.log(`Found ${fileTools.length} relevant tools:`);
        fileTools.forEach(tool => {
            const description = (tool.tool_description || 'No description').length > 60
                ? (tool.tool_description || 'No description').substring(0, 60) + '...'
                : (tool.tool_description || 'No description');
            console.log(`  - ${tool.tool_name || 'Unknown'}: ${description}`);
        });
        
    } catch (error) {
        console.error(`Tool retrieval demo failed: ${error.message}`);
    }
}

/**
 * Demonstrate error handling.
 */
async function demoErrorHandling() {
    console.log('\n=== Error Handling Demo ===');
    
    const client = new UnifiedMCPClient();
    
    const errorTests = [
        {
            name: 'Invalid tool call',
            test: () => client.callTool('invalid.tool')
        },
        {
            name: 'Empty task description',
            test: () => client.retrieveTools('')
        },
        {
            name: 'Malformed request',
            test: async () => {
                await client.client.post('/call', { invalid: 'data' });
            }
        }
    ];
    
    for (const { name, test } of errorTests) {
        console.log(`\nTesting: ${name}`);
        try {
            await test();
            console.log('  ✗ Expected error but got success');
        } catch (error) {
            console.log(`  ✓ Caught expected error: ${error.message}`);
        }
    }
}

/**
 * Demonstrate monitoring capabilities.
 */
async function demoMonitoring() {
    console.log('\n=== Monitoring Demo ===');
    
    const client = new UnifiedMCPClient();
    
    try {
        // Get detailed health information
        const health = await client.healthCheck();
        
        console.log('System Health:');
        console.log(`  Overall Status: ${health.status}`);
        console.log(`  Timestamp: ${health.timestamp}`);
        
        // System component health
        const system = health.components.system;
        console.log(`  System Status: ${system.overall_status}`);
        console.log(`  Orphaned Processes: ${system.orphaned_processes}`);
        
        // Tool retriever health
        const retriever = health.components.tool_retriever;
        console.log(`  Tool Retriever Status: ${retriever.status}`);
        
        const realRetriever = retriever.retrievers.real;
        const dummyRetriever = retriever.retrievers.dummy;
        console.log(`    Real Retriever: ${realRetriever.available ? '✓' : '✗'} (${realRetriever.enabled ? 'enabled' : 'disabled'})`);
        console.log(`    Dummy Retriever: ${dummyRetriever.available ? '✓' : '✗'} (${dummyRetriever.enabled ? 'enabled' : 'disabled'})`);
        
        // Server health
        const servers = health.components.servers;
        console.log('  Server Health:');
        Object.entries(servers).forEach(([serverName, serverInfo]) => {
            const statusIcon = serverInfo.status === 'healthy' ? '✓' : '✗';
            console.log(`    ${serverName}: ${statusIcon} ${serverInfo.status}`);
        });
        
    } catch (error) {
        console.error(`Monitoring demo failed: ${error.message}`);
    }
}

/**
 * Demonstrate a complete workflow.
 */
async function demoCompleteWorkflow() {
    console.log('\n=== Complete Workflow Demo ===');
    
    const client = new UnifiedMCPClient();
    
    try {
        // Wait for gateway to be ready
        console.log('Waiting for gateway to be healthy...');
        const isHealthy = await client.waitForHealthy(30);
        if (!isHealthy) {
            console.log('Gateway is not healthy, continuing anyway...');
        }
        
        // Step 1: Discover available capabilities
        console.log('\n1. Discovering available tools...');
        const tools = await client.listTools();
        const servers = await client.listServers();
        
        console.log(`   Found ${tools.length} tools across ${Object.keys(servers).length} servers`);
        
        // Step 2: Find relevant tools for a task
        console.log("\n2. Finding tools for task: 'get current time information'");
        const relevantTools = await client.retrieveTools('get current time information', 3);
        
        console.log(`   Found ${relevantTools.length} relevant tools`);
        
        // Step 3: Execute a tool
        console.log('\n3. Executing a tool...');
        
        // Find a time-related tool from discovered tools
        const timeTool = tools.find(tool => tool.name.toLowerCase().includes('time'));
        
        if (timeTool) {
            try {
                const result = await client.callTool(timeTool.name, { timezone: 'UTC' });
                console.log(`   Tool '${timeTool.name}' result: ${JSON.stringify(result, null, 2)}`);
            } catch (error) {
                console.log(`   Tool execution failed: ${error.message}`);
            }
        } else {
            console.log('   No time tool available for execution');
        }
        
        // Step 4: Monitor system health
        console.log('\n4. Checking system health...');
        const health = await client.healthCheck();
        
        const healthyServers = health.metrics.healthy_servers;
        const totalServers = health.metrics.total_servers;
        const totalTools = health.metrics.total_tools;
        
        console.log(`   System Status: ${health.status}`);
        console.log(`   Servers: ${healthyServers}/${totalServers} healthy`);
        console.log(`   Tools: ${totalTools} available`);
        
        console.log('\n✓ Workflow completed successfully!');
        
    } catch (error) {
        console.error(`Complete workflow demo failed: ${error.message}`);
    }
}

/**
 * Performance benchmarking demo.
 */
async function demoBenchmark() {
    console.log('\n=== Performance Benchmark Demo ===');
    
    const client = new UnifiedMCPClient();
    
    try {
        const benchmarks = [
            { name: 'Health Check', test: () => client.healthCheck() },
            { name: 'List Tools', test: () => client.listTools() },
            { name: 'List Servers', test: () => client.listServers() },
            { name: 'Tool Retrieval', test: () => client.retrieveTools('test query', 1) }
        ];
        
        console.log('Running performance benchmarks...');
        
        for (const { name, test } of benchmarks) {
            const iterations = 5;
            const times = [];
            
            for (let i = 0; i < iterations; i++) {
                const startTime = performance.now();
                try {
                    await test();
                    const endTime = performance.now();
                    times.push(endTime - startTime);
                } catch (error) {
                    console.log(`  ${name}: Error - ${error.message}`);
                    break;
                }
            }
            
            if (times.length > 0) {
                const avgTime = times.reduce((a, b) => a + b, 0) / times.length;
                const minTime = Math.min(...times);
                const maxTime = Math.max(...times);
                
                console.log(`  ${name}:`);
                console.log(`    Average: ${avgTime.toFixed(2)}ms`);
                console.log(`    Min: ${minTime.toFixed(2)}ms`);
                console.log(`    Max: ${maxTime.toFixed(2)}ms`);
            }
        }
        
    } catch (error) {
        console.error(`Benchmark demo failed: ${error.message}`);
    }
}

/**
 * Main function to run all demonstrations.
 */
async function main() {
    console.log('Unified MCP Gateway - Node.js Client Demo');
    console.log('='.repeat(50));
    
    try {
        await demoBasicUsage();
        await demoToolInvocation();
        await demoToolRetrieval();
        await demoErrorHandling();
        await demoMonitoring();
        await demoCompleteWorkflow();
        await demoBenchmark();
        
        console.log('\n' + '='.repeat(50));
        console.log('All demos completed successfully!');
        
    } catch (error) {
        console.error(`\nDemo failed with error: ${error.message}`);
        console.error('Stack trace:', error.stack);
    }
}

// Export for use as a module
module.exports = { UnifiedMCPClient };

// Run demos if called directly
if (require.main === module) {
    main().catch(error => {
        console.error('Fatal error:', error);
        process.exit(1);
    });
}