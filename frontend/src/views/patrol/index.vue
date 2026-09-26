<template>
  <section class="page" data-module="patrol">
    <header class="page-head">
      <div>
        <h2>日常巡查管理</h2>
        <p class="page-desc">巡查编号建立后按「待巡查 → 巡查中 → 已完成」依次流转；发现问题必须派单到班组并写清处置措施，处置办结后才能标记完成。</p>
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
      <label class="filter-item">
        <span>巡查编号 / 巡查路段</span>
        <input v-model="filters.keyword" placeholder="按巡查编号或路段检索" />
      </label>
      <label class="filter-item">
        <span>巡查状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th>巡查编号</th>
          <th>巡查路段</th>
          <th>巡查人员</th>
          <th>巡查日期</th>
          <th>巡查路线</th>
          <th>发现问题</th>
          <th>处置措施</th>
          <th>巡查状态</th>
          <th>待处置</th>
          <th>上一步操作</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td>{{ row['巡查编号'] }}</td>
          <td>{{ row['巡查路段'] }}</td>
          <td>{{ row['巡查人员'] }}</td>
          <td>{{ row['巡查日期'] || '—' }}</td>
          <td>{{ row['巡查路线'] || '—' }}</td>
          <td>{{ row['发现问题'] || '—' }}</td>
          <td>{{ row['处置措施'] || '—' }}</td>
          <td><span class="badge" :class="statusClass(row['巡查状态'])">{{ row['巡查状态'] }}</span></td>
          <td>{{ openCount(row) ? `${openCount(row)} 条` : '—' }}</td>
          <td>
            <template v-if="lastLog(row)">
              <div>{{ lastLog(row)!.time }} · {{ lastLog(row)!.action }}</div>
              <div class="muted-text">
                {{ lastLog(row)!.operator }}<span v-if="lastLog(row)!.remark">：{{ lastLog(row)!.remark }}</span>
              </div>
            </template>
            <span v-else>—</span>
          </td>
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
            <button class="link" type="button" @click="openLogs(row)">日志</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td colspan="11" class="empty-state">暂无日常巡查数据，可先登记巡查记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条日常巡查记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 登记巡查记录 -->
    <div v-if="createVisible" class="modal-mask" @click.self="createVisible = false">
      <div class="modal">
        <header class="modal-head">
          <h3>登记巡查记录</h3>
          <button class="link" type="button" @click="createVisible = false">关闭</button>
        </header>
        <div class="modal-body form-grid">
          <label class="form-item">
            <span>巡查编号<em>*</em></span>
            <input v-model="createForm['巡查编号']" placeholder="如 PATR-0005" />
          </label>
          <label class="form-item">
            <span>巡查人员<em>*</em></span>
            <input v-model="createForm['巡查人员']" placeholder="巡查人员姓名" />
          </label>
          <label class="form-item full">
            <span>巡查路段<em>*</em></span>
            <input v-model="createForm['巡查路段']" placeholder="如 人民路东段" />
          </label>
          <label class="form-item">
            <span>巡查日期</span>
            <input v-model="createForm['巡查日期']" type="date" />
          </label>
          <label class="form-item">
            <span>巡查路线</span>
            <input v-model="createForm['巡查路线']" placeholder="如 人民路东段全线" />
          </label>
        </div>
        <p class="hint-text">登记后状态为「待巡查」，按 待巡查 → 巡查中 → 已完成 依次流转。</p>
        <footer class="modal-foot">
          <span v-if="modalError" class="error-text">{{ modalError }}</span>
          <button class="btn primary" type="button" @click="submitCreate">提交登记</button>
        </footer>
      </div>
    </div>

    <!-- 问题派单：状态与列表页读同一条记录，保持一致 -->
    <div v-if="dispatchVisible && activeRow" class="modal-mask" @click.self="dispatchVisible = false">
      <div class="modal">
        <header class="modal-head">
          <h3>问题派单 · {{ activeRow['巡查编号'] }}</h3>
          <button class="link" type="button" @click="dispatchVisible = false">关闭</button>
        </header>
        <p class="hint-text">
          当前状态：<span class="badge" :class="statusClass(activeRow['巡查状态'])">{{ activeRow['巡查状态'] }}</span>
          <span class="muted-text">（与巡查列表页为同一条记录）</span>
        </p>
        <div class="modal-body form-grid">
          <label class="form-item full">
            <span>发现问题<em>*</em></span>
            <textarea v-model="dispatchForm['发现问题']" rows="2" placeholder="问题位置与情况，如 K2+300 快车道路面坑槽"></textarea>
          </label>
          <label class="form-item">
            <span>处置班组<em>*</em></span>
            <select v-model="dispatchForm['处置班组']">
              <option value="">请选择班组</option>
              <option v-for="team in teams" :key="team" :value="team">{{ team }}</option>
            </select>
          </label>
          <label class="form-item">
            <span>备注</span>
            <input v-model="dispatchForm.remark" placeholder="现场围挡、时限要求等" />
          </label>
          <label class="form-item full">
            <span>处置措施<em>*</em></span>
            <textarea v-model="dispatchForm['处置措施']" rows="2" placeholder="如 冷补料临时修补，三日内复验"></textarea>
          </label>
        </div>
        <footer class="modal-foot">
          <span v-if="modalError" class="error-text">{{ modalError }}</span>
          <button class="btn primary" type="button" @click="submitDispatch">确认派单</button>
        </footer>
      </div>
    </div>

    <!-- 处置办结 -->
    <div v-if="closeVisible && activeRow" class="modal-mask" @click.self="closeVisible = false">
      <div class="modal">
        <header class="modal-head">
          <h3>处置办结 · {{ activeRow['巡查编号'] }}</h3>
          <button class="link" type="button" @click="closeVisible = false">关闭</button>
        </header>
        <div class="modal-body">
          <div class="problem-pick">
            <label v-for="item in openProblems" :key="item.id">
              <input v-model="closeForm.problemId" type="radio" :value="item.id" />
              <strong>{{ item['发现问题'] }}</strong>
              <span class="muted-text">（{{ item['处置班组'] }} · {{ item['处置措施'] }}）</span>
            </label>
          </div>
          <label class="form-item full" style="margin-top: 10px;">
            <span>处置反馈</span>
            <textarea v-model="closeForm.remark" rows="2" placeholder="处置结果说明，办结后写入操作日志"></textarea>
          </label>
        </div>
        <footer class="modal-foot">
          <span v-if="modalError" class="error-text">{{ modalError }}</span>
          <button class="btn primary" type="button" @click="submitClose">确认办结</button>
        </footer>
      </div>
    </div>

    <!-- 通用动作：开始巡查 / 完成巡查 / 挂起巡查 / 恢复巡查 / 班长退回 -->
    <div v-if="actionVisible && activeRow" class="modal-mask" @click.self="actionVisible = false">
      <div class="modal">
        <header class="modal-head">
          <h3>{{ actionForm.action }} · {{ activeRow['巡查编号'] }}</h3>
          <button class="link" type="button" @click="actionVisible = false">关闭</button>
        </header>
        <p class="hint-text">
          当前状态：<span class="badge" :class="statusClass(activeRow['巡查状态'])">{{ activeRow['巡查状态'] }}</span>
        </p>
        <p v-if="actionForm.action === '班长退回'" class="hint-text">
          已完成的巡查补问题须由班长退回；退回后回到「巡查中」，巡查路线与巡查日期保持不变。
        </p>
        <p v-if="actionForm.action === '完成巡查' && openCount(activeRow) > 0" class="error-text">
          还有 {{ openCount(activeRow) }} 条问题未处置办结，不能标记完成。
        </p>
        <div class="modal-body form-grid">
          <label class="form-item">
            <span>操作人</span>
            <input v-model="actionForm.operator" placeholder="交班后请改成当前接手人" />
          </label>
          <label class="form-item">
            <span>操作角色</span>
            <select v-model="actionForm.role">
              <option value="巡查员">巡查员</option>
              <option value="班长">班长</option>
            </select>
          </label>
          <label class="form-item full">
            <span>备注</span>
            <textarea v-model="actionForm.remark" rows="2" placeholder="操作说明，会写入操作日志供交班查看"></textarea>
          </label>
        </div>
        <footer class="modal-foot">
          <span v-if="modalError" class="error-text">{{ modalError }}</span>
          <button
            class="btn primary"
            type="button"
            :disabled="actionForm.action === '完成巡查' && openCount(activeRow) > 0"
            @click="submitAction"
          >
            确认{{ actionForm.action }}
          </button>
        </footer>
      </div>
    </div>

    <!-- 操作日志：交班后新接手的人在这里看每一步的时间与备注 -->
    <div v-if="logsVisible && activeRow" class="modal-mask" @click.self="logsVisible = false">
      <div class="modal">
        <header class="modal-head">
          <h3>操作日志 · {{ activeRow['巡查编号'] }}</h3>
          <button class="link" type="button" @click="logsVisible = false">关闭</button>
        </header>
        <ul class="log-list">
          <li v-for="(log, index) in activeRow.logs ?? []" :key="index" class="log-item">
            <div>{{ log.time }} · {{ log.action }}</div>
            <div class="log-meta">
              {{ log.operator }}<span v-if="log.role">（{{ log.role }}）</span>
              <span v-if="log.remark">：{{ log.remark }}</span>
            </div>
          </li>
          <li v-if="!(activeRow.logs ?? []).length" class="log-item">暂无操作日志</li>
        </ul>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

