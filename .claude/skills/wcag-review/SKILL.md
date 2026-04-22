---
name: wcag-review
description: Audit UI code, HTML, templates, or components for Web Content Accessibility Guidelines (WCAG) 2.2 compliance. Use when the user asks to review accessibility, check WCAG compliance, audit a component for a11y issues, or fix accessibility violations. Covers Levels A and AA across all four POUR principles.
tools: Read, Glob, Grep, Bash
---

# WCAG 2.2 Accessibility Review

Audit code for WCAG 2.2 compliance (Levels A and AA). Identify violations, explain impact on users, and provide concrete fixes.

## Scope

By default, target the file or component the user specifies. If none is given, ask. You may also glob for templates, components, or views when a directory is given.

## Workflow

### 1. Collect Context

Read the target file(s). If it's a component library or full page, also check:
- Any associated CSS for color/contrast clues
- Any JS/TS for dynamic focus or ARIA manipulation
- Any i18n files for label text

### 2. Run the Checklist

Work through each POUR principle below. For each criterion, mark it as:
- **Pass** — satisfied
- **Fail** — violated (include the offending line/element and the fix)
- **N/A** — criterion does not apply to this content

Only report **Fails** and items you are **uncertain about** in the output. Skip clean passes unless the user asks for a full audit.

---

## WCAG 2.2 Criteria Reference (Levels A & AA)

### PERCEIVABLE

#### 1.1 Text Alternatives
- **1.1.1 Non-text Content (A)** — Every `<img>`, `<input type="image">`, icon, and SVG must have a meaningful `alt` (or `aria-label`). Decorative images use `alt=""`. Linked images describe the destination.

#### 1.2 Time-Based Media
- **1.2.1 Audio-only / Video-only Prerecorded (A)** — Provide transcript for audio-only; transcript or audio description for video-only.
- **1.2.2 Captions Prerecorded (A)** — Synchronized captions for all non-live video with audio.
- **1.2.4 Captions Live (AA)** — Live video with audio must have real-time captions.
- **1.2.5 Audio Description Prerecorded (AA)** — Audio description for non-live video when visual content conveys meaning not in the audio track.

#### 1.3 Adaptable
- **1.3.1 Info and Relationships (A)** — Use semantic HTML: headings (`h1`–`h6`), lists (`ul`/`ol`/`dl`), `<table>` with `<th scope>`, `<label for>` or `aria-labelledby`, landmarks (`<nav>`, `<main>`, `<header>`, etc.).
- **1.3.2 Meaningful Sequence (A)** — DOM order matches reading/logical order. Visual reordering via CSS/grid must not scramble the reading order.
- **1.3.3 Sensory Characteristics (A)** — Instructions must not rely solely on shape, size, position, color, or sound ("click the round button").
- **1.3.4 Orientation (AA)** — Do not lock orientation to portrait or landscape unless essential.
- **1.3.5 Identify Input Purpose (AA)** — Inputs collecting personal data (name, email, address, phone, CC) must have the appropriate `autocomplete` attribute (e.g., `autocomplete="email"`).

#### 1.4 Distinguishable
- **1.4.1 Use of Color (A)** — Color must not be the only way to convey information (e.g., required fields, errors, chart segments).
- **1.4.2 Audio Control (A)** — Auto-playing audio >3 s must have a pause/stop/mute control.
- **1.4.3 Contrast Minimum (AA)** — Normal text: 4.5:1. Large text (≥18pt / 14pt bold): 3:1. UI components and focus indicators: 3:1.
- **1.4.4 Resize Text (AA)** — Page must remain readable and functional when browser text is zoomed to 200%.
- **1.4.5 Images of Text (AA)** — Do not use images of text when live text can achieve the same visual effect (logos/logotypes excepted).
- **1.4.10 Reflow (AA)** — No horizontal scrolling at 320 CSS px viewport width (equivalent to 400% zoom on 1280 px). Exemptions: data tables, maps, complex diagrams.
- **1.4.11 Non-text Contrast (AA)** — UI components (inputs, buttons, checkboxes) and informational graphics must have 3:1 contrast against adjacent colors in all states (default, hover, focus, disabled).
- **1.4.12 Text Spacing (AA)** — No content or functionality lost when user overrides: line-height ≥1.5×, letter-spacing ≥0.12em, word-spacing ≥0.16em, paragraph spacing ≥2em.
- **1.4.13 Content on Hover or Focus (AA)** — Tooltip/popover content must: (a) be dismissible without moving focus (Esc), (b) allow pointer to move over the new content, (c) persist until dismissed or trigger loses focus.

