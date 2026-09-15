# Recording the TaskPilot demo

The demo uses this project's PRD and an explicitly supplied folder containing 2–8 real CVs. It runs the normal Gemini endpoints, validates their responses, then keeps those exact responses **only in the recording process's memory**. Playwright replays them with short waits while recording the actual frontend. This is a recording helper, not an application cache or a production mock mode.

Start the API and frontend normally. Use an existing Playwright installation (no app dependency is added):

```bash
PLAYWRIGHT_MODULE_PATH=/absolute/path/to/playwright node demo/prepare-recording.mjs '/path/to/CV folder'
```

When it prints `READY`, enter `record`. The 3840×2160 capture lasts approximately two minutes, contains no subtitles, and shows inputs, both Markdown documents, the graph appearing before owner matching, match evidence, and the GitHub connection area. It does not create GitHub issues or invent usernames. Enter `record` again to redo the capture without another Gemini call; enter `quit` to discard all in-memory results.

A transient Gemini failure gets one automatic retry. If a stage still fails, the runner waits for `retry` or `quit`; successful stages remain in memory. Validation failures are never replaced with fabricated results.

Recordings and stills are in ignored `output/playwright/`. They contain CV-derived personal data and must not be committed. Convert the source WebM to an MP4 with the existing FFmpeg installation, preserving 3840×2160 dimensions. The scripted browser zoom makes text readable at this resolution; graph layout and application data are unchanged.

For the requested clean presentation, the recorder hides technical review-note panels only inside its browser. Skill gaps, learning suggestions and their CV evidence stay visible. Application error screens cause the recording to fail; they are never hidden or replaced with successful results.

The application's health endpoint reports `RENDER_GIT_COMMIT` (or explicit `COMMIT`) so the deployed backend version can be checked after a release. Both Blueprint services target `main`.
