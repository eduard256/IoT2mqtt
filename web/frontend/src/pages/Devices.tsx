import { useTranslation } from 'react-i18next'

export default function Devices() {
  const { t } = useTranslation()
  
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">{t('devices.title')}</h1>
        <p className="text-muted-foreground mt-1">
          Control and monitor your IoT devices
        </p>
      </div>
      
      <div className="flex items-center justify-center h-96 border-2 border-dashed rounded-lg">
        <p className="text-muted-foreground">Device control interface coming soon...</p>
      </div>
    </div>
  )
}