# Records Assistant Chat UI Fixes — Bugfix Design

## Overview

The Records Assistant chat widget has two user-facing defects. This design formalizes both bugs using the bug-condition methodology and specifies a targeted, minimal fix that preserves all existing streaming, cancellation, resume, and preset-question behavior.

**Bug 1 — Cleanup only on page unmount / stuck send button.** `App.tsx` always renders `ChatDrawer`, and `ChatDrawer` always renders `ChatWindow`. Closing the drawer only slides it out via a CSS transform; `ChatWindow` is never unmounted. Its unmount `useEffect` cleanup (abort in-flight stream + fire session summary) therefore only runs on full page unmount, never on drawer close. Consequently, closing the drawer mid-stream leaves the stream running, the summary-on-close never fires, and a `loading` state that got stuck as `true` persists into the next open, leaving the send button permanently disabled.

**Fix strategy for Bug 1.** Thread an `open` prop from `App.tsx` → `ChatDrawer` → `ChatWindow`. In `ChatWindow`, add an effect keyed on `open` that runs the close-time behavior when `open` transitions from `true` to `false`: abort any in-flight stream, reset `loading` to `false`, and fire the fire-and-forget summary when a session with messages exists. Also re-run the resume-summary fetch when `open` transitions to `true`, so reopening refreshes the resume prompt. The existing `finally` block that resets `loading` is retained; the close-time reset is an additional safety net. The existing unmount cleanup is retained for the page-unmount case.

**Bug 2 — Preset chips vanish after first message.** The grouped preset questions render only inside `EmptyState`, which is shown only when `messages.length === 0`. After the first send, the empty state is replaced by the message list and the chips are gone with no way to recall them.

**Fix strategy for Bug 2.** Introduce a collapsible "Suggested questions" toggle just above the input area that is always available, including mid-conversation. Expanding it shows the same grouped questions (Suppliers / Invoices); clicking a question sends it and collapses the panel. The empty state continues to render the full grouped chips exactly as before. The `PRESET_QUESTION_GROUPS` data is the single source of truth reused by both the empty state and the toggle panel.

All code and comments remain English-only.

## Glossary

- **Bug_Condition (C)**: The condition that triggers a bug. For Bug 1: the drawer transitions from open to closed (`open` goes `true` → `false`) while a session/stream exists. For Bug 2: `messages.length > 0` (at least one message sent), which hides the preset questions.
- **Property (P)**: The desired behavior for buggy inputs. Bug 1: abort the stream, fire the summary, and reset `loading` on close. Bug 2: preset questions remain reachable after messages exist.
- **Preservation**: Behaviors that must remain unchanged — SSE streaming + typewriter, `AbortController` cancellation with `AbortError` swallowing, the exact resume prompt text, grouped chips in the empty state, Enter/Shift+Enter send semantics, and the `canSend` enable condition for non-buggy inputs.
- **ChatWindow**: The component in `frontend/src/components/chat/ChatWindow.tsx` that owns chat state (`messages`, `loading`, `sessionId`), the SSE loop, and the input/send UI.
- **ChatDrawer**: The component in `frontend/src/components/chat/ChatDrawer.tsx` that wraps `ChatWindow` in a slide-in panel and receives `open` from `App.tsx`.
- **open**: The boolean drawer-visibility flag owned by `App.tsx`, passed to `ChatDrawer` and (after this fix) down to `ChatWindow`.
- **loading**: The `ChatWindow` state that disables the send button while a stream is in flight; `canSend = input.trim().length > 0 && !loading`.

## Bug Details

### Bug Condition

**Bug 1** manifests when the drawer is closed (`open` transitions from `true` to `false`) rather than the page being unmounted. Because `ChatWindow` stays mounted, its unmount cleanup does not run, so an in-flight stream is not aborted, the session summary is not fired, and a stuck `loading === true` is never reset for the closed session.

**Bug 2** manifests when the user has sent at least one message (`messages.length > 0`): the empty state is replaced and the grouped preset questions disappear with no affordance to bring them back.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type ChatUiEvent
  OUTPUT: boolean

  // Bug 1: drawer close while a session/stream context exists
  IF input.kind = "drawerToggle" THEN
    RETURN input.previousOpen = true
           AND input.nextOpen = false
    // On this transition the unfixed code does NOT abort the stream,
    // does NOT fire the summary, and does NOT reset loading.
  END IF

  // Bug 2: preset questions become inaccessible once messages exist
  IF input.kind = "render" THEN
    RETURN input.messageCount > 0
    // The unfixed code renders no preset questions in this state.
  END IF

  RETURN false
