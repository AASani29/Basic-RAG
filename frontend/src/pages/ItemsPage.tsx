import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { getErrorMessage } from '../api/client'
import * as api from '../api/endpoints'
import Button from '../components/Button'
import FormField from '../components/FormField'

// Matches the page size the backend defaults to (see
// api/routes/items.py's `limit: int = Query(default=20, ...)`) — kept as an
// explicit constant here rather than omitted, so pagination math (offset +
// PAGE_SIZE) has one clear source instead of a bare literal reused in three
// places.
const PAGE_SIZE = 20

// title: matches the backend's ItemCreate exactly (min 1, max 200 — see
// backend/app/schemas/item.py). description has no length cap there either,
// so none is invented here.
const schema = z.object({
  title: z.string().min(1, 'Title is required').max(200, 'At most 200 characters'),
  description: z.string().optional(),
})

type FormValues = z.infer<typeof schema>

export default function ItemsPage() {
  const [offset, setOffset] = useState(0)
  const [formError, setFormError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  // The query key includes offset, so TanStack Query caches each page
  // separately — paging back to one already seen is served from cache
  // instantly instead of re-fetching it.
  const { data, isLoading, isError } = useQuery({
    queryKey: ['items', offset],
    queryFn: () => api.listItems(PAGE_SIZE, offset),
  })

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const createMutation = useMutation({
    mutationFn: api.createItem,
    onSuccess: () => {
      // Invalidates every cached items page, not just the one currently
      // viewed: a new item is inserted first (created_at DESC), which
      // shifts what belongs on every later page too — a stale page 2 would
      // otherwise show a row now duplicated on page 1.
      queryClient.invalidateQueries({ queryKey: ['items'] })
      reset()
    },
    onError: (error) => setFormError(getErrorMessage(error)),
  })

  const deleteMutation = useMutation({
    mutationFn: api.deleteItem,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['items'] }),
  })

  async function onSubmit(values: FormValues) {
    setFormError(null)
    await createMutation.mutateAsync({
      title: values.title,
      // The form always gives a string (possibly empty); the backend wants
      // either real text or null, not "".
      description: values.description ? values.description : null,
    })
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-gray-900">Items</h1>

      <form
        onSubmit={handleSubmit(onSubmit)}
        className="space-y-3 rounded-lg border border-gray-200 bg-white p-4"
        noValidate
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
          <div className="flex-1">
            <FormField
              id="title"
              label="Title"
              placeholder="e.g. Draft the proposal"
              error={errors.title}
              {...register('title')}
            />
          </div>
          <div className="flex-1">
            <FormField
              id="description"
              label="Description (optional)"
              placeholder="Any extra detail"
              error={errors.description}
              {...register('description')}
            />
          </div>
          <div className="pt-6 sm:pt-0 sm:self-end">
            <Button type="submit" isLoading={isSubmitting} loadingText="Adding…">
              Add item
            </Button>
          </div>
        </div>
        {formError && (
          <p role="alert" className="text-sm text-red-600">
            {formError}
          </p>
        )}
      </form>

      {isLoading && <p className="text-gray-500">Loading…</p>}
      {isError && <p className="text-red-600">Could not load items.</p>}

      {data && (
        <>
          <ul className="divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
            {data.items.length === 0 && (
              <li className="p-4 text-sm text-gray-500">No items yet — add one above.</li>
            )}
            {data.items.map((item) => (
              <li key={item.id} className="flex items-center justify-between gap-4 p-4">
                <div className="min-w-0">
                  <p className="font-medium text-gray-900">{item.title}</p>
                  {item.description && (
                    <p className="truncate text-sm text-gray-500">{item.description}</p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => deleteMutation.mutate(item.id)}
                  disabled={deleteMutation.isPending}
                  className="shrink-0 text-sm text-red-600 hover:underline disabled:opacity-50"
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>

          <div className="flex items-center justify-between text-sm text-gray-500">
            <span>
              {data.total === 0
                ? 'No items'
                : `Showing ${offset + 1}-${Math.min(offset + PAGE_SIZE, data.total)} of ${data.total}`}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
                disabled={offset === 0}
                className="rounded border border-gray-300 px-3 py-1 disabled:opacity-40"
              >
                Prev
              </button>
              <button
                type="button"
                onClick={() => setOffset((current) => current + PAGE_SIZE)}
                disabled={offset + PAGE_SIZE >= data.total}
                className="rounded border border-gray-300 px-3 py-1 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
