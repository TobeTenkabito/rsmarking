# README screenshots — November 2026

Captured on 2026-11-12 from the current local application at
`/client/index.html`, using Microsoft Edge through Playwright. Each PNG is an
unmodified browser capture at 1600 × 1000 pixels, with the application language
set to English to match the root README.

| File | View |
|---|---|
| `map-workspace.png` | Project Landsat MNDWI imagery with a saved candidate coastline vector overlay |
| `raster-calculator.png` | Raster calculator with an example water-mask expression; calculation was not submitted |
| `classification.png` | Unsupervised classification settings for the single-band image; classification was not submitted |
| `agent-workspace.png` | Current Agent renderer, Markdown table, visible history, notes, and a pinned conversation |
| `map-export.png` | Current map export settings |

The imagery comes from the existing local project. The vector overlay and the
Agent result summary come from the [recorded coastline validation](../../../docs/agent-coastline-validation-2026-11-12.md).
The Agent screenshot is a presentation of saved results, with demonstration
conversation titles and notes injected into browser memory. It does not show a
new live model response. The recorded run reached its cumulative budget before
final model acceptance, and the spectral sampling ratio is not ground-truth
accuracy.

Capture used the application's existing components and styles. A temporary
browser-only reference exposed the application instance for navigation and
loading the saved overlay. Conversation endpoints were replaced with empty
fixture responses in the screenshot browser, and model requests were blocked.
No private conversation history or API credentials were included; no new model
call or processing job was submitted. No application source changes were needed
for these captures.

Older images elsewhere in `resources/` are retained for existing references;
the root README now uses only the five images in this directory.
