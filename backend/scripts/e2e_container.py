# 容器端到端实测：上传 → 治理 → 审批 → SUCCESS → PDF 导出
import json
import time
import urllib.request

BE = "http://localhost:8080/api"


def call(method, path, body=None):
    req = urllib.request.Request(
        BE + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        return r.status, json.load(r)


# 1) 启动治理（用已上传的 ds）
ds = "ds_c9e1c72003"
s, d = call("POST", "/workflow/start", {"dataset_id": ds})
rid = d.get("run_id") or d.get("id")
print("start:", s, "run:", rid)

# 2) 轮询到终态（WAITING_APPROVAL 则提交审批）
for _ in range(60):
    time.sleep(5)
    s, st = call("GET", f"/workflow/{rid}")
    status = st.get("status")
    if status == "WAITING_APPROVAL":
        s, pending = call("GET", "/approval/pending")
        approvals = pending.get("approvals", [])
        decisions = {p["operation"]["id"]: "approve" for p in approvals if p.get("operation", {}).get("id")}
        print("审批:", len(decisions), "条", list(decisions)[:3])
        call("POST", "/approval/submit", {"run_id": rid, "operator": "docker-test", "decisions": decisions})
    elif status in ("SUCCESS", "FAILED"):
        print("终态:", status, "| 质量分:", st.get("before_score"), "->", st.get("after_score"))
        break
else:
    print("超时")

# 3) PDF 导出（容器 chromium）
try:
    with urllib.request.urlopen(f"{BE}/report/{rid}/pdf") as r:
        pdf = r.read()
    print("PDF:", len(pdf), "bytes, 头:", pdf[:5])
except Exception as e:
    print("PDF 失败:", str(e)[:120])
