import { useEffect, useState } from "react"
import { Check, Copy, Plug, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { api, type ApiKey } from "@/lib/api"
import { Button } from "@/components/ui/button"
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog"

export function ApiKeysDialog() {
  const [open, setOpen] = useState(false)
  const [keys, setKeys] = useState<ApiKey[]>([])
  // Shown once, right after minting: the server only ever stores a hash, so
  // there is no second chance to read it.
  const [fresh, setFresh] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (open) api.keys().then(setKeys).catch(() => {})
  }, [open])

  async function mint() {
    try {
      const { key, keys: next } = await api.createKey("Agent key")
      setFresh(key)
      setKeys(next)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "could not create a key")
    }
  }

  async function copy(text: string) {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const config = `{
  "mcpServers": {
    "wadr": {
      "command": "uv",
      "args": ["run", "--directory", "${"<path to IRPBL>"}", "wadr", "mcp"],
      "env": { "WADR_API_KEY": "${fresh ?? "<your key>"}" }
    }
  }
}`

  return (
    <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (!next) setFresh(null) }}>
      <DialogTrigger
        render={
          <Button size="icon" variant="ghost" className="size-7" aria-label="Agent access" />
        }
      >
        <Plug className="size-3.5" />
      </DialogTrigger>

      <DialogContent className="sm:max-w-lg [&>*]:min-w-0">
        <DialogHeader>
          <DialogTitle>Agent access</DialogTitle>
          <DialogDescription>
            Give Claude — or any MCP client — the ability to search and read
            these documents. A key acts for this account only.
          </DialogDescription>
        </DialogHeader>

        {fresh && (
          <div className="rounded-lg border border-dashed p-3">
            <p className="text-xs text-muted-foreground">
              Copy this now — it is never shown again.
            </p>
            <div className="mt-2 flex items-center gap-2">
              <code className="min-w-0 flex-1 truncate rounded bg-muted px-2 py-1 text-xs">
                {fresh}
              </code>
              <Button size="icon" variant="outline" className="size-8" onClick={() => copy(fresh)}>
                {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              </Button>
            </div>
          </div>
        )}

        <div className="flex flex-col gap-2">
          {keys.length === 0 && !fresh && (
            <p className="text-sm text-muted-foreground">No keys yet.</p>
          )}
          {keys.map((key) => (
            <div key={key.id} className="flex items-center gap-3 rounded-lg border px-3 py-2">
              <code className="text-xs text-muted-foreground">{key.prefix}…</code>
              <span className="min-w-0 flex-1 truncate text-sm">{key.label}</span>
              <span className="text-xs text-muted-foreground">
                {key.last_used_at ? "used" : "never used"}
              </span>
              <Button
                size="icon"
                variant="ghost"
                className="size-7"
                aria-label="Revoke"
                onClick={async () => {
                  await api.revokeKey(key.id)
                  setKeys(await api.keys())
                  toast.success("Key revoked")
                }}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          ))}
        </div>

        <Button onClick={mint} variant="secondary">Create a key</Button>

        <div className="min-w-0">
          <p className="mb-2 text-xs text-muted-foreground">
            Then add this to your Claude config and restart it:
          </p>
          <pre className="max-w-full overflow-x-auto rounded-lg bg-muted p-3 text-xs leading-relaxed">
            {config}
          </pre>
        </div>
      </DialogContent>
    </Dialog>
  )
}
