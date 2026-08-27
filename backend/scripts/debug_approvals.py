import sqlite3

con = sqlite3.connect("storage/app.db")
print("=== PENDING 审批条目 ===")
rows = con.execute(
    "SELECT a.id, a.run_id, a.operation, a.created_at, r.status "
    "FROM approvals a LEFT JOIN workflow_runs r ON a.run_id = r.id "
    "WHERE a.status='PENDING' ORDER BY a.created_at"
).fetchall()
for r in rows:
    op = (r[2] or "")[:80]
    print(f"{r[1]} | run_status={r[4]} | {op}")
print()
print("=== workflow_runs 状态 ===")
for r in con.execute("SELECT id, status FROM workflow_runs ORDER BY created_at DESC LIMIT 8").fetchall():
    print(r)
con.close()
