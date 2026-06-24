from core.llm_provider import get_llm_response, aget_llm_response


def _build_prompt(diff: str, memory_context: str = "") -> str:
    return f"""You are a principal engineer who has been woken up at 3 AM because code was pushed
to production without proper review and something broke. Now you're reviewing this diff BEFORE
it ships. Find every way it can fail.

{f"Context — issues this team has hit before: {memory_context}" if memory_context else ""}

Code diff to review:
{diff}

Review with a paranoid mindset across these five dimensions:

**1. CORRECTNESS — Does the logic actually work?**
- Trace through the code mentally with MINIMAL input: empty list, zero, null, single element.
  Then with BOUNDARY input: first item, last item, exactly at the limit, one past the limit.
- Off-by-one errors in loops, slices, array access, range boundaries.
- Inverted conditions, missing else branches, wrong comparison operator (< vs <=, == vs ===).
- Unstated assumptions baked into the code: "this list is never empty", "this key always exists",
  "the caller always passes a positive number." If the code would crash or produce wrong output
  when the assumption is violated, flag it.
- Type mismatches or implicit conversions that silently produce wrong results.

**2. FAILURE HANDLING — What happens when things go wrong?**
- External calls (API, DB, file I/O, network) without error handling — will crash on timeout,
  404, connection refused, malformed response.
- Bare except / except Exception that swallows errors silently — hides bugs in production.
- Error messages without context: catch(e) {{ log("error") }} tells you nothing at 3 AM.
  Good: log("Failed to fetch user", user_id=uid, error=str(e)).
- Partial failure: if step 2 of 3 fails, does step 1's side effect get rolled back or is the
  system left in an inconsistent state?
- Missing timeouts on network/DB calls that will hang the entire request indefinitely.
- What happens when a function returns None/null but the caller doesn't check for it?

**3. CONCURRENCY & STATE — What if two requests hit this simultaneously?**
- Shared mutable state (global variables, class-level dicts, module-level caches) modified
  without locks or thread-safe structures.
- Check-then-act race conditions: "if not exists → create" (another thread creates in between).
- Async operations not properly awaited — fire-and-forget that silently drops work or errors.
- Database operations that should be in a transaction but aren't (read-modify-write without
  atomicity).

**4. BACKWARD COMPATIBILITY — What breaks when this ships?**
- Changed function signatures that existing callers depend on (added required params, removed
  params, changed return type).
- Removed or renamed fields from API responses, config keys, database columns.
- Changed default behavior that existing users/callers expect.
- If this is a shared/core module, who else depends on it and will they break?

**5. OBSERVABILITY — Can we debug this in production?**
- New code paths without any logging — if this fails, there's zero visibility.
- Logs missing context: which user? which request ID? which input caused the failure?
- No way to distinguish between "this code path was never executed" and "it ran successfully
  with zero results."
- Errors that say "something went wrong" instead of specifically what went wrong and why.

Format each finding EXACTLY like this:
DIMENSION: [Correctness / Failure Handling / Concurrency / Backward Compat / Observability]
ISSUE: [precise description — what specifically is wrong]
LINE: [file name and/or line number]
SEVERITY: CRITICAL / HIGH / MEDIUM
IMPACT: [what happens in production if this isn't fixed — describe the specific failure scenario]
FIX: [exact code change or approach]

If the code handles all these well, respond with:
NO CRITICAL ISSUES FOUND

Every finding must describe a specific, reproducible problem with a concrete failure scenario.
Do not flag theoretical risks you can't describe a trigger for."""


def correctness_agent(diff: str, memory_context: str = "") -> str:
    result = get_llm_response(_build_prompt(diff, memory_context))
    print(f"🔍 Correctness Agent done: {len(result)} chars")
    return result


async def acorrectness_agent(diff: str, memory_context: str = "") -> str:
    result = await aget_llm_response(_build_prompt(diff, memory_context))
    print(f"🔍 Correctness Agent done: {len(result)} chars")
    return result