interface LogEntry {
  time: string
  action: string
  operator: string
  role: string
  remark: string
}

interface Problem {
  id: number
  发现问题: string
  处置班组: string
  处置措施: string
  status: string
  登记时间: string
  办结时间: string
  处置反馈: string
}

type Row = Record<string, any> & { id: number; logs?: LogEntry[]; problems?: Problem[] }

const ENDPOINT = '/api/patrol'
const statuses = ['待巡查', '巡查中', '已完成', '已挂起']
const teams = ['养护一班', '养护二班', '养护三班', '应急抢修班']
/** 各状态下允许执行的动作，与后端 ACTION_STATES 保持一致 */
const FLOW_ACTIONS: Record<string, string[]> = {
  待巡查: ['开始巡查'],
  巡查中: ['问题派单', '处置办结', '完成巡查', '挂起巡查'],
  已挂起: ['恢复巡查'],
  已完成: ['班长退回'],
}

const session = useSessionStore()

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const modalError = ref('')
const filters = reactive({ keyword: '', status: '' })

const createVisible = ref(false)
const dispatchVisible = ref(false)
const closeVisible = ref(false)
const actionVisible = ref(false)
const logsVisible = ref(false)
const activeRow = ref<Row | null>(null)

const createForm = reactive<Record<string, string>>({
  巡查编号: '',
  巡查路段: '',
  巡查人员: '',
  巡查日期: '',
  巡查路线: '',
})
const dispatchForm = reactive({ 发现问题: '', 处置班组: '', 处置措施: '', remark: '' })
const closeForm = reactive({ problemId: 0, remark: '' })
const actionForm = reactive({ action: '', operator: '', role: '巡查员', remark: '' })

