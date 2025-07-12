"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Server, Activity, Clock, Zap } from "lucide-react"
import { useState } from "react"

interface MCPServer {
  name: string
  status: "running" | "idle" | "starting" | "stopped"
  uptime: string
  toolCount: number
  lastUsed: string
}

export function ServerStatus() {
  const [servers, setServers] = useState<MCPServer[]>([
    {
      name: "tavily-mcp",
      status: "running",
      uptime: "2h 15m",
      toolCount: 3,
      lastUsed: "2 minutes ago",
    },
    {
      name: "sequential-thinking",
      status: "idle",
      uptime: "45m",
      toolCount: 2,
      lastUsed: "15 minutes ago",
    },
    {
      name: "time-mcp",
      status: "running",
      uptime: "1h 30m",
      toolCount: 4,
      lastUsed: "1 minute ago",
    },
  ])

  const getStatusIcon = (status: MCPServer["status"]) => {
    switch (status) {
      case "running":
        return <Activity className="w-3 h-3 text-green-500" />
      case "idle":
        return <Clock className="w-3 h-3 text-yellow-500" />
      case "starting":
        return <Zap className="w-3 h-3 text-blue-500 animate-pulse" />
      case "stopped":
        return <Server className="w-3 h-3 text-gray-500" />
    }
  }

  const getStatusColor = (status: MCPServer["status"]) => {
    switch (status) {
      case "running":
        return "bg-green-500/10 text-green-700 border-green-200"
      case "idle":
        return "bg-yellow-500/10 text-yellow-700 border-yellow-200"
      case "starting":
        return "bg-blue-500/10 text-blue-700 border-blue-200"
      case "stopped":
        return "bg-gray-500/10 text-gray-700 border-gray-200"
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center space-x-2">
          <Server className="w-4 h-4" />
          <span>MCP Servers</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {servers.map((server) => (
          <div key={server.name} className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                {getStatusIcon(server.status)}
                <span className="text-sm font-medium">{server.name}</span>
              </div>
              <Badge variant="outline" className={`text-xs ${getStatusColor(server.status)}`}>
                {server.status}
              </Badge>
            </div>
            <div className="text-xs text-muted-foreground space-y-1">
              <div className="flex justify-between">
                <span>Uptime:</span>
                <span>{server.uptime}</span>
              </div>
              <div className="flex justify-between">
                <span>Tools:</span>
                <span>{server.toolCount}</span>
              </div>
              <div className="flex justify-between">
                <span>Last used:</span>
                <span>{server.lastUsed}</span>
              </div>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
