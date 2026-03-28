"use client"

import { useEffect, useRef } from 'react'
import { Play, CheckCircle2, Loader2, Terminal, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useStore, type Endpoint } from '@/lib/store'
import { Button } from '@/components/ui/button'

export function MockFactory() {
  const { endpoints, updateEndpoint, logs, addLog, clearLogs } = useStore()
  const terminalRef = useRef<HTMLDivElement>(null)

  // Auto-scroll logs
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [logs])

  const generateMock = async (endpoint: Endpoint) => {
    updateEndpoint(endpoint.id, { generating: true })
    
    // Simulate LLM thinking process
    const thinkingSteps = [
      { delay: 500, level: 'thinking' as const, msg: 'Analyzing HTTP request/response schema...' },
      { delay: 1000, level: 'thinking' as const, msg: 'Extracting field types and validation rules...' },
      { delay: 1500, level: 'thinking' as const, msg: 'Generating Pydantic models...' },
      { delay: 2000, level: 'info' as const, msg: 'Configuring Faker providers for realistic data...' },
      { delay: 2500, level: 'info' as const, msg: 'Writing FastAPI route handler...' },
      { delay: 3000, level: 'success' as const, msg: `Generated mock for ${endpoint.method} ${endpoint.path}` },
    ]

    for (const step of thinkingSteps) {
      await new Promise(resolve => setTimeout(resolve, step.delay))
      addLog({ timestamp: new Date().toLocaleTimeString(), level: step.level, message: step.msg })
    }

    updateEndpoint(endpoint.id, { generating: false, generated: true })
  }

  const generateAll = async () => {
    clearLogs()
    addLog({ timestamp: new Date().toLocaleTimeString(), level: 'info', message: 'Starting batch generation for all endpoints...' })
    
    for (const endpoint of endpoints.filter(e => !e.generated)) {
      await generateMock(endpoint)
      await new Promise(resolve => setTimeout(resolve, 500))
    }
    
    addLog({ timestamp: new Date().toLocaleTimeString(), level: 'success', message: 'Batch generation complete!' })
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
            Detected Endpoints
          </h3>
          <Button size="sm" onClick={generateAll} disabled={endpoints.filter(e => !e.generated).length === 0}>
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
                      onClick={() => generateMock(endpoint)}
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
