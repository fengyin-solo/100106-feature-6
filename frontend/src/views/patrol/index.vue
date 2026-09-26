<template>
  <section class="page" data-module="patrol">
    <header class="page-head">
      <div>
        <h2>日常巡查管理</h2>
        <p class="page-desc">巡查编号建立后按 待巡查 → 巡查中 → 已完成 流转；发现问题须派单到班组并写清处置措施，处置未完成不得标记完成。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记巡查记录</button>
        <button class="btn" type="button" @click="exportRows">导出日常巡查清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <label class="filter-item">
        <span>巡查状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in rowActions(row)"
              :key="action"
              class="link"
              type="button"
              @click="openAction(action, row)"
            >
              {{ action }}
            </button>
            <button class="link" type="button" @click="openLogs(row)">流转记录</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无日常巡查数据，可先登记巡查记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条日常巡查记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="createVisible" class="modal-mask" @click.self="createVisible = false">
      <div class="modal">
        <h3>登记巡查记录</h3>
        <label v-for="field in createFields" :key="field" class="modal-item">
          <span>{{ field }}<em v-if="createRequired.includes(field)" class="required">*</em></span>
          <input v-model="createForm[field]" :placeholder="`请输入${field}`" />
        </label>
        <p v-if="modalError" class="error-text">{{ modalError }}</p>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="submitCreate">确认登记</button>
          <button class="btn ghost" type="button" @click="createVisible = false">取消</button>
        </div>
      </div>
    </div>

    <div v-if="actionDialog.visible" class="modal-mask" @click.self="actionDialog.visible = false">
      <div class="modal">
        <h3>{{ actionDialog.action }} — {{ actionDialog.entry?.['巡查编号'] }}</h3>
        <p class="modal-status">
          当前状态：<strong>{{ actionDialog.entry?.['巡查状态'] }}</strong>
          <span v-if="actionDialog.entry?.['处置状态']">（处置状态：{{ actionDialog.entry?.['处置状态'] }}）</span>
        </p>
        <template v-if="actionDialog.action === '派单处置'">
          <label class="modal-item">
            <span>发现问题<em class="required">*</em></span>
            <input v-model="actionDialog.form['发现问题']" placeholder="巡查路段上发现的问题" />
          </label>
          <label class="modal-item">
            <span>处置班组<em class="required">*</em></span>
            <input v-model="actionDialog.form['处置班组']" placeholder="派给的具体班组" />
          </label>
          <label class="modal-item">
            <span>处置措施<em class="required">*</em></span>
            <input v-model="actionDialog.form['处置措施']" placeholder="写清处置措施" />
          </label>
        </template>
        <label v-if="actionDialog.action === '班长退回'" class="modal-item">
          <span>操作人角色<em class="required">*</em></span>
          <select v-model="actionDialog.form['操作人角色']">
            <option value="">请选择角色</option>
            <option value="班长">班长</option>
            <option value="巡查员">巡查员</option>
          </select>
        </label>
        <label class="modal-item">
          <span>操作人</span>
          <input v-model="actionDialog.form['操作人']" placeholder="交班后便于追溯" />
        </label>
        <label class="modal-item">
          <span>备注</span>
          <input v-model="actionDialog.remark" placeholder="本步操作备注，交班后可见" />
        </label>
        <p v-if="modalError" class="error-text">{{ modalError }}</p>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="submitAction">确认{{ actionDialog.action }}</button>
          <button class="btn ghost" type="button" @click="actionDialog.visible = false">取消</button>
        </div>
      </div>
    </div>

    <div v-if="logDialog.visible" class="modal-mask" @click.self="logDialog.visible = false">
      <div class="modal">
        <h3>流转记录 — {{ logDialog.entry?.['巡查编号'] }}</h3>
        <p class="modal-status">当前状态：<strong>{{ logDialog.entry?.['巡查状态'] }}</strong></p>
        <table class="data-table">
          <thead>
            <tr><th>时间</th><th>动作</th><th>操作人</th><th>备注</th></tr>
          </thead>
          <tbody>
            <tr v-for="(log, index) in logDialog.logs" :key="index">
              <td>{{ log['时间'] }}</td>
              <td>{{ log['动作'] }}</td>
              <td>{{ log['操作人'] }}</td>
              <td>{{ log['备注'] || '—' }}</td>
            </tr>
            <tr v-if="!logDialog.logs.length">
              <td colspan="4" class="empty-state">暂无流转记录</td>
            </tr>
          </tbody>
        </table>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="logDialog.visible = false">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, any>

