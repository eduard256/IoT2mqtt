import { useEffect, useState, useRef } from 'react'
import { Terminal } from 'lucide-react'

interface LogEntry {
  timestamp: string
  level: string
  content: string
  color?: string
}

interface LogTerminalProps {
  containerId: string
  className?: string
}

export default function LogTerminal({ containerId, className = '' }: LogTerminalProps) {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [connected, setConnected] = useState(false)
  const terminalRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    // Connect to WebSocket for log streaming
    const wsUrl = `ws://localhost:8765/api/logs/${containerId}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      console.log('Connected to log stream')
    }

    ws.onmessage = (event) => {
      try {
        const logEntry = JSON.parse(event.data)
        setLogs(prev => [...prev, logEntry])
        
        // Auto-scroll to bottom
        if (terminalRef.current) {
          terminalRef.current.scrollTop = terminalRef.current.scrollHeight
        }
      } catch (error) {
        console.error('Error parsing log entry:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setConnected(false)
    }

    ws.onclose = () => {
      setConnected(false)
      console.log('Disconnected from log stream')
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [containerId])

  const getLogStyle = (level: string, color?: string) => {
    if (color) {
      return { color }
    }

    const colors: Record<string, string> = {
      error: '#ef4444',     // red-500
      warning: '#f59e0b',   // amber-500
      success: '#10b981',   // emerald-500
      info: '#3b82f6',      // blue-500
      debug: '#6b7280'      // gray-500
    }

    return { color: colors[level.toLowerCase()] || '#ffffff' }
  }

  const formatTimestamp = (timestamp: string) => {
    try {
      const date = new Date(timestamp)
      return date.toLocaleTimeString('en-US', { 
        hour12: false, 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit'
      })
    } catch {
      return timestamp
    }
  }

  return (
    <div className={`bg-black rounded-lg overflow-hidden ${className}`}>
      {/* Terminal Header */}
      <div className="bg-gray-800 px-4 py-2 flex items-center justify-between border-b border-gray-700">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-gray-400" />
          <span className="text-sm text-gray-400 font-mono">
            Container: {containerId}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className={`h-2 w-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-xs text-gray-400">
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Terminal Content */}
      <div 
        ref={terminalRef}
        className="p-4 h-96 overflow-y-auto font-mono text-sm leading-relaxed"
        style={{ backgroundColor: '#0d1117' }}
      >
        {logs.length === 0 ? (
          <div className="text-gray-500">Waiting for logs...</div>
        ) : (
          logs.map((log, index) => (
            <div key={index} className="whitespace-pre-wrap break-all">
              <span className="text-gray-500">[{formatTimestamp(log.timestamp)}]</span>
              {' '}
              <span 
                className="font-semibold uppercase"
                style={getLogStyle(log.level, log.color)}
              >
                [{log.level.padEnd(7)}]
              </span>
              {' '}
              <span className="text-gray-300">{log.content}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}