"""日常巡查接口：登记巡查记录，覆盖开始巡查、问题派单、处置办结、完成巡查、挂起/恢复与班长退回。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.patrol import STATUSES, PatrolService

router = APIRouter(prefix="/api/patrol", tags=["日常巡查"])

service = PatrolService()

LIST_FIELDS = ["巡查编号", "巡查路段", "巡查人员", "巡查日期", "巡查路线", "发现问题", "处置措施", "巡查状态", "待处置数"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按巡查编号或巡查路段检索"),
    status: str | None = Query(default=None, description="待巡查、巡查中、已完成、已挂起"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按巡查编号/路段与状态过滤日常巡查列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出日常巡查清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "patrol", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条巡查记录明细（含问题清单与操作日志）；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"巡查记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条巡查记录，初始状态为待巡查；缺字段或编号重复时说明原因而不是静默丢弃。"""
    entry, errors = service.create_entry(
        payload.values,
        operator=str(payload.values.get("operator") or ""),
        role=str(payload.values.get("role") or ""),
        remark=payload.remark or "",
    )
    if errors:
        return ActionResult(ok=False, message="；".join(errors))
    return ActionResult(ok=True, message="巡查记录已登记，状态为待巡查", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条巡查记录执行状态动作；不满足前置状态或派单校验时会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(
        entry_id,
        action,
        operator=str(payload.values.get("operator") or ""),
        role=str(payload.values.get("role") or ""),
        remark=payload.remark or str(payload.values.get("remark") or ""),
        values=payload.values,
    )
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
