"""One-way, explicitly reviewed GitHub export. Credentials exist only in the request.

Remote markers let retries reconcile already-created issues after partial failure.
No CVs or local export records are stored; a process lock serializes exports.
"""
import asyncio
import hashlib
import json
import threading
from urllib.error import HTTPError, URLError
from urllib.request import Request as URLRequest, build_opener, HTTPRedirectHandler
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import Field, ValidationError, model_validator

from ..brief_schemas import StrictModel
from ..envelope import ApiError, ok

router = APIRouter()
export_lock = threading.Lock()
LOGIN = r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$"


class Member(StrictModel):
    id: str = Field(pattern=r"^m[1-8]$")
    login: str = Field(pattern=LOGIN)


class Task(StrictModel):
    id: int = Field(gt=0, strict=True)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=6000)
    hours: int = Field(ge=1, le=1000, strict=True)
    people: int = Field(ge=1, le=8, strict=True)
    owners: list[str] = Field(min_length=1, max_length=8)
    prerequisites: list[int] = Field(max_length=50)


class ExportInput(StrictModel):
    repository: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}$")
    export_id: UUID
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=6000)
    members: list[Member] = Field(min_length=2, max_length=8)
    tasks: list[Task] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def coherent(self):
        members = {m.id: m for m in self.members}
        tasks = {t.id: t for t in self.tasks}
        if len(members) != len(self.members) or len({m.login.lower() for m in self.members}) != len(members):
            raise ValueError("Use unique members and GitHub accounts.")
        if len(tasks) != len(self.tasks):
            raise ValueError("Task IDs must be unique.")
        done = set()
        for t in self.tasks:
            if len(set(t.owners)) != t.people or len(t.owners) != t.people or not set(t.owners) <= members.keys():
                raise ValueError("Assign the required number of distinct team members to every task.")
            if t.id in t.prerequisites or not set(t.prerequisites) <= tasks.keys() or len(set(t.prerequisites)) != len(t.prerequisites):
                raise ValueError("Invalid task dependencies.")
        while len(done) < len(tasks):
            ready = {t.id for t in self.tasks if set(t.prerequisites) <= done} - done
            if not ready:
                raise ValueError("Task dependencies contain a cycle.")
            done |= ready
        return self