const stats = computed(() =>
  statuses.map((status) => ({
    label: status,
    value: rows.value.filter((row) => row['巡查状态'] === status).length,
  })),
)

const openProblems = computed<Problem[]>(() =>
  (activeRow.value?.problems ?? []).filter((item) => item.status === '待处置'),
)

function openCount(row: Row | null): number {
  if (!row) return 0
  return Number(row['待处置数'] ?? (row.problems ?? []).filter((item) => item.status === '待处置').length)
}

function lastLog(row: Row): LogEntry | null {
  const logs = row.logs ?? []
  return logs.length ? logs[logs.length - 1] : null
}

function statusClass(status: unknown): string {
  switch (String(status)) {
    case '待巡查':
      return 'is-pending'
    case '巡查中':
      return 'is-active'
    case '已完成':
      return 'is-done'
    case '已挂起':
      return 'is-suspended'
    default:
      return ''
  }
}

function rowActions(row: Row): string[] {
  const list = FLOW_ACTIONS[String(row['巡查状态'])] ?? []
  return list.filter((action) => action !== '处置办结' || openCount(row) > 0)
}

function resetFilters() {
  filters.keyword = ''
  filters.status = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  Object.keys(createForm).forEach((key) => {
    createForm[key] = ''
  })
  modalError.value = ''
  createVisible.value = true
}

