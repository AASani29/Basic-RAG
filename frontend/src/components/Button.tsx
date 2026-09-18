import type { ButtonHTMLAttributes } from 'react'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  isLoading?: boolean
  loadingText?: string
}

// Same extraction reasoning as FormField.tsx: once a third submit/action
// button needed the same "disabled + shows a loading label while pending"
// behavior, hand-writing it a third time stopped being the simpler option.
export default function Button({
  isLoading,
  loadingText,
  children,
  disabled,
  className = '',
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || isLoading}
      className={`rounded bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50 ${className}`}
      {...rest}
    >
      {isLoading ? (loadingText ?? 'Loading…') : children}
    </button>
  )
}
