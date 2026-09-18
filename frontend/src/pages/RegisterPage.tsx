import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { getErrorMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import Button from '../components/Button'
import FormField from '../components/FormField'

const schema = z
  .object({
    email: z.string().email('Enter a valid email'),
    // Mirrors the backend's UserCreate schema (min 8, max 72 — the max is
    // bcrypt's own hard limit, see backend/app/schemas/user.py) so a
    // rejection shows up here as a friendly inline message instead of a
    // round trip to the server just to find out the password was too long.
    password: z.string().min(8, 'At least 8 characters').max(72, 'At most 72 characters'),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  })

type FormValues = z.infer<typeof schema>

export default function RegisterPage() {
  const { register: registerUser } = useAuth()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  async function onSubmit(values: FormValues) {
    setServerError(null)
    try {
      await registerUser(values.email, values.password)
      navigate('/items')
    } catch (error) {
      // Surfaces the backend's own message directly — e.g. "Email already
      // registered" for a 409 — rather than a generic frontend string,
      // since that message was already written to be safe to show a user.
      setServerError(getErrorMessage(error, 'Could not register. Please try again.'))
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <form
        onSubmit={handleSubmit(onSubmit)}
        className="w-full max-w-sm space-y-4 rounded-lg border border-gray-200 bg-white p-8 shadow-sm"
        noValidate
      >
        <h1 className="text-xl font-semibold text-gray-900">Create an account</h1>

        {serverError && (
          <p role="alert" className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">
            {serverError}
          </p>
        )}

        <FormField
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          error={errors.email}
          {...register('email')}
        />

        <FormField
          id="password"
          label="Password"
          type="password"
          autoComplete="new-password"
          error={errors.password}
          {...register('password')}
        />

        <FormField
          id="confirmPassword"
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          error={errors.confirmPassword}
          {...register('confirmPassword')}
        />

        <Button type="submit" isLoading={isSubmitting} loadingText="Creating account…" className="w-full">
          Create account
        </Button>

        <p className="text-center text-sm text-gray-500">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-gray-900 underline">
            Log in
          </Link>
        </p>
      </form>
    </div>
  )
}
