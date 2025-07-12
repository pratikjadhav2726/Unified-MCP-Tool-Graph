import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { User, Bot, Wrench, Server } from "lucide-react"
import type { Message } from "@ai-sdk/react"

interface ChatMessageProps {
  message: Message
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user"

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div className={`flex max-w-[80%] ${isUser ? "flex-row-reverse" : "flex-row"} items-start space-x-3`}>
        {/* Avatar */}
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center ${
            isUser ? "bg-primary ml-3" : "bg-muted mr-3"
          }`}
        >
          {isUser ? (
            <User className="w-4 h-4 text-primary-foreground" />
          ) : (
            <Bot className="w-4 h-4 text-muted-foreground" />
          )}
        </div>

        {/* Message Content */}
        <Card className={`p-4 ${isUser ? "bg-primary text-primary-foreground" : "bg-card"}`}>
          <div className="space-y-2">
            {message.parts?.map((part, i) => {
              switch (part.type) {
                case "text":
                  return (
                    <div key={`${message.id}-${i}`} className="whitespace-pre-wrap">
                      {part.text}
                    </div>
                  )
                case "tool-call":
                  return (
                    <div key={`${message.id}-${i}`} className="space-y-2">
                      <div className="flex items-center space-x-2">
                        <Wrench className="w-4 h-4" />
                        <Badge variant="secondary" className="text-xs">
                          Tool: {part.toolName}
                        </Badge>
                      </div>
                      <div className="text-sm text-muted-foreground bg-muted/50 p-2 rounded">
                        <pre className="text-xs overflow-x-auto">{JSON.stringify(part.args, null, 2)}</pre>
                      </div>
                    </div>
                  )
                case "tool-result":
                  return (
                    <div key={`${message.id}-${i}`} className="space-y-2">
                      <div className="flex items-center space-x-2">
                        <Server className="w-4 h-4" />
                        <Badge variant="outline" className="text-xs">
                          Result
                        </Badge>
                      </div>
                      <div className="text-sm bg-muted/50 p-2 rounded">
                        <pre className="text-xs overflow-x-auto">
                          {typeof part.result === "string" ? part.result : JSON.stringify(part.result, null, 2)}
                        </pre>
                      </div>
                    </div>
                  )
                default:
                  return null
              }
            })}
          </div>
        </Card>
      </div>
    </div>
  )
}
