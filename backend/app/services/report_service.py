"""报告服务：聚合一次治理运行完整数据 → 自包含 HTML / PDF 导出。

- build_run_report(run_id): 从业务库聚合 issues/plans/executions/validations/approvals
- render_html(report): 生成零外部依赖的 HTML（内嵌 CSS，离线可打开）
- render_pdf(html): 用系统 Edge 无头打印 → 真 PDF（零额外浏览器下载）
"""

import json
import os
import subprocess
import tempfile
from datetime import datetime

from app.models import Approval, CleaningPlan, Dataset, Execution, Issue, Validation, WorkflowRun
from app.storage.database import SessionLocal

# ---------- 中文字典 ----------
TOOL_ZH = {
    "normalize_phone": "电话号归一化",
    "normalize_email": "邮箱归一化",
    "normalize_date": "日期归一化",
    "trim_whitespace": "去除首尾空白",
    "fill_missing": "缺失值填充",
    "delete_duplicate": "删除重复行",
}
SEVERITY_ZH = {"HIGH": "高", "MEDIUM": "中", "LOW": "低"}
ISSUE_TYPE_ZH = {
    "missing_value": "缺失值",
    "duplicate": "重复数据",
    "format": "格式错误",
    "pattern": "格式不规范",
    "outlier": "异常值",
    "inconsistent": "数据不一致",
    "invalid": "非法值",
    "format_issue": "格式问题",
    "phone": "电话号码",
    "email": "邮箱",
    "date": "日期",
}
APPROVAL_ZH = {"APPROVED": "已批准", "REJECTED": "已拒绝", "PENDING": "待审批"}
EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def _parse(v):
    """兼容字符串化 JSON（历史数据存的 str）与真实对象。"""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (json.JSONDecodeError, TypeError):
            return v
    return v


def _tool_zh(name: str) -> str:
    return TOOL_ZH.get(name, name)


