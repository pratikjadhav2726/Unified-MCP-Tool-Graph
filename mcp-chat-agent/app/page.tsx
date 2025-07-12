"use client"

import { useChat } from "@ai-sdk/react"
import { ChatMessage } from "@/components/chat-message"
import { ChatInput } from "@/components/chat-input"
import { ToolPanel } from "@/components/tool-panel"
import { ServerStatus } from "@/components/server-status"
import { Header } from "@/components/header"
import { useState } from "react"

export default function ChatAgent() {
  const [showToolPanel, setShowToolPanel] = useState(true)
  const { messages, input, handleInputChange, handleSubmit, isLoading } = useChat({
    api: "/api/chat",
  })

  return (
    <div className="flex h-screen bg-background">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        <Header showToolPanel={showToolPanel} onToggleToolPanel={() => setShowToolPanel(!showToolPanel)} />

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center space-y-4">
                <div className="w-16 h-16 mx-auto bg-primary/10 rounded-full flex items-center justify-center">
                  <svg className="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                    />
                  </svg>
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-foreground">MCP Tool Graph Agent</h2>
                  <p className="text-muted-foreground">
                    Ask me anything! I'll discover and use the best tools to help you.
                  </p>
                </div>
              </div>
            </div>
          ) : (
            messages.map((message) => <ChatMessage key={message.id} message={message} />)
          )}
        </div>

        {/* Input Area */}
        <div className="border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <ChatInput
            input={input}
            handleInputChange={handleInputChange}
            handleSubmit={handleSubmit}
            isLoading={isLoading}
          />
        </div>
      </div>

      {/* Tool Panel */}
      {showToolPanel && (
        <div className="w-80 border-l bg-muted/30 flex flex-col">
          <div className="p-4 border-b">
            <h3 className="font-semibold text-foreground">System Status</h3>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <ServerStatus />
            <ToolPanel />
          </div>
        </div>
      )}
    </div>
  )
}
