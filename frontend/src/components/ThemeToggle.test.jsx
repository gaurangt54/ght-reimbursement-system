import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ThemeToggle } from './ThemeToggle'

let listeners
function fakeSystem(prefersLight) {
  listeners = []
  vi.stubGlobal('matchMedia', () => ({
    matches: prefersLight,
    addEventListener: (_type, fn) => listeners.push(fn),
    removeEventListener: () => {},
  }))
}

beforeEach(() => {
  localStorage.clear()
  delete document.documentElement.dataset.theme
})
afterEach(() => vi.unstubAllGlobals())

describe('ThemeToggle', () => {
  it('starts from the theme set on <html> and switches it', async () => {
    fakeSystem(false)
    document.documentElement.dataset.theme = 'dark'
    render(<ThemeToggle />)
    await userEvent.click(screen.getByRole('button', { name: 'Switch to light theme' }))
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem('theme')).toBe('light')
    expect(screen.getByRole('button', { name: 'Switch to dark theme' })).toBeInTheDocument()
  })

  it('follows the OS setting until the user picks a theme', () => {
    fakeSystem(true)
    render(<ThemeToggle />)
    expect(screen.getByRole('button', { name: 'Switch to dark theme' })).toBeInTheDocument() // light from OS
    act(() => listeners.forEach((fn) => fn({ matches: false })))
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(screen.getByRole('button', { name: 'Switch to light theme' })).toBeInTheDocument()
  })

  it('ignores OS changes once the user has chosen', () => {
    fakeSystem(false)
    localStorage.setItem('theme', 'dark')
    document.documentElement.dataset.theme = 'dark'
    render(<ThemeToggle />)
    act(() => listeners.forEach((fn) => fn({ matches: true })))
    expect(document.documentElement.dataset.theme).toBe('dark')
  })
})
