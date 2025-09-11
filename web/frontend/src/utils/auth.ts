/**
 * Utility functions for authentication
 */

/**
 * Get authentication token from localStorage
 * Token is stored in Zustand persist storage under 'auth-storage' key
 */
export const getAuthToken = (): string | null => {
  const authStorage = localStorage.getItem('auth-storage')
  if (authStorage) {
    try {
      const authData = JSON.parse(authStorage)
      return authData?.state?.token || null
    } catch (e) {
      console.error('Failed to parse auth token:', e)
      return null
    }
  }
  return null
}

/**
 * Check if user is authenticated
 */
export const isAuthenticated = (): boolean => {
  return getAuthToken() !== null
}