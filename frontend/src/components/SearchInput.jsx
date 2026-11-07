import { useEffect, useRef, useState } from 'react'

// Text box that reports changes 300ms after the user stops typing.
export function SearchInput({ value, onChange, placeholder }) {
  const [text, setText] = useState(value ?? '')
  const onChangeRef = useRef(onChange)
  useEffect(() => {
    onChangeRef.current = onChange
  })

  useEffect(() => {
    if (text === (value ?? '')) return undefined
    const timer = setTimeout(() => onChangeRef.current(text), 300)
    return () => clearTimeout(timer)
  }, [text, value])

  return (
    <input
      type="search"
      className="input"
      aria-label="Search claims"
      placeholder={placeholder}
      value={text}
      onChange={(e) => setText(e.target.value)}
    />
  )
}