import sys
import os
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
import asyncio
import os
import json

load_dotenv()

os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2", "true")
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY", "")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "ai-code-reviewer")

from core.github_handler import (
    get_pr_details, post_pr_comment, post_inline_comments, post_pr_status,
)
from core.rag_pipeline import get_context
from core.memory import get_past_issues, store_review
from core.security import verify_github_signature, InvalidSignatureError
from core.config import load_config, filter_files
from core.dashboard import get_dashboard_data, DASHBOARD_HTML
from graph.review_graph import build_graph
from tools.runner import run_all_tools
from tools.repo_manager import PRWorkspace
from tools.pr_size_guardian import check_pr_size, format_size_warning
from tools.breaking_change_detector import detect_breaking_changes
from tools.git_history_analyzer import analyze_git_history
from tools.reviewer_assignment import suggest_reviewers, format_reviewer_suggestion

app = FastAPI(title="AI Code Reviewer")
review_graph = build_graph()


async def process_pr(repo_name: str, pr_number: int):
    """
    Full review pipeline:
      1. Fetch PR details + PR size check
      2. Clone PR workspace + read per-repo config
      3. Run static-analysis tools (language-aware, parallel)
      4. Git history hotspot detection + smart reviewer assignment
      5. Breaking change detection
      6. RAG context + team memory
      7. Run 6 AI agents in parallel
      8. Manager makes merge/block decision
      9. Auto-fix agent generates one-click patches
      10. Post everything to GitHub
    """
    try:
        print(f"\n{'='*60}")
        print(f"  REVIEWING PR #{pr_number} in {repo_name}")
        print(f"{'='*60}")

        # ── Step 1: Fetch PR details ──
        print("\n📥 Step 1: Fetching PR details...")
        pr_details = get_pr_details(repo_name, pr_number)
        post_pr_status(repo_name, pr_details["head_sha"], "pending", "AI review in progress...")
        changed_filenames = [f["filename"] for f in pr_details["files"]]

        # ── Step 1b: PR Size Guardian ──
        size_check = check_pr_size(pr_details)
        if size_check["is_oversized"]:
            print(f"  ⚠️ PR is oversized: {size_check['total_lines']} lines, {size_check['total_files']} files")
            post_pr_comment(repo_name, pr_number, format_size_warning(size_check))

        # ── Step 2: Clone workspace + load config ──
        print("\n📦 Step 2: Setting up workspace...")
        workspace = PRWorkspace(repo_name, pr_number)
        workspace_dir = await asyncio.to_thread(workspace.setup)
        print(f"  📦 Workspace ready")

        try:
            config = load_config(workspace_dir)
            filtered_files = filter_files(pr_details["files"], config)
            diff = json.dumps(filtered_files, indent=2)

            # ── Step 3: Static analysis tools ──
            print(f"\n🔧 Step 3: Static Analysis Tools (parallel)")
            tool_results = await run_all_tools(workspace_dir, filtered_files, config)
            tool_outputs = {name: r.to_prompt_text() for name, r in tool_results.items()}

            total_findings = 0
            for name, result in tool_results.items():
                status = "✅" if result.success else "⚠️ "
                count = len(result.findings) if result.success else 0
                total_findings += count
                print(f"  {status} {name}: {count} findings")
            print(f"  Total: {total_findings} tool findings")

            all_tool_findings = []
            for result in tool_results.values():
                if result.success:
                    for f in result.findings:
                        all_tool_findings.append({
                            "file": f.file, "line": f.line, "severity": f.severity,
                            "message": f"[{f.tool}] {f.message}", "suggestion": f.suggestion,
                        })

            # ── Step 4: Git history + reviewer assignment (parallel) ──
            print("\n📊 Step 4: Git History & Reviewer Assignment")
            history_result, reviewer_result = await asyncio.gather(
                asyncio.to_thread(analyze_git_history, repo_name, changed_filenames),
                asyncio.to_thread(suggest_reviewers, repo_name, changed_filenames, pr_details["author"]),
                return_exceptions=True,
            )

            history = history_result if not isinstance(history_result, Exception) else {"hotspots": [], "to_prompt_text": ""}
            reviewers = reviewer_result if not isinstance(reviewer_result, Exception) else []
            if history.get("hotspots"):
                print(f"  🔥 {len(history['hotspots'])} hotspot file(s) detected")
            if reviewers:
                print(f"  👥 Suggested reviewers: {', '.join(r['login'] for r in reviewers)}")

            # ── Step 5: Breaking change detection ──
            print("\n🔍 Step 5: Breaking Change Detection")
            breaking = detect_breaking_changes(filtered_files)
            if breaking["has_breaking_changes"]:
                print(f"  ⚠️ {len(breaking['findings'])} breaking change(s) detected")
            else:
                print(f"  ✅ No breaking changes")

        finally:
            print("\n  🧹 Cleaning up workspace...")
            await asyncio.to_thread(workspace.cleanup)

        # ── Step 6: RAG + memory context ──
        print("\n🧠 Step 6: RAG Context & Team Memory")
        context = get_context(diff, repo_name)
        past_issues = get_past_issues(repo_name)

        memory_parts = []
        if past_issues:
            memory_parts.append(f"Past issues in this repo: {', '.join(past_issues)}")
        if history.get("to_prompt_text"):
            memory_parts.append(history["to_prompt_text"])
        if breaking["has_breaking_changes"]:
            memory_parts.append("BREAKING CHANGES DETECTED:\n" + "\n".join(f"  - {f}" for f in breaking["findings"]))
        memory_context = "\n\n".join(memory_parts)

        # ── Step 7-9: AI agents + manager + autofix ──
        print("\n🤖 Step 7: AI Agents (6-way parallel → manager → autofix + scorer)")
        agent_config = config.get("agents", {})
        result = await review_graph.ainvoke({
            "diff": diff,
            "context": context,
            "memory_context": memory_context,
            "tool_outputs": tool_outputs,
            "correctness_review": "" if agent_config.get("correctness", True) else "SKIPPED",
            "security_review": "" if agent_config.get("security", True) else "SKIPPED",
            "performance_review": "" if agent_config.get("performance", True) else "SKIPPED",
            "maintainability_review": "" if agent_config.get("maintainability", True) else "SKIPPED",
            "dependency_review": "" if agent_config.get("dependency", True) else "SKIPPED",
            "test_review": "" if agent_config.get("test", True) else "SKIPPED",
            "final_review": "",
            "autofix_suggestions": "",
            "score": "",
        })

        # ── Step 10: Post results to GitHub ──
        print("\n📝 Step 10: Posting Results to GitHub")

        if all_tool_findings:
            post_inline_comments(repo_name, pr_number, all_tool_findings)

        # Build the full comment: review + autofix + reviewers
        full_comment = result["final_review"]

        autofix = result.get("autofix_suggestions", "")
        if autofix and "No Auto-Fixes Available" not in autofix:
            full_comment += f"\n\n---\n\n## 🔧 Auto-Fix Suggestions\n\n{autofix}"

        reviewer_text = format_reviewer_suggestion(reviewers)
        if reviewer_text:
            full_comment += f"\n\n---\n{reviewer_text}"

        post_pr_comment(repo_name, pr_number, full_comment)
        store_review(repo_name, pr_number, result["final_review"])

        score = result.get("score", "0")
        try:
            score_num = int(score)
        except (ValueError, TypeError):
            score_num = 5
        status = "success" if score_num >= 6 else "failure"
        post_pr_status(repo_name, pr_details["head_sha"], status, f"AI review score: {score}/10")

        print(f"\n{'='*60}")
        print(f"  ✅ REVIEW COMPLETE — PR #{pr_number} — Score: {score}/10")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"❌ Error processing PR #{pr_number}: {e}")
        import traceback
        traceback.print_exc()
        try:
            post_pr_comment(
                repo_name, pr_number,
                f"⚠️ AI Code Reviewer encountered an error: {str(e)}",
            )
        except Exception:
            print(f"❌ Could not post error comment to PR")


