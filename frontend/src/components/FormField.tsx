import type { InputHTMLAttributes } from 'react'
import type { FieldError } from 'react-hook-form'

interface FormFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: FieldError
}

// The one shared shape every form input in this app uses: a label, the
// input itself (spreading react-hook-form's register() props straight
// through via ...inputProps), and its validation error underneath.
// Extracted here once a third form (Items' create form, below) needed the
// exact same markup Login and Register already had — with two call sites it
// wasn't worth it, with three it was duplication.
export default function FormField({ label, error, id, ...inputProps }: FormFieldProps) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700">
        {label}
      </label>
      <input
        id={id}
        {...inputProps}
        className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
      />
      {error && <p className="mt-1 text-sm text-red-600">{error.message}</p>}
    </div>
  )
}
