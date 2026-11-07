// Light/dark theme. The theme lives on <html data-theme="…"> (set before first paint by the
// inline script in index.html). Until the user picks one, it follows the OS setting.
const STORAGE_KEY = 'theme'
const THEME_COLORS = { dark: '#0f1320', light: '#f4f6fb' }

export function storedTheme() {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value === 'light' || value === 'dark' ? value : null
  } catch {
    return null // storage blocked (private mode): just don't remember
  }
}

export function systemTheme() {
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

export function currentTheme() {
  const value = document.documentElement.dataset.theme
  return value === 'light' || value === 'dark' ? value : storedTheme() ?? systemTheme()
}

export function applyTheme(theme) {
  document.documentElement.dataset.theme = theme
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLORS[theme])
}

export function saveTheme(theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    /* ignore */
  }
  applyTheme(theme)
}
