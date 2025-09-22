import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { getAuthToken } from '@/utils/auth'
import { Search, Loader2, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { toast } from '@/hooks/use-toast'
import BrandIcon from './BrandIcon'
import FlowSetupForm from './FlowSetupForm'
import type { IntegrationSummary } from '@/types/integration'

interface AddIntegrationModalProps {
  onClose: () => void
  onIntegrationAdded: () => void
}

export default function AddIntegrationModal({ onClose, onIntegrationAdded }: AddIntegrationModalProps) {
  const { t } = useTranslation()
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [integrations, setIntegrations] = useState<IntegrationSummary[]>([])
  const [selectedIntegration, setSelectedIntegration] = useState<IntegrationSummary | null>(null)

  useEffect(() => {
    fetchIntegrations()
  }, [])

  const fetchIntegrations = async () => {
    try {
      const token = getAuthToken()
      if (!token) {
        throw new Error('No authentication token')
      }

      const response = await fetch('/api/connectors/available', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        const data: IntegrationSummary[] = await response.json()
        // Filter out _template during development
        const filtered = data.filter(integration => !integration.name.startsWith('_'))
        setIntegrations(filtered)
      } else {
        throw new Error('Failed to load integrations')
      }
    } catch (error) {
      toast({
        title: t('Error'),
        description: t('Failed to load available integrations'),
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

  const filteredIntegrations = integrations.filter(integration =>
    integration.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    integration.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (integration.branding?.category as string | undefined)?.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const handleIntegrationSelect = (integration: IntegrationSummary) => {
    setSelectedIntegration(integration)
  }

  const handleBackToList = () => {
    setSelectedIntegration(null)
  }

  const handleDeviceAdded = () => {
    onIntegrationAdded()
    onClose()
  }

  if (selectedIntegration) {
    // We will try to use FlowSetupForm when setup.json exists. We detect it lazily inside form.
    return (
      <Dialog open={true} onOpenChange={onClose}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleBackToList}
              >
                ← {t('Back')}
              </Button>
              <BrandIcon integration={selectedIntegration.name} className="w-8 h-8" size={32} />
              {t('Add')} {selectedIntegration.display_name}
            </DialogTitle>
          </DialogHeader>
          
          {/* Prefer new FlowSetupForm; if setup not defined it will show a warning and user can go back. */}
          {selectedIntegration && (
            <FlowSetupForm
              integration={selectedIntegration}
              onCancel={handleBackToList}
              onSuccess={handleDeviceAdded}
            />
          )}
        </DialogContent>
      </Dialog>
    )
  }

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-6xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t('Add Integration')}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Search Bar */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
            <Input
              type="text"
              placeholder={t('Search integrations...')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>

          {loading ? (
            <div className="flex items-center justify-center h-32">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : filteredIntegrations.length === 0 ? (
            <Alert>
              <AlertDescription>
                {searchQuery 
                  ? t('No integrations found matching your search')
                  : t('No integrations available')}
              </AlertDescription>
            </Alert>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredIntegrations.map((integration) => (
                <Card 
                  key={integration.name}
                  className="cursor-pointer hover:shadow-lg transition-all group"
                  onClick={() => handleIntegrationSelect(integration)}
                >
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3 flex-1">
                        <BrandIcon 
                          integration={integration.name}
                          className="w-10 h-10 rounded"
                          size={40}
                        />
                        
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <h4 className="font-semibold truncate">{integration.display_name}</h4>
                            {integration.discovery && (
                              <Badge variant="secondary" className="text-xs bg-blue-100 text-blue-800">
                                {t('Auto')}
                              </Badge>
                            )}
                          </div>
                          
                          <p className="text-sm text-muted-foreground line-clamp-2">
                            {integration.description}
                          </p>

                          <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                            <span>{t('Version')}: {integration.version}</span>
                            {integration.branding?.category && (
                              <Badge variant="outline" className="text-xs">
                                {integration.branding.category as string}
                              </Badge>
                            )}
                            {(integration.flows ?? []).slice(0, 2).map(flow => (
                              <Badge key={`${integration.name}-${flow.id}`} variant="secondary" className="text-xs">
                                {flow.name}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      </div>

                      <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-end pt-4">
          <Button variant="outline" onClick={onClose}>
            {t('Cancel')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
