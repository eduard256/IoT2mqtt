import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, Search, Sparkles, Wifi, Shield, Gauge, ChevronRight, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/hooks/use-toast'
import IntegrationWizard from '@/components/integrations/IntegrationWizard'
import DiscoveryModal from '@/components/integrations/DiscoveryModal'

interface Integration {
  name: string
  display_name: string
  description?: string
  instances: string[]
  has_setup: boolean
  branding?: {
    icon: string
    color: string
    background: string
    category: string
  }
}

export default function Integrations() {
  const { t } = useTranslation()
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedIntegration, setSelectedIntegration] = useState<Integration | null>(null)
  const [showWizard, setShowWizard] = useState(false)
  const [showDiscovery, setShowDiscovery] = useState(false)
  const [wizardMode, setWizardMode] = useState<'create' | 'edit'>('create')

  // Fetch integrations
  useEffect(() => {
    fetchIntegrations()
  }, [])

  const fetchIntegrations = async () => {
    try {
      const response = await fetch('/api/integrations')
      if (response.ok) {
        const data = await response.json()
        setIntegrations(data)
      } else {
        toast({
          title: t('error'),
          description: t('Failed to load integrations'),
          variant: 'destructive'
        })
      }
    } catch (error) {
      console.error('Error fetching integrations:', error)
      toast({
        title: t('error'),
        description: t('Failed to connect to server'),
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

  const handleIntegrationClick = (integration: Integration) => {
    if (integration.instances.length > 0) {
      // Has existing instances, ask what to do
      const action = confirm(
        `${integration.display_name} already has ${integration.instances.length} instance(s).\n\n` +
        `Would you like to create a new instance?\n` +
        `Click Cancel to edit existing instances.`
      )
      
      if (action) {
        setWizardMode('create')
      } else {
        setWizardMode('edit')
      }
    } else {
      setWizardMode('create')
    }
    
    setSelectedIntegration(integration)
    setShowWizard(true)
  }

  const filteredIntegrations = integrations.filter(integration =>
    integration.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    integration.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    integration.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const categories = {
    lighting: { icon: '💡', label: t('Lighting') },
    climate: { icon: '🌡️', label: t('Climate') },
    security: { icon: '🔒', label: t('Security') },
    sensor: { icon: '📡', label: t('Sensors') },
    media: { icon: '🎵', label: t('Media') },
    general: { icon: '⚙️', label: t('General') }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-primary to-purple-600 bg-clip-text text-transparent">
            {t('integrations.title')}
          </h1>
          <p className="text-muted-foreground mt-1">
            {t('Add and manage your device integrations')}
          </p>
        </div>
        
        <Button 
          size="lg"
          className="bg-gradient-to-r from-primary to-purple-600 hover:from-primary/90 hover:to-purple-600/90"
          onClick={() => setShowDiscovery(true)}
        >
          <Sparkles className="mr-2 h-5 w-5" />
          {t('Discover Devices')}
        </Button>
      </div>

      {/* Search Bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
        <Input
          type="text"
          placeholder={t('Search integrations...')}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10 h-12 text-lg"
        />
      </div>

      {/* Integration Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {filteredIntegrations.map((integration) => {
          const category = integration.branding?.category || 'general'
          const categoryInfo = categories[category as keyof typeof categories] || categories.general
          
          return (
            <Card
              key={integration.name}
              className="group relative overflow-hidden cursor-pointer transition-all duration-300 hover:scale-105 hover:shadow-2xl"
              onClick={() => handleIntegrationClick(integration)}
              style={{
                background: integration.branding?.background || 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
              }}
            >
              {/* Gradient Overlay for better text readability */}
              <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/20 to-transparent" />
              
              {/* Content */}
              <div className="relative p-6 h-full flex flex-col">
                {/* Icon and Category */}
                <div className="flex items-start justify-between mb-4">
                  <div className="text-4xl">
                    {integration.branding?.icon || categoryInfo.icon}
                  </div>
                  <Badge variant="secondary" className="bg-white/20 text-white border-white/30">
                    {categoryInfo.label}
                  </Badge>
                </div>

                {/* Title and Description */}
                <div className="flex-1">
                  <h3 className="text-xl font-bold text-white mb-2">
                    {integration.display_name}
                  </h3>
                  <p className="text-white/80 text-sm line-clamp-2">
                    {integration.description || `Connect your ${integration.display_name} devices`}
                  </p>
                </div>

                {/* Footer */}
                <div className="mt-4 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {integration.instances.length > 0 && (
                      <Badge className="bg-white/20 text-white border-white/30">
                        {integration.instances.length} {t('active')}
                      </Badge>
                    )}
                  </div>
                  
                  <ChevronRight className="h-5 w-5 text-white/60 group-hover:text-white transition-colors" />
                </div>

                {/* Status Icons */}
                <div className="absolute top-4 right-4 flex gap-2">
                  {integration.has_setup && (
                    <div className="p-1.5 bg-white/20 rounded-full" title="Setup available">
                      <Shield className="h-3 w-3 text-white" />
                    </div>
                  )}
                </div>
              </div>
            </Card>
          )
        })}

        {/* Add Integration Card */}
        <Card
          className="group relative overflow-hidden cursor-pointer transition-all duration-300 hover:scale-105 hover:shadow-2xl border-2 border-dashed"
          onClick={() => {
            toast({
              title: t('Coming Soon'),
              description: t('Custom integration support is coming soon!'),
            })
          }}
        >
          <div className="p-6 h-full flex flex-col items-center justify-center text-center">
            <div className="p-4 bg-muted rounded-full mb-4">
              <Plus className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold mb-2">{t('Add Custom')}</h3>
            <p className="text-sm text-muted-foreground">
              {t('Create your own integration')}
            </p>
          </div>
        </Card>
      </div>

      {/* Empty State */}
      {filteredIntegrations.length === 0 && searchQuery && (
        <div className="text-center py-12">
          <p className="text-lg text-muted-foreground">
            {t('No integrations found matching')} "{searchQuery}"
          </p>
        </div>
      )}

      {/* Stats Bar */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-8">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg">
              <Wifi className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('Total Integrations')}</p>
              <p className="text-2xl font-bold">{integrations.length}</p>
            </div>
          </div>
        </Card>
        
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-500/10 rounded-lg">
              <Shield className="h-5 w-5 text-green-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('Active Instances')}</p>
              <p className="text-2xl font-bold">
                {integrations.reduce((acc, int) => acc + int.instances.length, 0)}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/10 rounded-lg">
              <Gauge className="h-5 w-5 text-blue-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('Categories')}</p>
              <p className="text-2xl font-bold">{Object.keys(categories).length}</p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/10 rounded-lg">
              <Sparkles className="h-5 w-5 text-purple-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('Available')}</p>
              <p className="text-2xl font-bold">
                {integrations.filter(i => i.instances.length === 0).length}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Integration Wizard Modal */}
      {showWizard && selectedIntegration && (
        <IntegrationWizard
          integration={selectedIntegration}
          mode={wizardMode}
          onClose={() => {
            setShowWizard(false)
            setSelectedIntegration(null)
            fetchIntegrations() // Refresh list
          }}
        />
      )}

      {/* Discovery Modal */}
      {showDiscovery && (
        <DiscoveryModal
          onClose={() => setShowDiscovery(false)}
          onIntegrationFound={(integration) => {
            setShowDiscovery(false)
            handleIntegrationClick(integration)
          }}
        />
      )}
    </div>
  )
}