---

### OPERABLE

#### 2.1 Keyboard Accessible
- **2.1.1 Keyboard (A)** — Every interactive element must be reachable and operable via keyboard alone. Custom widgets (dropdowns, sliders, date pickers, modals) must follow ARIA Authoring Practices Guide (APG) keyboard patterns.
- **2.1.2 No Keyboard Trap (A)** — Focus must not become stranded. Modals/dialogs must trap focus while open and release it on close; focus must return to the trigger element.
- **2.1.4 Character Key Shortcuts (A)** — Single-character keyboard shortcuts must be remappable, disableable, or only active when the component has focus.

#### 2.2 Enough Time
- **2.2.1 Timing Adjustable (A)** — Time limits must be: turn-off-able, adjustable (extend ≥10×), or warn+extend with ≥20 s response window. Exceptions: real-time events, >20 h sessions.
- **2.2.2 Pause, Stop, Hide (A)** — Auto-moving/scrolling/blinking content lasting >5 s must have a pause/stop/hide control. Auto-updating content must be stoppable.

#### 2.3 Seizures and Physical Reactions
- **2.3.1 Three Flashes or Below Threshold (A)** — No content may flash more than 3 times per second unless the flash area is small or low-contrast.

#### 2.4 Navigable
- **2.4.1 Bypass Blocks (A)** — Provide a skip-to-main-content link (may be visually hidden, must be visible on focus) to bypass repeated navigation.
- **2.4.2 Page Titled (A)** — `<title>` must be descriptive and unique per page/view (for SPAs, update on route change).
- **2.4.3 Focus Order (A)** — Tab order must follow a logical, meaningful sequence. Avoid `tabindex` values >0.
- **2.4.4 Link Purpose In Context (A)** — Link text alone, or link + surrounding context (paragraph, list item, table cell), must make the destination clear. No bare "click here" or "read more".
- **2.4.5 Multiple Ways (AA)** — Provide at least two ways to find any page: e.g., site search + nav menu, or nav + sitemap.
- **2.4.6 Headings and Labels (AA)** — Headings and form labels must be descriptive. Avoid duplicate headings unless they serve distinct sections.
- **2.4.7 Focus Visible (AA)** — Keyboard focus indicator must be visually visible. Never `outline: none` without a replacement.
- **2.4.11 Focus Not Obscured Minimum (AA)** *(new in 2.2)* — A focused component must not be entirely hidden by sticky headers, cookie banners, or other author-created overlays.

#### 2.5 Input Modalities
- **2.5.1 Pointer Gestures (A)** — Multi-point or path-based gestures (pinch, swipe) must have single-pointer alternatives (buttons).
- **2.5.2 Pointer Cancellation (A)** — Activate functionality on the up-event, not the down-event, OR allow abort/reversal. Avoid activating on `mousedown`/`touchstart` for irreversible actions.
- **2.5.3 Label in Name (A)** — The accessible name of a control must contain the visible text label. `aria-label` must include the visible text (not replace it with something different).
- **2.5.4 Motion Actuation (A)** — If functionality responds to device motion (shake, tilt), provide a UI alternative and allow the motion trigger to be disabled.
- **2.5.7 Dragging Movements (AA)** *(new in 2.2)* — Any drag operation must also have a single-pointer alternative (e.g., buttons to reorder list items).
- **2.5.8 Target Size Minimum (AA)** *(new in 2.2)* — Pointer targets must be at least 24×24 CSS px, OR have ≥24 px of non-overlapping spacing around them. Inline text links, native browser UI, and essential-size controls are exempt.

