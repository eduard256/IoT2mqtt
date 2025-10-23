import { Button } from '@/components/ui/button'
import { Pencil, X } from 'lucide-react'

interface DeviceListItemProps {
  device: any
  index: number
  onRemove?: () => void
  onEdit?: () => void
  canRemove?: boolean
}

export function DeviceListItem({
  device,
  index,
  onRemove,
  onEdit,
  canRemove = true
}: DeviceListItemProps) {
  return (
    <div className="flex items-center justify-between p-3 border rounded-lg bg-background">
      <div className="flex-1">
        <div className="font-medium text-sm">{device.name}</div>
        <div className="text-xs text-muted-foreground">
          {device.ip}{device.port ? `:${device.port}` : ''}
        </div>
      </div>
      <div className="flex gap-1">
        {onEdit && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onEdit}
            className="hover:bg-primary/10"
          >
            <Pencil className="h-3 w-3" />
          </Button>
        )}
        {canRemove && onRemove && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onRemove}
            className="text-destructive hover:text-destructive hover:bg-destructive/10"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  )
}
