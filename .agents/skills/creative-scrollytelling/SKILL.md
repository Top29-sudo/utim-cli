---
name: creative-scrollytelling
description: Guidance on implementing high-end scrollytelling designs with intro loading texts, vertical kinetic question sweeps, and split-screen reveal transitions.
---

# Creative Scrollytelling Design Pattern

This skill details the architecture and implementation guidelines for highly creative, typography-driven kinetic scrolling experiences on modern landing pages. It replaces common 3D placeholders with clean, cinematic transitions.

## Phase Structure

A premium typography-split scrolling experience is composed of three consecutive phases driven by a single scroll timeline (`scrollYProgress`):

1. **The Hello Intro (Scroll `0.0` - `0.15`)**:
   - Full black screen with minimal white text showing `"hello!"`.
   - Smoothly scales up and fades out as the user begins scrolling.
   - Suppresses standard page headers and nav items to ensure full immersion.

2. **The Belief questioning Sweep (Scroll `0.15` - `0.58`)**:
   - A series of thought-provoking questions fade in, slide up, and fade out one by one at the center of the viewport.
   - Text is set in a large, elegant sans-serif (e.g., clamp sizes) to command visual authority.
   - Mapping:
     - Question 1: peaks at `0.25`
     - Question 2: peaks at `0.38`
     - Question 3: peaks at `0.50`

3. **The Split Reveal Gate (Scroll `0.58` - `0.72`)**:
   - The screen splits into two sliding panels (Left Gate and Right Gate) touching at `50vw` with a glowing neon seam.
   - Left Gate translates `x: -100%` and Right Gate translates `x: 100%`.
   - Revealing the structural bento grids and functional pages underneath.

4. **The Bento Box Grid Reveal (Scroll `0.72` - `1.0`)**:
   - Behind the splitting doors, the main grid of features fades in (`opacity: 1`) and scales up (`scale: 1`) to settle into view.

## Core CSS Layout for Gates

```css
.gate {
  position: absolute;
  top: 0;
  height: 100vh;
  width: 50vw;
  background: #000;
  z-index: 10;
  transition: border-color 0.3s;
}

.gate-left {
  left: 0;
  border-right: 1px solid rgba(0, 240, 255, 0.15);
}

.gate-right {
  right: 0;
  border-left: 1px solid rgba(0, 240, 255, 0.15);
}
```
