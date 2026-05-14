"use client"

import { useState, useEffect, useCallback } from 'react'
import { BookOpen, Play, Loader2, Copy, Check, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { useStore } from '@/lib/store'
import { getEndpoints, healthCheck } from '@/lib/api'

interface ApiEndpoint {
  id: string
  path: string
  method: string
  status: number
  generated: boolean
  generated_code?: string
  sample_request?: {
    url: string
    headers: Record<string, string>
    body: string | null
    query_params: Record<string, string>
  }
  sample_responses?: Array<{
    status: number
    body: string | null
    content_type: string | null
  }>
}

export function ApiDocs() {
  const { endpoints } = useStore()
  const [selectedEndpoint, setSelectedEndpoint] = useState<string | null>(null)
  const [requestBody, setRequestBody] = useState('')
  const [response, setResponse] = useState<{ status: number; data: unknown; time: number } | null>(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)
  const [backendEndpoints, setBackendEndpoints] = useState<ApiEndpoint[]>([])
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking')

  useEffect(() => {
    const check = async () => {
      const isHealthy = await healthCheck()
      setBackendStatus(isHealthy ? 'online' : 'offline')
      if (isHealthy) {
        try {
          const data = await getEndpoints()
          setBackendEndpoints(data.endpoints || [])
        } catch {
          setBackendEndpoints([])
        }
      }
    }
    check()
  }, [endpoints])

  const displayEndpoints = backendEndpoints.length > 0 ? backendEndpoints : endpoints.map(ep => ({
    id: ep.id,
    path: ep.path,
    method: ep.method,
    status: ep.status,
    generated: ep.generated,
  }))

  const currentEndpoint = displayEndpoints.find(ep => ep.id === selectedEndpoint)

  useEffect(() => {
    const ep = displayEndpoints.find(e => e.id === selectedEndpoint) as ApiEndpoint | undefined
    if (!ep) return
    if (ep.sample_request?.body) {
      try {
        const parsed = JSON.parse(ep.sample_request.body)
        setRequestBody(JSON.stringify(parsed, null, 2))
      } catch {
        setRequestBody(ep.sample_request.body)
      }
    } else {
      setRequestBody('')
    }
    setResponse(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedEndpoint])

  const sendRequest = useCallback(async () => {
    if (!currentEndpoint) return
    setLoading(true)
    setResponse(null)

    const ep = currentEndpoint as ApiEndpoint
    const startTime = performance.now()

    try {
      if (backendStatus === 'online') {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        const fetchOptions: RequestInit = {
          method: ep.method,
          headers: { 'Content-Type': 'application/json' },
        }
        if (['POST', 'PUT', 'PATCH'].includes(ep.method) && requestBody) {
          fetchOptions.body = requestBody
        }
        const res = await fetch(`${apiBase}${ep.path}`, fetchOptions)
        const elapsed = Math.round(performance.now() - startTime)
        let data: unknown
        const text = await res.text()
        try {
          data = JSON.parse(text)
        } catch {
          data = text
        }
        setResponse({ status: res.status, data, time: elapsed })
      } else {
        await new Promise(resolve => setTimeout(resolve, 800))
        const sampleResp = ep.sample_responses?.[0]
        const elapsed = Math.round(performance.now() - startTime)
        let data: unknown = {}
        if (sampleResp?.body) {
          try {
            data = JSON.parse(sampleResp.body)
          } catch {
            data = sampleResp.body
          }
        }
        setResponse({
          status: sampleResp?.status || 200,
          data,
          time: elapsed,
        })
      }
    } catch (error) {
      const elapsed = Math.round(performance.now() - startTime)
      setResponse({
        status: 0,
        data: { error: String(error) },
        time: elapsed,
      })
    } finally {
      setLoading(false)
    }
  }, [currentEndpoint, requestBody, backendStatus])

  const copyResponse = () => {
    navigator.clipboard.writeText(JSON.stringify(response?.data, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const getMethodColor = (method: string) => {
    switch (method.toUpperCase()) {
      case 'GET': return 'bg-green-500/20 text-green-400'
      case 'POST': return 'bg-blue-500/20 text-blue-400'
      case 'PUT': return 'bg-yellow-500/20 text-yellow-400'
      case 'DELETE': return 'bg-red-500/20 text-red-400'
      case 'PATCH': return 'bg-purple-500/20 text-purple-400'
      default: return 'bg-gray-500/20 text-gray-400'
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="bg-card rounded-xl border border-border overflow-hidden">
        <div className="p-4 border-b border-border">
          <h3 className="font-semibold flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-primary" />
            API Endpoints
            {backendStatus === 'online' && (
              <span className="text-xs text-green-500 ml-auto">Live</span>
            )}
          </h3>
        </div>

        <div className="divide-y divide-border max-h-[600px] overflow-y-auto">
          {displayEndpoints.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              {backendStatus === 'offline' ? (
                <div className="flex flex-col items-center gap-2">
                  <AlertCircle className="w-8 h-8 text-yellow-500" />
                  <span>Backend offline</span>
                  <span className="text-xs">Start brain.py to see live endpoints</span>
                </div>
              ) : (
                'No endpoints detected. Upload a HAR file first.'
              )}
            </div>
          ) : (
            displayEndpoints.map((ep) => (
              <button
                key={ep.id}
                className={cn(
                  "w-full p-4 text-left hover:bg-accent/50 transition-colors",
                  selectedEndpoint === ep.id && "bg-primary/10 border-l-2 border-primary"
                )}
                onClick={() => setSelectedEndpoint(ep.id)}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className={cn("px-2 py-0.5 rounded text-xs font-bold", getMethodColor(ep.method))}>
                    {ep.method}
                  </span>
                  {ep.generated && (
                    <span className="w-2 h-2 bg-green-500 rounded-full" />
                  )}
                </div>
                <p className="font-mono text-sm">{ep.path}</p>
                <p className="text-xs text-muted-foreground mt-1">Status: {ep.status}</p>
              </button>
            ))
          )}
        </div>
      </div>

      <div className="lg:col-span-2 space-y-4">
        {currentEndpoint && (
          <div className="bg-card rounded-xl border border-border p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">Endpoint Details</h3>
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-4 p-4 bg-accent/50 rounded-lg">
                <span className={cn("px-3 py-1 rounded font-bold", getMethodColor(currentEndpoint.method))}>
                  {currentEndpoint.method}
                </span>
                <code className="font-mono">{currentEndpoint.path}</code>
              </div>

              {['POST', 'PUT', 'PATCH'].includes(currentEndpoint.method) && (
                <div>
                  <label className="block text-sm font-medium mb-2">Request Body</label>
                  <textarea
                    value={requestBody}
                    onChange={(e) => setRequestBody(e.target.value)}
                    className="w-full h-32 p-3 bg-black/30 border border-border rounded-lg font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                    placeholder='{"key": "value"}'
                  />
                </div>
              )}

              <Button
                className="w-full"
                onClick={sendRequest}
                disabled={loading}
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Sending Request...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 mr-2" />
                    Send Request
                  </>
                )}
              </Button>
            </div>
          </div>
        )}

        {response && (
          <div className="bg-card rounded-xl border border-border p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <h3 className="font-semibold">Response</h3>
                <span className={cn(
                  "px-2 py-0.5 rounded text-sm",
                  response.status >= 200 && response.status < 300 && "bg-green-500/20 text-green-400",
                  response.status >= 400 && "bg-red-500/20 text-red-400",
                  response.status === 0 && "bg-red-500/20 text-red-400",
                )}>
                  {response.status === 0 ? 'Error' : response.status}
                </span>
                <span className="text-sm text-muted-foreground">{response.time}ms</span>
              </div>
              <Button size="sm" variant="ghost" onClick={copyResponse}>
                {copied ? (
                  <Check className="w-4 h-4 text-green-500" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </Button>
            </div>

            <pre className="bg-black/30 p-4 rounded-lg overflow-x-auto text-sm">
              <code className="text-green-400 font-mono">
                {JSON.stringify(response.data, null, 2)}
              </code>
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}
