import { useEffect, useState } from 'react'
import { applyTheme, currentTheme, saveTheme, storedTheme } from '../lib/theme'

// Switches between light and dark. Follows the OS setting until clicked; then remembers the choice.
export function ThemeToggle({ className = '' }) {
  const [theme, setTheme] = useState(currentTheme)

  useEffect(() => {
    const media = window.matchMedia?.('(prefers-color-scheme: light)')
    if (!media) return undefined
    const onChange = (event) => {
      if (storedTheme()) return // the user's explicit choice wins
      const next = event.matches ? 'light' : 'dark'
      applyTheme(next)
      setTheme(next)
    }
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  const next = theme === 'dark' ? 'light' : 'dark'
  return (
    <button
      type="button"
      className={`btn btn-ghost theme-toggle ${className}`}
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      onClick={() => {
        saveTheme(next)
        setTheme(next)
      }}
    >
      <span aria-hidden="true">{theme === 'dark' ? '☀' : '☾'}</span>
    </button>
  )
}
