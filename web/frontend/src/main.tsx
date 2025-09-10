import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import axios from 'axios'
import './styles/globals.css'
import './i18n/config'

// Initialize auth token BEFORE React starts
const authStorage = localStorage.getItem('auth-storage')
if (authStorage) {
  try {
    const authData = JSON.parse(authStorage)
    if (authData?.state?.token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${authData.state.token}`
    }
  } catch (e) {
    console.error('Failed to parse auth token from localStorage')
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)