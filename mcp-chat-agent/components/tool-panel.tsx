"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Wrench, Search, Clock, Globe, Brain } from "lucide-react"
import { useState } from "react"

interface Tool {
  name: string
  server: string
  description: string
  category: string
  lastUsed?: string
  usageCount: number
}

export function ToolPanel() {
  const [availableTools, setAvailableTools] = useState<Tool[]>([
    {
      name: "web_search",
      server: "tavily-mcp",
      description: "Search the web for current information",
      category: "search",
      lastUsed: "2 minutes ago",
      usageCount: 15,
    },
    {
      name: "think_step_by_step",
      server: "sequential-thinking",
      description: "Break down complex problems into steps",
      category: "reasoning",
      lastUsed: "15 minutes ago",
      usageCount: 8,
    },
    {
      name: "get_current_time",
      server: "time-mcp",
      description: "Get current date and time information",
      category: "utility",
      lastUsed: "1 minute ago",
      usageCount: 23,
    },
    {
      name: "get_timezone_info",
      server: "time-mcp",
      description: "Get timezone information for locations",
      category: "utility",
      usageCount: 5,
    },
  ])

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case "search":
        return <Search className="w-3 h-3" />
      case "reasoning":
        return <Brain className="w-3 h-3" />
      case "utility":
        return <Clock className="w-3 h-3" />
      default:
        return <Wrench className="w-3 h-3" />
    }
  }

  const getCategoryColor = (category: string) => {
    switch (category) {
      case "search":
        return "bg-blue-500/10 text-blue-700 border-blue-200"
      case "reasoning":
        return "bg-purple-500/10 text-purple-700 border-purple-200"
      case "utility":
        return "bg-green-500/10 text-green-700 border-green-200"
      default:
        return "bg-gray-500/10 text-gray-700 border-gray-200"
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center space-x-2">
          <Wrench className="w-4 h-4" />
          <span>Available Tools</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {availableTools.map((tool) => (
          <div key={`${tool.server}-${tool.name}`} className="space-y-2 p-2 rounded-lg border bg-card/50">
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-2">
                {getCategoryIcon(tool.category)}
                <span className="text-sm font-medium">{tool.name}</span>
              </div>
              <Badge variant="outline" className={`text-xs ${getCategoryColor(tool.category)}`}>
                {tool.category}
              </Badge>
            </div>

            <p className="text-xs text-muted-foreground">{tool.description}</p>

            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span className="flex items-center space-x-1">
                <Globe className="w-3 h-3" />
                <span>{tool.server}</span>
              </span>
              <div className="flex items-center space-x-2">
                <span>Used: {tool.usageCount}x</span>
                {tool.lastUsed && <span>• {tool.lastUsed}</span>}
              </div>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
