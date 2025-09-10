import { useTranslation } from 'react-i18next'

export default function Integrations() {
  const { t } = useTranslation()
  
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">{t('integrations.title')}</h1>
        <p className="text-muted-foreground mt-1">
          Add and manage your device integrations
        </p>
      </div>
      
      <div className="flex items-center justify-center h-96 border-2 border-dashed rounded-lg">
        <p className="text-muted-foreground">Integration management interface coming soon...</p>
      </div>
    </div>
  )
}