import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { 
  Book, Copy, ChevronRight, ChevronDown,
  Power, Sun, Palette, Thermometer, Wind,
  Volume2, Lock, Play, Droplets, Home,
  Settings, AlertCircle
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { toast } from '@/hooks/use-toast'
import { Badge } from '@/components/ui/badge'

interface CommandExample {
  name: string
  description: string
  icon: React.ReactNode
  payload: any
  category: string
}

const commandExamples: CommandExample[] = [
  // Power Control
  {
    name: 'Turn On',
    description: 'Turn device on',
    icon: <Power className="h-4 w-4" />,
    category: 'Power Control',
    payload: {
      values: { power: true }
    }
  },
  {
    name: 'Turn Off',
    description: 'Turn device off',
    icon: <Power className="h-4 w-4" />,
    category: 'Power Control',
    payload: {
      values: { power: false }
    }
  },
  {
    name: 'Toggle Power',
    description: 'Toggle device power state',
    icon: <Power className="h-4 w-4" />,
    category: 'Power Control',
    payload: {
      values: { power: 'toggle' }
    }
  },
  
  // Brightness Control
  {
    name: 'Set Brightness 50%',
    description: 'Set brightness to 50%',
    icon: <Sun className="h-4 w-4" />,
    category: 'Brightness',
    payload: {
      values: { brightness: 50 }
    }
  },
  {
    name: 'Full Brightness',
    description: 'Set brightness to 100%',
    icon: <Sun className="h-4 w-4" />,
    category: 'Brightness',
    payload: {
      values: { brightness: 100 }
    }
  },
  {
    name: 'Dim Light',
    description: 'Set brightness to 10%',
    icon: <Sun className="h-4 w-4" />,
    category: 'Brightness',
    payload: {
      values: { brightness: 10 }
    }
  },
  
  // Color Control
  {
    name: 'Red Color',
    description: 'Set color to red',
    icon: <Palette className="h-4 w-4" />,
    category: 'Color',
    payload: {
      values: { color: { r: 255, g: 0, b: 0 } }
    }
  },
  {
    name: 'Blue Color',
    description: 'Set color to blue',
    icon: <Palette className="h-4 w-4" />,
    category: 'Color',
    payload: {
      values: { color: { r: 0, g: 0, b: 255 } }
    }
  },
  {
    name: 'Warm White',
    description: 'Set color temperature to warm',
    icon: <Palette className="h-4 w-4" />,
    category: 'Color',
    payload: {
      values: { color_temp: 2700 }
    }
  },
  {
    name: 'Cool White',
    description: 'Set color temperature to cool',
    icon: <Palette className="h-4 w-4" />,
    category: 'Color',
    payload: {
      values: { color_temp: 6500 }
    }
  },
  
  // Temperature Control
  {
    name: 'Set Temperature 22°C',
    description: 'Set target temperature',
    icon: <Thermometer className="h-4 w-4" />,
    category: 'Temperature',
    payload: {
      values: { target_temp: 22 }
    }
  },
  {
    name: 'Heating Mode',
    description: 'Set to heating mode',
    icon: <Thermometer className="h-4 w-4" />,
    category: 'Temperature',
    payload: {
      values: { mode: 'heat' }
    }
  },
  {
    name: 'Cooling Mode',
    description: 'Set to cooling mode',
    icon: <Thermometer className="h-4 w-4" />,
    category: 'Temperature',
    payload: {
      values: { mode: 'cool' }
    }
  },
  
  // Fan Control
  {
    name: 'Fan Auto',
    description: 'Set fan to auto mode',
    icon: <Wind className="h-4 w-4" />,
    category: 'Fan',
    payload: {
      values: { fan_mode: 'auto' }
    }
  },
  {
    name: 'Fan High',
    description: 'Set fan to high speed',
    icon: <Wind className="h-4 w-4" />,
    category: 'Fan',
    payload: {
      values: { fan_mode: 'high' }
    }
  },
  {
    name: 'Fan Low',
    description: 'Set fan to low speed',
    icon: <Wind className="h-4 w-4" />,
    category: 'Fan',
    payload: {
      values: { fan_mode: 'low' }
    }
  },
  
  // Media Control
  {
    name: 'Play',
    description: 'Start playback',
    icon: <Play className="h-4 w-4" />,
    category: 'Media',
    payload: {
      values: { media: 'play' }
    }
  },
  {
    name: 'Pause',
    description: 'Pause playback',
    icon: <Play className="h-4 w-4" />,
    category: 'Media',
    payload: {
      values: { media: 'pause' }
    }
  },
  {
    name: 'Volume 50%',
    description: 'Set volume to 50%',
    icon: <Volume2 className="h-4 w-4" />,
    category: 'Media',
    payload: {
      values: { volume: 50 }
    }
  },
  {
    name: 'Mute',
    description: 'Mute audio',
    icon: <Volume2 className="h-4 w-4" />,
    category: 'Media',
    payload: {
      values: { mute: true }
    }
  },
  
  // Lock Control
  {
    name: 'Lock',
    description: 'Lock the device',
    icon: <Lock className="h-4 w-4" />,
    category: 'Security',
    payload: {
      values: { lock: true }
    }
  },
  {
    name: 'Unlock',
    description: 'Unlock the device',
    icon: <Lock className="h-4 w-4" />,
    category: 'Security',
    payload: {
      values: { lock: false }
    }
  },
  
  // Scene Control
  {
    name: 'Movie Scene',
    description: 'Activate movie scene',
    icon: <Home className="h-4 w-4" />,
    category: 'Scenes',
    payload: {
      values: { scene: 'movie_night' }
    }
  },
  {
    name: 'Sleep Scene',
    description: 'Activate sleep scene',
    icon: <Home className="h-4 w-4" />,
    category: 'Scenes',
    payload: {
      values: { scene: 'sleep' }
    }
  },
  
  // Irrigation/Water Control
  {
    name: 'Start Watering',
    description: 'Start irrigation',
    icon: <Droplets className="h-4 w-4" />,
    category: 'Water',
    payload: {
      values: { water: true, duration: 300 }
    }
  },
  {
    name: 'Stop Watering',
    description: 'Stop irrigation',
    icon: <Droplets className="h-4 w-4" />,
    category: 'Water',
    payload: {
      values: { water: false }
    }
  },
  
  // System Commands
  {
    name: 'Get State',
    description: 'Request current state',
    icon: <Settings className="h-4 w-4" />,
    category: 'System',
    payload: {
      values: { get_state: true }
    }
  },
  {
    name: 'Reboot',
    description: 'Reboot device',
    icon: <Settings className="h-4 w-4" />,
    category: 'System',
    payload: {
      values: { reboot: true }
    }
  }
]

interface PayloadEncyclopediaProps {
  onSelectPayload: (payload: string) => void
}

export function PayloadEncyclopedia({ onSelectPayload }: PayloadEncyclopediaProps) {
  const { t } = useTranslation(['mqtt_explorer', 'common'])
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set())
  const [selectedExample, setSelectedExample] = useState<CommandExample | null>(null)

  const categories = Array.from(new Set(commandExamples.map(cmd => cmd.category)))

  const toggleCategory = (category: string) => {
    setExpandedCategories(prev => {
      const newSet = new Set(prev)
      if (newSet.has(category)) {
        newSet.delete(category)
      } else {
        newSet.add(category)
      }
      return newSet
    })
  }

  const copyToClipboard = (payload: any) => {
    const payloadStr = JSON.stringify(payload, null, 2)
    navigator.clipboard.writeText(payloadStr)
    toast({
      title: t('common:copied'),
      description: t('mqtt_explorer:payload_copied'),
    })
  }

  const insertPayload = (example: CommandExample) => {
    // Update timestamp and ID for current time
    const payload = {
      ...example.payload,
      id: 'cmd_' + Date.now(),
      timestamp: new Date().toISOString()
    }
    onSelectPayload(JSON.stringify(payload, null, 2))
    setSelectedExample(example)
  }

  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 mb-4">
        <Book className="h-5 w-5" />
        <h3 className="font-semibold">{t('command_encyclopedia')}</h3>
      </div>
      
      <ScrollArea className="h-[400px]">
        <div className="space-y-2">
          {categories.map(category => {
            const isExpanded = expandedCategories.has(category)
            const categoryCommands = commandExamples.filter(cmd => cmd.category === category)
            
            return (
              <div key={category}>
                <div
                  className="flex items-center gap-2 p-2 hover:bg-accent rounded cursor-pointer"
                  onClick={() => toggleCategory(category)}
                >
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                  <span className="font-medium">{category}</span>
                  <Badge variant="secondary" className="ml-auto">
                    {categoryCommands.length}
                  </Badge>
                </div>
                
                {isExpanded && (
                  <div className="ml-6 space-y-1 mt-1">
                    {categoryCommands.map((cmd, idx) => (
                      <div
                        key={`${category}-${idx}`}
                        className={`flex items-center gap-2 p-2 hover:bg-accent rounded cursor-pointer ${
                          selectedExample === cmd ? 'bg-accent' : ''
                        }`}
                        onClick={() => insertPayload(cmd)}
                      >
                        {cmd.icon}
                        <div className="flex-1">
                          <div className="font-medium text-sm">{cmd.name}</div>
                          <div className="text-xs text-muted-foreground">
                            {cmd.description}
                          </div>
                        </div>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-6 w-6"
                          onClick={(e) => {
                            e.stopPropagation()
                            copyToClipboard(cmd.payload)
                          }}
                        >
                          <Copy className="h-3 w-3" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </ScrollArea>
      
      <div className="mt-4 p-3 bg-muted rounded-lg">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <AlertCircle className="h-4 w-4" />
          <span>{t('insert_hint')}</span>
        </div>
      </div>
    </Card>
  )
}
