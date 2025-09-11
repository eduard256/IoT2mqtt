import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { getAuthToken } from '@/utils/auth'
import { 
  ChevronRight, ChevronDown, Folder, FolderOpen, FileText, 
  Send, Copy,
  Wifi, WifiOff
} from 'lucide-react'
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
  // const [subscribedTopics, setSubscribedTopics] = useState<Set<string>>(new Set(['#']))
  
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    connectWebSocket()
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  const connectWebSocket = () => {
    const token = getAuthToken()
    if (!token) {
      toast({
        title: t('Error'),
        description: t('No authentication token found'),
        variant: 'destructive'
      })
      return
    }

    const wsUrl = `ws://localhost:8765/ws/mqtt?token=${token}`
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

  const handlePublish = () => {
    if (!wsRef.current || !publishTopic) return
    
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
        topic: publishTopic,
        payload: payload,
        qos: parseInt(publishQos),
        retain: publishRetain
      }))
      
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
          <h1 className="text-3xl font-bold">{t('MQTT Explorer')}</h1>
          <p className="text-muted-foreground mt-1">
            {t('Browse and interact with MQTT topics')}
          </p>
        </div>
        
        <Badge variant={connected ? "default" : "destructive"} className="gap-2">
          {connected ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
          {connected ? t('Connected') : t('Disconnected')}
        </Badge>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Topic Tree */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>{t('Topics')}</CardTitle>
            <Input
              type="text"
              placeholder={t('Search topics...')}
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
                  {t('No topics discovered yet')}
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
                <TabsTrigger value="details">{t('Details')}</TabsTrigger>
                <TabsTrigger value="publish">{t('Publish')}</TabsTrigger>
                <TabsTrigger value="messages">{t('Messages')}</TabsTrigger>
              </TabsList>
            </CardHeader>
            
            <CardContent>
              <TabsContent value="details" className="space-y-4">
                {selectedTopic ? (
                  <>
                    <div>
                      <Label>{t('Topic Path')}</Label>
                      <div className="flex items-center gap-2 mt-1">
                        <Input value={selectedTopic.path} readOnly className="font-mono" />
                        <Button
                          size="icon"
                          variant="outline"
                          onClick={() => {
                            navigator.clipboard.writeText(selectedTopic.path)
                            toast({
                              title: t('Copied'),
                              description: t('Topic path copied to clipboard'),
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
                          <Label>{t('Value')}</Label>
                          <pre className="mt-1 p-3 bg-muted rounded text-sm overflow-auto max-h-96">
                            {typeof selectedTopic.value === 'object'
                              ? JSON.stringify(selectedTopic.value, null, 2)
                              : String(selectedTopic.value)}
                          </pre>
                        </div>
                        
                        {selectedTopic.timestamp && (
                          <div>
                            <Label>{t('Last Update')}</Label>
                            <p className="text-sm text-muted-foreground mt-1">
                              {new Date(selectedTopic.timestamp).toLocaleString()}
                            </p>
                          </div>
                        )}
                        
                        {selectedTopic.retained !== undefined && (
                          <div>
                            <Label>{t('Retained')}</Label>
                            <p className="text-sm mt-1">
                              {selectedTopic.retained ? t('Yes') : t('No')}
                            </p>
                          </div>
                        )}
                      </>
                    )}
                  </>
                ) : (
                  <p className="text-muted-foreground text-center py-8">
                    {t('Select a topic to view details')}
                  </p>
                )}
              </TabsContent>
              
              <TabsContent value="publish" className="space-y-4">
                <div>
                  <Label htmlFor="publish-topic">{t('Topic')}</Label>
                  <Input
                    id="publish-topic"
                    value={publishTopic}
                    onChange={(e) => setPublishTopic(e.target.value)}
                    placeholder="home/temperature"
                    className="font-mono"
                  />
                </div>
                
                <div>
                  <Label htmlFor="publish-payload">{t('Payload')}</Label>
                  <textarea
                    id="publish-payload"
                    value={publishPayload}
                    onChange={(e) => setPublishPayload(e.target.value)}
                    placeholder='{"value": 22.5}'
                    className="w-full min-h-[100px] p-3 rounded-md border bg-background font-mono text-sm"
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
                  
                  <div className="flex items-end gap-2">
                    <Checkbox
                      id="publish-retain"
                      checked={publishRetain}
                      onCheckedChange={(checked) => setPublishRetain(checked as boolean)}
                    />
                    <Label htmlFor="publish-retain" className="cursor-pointer">
                      {t('Retain')}
                    </Label>
                  </div>
                </div>
                
                <Button onClick={handlePublish} className="w-full">
                  <Send className="mr-2 h-4 w-4" />
                  {t('Publish Message')}
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
                      {t('No messages received yet')}
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