---

### UNDERSTANDABLE

#### 3.1 Readable
- **3.1.1 Language of Page (A)** — `<html lang="en">` (or appropriate BCP 47 code) must be set.
- **3.1.2 Language of Parts (AA)** — Inline content in a different language must have `lang` on the containing element.

#### 3.2 Predictable
- **3.2.1 On Focus (A)** — Focusing an element must not trigger a context change (navigation, form submission, dialog open).
- **3.2.2 On Input (A)** — Changing a form control value must not auto-submit or navigate without warning.
- **3.2.3 Consistent Navigation (AA)** — Repeated navigation blocks must appear in the same relative order across pages.
- **3.2.4 Consistent Identification (AA)** — Components with the same function must be identified consistently (same label, same icon, same alt text).
- **3.2.6 Consistent Help (A)** *(new in 2.2)* — Help mechanisms (chat widget, phone number, FAQ link) must appear in the same location on every page where they are present.

#### 3.3 Input Assistance
- **3.3.1 Error Identification (A)** — Invalid fields must be identified in text (not color alone), with a description of the error.
- **3.3.2 Labels or Instructions (A)** — Provide labels for all inputs; include format instructions (e.g., "MM/DD/YYYY") where needed.
- **3.3.3 Error Suggestion (AA)** — Where possible, suggest a fix for the error (not just "invalid input").
- **3.3.4 Error Prevention (AA)** — For legal, financial, or data-deletion actions: make submissions reversible, provide a review step, or require explicit confirmation.
- **3.3.7 Redundant Entry (A)** *(new in 2.2)* — Auto-populate or offer to select previously entered data within the same session (exemptions: security, essential re-entry, data that changes).
- **3.3.8 Accessible Authentication Minimum (AA)** *(new in 2.2)* — Login must not require solving a cognitive puzzle (CAPTCHA) unless: an alternative method exists, assistance is provided, or the test uses object/image recognition of user-provided content.

---

### ROBUST

#### 4.1 Compatible
- **4.1.2 Name, Role, Value (A)** — Every UI component must expose: a name (label), a role (via semantic HTML or `role`), and state/value (via ARIA attributes or native HTML). Custom widgets must fully implement ARIA patterns.
- **4.1.3 Status Messages (AA)** — Dynamically injected status messages (success toasts, loading states, error alerts) must be exposed to assistive tech without receiving focus, via `role="status"`, `role="alert"`, or `aria-live` regions.

---

## Output Format

Group findings by POUR principle. For each violation use this structure:

```
### [Criterion number] [Criterion name] (Level [A/AA])

**Issue:** [What is wrong and where — include file:line if possible]
**Impact:** [Which users are affected and how]
**Fix:** [Concrete code change or technique]
```

After listing violations, provide a **Summary table**:

| Level | Pass | Fail | N/A |
|-------|------|------|-----|
| A     | X    | X    | X   |
| AA    | X    | X    | X   |

End with a **Priority order** — list the Level A failures first (they block conformance), then Level AA, then any quick wins.

## Notes

- WCAG 2.2 retired criterion 4.1.1 (Parsing) — do not flag HTML validation errors under it.
- Contrast ratios must be verified against actual rendered colors. If CSS variables or theme tokens are used and resolved values are not visible in the code, flag for manual verification with a tool (axe DevTools, Colour Contrast Analyser).
- ARIA must not be used to paper over missing semantics — fix the HTML first, then add ARIA only where HTML falls short.
- For React/Vue/Angular components, check that dynamic content updates (route changes, async loads, modal open/close) correctly manage focus and live regions.
