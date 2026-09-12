# Give it to an agent (MCP)

WADR is an MCP server, so Claude or any MCP client can search and *read* your
documents and answer from their contents.

## Creating a key

In the web app, click the plug icon next to your email, create a key, and paste
the config it shows you into Claude Desktop or Claude Code:

```json
{
  "mcpServers": {
    "wadr": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/IRPBL", "wadr", "mcp"],
      "env": { "WADR_API_KEY": "wadr_..." }
    }
  }
}
```

Or from the terminal: `uv run wadr apikey you@example.com`.

## Tools

Four tools, deliberately few:

| tool | what it is for |
|---|---|
| `search_documents` | find candidates; supports the same `from:` / `type:` / `after:` filters |
| `read_document` | the extracted text, so the agent answers from contents rather than filenames |
| `recent_documents` | "what came in this week" |
| `find_similar` | "more like this one" |

## Key scope

A key is scoped to one account, so an agent can only ever reach documents that
account's own numbers received. Keys are stored as SHA-256 hashes and the
plaintext is shown once, at creation. Revoking a key takes effect on the next
call.

Search results carry `weak: true` when nothing really matched, so the model can
say it found nothing instead of bluffing.
