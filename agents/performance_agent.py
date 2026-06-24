from core.llm_provider import get_llm_response, aget_llm_response


def _build_prompt(diff: str, memory_context: str = "", tool_output: str = "") -> str:
    return f"""You are a senior performance engineer. This code works fine in dev with 10 users
and 100 rows of data. Your job is to figure out what breaks when it hits production with
10,000 concurrent users and 10 million rows. Find the code that will cause the 3 AM page.

{"COMPLEXITY ANALYSIS (radon — cyclomatic complexity):\n" + tool_output + "\n\nHigh complexity scores indicate functions that are hard to optimize and likely to have performance bugs in their branching logic.\n" if tool_output else ""}

{f"Performance history for this team: {memory_context}" if memory_context else ""}

Code diff to review:
{diff}

**1. N+1 QUERIES — The #1 performance killer**
- Database or API calls inside a loop: for user in users: db.get_orders(user.id)
  At 10 users it's fine. At 10,000 users it's 10,000 queries instead of 1.
- ORM lazy-loading that triggers a query for each accessed relationship
- Any pattern where the number of external calls scales with the data size

**2. MEMORY — Will this OOM at scale?**
- Loading entire tables/datasets into memory: db.query("SELECT * FROM orders")
  Works with 100 rows. With 10 million rows, the server runs out of memory.
- Building large lists/dicts in memory when streaming/pagination is possible
- String concatenation in loops (creates N copies of growing strings)
- Caching without eviction limits (unbounded caches are memory leaks)

**3. ALGORITHMS — Does the time complexity match the data size?**
- O(n²) nested loops: for x in list: for y in list: — at 10,000 items that's 100M iterations
- Linear search where a hashmap/set lookup would be O(1)
- Sorting when you only need min/max
- Redundant computation: calculating the same expensive value multiple times

**4. I/O & BLOCKING — Is this blocking the event loop?**
- Synchronous file/network/DB calls in an async codebase — blocks the entire server
- Missing connection pooling — creating a new DB connection per request
- Large file reads without streaming — loading entire files into memory
- Missing timeouts on HTTP calls — one slow upstream = cascading failure

**5. SCALABILITY — What's the first thing that breaks at 100x?**
- In-memory state that doesn't work across multiple server instances
- File-based storage that won't scale horizontally
- Single-threaded bottlenecks in a concurrent system
- Missing rate limiting on expensive operations

For each finding, quantify the impact: how does it scale with N?

Format each finding EXACTLY like this:
ISSUE: [precise description of the performance problem]
SCALE: [what happens at 100x — e.g., "At 10K users, this becomes 10K DB queries per request"]
LINE: [file name and/or line number]
SEVERITY: CRITICAL / HIGH / MEDIUM
FIX: [exact optimization — not just "use caching" but what to cache and how]

If the code performs well at scale, respond with:
NO PERFORMANCE ISSUES FOUND

Only report issues that would actually cause problems at realistic production scale.
Micro-optimizations that save nanoseconds are not findings."""


def performance_agent(diff: str, memory_context: str = "", tool_output: str = "") -> str:
    result = get_llm_response(_build_prompt(diff, memory_context, tool_output))
    print(f"🟡 Performance Agent done: {len(result)} chars")
    return result


async def aperformance_agent(diff: str, memory_context: str = "", tool_output: str = "") -> str:
    result = await aget_llm_response(_build_prompt(diff, memory_context, tool_output))
    print(f"🟡 Performance Agent done: {len(result)} chars")
    return result
