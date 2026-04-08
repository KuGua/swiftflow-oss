# GitHub Release Materials Guide

This document summarizes the recommended public-facing materials for the SwiftFlow OSS repository.

## 1. README Positioning

Recommended repository positioning:

- Category: open-source workforce scheduling system
- Core scenario: multi-store retail and service operations
- Key value: unify store setup, employee readiness, and weekly schedule execution

Recommended headline style:

- Short and product-oriented
- Focus on operational value instead of internal implementation details
- Avoid client history or private project background in the first screen

Recommended first-screen structure:

1. Project name
2. One-sentence positioning
3. One short paragraph explaining target users and product scope
4. Highlights
5. Quick start
6. Screenshots
7. License

## 2. Screenshot Strategy

Recommended public screenshot count:

- 4 to 6 images for the README homepage
- 1 cover image plus 3 to 5 focused feature images

Recommended display order:

1. Overview dashboard
2. Store management workspace
3. Employee management workspace
4. Schedule center weekly view
5. Staff personal schedule view

Recommended image goals:

- Show one business outcome per screenshot
- Keep each image focused on a single module
- Prefer realistic seeded data, but remove personal or sensitive information
- Keep the UI language consistent across all public screenshots

Recommended asset naming:

- `docs/screenshots/01-dashboard-overview.png`
- `docs/screenshots/02-store-management.png`
- `docs/screenshots/03-employee-management.png`
- `docs/screenshots/04-schedule-center.png`
- `docs/screenshots/05-personal-schedule.png`

Recommended README layout:

```md
## Screenshots

| Overview | Store Management |
| --- | --- |
| ![Dashboard](docs/screenshots/01-dashboard-overview.png) | ![Store Management](docs/screenshots/02-store-management.png) |
| Operations overview for managers and admins. | Store setup, area assignment, staffing demand, and rule configuration. |

| Employee Management | Schedule Center |
| --- | --- |
| ![Employee Management](docs/screenshots/03-employee-management.png) | ![Schedule Center](docs/screenshots/04-schedule-center.png) |
| Employee profiles, skills, availability, and store authorization. | Weekly editing, anomaly review, and schedule generation workflows. |
```

Recommended image specs:

- Width: 1600 to 2200 px
- Aspect ratio: prefer 16:10 or 16:9
- Format: PNG for UI screenshots
- Use the same browser zoom and window size across all captures
- Crop away browser bookmarks and unrelated desktop UI

Recommended annotation style:

- Do not over-mark screenshots with too many arrows or boxes
- If annotation is needed, add at most 1 to 2 callouts per image
- Keep explanation text in the caption below the image, not inside the screenshot

Recommended caption template:

- Title: module or workflow name
- One sentence: what the user can accomplish on this screen

Example captions:

- `Operations Overview`: monitor store coverage, staffing readiness, and key operational signals.
- `Store Management`: configure business hours, staffing demand, and scheduling rules per store.
- `Employee Management`: manage employee profiles, skills, availability, and store-level authorization.
- `Schedule Center`: generate, inspect, and adjust weekly schedules in a single workspace.

## 3. Screenshot Capture Checklist

Before capturing screenshots:

- seed representative but non-sensitive demo data
- unify the UI language to English for the public set
- remove placeholder text, broken labels, and empty states that look unfinished
- use one visual theme consistently
- make sure the selected records actually show meaningful content

Avoid in public screenshots:

- personal phone numbers or identifiers
- customer names or internal organization names
- obviously incomplete forms
- debug messages, browser extensions, or development overlays

## 4. License Recommendation

Important note: the `LICENSE` file in the repository should match the final choice exactly. Do not publish an empty `LICENSE` file.

Recommended options:

- `MIT`
  - Best when you want the lowest adoption friction
  - Good for reusable infrastructure or product baseline projects
  - Commercial use is easy, attribution burden is low

- `Apache-2.0`
  - Better when you want an explicit patent grant
  - Slightly more formal than MIT
  - Suitable if you expect broader company adoption and want clearer legal language

- `GPL-3.0`
  - Best when you want derivatives to remain open source when distributed
  - Stronger reciprocal requirements
  - Can reduce adoption for teams that want fewer obligations

Recommended default for SwiftFlow OSS:

- First recommendation: `MIT`
- Second recommendation: `Apache-2.0`

Reasoning:

- SwiftFlow OSS is positioned as a reusable baseline platform
- Lower legal friction generally helps adoption, contribution, and external experimentation
- For an operations product foundation, permissive licensing is usually the most practical public-release strategy

Choose `GPL-3.0` only if your primary goal is to require reciprocally open derivative distributions.

## 5. Release Readiness Checklist

Before the public GitHub release:

- replace the empty `LICENSE` file with the final selected license text
- add final English screenshots under `docs/screenshots/`
- verify the root `README.md` renders correctly on GitHub
- keep `README.zh-CN.md` aligned with the English version
- remove any remaining garbled text, internal notes, or private references
- confirm the quick-start steps work from a clean clone

## 6. Suggested Next Step

The fastest path to a professional public repository is:

1. finalize the license
2. capture 4 to 5 English screenshots
3. embed the screenshot table into the root README
4. create the first tagged GitHub release with a concise release summary
