import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { getAuthToken } from '@/utils/auth'
import { ArrowLeft, Settings, Trash2, Play, Square, RotateCcw, Plus, Loader2, CheckCircle, AlertCircle, Clock, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { toast } from '@/hooks/use-toast'
import BrandIcon from './BrandIcon'
import EditInstanceDialog from './EditInstanceDialog'

interface IntegrationInstance {
  instance_id: string
  friendly_name: string
  integration: string
  status: string
  device_count: number
  last_seen?: string
  created_at: string
  config: Record<string, any>
}

interface IntegrationInstancesPageProps {
  integrationName: string
  onBack: () => void
}

export default function IntegrationInstancesPage({ integrationName, onBack }: IntegrationInstancesPageProps) {
  const { t } = useTranslation()
  const [loading, setLoading] = useState(true)
  const [instances, setInstances] = useState<IntegrationInstance[]>([])
  // @ts-ignore - selectedInstance will be used in future features
  const [selectedInstance, setSelectedInstance] = useState<IntegrationInstance | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [instanceToDelete, setInstanceToDelete] = useState<string | null>(null)
  const [editingInstanceId, setEditingInstanceId] = useState<string | null>(null)

  useEffect(() => {
    fetchInstances()
  }, [integrationName])

  const fetchInstances = async () => {
    try {
      const token = getAuthToken()
      if (!token) {
        throw new Error('No authentication token')
      }

      const response = await fetch(`/api/integrations/${integrationName}/instances`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        const data = await response.json()
        setInstances(data)
      } else {
        throw new Error('Failed to load instances')
      }
    } catch (error) {
      toast({
        title: t('Error'),
        description: t('Failed to load instances'),
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

  const handleInstanceAction = async (instanceId: string, action: 'start' | 'stop' | 'restart' | 'rebuild') => {
    setActionLoading(`${action}-${instanceId}`)

    try {
      const token = getAuthToken()
      const response = await fetch(`/api/integrations/instances/${instanceId}/${action}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        toast({
          title: t('Success'),
          description: t(`Instance {{action}} successfully`, { action })
        })
        fetchInstances() // Refresh data
      } else {
        throw new Error(`Failed to ${action} instance`)
      }
    } catch (error) {
      toast({
        title: t('Error'),
        description: t(`Failed to {{action}} instance`, { action }),
        variant: 'destructive'
      })
    } finally {
      setActionLoading(null)
    }
  }

  const handleDeleteInstance = async () => {
    if (!instanceToDelete) return

    setActionLoading(`delete-${instanceToDelete}`)
    
    try {
      const token = getAuthToken()
      const response = await fetch(`/api/integrations/instances/${instanceToDelete}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        toast({
          title: t('Success'),
          description: t('Instance deleted successfully')
        })
        setShowDeleteDialog(false)
        setInstanceToDelete(null)
        fetchInstances()
      } else {
        throw new Error('Failed to delete instance')
      }
    } catch (error) {
      toast({
        title: t('Error'),
        description: t('Failed to delete instance'),
        variant: 'destructive'
      })
    } finally {
      setActionLoading(null)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'connected':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-500" />
      case 'offline':
        return <Clock className="w-4 h-4 text-gray-500" />
      case 'configuring':
        return <Loader2 className="w-4 h-4 text-yellow-500 animate-spin" />
      default:
        return <Clock className="w-4 h-4 text-gray-500" />
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'connected':
        return t('Connected')
      case 'error':
        return t('Error')
      case 'offline':
        return t('Offline')
      case 'configuring':
        return t('Configuring')
      default:
        return t('Unknown')
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected':
        return 'text-green-600'
      case 'error':
        return 'text-red-600'
      case 'offline':
        return 'text-gray-500'
      case 'configuring':
        return 'text-yellow-600'
      default:
        return 'text-gray-500'
    }
  }

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={onBack}
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          {t('Back')}
        </Button>
        
        <div className="flex items-center gap-3">
          <BrandIcon integration={integrationName} className="w-8 h-8" size={32} />
          <div>
            <h1 className="text-2xl font-bold capitalize">{integrationName} {t('Integration')}</h1>
            <p className="text-muted-foreground">
              {t('Manage your {{integration}} instances', { integration: integrationName })}
            </p>
          </div>
        </div>
      </div>

      {/* Instances List */}
      {instances.length === 0 ? (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {t('No instances configured for this integration yet.')}
          </AlertDescription>
        </Alert>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {instances.map((instance) => (
            <Card key={instance.instance_id} className="relative">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <CardTitle className="text-lg">{instance.friendly_name}</CardTitle>
                    <CardDescription>
                      ID: {instance.instance_id}
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    {getStatusIcon(instance.status)}
                    <Badge 
                      variant="outline" 
                      className={getStatusColor(instance.status)}
                    >
                      {getStatusText(instance.status)}
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              
              <CardContent className="space-y-4">
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">{t('Devices')}:</span>
                    <span className="font-medium">{instance.device_count}</span>
                  </div>
                  
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">{t('Created')}:</span>
                    <span>{formatTimestamp(instance.created_at)}</span>
                  </div>
                  
                  {instance.last_seen && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">{t('Last seen')}:</span>
                      <span>{formatTimestamp(instance.last_seen)}</span>
                    </div>
                  )}
                </div>

                {/* Instance Actions */}
                <div className="flex gap-2">
                  {instance.status === 'connected' ? (
                    <Button 
                      size="sm" 
                      variant="outline"
                      onClick={() => handleInstanceAction(instance.instance_id, 'stop')}
                      disabled={actionLoading === `stop-${instance.instance_id}`}
                    >
                      {actionLoading === `stop-${instance.instance_id}` ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <Square className="w-3 h-3" />
                      )}
                    </Button>
                  ) : (
                    <Button 
                      size="sm" 
                      variant="outline"
                      onClick={() => handleInstanceAction(instance.instance_id, 'start')}
                      disabled={actionLoading === `start-${instance.instance_id}`}
                    >
                      {actionLoading === `start-${instance.instance_id}` ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <Play className="w-3 h-3" />
                      )}
                    </Button>
                  )}
                  
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleInstanceAction(instance.instance_id, 'restart')}
                    disabled={actionLoading === `restart-${instance.instance_id}`}
                  >
                    {actionLoading === `restart-${instance.instance_id}` ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <RotateCcw className="w-3 h-3" />
                    )}
                  </Button>

                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleInstanceAction(instance.instance_id, 'rebuild')}
                    disabled={actionLoading === `rebuild-${instance.instance_id}`}
                    title="Rebuild container (rebuild image and recreate)"
                  >
                    {actionLoading === `rebuild-${instance.instance_id}` ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <RefreshCw className="w-3 h-3" />
                    )}
                  </Button>

                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setEditingInstanceId(instance.instance_id)}
                  >
                    <Settings className="w-3 h-3" />
                  </Button>
                  
                  <Button 
                    size="sm" 
                    variant="outline"
                    onClick={() => {
                      setInstanceToDelete(instance.instance_id)
                      setShowDeleteDialog(true)
                    }}
                    disabled={actionLoading === `delete-${instance.instance_id}`}
                  >
                    {actionLoading === `delete-${instance.instance_id}` ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <Trash2 className="w-3 h-3 text-red-500" />
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Add New Instance Card */}
      <Card className="border-dashed border-2 hover:border-primary/50 transition-colors cursor-pointer">
        <CardContent className="flex items-center justify-center py-12">
          <div className="text-center">
            <Plus className="w-8 h-8 mx-auto mb-2 text-muted-foreground" />
            <p className="text-muted-foreground">{t('Add new instance')}</p>
          </div>
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('Delete Instance')}</DialogTitle>
            <DialogDescription>
              {t('Are you sure you want to delete this instance? This action cannot be undone and will remove:')}
              <ul className="list-disc pl-6 mt-2">
                <li>{t('Docker container')}</li>
                <li>{t('Configuration files')}</li>
                <li>{t('MQTT topics')}</li>
                <li>{t('All associated data')}</li>
              </ul>
            </DialogDescription>
          </DialogHeader>
          
          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => setShowDeleteDialog(false)}
              disabled={actionLoading !== null}
            >
              {t('Cancel')}
            </Button>
            <Button 
              variant="destructive" 
              onClick={handleDeleteInstance}
              disabled={actionLoading !== null}
            >
              {actionLoading === `delete-${instanceToDelete}` ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Trash2 className="w-4 h-4 mr-2" />
              )}
              {t('Delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Instance Dialog */}
      {editingInstanceId && (
        <EditInstanceDialog
          integration={integrationName}
          instanceId={editingInstanceId}
          onClose={() => setEditingInstanceId(null)}
          onSuccess={() => {
            fetchInstances()
            setEditingInstanceId(null)
          }}
        />
      )}
    </div>
  )
}