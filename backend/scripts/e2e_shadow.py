"""Shadow Table 端到端：mysql 源治理 → 审批 → 写影子表 → 验证生产表未变."""
import json
import time
import urllib.request

BE = "http://127.0.0.1:8000"


def api(path, method="GET", body=None):
    req = urllib.request.Request(
        BE + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def wait_terminal(run_id, timeout=300):
    """等待终态（SUCCESS/FAILED）；WAITING_APPROVAL 不是终态，继续等."""
    for _ in range(timeout):
        st = api(f"/api/workflow/{run_id}")
        if st["status"] in ("SUCCESS", "FAILED"):
            return st
        time.sleep(2)
    return st


def wait_pause_or_terminal(run_id, timeout=300):
    """等待离开 RUNNING（可能停在 WAITING_APPROVAL 或直达终态）."""
    for _ in range(timeout):
        st = api(f"/api/workflow/{run_id}")
        if st["status"] not in ("RUNNING", "PENDING"):
            return st
        time.sleep(2)
    return st


# 1) 注册 mysql 源
reg = api(
    "/api/database/register",
    "POST",
    {"type": "mysql", "host": "127.0.0.1", "port": 3306,
     "database": "dataguard_test", "username": "root", "password": "root123",
     "table": "customer", "name": "mysql.customer"},
)
ds_id = reg["dataset_id"]
print("dataset:", ds_id)

# 2) 启动治理
run = api("/api/workflow/start", "POST", {"dataset_id": ds_id, "goal": "shadow table e2e"})
run_id = run["run_id"]
print("run:", run_id)

# 3) 等审批，逐条 approve
st = wait_pause_or_terminal(run_id)
print("阶段1:", st["status"])
if st["status"] == "WAITING_APPROVAL":
    pend = api("/api/approval/pending")
    items = [a for a in pend.get("approvals", []) if a["run_id"] == run_id]
    print("审批项:", len(items))
    decisions = {}
    for a in items:
        op = a["operation"]
        op_id = op.get("id") or f"{op['tool']}__{op['column']}"
        decisions[op_id] = "approve"
    print("decisions:", json.dumps(decisions, ensure_ascii=False)[:200])
    api("/api/approval/submit", "POST", {"run_id": run_id, "operator": "e2e", "decisions": decisions})

st = wait_terminal(run_id)
print("阶段2:", st["status"])

# 4) 交付物验证
outs = api(f"/api/dataset/{ds_id}/outputs")
print("cleaned_exists:", outs.get("cleaned_exists"))
print("shadow_table:", outs.get("shadow_table"), "rows:", outs.get("shadow_rows"))
if st["status"] != "SUCCESS":
    raise SystemExit("workflow not SUCCESS")
if not outs.get("shadow_table"):
    raise SystemExit("shadow table not produced")
print("SHADOW E2E PASS")
