# Bugfix Requirements Document

## Introduction

The Records Assistant chat widget (`frontend/src/components/chat/`) has two user-facing defects that degrade the chat experience:

1. **Stuck send button** — The send button becomes unusable (permanently disabled) in certain flows because the `loading` state can get stuck as `true`. The root of this is that `ChatWindow` is never unmounted when the drawer closes (`App.tsx` always renders `ChatDrawer` and `ChatDrawer` always renders `ChatWindow`; the drawer only slides out via a CSS transform). As a result, the cleanup logic that aborts an in-flight stream and fires the session summary only runs on full page unmount, never on drawer close. Closing the drawer mid-stream leaves the stream running and any stuck `loading` persists when the drawer reopens; the summary-on-close never fires either.

2. **Preset question chips vanish permanently** — The grouped preset questions (Suppliers / Invoices) render only in the empty state (`messages.length === 0`). After the first message is sent, the empty state is replaced by the message list and the preset chips are gone with no way to bring them back.

This fix targets both defects while preserving all existing behavior: SSE streaming, the typewriter effect, `AbortController` cancellation, the resume-summary experience (including the exact prompt text "Hello! Do you want to continue the last conversation?"), and the grouped preset-question content. All code and comments remain English-only.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the user closes the chat drawer while a stream is in flight THEN the system does not run `ChatWindow`'s cleanup (abort + summary) because `ChatWindow` stays mounted, so the stream keeps running and the fire-and-forget summary is never sent
1.2 WHEN the drawer is closed with `loading === true` (e.g. the stream never emitted `done`/`error`, or was interrupted) and later reopened THEN the send button remains disabled because `loading` was never reset for that closed session
1.3 WHEN an SSE stream ends normally without ever emitting a `done` or `error` event THEN the assistant message may stay empty, and any dependent state relies solely on the `finally` block for reset, with no signal that the turn completed
1.4 WHEN the user has sent at least one message THEN the grouped preset question chips (Suppliers / Invoices) are no longer rendered and there is no affordance to access them again

### Expected Behavior (Correct)

2.1 WHEN the user closes the chat drawer while a stream is in flight THEN the system SHALL abort the in-flight stream and fire the fire-and-forget session summary on drawer close (not only on full page unmount)
2.2 WHEN the drawer is closed with `loading === true` and later reopened THEN the send button SHALL be usable, i.e. `loading` SHALL be reset so `canSend` reflects a non-loading state
2.3 WHEN an SSE stream ends by any path (normal completion, `done`, `error`, thrown exception, or abort) THEN the system SHALL always reset `loading` to `false`
2.4 WHEN the user has sent one or more messages THEN the system SHALL keep the grouped preset questions accessible through a visible, minimal affordance that reveals the existing Suppliers / Invoices groups

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a message is sent THEN the system SHALL CONTINUE TO stream tokens via SSE and render them with the typewriter effect
3.2 WHEN a stream is in flight THEN the system SHALL CONTINUE TO support cancellation via `AbortController` and swallow the expected `AbortError`
3.3 WHEN the chat opens with no messages THEN the system SHALL CONTINUE TO show the resume prompt exactly as "Hello! Do you want to continue the last conversation?" together with the stored session summary when one exists
3.4 WHEN the empty state is shown THEN the system SHALL CONTINUE TO render the grouped preset question chips (Suppliers / Invoices) with their existing questions and send-on-click behavior
3.5 WHEN Enter (without Shift) is pressed in the input THEN the system SHALL CONTINUE TO send the message, and Shift+Enter SHALL CONTINUE TO insert a newline
3.6 WHEN the send button's enable condition is evaluated with a non-empty input and no active load THEN the system SHALL CONTINUE TO enable the button (`canSend` unchanged for non-buggy inputs)
