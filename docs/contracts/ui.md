# Shared controls

Keep the existing green, cream and square-corner identity. `space` and `typeSize` in `theme.ts` are the small shared scale; do not rewrite every screen to use them in one change.

```tsx
<Button onPress={save} busy={saving} busyLabel="Saving changes…">Save changes</Button>
<Button variant="secondary" onPress={cancel}>Cancel</Button>
<Button variant="danger" onPress={remove}>Delete saved search</Button>
<Button variant="quiet" onPress={back}>Back to homes</Button>
```

`outline` remains supported and maps to secondary unless `variant` is explicit. Busy blocks interaction and exposes a progress label. Keep meaningful action verbs on destructive buttons; never communicate the action through red alone. Shared buttons and chips use a minimum 44×44 target. Web focus styling stays in `web.css`; hover and press styles supplement it. Use the existing `Field` purpose and error props for forms.
