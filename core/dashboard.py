import os


def get_dashboard_data() -> dict:
    """Aggregate review history from Supabase for the dashboard."""
    from supabase import create_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return {"error": "Supabase not configured"}

    try:
        supabase = create_client(url, key)
        reviews = (
            supabase.table("review_memory")
            .select("*")
            .order("created_at", desc=True)
            .limit(100)
            .execute()
        )

        if not reviews.data:
            return {"total_reviews": 0, "repos": [], "common_issues": [], "recent": []}

        repos = {}
        issue_counts = {}
        for review in reviews.data:
            repo = review.get("repo_name", "unknown")
            repos[repo] = repos.get(repo, 0) + 1
            for issue_type in review.get("issue_types") or []:
                issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1

        return {
            "total_reviews": len(reviews.data),
            "repos": sorted(
                [{"name": k, "count": v} for k, v in repos.items()],
                key=lambda x: -x["count"],
            ),
            "common_issues": sorted(
                [{"type": k, "count": v} for k, v in issue_counts.items()],
                key=lambda x: -x["count"],
            ),
            "recent": [
                {
                    "repo": r.get("repo_name"),
                    "pr": r.get("pr_number"),
                    "date": r.get("created_at"),
                    "issues": r.get("issue_types", []),
                }
                for r in reviews.data[:15]
            ],
        }
    except Exception as e:
        return {"error": str(e)}


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Code Reviewer — Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0d1117; color: #c9d1d9; padding: 2rem; }
  h1 { color: #58a6ff; margin-bottom: 0.5rem; }
  .subtitle { color: #8b949e; margin-bottom: 2rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 1.5rem; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.5rem; }
  .card h2 { color: #58a6ff; font-size: 1rem; margin-bottom: 1rem; }
  .stat { font-size: 2.5rem; font-weight: bold; color: #f0f6fc; }
  .stat-label { color: #8b949e; font-size: 0.85rem; }
  table { width: 100%%; border-collapse: collapse; margin-top: 0.5rem; }
  th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid #21262d; font-size: 0.85rem; }
  th { color: #8b949e; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 12px;
           font-size: 0.75rem; background: #1f6feb33; color: #58a6ff; margin: 2px; }
  canvas { max-height: 250px; }
</style>
</head>
<body>
<h1>AI Code Reviewer</h1>
<p class="subtitle">Review history &amp; trends</p>

<div class="grid">
  <div class="card">
    <h2>Total Reviews</h2>
    <div class="stat" id="total">—</div>
    <div class="stat-label">pull requests reviewed</div>
  </div>
  <div class="card">
    <h2>Issue Types</h2>
    <canvas id="issueChart"></canvas>
  </div>
  <div class="card">
    <h2>Reviews per Repo</h2>
    <canvas id="repoChart"></canvas>
  </div>
  <div class="card">
    <h2>Recent Reviews</h2>
    <table>
      <thead><tr><th>Repo</th><th>PR</th><th>Issues</th></tr></thead>
      <tbody id="recentTable"></tbody>
    </table>
  </div>
</div>

<script>
fetch('/dashboard/data').then(r => r.json()).then(data => {
  document.getElementById('total').textContent = data.total_reviews || 0;

  const issues = data.common_issues || [];
  new Chart(document.getElementById('issueChart'), {
    type: 'doughnut',
    data: {
      labels: issues.map(i => i.type),
      datasets: [{
        data: issues.map(i => i.count),
        backgroundColor: ['#f85149','#d29922','#3fb950','#58a6ff','#bc8cff','#f778ba'],
      }]
    },
    options: { plugins: { legend: { position: 'right', labels: { color: '#c9d1d9' } } } }
  });

  const repos = data.repos || [];
  new Chart(document.getElementById('repoChart'), {
    type: 'bar',
    data: {
      labels: repos.map(r => r.name.split('/').pop()),
      datasets: [{ label: 'Reviews', data: repos.map(r => r.count), backgroundColor: '#58a6ff' }]
    },
    options: {
      plugins: { legend: { display: false } },
      scales: { x: { ticks: { color: '#8b949e' } }, y: { ticks: { color: '#8b949e' } } }
    }
  });

  const tbody = document.getElementById('recentTable');
  (data.recent || []).forEach(r => {
    const issues = (r.issues || []).map(i => '<span class="badge">' + i + '</span>').join('');
    tbody.innerHTML += '<tr><td>' + (r.repo||'').split('/').pop() +
      '</td><td>#' + r.pr + '</td><td>' + issues + '</td></tr>';
  });
});
</script>
</body>
</html>"""