# ── Endpoints ──

@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receives GitHub webhook, verifies HMAC signature, triggers the review pipeline."""
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    try:
        verify_github_signature(raw_body, signature)
    except InvalidSignatureError as e:
        print(f"🚫 Rejected webhook — invalid signature: {e}")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = json.loads(raw_body)
    action = payload.get("action")

    if action in ("opened", "synchronize"):
        pr_number = payload["pull_request"]["number"]
        repo_name = payload["repository"]["full_name"]
        print(f"\n📬 Webhook received: PR #{pr_number} {action} in {repo_name}")
        background_tasks.add_task(process_pr, repo_name, pr_number)

    return {"status": "received", "message": "Review started in background"}


@app.get("/health")
async def health():
    return {
        "status": "running",
        "project": "AI Code Reviewer",
        "review_dimensions": [
            "correctness & reliability",
            "security",
            "performance & scalability",
            "maintainability & consistency",
            "dependency vulnerabilities",
            "test coverage & quality",
        ],
        "tools": ["bandit", "ruff", "detect-secrets", "pip-audit", "radon", "eslint"],
        "features": [
            "6 specialist AI agents (parallel)",
            "5+ static analysis tools (language-aware)",
            "auto-fix suggestions (one-click patches)",
            "PR size guardian",
            "breaking change detection",
            "git history hotspot analysis",
            "smart reviewer assignment",
            "per-repo config (.ai-reviewer.yml)",
            "inline PR comments",
            "commit status checks (pass/fail)",
            "review dashboard",
            "multi-language (Python + JS/TS)",
        ],
    }


@app.post("/review")
async def manual_review(request: Request):
    """Manual review endpoint for testing without GitHub webhooks."""
    body = await request.json()
    diff = body.get("diff", "")
    repo_name = body.get("repo_name", "test/repo")

    if not diff:
        return {"error": "Please provide diff in request body"}

    context = get_context(diff, repo_name)
    past_issues = get_past_issues(repo_name)
    memory_context = f"Past issues: {', '.join(past_issues)}" if past_issues else ""

    tool_outputs = {}

    result = await review_graph.ainvoke({
        "diff": diff,
        "context": context,
        "memory_context": memory_context,
        "tool_outputs": tool_outputs,
        "correctness_review": "",
        "security_review": "",
        "performance_review": "",
        "maintainability_review": "",
        "dependency_review": "",
        "test_review": "",
        "final_review": "",
        "autofix_suggestions": "",
        "score": "",
    })

    return {
        "correctness_review": result["correctness_review"],
        "security_review": result["security_review"],
        "performance_review": result["performance_review"],
        "maintainability_review": result["maintainability_review"],
        "dependency_review": result["dependency_review"],
        "test_review": result["test_review"],
        "final_review": result["final_review"],
        "autofix_suggestions": result["autofix_suggestions"],
        "score": result["score"],
    }


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Review history dashboard with charts."""
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/dashboard/data")
async def dashboard_data():
    """JSON API for dashboard data (consumed by the dashboard page)."""
    return get_dashboard_data()
