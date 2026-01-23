# Joan Design System (Glassy Motion)

Guidelines for the current visual language: soft glassy surfaces, ambient glows, motion-forward interactions, and mobile-first responsiveness (with sticky bottom nav).

## Visual Language
- **Surfaces**: Prefer borderless, blurred gradients over hard cards. Use rounded corners (`rounded-3xl`) with subtle ambient glows.
- **Glows/Accents**: Use faint color blooms behind hero elements (e.g., `bg-blue-500/10 blur-3xl`), and lighter accents for secondary areas.
- **Depth**: Rely on shadow + gradient layering; keep borders minimal (`border-white/40` or `border-gray-200/60` only where necessary).
- **Spacing**: Generous section gaps (`gap-6`/`gap-8`) and breathing room (`p-6`). Avoid dense card stacks.

## Color & Tone
- Continue semantic colors, but apply them to translucent layers:
  - **Primary surfaces**: `bg-gradient-to-br from-white/90 via-slate-50 to-white` (light) or `dark:from-gray-900 dark:via-slate-900 dark:to-gray-950`.
  - **Highlights**: `bg-blue-500/90` for active states, with glow (`box-shadow: 0 0 20px rgba(59,130,246,0.35)`).
  - **Ambient glows**: Soft blobs behind heroes, never overpowering text contrast.

## Typography
- Keep existing scale but allow larger hero numerals (timers) to breathe.
- Timer numerals: bold mono, large (`text-4xl` to `text-6xl` depending on context).
- Secondary text stays muted (`text-gray-500/600`).

## Surfaces & Containers
- **Hero/Primary container**:
```tsx
"relative overflow-hidden rounded-3xl bg-gradient-to-br from-white/90 via-slate-50 to-white dark:from-gray-900 dark:via-slate-900 dark:to-gray-950 shadow-xl"
```
- **Ambient glows**:
```tsx
"absolute -left-10 -top-10 h-32 w-32 rounded-full bg-blue-500/10 blur-3xl"
```
- Avoid heavy borders on primary focus areas; light borders only on dense utilities.

## Buttons
- **Primary**:
```tsx
"inline-flex items-center justify-center rounded-md text-sm font-medium bg-green-600 text-white hover:bg-green-700 h-10 px-4 py-2 transition-transform duration-200 hover:scale-105 active:scale-95"
```
- **Outline/Secondary**:
```tsx
"inline-flex items-center justify-center rounded-md text-sm font-medium border border-gray-200/70 bg-white/80 hover:bg-white h-10 px-4 py-2"
```
- **Icon/Ghost**:
```tsx
"inline-flex items-center justify-center rounded-md text-sm font-medium border border-gray-200/60 bg-white/70 dark:bg-gray-800/80 hover:bg-gray-50 dark:hover:bg-gray-700 h-10 w-10"
```

## Toggle / Timer Mode Selector (Updated)
- Use measured sliding indicator with glow; icon-first, text hidden on mobile for tight fit:
```tsx
<div className="relative inline-flex w-full items-center gap-1 rounded-xl bg-gray-100/80 dark:bg-gray-800/80 p-1.5 backdrop-blur-sm border border-gray-200/70 overflow-hidden">
  <div className="absolute top-1.5 bottom-1.5 rounded-lg bg-blue-500/90 shadow-lg transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)]" style={{ left, width }} />
  {/* Tabs: icons always, labels shown on sm+; custom tab icon-only with sr-only label */}
</div>
```

## Forms
- Inputs remain simple but lighter on borders:
```tsx
"flex h-10 w-full rounded-md border border-gray-200/60 bg-white/80 px-3 py-2 text-sm placeholder:text-gray-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-900/70 focus-visible:ring-offset-2"
```
- Search with icon: `relative` container + left icon; ensure padding so icons/settings don’t overlap inputs.

## Layout
- **Main layout**: `grid gap-8 md:grid-cols-3`; primary content `md:col-span-2`; sidebar `md:sticky md:top-4`.
- **Mobile**: stack sections with `pb-6`; allocate bottom padding to account for sticky bottom nav.
- **Hero sections**: avoid rigid cards; use gradients and shadow for separation.

## Navigation
- **Mobile**: sticky bottom nav with glass background (`bg-white/90 dark:bg-gray-900/90 backdrop-blur`), active tab glow, and sufficient bottom padding on pages.
- **Desktop**: minimal sidebar without heavy borders; rely on subtle background shifts and shadow; content remains centered.

## Animation
- **Toggle indicator**: `transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)]` + glow.
- **Timer running**: add pulsing halo (`bg-primary/15 blur-3xl animate-pulse`) and gentle `scale-105`.
- **Progress arcs**: `transition-all duration-1000 ease-linear`.
- **Buttons**: `hover:scale-105 active:scale-95` for primary/hero actions; keep utility buttons subtle.

## Pomodoro / Focus Patterns
- Glassy primary container with ambient glows; no hard borders.
- Timer face scales slightly when active; halo animation allowed.
- Mode toggle uses measured sliding indicator; custom tab icon-only.
- Session history mirrors the glass surface; sticky on desktop, stacked below timers on mobile.

