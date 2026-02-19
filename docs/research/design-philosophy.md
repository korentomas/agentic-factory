# LailaTov Design System: Philosophy, Research & Tokens

> A design system for an autonomous code factory that works while you sleep.
> Warm, gentle, Japanese-inspired minimalism. Not cyberpunk. Not cold tech.
> Think: a cozy workshop with a night owl mascot, humming quietly through the night.

---

## Table of Contents

1. [Japanese Aesthetic Principles](#1-japanese-aesthetic-principles)
2. [Typography System](#2-typography-system)
3. [Color Palette](#3-color-palette)
4. [Bento Box Layout System](#4-bento-box-layout-system)
5. [Design Tokens](#5-design-tokens)
6. [Implementation Guide (Next.js + Tailwind)](#6-implementation-guide)

---

## 1. Japanese Aesthetic Principles

These four principles form the philosophical foundation of every visual decision in the
LailaTov design system. Each one maps directly to concrete CSS and layout rules.

### 1.1 Ma (間) — The Art of Negative Space

Ma is not "empty space" -- it is *meaningful* space. It is the pause between musical notes
that gives the melody shape. In web design, Ma means every element earns its breathing room.

**CSS Translation:**

- Generous padding inside containers (minimum `2rem`, prefer `3rem--4rem` for hero sections)
- Large gaps between grid items (`1.5rem--2rem` minimum)
- Content never touches the edges of its container
- Sections separated by substantial vertical rhythm (`6rem--8rem` between major sections)
- Line height generous enough that text breathes (1.5--1.7 for body text)

**Anti-patterns to avoid:**
- Cramming elements together to "fill" space
- Sidebar + content + sidebar layouts that leave no room to breathe
- Pop-ups, banners, and notification bars that compress the Ma

**Reference:** Muji.com is the canonical example -- monochromatic, product-forward, with
whitespace doing more work than any decoration could.

```css
/* Ma spacing scale */
.section { padding-block: clamp(4rem, 8vw, 8rem); }
.container { padding-inline: clamp(1.5rem, 5vw, 4rem); }
.card { padding: clamp(1.5rem, 3vw, 2.5rem); }
```

### 1.2 Kanso (簡素) — Radical Simplicity

Kanso means stripping away everything that is not essential. Not minimalism as an aesthetic
trend, but minimalism as a *discipline*. If an element does not serve the user's immediate
need, it does not belong on the page.

**CSS Translation:**

- Maximum of 2--3 font weights per page (regular + medium, occasionally semibold)
- One accent color, used sparingly
- No decorative borders, gradients, or ornamental patterns
- UI chrome (navbars, footers, sidebars) should be visually quiet
- Icons only when they communicate faster than words
- Buttons: one primary style, one secondary, one ghost. That is the entire system.

**Component rules:**
- Cards have no border. Use subtle background color difference or a whisper of shadow.
- Navigation uses text, not icons with tooltips.
- Forms use labels, not placeholders-as-labels.

### 1.3 Wabi-Sabi (侘寂) — Beauty in Imperfection

Wabi-sabi celebrates the handmade, the organic, the slightly imperfect. In a digital
context, this means avoiding the sterile perfection of corporate design systems.

**CSS Translation:**

- Border radius should be soft but not perfectly circular (`0.5rem--0.75rem`, never `9999px`)
- Shadows should feel like natural light, not hard-edged CSS box-shadows
- Allow slight asymmetry in layouts (a 7/5 grid split instead of 6/6)
- Textures: very subtle paper or linen grain (at 3--5% opacity) as page background
- Illustrations should feel hand-drawn, not vector-perfect
- Micro-animations should have slight easing overshoot, like physical objects settling

```css
/* Wabi-sabi shadows -- soft, diffused, warm-tinted */
--shadow-sm: 0 1px 3px rgba(120, 100, 80, 0.06), 0 1px 2px rgba(120, 100, 80, 0.04);
--shadow-md: 0 4px 12px rgba(120, 100, 80, 0.08), 0 2px 4px rgba(120, 100, 80, 0.04);
--shadow-lg: 0 12px 32px rgba(120, 100, 80, 0.10), 0 4px 8px rgba(120, 100, 80, 0.04);

/* Wabi-sabi border radius -- soft, not bubbly */
--radius-sm: 0.375rem;  /* 6px */
--radius-md: 0.5rem;    /* 8px */
--radius-lg: 0.75rem;   /* 12px */
--radius-xl: 1rem;      /* 16px -- maximum, used for cards */
```

### 1.4 Shibui (渋い) — Subtle, Unobtrusive Beauty

Shibui is the quality of being beautiful without being obvious about it. The design should
feel inevitable, not designed. Users should not notice the design -- they should simply feel
comfortable.

**CSS Translation:**

- Transitions so subtle you barely notice them (200--300ms, ease-out)
- Hover states change opacity or translate slightly, not color explosively
- Typography hierarchy through size and weight, not color or decoration
- The most important element on any page should be the *content*, never the UI
- No element should scream for attention

```css
/* Shibui transitions */
--transition-fast: 150ms ease-out;
--transition-base: 250ms ease-out;
--transition-slow: 400ms ease-out;
--transition-settle: 500ms cubic-bezier(0.22, 1, 0.36, 1);
```

---

## 2. Typography System

Based on Butterick's *Practical Typography* rules, adapted for web and the LailaTov brand.

### 2.1 Core Rules (from Practical Typography)

| Rule | Specification |
|---|---|
| Body font size (web) | 16--20px (Butterick recommends 15--25px; 18px is the sweet spot) |
| Line spacing | 120--145% of font size (CSS: `line-height: 1.5` to `1.7`) |
| Line length | 45--90 characters per line (ideal: 65--75) |
| Font weights | Maximum 2--3 per page |
| Paragraph spacing | Either first-line indent OR vertical spacing, never both |
| Kerning | Always enable (`font-kerning: normal`) |
| Letterspacing | Add 5--12% for ALL CAPS or small caps text |

### 2.2 What NOT To Do

From Butterick's "F List" and anti-patterns:

- **Never use Arial, Comic Sans, Trebuchet, Papyrus, Impact** as body or heading text
- **Avoid Times New Roman** -- it signals indifference, not professionalism
- **Do not use system font stacks for body text** -- they are overexposed and often
  optimized for screen rendering at the expense of typographic quality
- **Never combine bold AND italic** on the same text
- **No underlining** except for links
- **Single space after sentences** -- never double
- **Do not use straight quotes** -- always use curly quotes (typographer's quotes)
- **Do not let lines run the full browser width** -- constrain with `max-width`

### 2.3 Font Recommendations for LailaTov

The following font stack balances warmth, readability, and the gentle aesthetic of the brand.

#### Primary Recommendation: Geist + Instrument Serif

| Role | Font | Fallback | Why |
|---|---|---|---|
| Body text | **Geist** (Vercel) | `system-ui, sans-serif` | Slightly rounder than Inter, friendlier apertures, modern but warm |
| Headings (display) | **Instrument Serif** | `Georgia, serif` | Adds editorial warmth, contrast with sans-serif body |
| Code / Monospace | **Geist Mono** | `ui-monospace, monospace` | Designed to pair with Geist, consistent x-height |
| Japanese text | **Noto Serif JP** | `serif` | Best coverage for Japanese characters, elegant serif |

#### Alternative Recommendation: Inter + Charter

| Role | Font | Why |
|---|---|---|
| Body text | **Inter** | Industry standard readability, excellent at small sizes |
| Headings | **Charter** (Butterick's recommendation) | Warm serif, works beautifully at display sizes |
| Code | **JetBrains Mono** | Excellent ligatures for code display |

#### Typography Scale

Based on a 1.25 ratio (Major Third) starting from 18px body:

```css
:root {
  /* Type scale -- Major Third (1.25) from 18px base */
  --text-xs:   0.75rem;   /* 12px -- captions, labels */
  --text-sm:   0.875rem;  /* 14px -- secondary text, metadata */
  --text-base: 1.125rem;  /* 18px -- body text */
  --text-lg:   1.25rem;   /* 20px -- lead paragraphs */
  --text-xl:   1.5rem;    /* 24px -- h4 */
  --text-2xl:  1.875rem;  /* 30px -- h3 */
  --text-3xl:  2.25rem;   /* 36px -- h2 */
  --text-4xl:  3rem;      /* 48px -- h1 */
  --text-5xl:  3.75rem;   /* 60px -- hero display */

  /* Line heights */
  --leading-tight:  1.25;  /* headings */
  --leading-snug:   1.375; /* subheadings */
  --leading-normal: 1.6;   /* body text -- within Butterick's 120-145% range */
  --leading-loose:  1.75;  /* body text with more breathing room */

  /* Line length constraint */
  --prose-width: 68ch;     /* ~65-75 characters -- the sweet spot */

  /* Font weights */
  --font-normal:   400;
  --font-medium:   500;
  --font-semibold: 600;

  /* Tracking (letterspacing) */
  --tracking-tight:  -0.02em;  /* large headings */
  --tracking-normal:  0;       /* body text */
  --tracking-wide:    0.05em;  /* all-caps labels, small caps */
  --tracking-wider:   0.1em;   /* very small all-caps text */
}
```

### 2.4 Implementation in Next.js + Tailwind

```tsx
// app/layout.tsx
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import localFont from 'next/font/local';

// Or via next/font/google:
// import { Instrument_Serif } from 'next/font/google';

const instrumentSerif = localFont({
  src: './fonts/InstrumentSerif-Regular.woff2',
  variable: '--font-serif',
  display: 'swap',
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${GeistSans.variable} ${GeistMono.variable} ${instrumentSerif.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
```

```css
/* globals.css -- Tailwind v4 style */
@theme {
  --font-sans: var(--font-geist-sans), system-ui, sans-serif;
  --font-serif: var(--font-serif), Georgia, serif;
  --font-mono: var(--font-geist-mono), ui-monospace, monospace;
}

/* Prose defaults */
.prose {
  font-family: var(--font-sans);
  font-size: var(--text-base);
  line-height: var(--leading-normal);
  max-width: var(--prose-width);
  font-kerning: normal;
  font-feature-settings: "kern" 1, "liga" 1;
}

.prose h1, .prose h2, .prose h3 {
  font-family: var(--font-serif);
  line-height: var(--leading-tight);
  letter-spacing: var(--tracking-tight);
}
```

---

## 3. Color Palette

### 3.1 Philosophy

The LailaTov palette draws from traditional Japanese colors (和色, wairo) -- specifically the
warm, muted tones found in nature, ceramics, and textiles. These colors have been refined
over centuries and carry an inherent harmony that synthetic palettes rarely achieve.

The palette should feel like:
- A warm room with paper lanterns and wooden shelves
- The sky just after sunset, deep blue fading to warm amber
- An owl's feathers -- soft browns, warm grays, amber eyes

It should NOT feel like:
- A Silicon Valley SaaS dashboard
- A dark-mode-first developer tool
- A neon-accented gaming interface

### 3.2 Traditional Japanese Color References

These are the source colors from the 和色 tradition, with verified hex values:

| Japanese Name | Romaji | English | Hex | Use Case |
|---|---|---|---|---|
| 生成り色 | Kinari-iro | Raw silk / unbleached | `#F7F6F0` | Light mode background |
| 胡粉 | Gofun | Shell white | `#FFFFFB` | Light mode surface (cards) |
| 鳥の子 | Torinoko | Eggshell | `#ECE2D0` | Light mode secondary surface |
| 白練 | Shironeri | White silk | `#F3F3F2` | Light mode alternate background |
| 藍色 | Ai-iro | Indigo | `#264348` | Dark mode background, primary accent |
| 紺色 | Kon-iro | Deep navy | `#223A5E` | Dark mode surface |
| 朱色 | Shu-iro | Vermillion | `#EB6101` | Warm accent (warnings, CTA) |
| 若草色 | Wakakusa-iro | Young grass | `#8DB255` | Success, positive states (muted) |
| 薄墨 | Usuzumi | Pale ink | `#A3A3A2` | Muted text, borders |
| 墨 | Sumi | Ink black | `#27292B` | Dark mode text on light, headings |
| 鼠色 | Nezumi-iro | Mouse gray | `#7D7D7D` | Secondary text |
| 桜色 | Sakura-iro | Cherry blossom | `#FEDFE1` | Subtle highlight, decorative |
| 狐色 | Kitsune-iro | Fox brown | `#985629` | Warm accent, links on dark |
| 利休茶 | Rikyu-cha | Tea master's brown | `#826B58` | Warm neutral accent |
| 水色 | Mizu-iro | Water blue | `#86ABA5` | Cool accent, info states |

### 3.3 Derived Design Palette

The following CSS custom properties derive from the traditional colors above, structured for
both light and dark mode. This is the palette developers should use directly.

```css
:root {
  /* ========================================
     LAILATOV COLOR SYSTEM
     Inspired by 和色 (traditional Japanese colors)
     ======================================== */

  /* --- Light Mode (default) --- */

  /* Backgrounds */
  --color-bg-primary:     #F7F6F0;  /* kinari -- warm off-white */
  --color-bg-secondary:   #F3F3F2;  /* shironeri -- cool silk */
  --color-bg-tertiary:    #ECE2D0;  /* torinoko -- eggshell warmth */
  --color-bg-surface:     #FFFFFB;  /* gofun -- pure surface white */
  --color-bg-elevated:    #FFFFFF;  /* true white for elevated cards */

  /* Text */
  --color-text-primary:   #27292B;  /* sumi -- rich near-black */
  --color-text-secondary: #5C5C5B;  /* darkened nezumi */
  --color-text-tertiary:  #7D7D7D;  /* nezumi -- muted */
  --color-text-inverse:   #F7F6F0;  /* kinari on dark backgrounds */

  /* Borders & Dividers */
  --color-border-subtle:  #E8E5DF;  /* warm gray, barely visible */
  --color-border-default: #D4CFC6;  /* torinoko-derived */
  --color-border-strong:  #A3A3A2;  /* usuzumi */

  /* Accent -- Indigo (ai-iro) as primary brand color */
  --color-accent-primary:     #264348;  /* ai-iro -- deep indigo-teal */
  --color-accent-primary-hover: #1E363A; /* darkened ai-iro */
  --color-accent-primary-text: #FFFFFB; /* gofun on accent */

  /* Accent -- Warm (shu-iro / vermillion for CTAs) */
  --color-accent-warm:        #D4570A;  /* muted shu-iro */
  --color-accent-warm-hover:  #EB6101;  /* full shu-iro */
  --color-accent-warm-subtle: #FDF0E6;  /* shu-iro at 8% */

  /* Semantic */
  --color-success:        #6B8F3C;  /* muted wakakusa */
  --color-success-subtle: #F0F5E8;  /* wakakusa at 8% */
  --color-warning:        #D4570A;  /* shu-iro */
  --color-warning-subtle: #FDF0E6;  /* shu-iro at 8% */
  --color-error:          #C43E2A;  /* darker vermillion */
  --color-error-subtle:   #FDE8E4;  /* error at 8% */
  --color-info:           #4A8A82;  /* muted mizu-iro */
  --color-info-subtle:    #EBF3F2;  /* mizu at 8% */

  /* Interactive */
  --color-link:           #264348;  /* ai-iro */
  --color-link-hover:     #1E363A;  /* darker ai-iro */
  --color-link-visited:   #5A4A6A;  /* muted purple */
  --color-focus-ring:     rgba(38, 67, 72, 0.4);  /* ai-iro at 40% */

  /* Decorative */
  --color-sakura:         #FEDFE1;  /* cherry blossom pink */
  --color-kitsune:        #985629;  /* fox brown */
  --color-rikyu:          #826B58;  /* tea brown */
}

/* --- Dark Mode --- */
[data-theme="dark"],
.dark {
  /* Backgrounds -- built from ai-iro and kon-iro */
  --color-bg-primary:     #1A2A2E;  /* deepened ai-iro */
  --color-bg-secondary:   #1F3236;  /* slightly lighter */
  --color-bg-tertiary:    #253D42;  /* mid ai-iro */
  --color-bg-surface:     #223A3E;  /* card surface */
  --color-bg-elevated:    #2A454A;  /* elevated cards */

  /* Text */
  --color-text-primary:   #ECE2D0;  /* torinoko -- warm light */
  --color-text-secondary: #B8AFA2;  /* muted torinoko */
  --color-text-tertiary:  #7A8A8D;  /* muted teal-gray */
  --color-text-inverse:   #27292B;  /* sumi */

  /* Borders */
  --color-border-subtle:  #2E4A4F;  /* dark teal */
  --color-border-default: #3A5A60;  /* medium teal */
  --color-border-strong:  #5A7A80;  /* visible teal */

  /* Accents shift warmer in dark mode */
  --color-accent-primary:      #5AADA3; /* brightened mizu-iro */
  --color-accent-primary-hover: #6BBDB3;
  --color-accent-primary-text: #1A2A2E;

  --color-accent-warm:         #EB6101; /* shu-iro pops in dark */
  --color-accent-warm-hover:   #F57A2A;
  --color-accent-warm-subtle:  rgba(235, 97, 1, 0.12);

  /* Semantic (brighter for dark backgrounds) */
  --color-success:        #8DB255;  /* full wakakusa */
  --color-success-subtle: rgba(141, 178, 85, 0.12);
  --color-warning:        #EB6101;  /* shu-iro */
  --color-warning-subtle: rgba(235, 97, 1, 0.12);
  --color-error:          #E85A48;  /* brightened error */
  --color-error-subtle:   rgba(232, 90, 72, 0.12);
  --color-info:           #86ABA5;  /* mizu-iro */
  --color-info-subtle:    rgba(134, 171, 165, 0.12);

  /* Interactive */
  --color-link:           #5AADA3;
  --color-link-hover:     #6BBDB3;
  --color-focus-ring:     rgba(90, 173, 163, 0.4);

  /* Decorative */
  --color-sakura:         #4A3A3B;  /* muted sakura for dark */
  --color-kitsune:        #C47A4A;  /* brightened fox */
  --color-rikyu:          #A08A72;  /* brightened tea */
}

/* --- Dark mode via system preference --- */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    /* Same as [data-theme="dark"] above */
    --color-bg-primary:     #1A2A2E;
    --color-bg-secondary:   #1F3236;
    --color-bg-tertiary:    #253D42;
    --color-bg-surface:     #223A3E;
    --color-bg-elevated:    #2A454A;
    --color-text-primary:   #ECE2D0;
    --color-text-secondary: #B8AFA2;
    --color-text-tertiary:  #7A8A8D;
    /* ... (full dark mode values as above) */
  }
}
```

### 3.4 Palette Generation Tools

For extending or tweaking this palette:

- **[Coolors](https://coolors.co/)** -- Best general-purpose palette generator. Lock your
  base colors and generate harmonious companions. Supports export to CSS variables.
- **[NIPPON COLORS](https://nipponcolors.com/)** -- The canonical reference for 250+
  traditional Japanese colors with CMYK, RGB, and HEX values. Essential for this project.
- **[Adobe Color](https://color.adobe.com/)** -- Best for exploring color harmony rules
  (analogous, monochromatic, split-complementary). Free with Adobe account.
- **[和色大辞典 (Wairo Dictionary)](https://www.colordic.org/w)** -- Japanese-language
  reference with hundreds of traditional colors organized by hue family.
- **[Realtime Colors](https://www.realtimecolors.com/)** -- Preview your palette on a
  real website layout instantly. Excellent for testing light/dark modes.

---

## 4. Bento Box Layout System

### 4.1 Philosophy

The bento box (弁当) is a Japanese lunchbox with compartments of different sizes, each
holding a carefully prepared item. The beauty is in the *composition* -- the variety of
sizes, the careful arrangement, the way each compartment relates to its neighbors.

In web design, the bento grid breaks content into modular cards of varying sizes on a
shared grid. Apple popularized this pattern for product feature pages (iPhone, MacBook).
It works because:

- It creates visual hierarchy without relying on text size alone
- Each "compartment" is self-contained and scannable
- The grid structure provides order while size variation provides interest
- It maps naturally to CSS Grid with `span` directives

### 4.2 Grid Proportions

Two systems of harmonious proportion inform our grid:

**Tatami Mat Ratio (1:2)**

Traditional Japanese rooms are measured in tatami mats, each with a 1:2 ratio. Rooms are
laid out in patterns of these mats, creating natural grid rhythms. In our bento grid, the
base cell is a square, and a "tatami" cell spans 2 columns or 2 rows -- maintaining this
1:2 proportion.

**Golden Ratio (1:1.618)**

For overall page layout, use golden ratio proportions:
- Main content area : sidebar = 1.618 : 1 (approximately 62% : 38%)
- Hero card : standard card = roughly 2:1 area
- Feature grid: one 2x2 hero, surrounded by 1x1 and 1x2 supporting cards

### 4.3 CSS Grid Implementation

```css
/* ========================================
   BENTO GRID SYSTEM
   Base: 12-column grid with variable rows
   ======================================== */

.bento-grid {
  --bento-cols: 4;
  --bento-gap: 1.25rem;     /* Ma: breathing room between cells */
  --bento-radius: 0.75rem;  /* Wabi-sabi: soft, not bubbly */
  --bento-padding: 1.5rem;  /* Interior Ma */

  display: grid;
  grid-template-columns: repeat(var(--bento-cols), 1fr);
  grid-auto-rows: minmax(180px, auto);
  gap: var(--bento-gap);
  width: 100%;
}

/* Cell variants */
.bento-cell {
  background: var(--color-bg-surface);
  border-radius: var(--bento-radius);
  padding: var(--bento-padding);
  overflow: hidden;
  position: relative;
}

/* Span modifiers -- tatami-inspired sizes */
.bento-cell--wide     { grid-column: span 2; }                /* 2x1 -- horizontal tatami */
.bento-cell--tall     { grid-row: span 2; }                   /* 1x2 -- vertical tatami */
.bento-cell--hero     { grid-column: span 2; grid-row: span 2; } /* 2x2 -- featured */
.bento-cell--full     { grid-column: 1 / -1; }                /* full width */

/* Responsive breakpoints */
@media (max-width: 1024px) {
  .bento-grid { --bento-cols: 3; }
}

@media (max-width: 768px) {
  .bento-grid { --bento-cols: 2; }
  .bento-cell--hero { grid-column: 1 / -1; } /* hero goes full on tablet */
}

@media (max-width: 480px) {
  .bento-grid {
    --bento-cols: 1;
    --bento-gap: 1rem;
  }
  .bento-cell--wide,
  .bento-cell--tall,
  .bento-cell--hero {
    grid-column: span 1;
    grid-row: span 1;
  }
}
```

### 4.4 Tailwind Implementation

```html
<!-- Bento grid in Tailwind v4 -->
<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 auto-rows-[180px]">

  <!-- Hero cell: 2x2 -->
  <div class="sm:col-span-2 sm:row-span-2 bg-[var(--color-bg-surface)]
              rounded-xl p-6 overflow-hidden">
    <h2 class="font-serif text-3xl">Ship while you sleep</h2>
    <p>Your codebase keeps improving, even at 3am.</p>
  </div>

  <!-- Standard cell: 1x1 -->
  <div class="bg-[var(--color-bg-surface)] rounded-xl p-6">
    <h3 class="font-medium text-lg">Auto-triage</h3>
    <p class="text-sm text-[var(--color-text-secondary)]">
      Issues analyzed and prioritized automatically.
    </p>
  </div>

  <!-- Wide cell: 2x1 (horizontal tatami) -->
  <div class="sm:col-span-2 bg-[var(--color-bg-surface)] rounded-xl p-6">
    <h3 class="font-medium text-lg">Pipeline status</h3>
    <!-- content -->
  </div>

  <!-- Tall cell: 1x2 (vertical tatami) -->
  <div class="sm:row-span-2 bg-[var(--color-bg-surface)] rounded-xl p-6">
    <h3 class="font-medium text-lg">Activity feed</h3>
    <!-- content -->
  </div>

</div>
```

### 4.5 Common Bento Compositions

These are tested arrangements that feel balanced:

```
Layout A: "Feature Spotlight"           Layout B: "Equal Weight"
+-------+-------+---+---+              +---+---+---+---+
|       |       |   |   |              |   |   |       |
| hero  | hero  | 1 | 2 |              | 1 | 2 | wide  |
|       |       |   |   |              |   |   |       |
+-------+-------+---+---+              +---+---+-------+
|  wide         | 3 | 4 |              |       | 5 | 6 |
+-------+-------+---+---+              | wide  +---+---+
                                        |       | 7 | 8 |
                                        +-------+---+---+

Layout C: "Editorial" (golden ratio)
+----------+------+
|          |      |
|   main   | side |
|  (62%)   |(38%) |
|          |      |
+----------+------+
| wide               |
+----+----+----+----+
|    |    |    |    |
+----+----+----+----+
```

---

## 5. Design Tokens

### 5.1 Spacing Scale

Based on an 8px grid, informed by Ma principles. The scale is intentionally generous --
tighter scales feel cramped, which violates Ma.

```css
:root {
  /* Spacing scale -- 8px base with Ma-inspired generosity */
  --space-0:   0;
  --space-px:  1px;
  --space-0.5: 0.125rem;  /*  2px -- hairline */
  --space-1:   0.25rem;   /*  4px -- tight */
  --space-2:   0.5rem;    /*  8px -- base unit */
  --space-3:   0.75rem;   /* 12px */
  --space-4:   1rem;      /* 16px -- component padding */
  --space-5:   1.25rem;   /* 20px */
  --space-6:   1.5rem;    /* 24px -- card padding */
  --space-8:   2rem;      /* 32px -- section gap */
  --space-10:  2.5rem;    /* 40px */
  --space-12:  3rem;      /* 48px -- major section padding */
  --space-16:  4rem;      /* 64px -- section separation */
  --space-20:  5rem;      /* 80px */
  --space-24:  6rem;      /* 96px -- major vertical rhythm */
  --space-32:  8rem;      /* 128px -- hero spacing */

  /* Semantic spacing aliases */
  --space-page-x:     clamp(1.5rem, 5vw, 4rem);    /* horizontal page padding */
  --space-page-y:     clamp(4rem, 8vw, 8rem);       /* vertical section spacing */
  --space-card:       clamp(1.25rem, 3vw, 2rem);    /* card internal padding */
  --space-stack-sm:   0.5rem;                        /* between tight elements */
  --space-stack-md:   1rem;                          /* between paragraphs */
  --space-stack-lg:   2rem;                          /* between content blocks */
  --space-inline-sm:  0.5rem;                        /* between inline elements */
  --space-inline-md:  1rem;
  --space-inline-lg:  2rem;
}
```

### 5.2 Border Radius

Wabi-sabi principle: soft enough to feel friendly, never so round it feels cartoonish.

```css
:root {
  --radius-none: 0;
  --radius-sm:   0.375rem;  /*  6px -- buttons, inputs, badges */
  --radius-md:   0.5rem;    /*  8px -- small cards, dropdowns */
  --radius-lg:   0.75rem;   /* 12px -- cards, modals */
  --radius-xl:   1rem;      /* 16px -- large cards, bento cells */
  --radius-2xl:  1.25rem;   /* 20px -- hero sections, max roundness */
  --radius-full: 9999px;    /* pills, avatars ONLY */
}
```

### 5.3 Shadow System

Shadows should feel like warm, natural light from above-right -- like a desk lamp in a
cozy workshop, not fluorescent office lighting.

```css
:root {
  /* Warm-tinted shadows (brown undertone, not blue-gray) */
  --shadow-xs:  0 1px 2px rgba(120, 100, 80, 0.05);
  --shadow-sm:  0 1px 3px rgba(120, 100, 80, 0.07),
                0 1px 2px rgba(120, 100, 80, 0.04);
  --shadow-md:  0 4px 8px rgba(120, 100, 80, 0.07),
                0 2px 4px rgba(120, 100, 80, 0.04);
  --shadow-lg:  0 8px 24px rgba(120, 100, 80, 0.09),
                0 4px 8px rgba(120, 100, 80, 0.04);
  --shadow-xl:  0 16px 48px rgba(120, 100, 80, 0.10),
                0 8px 16px rgba(120, 100, 80, 0.04);

  /* Glow (for focus states, notifications) */
  --shadow-glow-accent: 0 0 0 3px var(--color-focus-ring);
  --shadow-glow-warm:   0 0 16px rgba(235, 97, 1, 0.15);

  /* Inner shadow (for pressed states, inset inputs) */
  --shadow-inner: inset 0 1px 3px rgba(120, 100, 80, 0.08);
}

/* Dark mode shadows shift darker and cooler */
[data-theme="dark"],
.dark {
  --shadow-xs:  0 1px 2px rgba(0, 0, 0, 0.2);
  --shadow-sm:  0 1px 3px rgba(0, 0, 0, 0.25),
                0 1px 2px rgba(0, 0, 0, 0.15);
  --shadow-md:  0 4px 8px rgba(0, 0, 0, 0.25),
                0 2px 4px rgba(0, 0, 0, 0.15);
  --shadow-lg:  0 8px 24px rgba(0, 0, 0, 0.3),
                0 4px 8px rgba(0, 0, 0, 0.15);
  --shadow-xl:  0 16px 48px rgba(0, 0, 0, 0.35),
                0 8px 16px rgba(0, 0, 0, 0.15);
}
```

### 5.4 Animation Principles

Shibui demands that animation is felt, not seen. Every motion should have a purpose.
If removing the animation would not reduce understanding, the animation should not exist.

```css
:root {
  /* Duration scale */
  --duration-instant: 100ms;  /* toggles, micro-interactions */
  --duration-fast:    150ms;  /* hover states, button press */
  --duration-base:    250ms;  /* most transitions */
  --duration-slow:    400ms;  /* modals, overlays appearing */
  --duration-slower:  600ms;  /* page transitions, large movements */

  /* Easing curves */
  --ease-out:     cubic-bezier(0.22, 1, 0.36, 1);    /* elements arriving */
  --ease-in:      cubic-bezier(0.55, 0, 1, 0.45);    /* elements leaving */
  --ease-in-out:  cubic-bezier(0.45, 0, 0.55, 1);    /* looping, back-and-forth */
  --ease-settle:  cubic-bezier(0.22, 1, 0.36, 1);    /* slight overshoot, then rest */
  --ease-spring:  cubic-bezier(0.34, 1.56, 0.64, 1); /* playful bounce (use sparingly) */

  /* Composite transitions */
  --transition-colors:   color var(--duration-fast) var(--ease-out),
                         background-color var(--duration-fast) var(--ease-out),
                         border-color var(--duration-fast) var(--ease-out);
  --transition-opacity:  opacity var(--duration-base) var(--ease-out);
  --transition-transform: transform var(--duration-base) var(--ease-settle);
  --transition-shadow:   box-shadow var(--duration-base) var(--ease-out);
  --transition-all:      all var(--duration-base) var(--ease-out);
}
```

**Animation guidelines:**

| Context | Behavior | Duration | Easing |
|---|---|---|---|
| Button hover | Subtle background shift | 150ms | ease-out |
| Card hover | Lift 2px + shadow increase | 250ms | ease-settle |
| Modal open | Fade in + scale from 0.97 | 300ms | ease-out |
| Modal close | Fade out + scale to 0.97 | 200ms | ease-in |
| Page transition | Crossfade | 400ms | ease-in-out |
| Skeleton loading | Pulse opacity 0.4 to 0.7 | 1.5s | ease-in-out, infinite |
| Success check | Draw SVG stroke | 400ms | ease-settle |
| Toast appear | Slide up + fade in | 300ms | ease-settle |
| Toast dismiss | Slide down + fade out | 200ms | ease-in |

**What NOT to animate:**
- Layout shifts (no animating width/height of content containers)
- Color changes on text (jarring and accessibility-hostile)
- Anything on page load that delays content visibility
- Parallax scrolling (violates Kanso -- it is decoration, not function)
- Animated gradients or particle effects (violates Shibui -- too attention-seeking)

---

## 6. Implementation Guide

### 6.1 Complete Tailwind v4 Theme Extension

```css
/* globals.css */
@import "tailwindcss";

@theme {
  /* Colors */
  --color-kinari: #F7F6F0;
  --color-gofun: #FFFFFB;
  --color-torinoko: #ECE2D0;
  --color-shironeri: #F3F3F2;
  --color-ai: #264348;
  --color-kon: #223A5E;
  --color-shu: #EB6101;
  --color-wakakusa: #8DB255;
  --color-usuzumi: #A3A3A2;
  --color-sumi: #27292B;
  --color-nezumi: #7D7D7D;
  --color-sakura: #FEDFE1;
  --color-kitsune: #985629;
  --color-rikyu: #826B58;
  --color-mizu: #86ABA5;

  /* Fonts */
  --font-sans: var(--font-geist-sans), system-ui, -apple-system, sans-serif;
  --font-serif: var(--font-instrument-serif), Georgia, "Times New Roman", serif;
  --font-mono: var(--font-geist-mono), ui-monospace, "Cascadia Code", monospace;

  /* Spacing */
  --spacing-page-x: clamp(1.5rem, 5vw, 4rem);
  --spacing-page-y: clamp(4rem, 8vw, 8rem);
  --spacing-card: clamp(1.25rem, 3vw, 2rem);

  /* Border radius */
  --radius-bento: 0.75rem;
  --radius-card: 1rem;

  /* Shadows */
  --shadow-bento: 0 1px 3px rgba(120, 100, 80, 0.06), 0 1px 2px rgba(120, 100, 80, 0.04);
  --shadow-bento-hover: 0 8px 24px rgba(120, 100, 80, 0.09), 0 4px 8px rgba(120, 100, 80, 0.04);
}

/* Base styles */
html {
  font-size: 100%;  /* 16px base, scale with user preferences */
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-kerning: normal;
  font-feature-settings: "kern" 1, "liga" 1;
}

body {
  font-family: var(--font-sans);
  font-size: 1.125rem;         /* 18px body text */
  line-height: 1.6;            /* Butterick: 120-145% range */
  color: var(--color-text-primary);
  background-color: var(--color-bg-primary);
}

/* Prose constraint -- never exceed 68 characters */
.prose { max-width: 68ch; }

/* All caps helper with proper letterspacing */
.caps {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.8em;
}
```

### 6.2 Component Examples

```tsx
// BentoGrid.tsx -- reusable bento layout component
interface BentoGridProps {
  children: React.ReactNode;
  className?: string;
}

export function BentoGrid({ children, className = '' }: BentoGridProps) {
  return (
    <div
      className={`
        grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4
        gap-5 auto-rows-[180px]
        ${className}
      `}
    >
      {children}
    </div>
  );
}

interface BentoCellProps {
  children: React.ReactNode;
  size?: 'default' | 'wide' | 'tall' | 'hero';
  className?: string;
}

export function BentoCell({
  children,
  size = 'default',
  className = '',
}: BentoCellProps) {
  const sizeClasses = {
    default: '',
    wide: 'sm:col-span-2',
    tall: 'sm:row-span-2',
    hero: 'sm:col-span-2 sm:row-span-2',
  };

  return (
    <div
      className={`
        bg-[var(--color-bg-surface)]
        rounded-xl p-[var(--spacing-card)]
        shadow-[var(--shadow-bento)]
        hover:shadow-[var(--shadow-bento-hover)]
        transition-shadow duration-250 ease-out
        overflow-hidden
        ${sizeClasses[size]}
        ${className}
      `}
    >
      {children}
    </div>
  );
}
```

```tsx
// Example usage: Features section
export function FeaturesSection() {
  return (
    <section className="px-[var(--spacing-page-x)] py-[var(--spacing-page-y)]">
      <h2 className="font-serif text-4xl tracking-tight mb-12">
        Your codebase, always improving
      </h2>

      <BentoGrid>
        <BentoCell size="hero">
          <span className="caps text-[var(--color-text-tertiary)]">
            Autonomous Pipeline
          </span>
          <h3 className="font-serif text-3xl mt-3 mb-4">
            Ship while you sleep
          </h3>
          <p className="text-[var(--color-text-secondary)]">
            Issues triaged, code written, PRs reviewed --
            all before your morning coffee.
          </p>
        </BentoCell>

        <BentoCell>
          <h3 className="font-medium text-lg">Auto-Triage</h3>
          <p className="text-sm text-[var(--color-text-secondary)] mt-2">
            Every issue analyzed, prioritized, and routed.
          </p>
        </BentoCell>

        <BentoCell>
          <h3 className="font-medium text-lg">Self-Review</h3>
          <p className="text-sm text-[var(--color-text-secondary)] mt-2">
            Code reviewed against learned patterns.
          </p>
        </BentoCell>

        <BentoCell size="wide">
          <h3 className="font-medium text-lg">Pattern Learning</h3>
          <p className="text-sm text-[var(--color-text-secondary)] mt-2">
            Every PR teaches the system something new.
            Success patterns reinforced, anti-patterns eliminated.
          </p>
        </BentoCell>
      </BentoGrid>
    </section>
  );
}
```

### 6.3 Accessibility Checklist

This palette has been designed with contrast in mind, but always verify:

| Pair | Light Mode | Dark Mode | WCAG Target |
|---|---|---|---|
| Primary text on bg | `#27292B` on `#F7F6F0` | `#ECE2D0` on `#1A2A2E` | AAA (7:1+) |
| Secondary text on bg | `#5C5C5B` on `#F7F6F0` | `#B8AFA2` on `#1A2A2E` | AA (4.5:1+) |
| Accent on bg | `#264348` on `#F7F6F0` | `#5AADA3` on `#1A2A2E` | AA (4.5:1+) |
| Accent text on accent bg | `#FFFFFB` on `#264348` | `#1A2A2E` on `#5AADA3` | AA (4.5:1+) |

Always test with:
- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
- `prefers-reduced-motion` media query for all animations
- `prefers-color-scheme` for automatic dark mode
- Screen reader testing for bento grid reading order

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

---

## Sources & References

### Japanese Aesthetics
- [Wabi-Sabi in Web Design -- Silphium Design](https://silphiumdesign.com/wabi-sabi-web-design-understanding-imp-prin/)
- [Theories Behind Japanese Design -- Design Sojourn](https://designsojourn.com/theories-behind-japanese-design/)
- [Japanese Principles of Design -- J-Life International](https://jlifeinternational.com/blogs/news/japanese-principles-of-design)
- [White Space in Web Design (2025 Guide) -- Ink Bot Design](https://inkbotdesign.com/white-space-in-web-design/)
- [NIPPON COLORS -- Japanese Traditional Colors](https://nipponcolors.com/)
- [Traditional Colors of Japan -- Wikipedia](https://en.wikipedia.org/wiki/Traditional_colors_of_Japan)
- [Japanese Color Names -- japanesewithanime.com](https://colors.japanesewithanime.com/)
- [Traditional Japanese Color Hex Values -- GitHub Gist](https://gist.github.com/jpegzilla/2ab93a895b0e484fa042b7bde29a093c)
- [NIPPON COLORS Overview -- Art Learnings](https://artlearnings.com/2024/02/14/nippon-colors-overview-of-250-japanese-traditional-colors/)

### Typography
- [Butterick's Practical Typography](https://practicaltypography.com/)
- [Typography in Ten Minutes](https://practicaltypography.com/typography-in-ten-minutes.html)
- [Summary of Key Rules](https://practicaltypography.com/summary-of-key-rules.html)
- [Geist Font -- Vercel](https://vercel.com/font)
- [Google Fonts in Next.js 15 + Tailwind v4](https://www.buildwithmatija.com/blog/how-to-use-custom-google-fonts-in-next-js-15-and-tailwind-v4)
- [Tailwind CSS Typography Plugin](https://github.com/tailwindlabs/tailwindcss-typography)

### Bento Box Layout
- [Web Design Trend: Bento Box -- Medium](https://medium.com/design-bootcamp/web-design-trend-bento-box-95814d99ac62)
- [Bento Box Layout Using Modern CSS -- Codemotion](https://www.codemotion.com/magazine/frontend/lets-create-a-bento-box-design-layout-using-modern-css/)
- [Bento Grids (gallery)](https://bentogrids.com/)
- [How to Use Bento Grids -- freeCodeCamp](https://www.freecodecamp.org/news/bento-grids-in-web-design/)
- [Bento Grid Design: 2025 UI Trend -- Senorit](https://senorit.de/en/blog/bento-grid-design-trend-2025)

### Proportions & Grid Theory
- [Golden Ratio in UI Design -- Nielsen Norman Group](https://www.nngroup.com/articles/golden-ratio-ui-design/)
- [Tatami -- Wikipedia](https://en.wikipedia.org/wiki/Tatami)
- [Niseko Construction: Scale & Proportion](https://nisekoprojects.com/building-in-japan/niseko-construction-basics-scale-proportion/)

### Color Tools
- [Coolors -- Palette Generator](https://coolors.co/)
- [Adobe Color](https://color.adobe.com/)
- [和色大辞典 (Wairo Dictionary)](https://www.colordic.org/w)
- [Realtime Colors](https://www.realtimecolors.com/)
