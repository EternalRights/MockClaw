"use client"

import { useEffect, useRef } from 'react'
import { Play, CheckCircle2, Loader2, Terminal, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useStore, type Endpoint } from '@/lib/store'
import { Button } from '@/components/ui/button'
import { generateMock, generateAll as apiGenerateAll } from '@/lib/api'

export function MockFactory() {
  const { endpoints, updateEndpoint, logs, addLog, clearLogs } = useStore()
  const terminalRef = useRef<HTMLDivElement>(null)

  // Auto-scroll logs
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [logs])

  const generateEndpoint = async (endpoint: Endpoint) => {
    updateEndpoint(endpoint.id, { generating: true })
    
    try {
      const result = await generateMock(endpoint.id)
      
      // Add logs from API
      result.logs.forEach((log: any) => {
        addLog({ timestamp: log.timestamp, level: log.level, message: log.message })
      })

      updateEndpoint(endpoint.id, { generating: false, generated: result.success })
    } catch (error) {
      addLog({ 
        timestamp: new Date().toLocaleTimeString(), 
        level: 'error', 
        message: `Failed to generate ${endpoint.path}: ${error}` 
      })
      updateEndpoint(endpoint.id, { generating: false })
    }
  }

  const generateAllEndpoints = async () => {
    clearLogs()
    addLog({ timestamp: new Date().toLocaleTimeString(), level: 'info', message: 'Starting batch generation...' })
    
    try {
      const result = await apiGenerateAll()
      addLog({ 
        timestamp: new Date().toLocaleTimeString(), 
        level: 'success', 
        message: `Generated ${result.generated_count} endpoints!` 
      })
      
      // Refresh endpoints from backend
      const { getEndpoints } = await import('@/lib/api')
      const endpointsData = await getEndpoints()
      // Update store...
      
    } catch (error) {
      addLog({ timestamp: new Date().toLocaleTimeString(), level: 'error', message: String(error) })
    }
  }

  const getMethodColor = (method: string) => {
    switch (method) {
      case 'GET': return 'bg-green-500/20 text-green-400'
      case 'POST': return 'bg-blue-500/20 text-blue-400'
      case 'PUT': return 'bg-yellow-500/20 text-yellow-400'
      case 'DELETE': return 'bg-red-500/20 text-red-400'
      case 'PATCH': return 'bg-purple-500/20 text-purple-400'
      default: return 'bg-gray-500/20 text-gray-400'
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Endpoints Table */}
      <div className="bg-card rounded-xl border border-border overflow-hidden">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h3 className="font-semibold flex items-center gap-2">
            <Zap className="w-5 h-5 text-primary" />
            Detected Endpoints ({endpoints.length})
          </h3>
          <Button 
            size="sm" 
            onClick={generateAllEndpoints} 
            disabled={endpoints.filter(e => !e.generated).length === 0}
          >
            Generate All
          </Button>
        </div>

        <div className="divide-y divide-border">
          {endpoints.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              No endpoints detected. Upload a HAR file first.
            </div>
          ) : (
            endpoints.map((endpoint) => (
              <div key={endpoint.id} className="p-4 flex items-center justify-between hover:bg-accent/50 transition-colors">
                <div className="flex items-center gap-3">
                  <span className={cn("px-2 py-0.5 rounded text-xs font-bold", getMethodColor(endpoint.method))}>
                    {endpoint.method}
                  </span>
                  <span className="font-mono text-sm">{endpoint.path}</span>
                </div>
                
                <div className="flex items-center gap-2">
                  {endpoint.generated ? (
                    <div className="flex items-center gap-2 text-green-500">
                      <CheckCircle2 className="w-4 h-4" />
                      <span className="text-sm">Generated</span>
                    </div>
                  ) : (
                    <Button
                      size="sm"
                      onClick={() => generateEndpoint(endpoint)}
                      disabled={endpoint.generating}
                    >
                      {endpoint.generating ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                          Generating
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4 mr-1" />
                          Generate
                        </>
                      )}
                    </Button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Terminal Logs */}
      <div className="bg-card rounded-xl border border-border overflow-hidden">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h3 className="font-semibold flex items-center gap-2">
            <Terminal className="w-5 h-5 text-green-500" />
            Generation Logs
          </h3>
          <Button size="sm" variant="ghost" onClick={clearLogs}>
            Clear
          </Button>
        </div>

        <div 
          ref={terminalRef}
          className="h-96 overflow-y-auto bg-black/50 p-4 font-mono text-sm"
        >
          {logs.length === 0 ? (
            <div className="text-muted-foreground">
              Logs will appear here when generating mocks...
            </div>
          ) : (
            logs.map((log, i) => (
              <div key={i} className="flex gap-3 mb-1">
                <span className="text-muted-foreground">[{log.timestamp}]</span>
                <span className={cn(
                  log.level === 'success' && 'text-green-500',
                  log.level === 'error' && 'text-red-500',
                  log.level === 'thinking' && 'text-yellow-500',
                  log.level === 'info' && 'text-blue-400',
                )}>
                  {log.message}
                </span>
                {log.level === 'thinking' && (
                  <span className="terminal-cursor text-primary">_</span>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
