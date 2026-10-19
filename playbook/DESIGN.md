---
version: alpha
name: Next Stop
description: A personal task planner dressed as a railway/airport departures hall. Enamel signs, split-flap boards, paper tickets on a dotted platform floor.
colors:
  primary: "#E03A2D"
  secondary: "#17161A"
  tertiary: "#F6C64B"
  neutral: "#E5E0D4"
  surface: "#F7F4ED"
  paper: "#FBF8F0"
  sign: "#111113"
  board: "#151515"
  flap-top: "#2A2A2A"
  flap-bottom: "#202020"
  ink-soft: "#5D5950"
  go: "#4CCB8C"
  late: "#FF6E60"
  on-dark: "#F3F0E8"
  line-gym: "#3D9A5F"
  line-work: "#2F64A8"
  line-learn: "#8455B8"
  line-home: "#DA7A2C"
  line-personal: "#D4433A"
typography:
  display:
    fontFamily: Archivo
    fontSize: 52px
    fontWeight: 800
    lineHeight: 0.95
    letterSpacing: "-0.02em"
  headline:
    fontFamily: Archivo
    fontSize: 42px
    fontWeight: 800
    lineHeight: 1.04
    letterSpacing: "-0.015em"
  board:
    fontFamily: Doto
    fontSize: 22px
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "0.04em"
    fontVariation: "'ROND' 100"
  stamp:
    fontFamily: Alfa Slab One
    fontSize: 28px
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.08em"
  label:
    fontFamily: Archivo
    fontSize: 11px
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "0.14em"
  body:
    fontFamily: Archivo
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.45
rounded:
  sm: 6px
  md: 10px
  lg: 14px
  pill: 999px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#FFFFFF"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: 12px
  button-ghost:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.secondary}"
    rounded: "{rounded.sm}"
    padding: 12px
  station-sign:
    backgroundColor: "{colors.sign}"
    textColor: "{colors.tertiary}"
    typography: "{typography.display}"
    rounded: "{rounded.lg}"
  board-tile:
    backgroundColor: "{colors.flap-top}"
    textColor: "{colors.tertiary}"
    typography: "{typography.board}"
    rounded: "{rounded.sm}"
  board-panel:
    backgroundColor: "{colors.board}"
    textColor: "{colors.on-dark}"
    rounded: "{rounded.lg}"
  ticket:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.secondary}"
    rounded: "{rounded.md}"
  status-ok:
    backgroundColor: "{colors.sign}"
    textColor: "{colors.go}"
    typography: "{typography.board}"
    rounded: "{rounded.pill}"
  status-late:
    backgroundColor: "{colors.sign}"
    textColor: "{colors.late}"
    typography: "{typography.board}"
    rounded: "{rounded.pill}"
  page:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-soft}"
    typography: "{typography.body}"
  board-flap:
    backgroundColor: "{colors.flap-bottom}"
    textColor: "{colors.tertiary}"
  line-badge-gym:
    backgroundColor: "{colors.line-gym}"
    textColor: "#FFFFFF"
    rounded: "{rounded.pill}"
  line-badge-work:
    backgroundColor: "{colors.line-work}"
    textColor: "#FFFFFF"
    rounded: "{rounded.pill}"
  line-badge-learn:
    backgroundColor: "{colors.line-learn}"
    textColor: "#FFFFFF"
    rounded: "{rounded.pill}"
  line-badge-home:
    backgroundColor: "{colors.line-home}"
    textColor: "#111113"
    rounded: "{rounded.pill}"
  line-badge-personal:
    backgroundColor: "{colors.line-personal}"
    textColor: "#FFFFFF"
    rounded: "{rounded.pill}"
---

## Overview

Next Stop turns a to-do list into a departures hall. A **flight** is a task with a deadline, its **stops** are paper tickets you tear, **boarding** means starting the work, and **departing** means done. Every surface should feel like it came out of a station: black enamel signs, amber split-flap boards, paper tickets with perforations, rubber stamps.

Voice: short, calm, station-announcer. "Last call for passenger Alex." "Gate open. Board to start the work." Never cute, never exclamation marks.

## Colors

- **Signal red (#E03A2D):** the only call-to-action colour. Book, Board now, Share. One red thing per screen.
- **Ink (#17161A):** text, rules, sign panels in light mode.
- **Amber (#F6C64B):** everything shown *on a board*: times, flight codes, LED text, the clock. Never use it on the light floor for body text.
- **Platform floor (#E5E0D4) + dot grid:** page background. Paper (#FBF8F0) for tickets and boarding passes.
- **Go green (#4CCB8C) / late coral (#FF6E60):** status only (Boarding/Boarded vs Delayed/Last call).
- **Line colours:** Gym green, Work blue, Learn purple, Home orange, Personal red. Used for the line badge, the left accent bar and the progress segments. Shown together as the five-stripe bar under every header.

## Typography

- **Archivo** (variable, condensed at 86–92% width, weight 800) for headlines, signs and labels. Labels are 11px caps with 0.14em tracking.
- **Doto** (dot-matrix, ROND 100) for anything displayed on a board: times, codes, statuses, numbers in stats. Switchable to split-flap (Archivo 75% width) with the Dot/Flap toggle.
- **Alfa Slab One** for stamps, airport codes and ticket kickers ("ONE TRIP", "USED", "BOARDED").

## Layout

Max content width 1200px (1480px from 1600px screens, 1800px on 4K). Side padding `clamp(16px, 4vw, 32px)`. Under 520px the board switches from flap rows to stacked cards, still built from tiles. Headlines balance-wrap. Nothing scrolls sideways at any size.

## Elevation & Depth

Flat signs with a 1px hairline. Paper items get a two-step drop shadow (1px contact + 10–16px soft). Boards have an inset dot grid like an LED panel.

## Shapes

Signs and boards: 14px radius. Tickets: notched corners and a dotted perforation line, done with CSS masks. Status pills and line badges: full pill. Buttons: 8px. The "Book a flight" button is itself a ticket (side notches + dashed perforation).

## Components

- `station-sign`: black panel, thin rule 8px from the top, amber dot-matrix title.
- `board-tile`: one character per tile, top/bottom halves in two greys with a 1px seam; letters flip through the alphabet when they change.
- `ticket`: tinted paper (5 palettes), tear-off stub on the right; tearing stamps it USED.
- Boarding pass: vertical, airline band in the line colour, big slab airport codes, date strip, 2-column details, barcode, tear-off stub at the bottom. Boarded = green BOARDED stamp.

## Do's and Don'ts

- Do put every time, code and status on tiles or in Doto.
- Do keep one red call to action per view.
- Do write statuses in board caps: ON TIME, CLOSING, LAST CALL, BOARDED, DELAYED, DEPARTED.
- Don't use amber text on the light floor.
- Don't round tickets into plain cards; they always keep notches or perforations.
- Don't add new accent colours; use a line colour instead.