def _fmt_time(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def build_run_report(run_id: str) -> dict:
    """聚合一次运行的全部数据为结构化 dict。"""
    with SessionLocal() as session:
        run = session.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
        if not run:
            raise ValueError(f"运行不存在: {run_id}")
        ds = session.query(Dataset).filter(Dataset.id == run.dataset_id).first()
        issues = session.query(Issue).filter(Issue.run_id == run_id).order_by(Issue.id).all()
        plans = session.query(CleaningPlan).filter(CleaningPlan.run_id == run_id).order_by(CleaningPlan.created_at.desc()).all()
        executions = session.query(Execution).filter(Execution.run_id == run_id).order_by(Execution.id).all()
        validations = session.query(Validation).filter(Validation.run_id == run_id).order_by(Validation.id.desc()).limit(1).all()
        approvals = session.query(Approval).filter(Approval.run_id == run_id).order_by(Approval.id).all()

    val = validations[0] if validations else None
    plan = plans[0] if plans else None
    plan_data = _parse(plan.plan) if plan else {}
    actions = plan_data.get("actions", []) if isinstance(plan_data, dict) else []
    details = _parse(val.details) if val else []

    # 质量维度：解析 "completeness: 0.997 -> 1.000"
    quality_dims = []
    for d in details if isinstance(details, list) else []:
        if "->" in str(d):
            name, pair = str(d).split(":", 1)
            before_s, after_s = pair.split("->", 1)
            try:
                quality_dims.append(
                    {
                        "name": name.strip(),
                        "before": round(float(before_s.strip()), 4),
                        "after": round(float(after_s.strip()), 4),
                    }
                )
            except ValueError:
                continue

    # 问题分布
    issue_list = []
    sev_counter = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    type_counter: dict = {}
    for it in issues:
        sev = it.severity or "LOW"
        sev_counter[sev] = sev_counter.get(sev, 0) + 1
        type_counter[it.issue_type] = type_counter.get(it.issue_type, 0) + 1
        issue_list.append(
            {
                "id": it.agent_issue_id or it.id,
                "type": it.issue_type,
                "type_zh": ISSUE_TYPE_ZH.get(it.issue_type, it.issue_type),
                "column": it.column_name,
                "severity": sev,
                "severity_zh": SEVERITY_ZH.get(sev, sev),
                "affected_rows": it.affected_rows or 0,
                "confidence": round(it.confidence or 0, 2),
            }
        )

    # 执行明细（样本取前 5 条做 before/after 对比）
    exe_list = []
    total_affected = 0
    success_exe = 0
    for ex in executions:
        out = _parse(ex.output) or {}
        affected = out.get("affected_rows", 0)
        samples = (out.get("samples") or [])[:5]
        if ex.status == "success":
            success_exe += 1
        total_affected += int(affected or 0)
        exe_list.append(
            {
                "tool": ex.tool_name,
                "tool_zh": _tool_zh(ex.tool_name),
                "status": ex.status,
                "status_zh": "成功" if ex.status == "success" else "失败",
                "affected_rows": int(affected or 0),
                "samples": samples,
            }
        )

    # 审批记录（operation 是字符串化 JSON：{tool, column, risk, affected_rows, samples}）
    approval_list = []
    for ap in approvals:
        op = _parse(ap.operation)
        if isinstance(op, dict):
            approval_list.append(
                {
                    "tool": op.get("tool", ""),
                    "tool_zh": _tool_zh(op.get("tool", "")),
                    "column": op.get("column", ""),
                    "risk": SEVERITY_ZH.get(op.get("risk", ""), op.get("risk", "")),
                    "affected_rows": op.get("affected_rows", 0),
                    "status": ap.status,
                    "status_zh": APPROVAL_ZH.get(ap.status, ap.status),
                }
            )
        else:
            approval_list.append({"tool": str(ap.operation)[:40], "tool_zh": str(ap.operation)[:40], "column": "", "risk": "", "affected_rows": 0, "status": ap.status, "status_zh": APPROVAL_ZH.get(ap.status, ap.status)})

    cleaning_rate = round(success_exe / len(executions) * 100, 1) if executions else 0.0

    return {
        "run_id": run.id,
        "dataset_name": ds.name or ds.filename if ds else "",
        "filename": ds.filename if ds else "",
        "source_type": ds.source_type if ds else "",
        "source_zh": {"file": "文件上传", "web": "网页抓取", "database": "数据库"}.get(ds.source_type if ds else "", ""),
        "row_count": ds.row_count if ds else 0,
        "status": run.status,
        "status_zh": {"SUCCESS": "成功", "FAILED": "失败", "WAITING_APPROVAL": "待审批", "RUNNING": "运行中", "PENDING": "待开始"}.get(run.status, run.status),
        "iteration": run.iteration,
        "goal": run.goal or "通用数据质量治理",
        "created_at": _fmt_time(run.created_at),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "summary": {
            "issues_total": len(issues),
            "issues_high": sev_counter.get("HIGH", 0),
            "issues_medium": sev_counter.get("MEDIUM", 0),
            "issues_low": sev_counter.get("LOW", 0),
            "cleaning_rate": cleaning_rate,
            "affected_rows": total_affected,
            "before_score": round(val.before_score, 2) if val else None,
            "after_score": round(val.after_score, 2) if val else None,
        },
        "quality_dims": quality_dims,
        "severity_dist": [{"name": SEVERITY_ZH[k], "count": v} for k, v in sev_counter.items()],
        "type_dist": [{"name": ISSUE_TYPE_ZH.get(k, k), "count": v} for k, v in type_counter.items()],
        "issues": issue_list,
        "actions": [
            {
                "tool": a.get("tool", ""),
                "tool_zh": _tool_zh(a.get("tool", "")),
                "column": a.get("column", ""),
                "risk": SEVERITY_ZH.get(a.get("risk", ""), a.get("risk", "")),
                "issue_id": a.get("issue_id", ""),
            }
            for a in actions
        ],
        "executions": exe_list,
        "approvals": approval_list,
    }


# ---------- HTML 渲染 ----------
CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; color: #303133; background: #fff; padding: 32px 40px; font-size: 13px; }
h1 { font-size: 24px; color: #1f2d3d; }
.sub { color: #909399; font-size: 12px; margin-top: 4px; }
.head { display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 2px solid #409eff; padding-bottom: 12px; margin-bottom: 20px; }
.head .meta { text-align: right; font-size: 12px; color: #606266; line-height: 1.8; }
.cards { display: flex; gap: 12px; margin-bottom: 20px; }
.card { flex: 1; border: 1px solid #e4e7ed; border-radius: 8px; padding: 12px 14px; }
.card .k { font-size: 12px; color: #909399; margin-bottom: 6px; }
.card .v { font-size: 22px; font-weight: 700; color: #1f2d3d; }
.card .v .unit { font-size: 12px; color: #909399; font-weight: 400; }
.card.up .v { color: #67c23a; }
.card.down .v { color: #f56c6c; }
.card .d { font-size: 12px; color: #67c23a; margin-top: 4px; }
h2 { font-size: 15px; margin: 22px 0 10px; padding-left: 8px; border-left: 4px solid #409eff; color: #1f2d3d; }
.bars { display: flex; flex-direction: column; gap: 8px; }
.bar-row { display: flex; align-items: center; gap: 10px; }
.bar-row .label { width: 90px; font-size: 12px; color: #606266; text-align: right; flex-shrink: 0; }
.bar-row .track { flex: 1; background: #f5f7fa; border-radius: 4px; height: 18px; }
.bar-row .fill { height: 18px; border-radius: 4px; background: linear-gradient(90deg,#409eff,#79bbff); }
.bar-row .num { width: 56px; font-size: 12px; color: #606266; }
table { width: 100%; border-collapse: collapse; margin-top: 6px; }
th, td { border: 1px solid #ebeef5; padding: 7px 10px; text-align: left; font-size: 12px; }
th { background: #f5f7fa; font-weight: 600; color: #606266; }
.tag { display: inline-block; padding: 1px 8px; border-radius: 3px; font-size: 11px; }
.tag.high { background: #fef0f0; color: #f56c6c; }
.tag.medium { background: #fdf6ec; color: #e6a23c; }
.tag.low { background: #f4f4f5; color: #909399; }
.tag.ok { background: #f0f9eb; color: #67c23a; }
.sample { background: #fafafa; border: 1px dashed #e4e7ed; border-radius: 6px; padding: 8px 10px; margin-bottom: 8px; }
.sample .st { font-size: 12px; font-weight: 600; margin-bottom: 6px; }
.sample table { margin-top: 0; }
.before, .after { font-family: Consolas, monospace; font-size: 12px; }
.after { color: #67c23a; }
.before { color: #f56c6c; }
.footer { margin-top: 28px; padding-top: 10px; border-top: 1px solid #ebeef5; color: #c0c4cc; font-size: 11px; text-align: center; }
"""


def _bar(name: str, count: int, total: int, color: str = "#409eff") -> str:
    pct = round(count / total * 100) if total else 0
    return f'<div class="bar-row"><span class="label">{name}</span><div class="track"><div class="fill" style="width:{pct}%;background:{color}"></div></div><span class="num">{count} 条</span></div>'


def render_html(r: dict) -> str:
    s = r["summary"]
    score_html = ""
    if s.get("before_score") is not None:
        delta = round(s["after_score"] - s["before_score"], 2)
        score_html = f'<div class="card up"><div class="k">质量评分</div><div class="v">{s["after_score"]}<span class="unit"> / 100</span></div><div class="d">▲ {s["before_score"]} → {s["after_score"]}（+{delta}）</div></div>'
    else:
        score_html = '<div class="card"><div class="k">质量评分</div><div class="v">—</div></div>'

    # 问题分布
    sev_bars = "".join(_bar(x["name"], x["count"], s["issues_total"] or 1, {"高": "#f56c6c", "中": "#e6a23c", "低": "#909399"}.get(x["name"], "#409eff")) for x in r["severity_dist"])
    type_bars = "".join(_bar(x["name"], x["count"], s["issues_total"] or 1, "#409eff") for x in r["type_dist"]) or '<p style="color:#c0c4cc">无</p>'

    # 质量维度
    dim_rows = ""
    if r["quality_dims"]:
        for d in r["quality_dims"]:
            dim_rows += f'<tr><td>{d["name"]}</td><td>{d["before"]:.4f}</td><td style="color:#67c23a">→ {d["after"]:.4f}</td><td style="color:#67c23a">▲ {d["after"] - d["before"]:+.4f}</td></tr>'
    else:
        dim_rows = '<tr><td colspan="4" style="color:#c0c4cc">无维度数据</td></tr>'

    # 清洗计划
    action_rows = "".join(
        f'<tr><td>{a["tool_zh"]}<span style="color:#c0c4cc">（{a["tool"]}）</span></td><td>{a["column"]}</td><td><span class="tag {"high" if a["risk"]=="高" else "medium" if a["risk"]=="中" else "low"}">{a["risk"]}</span></td><td>{a["issue_id"]}</td></tr>'
        for a in r["actions"]
    ) or '<tr><td colspan="4" style="color:#c0c4cc">无计划</td></tr>'

    # 执行明细 + 样本
    exe_html = ""
    for ex in r["executions"]:
        samples_html = ""
        if ex["samples"]:
            rows = ""
            for sm in ex["samples"]:
                before = sm.get("before", "")
                after = sm.get("after", "")
                b_txt = json.dumps(before, ensure_ascii=False) if isinstance(before, (dict, list)) else str(before)
                a_txt = json.dumps(after, ensure_ascii=False) if isinstance(after, (dict, list)) else str(after)
                rows += f'<tr><td class="before">{b_txt}</td><td class="after">{a_txt}</td></tr>'
            samples_html = f'<div class="sample"><div class="st">样本对比（前 {len(ex["samples"])} 条）</div><table><tr><th>清洗前</th><th>清洗后</th></tr>{rows}</table></div>'
        exe_html += f'<div class="sample"><div class="st">{ex["tool_zh"]}（{ex["tool"]}）<span class="tag ok" style="margin-left:8px">{ex["status_zh"]}</span>　影响 {ex["affected_rows"]} 行</div>{samples_html}</div>'

    # 审批记录
    appr_rows = "".join(
        f'<tr><td>{a["tool_zh"]}</td><td>{a["column"]}</td><td>{a["risk"]}</td><td>{a["affected_rows"]}</td><td><span class="tag ok">{"已批准" if a["status"]=="APPROVED" else "已拒绝" if a["status"]=="REJECTED" else "待审批"}</span></td></tr>'
        for a in r["approvals"]
    ) or '<tr><td colspan="5" style="color:#c0c4cc">无需审批的操作</td></tr>'

    # 问题明细
    issue_rows = "".join(
        f'<tr><td>{i["id"]}</td><td>{i["type_zh"]}<span style="color:#c0c4cc">（{i["type"]}）</span></td><td>{i["column"]}</td><td><span class="tag {"high" if i["severity"]=="HIGH" else "medium" if i["severity"]=="MEDIUM" else "low"}">{i["severity_zh"]}</span></td><td>{i["affected_rows"]}</td><td>{i["confidence"]}</td></tr>'
        for i in r["issues"]
    ) or '<tr><td colspan="6" style="color:#c0c4cc">未发现问题</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>数据治理报告 - {r['dataset_name']}</title><style>{CSS}</style></head>
<body>
  <div class="head">
    <div>
      <h1>📋 数据治理报告</h1>
      <div class="sub">数据集：{r['dataset_name']}　{'' if not r['filename'] or r['filename'] == r['dataset_name'] else f'（{r["filename"]}）'}　来源：{r['source_zh']}　行数：{r['row_count']}</div>
    </div>
    <div class="meta">
      运行编号：{r['run_id']}<br>
      运行状态：{r['status_zh']}　重规划次数：{r['iteration']}<br>
      治理时间：{r['created_at']}
    </div>
  </div>

  <div class="cards">
    <div class="card"><div class="k">发现问题</div><div class="v">{s['issues_total']}<span class="unit"> 条</span></div><div class="d">高 {s['issues_high']} · 中 {s['issues_medium']} · 低 {s['issues_low']}</div></div>
    <div class="card"><div class="k">清洗动作成功率</div><div class="v">{s['cleaning_rate']}<span class="unit"> %</span></div></div>
    <div class="card"><div class="k">影响行数</div><div class="v">{s['affected_rows']}<span class="unit"> 行</span></div></div>
    {score_html}
  </div>

  <h2>质量维度得分</h2>
  <table><tr><th>维度</th><th>治理前</th><th>治理后</th><th>变化</th></tr>{dim_rows}</table>

  <h2>问题分布</h2>
  <div class="bars"><div class="sub" style="margin-bottom:4px">按严重级别</div>{sev_bars}<div class="sub" style="margin:10px 0 4px">按问题类型</div>{type_bars}</div>

  <h2>清洗计划</h2>
  <table><tr><th>动作</th><th>字段</th><th>风险</th><th>关联问题</th></tr>{action_rows}</table>

  <h2>执行明细与样本对比</h2>
  {exe_html}

  <h2>审批记录</h2>
  <table><tr><th>动作</th><th>字段</th><th>风险</th><th>影响行数</th><th>状态</th></tr>{appr_rows}</table>

  <h2>问题明细</h2>
  <table><tr><th>编号</th><th>类型</th><th>字段</th><th>级别</th><th>影响行数</th><th>置信度</th></tr>{issue_rows}</table>

  <div class="footer">由 DataGuard AI 自动生成 · 生成时间：{r['generated_at']} · 本报告基于真实运行数据（Trace 可溯源）</div>
</body></html>"""
    return html


# ---------- PDF 渲染（系统 Edge 无头打印） ----------
def render_pdf(html: str) -> bytes:
    edge = next((p for p in EDGE_CANDIDATES if os.path.exists(p)), None)
    if not edge:
        raise RuntimeError("未找到系统 Edge 浏览器，无法导出 PDF（HTML 导出仍可用）")
    with tempfile.TemporaryDirectory() as tmp:
        html_path = os.path.join(tmp, "report.html")
        pdf_path = os.path.join(tmp, "report.pdf")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        url = "file:///" + html_path.replace("\\", "/")
        result = subprocess.run(
            [edge, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}", url],
            capture_output=True,
            timeout=90,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Edge 打印失败: {result.stderr.decode(errors='ignore')[:200]}")
        with open(pdf_path, "rb") as f:
            return f.read()
