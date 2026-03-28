"use client"

import { useState, useEffect } from 'react'
import { Box, Play, Square, RotateCcw, FileText, Cpu, MemoryStick, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { useStore, type Container } from '@/lib/store'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

// Mock container data
const mockContainers: Container[] = [
  {
    id: 'mockclaw_1',
    name: 'mockclaw_instance_1',
    image: 'mockclaw/server:latest',
    status: 'running',
    cpu: 12.5,
    memory: 256,
    ports: ['4000:80', '4001:443'],
  },
  {
    id: 'mockclaw_2',
    name: 'mockclaw_instance_2',
    image: 'mockclaw/server:latest',
    status: 'running',
    cpu: 8.3,
    memory: 128,
    ports: ['4002:80'],
  },
  {
    id: 'mockclaw_3',
    name: 'mockclaw_brain',
    image: 'mockclaw/brain:latest',
    status: 'stopped',
    cpu: 0,
    memory: 0,
    ports: ['8000:8000'],
  },
]

const COLORS = {
  running: '#22c55e',
  stopped: '#ef4444',
  restarting: '#f59e0b',
}

export function DockerLab() {
  const { containers, setContainers, updateContainer } = useStore()
  const [selectedContainer, setSelectedContainer] = useState<Container | null>(null)
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  useEffect(() => {
    // Simulate loading containers
    setLoading(true)
    setTimeout(() => {
      setContainers(mockContainers)
      setLoading(false)
    }, 1000)
  }, [setContainers])

  const refreshContainers = () => {
    setLoading(true)
    setTimeout(() => {
      setContainers(mockContainers.map(c => ({
        ...c,
        cpu: Math.random() * 20,
        memory: 100 + Math.random() * 200,
      })))
      setLoading(false)
    }, 1500)
  }

  const handleAction = async (container: Container, action: 'start' | 'stop' | 'restart') => {
    setActionLoading(container.id)
    
    // Simulate action
    await new Promise(resolve => setTimeout(resolve, 1500))
    
    if (action === 'start') {
      updateContainer(container.id, { status: 'running', cpu: 10, memory: 128 })
    } else if (action === 'stop') {
      updateContainer(container.id, { status: 'stopped', cpu: 0, memory: 0 })
    } else if (action === 'restart') {
      updateContainer(container.id, { status: 'restarting', cpu: 5, memory: 64 })
      setTimeout(() => {
        updateContainer(container.id, { status: 'running', cpu: 12, memory: 256 })
      }, 2000)
    }
    
    setActionLoading(null)
  }

  const chartData = containers.map(c => ({
    name: c.name.split('_').slice(-1)[0],
    cpu: c.cpu,
    memory: c.memory / 10, // Scale for visualization
  }))

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-3">
          <Box className="w-8 h-8 text-primary" />
          Docker Control Plane
        </h2>
        <Button variant="outline" size="sm" onClick={refreshContainers} disabled={loading}>
          <RefreshCw className={cn("w-4 h-4 mr-2", loading && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {loading && containers.length === 0 ? (
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-48 bg-card rounded-xl animate-pulse" />
          ))}
        </div>
      ) : (
        <>
          {/* Stats Overview */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-card rounded-xl p-4 border border-border">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <Box className="w-5 h-5 text-primary" />
                </div>
                <span className="text-muted-foreground">Total Containers</span>
              </div>
              <p className="text-3xl font-bold">{containers.length}</p>
            </div>
            
            <div className="bg-card rounded-xl p-4 border border-border">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-green-500/10 rounded-lg">
                  <Play className="w-5 h-5 text-green-500" />
                </div>
                <span className="text-muted-foreground">Running</span>
              </div>
              <p className="text-3xl font-bold text-green-500">
                {containers.filter(c => c.status === 'running').length}
              </p>
            </div>

            <div className="bg-card rounded-xl p-4 border border-border">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-red-500/10 rounded-lg">
                  <Square className="w-5 h-5 text-red-500" />
                </div>
                <span className="text-muted-foreground">Stopped</span>
              </div>
              <p className="text-3xl font-bold text-red-500">
                {containers.filter(c => c.status === 'stopped').length}
              </p>
            </div>

            <div className="bg-card rounded-xl p-4 border border-border">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-yellow-500/10 rounded-lg">
                  <Cpu className="w-5 h-5 text-yellow-500" />
                </div>
                <span className="text-muted-foreground">Avg CPU</span>
              </div>
              <p className="text-3xl font-bold">
                {containers.length > 0 
                  ? (containers.reduce((acc, c) => acc + c.cpu, 0) / containers.length).toFixed(1)
                  : 0}%
              </p>
            </div>
          </div>

          {/* Charts */}
          <div className="bg-card rounded-xl p-6 border border-border">
            <h3 className="font-semibold mb-4">Resource Usage</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <XAxis dataKey="name" stroke="#888" />
                  <YAxis stroke="#888" />
                  <Tooltip 
                    contentStyle={{ 
                      background: 'hsl(240 10% 3.9%)', 
                      border: '1px solid hsl(240 3.7% 15.9%)',
                      borderRadius: '8px'
                    }}
                  />
                  <Bar dataKey="cpu" fill="#6366f1" radius={[4, 4, 0, 0]}>
                    {chartData.map((_, index) => (
                      <Cell key={index} fill={COLORS.running} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Container List */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {containers.map((container) => (
              <div 
                key={container.id}
                className={cn(
                  "bg-card rounded-xl p-4 border transition-all cursor-pointer",
                  selectedContainer?.id === container.id 
                    ? "border-primary ring-2 ring-primary/20" 
                    : "border-border hover:border-primary/50"
                )}
                onClick={() => setSelectedContainer(container)}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      "w-3 h-3 rounded-full",
                      container.status === 'running' && "bg-green-500 animate-pulse",
                      container.status === 'stopped' && "bg-red-500",
                      container.status === 'restarting' && "bg-yellow-500 animate-pulse",
                    )} />
                    <div>
                      <p className="font-semibold">{container.name}</p>
                      <p className="text-xs text-muted-foreground">{container.image}</p>
                    </div>
                  </div>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-2 gap-3 mb-4">
                  <div className="flex items-center gap-2 text-sm">
                    <Cpu className="w-4 h-4 text-muted-foreground" />
                    <span>{container.cpu.toFixed(1)}%</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <MemoryStick className="w-4 h-4 text-muted-foreground" />
                    <span>{container.memory}MB</span>
                  </div>
                </div>

                {/* Ports */}
                <div className="flex flex-wrap gap-1 mb-4">
                  {container.ports.map((port) => (
                    <span key={port} className="px-2 py-0.5 bg-accent rounded text-xs">
                      {port}
                    </span>
                  ))}
                </div>

                {/* Actions */}
                <div className="flex gap-2">
                  {container.status !== 'running' ? (
                    <Button 
                      size="sm" 
                      variant="success"
                      className="flex-1"
                      onClick={(e) => { e.stopPropagation(); handleAction(container, 'start') }}
                      disabled={actionLoading === container.id}
                    >
                      <Play className="w-4 h-4 mr-1" />
                      {actionLoading === container.id ? 'Starting...' : 'Start'}
                    </Button>
                  ) : (
                    <>
                      <Button 
                        size="sm" 
                        variant="destructive"
                        className="flex-1"
                        onClick={(e) => { e.stopPropagation(); handleAction(container, 'stop') }}
                        disabled={actionLoading === container.id}
                      >
                        <Square className="w-4 h-4 mr-1" />
                        {actionLoading === container.id ? 'Stopping...' : 'Stop'}
                      </Button>
                      <Button 
                        size="sm" 
                        variant="outline"
                        onClick={(e) => { e.stopPropagation(); handleAction(container, 'restart') }}
                        disabled={actionLoading === container.id}
                      >
                        <RotateCcw className="w-4 h-4" />
                      </Button>
                    </>
                  )}
                  <Button size="sm" variant="ghost">
                    <FileText className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
