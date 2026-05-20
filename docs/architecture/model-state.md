# Model State

The canonical ForgeCAD model state lives in the shared CAD service.

## Terms

`session_id`
: A workspace or project-level CAD session.

`model_id`
: A stable model identity inside a session.

`revision_id`
: An immutable version of a model after an evaluation, import, edit, or other
  model-changing operation.

`active_model_id`
: The model used when tools are called without an explicit model ID.

`active_revision_id`
: The revision used when tools are called without an explicit revision ID.

## Why This Matters

Agents often ask for actions like "inspect the current model" or "export it".
Without a canonical service-owned current model, those requests are ambiguous:
the current model could mean the last Python `show()` call, the model currently
visible in a WebView, the active editor file, or an MCP client's last result.

ForgeCAD resolves that ambiguity at the service layer.

## Resolution Rules

When a request omits `model_id`:

1. Use the MCP client session's pinned model, if present.
2. Otherwise use the workspace session's `active_model_id`.
3. Otherwise fail with `NO_ACTIVE_MODEL`.

When a request omits `revision_id`:

1. Use the explicit model's latest revision, if `model_id` is provided.
2. Otherwise use the workspace session's `active_revision_id`.
3. Otherwise fail with `NO_ACTIVE_REVISION`.

Every response that acts on geometry must return:

- `session_id`
- `model_id`
- `revision_id`

## Revision Policy

The following operations create revisions:

- Evaluating a CAD script.
- Loading an imported model.
- Applying a parametric edit.
- Applying a future feature operation.

The following operations do not create revisions:

- Moving the camera.
- Capturing a screenshot.
- Hiding or showing tree nodes in a renderer.
- Changing clipping planes for visual inspection.
- Selecting shapes.

Those operations affect view state, not model state.

## First Model Record

Initial model records should include:

```json
{
  "model_id": "model_...",
  "session_id": "session_...",
  "name": "bracket",
  "source_kind": "script",
  "active_revision_id": "rev_...",
  "created_at": "...",
  "updated_at": "..."
}
```

Initial revision records should include:

```json
{
  "revision_id": "rev_...",
  "model_id": "model_...",
  "source_ref": {
    "kind": "file",
    "path": "models/bracket.py"
  },
  "metadata": {},
  "scene_tree": {},
  "warnings": [],
  "errors": []
}
```
