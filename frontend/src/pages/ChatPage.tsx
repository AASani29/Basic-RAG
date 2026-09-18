import { useMutation } from '@tanstack/react-query'
import { useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { getErrorMessage } from '../api/client'
import * as api from '../api/endpoints'
import type { ChatResponse } from '../api/endpoints'
import Button from '../components/Button'

interface ConversationTurn {
  id: string
  question: string
  response: ChatResponse
}

export default function ChatPage() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploadMessage, setUploadMessage] = useState<string | null>(null)
  const [question, setQuestion] = useState('')
  const [conversation, setConversation] = useState<ConversationTurn[]>([])

  const uploadMutation = useMutation({
    mutationFn: api.uploadDocument,
    onSuccess: (result) => {
      const plural = result.chunk_count === 1 ? '' : 's'
      setUploadMessage(`Uploaded "${result.filename}" — ${result.chunk_count} chunk${plural} indexed.`)
      // Clears the picked file so selecting the SAME file again still fires
      // onChange — a native <input type="file"> only fires when its value
      // actually changes, which it wouldn't for a repeat pick otherwise.
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    },
    onError: (error) => setUploadMessage(getErrorMessage(error, 'Upload failed.')),
  })

  const chatMutation = useMutation({
    mutationFn: api.chat,
    onSuccess: (response, askedQuestion) => {
      setConversation((prev) => [
        ...prev,
        { id: crypto.randomUUID(), question: askedQuestion, response },
      ])
      setQuestion('')
    },
  })

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }
    setUploadMessage(null)
    uploadMutation.mutate(file)
  }

  function handleAsk(event: FormEvent) {
    event.preventDefault()
    if (!question.trim() || chatMutation.isPending) {
      return
    }
    chatMutation.mutate(question)
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-gray-900">Chat</h1>

      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <label htmlFor="document" className="block text-sm font-medium text-gray-700">
          Upload a document (.txt or .pdf)
        </label>
        <input
          id="document"
          ref={fileInputRef}
          type="file"
          accept=".txt,.pdf"
          onChange={handleFileChange}
          disabled={uploadMutation.isPending}
          className="mt-2 text-sm"
        />
        {uploadMutation.isPending && <p className="mt-2 text-sm text-gray-500">Uploading…</p>}
        {uploadMessage && !uploadMutation.isPending && (
          <p className={`mt-2 text-sm ${uploadMutation.isError ? 'text-red-600' : 'text-green-700'}`}>
            {uploadMessage}
          </p>
        )}
      </div>

      <div className="space-y-4">
        {conversation.length === 0 && !chatMutation.isPending && (
          <p className="text-sm text-gray-500">
            Upload a document above, then ask a question about it.
          </p>
        )}
        {conversation.map((turn) => (
          <div key={turn.id} className="space-y-2">
            <p className="font-medium text-gray-900">You: {turn.question}</p>
            <p className="rounded-lg bg-gray-100 p-3 text-gray-800">{turn.response.answer}</p>
            {turn.response.sources.length > 0 && (
              <details className="text-sm text-gray-500">
                <summary className="cursor-pointer select-none">
                  {turn.response.sources.length}{' '}
                  {turn.response.sources.length === 1 ? 'source' : 'sources'}
                </summary>
                <ul className="mt-2 space-y-2">
                  {turn.response.sources.map((source) => (
                    <li
                      key={`${source.filename}-${source.chunk_index}`}
                      className="rounded border border-gray-200 p-2"
                    >
                      <p className="font-medium text-gray-700">
                        {source.filename} — chunk {source.chunk_index}
                      </p>
                      <p className="line-clamp-3">{source.content}</p>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        ))}
        {chatMutation.isPending && <p className="text-gray-500">Thinking…</p>}
      </div>

      <form onSubmit={handleAsk} className="flex gap-3">
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask a question about your documents…"
          disabled={chatMutation.isPending}
          className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
        />
        <Button
          type="submit"
          isLoading={chatMutation.isPending}
          loadingText="Asking…"
          disabled={!question.trim()}
        >
          Ask
        </Button>
      </form>
    </div>
  )
}
