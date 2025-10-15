import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { getAuthToken } from '@/utils/auth'
import { 
  ChevronRight, ChevronDown, Folder, FolderOpen, FileText, 
  Send, Copy, Search,
  Wifi, WifiOff
} from 'lucide-react'
import { PayloadEncyclopedia } from '@/components/mqtt/PayloadEncyclopedia'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { toast } from '@/hooks/use-toast'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'

interface MQTTTopic {
  path: string
  name: string
  value?: any
  timestamp?: string
  retained?: boolean
  children?: Map<string, MQTTTopic>
}

interface MQTTMessage {
  topic: string
  value: any
  timestamp: string
  retained: boolean
}

interface Device {
  instance_id: string
  device_id: string
  name?: string
  model?: string
  online?: boolean
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
  const [messages, setMessages] = useState<MQTTMessage[]>([])
  const [devices, setDevices] = useState<Device[]>([])
  const [showDeviceSelector, setShowDeviceSelector] = useState(false)
  const [deviceSearchQuery, setDeviceSearchQuery] = useState('')
  const [currentDeviceTopic, setCurrentDeviceTopic] = useState<string | null>(null)
  // const [subscribedTopics, setSubscribedTopics] = useState<Set<string>>(new Set(['#']))
  
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    connectWebSocket()
    fetchDevices()
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  // Auto-fill topic when switching to publish tab
  useEffect(() => {
    if (selectedTopic && selectedTopic.path.includes('/devices/')) {
      // Extract device topic pattern
      const match = selectedTopic.path.match(/(.+\/devices\/[^\/]+)/)
      if (match) {
        const deviceBaseTopic = match[1] + '/cmd'
        setCurrentDeviceTopic(deviceBaseTopic)
        setPublishTopic(deviceBaseTopic)  // Also set publishTopic for logical binding
      }
    }
  }, [selectedTopic])

  const fetchDevices = async () => {
    try {
      const token = getAuthToken()
      if (!token) return

      // Fetch all devices from all instances
      const base = window.location.origin
      const response = await fetch(`${base}/api/devices`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (response.ok) {
        const data = await response.json()
        const normalized = Array.isArray(data)
          ? data
          : Array.isArray(data?.devices)
            ? data.devices
            : []
        setDevices(normalized)
      }
    } catch (error) {
      console.error('Error fetching devices:', error)
    }
  }

  const connectWebSocket = () => {
    const token = getAuthToken()
    if (!token) {
      toast({
        title: t('common.error'),
        description: t('common.no_auth_token_found'),
        variant: 'destructive'
      })
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsUrl = `${protocol}://${window.location.host}/ws/mqtt?token=${token}`
    wsRef.current = new WebSocket(wsUrl)
    
    wsRef.current.onopen = () => {
      console.log('MQTT WebSocket connected')
      setConnected(true)
    }
    
    wsRef.current.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        
        if (message.type === 'topics') {
          // Initial topics list from server - flat array
          const topicTree = buildTopicTree(message.data)
          setTopics(topicTree)
        } else if (message.type === 'update') {
          // Single topic update
          updateTopicValue(message.topic, message.value, message.timestamp, message.retained)
          
          // Add to messages list
          const newMessage: MQTTMessage = {
            topic: message.topic,
            value: message.value,
            timestamp: message.timestamp,
            retained: message.retained || false
          }
          setMessages(prev => [newMessage, ...prev].slice(0, 100)) // Keep last 100 messages
        } else if (message.type === 'delete') {
          // Topic deletion
          deleteTopicFromTree(message.topic)
        }
      } catch (error) {
        console.error('Error parsing MQTT message:', error)
      }
    }
    
    wsRef.current.onerror = (error) => {
      console.error('MQTT WebSocket error:', error)
      setConnected(false)
    }
    
    wsRef.current.onclose = () => {
      console.log('MQTT WebSocket disconnected')
      setConnected(false)
    }
  }

  const buildTopicTree = (topicsList: Array<{topic: string, value: any, timestamp: string, retained: boolean}>) => {
    const tree = new Map<string, MQTTTopic>()
    
    topicsList.forEach(item => {
      const parts = item.topic.split('/')
      let currentLevel = tree
      let currentPath = ''
      
      parts.forEach((part, index) => {
        currentPath = index === 0 ? part : `${currentPath}/${part}`
        
        if (!currentLevel.has(part)) {
          const newTopic: MQTTTopic = {
            path: currentPath,
            name: part,
            children: new Map()
          }
          currentLevel.set(part, newTopic)
        }
        
        const node = currentLevel.get(part)!
        
        // If it's the last part, add the value
        if (index === parts.length - 1) {
          node.value = item.value
          node.timestamp = item.timestamp
          node.retained = item.retained
        }
        
        if (node.children) {
          currentLevel = node.children
        }
      })
    })
    
    return tree
  }

