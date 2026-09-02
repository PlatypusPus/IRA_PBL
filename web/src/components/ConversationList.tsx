import { MessageSquare, Plus, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { api, type Conversation } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

export function ConversationList({
  conversations, selected, loading, onSelect, onChanged,
}: {
  conversations: Conversation[]
  selected: number | null
  loading: boolean
  onSelect: (id: number | null) => void
  onChanged: () => void
}) {
  async function remove(conversation: Conversation) {
    try {
      await api.deleteConversation(conversation.id)
      if (selected === conversation.id) onSelect(null)
      onChanged()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "could not delete that chat")
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="px-2 py-2">
        {/* No server round-trip: an empty conversation is only worth creating
            once something has actually been asked in it. */}
        <Button variant="outline" className="w-full justify-start" onClick={() => onSelect(null)}>
          <Plus className="size-4" /> New chat
        </Button>
      </div>

      <div className="flex flex-col gap-0.5 overflow-y-auto px-2 pb-2">
        {loading && <Skeleton className="mx-1 h-9 rounded-lg" />}

        {!loading && conversations.length === 0 && (
          <p className="px-3 py-2 text-xs text-muted-foreground">
            Nothing yet. Ask for a document to start.
          </p>
        )}

        {conversations.map((conversation) => (
          <div
            key={conversation.id}
            className={
              "group flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm " +
              (conversation.id === selected ? "bg-accent" : "hover:bg-accent/50")
            }
          >
            <button
              className="flex min-w-0 flex-1 items-center gap-2 text-left"
              onClick={() => onSelect(conversation.id)}
            >
              <MessageSquare className="size-3.5 shrink-0 text-muted-foreground" />
              <span className="truncate">{conversation.title ?? "New chat"}</span>
            </button>
            <Button
              size="icon"
              variant="ghost"
              aria-label="Delete chat"
              // shown on hover, but always present for keyboard and touch
              className="size-6 opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
              onClick={() => remove(conversation)}
            >
              <Trash2 className="size-3.5" />
            </Button>
          </div>
        ))}
      </div>
    </div>
  )
}
