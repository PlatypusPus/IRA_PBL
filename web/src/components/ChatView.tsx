import { useEffect, useRef, useState } from "react"
import { ArrowUp, Download, FileText, Sparkles } from "lucide-react"
import { toast } from "sonner"

import { api, type Hit, type Message } from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"

const EXAMPLES = [
  "the exam timetable",
  "invoice from:dad type:pdf",
  "lecture notes after:2026-01-01",
]

export function ChatView({ hasNumbers }: { hasNumbers: boolean }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [text, setText] = useState("")
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.history()
      .then(setMessages)
      .catch(() => toast.error("could not load your conversation"))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, sending])

  async function send(query: string) {
    const trimmed = query.trim()
    if (!trimmed || sending) return
    setText("")
    setSending(true)
    // Show the question immediately; a search round-trip is ~300ms and the
    // input feeling dead for that long reads as broken.
    const optimistic: Message = {
      id: -Date.now(), role: "user", text: trimmed, results: [],
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, optimistic])
    try {
      const reply = await api.ask(trimmed)
      setMessages((prev) => [...prev, reply])
    } catch (e) {
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id))
      setText(trimmed)
      toast.error(e instanceof Error ? e.message : "search failed")
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-8">
          {loading && <Skeleton className="h-20 rounded-xl" />}

          {!loading && messages.length === 0 && (
            <Empty hasNumbers={hasNumbers} onPick={send} />
          )}

          {messages.map((message) => (
            <MessageRow key={message.id} message={message} />
          ))}

          {sending && (
            <div className="flex gap-3">
              <Sparkles className="mt-1 size-4 shrink-0 animate-pulse text-muted-foreground" />
              <Skeleton className="h-5 w-40" />
            </div>
          )}
          <div ref={bottom} />
        </div>
      </div>

      <div className="border-t bg-background/80 backdrop-blur">
        <form
          onSubmit={(e) => { e.preventDefault(); send(text) }}
          className="mx-auto flex w-full max-w-3xl items-center gap-2 px-6 py-4"
        >
          <Input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Ask for a document…  try  invoice from:dad type:pdf"
            autoFocus
          />
          <Button type="submit" size="icon" disabled={!text.trim() || sending}>
            <ArrowUp className="size-4" />
          </Button>
        </form>
      </div>
    </div>
  )
}

function Empty({ hasNumbers, onPick }: { hasNumbers: boolean; onPick: (q: string) => void }) {
  return (
    <div className="mt-16 text-center">
      <h2 className="text-lg font-medium">
        {hasNumbers ? "What are you looking for?" : "Link a number to begin"}
      </h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
        {hasNumbers
          ? "Every PDF, photo and voice note shared with your linked numbers is searchable — including text inside scans and what was said in voice notes."
          : "Connect a WhatsApp number from the sidebar. Everything shared with it becomes searchable here."}
      </p>
      {hasNumbers && (
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {EXAMPLES.map((example) => (
            <Button key={example} variant="outline" size="sm" onClick={() => onPick(example)}>
              {example}
            </Button>
          ))}
        </div>
      )}
    </div>
  )
}

function MessageRow({ message }: { message: Message }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-primary px-4 py-2 text-primary-foreground">
          {message.text}
        </div>
      </div>
    )
  }
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">{message.text}</p>
      {message.results.map((hit) => (
        <ResultCard key={hit.document_id} hit={hit} />
      ))}
    </div>
  )
}

function ResultCard({ hit }: { hit: Hit }) {
  // The snippet arrives with *stars* around matched terms (Postgres
  // ts_headline, the same markup WhatsApp uses for bold).
  const parts = hit.snippet.split("*")
  return (
    <div
      className={
        "rounded-xl border p-4 transition-colors hover:bg-accent/40 " +
        (hit.weak ? "border-dashed opacity-70" : "")
      }
    >
      <div className="flex items-start gap-3">
        <FileText className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate font-medium">{hit.filename}</span>
            {hit.sent_at && (
              <Badge variant="secondary" className="font-normal">
                {new Date(hit.sent_at).toLocaleDateString()}
              </Badge>
            )}
            {hit.weak && (
              <Badge variant="outline" className="font-normal">
                loose match
              </Badge>
            )}
          </div>
          {hit.sender && (
            <p className="mt-0.5 text-xs text-muted-foreground">from {hit.sender}</p>
          )}
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            {parts.map((part, i) =>
              i % 2 ? <mark key={i} className="bg-transparent font-medium text-foreground">{part}</mark> : part,
            )}
          </p>
        </div>
        <a
          href={api.fileUrl(hit.document_id)}
          download
          aria-label={`Download ${hit.filename}`}
          className={buttonVariants({ variant: "ghost", size: "sm" })}
        >
          <Download className="size-4" />
        </a>
      </div>
    </div>
  )
}
