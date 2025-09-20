import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import HttpBackend from 'i18next-http-backend'

// Load translations from static files served from /locales/{{lng}}.json
// Files are copied from web/frontend/public/locales into dist/locales by Vite.
i18n
  .use(HttpBackend)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    backend: {
      loadPath: '/locales/{{lng}}.json',
      requestOptions: {
        cache: 'no-store'
      }
    },
    supportedLngs: ['en', 'ru', 'zh'],
    fallbackLng: 'en',
    load: 'currentOnly',
    debug: false,
    interpolation: { escapeValue: false }
  })

export default i18n