  const updateTopicValue = (topicPath: string, value: any, timestamp: string, retained: boolean) => {
    const parts = topicPath.split('/')
    setTopics(prev => {
      const newTopics = new Map(prev)
      let currentLevel = newTopics
      
      parts.forEach((part, index) => {
        if (!currentLevel.has(part)) {
          const newTopic: MQTTTopic = {
            path: index === 0 ? part : parts.slice(0, index + 1).join('/'),
            name: part,
            children: new Map()
          }
          currentLevel.set(part, newTopic)
        }
        
        const node = currentLevel.get(part)!
        
        if (index === parts.length - 1) {
          // Update leaf node value
          node.value = value
          node.timestamp = timestamp
          node.retained = retained
        }
        
        if (node.children) {
          currentLevel = node.children
        }
      })
      
      return newTopics
    })
  }

  const deleteTopicFromTree = (topicPath: string) => {
    const parts = topicPath.split('/')
    setTopics(prev => {
      const newTopics = new Map(prev)
      
      // Function to recursively delete empty branches
      const deleteIfEmpty = (map: Map<string, MQTTTopic>, pathParts: string[], index: number): boolean => {
        if (index >= pathParts.length) return true
        
        const part = pathParts[index]
        const node = map.get(part)
        
        if (!node) return true
        
        if (index === pathParts.length - 1) {
          // Last part - delete the value
          delete node.value
          delete node.timestamp
          delete node.retained
          
          // If no children, remove the node entirely
          if (!node.children || node.children.size === 0) {
            map.delete(part)
            return map.size === 0
          }
          return false
        }
        
        // Recursively process children
        if (node.children) {
          const shouldDelete = deleteIfEmpty(node.children, pathParts, index + 1)
          
          // If children are now empty and node has no value, delete it
          if (shouldDelete && !node.value) {
            map.delete(part)
            return map.size === 0
          }
        }
        
        return false
      }
      
      deleteIfEmpty(newTopics, parts, 0)
      return newTopics
    })
    
    // Remove from selected topic if it was deleted
    if (selectedTopic && selectedTopic.path === topicPath) {
      setSelectedTopic(null)
    }
  }

  const handlePublish = () => {
    const topicToPublish = publishTopic || currentDeviceTopic || ''
    if (!wsRef.current || !topicToPublish) return
    
    try {
      // Parse payload if it's JSON
      let payload = publishPayload
      try {
        payload = JSON.parse(publishPayload)
      } catch {
        // Keep as string if not valid JSON
      }
      
      wsRef.current.send(JSON.stringify({
        action: 'publish',
        topic: topicToPublish,
        payload: payload,
        qos: parseInt(publishQos),
        retain: publishRetain
      }))
      
      toast({
        title: t('common.success'),
        description: t('mqtt_explorer.message_published'),
      })

      // Clear form
      setPublishPayload('')
    } catch (error) {
      toast({
        title: t('common.error'),
        description: t('mqtt_explorer.failed_to_publish'),
        variant: 'destructive'
      })
    }
  }

  /*const handleSubscribe = (topic: string) => {
    if (!wsRef.current) return
    
    wsRef.current.send(JSON.stringify({
      action: 'subscribe',
      topic: topic
    }))
    
    setSubscribedTopics(prev => new Set([...prev, topic]))
  }*/

  /*const handleUnsubscribe = (topic: string) => {
    if (!wsRef.current) return
    
    wsRef.current.send(JSON.stringify({
      action: 'unsubscribe',
      topic: topic
    }))
    
    setSubscribedTopics(prev => {
      const newSet = new Set(prev)
      newSet.delete(topic)
      return newSet
    })
  }*/

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
    const items: JSX.Element[] = []
    
    topics.forEach((topic) => {
      const hasChildren = topic.children && topic.children.size > 0
      const isExpanded = expandedTopics.has(topic.path)
      const hasValue = topic.value !== undefined
      
      items.push(
        <div key={topic.path}>
          <div
            className={`flex items-center gap-2 px-2 py-1 hover:bg-accent rounded cursor-pointer ${
              selectedTopic?.path === topic.path ? 'bg-accent' : ''
            }`}
            style={{ paddingLeft: `${level * 20 + 8}px` }}
            onClick={() => {
              if (hasChildren) {
                toggleExpanded(topic.path)
              }
              setSelectedTopic(topic)
            }}
          >
            {hasChildren ? (
              isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />
            ) : (
              <div className="w-4" />
            )}
            
            {hasChildren ? (
              isExpanded ? <FolderOpen className="h-4 w-4 text-blue-500" /> : <Folder className="h-4 w-4 text-blue-500" />
            ) : (
              <FileText className="h-4 w-4 text-green-500" />
            )}
            
            <span className="flex-1 text-sm font-mono">{topic.name}</span>
            
            {hasValue && (
              <Badge variant="secondary" className="text-xs">
                {typeof topic.value === 'object' ? 'JSON' : String(topic.value).slice(0, 20)}
              </Badge>
            )}
            
            {topic.retained && (
              <Badge variant="outline" className="text-xs">R</Badge>
            )}
          </div>
          
          {hasChildren && isExpanded && (
            <div>{renderTopicTree(topic.children!, level + 1)}</div>
          )}
        </div>
      )
    })
    
