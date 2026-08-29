# Implementation Plan

- [ ] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Drawer Close Cleanup and Preset Accessibility
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bugs exist
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate both bugs exist
  - **Scoped PBT Approach**: These are deterministic UI defects; scope the property to the concrete failing cases below
  - Render `ChatWindow` (with mocked `api`) and exercise the Bug Condition from design:
    - Send a message with `open={true}`, then rerender with `open={false}`; assert `summarizeSession` was called and the in-flight `AbortController` was aborted
    - Force a stuck `loading=true`, close then reopen; assert the send button becomes enabled with non-empty input
    - With `messages.length > 0`, assert a "Suggested questions" affordance is present
  - The test assertions should match the Expected Behavior Properties from design (Property 1)
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bugs exist)
  - Document counterexamples found (summary not fired on close, abort not triggered, send stays disabled, no preset affordance)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Streaming, Cancellation, Resume, Empty-State, and Input Semantics
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs and capture it as tests:
    - Streaming while open appends tokens with the typewriter effect
    - Empty state renders the grouped preset chips (Suppliers / Invoices)
    - Resume prompt renders exactly "Hello! Do you want to continue the last conversation?" with the stored summary
    - Enter sends, Shift+Enter inserts newline; `canSend === (input.trim().length > 0 && !loading)`
  - Write property-based tests capturing observed behavior from Preservation Requirements
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ] 3. Fix for stuck send button / cleanup-on-close and vanishing preset chips

  - [ ] 3.1 Forward `open` from ChatDrawer to ChatWindow
    - In `ChatDrawer.tsx`, pass the `open` prop into `<ChatWindow open={open} />`
    - Confirm `App.tsx` continues to pass `open={chatOpen}` to `ChatDrawer`
    - _Bug_Condition: isBugCondition(input) from design (drawerToggle true→false)_
    - _Expected_Behavior: expectedBehavior(result) from design (Property 1)_
    - _Preservation: Preservation Requirements from design_
    - _Requirements: 2.1, 2.2_

  - [ ] 3.2 Add close-time cleanup and open-time resume refresh in ChatWindow
    - Add `interface ChatWindowProps { open: boolean }` and destructure `open`
    - Add a `useEffect` keyed on `open` that, on a true→false transition, calls `abortRef.current?.abort()`, `setLoading(false)`, and fires `summarizeSession(sessionIdRef.current)` when `sessionIdRef.current && messageCountRef.current > 0` (guard with a prev-open ref)
    - On open→true transition, re-run `getLatestSessionSummary()` to refresh the resume prompt (keep the cancellation guard)
    - Keep the send `finally` `setLoading(false)` and keep `AbortError` swallowing intact
    - _Bug_Condition: isBugCondition(input) from design_
    - _Expected_Behavior: expectedBehavior(result) from design (Property 1)_
    - _Preservation: Preservation Requirements 3.1, 3.2, 3.3_
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 3.3 Add always-available "Suggested questions" toggle
    - Reuse `PRESET_QUESTION_GROUPS` as the single source for both the empty state and the toggle panel (no duplicated question strings)
    - Add local `showSuggestions` state and a small toggle button above the input area, available even when `messages.length > 0`
    - Expanded panel lists the grouped questions; clicking one calls `handleSend(q)` and collapses the panel
    - Leave the empty-state grouped chips unchanged (regression guard 3.4)
    - _Bug_Condition: isBugCondition(input) from design (render with messageCount > 0)_
    - _Expected_Behavior: expectedBehavior(result) from design (Property 1)_
    - _Preservation: Preservation Requirements 3.4_
    - _Requirements: 2.4_

  - [ ] 3.4 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Drawer Close Cleanup and Preset Accessibility
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bugs are fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ] 3.5 Verify preservation tests still pass
    - **Property 2: Preservation** - Streaming, Cancellation, Resume, Empty-State, and Input Semantics
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ] 4. Checkpoint - Ensure all tests pass and the build succeeds
  - Run `cd frontend && node node_modules/typescript/bin/tsc -b && npm run build`
  - Ensure all tests pass, ask the user if questions arise.
