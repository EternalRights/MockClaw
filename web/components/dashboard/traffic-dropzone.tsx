"use client"

import { useCallback, useState, useEffect } from 'react'
import { Upload, FileJson, CheckCircle2, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useStore } from '@/lib/store'
import { parseHarFile, healthCheck } from '@/lib/api'

export function TrafficDropzone() {
  const [isDragging, setIsDragging] = useState(false)
  const [clawAnimation, setClawAnimation] = useState(false)
  const [matrixChars, setMatrixChars] = useState<Array<{ id: number; char: string; delay: number }>>([])
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking')
  const { harFile, setHarFile, isProcessing, setProcessing, addEndpoints, clearEndpoints } = useStore()

  // Check backend health on mount
  useEffect(() => {
    const checkHealth = async () => {
      const isHealthy = await healthCheck()
      setBackendStatus(isHealthy ? 'online' : 'offline')
    }
    checkHealth()
  }, [])

  const handleFile = useCallback(async (file: File) => {
    if (!file.name.endsWith('.har')) {
      alert('Please upload a .har file')
      return
    }

    setHarFile(file)
    setProcessing(true)
    setClawAnimation(true)
    clearEndpoints()

    // Start matrix effect
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%^&*()'
    const newChars = Array.from({ length: 30 }, (_, i) => ({
      id: Date.now() + i,
      char: chars[Math.floor(Math.random() * chars.length)],
      delay: i * 0.1,
    }))
    setMatrixChars(newChars)

    try {
      // Call real API
      const result = await parseHarFile(file)
      
      // Add endpoints to store
      addEndpoints(result.endpoints.map((ep: any) => ({
        id: ep.id,
        path: ep.path,
        method: ep.method,
        status: ep.status,
        generated: false,
        generating: false,
      })))

    } catch (error) {
      console.error('Parse error:', error)
      alert('Failed to parse HAR file. Check backend is running on port 8000.')
    } finally {
      setProcessing(false)
      setMatrixChars([])
      setClawAnimation(false)
    }
  }, [setHarFile, setProcessing, addEndpoints, clearEndpoints])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  return (
    <div className="space-y-4">
      {/* Backend Status */}
      <div className="flex items-center gap-2 text-sm">
        <div className={cn(
          "w-2 h-2 rounded-full",
          backendStatus === 'checking' && "bg-yellow-500 animate-pulse",
          backendStatus === 'online' && "bg-green-500",
          backendStatus === 'offline' && "bg-red-500"
        )} />
        <span className="text-muted-foreground">
          Backend: {backendStatus === 'online' ? 'Connected' : backendStatus === 'offline' ? 'Offline (start brain.py)' : 'Checking...'}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Dropzone */}
        <div
          className={cn(
            "relative border-2 border-dashed rounded-xl p-8 transition-all duration-300",
            isDragging 
              ? "border-primary bg-primary/10 scale-[1.02]" 
              : "border-border hover:border-primary/50",
            clawAnimation && "pulse-glow"
          )}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={onDrop}
        >
          {/* Claw Icon */}
          <div className={cn(
            "flex flex-col items-center justify-center py-12 transition-transform duration-500",
            clawAnimation && "claw-animate"
          )}>
            <div className={cn(
              "p-6 rounded-full bg-card mb-6 transition-all",
              isDragging && "bg-primary/20 scale-110"
            )}>
              {isProcessing ? (
                <Loader2 className="w-16 h-16 text-primary animate-spin" />
              ) : harFile ? (
                <CheckCircle2 className="w-16 h-16 text-green-500" />
              ) : (
                <Upload className={cn(
                  "w-16 h-16 transition-colors",
                  isDragging ? "text-primary" : "text-muted-foreground"
                )} />
              )}
            </div>

            <h3 className="text-xl font-semibold mb-2">
              {isProcessing ? 'Processing...' : harFile ? 'HAR File Loaded!' : 'Drop HAR File Here'}
            </h3>
            
            <p className="text-muted-foreground text-center max-w-sm">
              {isProcessing 
                ? 'Analyzing HTTP traffic patterns...'
                : harFile 
                  ? `Loaded: ${harFile.name}`
                  : 'Drag and drop a .har file or click to browse'
              }
            </p>

            <input
              type="file"
              accept=".har"
              className="absolute inset-0 opacity-0 cursor-pointer"
              onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
              disabled={backendStatus !== 'online'}
            />
          </div>

          {/* Claw Animation Overlay */}
          {clawAnimation && (
            <div className="absolute top-4 right-4">
              <FileJson className="w-8 h-8 text-primary animate-pulse" />
            </div>
          )}
        </div>

        {/* Matrix Stream */}
        <div className="bg-card rounded-xl p-6 border border-border overflow-hidden">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              Live URL Detection
            </h3>
            <span className="text-xs text-muted-foreground">
              {isProcessing ? 'Streaming...' : 'Idle'}
            </span>
          </div>

          <div className="h-64 overflow-hidden relative bg-black/30 rounded-lg p-4">
            {/* Matrix Rain Effect */}
            {matrixChars.map((item) => (
              <span
                key={item.id}
                className="matrix-char text-green-500 font-mono text-sm"
                style={{ 
                  animationDuration: '2s',
                  animationDelay: `${item.delay}s`,
                  position: 'absolute',
                  left: `${(item.id % 10) * 10}%`,
                }}
              >
                {item.char}
              </span>
            ))}

            {/* Detected Endpoints */}
            <div className="space-y-2 relative z-10">
              {useStore.getState().endpoints.slice(0, 6).map((endpoint, i) => (
                <div 
                  key={endpoint.id}
                  className="flex items-center gap-3 font-mono text-sm"
                  style={{ animationDelay: `${i * 0.2}s` }}
                >
                  <span className={cn(
                    "px-2 py-0.5 rounded text-xs font-bold",
                    endpoint.method === 'POST' ? "bg-blue-500/20 text-blue-400" :
                    endpoint.method === 'GET' ? "bg-green-500/20 text-green-400" :
                    endpoint.method === 'PUT' ? "bg-yellow-500/20 text-yellow-400" :
                    endpoint.method === 'DELETE' ? "bg-red-500/20 text-red-400" :
                    "bg-gray-500/20 text-gray-400"
                  )}>
                    {endpoint.method}
                  </span>
                  <span className="text-muted-foreground">{endpoint.path}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
