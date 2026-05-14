"use client"

import { useEffect, useSyncExternalStore } from 'react'
import { Moon, Sun, Box, Zap } from 'lucide-react'

// GitHub icon component
function GithubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
    </svg>
  )
}
import { motion } from 'framer-motion'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { useStore } from '@/lib/store'
import { TrafficDropzone } from './traffic-dropzone'
import { MockFactory } from './mock-factory'
import { DockerLab } from './docker-lab'
import { ApiDocs } from './api-docs'
import toast, { Toaster } from 'react-hot-toast'

function ClawLogo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M12 2L2 7l10 5 10-5-10-5z" />
      <path d="M2 17l10 5 10-5" />
      <path d="M2 12l10 5 10-5" />
    </svg>
  )
}

export function Dashboard() {
  const { theme, setTheme, isProcessing } = useStore()
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  )

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [theme])

  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark'
    setTheme(newTheme)
    toast.success(`${newTheme === 'dark' ? '🌙' : '☀️'} ${newTheme.charAt(0).toUpperCase() + newTheme.slice(1)} mode activated`)
  }

  if (!mounted) return null

  return (
    <div className="min-h-screen bg-background">
      <Toaster 
        position="bottom-right"
        toastOptions={{
          style: {
            background: 'hsl(var(--card))',
            color: 'hsl(var(--foreground))',
            border: '1px solid hsl(var(--border))',
          },
        }}
      />
      
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-xl sticky top-0 z-50">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <motion.div 
              className="flex items-center gap-4"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.5 }}
            >
              <div className="p-2 bg-gradient-to-br from-primary to-cyan-500 rounded-xl shadow-lg shadow-primary/30">
                <ClawLogo className="w-8 h-8 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold bg-gradient-to-r from-primary via-purple-400 to-cyan-400 bg-clip-text text-transparent">
                  MockClaw
                </h1>
                <p className="text-xs text-muted-foreground">
                  AI-Powered Mock API Generator
                </p>
              </div>
            </motion.div>

            <motion.div 
              className="flex items-center gap-4"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.5 }}
            >
              {/* Status */}
              <Card className="px-4 py-2">
                <div className="flex items-center gap-2">
                  <div className={isProcessing ? "w-2 h-2 bg-yellow-500 rounded-full animate-pulse" : "w-2 h-2 bg-green-500 rounded-full"} />
                  <span className="text-sm font-medium">{isProcessing ? 'Processing' : 'Ready'}</span>
                </div>
              </Card>

              {/* Theme Toggle */}
              <div className="flex items-center gap-2">
                <Sun className="w-4 h-4 text-muted-foreground" />
                <Switch
                  checked={theme === 'dark'}
                  onCheckedChange={toggleTheme}
                />
                <Moon className="w-4 h-4 text-muted-foreground" />
              </div>

              {/* GitHub Link */}
              <Button
                variant="ghost"
                size="icon"
                onClick={() => window.open('https://github.com/EternalRights/MockClaw', '_blank')}
                className="rounded-full"
              >
                <GithubIcon className="w-5 h-5" />
              </Button>
            </motion.div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <Tabs defaultValue="traffic" className="space-y-6">
            <TabsList className="grid w-full grid-cols-4 lg:w-[600px]">
              <TabsTrigger value="traffic" className="gap-2">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" />
                </svg>
                Traffic
              </TabsTrigger>
              <TabsTrigger value="factory" className="gap-2">
                <Zap className="w-4 h-4" />
                Factory
              </TabsTrigger>
              <TabsTrigger value="docker" className="gap-2">
                <Box className="w-4 h-4" />
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
        </motion.div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border mt-12">
        <div className="container mx-auto px-6 py-6">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <ClawLogo className="w-4 h-4 text-primary" />
              <span>MockClaw v0.1.0</span>
            </div>
            <div className="flex items-center gap-4">
              <a href="https://github.com/EternalRights/MockClaw" className="hover:text-foreground transition-colors flex items-center gap-1">
                <GithubIcon className="w-4 h-4" />
                GitHub
              </a>
              <span>Built with AI</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
