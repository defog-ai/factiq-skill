# Publish a bespoke HTML report to FactIQ

Writable FactIQ MCP clients expose `publish_html_report`. Configured read-only
connectors do not list or accept it. The tool returns the canonical
`https://www.factiq.com/share/{share_id}` URL.

Use this for a bespoke report that should live on FactIQ rather than only as a
local file. Existing structured report JSON remains a separate local output.

## Contract and limits

Every eligible FactIQ data-tool result includes:

```json
"_factiq_data_ref": {
  "id": "opaque-reference-id",
  "expires_at": "2026-08-23T12:00:00+00:00"
}
```

The reference belongs to the authenticated user and expires after 24 hours.
`publish_html_report` accepts only:

- `question`: the report title/question, at most 2,000 characters;
- `html`: one complete UTF-8 HTML document, at most 1,000,000 bytes;
- `data_assets`: at most 12 `{key, ref_id}` mappings, at most 1,000,000 JSON
  bytes total;
- `model`: an optional author/model label, at most 100 characters.

Keys start with a letter and contain only letters, digits, `_`, or `-`. A key
named `jobs` is available inside the published page at `./data/jobs.json`.
FactIQ validates every reference and copies the exact prior MCP result bytes
into immutable, report-scoped JSON assets in the same transaction as the HTML.
Missing, expired, or another user's references make the entire publish call
fail; no partial public page is created.

## Complete workflow

1. Fetch with `run_sql`, `get_series`, or another FactIQ data tool. Keep each
   returned `_factiq_data_ref.id`; do not copy its `results` rows into a later
   model-authored payload.
2. Immediately save each exact tool result locally for authoring and preview:

   ```bash
   python3 "{plugin_root}/scripts/build_viz.py" save \
     --tool run_sql --match "distinctive SQL fragment" --out /tmp/jobs.json
   ```

   `save` copies the harness transcript bytes. Never recreate the JSON with
   Write, a heredoc, or model-generated row arrays.
3. Copy `assets/viz-shell.html` to a report template. Read each dataset with the
   shell's asynchronous loader:

   ```js
   const jobs = await factiqData("jobs");
   const rows = jobs.results;
   ```

   The checked-in shell has two modes. An assembled local preview reads `jobs`
   from its injected `DATA`; the original unassembled template sees the
   `__FACTIQ_DATA__` marker and fetches `./data/jobs.json`. Do not paste rows
   into the HTML.
4. Assemble and locally render the preview against the exact saved files:

   ```bash
   python3 "{plugin_root}/scripts/build_viz.py" assemble \
     --template report-template.html \
     --data jobs=/tmp/jobs.json markets=/tmp/markets.json \
     --out /tmp/report-preview.html
   python3 "{plugin_root}/scripts/build_viz.py" render \
     /tmp/report-preview.html --out /tmp/report-preview.png
   ```

   Inspect the PNG and iterate until the report is readable at its target
   width. Publish the **unassembled template**, not `report-preview.html`; the
   assembled preview contains local data by design.
5. Call `publish_html_report` once with the unassembled template text and the
   references from step 1:

   ```json
   {
     "question": "What changed in the labor market?",
     "html": "<the unassembled report-template.html text>",
     "data_assets": [
       {"key": "jobs", "ref_id": "<run_sql _factiq_data_ref.id>"},
       {"key": "markets", "ref_id": "<get_market_data _factiq_data_ref.id>"}
     ],
     "model": "the current model name"
   }
   ```

   Verify that neither the HTML nor the publish arguments contains a source
   result row. Return the `share_url` from the tool response to the user.

Published HTML executes in a sandboxed iframe without FactIQ cookie/storage,
parent-DOM, or top-navigation access. It may run scripts and fetch its own
immutable report-scoped JSON assets. For responsive height, the report can
send `parent.postMessage({type: "factiq-report-height", height: document.documentElement.scrollHeight}, "*")`;
FactIQ bounds the accepted height.
