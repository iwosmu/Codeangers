# TaskPilot — a shared starting point for a new team

## Problem and users
Freshly formed hackathon teams waste their first hours discovering who can do what and agreeing on what they are building. Jamie is a 20-year-old computer science student coordinating a team of near-strangers tonight.

## Product
Build a minimal web app that turns the team's CVs and project material into a shared understanding, a dependency graph, and evidence-backed owner suggestions. Assume this is a NEW project starting from an empty repository.

## Demo deliverables
- Project setup: name, context and known constraints; free text and optional MD/PRD, PDF, DOCX, slides, whiteboard images or audio.
- Adjustable teams of 2–8 people; PDF, DOCX, CV images and pasted text, including batch uploads.
- Two independent Gemini analyses, rendered as downloadable and viewable team.md and project.md. Team skills and role suggestions cite the person's CV. Missing information stays 'not stated'. Project output focuses on vision, deliverables, success criteria and open questions.
- A team coverage overview showing strengths, gaps and overlaps, with citations.
- A dependency graph of concrete tasks, headcounts and effort. Preserve a readable layered layout, with zoom, pan, focus mode and a task inspector.
- Load the chart first. Then match people in the background and show suggested owners on the SAME chart. Prefer direct CV evidence. If nobody has a required skill, mark the gap, suggest the closest supported skillset and a first learning step; if there is no relevant evidence, mark the fit unconfirmed. Owners remain editable.
- Connect confirmed GitHub usernames to team members. Preview a parent issue and task sub-issues, with assignees and prerequisite links, before explicit export. Handle partial-export retry.

## Constraints
Use Gemini only (gemini-3.8-flash), native multimodal input and structured output. Use React/TypeScript and FastAPI/Python. Keep CVs and results in memory for the session. Keep the interface minimal and polished. Do not invent skills, expertise, availability or learning-speed claims. This is a hackathon prototype; billing, enterprise permissions and long-term project tracking are out of scope.

## Success
A newly formed team can quickly agree on the project and its skill coverage, download both briefs, and review a usable task graph with owner suggestions. Every suggested match is understandable and traceable. The demo must show a clear transition from inputs to briefs to a graph with people, and a path to GitHub issues.
