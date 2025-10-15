import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { getAuthToken } from '@/utils/auth'
import { 
  Play, Pause, RotateCw, Trash2, Terminal,
  Circle, Download,
  Container, Cpu, HardDrive
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { toast } from '@/hooks/use-toast'
import { Progress } from '@/components/ui/progress'
import { 
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

interface DockerContainer {
  id: string
  name: string
  image: string
  status: string
  state: string
  created: string
  ports: any
  labels: any
  connector_type?: string
  instance_id?: string
  stats?: {
    cpu_percent: number
    memory_usage: number
    memory_limit: number
    network_rx: number
    network_tx: number
  }
}

interface LogEntry {
  timestamp: string
  level: 'info' | 'warning' | 'error' | 'success' | 'debug'
  content: string
}

export default function Containers() {
  const { t } = useTranslation()
  const [containers, setContainers] = useState<DockerContainer[]>([])
  const [selectedContainer, setSelectedContainer] = useState<DockerContainer | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [containerToDelete, setContainerToDelete] = useState<DockerContainer | null>(null)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    fetchContainers()
    const interval = autoRefresh ? setInterval(fetchContainers, 5000) : null
    return () => {
      if (interval) clearInterval(interval)
      if (wsRef.current) wsRef.current.close()
    }
  }, [autoRefresh])

  useEffect(() => {
    if (selectedContainer) {
      connectToLogs(selectedContainer.id)
    }
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [selectedContainer])

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs])

  const fetchContainers = async () => {
    try {
      const token = getAuthToken()
      if (!token) {
        throw new Error('No authentication token')
      }

      const response = await fetch('/api/docker/containers', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem('token')
        window.location.href = '/login'
        return
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      setContainers(data)
    } catch (error) {
      if (error instanceof Error && error.message !== 'No authentication token') {
        toast({
          title: t('common.error'),
          description: t('containers.failed_to_fetch'),
          variant: 'destructive'
        })
      }
    } finally {
      setLoading(false)
    }
  }

  const connectToLogs = (containerId: string) => {
    // Clear previous logs
    setLogs([])
    
    // Close existing WebSocket if any
    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
      wsRef.current.close()
      wsRef.current = null
    }

    const token = getAuthToken()
    if (!token) {
      toast({
        title: t('common.error'),
        description: t('common.no_auth_token'),
        variant: 'destructive'
      })
      return
    }

    // Create WebSocket connection for real-time logs
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    wsRef.current = new WebSocket(`${protocol}//${host}/ws/logs/${containerId}?token=${token}`)
    
    wsRef.current.onopen = () => {
      console.log('WebSocket connected for container logs')
    }
    
    wsRef.current.onmessage = (event) => {
      try {
        const log = JSON.parse(event.data)
        
        // Handle error messages
        if (log.error) {
          console.error('Log error:', log.error)
          return
        }
        
        setLogs(prev => {
          // Keep only last 500 logs to prevent memory issues
          const newLogs = [...prev, log]
          if (newLogs.length > 500) {
            return newLogs.slice(-500)
          }
          return newLogs
        })
      } catch (error) {
        console.error('Error parsing log:', error)
      }
    }
    
    wsRef.current.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
    
    wsRef.current.onclose = (event) => {
      console.log('WebSocket disconnected:', event.code, event.reason)
    }
  }

  const handleContainerAction = async (container: DockerContainer, action: 'start' | 'stop' | 'restart') => {
    try {
      const token = getAuthToken()
      if (!token) {
        throw new Error('No authentication token')
      }

      const response = await fetch(`/api/docker/containers/${container.id}/${action}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem('token')
        window.location.href = '/login'
        return
      }

      if (!response.ok) {
        throw new Error(`Failed to ${action} container`)
      }

      toast({
        title: t('common.success'),
        description: t('containers.action_success', { action }),
      })

      // Refresh container list
      await fetchContainers()
    } catch (error) {
      toast({
        title: t('common.error'),
        description: t('containers.action_failed', { action }),
        variant: 'destructive'
      })
    }
  }

  const handleDeleteContainer = async () => {
    if (!containerToDelete) return
    
    try {
      const token = getAuthToken()
      if (!token) {
        throw new Error('No authentication token')
      }

      const response = await fetch(`/api/docker/containers/${containerToDelete.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem('token')
        window.location.href = '/login'
        return
      }

      if (!response.ok) {
        throw new Error('Failed to delete container')
      }

      // Remove from local state
      setContainers(prev => prev.filter(c => c.id !== containerToDelete.id))
      
      if (selectedContainer?.id === containerToDelete.id) {
        setSelectedContainer(null)
        setLogs([])
      }
      
      toast({
        title: t('common.success'),
        description: t('containers.deleted_successfully'),
      })

      setShowDeleteDialog(false)
      setContainerToDelete(null)
    } catch (error) {
      toast({
        title: t('common.error'),
        description: t('containers.failed_to_delete'),
        variant: 'destructive'
      })
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <Circle className="h-3 w-3 fill-green-500 text-green-500" />
      case 'exited':
        return <Circle className="h-3 w-3 fill-gray-500 text-gray-500" />
      case 'paused':
        return <Circle className="h-3 w-3 fill-yellow-500 text-yellow-500" />
      default:
        return <Circle className="h-3 w-3 fill-red-500 text-red-500" />
    }
  }

  const getLogLevelColor = (level: string) => {
    switch (level) {
      case 'error':
        return 'text-red-500'
      case 'warning':
        return 'text-yellow-500'
      case 'success':
        return 'text-green-500'
      case 'debug':
        return 'text-gray-500'
      default:
        return 'text-blue-500'
    }
  }

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const downloadLogs = () => {
    const logText = logs.map(log => 
      `[${new Date(log.timestamp).toLocaleString()}] [${log.level.toUpperCase()}] ${log.content}`
    ).join('\n')
    
    const blob = new Blob([logText], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${selectedContainer?.name || 'container'}-logs-${new Date().toISOString()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <Container className="h-12 w-12 animate-pulse text-muted-foreground mx-auto mb-4" />
          <p className="text-muted-foreground">{t('containers.loading')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold">{t('containers.title')}</h1>
          <p className="text-muted-foreground mt-1">
            {t('containers.description')}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="outline" className="gap-2">
            <Container className="h-3 w-3" />
            {containers.length} {t('containers.count')}
          </Badge>
          <Button
            variant="outline"
            size="icon"
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={autoRefresh ? 'text-green-500' : ''}
          >
            <RotateCw className={`h-4 w-4 ${autoRefresh ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 min-h-0">
        {/* Container List */}
        <Card className="lg:col-span-1 flex flex-col">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{t('containers.title')}</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 p-0">
            <ScrollArea className="h-[600px]">
              <div className="space-y-2 p-4">
                {containers.map((container) => (
                  <div
                    key={container.id}
                    className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                      selectedContainer?.id === container.id
                        ? 'bg-accent border-primary'
                        : 'hover:bg-accent/50'
                    }`}
                    onClick={() => setSelectedContainer(container)}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        {getStatusIcon(container.status)}
                        <span className="font-medium text-sm">
                          {container.name.replace('iot2mqtt_', '')}
                        </span>
                      </div>
                      <Badge variant={container.status === 'running' ? 'default' : 'secondary'}>
                        {container.status}
                      </Badge>
                    </div>
                    
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">
                        {container.image}
                      </p>
                      {container.connector_type && (
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-xs">
                            {container.connector_type}
                          </Badge>
                          {container.instance_id && (
                            <Badge variant="outline" className="text-xs">
                              {container.instance_id}
                            </Badge>
                          )}
                        </div>
                      )}
                      {container.stats && container.status === 'running' && (
                        <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Cpu className="h-3 w-3" />
                            {container.stats.cpu_percent.toFixed(1)}%
                          </span>
                          <span className="flex items-center gap-1">
                            <HardDrive className="h-3 w-3" />
                            {formatBytes(container.stats.memory_usage)}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                
                {containers.length === 0 && (
                  <div className="text-center py-8 text-muted-foreground">
                    <Container className="h-12 w-12 mx-auto mb-2 opacity-50" />
                    <p>{t('containers.no_containers')}</p>
                  </div>
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Container Details */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          {selectedContainer ? (
            <>
              {/* Container Info Card */}
              <Card>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-lg">
                        {selectedContainer.name.replace('iot2mqtt_', '')}
                      </CardTitle>
                      <CardDescription>
                        {selectedContainer.image}
                      </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                      {selectedContainer.status === 'running' ? (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleContainerAction(selectedContainer, 'stop')}
                          >
                            <Pause className="mr-2 h-4 w-4" />
                            {t('common.stop')}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleContainerAction(selectedContainer, 'restart')}
                          >
                            <RotateCw className="mr-2 h-4 w-4" />
                            {t('common.restart')}
                          </Button>
                        </>
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleContainerAction(selectedContainer, 'start')}
                        >
                          <Play className="mr-2 h-4 w-4" />
                          {t('common.start')}
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setContainerToDelete(selectedContainer)
                          setShowDeleteDialog(true)
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-muted-foreground">{t('containers.container_id')}</p>
                      <p className="font-mono text-sm">{selectedContainer.id.substring(0, 12)}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">{t('containers.created')}</p>
                      <p className="text-sm">
                        {new Date(selectedContainer.created).toLocaleDateString()}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">{t('containers.status')}</p>
                      <div className="flex items-center gap-2">
                        {getStatusIcon(selectedContainer.status)}
                        <span className="text-sm capitalize">{selectedContainer.status}</span>
                      </div>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">{t('containers.ports')}</p>
                      <p className="text-sm font-mono">
                        {Object.entries(selectedContainer.ports)
                          .map(([port, mapping]) => 
                            mapping && Array.isArray(mapping) && mapping[0]?.HostPort
                              ? `${mapping[0].HostPort}→${port}`
                              : port
                          )
                          .join(', ') || 'None'}
                      </p>
                    </div>
                  </div>
                  
                  {selectedContainer.stats && selectedContainer.status === 'running' && (
                    <>
                      <div className="mt-4 pt-4 border-t">
                        <p className="text-sm font-medium mb-3">{t('containers.resource_usage')}</p>
                        <div className="space-y-3">
                          <div>
                            <div className="flex items-center justify-between text-sm mb-1">
                              <span className="flex items-center gap-2">
                                <Cpu className="h-4 w-4" />
                                {t('containers.cpu')}
                              </span>
                              <span>{selectedContainer.stats.cpu_percent.toFixed(1)}%</span>
                            </div>
                            <Progress value={selectedContainer.stats.cpu_percent} className="h-2" />
                          </div>

                          <div>
                            <div className="flex items-center justify-between text-sm mb-1">
                              <span className="flex items-center gap-2">
                                <HardDrive className="h-4 w-4" />
                                {t('containers.memory')}
                              </span>
                              <span>
                                {formatBytes(selectedContainer.stats.memory_usage)} / 
                                {formatBytes(selectedContainer.stats.memory_limit)}
                              </span>
                            </div>
                            <Progress 
                              value={(selectedContainer.stats.memory_usage / selectedContainer.stats.memory_limit) * 100} 
                              className="h-2" 
                            />
                          </div>
                          
                          <div className="grid grid-cols-2 gap-4 pt-2">
                            <div>
                              <p className="text-xs text-muted-foreground">{t('containers.network_rx')}</p>
                              <p className="text-sm font-mono">
                                {formatBytes(selectedContainer.stats.network_rx)}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-muted-foreground">{t('containers.network_tx')}</p>
                              <p className="text-sm font-mono">
                                {formatBytes(selectedContainer.stats.network_tx)}
                              </p>
                            </div>
                          </div>
                        </div>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>

              {/* Logs */}
              <Card className="flex-1 flex flex-col">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base flex items-center gap-2">
                      <Terminal className="h-4 w-4" />
                      {t('containers.container_logs')}
                    </CardTitle>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={downloadLogs}
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="flex-1 p-0">
                  <ScrollArea className="h-[300px] bg-black/5 dark:bg-black/20">
                    <div className="p-4 font-mono text-xs space-y-1">
                      {logs.map((log, index) => (
                        <div key={index} className="flex items-start gap-2">
                          <span className="text-muted-foreground">
                            {new Date(log.timestamp).toLocaleTimeString()}
                          </span>
                          <span className={getLogLevelColor(log.level)}>
                            [{log.level.toUpperCase()}]
                          </span>
                          <span className="flex-1 break-all">{log.content}</span>
                        </div>
                      ))}
                      <div ref={logsEndRef} />
                    </div>
                  </ScrollArea>
                </CardContent>
              </Card>
            </>
          ) : (
            <Card className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <Container className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-lg font-medium mb-2">{t('containers.select_container')}</p>
                <p className="text-muted-foreground">
                  {t('containers.click_to_view')}
                </p>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('containers.delete_container')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('containers.confirm_delete')} {containerToDelete?.name}?
              {t('containers.action_cannot_undone')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setContainerToDelete(null)}>
              {t('common.cancel')}
            </AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteContainer}>
              {t('common.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}