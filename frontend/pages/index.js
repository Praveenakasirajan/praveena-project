import { useState } from 'react'
import QuestionCard from '../components/QuestionCard'
import LoadingSpinner from '../components/LoadingSpinner'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'

export default function Home() {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function fetchQuestion() {
    setError(null)
    setLoading(true)
    try {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 15000)

      const res = await fetch(`${API_URL}/question`, { signal: controller.signal })
      clearTimeout(timeout)

      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
      }

      const data = await res.json()

      if (!data.question) throw new Error('Invalid response from server')

      setQuestion(data.question)
    } catch (err) {
      if (err.name === 'AbortError') {
        setError('Request timed out. Try again.')
      } else {
        setError(err.message || 'Failed to fetch question')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-4xl">
        <header className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold">AI Interview Coach — Question Generator</h1>
          <div className="space-x-2">
            {!question ? (
              <button
                onClick={fetchQuestion}
                className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-md shadow-md hover:bg-indigo-700"
              >
                {loading ? <LoadingSpinner size={4} /> : 'Generate Question'}
              </button>
            ) : (
              <button
                onClick={fetchQuestion}
                className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-md shadow-md hover:bg-indigo-700"
              >
                {loading ? <LoadingSpinner size={4} /> : 'Next Question'}
              </button>
            )}
          </div>
        </header>

        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 text-red-700 rounded">
            Error: {error}
          </div>
        )}

        <section>
          {loading && !question ? (
            <div className="flex items-center justify-center py-12">
              <LoadingSpinner size={12} />
            </div>
          ) : question ? (
            <QuestionCard question={question} />
          ) : (
            <div className="text-center text-gray-600 py-20">
              Click "Generate Question" to create an interview question.
            </div>
          )}
        </section>
      </div>
    </main>
  )
}
