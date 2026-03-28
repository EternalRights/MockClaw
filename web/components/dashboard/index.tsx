"use client"

import { useEffect } from 'react'
import { Moon, Sun, Box, AlertCircle, RefreshCw } from 'lucide-react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { useStore } from '@/lib/store'
import { TrafficDropzone } from './traffic-dropzone'
import { MockFactory } from './mock-factory'
import { DockerLab } from './docker-lab'
import { ApiDocs } from './api-docs'

function ErrorFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center p-8">
        <div className="w-24 h-24 mx-auto mb-6 bg-destructive/10 rounded-full flex items-center justify-center">
          <AlertCircle className="w-12 h-12 text-destructive" />
        </div>
        <h1 className="text-2xl font-bold mb-2">Backend Offline</h1>
        <p className="text-muted-foreground mb-6">
          Unable to connect to the MockClaw Brain service.
        </p>
        <Button onClick={() => window.location.reload()}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Reconnect
        </Button>
      </div>
    </div>
  )
}

function LoadingFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center">
        <div className="w-16 h-16 mx-auto mb-4 border-4 border-primary/30 border-t-primary rounded-full animate-spin" />
        <p className="text-muted-foreground">Initializing MockClaw...</p>
      </div>
    </div>
  )
}

export function Dashboard() {
  const { theme, setTheme, isProcessing } = useStore()

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="p-2 bg-primary/10 rounded-xl">
                <Box className="w-8 h-8 text-primary" />
              </div>
              <div>
                <h1 className="text-2xl font-bold gradient-text">MockClaw</h1>
                <p className="text-xs text-muted-foreground">
                  AI-Powered Mock API Generator
                </p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              {/* Status */}
              <div className="flex items-center gap-2 px-4 py-2 bg-card rounded-full border border-border">
                <div className={isProcessing ? "w-2 h-2 bg-yellow-500 rounded-full animate-pulse" : "w-2 h-2 bg-green-500 rounded-full"} />
                <span className="text-sm">{isProcessing ? 'Processing' : 'Ready'}</span>
              </div>

              {/* Theme Toggle */}
              <Button
                variant="outline"
                size="icon"
                onClick={toggleTheme}
                className="rounded-full"
              >
                {theme === 'dark' ? (
                  <Sun className="w-5 h-5" />
                ) : (
                  <Moon className="w-5 h-5" />
                )}
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        <Tabs defaultValue="traffic" className="space-y-6">
          <TabsList className="grid w-full grid-cols-4 lg:w-[600px]">
            <TabsTrigger value="traffic" className="gap-2">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" />
              </svg>
              Traffic
            </TabsTrigger>
            <TabsTrigger value="factory" className="gap-2">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
              </svg>
              Factory
            </TabsTrigger>
            <TabsTrigger value="docker" className="gap-2">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="7" width="20" height="14" rx="2" />
                <path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16" />
              </svg>
              Docker
            </TabsTrigger>
            <TabsTrigger value="docs" className="gap-2">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 19.5A2.5 2.5 0 016.5 17H20M4 19.5A2.5 2.5 0 014 14.5M4 19.5v-15" />
              </svg>
              Docs
            </TabsTrigger>
          </TabsList>

          <TabsContent value="traffic">
            <TrafficDropzone />
          </TabsContent>

          <TabsContent value="factory">
            <MockFactory />
          </TabsContent>

          <TabsContent value="docker">
            <DockerLab />
          </TabsContent>

          <TabsContent value="docs">
            <ApiDocs />
          </TabsContent>
        </Tabs>
      </main>

      {/* Footer */}
      <footer className="border-t border-border mt-12">
        <div className="container mx-auto px-6 py-6">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <Box className="w-4 h-4 text-primary" />
              <span>MockClaw v0.1.0</span>
            </div>
            <div>
              <a href="https://github.com/EternalRights/MockClaw" className="hover:text-foreground transition-colors">
                GitHub
              </a>
              <span className="mx-2">|</span>
              <span>Built with AI</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}

export { ErrorFallback, LoadingFallback }
