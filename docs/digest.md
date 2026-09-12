# The weekly digest

Documents arrive in group chats nobody reads to the end. `wadr digest` sends
each user a list of what actually landed on their numbers, to the number
itself, so the summary shows up in the same app the documents did:

```sh
uv run wadr digest --dry-run     # print it, send nothing
uv run wadr digest               # send
```

Schedule it weekly with cron, or Task Scheduler on Windows. Each digest starts
where the last one stopped rather than at "seven days ago", so a run that is
skipped, or a bridge that was offline for it, widens the next digest instead of
losing the week it missed.

## Summaries

Each file comes with a one line summary, because `wa-1788370118.jpeg` tells you
nothing about the exam notice inside it. Point it at any local chat model and
it writes them:

```sh
ollama pull llama3.2:3b
export WADR_SUMMARY_MODEL=llama3.2:3b   # or add it to .env
```

See what it writes before anyone else does:

```sh
uv run wadr summarize                   # summarise what has none yet
uv run wadr summarize --redo --limit 5  # rewrite five, to compare models
uv run wadr summarize --id 342          # one specific document
uv run wadr digest --dry-run --days 400 # the whole message, sent nowhere
```

It prints the model it used, so "why are the summaries bad" answers itself when
the answer is "no model is configured".

The same summary appears on each search result in the web app, which is what
makes a result readable when WhatsApp named the file `1787227836920-lnml9ufa.pdf`
and the page OCR'd into rubble. A snippet that is not prose is dropped rather
than shown, because the summary is the only useful thing left to say about it.
New documents get their summary from the next digest, or run `wadr summarize`
on a schedule next to it.

## Without a model

It falls back to the document's own opening sentence, which is right for
anything that leads with its subject and merely adequate for a scanned
letterhead. Garbled OCR is left unsummarised rather than quoted back: measured
on this corpus, rubble scores 2.25 mean word length while every real opening
scores above 4.3, so anything under 3.5 is dropped.

Summaries are written once, on first use, and never during ingest. A model call
on the webhook path would hold WhatsApp's delivery open for seconds per file.
