"""日常巡查业务规则：状态流转、派单校验与操作留痕都收在这里。

状态主线：待巡查 → 巡查中 → 已完成；巡查中可挂起为「已挂起」并恢复；
已完成的记录只能由班长退回，退回后回到巡查中，巡查路线与巡查日期保持不变。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "patrol"
REQUIRED_FIELDS = ["巡查编号", "巡查路段", "巡查人员"]
OPTIONAL_FIELDS = ["巡查日期", "巡查路线"]
STATUS_ORDER = ["待巡查", "巡查中", "已完成"]
SUSPEND_STATUS = "已挂起"
STATUSES = STATUS_ORDER + [SUSPEND_STATUS]
LEADER_ROLE = "班长"

# 每个动作允许执行的前置状态；问题派单与处置办结只维护问题清单，不改变主状态。
ACTION_STATES = {
    "开始巡查": ["待巡查"],
    "问题派单": ["巡查中"],
    "处置办结": ["巡查中"],
    "完成巡查": ["巡查中"],
    "挂起巡查": ["巡查中"],
    "恢复巡查": [SUSPEND_STATUS],
    "班长退回": ["已完成"],
}
ACTION_TARGETS = {
    "开始巡查": "巡查中",
    "完成巡查": "已完成",
    "挂起巡查": SUSPEND_STATUS,
    "恢复巡查": "巡查中",
    "班长退回": "巡查中",
}
DISPATCH_REQUIRED = ["发现问题", "处置班组", "处置措施"]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _open_problems(entry: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in entry.get("problems", []) if item.get("status") == "待处置"]


def _sync(entry: dict[str, Any]) -> None:
    """派生字段与主状态对齐：列表页和派单弹窗读到的是同一份状态。"""
    problems = entry.get("problems", [])
    latest = problems[-1] if problems else {}
    entry["巡查状态"] = entry["status"]
    entry["发现问题"] = latest.get("发现问题", "")
    entry["处置措施"] = latest.get("处置措施", "")
    entry["待处置数"] = len(_open_problems(entry))
    entry["pending"] = entry["status"] != "已完成"
    entry["abnormal"] = bool(_open_problems(entry))


def _append_log(entry: dict[str, Any], action: str, operator: str, role: str, remark: str) -> None:
    """每个动作都留痕：交班后新接手的人能看到上一步的操作时间与备注。"""
    entry.setdefault("logs", []).append({
        "time": _now(),
        "action": action,
        "operator": operator or "未留名",
        "role": role or "",
        "remark": remark or "",
    })


class PatrolService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [
                row for row in rows
                if keyword in str(row.get("巡查编号", "")) or keyword in str(row.get("巡查路段", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(
        self,
        values: dict[str, Any],
        *,
        operator: str = "",
        role: str = "",
        remark: str = "",
    ) -> tuple[dict[str, Any] | None, list[str]]:
        errors = [f"缺少必填字段：{field}" for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        code = str(values.get("巡查编号") or "").strip()
        if code and any(str(row.get("巡查编号")) == code for row in store.rows(MODULE)):
            errors.append(f"巡查编号 {code} 已存在，请换一个编号")
        if errors:
            return None, errors
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in REQUIRED_FIELDS + OPTIONAL_FIELDS:
            entry[field] = str(values.get(field) or "").strip()
        entry["status"] = STATUS_ORDER[0]
        entry["problems"] = []
        entry["logs"] = []
        _sync(entry)
        _append_log(entry, "登记巡查", operator, role, remark)
        rows.append(entry)
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        *,
        operator: str = "",
        role: str = "",
        remark: str = "",
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        values = values or {}
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"巡查记录 {entry_id} 不存在或已归档"
        if action not in ACTION_STATES:
            return None, f"动作「{action}」不属于日常巡查可执行范围"
        current = str(entry.get("status") or "")
        if current not in ACTION_STATES[action]:
            expect = "、".join(ACTION_STATES[action])
            return None, f"当前状态为「{current}」，只有「{expect}」状态才能执行{action}"

        handler = {
            "问题派单": self._dispatch,
            "处置办结": self._close_problem,
            "班长退回": self._return_by_leader,
        }.get(action)
        if handler is not None:
            error = handler(entry, operator=operator, role=role, remark=remark, values=values)
            if error:
                return None, error
        else:
            if action == "完成巡查":
                opens = _open_problems(entry)
                if opens:
                    return None, f"还有 {len(opens)} 条问题未处置办结，不能标记完成"
            entry["status"] = ACTION_TARGETS[action]

        _sync(entry)
        _append_log(entry, action, operator, role, remark)
        message = f"巡查记录已{action}"
        if action == "班长退回":
            message = "巡查记录已退回至巡查中，巡查路线与巡查日期保持不变"
        return entry, message

    def _dispatch(self, entry: dict[str, Any], *, values: dict[str, Any], **_: Any) -> str | None:
        """巡查中发现问题：必须派给具体班组并写清处置措施。"""
        missing = [field for field in DISPATCH_REQUIRED if not str(values.get(field) or "").strip()]
        if missing:
            return f"发现问题必须派单：请补齐{'、'.join(missing)}"
        problems = entry.setdefault("problems", [])
        problems.append({
            "id": max((int(item.get("id", 0)) for item in problems), default=0) + 1,
            "发现问题": str(values["发现问题"]).strip(),
            "处置班组": str(values["处置班组"]).strip(),
            "处置措施": str(values["处置措施"]).strip(),
            "status": "待处置",
            "登记时间": _now(),
            "办结时间": "",
            "处置反馈": "",
        })
        return None

    def _close_problem(self, entry: dict[str, Any], *, remark: str, values: dict[str, Any], **_: Any) -> str | None:
        """处置办结：逐条销号，全部办结后才允许完成巡查。"""
        try:
            problem_id = int(values.get("problem_id"))
        except (TypeError, ValueError):
            return "请先选择要办结的问题"
        for item in _open_problems(entry):
            if int(item.get("id", 0)) == problem_id:
                item["status"] = "已处置"
                item["办结时间"] = _now()
                item["处置反馈"] = remark or ""
                return None
        return f"问题 {problem_id} 不存在或已办结"

    def _return_by_leader(self, entry: dict[str, Any], *, role: str, **_: Any) -> str | None:
        """班长退回：已完成补问题的唯一入口，巡查路线与巡查日期保持不变。"""
        if role != LEADER_ROLE:
            return "已完成的巡查只能由班长退回，请用班长身份操作"
        entry["status"] = ACTION_TARGETS["班长退回"]
        return None
