import { useEffect, useState } from 'react'
import { storage } from './utils'

const KEY = 'newssense-theme' // also read by the inline script in index.html

type Theme = 'light' | 'dark'

const current = (): Theme => (document.documentElement.classList.contains('dark') ? 'dark' : 'light')

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(current)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  // Follow the system setting until the reader picks a theme themselves
  useEffect(() => {
    if (storage.get(KEY)) return
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (event: MediaQueryListEvent) => setTheme(event.matches ? 'dark' : 'light')
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    storage.set(KEY, next)
    setTheme(next)
  }

  return { theme, toggle }
}