class GitHubFailure(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class GitHub:
    def __init__(self, token):
        self.token = token

    def call(self, method, path, body=None):
        payload = json.dumps(body).encode() if body is not None else None
        request = URLRequest("https://api.github.com" + path, data=payload, method=method, headers={
            "Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10", "Content-Type": "application/json", "User-Agent": "TaskPilot",
        })
        try:
            with build_opener(NoRedirect()).open(request, timeout=20) as response:
                data = response.read()
                return json.loads(data) if data else None
        except HTTPError as exc:
            messages = {401: "GitHub rejected the token. Check or replace it.",
                        403: "GitHub denied this action or rate-limited the request. Check Issues write permission and organization approval.",
                        404: "GitHub could not find this repository, issue or assignable account. Check access and team membership.",
                        422: "GitHub rejected the issue or relationship. Check repository settings and assignments."}
            raise GitHubFailure(messages.get(exc.code, f"GitHub returned HTTP {exc.code}. Retry after checking the repository.")) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise GitHubFailure("GitHub did not return a usable response. An action may have completed; resume this export to reconcile it.") from None


def preflight(client, body):
    user = client.call("GET", "/user")
    repo = client.call("GET", f"/repos/{body.repository}")
    if not repo.get("has_issues") or repo.get("archived"):
        raise GitHubFailure("Choose an active repository with Issues enabled.")
    for m in body.members:
        client.call("GET", f"/repos/{body.repository}/assignees/{m.login}")
    return {"login": user["login"], "repository": repo["full_name"], "private": repo["private"]}


def marker(body, key):
    digest = hashlib.sha256(body.model_dump_json().encode()).hexdigest()[:20]
    return f"<!-- taskpilot:{body.export_id}:{digest}:{key} -->"


def render(body, issues=None):
    issues = issues or {}
    members = {m.id: m.login for m in body.members}
    def link(tid):
        return issues[str(tid)]["html_url"] if str(tid) in issues else f"[task {tid} issue link]"
    parent_body = body.summary + "\n\n## Tasks\n" + "\n".join(f"- [ ] {link(t.id)} — {t.title}" for t in body.tasks)
    parent_body += "\n\n## Dependency flow\n```mermaid\nflowchart TD\n"
    parent_body += "\n".join(f'  T{t.id}["Task {t.id}"]' for t in body.tasks) + "\n"
    parent_body += "\n".join(f"  T{p} --> T{t.id}" for t in body.tasks for p in t.prerequisites) + "\n```"
    parent = {"key": "parent", "title": body.title, "body": parent_body, "assignees": []}
    tasks = []
    for t in body.tasks:
        text = t.description + f"\n\n## Estimate\n{t.hours} hours · {t.people} people"
        text += "\n\n## Prerequisites\n" + ("\n".join(f"- {link(p)}" for p in t.prerequisites) or "None — ready to start when owners are available.")
        text += "\n\n## Project\n" + (issues["parent"]["html_url"] if "parent" in issues else "[parent issue link]")
        tasks.append({"key": str(t.id), "title": f"{t.id}. {t.title}", "body": text, "assignees": [members[mid] for mid in t.owners]})
    return [parent, *tasks]


def export(client, body):
    issues = {}
    result = {"complete": False, "issues": [], "error": None}
    # No request data retained in this lock or elsewhere after the response.
    with export_lock:
        try:
            preflight(client, body)
            base = f"/repos/{body.repository}/issues"
            expected = {marker(body, key): key for key in ["parent", *(str(t.id) for t in body.tasks)]}
            prefix = f"<!-- taskpilot:{body.export_id}:"
            # Paginated list is strongly preferable to GitHub search indexing for retries.
            for page in range(1, 11):
                batch = client.call("GET", f"{base}?state=all&per_page=100&page={page}")
                for issue in batch:
                    content = issue.get("body") or ""
                    if prefix not in content:
                        continue
                    matches = [key for tag, key in expected.items() if tag in content]
                    if not matches:
                        raise GitHubFailure("This export has already started with different content. Restore the original plan before resuming.")
                    key = matches[0]
                    if key in issues:
                        raise GitHubFailure("Duplicate export markers found. Review existing issues before continuing.")
                    issues[key] = issue
                if len(batch) < 100:
                    break
            else:
                raise GitHubFailure("Repository is too large to reconcile safely in this version. Use a smaller project repository.")
            for draft in render(body):
                key = draft["key"]
                if key not in issues:
                    issues[key] = client.call("POST", base, {"title": draft["title"], "body": draft["body"] + "\n\n" + marker(body, key), "assignees": draft["assignees"]})
            parent = issues["parent"]
            existing = set()
            for page in range(1, 3):
                children = client.call("GET", f"{base}/{parent['number']}/sub_issues?per_page=100&page={page}")
                existing.update(child["id"] for child in children)
                if len(children) < 100:
                    break
            for task in body.tasks:
                child = issues[str(task.id)]
                if child["id"] not in existing:
                    client.call("POST", f"{base}/{parent['number']}/sub_issues", {"sub_issue_id": child["id"]})
            for draft in render(body, issues):
                issue = client.call("PATCH", f"{base}/{issues[draft['key']]['number']}", {"body": draft["body"] + "\n\n" + marker(body, draft["key"]), "assignees": draft["assignees"]})
                actual = {a["login"].lower() for a in issue.get("assignees", [])}
                if actual != {name.lower() for name in draft["assignees"]}:
                    raise GitHubFailure("GitHub did not apply every assignee. Check access, then resume this export.")
            result["complete"] = True
        except GitHubFailure as exc:
            result["error"] = str(exc)
        result["issues"] = [{"key": key, "number": issue["number"], "url": issue["html_url"]} for key, issue in issues.items()]
        return result


async def read_input(request):
    token = request.headers.get("x-github-token", "").strip()
    if not token or len(token) > 500 or any(c.isspace() for c in token):
        raise ApiError("bad_input", "Supply a GitHub token for this session with Issues read/write access to the chosen repository.")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > 500_000:
            raise ApiError("bad_input", "Export is too large. Limit it to 50 tasks.")
        data.extend(chunk)
    try:
        return GitHub(token), ExportInput.model_validate_json(data)
    except ValidationError:
        raise ApiError("bad_input", "Check the repository, distinct GitHub usernames, task dependencies and required owner counts.") from None


@router.post("/github/preview")
async def preview(request: Request):
    client, body = await read_input(request)
    try:
        account = await asyncio.to_thread(preflight, client, body)
    except GitHubFailure as exc:
        raise ApiError("bad_input", str(exc), retryable=True) from None
    return ok({"account": account, "issues": render(body)})


@router.post("/github/export")
async def create_export(request: Request):
    client, body = await read_input(request)
    return ok(await asyncio.to_thread(export, client, body))
