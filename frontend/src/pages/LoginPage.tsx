import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { getErrorMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import Button from '../components/Button'
import FormField from '../components/FormField'

const schema = z.object({
  email: z.string().email('Enter a valid email'),
  // No min-length check here beyond "present": this is a login form, not a
  // signup form — the backend either accepts the password or it doesn't,
  // and duplicating its rules here would just be two places that could
  // disagree about what a "valid" password looks like.
  password: z.string().min(1, 'Password is required'),
})

type FormValues = z.infer<typeof schema>

export default function LoginPage() {
  const { login } = useAuth()
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
      await login(values.email, values.password)
      navigate('/items')
    } catch (error) {
      setServerError(getErrorMessage(error, 'Could not log in. Please try again.'))
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <form
        onSubmit={handleSubmit(onSubmit)}
        className="w-full max-w-sm space-y-4 rounded-lg border border-gray-200 bg-white p-8 shadow-sm"
        noValidate
      >
        <h1 className="text-xl font-semibold text-gray-900">Log in</h1>

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
          autoComplete="current-password"
          error={errors.password}
          {...register('password')}
        />

        <Button type="submit" isLoading={isSubmitting} loadingText="Logging in…" className="w-full">
          Log in
        </Button>

        <p className="text-center text-sm text-gray-500">
          No account?{' '}
          <Link to="/register" className="font-medium text-gray-900 underline">
            Register
          </Link>
        </p>
      </form>
    </div>
  )
}