function openAction(action: string, row: Row) {
  activeRow.value = row
  modalError.value = ''
  if (action === '问题派单') {
    dispatchForm['发现问题'] = ''
    dispatchForm['处置班组'] = ''
    dispatchForm['处置措施'] = ''
    dispatchForm.remark = ''
    dispatchVisible.value = true
    return
  }
  if (action === '处置办结') {
    closeForm.problemId = openProblemsOf(row)[0]?.id ?? 0
    closeForm.remark = ''
    closeVisible.value = true
    return
  }
  actionForm.action = action
  actionForm.operator = session.operator
  actionForm.role = action === '班长退回' ? '班长' : '巡查员'
  actionForm.remark = ''
  actionVisible.value = true
}

function openProblemsOf(row: Row): Problem[] {
  return (row.problems ?? []).filter((item) => item.status === '待处置')
}

function openLogs(row: Row) {
  activeRow.value = row
  logsVisible.value = true
}

async function parseResult(response: Response): Promise<{ ok: boolean; message: string }> {
  const payload = (await response.json().catch(() => null)) as { ok?: boolean; message?: string; detail?: string } | null
  if (!response.ok) {
    throw new Error(payload?.detail ?? `接口返回 ${response.status}，操作未生效`)
  }
  if (!payload?.ok) {
    throw new Error(payload?.message ?? '日常巡查动作未生效，请稍后重试')
  }
  return { ok: true, message: payload.message ?? '' }
}

async function submitCreate() {
  modalError.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ ...createForm, operator: session.operator }),
    })
    await parseResult(response)
    createVisible.value = false
    await reload()
  } catch (error) {
    modalError.value = error instanceof Error ? error.message : '巡查记录登记失败'
  }
}

async function submitDispatch() {
  if (!activeRow.value) return
  modalError.value = ''
  try {
    const response = await request(`${ENDPOINT}/${activeRow.value.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({
        action: '问题派单',
        operator: session.operator,
        发现问题: dispatchForm['发现问题'],
        处置班组: dispatchForm['处置班组'],
        处置措施: dispatchForm['处置措施'],
        remark: dispatchForm.remark,
      }),
    })
    await parseResult(response)
    dispatchVisible.value = false
    await reload()
  } catch (error) {
    modalError.value = error instanceof Error ? error.message : '问题派单失败'
  }
}

async function submitClose() {
  if (!activeRow.value) return
  modalError.value = ''
  try {
    const response = await request(`${ENDPOINT}/${activeRow.value.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({
        action: '处置办结',
        operator: session.operator,
        problem_id: closeForm.problemId,
        remark: closeForm.remark,
      }),
    })
    await parseResult(response)
    closeVisible.value = false
    await reload()
  } catch (error) {
    modalError.value = error instanceof Error ? error.message : '处置办结失败'
  }
}

async function submitAction() {
  if (!activeRow.value) return
  modalError.value = ''
  try {
    const response = await request(`${ENDPOINT}/${activeRow.value.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({
        action: actionForm.action,
        operator: actionForm.operator,
        role: actionForm.role,
        remark: actionForm.remark,
      }),
    })
    await parseResult(response)
    actionVisible.value = false
    await reload()
  } catch (error) {
    modalError.value = error instanceof Error ? error.message : '日常巡查操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.keyword) query.set('keyword', filters.keyword)
  if (filters.status) query.set('status', filters.status)
  query.set('size', '200')
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
