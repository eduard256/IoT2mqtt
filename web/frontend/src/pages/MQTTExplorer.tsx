import { useTranslation } from 'react-i18next'

export default function MQTTExplorer() {
  const { t } = useTranslation()
  
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">{t('mqtt_explorer.title')}</h1>
        <p className="text-muted-foreground mt-1">
          Browse and interact with MQTT topics
        </p>
      </div>
      
      <div className="flex items-center justify-center h-96 border-2 border-dashed rounded-lg">
        <p className="text-muted-foreground">MQTT Explorer interface coming soon...</p>
      </div>
    </div>
  )
}