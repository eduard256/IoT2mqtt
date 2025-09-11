import { useState, useEffect } from 'react'

interface BrandIconProps {
  integration: string
  className?: string
  size?: number
}

export default function BrandIcon({ integration, className = "w-8 h-8", size = 32 }: BrandIconProps) {
  const [iconSrc, setIconSrc] = useState<string | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    const loadIcon = async () => {
      if (error) return

      try {
        // Try to load integration-specific icon
        const response = await fetch(`/api/integrations/${integration}/icon`)
        
        if (response.ok) {
          const svgText = await response.text()
          const blob = new Blob([svgText], { type: 'image/svg+xml' })
          const url = URL.createObjectURL(blob)
          setIconSrc(url)
        } else {
          throw new Error('Icon not found')
        }
      } catch (error) {
        console.log(`No icon found for ${integration}, using default`)
        setIconSrc('/icons/default.svg')
        setError(true)
      }
    }

    loadIcon()

    // Cleanup blob URL on unmount
    return () => {
      if (iconSrc && iconSrc.startsWith('blob:')) {
        URL.revokeObjectURL(iconSrc)
      }
    }
  }, [integration, error])

  useEffect(() => {
    // Reset error state when integration changes
    setError(false)
  }, [integration])

  if (!iconSrc) {
    // Loading placeholder
    return (
      <div 
        className={`${className} bg-gray-200 animate-pulse rounded`}
        style={{ width: size, height: size }}
      />
    )
  }

  return (
    <img
      src={iconSrc}
      alt={`${integration} icon`}
      className={className}
      style={{ width: size, height: size }}
      onError={() => {
        if (!error) {
          setError(true)
          setIconSrc('/icons/default.svg')
        }
      }}
    />
  )
}