const ENDPOINT = '/api/patrol'
const columns = ["巡查编号", "巡查路段", "巡查人员", "巡查日期", "巡查路线", "发现问题", "处置班组", "处置状态", "巡查状态", "最近操作时间", "最近操作备注"]
const statuses = ["待巡查", "巡查中", "已挂起", "已完成"]
const createFields = ["巡查编号", "巡查路段", "巡查人员", "巡查日期", "巡查路线"]
const createRequired = ["巡查编号", "巡查路段", "巡查人员"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const modalError = ref('')
const filters = ref<Record<string, string>>({})
const statusFilter = ref('')
const filterFields = columns.slice(0, 1)

const stats = computed(() => statuses.map((status) => ({
  label: status,
  value: rows.value.filter((row) => row['巡查状态'] === status).length,
})))

const createVisible = ref(false)
const createForm = ref<Record<string, string>>({})

const actionDialog = ref({
  visible: false,
  action: '',
  entry: null as Row | null,
  form: {} as Record<string, string>,
  remark: '',
})

const logDialog = ref({
  visible: false,
  entry: null as Row | null,
  logs: [] as Row[],
})

function rowActions(row: Row): string[] {
  switch (String(row['巡查状态'] ?? '')) {
    case '待巡查':
      return ['开始巡查']
    case '巡查中': {
      const list = ['派单处置']
      if (row['处置状态'] === '处置中') list.push('处置完成')
      list.push('完成巡查', '挂起巡查')
      return list
    }
    case '已挂起':
      return ['恢复巡查']
    case '已完成':
      return ['班长退回']
    default:
      return []
  }
}

function resetFilters() {
  filters.value = {}
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = {}
  modalError.value = ''
  createVisible.value = true
}

async function submitCreate() {
  modalError.value = ''
  try {
    const payload = await postJson(ENDPOINT, { values: createForm.value })
    if (!payload.ok) {
      modalError.value = payload.message || '巡查记录登记失败'
      return
    }
    createVisible.value = false
    await reload()
  } catch (error) {
    modalError.value = error instanceof Error ? error.message : '巡查记录登记失败'
  }
}

async function openAction(action: string, row: Row) {
  modalError.value = ''
  // 派单弹窗打开时重新拉取明细，保证弹窗里的状态与列表页看到的是同一份
  const response = await request(`${ENDPOINT}/${row.id}`)
  const entry = response.ok ? await response.json() : row
  actionDialog.value = {
    visible: true,
    action,
    entry,
    remark: '',
    form: {
      '发现问题': entry['发现问题'] ?? '',
      '处置班组': entry['处置班组'] ?? '',
      '处置措施': entry['处置措施'] ?? '',
      '操作人角色': '',
      '操作人': '',
    },
  }
}

async function submitAction() {
  const dialog = actionDialog.value
  if (!dialog.entry) return
  modalError.value = ''
  try {
    const payload = await postJson(`${ENDPOINT}/${dialog.entry.id}/actions`, {
      values: { action: dialog.action, ...dialog.form },
      remark: dialog.remark,
    })
    if (!payload.ok) {
      modalError.value = payload.message || '日常巡查动作未生效'
      return
    }
    dialog.visible = false
    await reload()
  } catch (error) {
    modalError.value = error instanceof Error ? error.message : '日常巡查操作失败'
  }
}

async function openLogs(row: Row) {
  modalError.value = ''
  const response = await request(`${ENDPOINT}/${row.id}`)
  const entry = response.ok ? await response.json() : row
  logDialog.value = { visible: true, entry, logs: entry['操作记录'] ?? [] }
}

async function postJson(path: string, body: Record<string, unknown>) {
  const response = await request(path, { method: 'POST', body: JSON.stringify(body) })
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，操作未生效`)
  }
  return await response.json()
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  for (const [field, keyword] of Object.entries(filters.value)) {
    if (keyword) query.set(field === '巡查编号' ? 'keyword' : field, keyword)
  }
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('巡查记录列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '日常巡查列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}
.modal {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  width: 420px;
  max-height: 80vh;
  overflow: auto;
}
.modal h3 { margin: 0 0 12px; font-size: 15px; }
.modal-status { font-size: 13px; color: var(--muted); margin: 0 0 10px; }
.modal-item { display: block; margin-bottom: 10px; font-size: 13px; }
.modal-item span { display: block; color: var(--muted); margin-bottom: 4px; }
.modal-item input, .modal-item select {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
}
.required { color: #b42318; font-style: normal; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 12px; }
</style>
