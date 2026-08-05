---
name: web-design-premium
description: Design principles and code implementation guidelines for premium, modern, and visually striking web interfaces. Covers glassmorphism, responsive styling, color systems, micro-animations, typography, and SEO best practices. Activate this skill when writing HTML, CSS, or JS/React interfaces.
---

# Premium Web Design Guide

Create premium, high-end web applications that instantly command attention. Avoid basic default styles, plain colors, and low-contrast borders. Instead, construct responsive layouts with rich typography, glassmorphism, depth, and micro-animations.

---

## 1. Core Design System & CSS Variables

Always define a solid foundation of variables in your CSS root (`index.css` or `App.css`). Use HSL for precise alpha-channel transparency control.

### Premium Dark Theme Core Variables
```css
:root {
  /* HSL Tailored Colors */
  --bg-primary: hsl(230, 25%, 8%);
  --bg-secondary: hsl(230, 20%, 12%);
  --accent-color: hsl(190, 100%, 50%);
  --accent-glow: hsla(190, 100%, 50%, 0.15);
  --text-main: hsl(210, 20%, 95%);
  --text-muted: hsl(210, 10%, 65%);
  
  /* Glassmorphism details */
  --glass-bg: hsla(230, 20%, 12%, 0.6);
  --glass-border: hsla(0, 0%, 100%, 0.08);
  --glass-shadow: 0 8px 32px 0 hsla(0, 0%, 0%, 0.37);
  
  /* Font Family - Premium typography */
  --font-family: 'Outfit', 'Inter', -apple-system, sans-serif;
  
  /* Transitions */
  --transition-smooth: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
```

---

## 2. Glassmorphism Card Pattern

Apply glassmorphism effects for modern structural panels. Combine backing blur with subtle semi-transparent borders.

```css
.premium-card {
  background: var(--glass-bg);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  box-shadow: var(--glass-shadow);
  padding: 24px;
  transition: var(--transition-smooth);
}

.premium-card:hover {
  transform: translateY(-4px);
  border-color: hsla(190, 100%, 50%, 0.3);
  box-shadow: 0 12px 40px 0 hsla(190, 100%, 50%, 0.1);
}
```

---

## 3. High-End Typography & Headers

1. **Font Loading**: Always link Google Fonts like `Outfit` or `Inter` in your HTML `<head>` rather than using browser default sans-serif:
   `<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">`
2. **Text Gradients**: Create striking headings by clipping text to dynamic gradients:
```css
h1 {
  font-family: var(--font-family);
  font-weight: 700;
  font-size: 3rem;
  background: linear-gradient(135deg, var(--text-main) 30%, var(--accent-color) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: -0.02em;
}
```

---

## 4. Interaction Effects & Micro-Animations

Button interactions must feel fluid. Use cubic-bezier curves for transitions and add glow highlights on hover.

```css
.primary-btn {
  background: linear-gradient(135deg, hsl(190, 100%, 50%), hsl(220, 100%, 50%));
  color: #fff;
  border: none;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 15px var(--accent-glow);
  transition: var(--transition-smooth);
}

.primary-btn:hover {
  transform: scale(1.03);
  box-shadow: 0 8px 25px hsla(190, 100%, 50%, 0.4);
}

.primary-btn:active {
  transform: scale(0.98);
}
```

---

## 5. Built-in SEO Checklist

Every interface layout must be semantic and SEO-friendly:
1. **Title and Meta Tags**: Define a title tag and a clear meta description under 160 characters.
2. **Semantic Elements**: Structure the interface with `<header>`, `<main>`, `<section>`, and `<footer>` elements instead of nesting generic `<div>` containers.
3. **Unique Form Elements**: Ensure every input has a matching `<label>` and unique, descriptive `id` attributes for cross-browser testing.
4. **Fast Load Speeds**: Keep images properly compressed, bundle files, and defer render-blocking JavaScript scripts.
