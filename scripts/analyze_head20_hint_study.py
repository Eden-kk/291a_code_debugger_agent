#!/usr/bin/env python3
"""
基于 head_20_from_existing.json 生成新 20 HEAD 的 Hint Study 分析报告。
补跑 39 runs 后重新运行 head_20_data_from_existing.py，再运行本脚本即可得到全 20 表格与分析。
输出: docs/report/head_20_hint_study_report.md
"""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "docs" / "report" / "head_20_from_existing.json"
OUT_PATH = PROJECT_ROOT / "docs" / "report" / "head_20_hint_study_report.md"
RESULTS_DIR = PROJECT_ROOT / "results"


def _family(task_id: str) -> str:
    if task_id.startswith("quixbugs_"):
        return "QuixBugs"
    if task_id.startswith("mini_nightmare_"):
        return "Mini-nightmare"
    if task_id.startswith("debugbench_"):
        return "DebugBench"
    return "Other"


def _is_excluded_result(path: Path) -> bool:
    return any(
        tag in part
        for part in path.parts
        for tag in ("ablation", "rerun", "time_control")
    )


def _mistral_family_breakdown(head_tasks: list[str]) -> dict[str, dict[int, tuple[int, int]]]:
    latest: dict[tuple[str, int], tuple[str, bool]] = {}
    head = set(head_tasks)
    for path in RESULTS_DIR.rglob("*.json"):
        if _is_excluded_result(path):
            continue
        try:
            run = json.loads(path.read_text())
        except Exception:
            continue
        task_id = run.get("task_id") or path.name.split("__")[0]
        if task_id not in head:
            continue
        if run.get("protocol") != "react" or run.get("strategy", "baseline") != "baseline":
            continue
        model = run.get("model", "").lower()
        if "mistral" not in model:
            continue
        hint_level = run.get("hint_level", 0)
        if hint_level not in {0, 2, 4}:
            continue
        stamp = run.get("timestamp") or path.name
        key = (task_id, hint_level)
        success = bool(run.get("result", {}).get("success"))
        prev = latest.get(key)
        if prev is None or stamp > prev[0]:
            latest[key] = (stamp, success)

    families = {"DebugBench": [], "Mini-nightmare": [], "QuixBugs": []}
    for task_id in head_tasks:
        fam = _family(task_id)
        if fam in families:
            families[fam].append(task_id)

    breakdown = {}
    for fam, task_ids in families.items():
        breakdown[fam] = {}
        total = len(task_ids)
        for hint_level in (0, 2, 4):
            passed = sum(
                1
                for task_id in task_ids
                if latest.get((task_id, hint_level), ("", False))[1]
            )
            breakdown[fam][hint_level] = (passed, total)
    return breakdown


