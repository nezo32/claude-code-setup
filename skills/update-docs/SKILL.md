---
name: update-docs
description: Keep README, RUNBOOK, API spec (OpenAPI) and request collections in sync with the code after a change. Runs a read-only drift scanner (routes in code vs. routes mentioned in docs, removed request fields still shown in examples, recent changes per module), then edits by fixed rules and validates. Use when asked to "update the readme", "update docs", "document this change", or after any API/behaviour change, before a release.
---

# Update docs

Human-facing docs drift independently of the code and of each other. This skill finds the drift and lists what to fix.

Typical doc set (configure yours in the scanner's env, see below):

| Doc | Scope |
|---|---|
| `README.md` | Architecture, quickstart, API reference, layout |
| `RUNBOOK.md` | Step-by-step "start it and prove it is alive" (curl / HTTP client) |
| `api/openapi.yaml` | The API contract (schemas, status codes) |
| `*.postman_collection.json` or `.http` files | Runnable request collection |
| per-module `README.md` | Module details |

## Run the drift scanner first

```bash
bash .claude/skills/update-docs/doc-drift.sh
```

Read-only. It reports:

1. **Route coverage**: every route found in the router files and which docs mention it. `*** NONE ***` = undocumented (a new route is the usual miss).
2. **Removed request fields still in docs**: names in `DOC_REMOVED_FIELDS` that still appear in docs. A removed field in a *request* example is drift; the same name in a *response* schema may be legitimate. Judge each hit.
3. **Recent changes per module**: last commits and working-tree state, so you know which behaviour changed.
4. **Docs inventory**: which expected docs exist.

Configuration (env vars, all optional; put them in a small wrapper script per project):

| Var | Default | Meaning |
|---|---|---|
| `DOC_FILES` | `README.md RUNBOOK.md` | docs to check, space-separated |
| `DOC_ROUTE_FILES` | empty | router source files, space-separated globs |
| `DOC_ROUTE_REGEX` | `"(GET\|POST\|PUT\|DELETE\|PATCH) /[^"]+"` | extended regex that matches one route literal |
| `DOC_REMOVED_FIELDS` | empty | request field names that must no longer appear |
| `DOC_MODULES` | `.` plus submodules | dirs to show recent changes for |

## Then edit, by these rules

- **Every command and JSON body in a doc must be currently valid.** If a request shape changes, fix it everywhere it appears: README quickstart and API reference, RUNBOOK, module README, OpenAPI, request collection. The scanner output is your checklist.
- **New endpoint**: add it to the README API table, the RUNBOOK if it is on the happy path, OpenAPI (path, responses, schemas), and the collection.
- **New status code or error** (e.g. 409 on a duplicate, 429): add it to the endpoint's responses in OpenAPI and mention it in the README.
- **Keep the RUNBOOK copy-pasteable and linear.** README is the exhaustive reference; RUNBOOK is one guided happy path. Do not turn the RUNBOOK into a second reference.
- **Never document a removed field.** Delete it from request examples and tables.

## Validate before you are done

```bash
python -c "import yaml; yaml.safe_load(open('api/openapi.yaml'))"
python -c "import json; json.load(open('api/collection.postman_collection.json'))"
bash .claude/skills/update-docs/doc-drift.sh   # re-run: no NONE routes, no removed-field hits in requests
```

Use `pre-prod-check` for the full release gate and `commit-push` to land the edits.

## Gotchas

- **A field name can be legitimate in a response and stale in a request.** Read the context before deleting.
- **The OpenAPI `$ref` description trap**: a sibling `description:` next to `$ref` is ignored by the spec. Wrap it: `allOf: [ {$ref: ...} ]` plus `description:`.