## Accessibility
- Preserve focus-visible rings on all interactive elements.
- Keep sr-only text for icon-only controls (e.g., custom timer tab).
- Maintain sufficient contrast even with translucent surfaces.

## Responsive Behaviors
- Bottom nav stays above content; add `pb-20` (or `pb-24` in layout) on mobile.
- Task search and utility icons stack to avoid overlap; place utility icons above the search on small screens.
- Toggles/controls compress horizontally via icon-first layout; text appears on `sm+`.

## Kanban / Task Management Patterns

### Glassy Task Cards
Cards use translucent backgrounds with backdrop blur for the glassy effect:
```tsx
"bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm p-4 rounded-xl shadow-sm border border-white/30 dark:border-gray-700/50 transition-all duration-200 hover:shadow-lg hover:scale-[1.02]"
```

### Kanban Columns
Columns use softer glassy containers:
```tsx
"bg-white/50 dark:bg-gray-800/50 backdrop-blur-sm rounded-2xl p-4 border border-white/30 dark:border-gray-700/50"
```

### Mobile Kanban Carousel
On mobile (<768px), Kanban columns display as a swipeable carousel:
- Use CSS scroll-snap for native-feeling swipe: `snap-x snap-mandatory`
- Each column: `w-full shrink-0 snap-center`
- Track active column with IntersectionObserver
- Show dot indicators below carousel:
```tsx
// Active dot
"h-2 w-6 rounded-full bg-blue-500 dark:bg-blue-400 transition-all duration-300"
// Inactive dot
"h-2 w-2 rounded-full bg-gray-300 dark:bg-gray-600"
```

### Drag & Drop Visual Feedback
- Dragged item: `opacity-40` on original, overlay shows `shadow-2xl rotate-[2deg] scale-105 border-2 border-blue-400`
- Drop indicator: `h-0.5 bg-blue-500 rounded-full` with pulsing dots at edges
- Column hover state: `ring-2 ring-blue-400/50 bg-blue-50/30 dark:bg-blue-900/20`

### Filter Bar - Minimal + Advanced Pattern
Desktop shows all filters inline. Mobile uses progressive disclosure:
```tsx
// Mobile: Always visible
<SearchInput /> <StatusDropdown />
// Mobile: Behind "More Filters" button
<PriorityDropdown /> <SortDropdown />
```
Expand animation: `max-h-0 opacity-0` → `max-h-40 opacity-100` with `transition-all duration-300`

### Glassy Dropdowns (Headless UI Listbox)
```tsx
// Trigger button
"rounded-xl bg-white/60 dark:bg-gray-800/60 backdrop-blur-sm py-2.5 pl-4 pr-10 border border-white/30 dark:border-gray-700/50 hover:bg-white/80"

// Options panel
"rounded-xl bg-white/90 dark:bg-gray-800/90 backdrop-blur-md shadow-xl border border-white/30 dark:border-gray-700/50"

// Option hover
"bg-blue-500/10 dark:bg-blue-500/20 text-blue-700 dark:text-blue-300"
```

### View Toggle with Sliding Indicator
```tsx
// Container
"relative inline-flex items-center gap-1 rounded-xl bg-white/60 dark:bg-gray-800/60 backdrop-blur-sm p-1.5 border border-white/30 dark:border-gray-700/50"

// Sliding pill indicator
"absolute top-1.5 bottom-1.5 rounded-lg bg-blue-500/90 shadow-lg transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)]"
// With glow: style={{ boxShadow: '0 0 20px rgba(59,130,246,0.35)' }}

// Active tab text
"text-white"
// Inactive tab text
"text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100"
```

### Empty States
```tsx
// Container
"flex flex-col items-center justify-center py-16 px-4"

// Icon container
"w-20 h-20 rounded-2xl bg-white/60 dark:bg-gray-800/60 backdrop-blur-sm flex items-center justify-center mb-6 border border-white/30 dark:border-gray-700/50"
```

### Task Metadata Display
- Priority: Emoji indicators `🟢 low` `🟡 medium` `🔴 high`
- Difficulty/Effort: Animal emojis by size `🐭 small` → `🐋 epic`
- Assignee: Small user icon + truncated name
- Subtask count: Inline text `(3/5)`

### Stats Bar
Inline stats with bullet separators:
```tsx
"flex flex-wrap items-center gap-2 sm:gap-4 text-sm text-gray-500 dark:text-gray-400"
// Numbers highlighted
"font-medium text-gray-700 dark:text-gray-300"
```

## Usage Notes
1. Favor gradients + blur over borders for primary areas; borders are secondary.
2. Add ambient glows sparingly to guide focus, not decorate everything.
3. Maintain motion that feels intentional (ease-out bounce on toggles, pulse on running states).
4. Update this doc when introducing new patterns—do not add ad-hoc styles in code.
5. For mobile Kanban, always provide swipe carousel with dot indicators.
6. Use progressive disclosure (Minimal + Advanced) pattern for complex filter UIs on mobile.
7. Task cards should have subtle hover animations (`scale-[1.02]`) to indicate interactivity.
