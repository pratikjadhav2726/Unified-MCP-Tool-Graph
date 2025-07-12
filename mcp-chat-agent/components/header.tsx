"use client"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { PanelRightOpen, PanelRightClose, Activity } from "lucide-react"

interface HeaderProps {
  showToolPanel: boolean
  onToggleToolPanel: () => void
}

export function Header({ showToolPanel, onToggleToolPanel }: HeaderProps) {
  return (
    <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex items-center justify-between p-4">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
            <Activity className="w-4 h-4 text-primary-foreground" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-foreground">MCP Tool Graph Agent</h1>
            <div className="flex items-center space-x-2">
              <Badge variant="secondary" className="text-xs">
                Dynamic Tool Discovery
              </Badge>
              <Badge variant="outline" className="text-xs">
                MCP Orchestration
              </Badge>
            </div>
          </div>
        </div>

        <Button variant="ghost" size="sm" onClick={onToggleToolPanel} className="flex items-center space-x-2">
          {showToolPanel ? (
            <>
              <PanelRightClose className="w-4 h-4" />
              <span className="hidden sm:inline">Hide Panel</span>
            </>
          ) : (
            <>
              <PanelRightOpen className="w-4 h-4" />
              <span className="hidden sm:inline">Show Panel</span>
            </>
          )}
        </Button>
      </div>
    </header>
  )
}
