import { useEffect, useRef, useState } from "react"
import { Loader2, Plus, Smartphone, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { api, type Account, type LinkState } from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"

const STATUS: Record<string, { label: string; variant: "default" | "secondary" | "outline" }> = {
  linked: { label: "Connected", variant: "default" },
  pending: { label: "Not linked", variant: "secondary" },
  logged_out: { label: "Signed out", variant: "outline" },
}

export function NumbersPanel({
  accounts, loading, onChanged,
}: {
  accounts: Account[]
  loading: boolean
  onChanged: () => void
}) {
  const [linking, setLinking] = useState<Account | null>(null)

  async function add() {
    try {
      const account = await api.addAccount("")
      onChanged()
      setLinking(account)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "could not add a number")
    }
  }

  async function remove(account: Account) {
    if (!confirm(`Unlink ${account.phone ?? account.label}? Its documents stop being searchable.`))
      return
    await api.removeAccount(account.id)
    toast.success("Number unlinked")
    onChanged()
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-4 py-3">
        <h2 className="text-sm font-medium">Numbers</h2>
        <Button size="sm" variant="ghost" onClick={add} aria-label="Link a number">
          <Plus className="size-4" />
        </Button>
      </div>

      <div className="flex flex-col gap-1 px-2">
        {loading && <Skeleton className="mx-2 h-14 rounded-lg" />}

        {!loading && accounts.length === 0 && (
          <p className="px-3 pb-2 text-xs leading-relaxed text-muted-foreground">
            No numbers yet. Link one and everything shared with it becomes searchable.
          </p>
        )}

        {accounts.map((account) => {
          const status = STATUS[account.status] ?? STATUS.pending
          return (
            <div
              key={account.id}
              className="group flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-accent"
            >
              <Smartphone className="size-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">
                  {account.phone ? `+${account.phone}` : account.label}
                </div>
                <div className="text-xs text-muted-foreground">
                  {account.documents} document{account.documents === 1 ? "" : "s"}
                </div>
              </div>
              {account.status === "linked" ? (
                <Badge variant={status.variant}>{status.label}</Badge>
              ) : (
                <Button size="sm" variant="outline" onClick={() => setLinking(account)}>
                  Connect
                </Button>
              )}
              <Button
                size="icon"
                variant="ghost"
                className="size-7 opacity-0 group-hover:opacity-100"
                onClick={() => remove(account)}
                aria-label="Unlink"
              >
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          )
        })}
      </div>

      <LinkDialog
        account={linking}
        onClose={() => { setLinking(null); onChanged() }}
      />
    </div>
  )
}

function LinkDialog({ account, onClose }: { account: Account | null; onClose: () => void }) {
  const [state, setState] = useState<LinkState | null>(null)
  const [phone, setPhone] = useState("")
  const [code, setCode] = useState<string | null>(null)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (!account) return
    setState(null)
    setCode(null)

    // Poll: the QR rotates every ~20s and linking finishes asynchronously when
    // the user scans, so there is nothing to await here.
    const tick = async () => {
      try {
        const next = await api.linkState(account.id)
        setState(next)
        if (next.status === "linked") {
          toast.success("WhatsApp connected")
          onClose()
          return
        }
      } catch {
        /* keep polling; a blip should not close the dialog */
      }
      timer.current = window.setTimeout(tick, 2000)
    }
    tick()
    return () => window.clearTimeout(timer.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [account])

  async function requestCode() {
    if (!account) return
    try {
      const next = await api.pairingCode(account.id, phone)
      if (next.pairing_code) setCode(next.pairing_code)
      else toast.error(next.detail ?? "could not get a code")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "could not get a code")
    }
  }

  const offline = state?.status === "bridge_offline"

  return (
    <Dialog open={!!account} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Connect WhatsApp</DialogTitle>
          <DialogDescription>
            On your phone: <b>Settings → Linked devices → Link a device</b>, then scan.
          </DialogDescription>
        </DialogHeader>

        {offline ? (
          <p className="text-sm text-destructive">{state?.detail}</p>
        ) : (
          <div className="flex flex-col items-center gap-4">
            {state?.qr ? (
              <img
                src={state.qr}
                alt="WhatsApp linking QR code"
                className="size-64 rounded-lg bg-white p-3"
              />
            ) : (
              <div className="flex size-64 items-center justify-center rounded-lg border border-dashed">
                <Loader2 className="size-5 animate-spin text-muted-foreground" />
              </div>
            )}

            <div className="w-full border-t pt-4">
              {code ? (
                <div className="text-center">
                  <p className="text-xs text-muted-foreground">
                    Enter this in WhatsApp → Link with phone number
                  </p>
                  <p className="mt-1 font-mono text-2xl tracking-[0.2em]">{code}</p>
                </div>
              ) : (
                <>
                  <p className="mb-2 text-xs text-muted-foreground">
                    On iPhone the camera often struggles with an on-screen QR. Get a
                    pairing code instead:
                  </p>
                  <div className="flex gap-2">
                    <Input
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="919876543210"
                      inputMode="numeric"
                    />
                    <Button variant="secondary" onClick={requestCode} disabled={!phone}>
                      Get code
                    </Button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