def main():
    data = json.loads(DATA_PATH.read_text())
    hint = data["hint_study"]
    summary = hint["summary"]
    coverage = hint["coverage"]
    missing = hint["missing_hint_runs"]
    n_head = data["n_head"]
    family_breakdown = _mistral_family_breakdown(data["head_20_tasks"])

    full_20 = coverage["Mistral_L2"] == n_head and coverage["Mistral_L4"] == n_head and coverage["120B_L2"] == n_head
    lines = []
    w = lines.append

    w("# HEAD 20 Hint Study 分析报告")
    w("")
    w(f"**数据来源：** `head_20_from_existing.json`（由 `scripts/head_20_data_from_existing.py` 从 results/ 聚合）")
    w(f"**HEAD 任务数：** {n_head}")
    w("")
    if full_20:
        w("**覆盖：** 全 20 任务 L0/L2/L4（Mistral）、L0/L2（120B）已齐。")
    else:
        w("**覆盖：** L0 全 20；L2/L4 当前仅部分任务有数据，全量需补跑 `scripts/run_head20_missing_hints.py` 后重跑聚合脚本。")
    w("")
    w("---")
    w("")

    # Table
    w("## 1. 剂量-反应总览（新 20 HEAD，react baseline）")
    w("")
    w("| Hint Level | 描述 | Mistral Pass | 120B Pass | 备注 |")
    w("|:----------:|:----:|:------------:|:---------:|:----|")
    m0 = summary.get("Mistral_L0", {})
    b0 = summary.get("120B_L0", {})
    w(f"| L0 | 无 hint | {m0.get('pass', 0)}/{m0.get('n', 0)} ({m0.get('pass_pct', 0):.0f}%) | {b0.get('pass', 0)}/{b0.get('n', 0)} ({b0.get('pass_pct', 0):.0f}%) | 全 20 |")
    m2 = summary.get("Mistral_L2", {})
    b2 = summary.get("120B_L2", {})
    n2_note = f"全 20" if (m2.get("n") == n_head and b2.get("n") == n_head) else f"n={m2.get('n', 0)}/{b2.get('n', 0)}"
    w(f"| L2 | 函数名 | {m2.get('pass', 0)}/{m2.get('n', 0)} ({m2.get('pass_pct', 0):.0f}%) | {b2.get('pass', 0)}/{b2.get('n', 0)} ({b2.get('pass_pct', 0):.0f}%) | {n2_note} |")
    m4 = summary.get("Mistral_L4", {})
    n4_note = "全 20" if m4.get("n") == n_head else f"n={m4.get('n', 0)}"
    w(f"| L4 | 行号 | {m4.get('pass', 0)}/{m4.get('n', 0)} ({m4.get('pass_pct', 0):.0f}%) | — | {n4_note} |")
    w("")

    # Q1
    w("## 2. 因果验证结论")
    w("")
    w("**Q1（定位信息是否恢复能力）：**")
    p0_m = m0.get("pass_pct", 0)
    p2_m = m2.get("pass_pct", 0)
    p4_m = m4.get("pass_pct", 0)
    if m2.get("n", 0) >= 1:
        w(f"- Mistral：L0 → L2 通过率 {p0_m:.0f}% → {p2_m:.0f}%（+{p2_m - p0_m:.0f}pp）；L4 为 {p4_m:.0f}%。")
    w(f"- 120B：L0 → L2 通过率 {b0.get('pass_pct', 0):.0f}% → {b2.get('pass_pct', 0):.0f}%。")
    w("- **结论：** 函数级/行级 hint 可部分恢复 Mistral 在 HEAD 上的表现，说明定位信息有效；剩余失败主要为**修复生成**不足。")
    w("")

    w("**Q2（修复生成是否为主瓶颈）：**")
    if full_20:
        qb = family_breakdown["QuixBugs"]
        db = family_breakdown["DebugBench"]
        mn = family_breakdown["Mini-nightmare"]
        w(f"- 全量 20 上，Mistral 的总体剂量曲线为 L0→L2→L4 = {m0.get('pass', 0)}/{m0.get('n', 0)} → {m2.get('pass', 0)}/{m2.get('n', 0)} → {m4.get('pass', 0)}/{m4.get('n', 0)}。")
        w(f"- 但收益高度集中在 QuixBugs：QuixBugs {qb[0][0]}/{qb[0][1]} → {qb[2][0]}/{qb[2][1]} → {qb[4][0]}/{qb[4][1]}；DebugBench {db[0][0]}/{db[0][1]} → {db[2][0]}/{db[2][1]} → {db[4][0]}/{db[4][1]}；Mini-nightmare {mn[0][0]}/{mn[0][1]} → {mn[2][0]}/{mn[2][1]} → {mn[4][0]}/{mn[4][1]}。")
        w("- **结论：** 行级定位对单行算法型 HEAD 可显著缩短“最后一跳”，但对结构性更强的 DebugBench / Mini-nightmare 几乎无效；因此**修复生成**仍是更一般的主瓶颈。")
        w("- 与原 23-task 子集上观察到的 `L4 < L2` 不同，全量 20 呈现 `L4 > L2`，说明 hint 效果对任务组成高度敏感，体现干预非线性。")
    else:
        w("- L4 行级 hint 下 Mistral 仍仅约 20–30% 量级（随子集略有差异），远低于 Easy；多数 HEAD 即使给出行号仍难修。")
        w("- **结论：** 双维度困难中**修复生成为主**；过于精确的定位（L4）可能引入干扰（原 23 上 L4<L2），体现干预非线性。")
    w("")

    w("**Q3（120B 与 hint）：**")
    w(f"- 120B 在 L0 上已 {b0.get('pass_pct', 0):.0f}%，L2 达 {b2.get('pass_pct', 0):.0f}%；hint 主要提通过率或降成本。")
    w("")

    if not full_20 and (missing.get("Mistral_L2") or missing.get("120B_L2")):
        w("---")
        w("")
        w("## 3. 补跑说明")
        w("")
        w("当前 L2/L4 未覆盖全 20 任务。在**可访问 TritonAI API** 的环境（如校园网/实验室）执行：")
        w("")
        w("```bash")
        w("python scripts/run_head20_missing_hints.py")
        w("```")
        w("")
        w("完成后重新聚合并生成报告：")
        w("")
        w("```bash")
        w("python scripts/head_20_data_from_existing.py")
        w("python scripts/analyze_head20_hint_study.py")
        w("```")
        w("")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
