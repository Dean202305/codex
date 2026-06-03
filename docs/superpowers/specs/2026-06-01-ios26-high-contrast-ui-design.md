# iOS 26 High Contrast UI Design

## Goal

Refresh the local resume screening app with an iOS 26-inspired, high-contrast workbench interface while keeping the existing workflow and backend APIs unchanged.

## Direction

Use a dark high-contrast application background, a bright readable content surface, and Liquid Glass-inspired functional layers for the top bar, stepper, status banners, and primary controls. The interface should feel like a polished local productivity app rather than a marketing page.

## Requirements

- Keep the existing four-step workflow: file paths, model configuration, precheck, screening run.
- Preserve all current form fields, API calls, run polling, cancellation, notices, and errors.
- Make the current step and main action visually obvious.
- Improve contrast for text, inputs, focus states, success, warning, danger, progress, and logs.
- Use glass treatment only on navigation and control surfaces, not as decoration over every content area.
- Keep layout responsive on desktop and narrow windows.
- Rebuild the static frontend assets used by the packaged local app.

## Visual System

- Background: near-black blue/graphite base with subtle radial highlights.
- Content: high-luminance cards with strong text contrast and restrained 8px radius.
- Controls: translucent top and step controls with blur, borders, and crisp active states.
- Accent: vivid system blue/cyan for primary actions, vivid red for destructive actions.
- Typography: system font stack, compact headings inside panels, no viewport-scaled text.

## Testing

- Run the Vite production build.
- Confirm generated static files update under `src/resume_screening/web/static`.
- Start the local web app and verify the primary screens render in the browser.
- Check that text and controls do not overlap at desktop and mobile widths.
