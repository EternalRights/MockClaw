"use client"

import { useState, useEffect } from 'react'
import { BookOpen, Play, Loader2, Copy, Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

// Mock OpenAPI spec
const mockSpec = {
  openapi: '3.0.0',
  info: {
    title: 'MockClaw Generated API',
    version: '0.1.0',
    description: 'Auto-generated mock API endpoints',
  },
  servers: [{ url: 'http://localhost:4000' }],
  paths: {
    '/health': {
      get: {
        summary: 'Health Check',
        responses: {
          '200': {
            description: 'Service is healthy',
            content: {
              'application/json': {
                example: { status: 'OK', service: 'MockClaw' },
              },
            },
          },
        },
      },
    },
    '/mockclaw/info': {
      get: {
        summary: 'Get MockClaw Info',
        responses: {
          '200': {
            description: 'MockClaw metadata',
            content: {
              'application/json': {
                example: {
                  generator: 'MockClaw',
                  version: '0.1.0',
                  endpoints: [],
                },
              },
            },
          },
        },
      },
    },
    '/api/login': {
      post: {
        summary: 'User Login',
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                properties: {
                  username: { type: 'string' },
                  password: { type: 'string' },
                },
              },
              example: { username: 'testuser', password: 'secret123' },
            },
          },
        },
        responses: {
          '200': {
            description: 'Login successful',
            content: {
              'application/json': {
                example: {
                  token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
                  user: { id: 1, username: 'testuser', email: 'test@example.com' },
                },
              },
            },
          },
        },
      },
    },
    '/api/users/{id}': {
      get: {
        summary: 'Get User by ID',
        parameters: [
          {
            name: 'id',
            in: 'path',
            required: true,
            schema: { type: 'integer' },
            example: 123,
          },
        ],
        responses: {
          '200': {
            description: 'User data',
            content: {
              'application/json': {
                example: {
                  id: 123,
                  name: 'John Doe',
                  email: 'john@example.com',
                  profile: { bio: 'Software Engineer' },
                },
              },
            },
          },
        },
      },
    },
  },
}

export function ApiDocs() {
  const [selectedEndpoint, setSelectedEndpoint] = useState<string>('/health')
  const [requestBody, setRequestBody] = useState('')
  const [response, setResponse] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  const endpoints = Object.entries(mockSpec.paths)
  const currentEndpoint = endpoints.find(([path]) => path === selectedEndpoint)

  useEffect(() => {
    if (currentEndpoint) {
      const [, methods] = currentEndpoint
      const method = Object.values(methods)[0] as any
      if (method.requestBody?.content?.['application/json']?.example) {
        setRequestBody(JSON.stringify(method.requestBody.content['application/json'].example, null, 2))
      } else if (method.responses?.['200']?.content?.['application/json']?.example) {
        setRequestBody('')
      }
    }
  }, [selectedEndpoint])

  const sendRequest = async () => {
    setLoading(true)
    setResponse(null)

    // Simulate request
    await new Promise(resolve => setTimeout(resolve, 1500))

    const method = Object.values(currentEndpoint![1])[0] as any
    const exampleResponse = method.responses?.['200']?.content?.['application/json']?.example

    setResponse({
      status: 200,
      data: exampleResponse,
      time: Math.floor(Math.random() * 500) + 100,
    })

    setLoading(false)
  }

  const copyResponse = () => {
    navigator.clipboard.writeText(JSON.stringify(response?.data, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Endpoints List */}
      <div className="bg-card rounded-xl border border-border overflow-hidden">
        <div className="p-4 border-b border-border">
          <h3 className="font-semibold flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-primary" />
            API Endpoints
          </h3>
        </div>

        <div className="divide-y divide-border max-h-[600px] overflow-y-auto">
          {endpoints.map(([path, methods]) => {
            const [method, details] = Object.entries(methods)[0] as [string, any]
            return (
              <button
                key={path}
                className={cn(
                  "w-full p-4 text-left hover:bg-accent/50 transition-colors",
                  selectedEndpoint === path && "bg-primary/10 border-l-2 border-primary"
                )}
                onClick={() => setSelectedEndpoint(path)}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className={cn(
                    "px-2 py-0.5 rounded text-xs font-bold",
                    method === 'GET' && "bg-green-500/20 text-green-400",
                    method === 'POST' && "bg-blue-500/20 text-blue-400",
                    method === 'PUT' && "bg-yellow-500/20 text-yellow-400",
                    method === 'DELETE' && "bg-red-500/20 text-red-400",
                  )}>
                    {method}
                  </span>
                </div>
                <p className="font-mono text-sm">{path}</p>
                <p className="text-xs text-muted-foreground mt-1">{details.summary}</p>
              </button>
            )
          })}
        </div>
      </div>

      {/* Request/Response Panel */}
      <div className="lg:col-span-2 space-y-4">
        {/* Endpoint Details */}
        {currentEndpoint && (
          <div className="bg-card rounded-xl border border-border p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">Endpoint Details</h3>
            </div>

            <div className="space-y-4">
              {/* Method & Path */}
              <div className="flex items-center gap-4 p-4 bg-accent/50 rounded-lg">
                <span className={cn(
                  "px-3 py-1 rounded font-bold",
                  Object.keys(currentEndpoint[1])[0] === 'GET' && "bg-green-500/20 text-green-400",
                  Object.keys(currentEndpoint[1])[0] === 'POST' && "bg-blue-500/20 text-blue-400",
                )}>
                  {Object.keys(currentEndpoint[1])[0]}
                </span>
                <code className="font-mono">{selectedEndpoint}</code>
              </div>

              {/* Request Body (if applicable) */}
              {Object.values(currentEndpoint[1])[0]?.requestBody && (
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

              {/* Send Button */}
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

        {/* Response */}
        {response && (
          <div className="bg-card rounded-xl border border-border p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <h3 className="font-semibold">Response</h3>
                <span className={cn(
                  "px-2 py-0.5 rounded text-sm",
                  response.status === 200 && "bg-green-500/20 text-green-400",
                  response.status >= 400 && "bg-red-500/20 text-red-400",
                )}>
                  {response.status}
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
