# IntelliProcess AI Presentation

A standalone, presentation-first product website for the IntelliProcess AI platform. This app is intentionally isolated from the existing AWS implementation and is designed to run as its own deployable frontend.

## Purpose

- Product-launch presentation deck
- Client demo walkthrough
- Investor or stakeholder storytelling
- Executive briefing for finance and operations teams
- Self-contained Vercel-ready deployment

## Stack

- React + TypeScript
- Vite
- Tailwind CSS
- React Router
- Vitest + Testing Library

## Local development

```bash
npm install
npm run dev
```

Then open the local Vite URL shown in the terminal.

## Production build

```bash
npm run build
```

## Preview production build

```bash
npm run preview
```

## Testing

```bash
npm run test
```

## Deployment

This folder can be deployed as a standalone app on Vercel or any static hosting platform.

Recommended setup:

1. Import this folder as a separate project in Vercel.
2. Use the default Vite build output.
3. Set any environment variables if needed for integrations or product links.

Example environment variable:

```bash
VITE_PRODUCT_APP_URL=https://your-live-app-url
```

## Notes

- The presentation website is independent from the existing IntelliProcess project source.
- It is intended as a narrative deck rather than an operational application.
- All slide content is presentation-demo oriented and should be reviewed before external sharing.
