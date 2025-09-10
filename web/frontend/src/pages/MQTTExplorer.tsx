import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { 
  ChevronRight, ChevronDown, Folder, FolderOpen, FileText, 
  Send, Copy, Trash2, Plus, Download,
  Wifi, WifiOff
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { toast } from '@/hooks/use-toast'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'

interface MQTTTopic {
  path: string
  name: string
  value?: any
  qos?: number
  retained?: boolean
  timestamp?: string
  children?: Map<string, MQTTTopic>
  messageCount?: number
  lastUpdate?: string
}

interface MQTTMessage {
  topic: string
  payload: any
  qos: number
  retained: boolean
  timestamp: string
}

export default function MQTTExplorer() {
  const { t } = useTranslation()
  const [connected, setConnected] = useState(false)
  const [topics, setTopics] = useState<Map<string, MQTTTopic>>(new Map())
  const [selectedTopic, setSelectedTopic] = useState<MQTTTopic | null>(null)
  const [expandedTopics, setExpandedTopics] = useState<Set<string>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')
  const [publishTopic, setPublishTopic] = useState('')
  const [publishPayload, setPublishPayload] = useState('')
  const [publishQos, setPublishQos] = useState('0')
  const [publishRetain, setPublishRetain] = useState(false)
  const [subscribedTopics, setSubscribedTopics] = useState<string[]>(['IoT2mqtt/v1/#'])
  const [messages, setMessages] = useState<MQTTMessage[]>([])
  const [autoScroll, setAutoScroll] = useState(true)
  const [filterRetained, setFilterRetained] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  // WebSocket ref for future real-time updates
  // const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    // Simulate MQTT connection with mock data
    setConnected(true)
    generateMockData()
  }, [])

  useEffect(() => {
    if (autoScroll && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, autoScroll])

  const generateMockData = () => {
    // Generate mock topic tree
    const mockTopics = new Map<string, MQTTTopic>()
    
    // IoT2mqtt structure
    const iot2mqtt: MQTTTopic = {
      path: 'IoT2mqtt',
      name: 'IoT2mqtt',
      children: new Map([
        ['v1', {
          path: 'IoT2mqtt/v1',
          name: 'v1',
          children: new Map([
            ['instances', {
              path: 'IoT2mqtt/v1/instances',
              name: 'instances',
              children: new Map([
                ['yeelight_home', {
                  path: 'IoT2mqtt/v1/instances/yeelight_home',
                  name: 'yeelight_home',
                  children: new Map([
                    ['status', {
                      path: 'IoT2mqtt/v1/instances/yeelight_home/status',
                      name: 'status',
                      value: 'online',
                      retained: true,
                      qos: 1,
                      timestamp: new Date().toISOString(),
                      messageCount: 5
                    }],
                    ['devices', {
                      path: 'IoT2mqtt/v1/instances/yeelight_home/devices',
                      name: 'devices',
                      children: new Map([
                        ['bedroom_light', {
                          path: 'IoT2mqtt/v1/instances/yeelight_home/devices/bedroom_light',
                          name: 'bedroom_light',
                          children: new Map([
                            ['state', {
                              path: 'IoT2mqtt/v1/instances/yeelight_home/devices/bedroom_light/state',
                              name: 'state',
                              value: { power: true, brightness: 75, color_temp: 4000 },
                              retained: true,
                              qos: 1,
                              timestamp: new Date().toISOString(),
                              messageCount: 12
                            }],
                            ['cmd', {
                              path: 'IoT2mqtt/v1/instances/yeelight_home/devices/bedroom_light/cmd',
                              name: 'cmd',
                              value: {},
                              qos: 1,
                              messageCount: 3
                            }]
                          ])
                        }]
                      ])
                    }]
                  ])
                }]
              ])
            }],
            ['bridge', {
              path: 'IoT2mqtt/v1/bridge',
              name: 'bridge',
              children: new Map([
                ['status', {
                  path: 'IoT2mqtt/v1/bridge/status',
                  name: 'status',
                  value: 'online',
                  retained: true,
                  qos: 2,
                  timestamp: new Date().toISOString(),
                  messageCount: 1
                }]
              ])
            }]
          ])
        }]
      ])
    }
    
    mockTopics.set('IoT2mqtt', iot2mqtt)
    setTopics(mockTopics)
    
    // Generate mock messages
    const mockMessages: MQTTMessage[] = [
      {
        topic: 'IoT2mqtt/v1/instances/yeelight_home/status',
        payload: 'online',
        qos: 1,
        retained: true,
        timestamp: new Date(Date.now() - 5000).toISOString()
      },
      {
        topic: 'IoT2mqtt/v1/instances/yeelight_home/devices/bedroom_light/state',
        payload: { power: true, brightness: 75, color_temp: 4000 },
        qos: 1,
        retained: true,
        timestamp: new Date(Date.now() - 3000).toISOString()
      },
      {
        topic: 'IoT2mqtt/v1/bridge/status',
        payload: 'online',
        qos: 2,
        retained: true,
        timestamp: new Date(Date.now() - 1000).toISOString()
      }
    ]
    
    setMessages(mockMessages)
  }

  const toggleExpanded = (path: string) => {
    setExpandedTopics(prev => {
      const newSet = new Set(prev)
      if (newSet.has(path)) {
        newSet.delete(path)
      } else {
        newSet.add(path)
      }
      return newSet
    })
  }

  const renderTopicTree = (topics: Map<string, MQTTTopic>, level = 0) => {
    return Array.from(topics.entries())
      .filter(([name]) => {
        if (!searchQuery) return true
        return name.toLowerCase().includes(searchQuery.toLowerCase())
      })
      .map(([name, topic]) => {
        const hasChildren = topic.children && topic.children.size > 0
        const isExpanded = expandedTopics.has(topic.path)
        const isSelected = selectedTopic?.path === topic.path
        
        return (
          <div key={topic.path}>
            <div
              className={`flex items-center gap-2 px-2 py-1 hover:bg-accent rounded cursor-pointer ${
                isSelected ? 'bg-accent' : ''
              }`}
              style={{ paddingLeft: `${level * 20 + 8}px` }}
              onClick={() => {
                setSelectedTopic(topic)
                if (hasChildren) {
                  toggleExpanded(topic.path)
                }
              }}
            >
              {hasChildren ? (
                isExpanded ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )
              ) : (
                <FileText className="h-4 w-4 text-muted-foreground" />
              )}
              
              {hasChildren ? (
                isExpanded ? (
                  <FolderOpen className="h-4 w-4 text-blue-500" />
                ) : (
                  <Folder className="h-4 w-4 text-blue-500" />
                )
              ) : null}
              
              <span className="flex-1 text-sm">{name}</span>
              
              {topic.messageCount && (
                <Badge variant="secondary" className="text-xs">
                  {topic.messageCount}
                </Badge>
              )}
              
              {topic.retained && (
                <Badge variant="outline" className="text-xs">
                  R
                </Badge>
              )}
            </div>
            
            {hasChildren && isExpanded && (
              <div>
                {renderTopicTree(topic.children!, level + 1)}
              </div>
            )}
          </div>
        )
      })
  }

  const handlePublish = () => {
    if (!publishTopic || !publishPayload) {
      toast({
        title: t('Error'),
        description: t('Please enter topic and payload'),
        variant: 'destructive'
      })
      return
    }
    
    try {
      // Try to parse as JSON
      let payload = publishPayload
      try {
        payload = JSON.parse(publishPayload)
      } catch {
        // Not JSON, send as string
      }
      
      // Simulate publishing
      const newMessage: MQTTMessage = {
        topic: publishTopic,
        payload: payload,
        qos: parseInt(publishQos),
        retained: publishRetain,
        timestamp: new Date().toISOString()
      }
      
      setMessages(prev => [...prev, newMessage])
      
      toast({
        title: t('Success'),
        description: t('Message published'),
      })
      
      // Clear form
      setPublishPayload('')
    } catch (error) {
      toast({
        title: t('Error'),
        description: t('Failed to publish message'),
        variant: 'destructive'
      })
    }
  }

  const handleSubscribe = (topic: string) => {
    setSubscribedTopics(prev => [...prev, topic])
    
    toast({
      title: t('Success'),
      description: `Subscribed to ${topic}`,
    })
  }

  const handleUnsubscribe = (topic: string) => {
    setSubscribedTopics(prev => prev.filter(t => t !== topic))
    
    toast({
      title: t('Success'),
      description: `Unsubscribed from ${topic}`,
    })
  }

  const formatPayload = (payload: any) => {
    if (typeof payload === 'object') {
      return JSON.stringify(payload, null, 2)
    }
    return String(payload)
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast({
      title: t('Copied'),
      description: t('Copied to clipboard'),
    })
  }

  const exportMessages = () => {
    const data = JSON.stringify(messages, null, 2)
    const blob = new Blob([data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mqtt-messages-${new Date().toISOString()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const filteredMessages = filterRetained 
    ? messages.filter(m => m.retained)
    : messages

  return (
    <div className="h-full flex flex-col space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold">{t('mqtt_explorer.title')}</h1>
          <p className="text-muted-foreground mt-1">
            {t('Browse and interact with MQTT topics')}
          </p>
        </div>
        
        <div className="flex items-center gap-2">
          <Badge variant={connected ? 'default' : 'destructive'} className="gap-2">
            {connected ? (
              <><Wifi className="h-3 w-3" /> Connected</>
            ) : (
              <><WifiOff className="h-3 w-3" /> Disconnected</>
            )}
          </Badge>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 min-h-0">
        {/* Topic Tree */}
        <Card className="lg:col-span-1 flex flex-col">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Folder className="h-4 w-4" />
              {t('Topic Tree')}
            </CardTitle>
            <Input
              type="text"
              placeholder={t('Search topics...')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="mt-2"
            />
          </CardHeader>
          <CardContent className="flex-1 p-0">
            <ScrollArea className="h-[500px] px-4">
              {topics.size > 0 ? (
                renderTopicTree(topics)
              ) : (
                <div className="text-center text-muted-foreground py-8">
                  {t('No topics discovered yet')}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Details & Tools */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          <Tabs defaultValue="details" className="flex-1 flex flex-col">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="details">{t('Details')}</TabsTrigger>
              <TabsTrigger value="publish">{t('Publish')}</TabsTrigger>
              <TabsTrigger value="subscribe">{t('Subscribe')}</TabsTrigger>
              <TabsTrigger value="messages">
                {t('Messages')} 
                {messages.length > 0 && (
                  <Badge variant="secondary" className="ml-2">
                    {messages.length}
                  </Badge>
                )}
              </TabsTrigger>
            </TabsList>
            
            <TabsContent value="details" className="flex-1">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    {selectedTopic ? selectedTopic.path : t('Select a topic')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {selectedTopic ? (
                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label className="text-xs text-muted-foreground">{t('Last Update')}</Label>
                          <p className="text-sm font-mono">
                            {selectedTopic.lastUpdate || selectedTopic.timestamp || 'N/A'}
                          </p>
                        </div>
                        <div>
                          <Label className="text-xs text-muted-foreground">{t('Message Count')}</Label>
                          <p className="text-sm font-mono">
                            {selectedTopic.messageCount || 0}
                          </p>
                        </div>
                        <div>
                          <Label className="text-xs text-muted-foreground">{t('QoS')}</Label>
                          <p className="text-sm font-mono">
                            {selectedTopic.qos !== undefined ? selectedTopic.qos : 'N/A'}
                          </p>
                        </div>
                        <div>
                          <Label className="text-xs text-muted-foreground">{t('Retained')}</Label>
                          <p className="text-sm font-mono">
                            {selectedTopic.retained ? 'Yes' : 'No'}
                          </p>
                        </div>
                      </div>
                      
                      <Separator />
                      
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <Label className="text-xs text-muted-foreground">{t('Payload')}</Label>
                          {selectedTopic.value && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6"
                              onClick={() => copyToClipboard(formatPayload(selectedTopic.value))}
                            >
                              <Copy className="h-3 w-3" />
                            </Button>
                          )}
                        </div>
                        <pre className="text-xs bg-muted p-3 rounded-md overflow-x-auto">
                          {selectedTopic.value ? formatPayload(selectedTopic.value) : 'No payload'}
                        </pre>
                      </div>
                      
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setPublishTopic(selectedTopic.path)}
                        >
                          <Send className="mr-2 h-4 w-4" />
                          {t('Publish to this topic')}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleSubscribe(selectedTopic.path)}
                        >
                          <Plus className="mr-2 h-4 w-4" />
                          {t('Subscribe')}
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <p className="text-muted-foreground text-center py-8">
                      {t('Select a topic from the tree to view details')}
                    </p>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
            
            <TabsContent value="publish">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">{t('Publish Message')}</CardTitle>
                  <CardDescription>
                    {t('Send a message to an MQTT topic')}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <Label htmlFor="publish-topic">{t('Topic')}</Label>
                    <Input
                      id="publish-topic"
                      value={publishTopic}
                      onChange={(e) => setPublishTopic(e.target.value)}
                      placeholder="IoT2mqtt/v1/instances/test/cmd"
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="publish-payload">{t('Payload')}</Label>
                    <textarea
                      id="publish-payload"
                      value={publishPayload}
                      onChange={(e) => setPublishPayload(e.target.value)}
                      placeholder='{"power": true, "brightness": 75}'
                      className="w-full h-32 px-3 py-2 text-sm rounded-md border bg-background font-mono"
                    />
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="publish-qos">{t('QoS')}</Label>
                      <Select value={publishQos} onValueChange={setPublishQos}>
                        <SelectTrigger id="publish-qos">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="0">0 - At most once</SelectItem>
                          <SelectItem value="1">1 - At least once</SelectItem>
                          <SelectItem value="2">2 - Exactly once</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    
                    <div className="flex items-end">
                      <div className="flex items-center space-x-2">
                        <Checkbox
                          id="publish-retain"
                          checked={publishRetain}
                          onCheckedChange={(checked) => setPublishRetain(checked as boolean)}
                        />
                        <Label htmlFor="publish-retain">{t('Retained')}</Label>
                      </div>
                    </div>
                  </div>
                  
                  <Button onClick={handlePublish} className="w-full">
                    <Send className="mr-2 h-4 w-4" />
                    {t('Publish')}
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>
            
            <TabsContent value="subscribe">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">{t('Subscriptions')}</CardTitle>
                  <CardDescription>
                    {t('Manage topic subscriptions')}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex gap-2">
                    <Input
                      placeholder="IoT2mqtt/v1/#"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          const input = e.currentTarget
                          handleSubscribe(input.value)
                          input.value = ''
                        }
                      }}
                    />
                    <Button variant="outline">
                      <Plus className="h-4 w-4" />
                    </Button>
                  </div>
                  
                  <div className="space-y-2">
                    {subscribedTopics.map((topic) => (
                      <div key={topic} className="flex items-center justify-between p-2 rounded-md bg-muted">
                        <span className="text-sm font-mono">{topic}</span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => handleUnsubscribe(topic)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
            
            <TabsContent value="messages" className="flex-1 flex flex-col">
              <Card className="flex-1 flex flex-col">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">{t('Live Messages')}</CardTitle>
                    <div className="flex items-center gap-2">
                      <div className="flex items-center space-x-2">
                        <Checkbox
                          id="filter-retained"
                          checked={filterRetained}
                          onCheckedChange={(checked) => setFilterRetained(checked as boolean)}
                        />
                        <Label htmlFor="filter-retained" className="text-sm">
                          {t('Retained only')}
                        </Label>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Checkbox
                          id="auto-scroll"
                          checked={autoScroll}
                          onCheckedChange={(checked) => setAutoScroll(checked as boolean)}
                        />
                        <Label htmlFor="auto-scroll" className="text-sm">
                          {t('Auto-scroll')}
                        </Label>
                      </div>
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={() => setMessages([])}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={exportMessages}
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="flex-1 p-0">
                  <ScrollArea className="h-[400px] px-4">
                    <div className="space-y-2 py-2">
                      {filteredMessages.map((msg, index) => (
                        <div
                          key={index}
                          className="p-2 rounded-md bg-muted/50 hover:bg-muted transition-colors"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs text-muted-foreground">
                                  {new Date(msg.timestamp).toLocaleTimeString()}
                                </span>
                                <Badge variant="outline" className="text-xs">
                                  QoS {msg.qos}
                                </Badge>
                                {msg.retained && (
                                  <Badge variant="secondary" className="text-xs">
                                    Retained
                                  </Badge>
                                )}
                              </div>
                              <p className="text-sm font-mono text-blue-600 dark:text-blue-400 break-all">
                                {msg.topic}
                              </p>
                              <pre className="text-xs mt-1 text-muted-foreground break-all">
                                {formatPayload(msg.payload).substring(0, 100)}
                                {formatPayload(msg.payload).length > 100 && '...'}
                              </pre>
                            </div>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6 shrink-0"
                              onClick={() => copyToClipboard(formatPayload(msg.payload))}
                            >
                              <Copy className="h-3 w-3" />
                            </Button>
                          </div>
                        </div>
                      ))}
                      <div ref={messagesEndRef} />
                    </div>
                  </ScrollArea>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  )
}