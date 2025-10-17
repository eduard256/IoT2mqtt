import { useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2 } from 'lucide-react'
import { getAuthToken } from '@/utils/auth'
import type { StepComponentProps } from '../../types'

export function OAuthStep({
  step,
  flowState,
  updateFlowState,
  busy,
  setBusy,
  setError,
  onNext
}: StepComponentProps) {
  const provider = step.oauth?.provider ?? 'provider'
  const sessionActive = flowState.oauth[provider]

  const startOAuth = useCallback(async () => {
    if (!provider) {
      setError('OAuth provider not specified')
      return
    }

    setBusy(true)
    setError(null)

    try {
      const token = getAuthToken()
      const response = await fetch(`/api/oauth/${provider}/session`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ redirect_uri: step.oauth?.redirect_uri })
      })

      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data?.detail ?? 'Failed to start OAuth flow')
      }

      const data = await response.json()

      // Open popup window
      const popup = window.open(data.authorization_url, '_blank', 'width=600,height=700')
      if (!popup) {
        throw new Error('Please allow popups to continue OAuth authorization')
      }

      // Listen for authorization completion
      const messageHandler = async (event: MessageEvent) => {
        if (!event.data || typeof event.data !== 'object') return
        if (!('status' in event.data)) return

        if (event.data.status === 'authorized' && event.data.session_id) {
          window.removeEventListener('message', messageHandler)
          await fetchOAuthSession(event.data.session_id)
        }
      }

      window.addEventListener('message', messageHandler)
    } catch (e: any) {
      setError(e?.message ?? 'Failed to start OAuth flow')
    } finally {
      setBusy(false)
    }
  }, [provider, step.oauth?.redirect_uri, setBusy, setError])

  const fetchOAuthSession = useCallback(
    async (sessionId: string) => {
      try {
        const token = getAuthToken()
        const response = await fetch(`/api/oauth/session/${sessionId}`, {
          headers: { Authorization: `Bearer ${token}` }
        })

        if (!response.ok) throw new Error('Failed to load OAuth session')

        const session = await response.json()

        updateFlowState(prev => ({
          ...prev,
          oauth: {
            ...prev.oauth,
            [session.provider]: session
          }
        }))

        // Auto-advance if configured
        if (step.auto_advance) {
          await onNext()
        }
      } catch (e: any) {
        setError(e?.message ?? 'Failed to fetch OAuth session')
      }
    },
    [updateFlowState, step.auto_advance, onNext, setError]
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>{step.title ?? `Authorize ${provider}`}</CardTitle>
        {step.description && <CardDescription>{step.description}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Sign in with your {provider} account to continue. A popup window will open to complete the
          authorization.
        </p>

        <Button disabled={busy} onClick={startOAuth}>
          {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
          Authorize {provider}
        </Button>

        {sessionActive && (
          <Alert>
            <AlertDescription>
              Connected as {sessionActive.tokens?.account ?? 'authorized account'}
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  )
}
