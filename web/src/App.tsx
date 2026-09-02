import { useCallback, useEffect, useState } from "react"
import { LogOut, MessageSquareText } from "lucide-react"

import { api, type Account, type Conversation, type User } from "@/lib/api"
import { ApiKeysDialog } from "@/components/ApiKeysDialog"
import { AuthScreen } from "@/components/AuthScreen"
import { ChatView } from "@/components/ChatView"
import { ConversationList } from "@/components/ConversationList"
import { NumbersDialog } from "@/components/NumbersPanel"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Toaster } from "@/components/ui/sonner"

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [checking, setChecking] = useState(true)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loadingAccounts, setLoadingAccounts] = useState(true)
  const [chats, setChats] = useState<Conversation[]>([])
  const [loadingChats, setLoadingChats] = useState(true)
  // null = a new chat nobody has typed in yet; it is created on first message,
  // so abandoning one leaves nothing behind.
  const [selected, setSelected] = useState<number | null>(null)

  useEffect(() => {
    // The session cookie may already be valid from a previous visit.
    api.me().then(setUser).catch(() => {}).finally(() => setChecking(false))
  }, [])

  const refreshAccounts = useCallback(() => {
    if (!user) return
    setLoadingAccounts(true)
    api.accounts()
      .then(setAccounts)
      .catch(() => {})
      .finally(() => setLoadingAccounts(false))
  }, [user])

  const refreshChats = useCallback(() => {
    if (!user) return
    api.conversations()
      .then(setChats)
      .catch(() => {})
      .finally(() => setLoadingChats(false))
  }, [user])

  useEffect(refreshAccounts, [refreshAccounts])
  useEffect(refreshChats, [refreshChats])

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Skeleton className="h-24 w-64 rounded-xl" />
      </div>
    )
  }

  if (!user) {
    return (
      <>
        <AuthScreen onSignedIn={setUser} />
        <Toaster />
      </>
    )
  }

  async function signOut() {
    await api.logOut()
    setUser(null)
    setAccounts([])
    setChats([])
    setSelected(null)
  }

  return (
    <div className="flex h-screen">
      <aside className="hidden w-72 shrink-0 flex-col border-r bg-muted/20 md:flex">
        <div className="flex items-center gap-2 px-4 py-4">
          <div className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <MessageSquareText className="size-4" />
          </div>
          <span className="font-semibold tracking-tight">WADR</span>
        </div>

        <Separator />
        <div className="flex-1 overflow-y-auto py-1">
          <ConversationList
            conversations={chats}
            selected={selected}
            loading={loadingChats}
            onSelect={setSelected}
            onChanged={refreshChats}
          />
        </div>

        <Separator />
        <div className="flex items-center justify-between gap-1 px-2 py-2">
          <NumbersDialog
            accounts={accounts}
            loading={loadingAccounts}
            onChanged={refreshAccounts}
          />
          <div className="flex items-center gap-1">
            <ApiKeysDialog />
            <Button size="icon" variant="ghost" className="size-7" onClick={signOut} aria-label="Sign out">
              <LogOut className="size-3.5" />
            </Button>
          </div>
        </div>
        <div className="truncate px-3 pb-3 text-xs text-muted-foreground">{user.email}</div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <ChatView
          key={selected ?? "new"}  // a chat switch starts from a clean slate
          conversationId={selected}
          hasNumbers={accounts.some((a) => a.status === "linked")}
          onStarted={(id) => { setSelected(id); refreshChats() }}
        />
      </main>

      <Toaster />
    </div>
  )
}
