import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { getAuthToken } from '@/utils/auth'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, AlertCircle } from 'lucide-react'
import FlowSetupForm from './FlowSetupForm'

interface EditInstanceDialogProps {
  integration: string
  instanceId: string
  onClose: () => void
  onSuccess: () => void
}

export default function EditInstanceDialog({
  integration,
  instanceId,
  onClose,
  onSuccess
}: EditInstanceDialogProps) {
  const { t } = useTranslation()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [instanceData, setInstanceData] = useState<any>(null)

  useEffect(() => {
    fetchInstanceData()
  }, [integration, instanceId])

  const fetchInstanceData = async () => {
    try {
      setLoading(true)
      setError(null)

      const token = getAuthToken()
      if (!token) {
        throw new Error('No authentication token')
      }

      const response = await fetch(`/api/instances/${integration}/${instanceId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error(`Failed to load instance: ${response.statusText}`)
      }

      const data = await response.json()
      setInstanceData(data)
    } catch (err: any) {
      setError(err?.message ?? 'Failed to load instance data')
    } finally {
      setLoading(false)
    }
  }

  const handleSuccess = () => {
    onSuccess()
    onClose()
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {t('Edit')} {instanceData?.friendly_name ?? instanceId}
          </DialogTitle>
        </DialogHeader>

        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {!loading && !error && instanceData && (
          <FlowSetupForm
            integration={{ name: integration }}
            mode="edit"
            existingInstanceId={instanceId}
            initialDevices={instanceData.devices || []}
            initialConfig={instanceData.config || {}}
            onCancel={onClose}
            onSuccess={handleSuccess}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
