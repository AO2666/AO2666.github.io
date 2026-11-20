# Antonio Ortega — academic site (agentic version)

A single-page academic site with two additions over the previous version:

1. **An assistant embedded in the page** — visitors can ask about the research,
   publications, students, courses, awards, service, funding and contact details.
2. **Self-maintaining content** — the recent-publication list and the live
   citation statistics are generated from OpenAlex instead of being typed into
   the HTML.

## Files

```
index.html                          the whole site (one file, no build step)
data/publications.json              generated data the page reads at load time
scripts/update_publications.py      regenerates data/publications.json
images/IntroGSP-Cover.jpg           book cover
.github/workflows/update-publications.yml   weekly refresh on GitHub Actions
```

## Deploying to ao2666.github.io

Copy `index.html`, the `data/` folder, the `images/` folder, `scripts/` and
`.github/` into the root of the `ao2666.github.io` repository, then commit and
push. GitHub Pages serves `index.html` at the repository root.

The page must be served over HTTP (GitHub Pages is), not opened as a local
`file://` path — otherwise the browser blocks the `fetch` of
`data/publications.json` and the page falls back to its built-in snapshot.

## 1. The assistant

**Default mode — no key, no server.** The assistant indexes the text of the page
in the visitor's browser and answers by quoting the passages that match the
question. Nothing is sent anywhere, so it works on a plain static site with no
account and no API key. It is deliberately extractive: it will not invent facts.

**Optional mode — a real language model.** Open the gear icon in the assistant
panel and enter an endpoint URL. The page then POSTs:

```json
{ "question": "…", "context": "…the most relevant sections of this page…" }
```

and expects `{ "answer": "…" }` back. An optional bearer token can be set too.

Do **not** put a provider API key in `index.html` — the file is public. Instead
put a tiny proxy in front of the model, for example a Cloudflare Worker that
holds the key as a secret:

```js
export default {
  async fetch(req, env) {
    const { question, context } = await req.json();
    const r = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${env.OPENAI_API_KEY}`
      },
      body: JSON.stringify({
        model: "gpt-4o-mini",
        messages: [
          { role: "system", content:
            "Answer only from the CONTEXT. If the answer is not there, say so." },
          { role: "user", content: `CONTEXT:\n${context}\n\nQUESTION: ${question}` }
        ]
      })
    });
    const d = await r.json();
    return Response.json({ answer: d.choices[0].message.content });
  }
};
```

Set `OPENAI_API_KEY` with `wrangler secret put OPENAI_API_KEY`, deploy, and paste
the Worker URL into the assistant's settings. Any provider works the same way —
the page only needs `{answer}` back.

## 2. Automatic updates

`scripts/update_publications.py` queries OpenAlex (free, no key needed at this
volume) for the author record and the most recent works, then writes
`data/publications.json`:

```bash
python3 scripts/update_publications.py --since 2024-01-01 --limit 30
```

It filters out works OpenAlex has mis-attributed to a namesake (by checking the
affiliation is USC or unrecorded), de-duplicates titles, and shortens venue
names. `index.html` fetches that JSON on load and renders the "Recent" tab and
the OpenAlex statistics line.

`.github/workflows/update-publications.yml` runs the script every Monday and
commits the result, so the site updates itself. You can also trigger it from the
repository's **Actions → Update publications and statistics → Run workflow**.

Optional repository secrets (Settings → Secrets and variables → Actions):

| Secret | Purpose |
|---|---|
| `OPENALEX_API_KEY` | free key from https://openalex.org/settings/api — raises the daily limit |
| `OPENALEX_MAILTO` | your e-mail, for OpenAlex's polite pool |

Neither is required.

### What stays hand-edited

The headline statistics (Google Scholar citations, h-index, publications, PhD
graduates, best paper awards, years at USC), the best-paper and student-paper
award lists, awards, service, lab members, alumni, courses, funding and contact
details are curated content in `index.html`. Only the recent-publication list and
the OpenAlex statistics line are generated.

To change the author being tracked, edit `AUTHOR_ID` in
`scripts/update_publications.py` (default `A5040001106`, Antonio Ortega at USC).