    return <>{items}</>
  }

  const filteredTopics = searchQuery
    ? new Map(
        Array.from(topics.entries()).filter(([, topic]) =>
          topic.path.toLowerCase().includes(searchQuery.toLowerCase())
        )
      )
    : topics

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{t('mqtt_explorer.title')}</h1>
          <p className="text-muted-foreground mt-1">
            {t('mqtt_explorer.description')}
          </p>
        </div>

        <Badge variant={connected ? "default" : "destructive"} className="gap-2">
          {connected ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
          {connected ? t('common.connected') : t('common.disconnected')}
        </Badge>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Topic Tree */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>{t('mqtt_explorer.topics')}</CardTitle>
            <Input
              type="text"
              placeholder={t('mqtt_explorer.search_topics')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="mt-2"
            />
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[600px]">
              {filteredTopics.size > 0 ? (
                renderTopicTree(filteredTopics)
              ) : (
                <p className="text-muted-foreground text-center py-8">
                  {t('mqtt_explorer.no_topics')}
                </p>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Details and Actions */}
        <Card className="lg:col-span-2">
          <Tabs defaultValue="details">
            <CardHeader>
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="details">{t('mqtt_explorer.details')}</TabsTrigger>
                <TabsTrigger value="publish">{t('mqtt_explorer.publish_tab')}</TabsTrigger>
                <TabsTrigger value="messages">{t('mqtt_explorer.messages')}</TabsTrigger>
              </TabsList>
            </CardHeader>
            
            <CardContent>
              <TabsContent value="details" className="space-y-4">
                {selectedTopic ? (
                  <>
                    <div>
                      <Label>{t('mqtt_explorer.topic_path')}</Label>
                      <div className="flex items-center gap-2 mt-1">
                        <Input value={selectedTopic.path} readOnly className="font-mono" />
                        <Button
                          size="icon"
                          variant="outline"
                          onClick={() => {
                            navigator.clipboard.writeText(selectedTopic.path)
                            toast({
                              title: t('common.copied'),
                              description: t('mqtt_explorer.path_copied'),
                            })
                          }}
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    {selectedTopic.value !== undefined && (
                      <>
                        <div>
                          <Label>{t('mqtt_explorer.value')}</Label>
                          <pre className="mt-1 p-3 bg-muted rounded text-sm overflow-auto max-h-96">
                            {typeof selectedTopic.value === 'object'
                              ? JSON.stringify(selectedTopic.value, null, 2)
                              : String(selectedTopic.value)}
                          </pre>
                        </div>
                        
                        {selectedTopic.timestamp && (
                          <div>
                            <Label>{t('mqtt_explorer.last_update')}</Label>
                            <p className="text-sm text-muted-foreground mt-1">
                              {new Date(selectedTopic.timestamp).toLocaleString()}
                            </p>
                          </div>
                        )}

                        {selectedTopic.retained !== undefined && (
                          <div>
                            <Label>{t('mqtt_explorer.retained')}</Label>
                            <p className="text-sm mt-1">
                              {selectedTopic.retained ? t('common.yes') : t('common.no')}
                            </p>
                          </div>
                        )}
                      </>
                    )}
                  </>
                ) : (
                  <p className="text-muted-foreground text-center py-8">
                    {t('mqtt_explorer.select_topic')}
                  </p>
                )}
              </TabsContent>
              
              <TabsContent value="publish" className="space-y-4">
                <div>
                  <Label htmlFor="publish-topic">{t('mqtt_explorer.topic')}</Label>
                  <div className="flex items-center gap-2">
                    <Input
                      id="publish-topic"
                      value={publishTopic || currentDeviceTopic || ''}
                      onChange={(e) => setPublishTopic(e.target.value)}
                      placeholder="IoT2mqtt/v1/instances/{instance_id}/devices/{device_id}/cmd"
                      className="font-mono flex-1"
                    />
                    <Button
                      size="icon"
                      variant="outline"
                      onClick={() => setShowDeviceSelector(!showDeviceSelector)}
                      title={t('mqtt_explorer.select_device')}
                    >
                      <Search className="h-4 w-4" />
                    </Button>
                  </div>

                  {showDeviceSelector && (
                    <Card className="mt-2 p-3">
                      <Input
                        type="text"
                        placeholder={t('mqtt_explorer.search_devices')}
                        value={deviceSearchQuery}
                        onChange={(e) => setDeviceSearchQuery(e.target.value)}
                        className="mb-2"
                      />
                      <ScrollArea className="h-[200px]">
                        <div className="space-y-1">
                          {devices
                            .filter(device => 
                              !deviceSearchQuery || 
                              device.device_id.toLowerCase().includes(deviceSearchQuery.toLowerCase()) ||
                              (device.name && device.name.toLowerCase().includes(deviceSearchQuery.toLowerCase()))
                            )
                            .map(device => (
                              <div
                                key={`${device.instance_id}_${device.device_id}`}
                                className="flex items-center justify-between p-2 hover:bg-accent rounded cursor-pointer"
                                onClick={() => {
                                  const topic = `IoT2mqtt/v1/instances/${device.instance_id}/devices/${device.device_id}/cmd`
                                  setPublishTopic(topic)
                                  setShowDeviceSelector(false)
                                  setDeviceSearchQuery('')
                                }}
                              >
                                <div>
                                  <div className="font-medium text-sm">
                                    {device.name || device.device_id}
                                  </div>
                                  <div className="text-xs text-muted-foreground">
                                    {device.instance_id} • {device.model || 'Unknown'}
                                  </div>
                                </div>
                                {device.online && (
                                  <Badge variant="default" className="text-xs">{t('common.online')}</Badge>
                                )}
                              </div>
                            ))
                          }
                        </div>
                      </ScrollArea>
                    </Card>
                  )}
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="publish-payload">{t('mqtt_explorer.payload')}</Label>
                    <textarea
                      id="publish-payload"
                      value={publishPayload}
                      onChange={(e) => setPublishPayload(e.target.value)}
                      placeholder='{\n  "id": "cmd_123",\n  "timestamp": "2024-01-15T10:30:00.123Z",\n  "values": {\n    "power": true\n  }\n}'
                      className="w-full min-h-[300px] p-3 rounded-md border bg-background font-mono text-sm"
                    />
                  </div>
                  
                  <div>
                    <PayloadEncyclopedia 
                      onSelectPayload={(payload) => setPublishPayload(payload)}
                    />
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="publish-qos">{t('mqtt_explorer.qos')}</Label>
                    <Select value={publishQos} onValueChange={setPublishQos}>
                      <SelectTrigger id="publish-qos">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="0">{t('mqtt_explorer.qos_0')}</SelectItem>
                        <SelectItem value="1">{t('mqtt_explorer.qos_1')}</SelectItem>
                        <SelectItem value="2">{t('mqtt_explorer.qos_2')}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="flex items-end gap-2">
                    <Checkbox
                      id="publish-retain"
                      checked={publishRetain}
                      onCheckedChange={(checked) => setPublishRetain(checked as boolean)}
                    />
                    <Label htmlFor="publish-retain" className="cursor-pointer">
                      {t('mqtt_explorer.retained')}
                    </Label>
                  </div>
                </div>

                <Button onClick={handlePublish} className="w-full">
                  <Send className="mr-2 h-4 w-4" />
                  {t('mqtt_explorer.publish_message')}
                </Button>
              </TabsContent>
              
              <TabsContent value="messages">
                <ScrollArea className="h-[500px]">
                  {messages.length > 0 ? (
                    <div className="space-y-2">
                      {messages.map((msg, index) => (
                        <Card key={index} className="p-3">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <p className="font-mono text-sm font-semibold">{msg.topic}</p>
                              <pre className="text-xs text-muted-foreground mt-1">
                                {typeof msg.value === 'object'
                                  ? JSON.stringify(msg.value, null, 2)
                                  : String(msg.value)}
                              </pre>
                            </div>
                            <div className="text-right">
                              <p className="text-xs text-muted-foreground">
                                {new Date(msg.timestamp).toLocaleTimeString()}
                              </p>
                              {msg.retained && (
                                <Badge variant="outline" className="text-xs mt-1">R</Badge>
                              )}
                            </div>
                          </div>
                        </Card>
                      ))}
                    </div>
                  ) : (
                    <p className="text-muted-foreground text-center py-8">
                      {t('mqtt_explorer.no_messages')}
                    </p>
                  )}
                </ScrollArea>
              </TabsContent>
            </CardContent>
          </Tabs>
        </Card>
      </div>
    </div>
  )
}
