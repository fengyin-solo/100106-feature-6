"""日常巡查业务规则：状态流转、派单处置、挂起恢复与班长退回都收在这里。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "patrol"
REQUIRED_FIELDS = ["巡查编号", "巡查路段", "巡查人员"]
OPTIONAL_FIELDS = ["巡查日期", "巡查路线", "发现问题"]
STATUS_ORDER = ["待巡查", "巡查中", "已挂起", "已完成"]

# 动作 -> (允许的来源状态, 目标状态)；目标状态为 None 表示只登记信息、不改状态
ACTION_RULES: dict[str, tuple[tuple[str, ...], str | None]] = {
    "开始巡查": (("待巡查",), "巡查中"),
    "派单处置": (("巡查中",), None),
    "处置完成": (("巡查中",), None),
    "完成巡查": (("巡查中",), "已完成"),
    "挂起巡查": (("巡查中",), "已挂起"),
    "恢复巡查": (("已挂起",), "巡查中"),
    "班长退回": (("已完成",), "巡查中"),
}


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
            rows = [row for row in rows if keyword in str(row.get("巡查编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS + OPTIONAL_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["处置班组"] = ""
        entry["处置措施"] = ""
        entry["处置状态"] = "无"
        entry["操作记录"] = []
        self._sync_flags(entry)
        self._log(entry, "登记巡查", values, "巡查编号建立，进入待巡查")
        rows.append(entry)
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
        remark: str = "",
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"巡查记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于日常巡查可执行范围"
        values = values or {}
        allowed_from, target = ACTION_RULES[action]
        current = str(entry.get("status") or "")
        if current not in allowed_from:
            return None, f"当前状态「{current}」不允许执行「{action}」"

        if action == "派单处置":
            problem = str(values.get("发现问题") or "").strip()
            team = str(values.get("处置班组") or "").strip()
            measure = str(values.get("处置措施") or "").strip()
            if problem:
                entry["发现问题"] = problem
            if not str(entry.get("发现问题") or "").strip():
                return None, "请先写清发现问题再派单"
            if not team:
                return None, "发现问题后必须派给具体班组，请填写处置班组"
            if not measure:
                return None, "派单时必须写清处置措施"
            entry["处置班组"] = team
            entry["处置措施"] = measure
            entry["处置状态"] = "处置中"
        elif action == "处置完成":
            if entry.get("处置状态") != "处置中":
                return None, "当前没有处置中的问题，无需标记处置完成"
            entry["处置状态"] = "已处置"
        elif action == "完成巡查":
            if entry.get("处置状态") == "处置中":
                return None, "处置措施尚未做完，不允许标记完成"
        elif action == "班长退回":
            role = str(values.get("操作人角色") or "").strip()
            if role != "班长":
                return None, "已完成的巡查补问题必须由班长退回"
            # 退回只改状态，巡查路线与巡查日期保持原样不动

        if target is not None:
            entry["status"] = target
        self._sync_flags(entry)
        self._log(entry, action, values, remark)
        return entry, f"巡查记录已{action}"

    def _sync_flags(self, entry: dict[str, Any]) -> None:
        """把列表页和派单弹窗共用的展示字段与内部状态对齐，保证两处看到的一样。"""
        entry["巡查状态"] = entry["status"]
        entry["pending"] = entry["status"] != "已完成"
        entry["abnormal"] = entry.get("处置状态") == "处置中"

    def _log(self, entry: dict[str, Any], action: str, values: dict[str, Any], remark: str) -> None:
        """每一步都记下操作时间、操作人与备注，交班后新接手的人能接上。"""
        operator = str(values.get("操作人") or "").strip() or str(entry.get("巡查人员") or "系统")
        record = {
            "时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "动作": action,
            "操作人": operator,
            "备注": str(remark or "").strip(),
        }
        entry.setdefault("操作记录", []).append(record)
        entry["最近操作时间"] = record["时间"]
        entry["最近操作备注"] = record["备注"] or record["动作"]