END FUNCTION
```

### Examples

- User opens the drawer, sends a question, and closes the drawer while tokens are still streaming. Expected: the stream is aborted and a summary request is fired. Actual (unfixed): the stream keeps running and no summary is fired.
- A stream gets stuck with `loading === true` (never emitted `done`/`error`), the user closes the drawer and reopens it. Expected: send button usable. Actual (unfixed): send button stays disabled because `loading` was never reset for the closed session.
- User sends one message, then wants a preset question again. Expected: preset questions reachable via a visible affordance. Actual (unfixed): chips are gone permanently.
- Edge case: user opens the drawer, sends nothing, and closes it. Expected: no summary fired (no messages), no error. Non-bug for the summary path.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- SSE streaming continues to render tokens with the typewriter effect (append-per-token).
- `AbortController` cancellation continues to work and the expected `AbortError` is swallowed.
- The resume prompt renders exactly as "Hello! Do you want to continue the last conversation?" with the stored session summary when one exists.
- The empty state continues to render the grouped preset question chips (Suppliers / Invoices) with send-on-click behavior.
- Enter (no Shift) sends; Shift+Enter inserts a newline.
- `canSend` remains `input.trim().length > 0 && !loading` for non-buggy inputs.

**Scope:**
All inputs that do NOT match the bug condition must be completely unaffected:
- Sending, receiving, and rendering messages while the drawer stays open.
- The empty-state preset chips and resume prompt.
- Keyboard send semantics and the send-button enable logic when the drawer is open and not mid-close.

## Hypothesized Root Cause

1. **ChatWindow never unmounts on drawer close.** `App.tsx` always mounts `ChatDrawer`, which always mounts `ChatWindow`; the drawer only slides via CSS transform. The unmount `useEffect` cleanup (abort + summary) fires only on full page unmount. This is the primary cause of Bug 1.

2. **`loading` is only reset by the send `finally` block.** If a stream ends without `done`/`error` or is interrupted in a way that the `finally` doesn't cover for a closed session, `loading` can remain `true`, disabling the send button after reopen. No close-time reset exists.

3. **Preset questions are scoped to the empty state.** `PRESET_QUESTION_GROUPS` is rendered only inside `EmptyState`, gated on `messages.length === 0`, with no alternate affordance once messages exist. This is the cause of Bug 2.

## Correctness Properties

Property 1: Bug Condition - Drawer Close Cleanup and Preset Accessibility

_For any_ input where the bug condition holds (isBugCondition returns true), the fixed code SHALL produce the correct behavior: on a drawer close transition (open true → false) it SHALL abort any in-flight stream, reset `loading` to `false`, and fire the fire-and-forget session summary when a session with messages exists; and when `messages.length > 0` the UI SHALL keep the grouped preset questions accessible through a visible affordance.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 2: Preservation - Streaming, Cancellation, Resume, Empty-State, and Input Semantics

_For any_ input where the bug condition does NOT hold (isBugCondition returns false), the fixed code SHALL produce the same observable behavior as the original: SSE tokens render with the typewriter effect, `AbortController` cancellation swallows `AbortError`, the resume prompt text is exactly "Hello! Do you want to continue the last conversation?", the empty state renders the grouped preset chips, Enter/Shift+Enter behave as before, and `canSend` remains `input.trim().length > 0 && !loading`.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

## Fix Implementation

### Changes Required

**File**: `frontend/src/App.tsx`

- No API change strictly required (already passes `open` to `ChatDrawer`). Confirm `open={chatOpen}` continues to flow to `ChatDrawer`.

**File**: `frontend/src/components/chat/ChatDrawer.tsx`

**Specific Changes**:
1. **Forward `open` to ChatWindow**: `ChatDrawer` already receives `open`. Pass it into the child: `<ChatWindow open={open} />`.

**File**: `frontend/src/components/chat/ChatWindow.tsx`

**Function/Component**: `ChatWindow`

**Specific Changes**:
1. **Accept `open` prop**: Add `interface ChatWindowProps { open: boolean }` and destructure `open`.
2. **Close-time cleanup effect**: Add a `useEffect` keyed on `open` that, when `open` becomes `false`, calls `abortRef.current?.abort()`, `setLoading(false)`, and fires `summarizeSession(sessionIdRef.current)` when `sessionIdRef.current && messageCountRef.current > 0`. Guard with a ref tracking the previous `open` value so the cleanup runs only on a true→false transition.
3. **Open-time resume refresh**: When `open` becomes `true`, re-run `getLatestSessionSummary()` to refresh `resumeSummary` (retain the existing on-mount fetch or fold it into the open-driven effect while keeping the same cancellation guard).
4. **Retain finally reset**: Keep `setLoading(false)` in the send `finally` block; the close-time reset is an additional safety net.
5. **Keep AbortError swallowing** intact in the send `catch`.
6. **Extract preset rendering data**: Keep `PRESET_QUESTION_GROUPS` as the single source; both `EmptyState` and the new toggle panel read from it.
7. **Add collapsible "Suggested questions" toggle**: Render a small toggle button above the input area, always available. Local `showSuggestions` state controls a panel that lists the grouped questions; clicking a question calls `handleSend(q)` and sets `showSuggestions` to `false`. The empty-state chips are unchanged.

## Testing Strategy

### Validation Approach

Two-phase approach: first surface counterexamples that demonstrate the bugs on unfixed code, then verify the fix works and preserves existing behavior. Because these are deterministic React UI defects, exploration properties are scoped to concrete failing cases.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bugs BEFORE implementing the fix, confirming the root-cause analysis.

**Test Plan**: Render `ChatWindow` in a test harness (React Testing Library) with mocked `api` functions. For Bug 1, render with `open={true}`, trigger a send, then rerender with `open={false}` and assert `summarizeSession` was called and the abort fired. For Bug 2, seed a sent message and assert a preset-question affordance is present.

**Test Cases**:
1. **Drawer-close summary Test**: Send a message, then set `open=false`; assert `summarizeSession` was invoked (will fail on unfixed code — cleanup only runs on unmount).
2. **Drawer-close abort Test**: Start a stream, set `open=false`; assert the `AbortController` was aborted (will fail on unfixed code).
3. **Stuck loading reset Test**: Force `loading=true`, close and reopen; assert the send button becomes enabled with non-empty input (will fail on unfixed code).
4. **Preset accessibility Test**: With `messages.length > 0`, assert a "Suggested questions" affordance exists (will fail on unfixed code).

**Expected Counterexamples**:
- `summarizeSession` not called on drawer close; abort not triggered; send button stays disabled after reopen; no preset affordance after first message.

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed code produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := fixedBehavior(input)
  ASSERT expectedBehavior(result)
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed code behaves identically to the original.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT originalBehavior(input) = fixedBehavior(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation because it generates many inputs across the domain, catches edge cases, and gives stronger guarantees that behavior is unchanged for non-buggy inputs.

**Test Plan**: Observe behavior on UNFIXED code for non-bug inputs (streaming while open, empty-state chips, resume prompt, keyboard semantics), then write property-based tests capturing those observations.

**Test Cases**:
1. **Streaming Preservation**: Observe token append + typewriter while open; verify unchanged after fix.
2. **Empty-State Chips Preservation**: Observe grouped chips in empty state; verify unchanged after fix.
3. **Resume Prompt Preservation**: Observe exact prompt text with stored summary; verify unchanged after fix.
4. **Keyboard/canSend Preservation**: Observe Enter/Shift+Enter and `canSend` behavior; verify unchanged after fix.

### Unit Tests

- Close-time cleanup fires abort + summary + loading reset on open→false transition.
- Preset toggle renders and sends the selected question, then collapses.
- Empty state still renders grouped chips.

### Property-Based Tests

- For random non-empty inputs and `loading=false`, `canSend` is always `true` (preservation of enable logic).
- For random message sequences, streamed tokens are appended in order (typewriter preservation).
- For all `open` true→false transitions with a session and messages, a summary is fired exactly once.

### Integration Tests

- Full open → send → close flow triggers summary and abort.
- Open → send → use suggested-questions toggle → send again keeps working.
- Close then reopen leaves the send button usable.
