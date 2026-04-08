<template>
  <div class="schedule-page">
    <header class="hero-panel schedule-hero">
      <div class="hero-main">
        <p class="eyebrow">排班中心</p>
        <h1>先看整周时间轴，再就地调整具体班次</h1>
        <p class="hero-copy">周视图保留横向时间刻度，日视图则聚焦到员工班次。点击任意时间条后，会在当前时间表下方直接展开编辑面板。</p>
        <div class="hero-highlights">
          <span class="hero-highlight">
            <small>当前门店</small>
            <strong>{{ selectedStore?.name || '请选择门店' }}</strong>
          </span>
          <span class="hero-highlight">
            <small>营业时间</small>
            <strong>{{ businessHoursText }}</strong>
          </span>
          <span class="hero-highlight">
            <small>当前周</small>
            <strong>{{ weekRangeLabel }}</strong>
          </span>
        </div>
      </div>
      <div class="hero-actions hero-control-card">
        <label class="field compact-field">
          <span>门店</span>
          <select v-model.number="selectedStoreId" :disabled="isBootstrapping || !stores.length">
            <option v-for="store in stores" :key="store.id" :value="store.id">{{ store.name }}</option>
          </select>
        </label>
        <label class="field compact-field">
          <span>周起始日</span>
          <input :value="weekStart" type="date" disabled />
        </label>
      </div>
    </header>

    <div class="action-row control-strip">
      <div class="week-actions">
        <button class="ghost-btn" :disabled="isScheduleLoading" @click="shiftWeek(-7)">上一周</button>
        <button class="ghost-btn" :disabled="isScheduleLoading" @click="jumpToCurrentWeek">本周</button>
        <button class="ghost-btn" :disabled="isScheduleLoading" @click="shiftWeek(7)">下一周</button>
        <button v-if="canDownloadWeeklyView" class="ghost-btn" :disabled="!selectedStore || isScheduleLoading" @click="downloadWeeklyCalendar">下载周历视图</button>
      </div>
      <div v-if="canUseSchedulingActions" class="week-actions">
        <button class="ghost-btn" :disabled="isRepairing || !alertCards.length || !selectedStore" @click="repairAnomalies">修复异常</button>
        <button v-if="showGenerateAllSchedules" class="ghost-btn" :disabled="isGenerating || isGeneratingAll || !selectedStore" @click="generateAllSchedules">
          {{ isGeneratingAll ? '批量生成中…' : '批量生成全部门店' }}
        </button>
        <button class="primary-btn" :disabled="isGenerating || isGeneratingAll || !selectedStore" @click="generateSchedules">
          {{ isGenerating ? '生成中…' : '生成当前门店班表' }}
        </button>
      </div>
    </div>

    <div v-if="errorMsg" class="notice error">{{ errorMsg }}</div>
    <div v-else-if="successMsg" class="notice success">{{ successMsg }}</div>

    <section v-if="selectedStore" class="metrics-grid">
      <article class="metric-card feature">
        <span class="metric-label">门店</span>
        <strong class="metric-value small">{{ selectedStore.name }}</strong>
        <small>{{ businessHoursText }} · {{ storeEmployees.length }} 名授权员工</small>
      </article>
      <article class="metric-card">
        <span class="metric-label">本周异常</span>
        <strong class="metric-value">{{ anomalySummary.total }}</strong>
        <small>无人值班 {{ anomalySummary.empty }} · 人手不足 {{ anomalySummary.shortage }}</small>
      </article>
      <article class="metric-card">
        <span class="metric-label">已排工时</span>
        <strong class="metric-value">{{ totalAssignedHours }}</strong>
        <small>本周累计排班人时</small>
      </article>
      <article class="metric-card">
        <span class="metric-label">规则原型</span>
        <strong class="metric-value small">{{ archetypeLabel }}</strong>
        <small>{{ selectedRuleConfig?.require_opening_dual_skill ? '开店要求前后场双技能' : '开店规则较灵活' }}</small>
      </article>
    </section>

    <section v-if="selectedStore" class="workspace-grid">
      <main class="main-stack full-width">
        <section ref="weeklyPanelRef" class="panel-shell">
          <div class="panel-head">
            <div>
              <h2>周历视图</h2>
              <p>时间刻度、时间条和编辑面板都在同一个工作区内完成，避免跳出当前排班上下文。</p>
            </div>
            <div v-if="allowDailyView" class="view-toggle">
              <button class="switch-btn" :class="{ active: viewMode === 'weekly' }" @click="viewMode = 'weekly'">周视图</button>
              <button class="switch-btn" :class="{ active: viewMode === 'daily' }" @click="viewMode = 'daily'">日视图</button>
            </div>
          </div>

          <div ref="weeklyCalendarWrap" class="weekly-calendar-wrap">
            <div class="weekly-calendar" :style="timelineStyle">
              <div class="weekly-header">
                <div class="calendar-corner">日期 / 时段</div>
                <div class="calendar-hours" :style="timelineStyle">
                  <span v-for="slot in hourSlots" :key="`head-${slot.hour}`">{{ slot.label }}</span>
                </div>
              </div>

              <div v-for="day in dayBoards" :key="day.date" class="calendar-row">
                <div class="calendar-day-column">
                  <button class="calendar-day-label" :class="{ active: selectedDayDate === day.date, alert: day.hasCriticalAlert }" @click="handleDayClick(day.date)">
                    <strong>{{ day.weekdayLabel }}</strong>
                    <span>{{ day.displayDate }}</span>
                    <small>{{ day.employeeCount }} 人 · {{ day.assignedHours }}h</small>
                  </button>
                  <button v-if="canEditShifts" class="ghost-btn shift-create-trigger day-create-trigger" type="button" @click="openCreateShiftEditor(day.date)">
                    新增排班
                  </button>
                </div>

                <div class="calendar-row-body">
                  <div class="calendar-slots">
                    <div class="calendar-track-grid" :style="timelineStyle">
                      <span v-for="slot in hourSlots" :key="`${day.date}-grid-${slot.hour}`"></span>
                    </div>
                    <div class="track-bands">
                      <span v-for="band in day.demandBands" :key="`${day.date}-${band.segmentKey}`" class="track-band" :class="band.status" :style="band.style"></span>
                    </div>

                    <button
                      v-for="bar in day.shiftBars"
                      :key="`${day.date}-${bar.employee.id}-${bar.segmentKey}`"
                      class="calendar-bar-row"
                      :class="{ active: selectedShiftBar?.uniqueKey === `${day.date}-${bar.employee.id}-${bar.segmentKey}` }"
                      :disabled="!canEditShifts"
                      @click="openShiftEditor(day.date, bar)"
                    >
                      <span class="calendar-bar-meta">
                        <strong>{{ bar.employee.name }}</strong>
                        <small>{{ employmentLabel(bar.employee.employment_type) }}</small>
                      </span>
                      <span class="calendar-bar-track">
                        <span class="calendar-bar-fill" :class="bar.variant" :style="bar.style" :title="`${bar.employee.name} ${bar.label}`">
                          <strong>{{ bar.label }}</strong>
                        </span>
                      </span>
                    </button>

                    <div v-if="!day.shiftBars.length" class="timeline-empty">当天还没有排出班次</div>
                  </div>

                  <div v-if="activeEditorDate === day.date" class="inline-shift-panel">
                    <div class="panel-head inline-panel-head">
                      <div>
                        <h3>{{ isCreatingShift ? '新增排班时间段' : '班次编辑' }}</h3>
                        <p>{{ isCreatingShift ? '在当前周视图下方直接新增班次，并选择可安排的员工。' : '在当前周视图下方直接修改时间，并选择可顶班人员。' }}</p>
                      </div>
                    </div>
                    <div class="shift-editor">
                      <div class="detail-row"><span>日期</span><strong>{{ day.displayDate }}</strong></div>
                      <div v-if="!isCreatingShift && selectedShiftBar" class="detail-row"><span>原班次</span><strong>{{ selectedShiftBar.employee.name }} · {{ selectedShiftBar.label }}</strong></div>
                      <div v-else class="detail-row"><span>新增模式</span><strong>为当前日期新增一段排班</strong></div>
                      <div class="editor-grid">
                        <label class="field">
                          <span>开始时间</span>
                          <select v-model.number="shiftEditor.startHour">
                            <option v-for="slot in hourSlots" :key="`week-start-${day.date}-${slot.hour}`" :value="slot.hour">{{ slot.label }}</option>
                          </select>
                        </label>
                        <label class="field">
                          <span>结束时间</span>
                          <select v-model.number="shiftEditor.endHour">
                            <option v-for="slot in hourSlots" :key="`week-end-${day.date}-${slot.hour}`" :value="slot.hour + 1">{{ formatHour(slot.hour + 1) }}</option>
                          </select>
                        </label>
                      </div>
                      <label class="field">
                        <span>安排员工</span>
                        <select v-model.number="shiftEditor.employeeId">
                          <option v-if="isCreatingShift" :value="null">请选择员工</option>
                          <option v-else-if="selectedShiftBar" :value="selectedShiftBar.employee.id">{{ selectedShiftBar.employee.name }}（当前）</option>
                          <option v-for="candidate in replacementCandidates" :key="`week-candidate-${candidate.employee.id}`" :value="candidate.employee.id">
                            {{ candidate.employee.name }} · {{ candidate.reasonText }}
                          </option>
                        </select>
                      </label>
                      <div class="editor-actions">
                        <button class="ghost-btn" type="button" @click="closeShiftEditor">取消</button>
                        <button v-if="!isCreatingShift" class="ghost-btn danger-btn" type="button" :disabled="isDeletingShift || isSavingShift" @click="deleteShiftEdit">{{ isDeletingShift ? '删除中…' : '删除当前排班' }}</button>
                        <button class="primary-btn" type="button" :disabled="isSavingShift || isDeletingShift" @click="saveShiftEdit">{{ isSavingShift ? '保存中…' : isCreatingShift ? '保存新增排班' : '保存班次调整' }}</button>
                      </div>
                      <div>
                        <span class="detail-label">{{ isCreatingShift ? '可安排员工' : '可顶班人员' }}</span>
                        <div v-if="replacementCandidates.length" class="candidate-list">
                          <button v-for="candidate in replacementCandidates" :key="`week-card-${candidate.employee.id}`" class="candidate-card" type="button" @click="setReplacementCandidate(candidate.employee.id)">
                            <strong>{{ candidate.employee.name }}</strong>
                            <span>{{ employmentLabel(candidate.employee.employment_type) }}</span>
                            <small>{{ candidate.reasonText }}</small>
                          </button>
                        </div>
                        <div v-else class="empty-block">{{ isCreatingShift ? '当前没有可完整覆盖该时间段的员工。' : '当前没有可完整覆盖该时间段的候选人员。' }}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="allowDailyView && selectedDayBoard" class="day-layout">
            <div class="day-summary">
              <div>
                <h3>{{ selectedDayBoard.displayDate }}</h3>
                <p>{{ businessHoursText }} · {{ selectedDayBoard.employeeCount }} 人上班</p>
              </div>
              <div class="chips-row">
                <span class="soft-tag">{{ selectedDayBoard.assignedHours }} 已排工时</span>
                <span v-if="selectedDayBoard.emptySlots" class="soft-tag alert-tag">无人值班 {{ selectedDayBoard.emptySlots }}</span>
                <span v-if="selectedDayBoard.shortageSlots" class="soft-tag warning-tag">人手不足 {{ selectedDayBoard.shortageSlots }}</span>
                <button v-if="canEditShifts" class="ghost-btn shift-create-trigger" type="button" @click="openCreateShiftEditor(selectedDayBoard.date, selectedSlot?.date === selectedDayBoard.date ? selectedSlot.hour : null)">
                  新增排班
                </button>
              </div>
            </div>

            <div class="hour-table-wrap">
              <table class="hour-table">
                <thead>
                  <tr>
                    <th>时段</th>
                    <th>已排 / 需求</th>
                    <th>状态</th>
                    <th>员工</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="slot in selectedDayBoard.slots" :key="`${selectedDayBoard.date}-${slot.hour}`" @click="selectSlot(selectedDayBoard.date, slot.hour)">
                    <td>{{ slot.range }}</td>
                    <td>{{ slot.assigned }} / {{ slot.required }}</td>
                    <td><span class="status-dot" :class="slot.status"></span>{{ slot.statusLabel }}</td>
                    <td>{{ slot.names.length ? slot.names.join('、') : '无人安排' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="employee-lanes">
              <article v-for="row in selectedDayBoard.employeeRows" :key="row.employee.id" class="employee-lane">
                <div class="lane-head">
                  <strong>{{ row.employee.name }}</strong>
                  <span>{{ employmentLabel(row.employee.employment_type) }} · {{ row.segmentLabels.join('、') }}</span>
                </div>
                <div class="lane-track-grid" :style="timelineStyle">
                  <span v-for="slot in hourSlots" :key="`${row.employee.id}-grid-${slot.hour}`"></span>
                </div>
                <div class="lane-track">
                  <div class="track-bands">
                    <span v-for="band in selectedDayBoard.demandBands" :key="`${row.employee.id}-${band.segmentKey}`" class="track-band" :class="band.status" :style="band.style"></span>
                  </div>
                  <button
                    v-for="segment in row.segments"
                    :key="`${row.employee.id}-${segment.segmentKey}`"
                    class="lane-bar"
                    :class="[
                      row.employee.employment_type === 'full_time' ? 'full-time' : 'part-time',
                      selectedShiftBar?.uniqueKey === `${selectedDayBoard.date}-${row.employee.id}-${segment.segmentKey}` ? 'active' : '',
                    ]"
                    :style="segment.style"
                    :title="`${row.employee.name} ${segment.label}`"
                    :disabled="!canEditShifts"
                    @click="openShiftEditor(selectedDayBoard.date, { ...segment, employee: row.employee })"
                  >
                    <strong>{{ segment.label }}</strong>
                  </button>
                </div>
              </article>
            </div>

            <div v-if="canEditShifts && activeEditorDate === selectedDayBoard.date" class="inline-shift-panel">
              <div class="panel-head inline-panel-head">
                <div>
                  <h3>{{ isCreatingShift ? '新增排班时间段' : '班次编辑' }}</h3>
                  <p>{{ isCreatingShift ? '在当前日视图下方直接新增班次，并选择可安排的员工。' : '在当前日视图下方直接修改时间，并选择可顶班人员。' }}</p>
                </div>
              </div>
              <div class="shift-editor">
                <div class="detail-row"><span>日期</span><strong>{{ selectedDayBoard.displayDate }}</strong></div>
                <div v-if="!isCreatingShift && selectedShiftBar" class="detail-row"><span>原班次</span><strong>{{ selectedShiftBar.employee.name }} · {{ selectedShiftBar.label }}</strong></div>
                <div v-else class="detail-row"><span>新增模式</span><strong>为当前日期新增一段排班</strong></div>
                <div class="editor-grid">
                  <label class="field">
                    <span>开始时间</span>
                    <select v-model.number="shiftEditor.startHour">
                      <option v-for="slot in hourSlots" :key="`day-start-${slot.hour}`" :value="slot.hour">{{ slot.label }}</option>
                    </select>
                  </label>
                  <label class="field">
                    <span>结束时间</span>
                    <select v-model.number="shiftEditor.endHour">
                      <option v-for="slot in hourSlots" :key="`day-end-${slot.hour}`" :value="slot.hour + 1">{{ formatHour(slot.hour + 1) }}</option>
                    </select>
                  </label>
                </div>
                <label class="field">
                  <span>安排员工</span>
                  <select v-model.number="shiftEditor.employeeId">
                    <option v-if="isCreatingShift" :value="null">请选择员工</option>
                    <option v-else-if="selectedShiftBar" :value="selectedShiftBar.employee.id">{{ selectedShiftBar.employee.name }}（当前）</option>
                    <option v-for="candidate in replacementCandidates" :key="`day-candidate-${candidate.employee.id}`" :value="candidate.employee.id">
                      {{ candidate.employee.name }} · {{ candidate.reasonText }}
                    </option>
                  </select>
                </label>
                <div class="editor-actions">
                  <button class="ghost-btn" type="button" @click="closeShiftEditor">取消</button>
                  <button v-if="!isCreatingShift" class="ghost-btn danger-btn" type="button" :disabled="isDeletingShift || isSavingShift" @click="deleteShiftEdit">{{ isDeletingShift ? '删除中…' : '删除当前排班' }}</button>
                  <button class="primary-btn" type="button" :disabled="isSavingShift || isDeletingShift" @click="saveShiftEdit">{{ isSavingShift ? '保存中…' : isCreatingShift ? '保存新增排班' : '保存班次调整' }}</button>
                </div>
                <div>
                  <span class="detail-label">{{ isCreatingShift ? '可安排员工' : '可顶班人员' }}</span>
                  <div v-if="replacementCandidates.length" class="candidate-list">
                    <button v-for="candidate in replacementCandidates" :key="`day-card-${candidate.employee.id}`" class="candidate-card" type="button" @click="setReplacementCandidate(candidate.employee.id)">
                      <strong>{{ candidate.employee.name }}</strong>
                      <span>{{ employmentLabel(candidate.employee.employment_type) }}</span>
                      <small>{{ candidate.reasonText }}</small>
                    </button>
                  </div>
                  <div v-else class="empty-block">{{ isCreatingShift ? '当前没有可完整覆盖该时间段的员工。' : '当前没有可完整覆盖该时间段的候选人员。' }}</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <aside v-if="showAnalysisPanels" class="side-stack">
          <section class="panel-shell">
            <div class="panel-head">
              <div>
                <h2>重点异常</h2>
                <p>优先查看最需要处理的缺岗和人手不足时段。</p>
              </div>
            </div>
            <div v-if="alertCards.length" class="alert-list">
              <button v-for="alert in alertCards" :key="alert.key" class="alert-card" :class="alert.kind" @click="selectSlot(alert.date, alert.hour); selectedDayDate = alert.date">
                <strong>{{ alert.dayLabel }}</strong>
                <span>{{ alert.range }}</span>
                <p>{{ alert.message }}</p>
                <small v-if="alert.reasonText">{{ alert.reasonText }}</small>
              </button>
            </div>
            <div v-else class="empty-block">本周没有发现无人值班或人手不足的时段。</div>
          </section>

          <section v-if="showFocusPanel" class="panel-shell">
            <div class="panel-head">
              <div>
                <h2>聚焦时段</h2>
                <p>点击异常或时间格，即可查看当前覆盖情况和未覆盖原因。</p>
              </div>
            </div>
            <div v-if="selectedSlotDetail" class="slot-detail">
              <div class="detail-row"><span>日期</span><strong>{{ selectedSlotDetail.dayLabel }}</strong></div>
              <div class="detail-row"><span>时段</span><strong>{{ selectedSlotDetail.range }}</strong></div>
              <div class="detail-row"><span>覆盖情况</span><strong>{{ selectedSlotDetail.assigned }} / {{ selectedSlotDetail.required }}</strong></div>
              <div class="detail-row"><span>状态</span><strong>{{ selectedSlotDetail.statusText }}</strong></div>
              <div>
                <span class="detail-label">在岗员工</span>
                <ul class="name-list">
                  <li v-for="name in selectedSlotDetail.assignedNames" :key="name">{{ name }}</li>
                  <li v-if="!selectedSlotDetail.assignedNames.length">当前无人安排。</li>
                </ul>
              </div>
              <div v-if="selectedSlotDetail.reasons.length">
                <span class="detail-label">未覆盖原因</span>
                <ul class="name-list">
                  <li v-for="reason in selectedSlotDetail.reasons" :key="`${reason.code}-${reason.label}`">{{ reason.label }}：{{ reason.detail }}</li>
                </ul>
              </div>
            </div>
            <div v-else class="empty-block">点击一个时段查看详细覆盖信息。</div>
          </section>
        </aside>
      </main>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '@/lib/apiClient'

const stores = ref([])
const employees = ref([])
const demandMap = ref({})
const ruleConfigMap = ref({})
const scheduleItems = ref([])
const anomalyItems = ref([])
const selectedStoreId = ref(null)
const weekStart = ref(getMonday(new Date()))
const weeklyPanelRef = ref(null)
const weeklyCalendarWrap = ref(null)
const selectedSlot = ref(null)
const selectedDayDate = ref('')
const selectedShiftKey = ref('')
const shiftEditorMode = ref('edit')
const creatingShiftDate = ref('')
const viewMode = ref('weekly')
const currentRole = ref('')
const isBootstrapping = ref(false)
const isScheduleLoading = ref(false)
const isGenerating = ref(false)
const isGeneratingAll = ref(false)
const isRepairing = ref(false)
const isSavingShift = ref(false)
const isDeletingShift = ref(false)
const errorMsg = ref('')
const successMsg = ref('')
const shiftEditor = ref({
  employeeId: null,
  startHour: null,
  endHour: null,
})

const selectedStore = computed(() => stores.value.find(store => store.id === Number(selectedStoreId.value)) || null)
const canUseSchedulingActions = computed(() => ['area_manager', 'store_manager'].includes(currentRole.value))
const canDownloadWeeklyView = computed(() => ['super_admin', 'admin', 'area_manager', 'store_manager'].includes(currentRole.value))
const showGenerateAllSchedules = computed(() => canUseSchedulingActions.value && stores.value.length > 1)
const showAnalysisPanels = computed(() => ['area_manager', 'store_manager'].includes(currentRole.value))
const showFocusPanel = computed(() => false)
const allowDailyView = computed(() => false)
const canEditShifts = computed(() => ['area_manager', 'store_manager'].includes(currentRole.value))
const selectedRuleConfig = computed(() => (selectedStore.value ? ruleConfigMap.value[selectedStore.value.id] || null : null))
const selectedDemand = computed(() => (selectedStore.value ? demandMap.value[selectedStore.value.id] || { items: [], profiles: [] } : { items: [], profiles: [] }))
const employeeMap = computed(() => Object.fromEntries(employees.value.map(employee => [employee.id, employee])))
const storeEmployees = computed(() => {
  if (!selectedStore.value) return []
  return [...employees.value]
    .filter(employee => (employee.store_settings || []).some(item => Number(item.store_id) === Number(selectedStore.value.id)))
    .sort((a, b) => a.name.localeCompare(b.name, 'zh-Hans-CN'))
})
const archetypeLabel = computed(() => String(selectedRuleConfig.value?.schedule_archetype || '自动识别'))
const businessHoursText = computed(() => `${selectedStore.value?.open_time || '--:--'} - ${selectedStore.value?.close_time || '--:--'}`)
const weekRangeLabel = computed(() => {
  if (!weekDays.value.length) return '--'
  return `${weekDays.value[0].displayDate} 至 ${weekDays.value[weekDays.value.length - 1].displayDate}`
})

const weekDays = computed(() => {
  const monday = new Date(`${weekStart.value}T00:00:00`)
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(monday)
    date.setDate(monday.getDate() + index)
    return {
      date: formatDate(date),
      displayDate: formatDisplayDate(date),
      weekdayLabel: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][index],
      dayOfWeek: index,
    }
  })
})

const hourSlots = computed(() => {
  if (!selectedStore.value) return []
  const { startHour, endHour } = buildHourBounds(selectedStore.value.open_time, selectedStore.value.close_time)
  return Array.from({ length: endHour - startHour + 1 }, (_, index) => {
    const hour = startHour + index
    return { hour, label: formatHour(hour), range: `${formatHour(hour)}-${formatHour(hour + 1)}` }
  })
})

const timelineMeta = computed(() => {
  if (!hourSlots.value.length) return { startHour: 0, totalHours: 1 }
  return {
    startHour: hourSlots.value[0].hour,
    totalHours: hourSlots.value.length,
  }
})

const timelineStyle = computed(() => ({
  '--slot-count': String(Math.max(hourSlots.value.length, 1)),
  '--timeline-label-width': '120px',
  '--timeline-track-gap': '12px',
  '--timeline-inner-padding': '14px',
}))

const scheduleLookup = computed(() => {
  const lookup = {}
  for (const item of scheduleItems.value) {
    if (!lookup[item.date]) lookup[item.date] = {}
    if (!lookup[item.date][item.hour]) lookup[item.date][item.hour] = []
    lookup[item.date][item.hour].push(Number(item.employee_id))
  }
  return lookup
})

const demandLookup = computed(() => {
  const result = {}
  const items = Array.isArray(selectedDemand.value.items) ? selectedDemand.value.items : []
  for (const item of items) {
    const day = Number(item.day_of_week)
    if (!result[day]) result[day] = {}
    result[day][Number(item.hour)] = Number(item.min_staff || 0)
  }
  if (Object.keys(result).length) return result
  const profiles = Array.isArray(selectedDemand.value.profiles) ? selectedDemand.value.profiles : []
  for (const profile of profiles) {
    const targetDays = profile.day_type === 'weekend' ? [5, 6] : [0, 1, 2, 3, 4]
    for (const day of targetDays) {
      if (!result[day]) result[day] = {}
      result[day][Number(profile.hour)] = Number(profile.min_staff || 0)
    }
  }
  return result
})

const anomalyLookup = computed(() => {
  const lookup = {}
  for (const item of anomalyItems.value) {
    lookup[`${item.date}-${item.hour}`] = item
  }
  return lookup
})

const dayBoards = computed(() => weekDays.value.map(day => buildDayBoard(day)))
const selectedDayBoard = computed(() => dayBoards.value.find(day => day.date === selectedDayDate.value) || dayBoards.value[0] || null)
const totalAssignedHours = computed(() => dayBoards.value.reduce((sum, day) => sum + day.assignedHours, 0))
const allShiftBars = computed(() => dayBoards.value.flatMap(day => day.shiftBars.map(bar => ({
  ...bar,
  date: day.date,
  dayLabel: day.displayDate,
  weekdayLabel: day.weekdayLabel,
  uniqueKey: `${day.date}-${bar.employee.id}-${bar.segmentKey}`,
}))))
const selectedShiftBar = computed(() => allShiftBars.value.find(item => item.uniqueKey === selectedShiftKey.value) || null)
const isCreatingShift = computed(() => shiftEditorMode.value === 'create' && !!creatingShiftDate.value)
const activeEditorDate = computed(() => isCreatingShift.value ? creatingShiftDate.value : (selectedShiftBar.value?.date || ''))

const alertCards = computed(() => anomalyItems.value.map(item => {
  const day = dayBoards.value.find(entry => entry.date === item.date)
  const slot = day?.slots.find(entry => entry.hour === item.hour)
  const primaryReason = item.reasons?.[0] || null
  return {
    key: `${item.date}-${item.hour}`,
    kind: item.kind,
    date: item.date,
    hour: item.hour,
    dayLabel: day?.displayDate || item.date,
    range: slot?.range || `${formatHour(item.hour)}-${formatHour(item.hour + 1)}`,
    message: item.kind === 'empty'
      ? `需求 ${item.required} 人，当前无人值班。`
      : `需求 ${item.required} 人，当前已排 ${item.assigned} 人。`,
    reasonText: primaryReason ? `${primaryReason.label}：${primaryReason.detail}` : '',
  }
}))

const anomalySummary = computed(() => ({
  total: alertCards.value.length,
  empty: alertCards.value.filter(item => item.kind === 'empty').length,
  shortage: alertCards.value.filter(item => item.kind === 'shortage').length,
}))

const selectedSlotDetail = computed(() => {
  if (!selectedSlot.value) return null
  const day = dayBoards.value.find(item => item.date === selectedSlot.value.date)
  const slot = day?.slots.find(item => item.hour === selectedSlot.value.hour)
  if (!slot || !day) return null
  return {
    dayLabel: day.displayDate,
    range: slot.range,
    required: slot.required,
    assigned: slot.assigned,
    statusText: slot.statusLabel,
    assignedNames: slot.names,
    reasons: anomalyLookup.value[`${day.date}-${slot.hour}`]?.reasons || [],
  }
})

const replacementCandidates = computed(() => {
  if (!selectedStore.value) return []
  if (isCreatingShift.value) {
    const date = creatingShiftDate.value
    const startHour = Number(shiftEditor.value.startHour)
    const endHour = Number(shiftEditor.value.endHour)
    if (!date || !Number.isFinite(startHour) || !Number.isFinite(endHour) || endHour <= startHour) return []
    return storeEmployees.value
      .map(employee => buildCoverageCandidate(employee, { date, startHour, endHour }))
      .filter(candidate => candidate.canCover)
      .sort((a, b) => a.sortScore - b.sortScore || a.employee.name.localeCompare(b.employee.name, 'zh-Hans-CN'))
  }
  const shift = selectedShiftBar.value
  if (!shift) return []
  return storeEmployees.value
    .filter(employee => employee.id !== shift.employee.id)
    .map(employee => buildCoverageCandidate(employee, {
      date: shift.date,
      startHour: shift.startHour,
      endHour: shift.endHour,
      excludedSegment: {
        employeeId: shift.employee.id,
        startHour: shift.startHour,
        endHour: shift.endHour,
      },
    }))
    .filter(candidate => candidate.canCover)
    .sort((a, b) => a.sortScore - b.sortScore || a.employee.name.localeCompare(b.employee.name, 'zh-Hans-CN'))
})

watch(selectedStoreId, () => {
  successMsg.value = ''
  selectedSlot.value = null
  closeShiftEditor()
})

watch([selectedStoreId, weekStart], async ([storeId]) => {
  if (!storeId) return
  await loadSchedule()
})

watch(dayBoards, boards => {
  if (!selectedDayDate.value || !boards.some(day => day.date === selectedDayDate.value)) {
    selectedDayDate.value = boards[0]?.date || ''
  }
}, { immediate: true })

watch(selectedShiftBar, shift => {
  if (isCreatingShift.value) return
  if (!shift) {
    shiftEditor.value = { employeeId: null, startHour: null, endHour: null }
    return
  }
  shiftEditor.value = {
    employeeId: shift.employee.id,
    startHour: shift.startHour,
    endHour: shift.endHour,
  }
}, { immediate: true })

watch(
  [isCreatingShift, creatingShiftDate, () => shiftEditor.value.startHour, () => shiftEditor.value.endHour, replacementCandidates],
  ([creating]) => {
    if (!creating) return
    const currentEmployeeId = Number(shiftEditor.value.employeeId)
    if (currentEmployeeId && replacementCandidates.value.some(candidate => candidate.employee.id === currentEmployeeId)) return
    shiftEditor.value = {
      ...shiftEditor.value,
      employeeId: replacementCandidates.value[0]?.employee.id ?? null,
    }
  },
)

onMounted(() => {
  loadBaseData()
  document.addEventListener('pointerdown', handleGlobalPointerDown, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', handleGlobalPointerDown, true)
})

function buildDayBoard(day) {
  const daySchedule = scheduleLookup.value[day.date] || {}
  const slots = hourSlots.value.map(slot => {
    const assignedIds = [...(daySchedule[slot.hour] || [])].sort((a, b) => a - b)
    const required = Number(demandLookup.value[day.dayOfWeek]?.[slot.hour] || 0)
    const assigned = assignedIds.length
    const status = assigned === 0 && required > 0 ? 'empty' : assigned < required ? 'shortage' : 'ok'
    const names = assignedIds.map(id => employeeMap.value[id]?.name || `#${id}`)
    return {
      ...slot,
      assignedIds,
      names,
      assigned,
      required,
      status,
      statusLabel: status === 'empty' ? '无人值班' : status === 'shortage' ? '人手不足' : '已覆盖',
    }
  })

  const employeeRows = storeEmployees.value.map(employee => {
    const hours = slots.filter(slot => slot.assignedIds.includes(employee.id)).map(slot => slot.hour)
    if (!hours.length) return null
    const segments = buildSegments(hours)
    return {
      employee,
      segments,
      segmentLabels: segments.map(segment => segment.label),
    }
  }).filter(Boolean)

  const shiftBars = employeeRows.flatMap(row => row.segments.map(segment => ({
    ...segment,
    employee: row.employee,
    variant: row.employee.employment_type === 'full_time' ? 'full-time' : 'part-time',
  }))).sort((a, b) => a.startHour - b.startHour || a.employee.name.localeCompare(b.employee.name, 'zh-Hans-CN'))

  const emptySlots = slots.filter(slot => slot.status === 'empty').length
  const shortageSlots = slots.filter(slot => slot.status === 'shortage').length
  return {
    ...day,
    slots,
    employeeRows,
    shiftBars,
    demandBands: buildDemandBands(slots),
    employeeCount: employeeRows.length,
    assignedHours: slots.reduce((sum, slot) => sum + slot.assigned, 0),
    peakDemand: Math.max(0, ...slots.map(slot => slot.required)),
    emptySlots,
    shortageSlots,
    hasCriticalAlert: emptySlots > 0 || shortageSlots > 0,
  }
}

function buildSegments(hours) {
  const sorted = [...hours].sort((a, b) => a - b)
  const segments = []
  let start = sorted[0]
  let previous = sorted[0]
  for (let index = 1; index <= sorted.length; index += 1) {
    const current = sorted[index]
    if (current === undefined || current !== previous + 1) {
      segments.push(buildTimelineSegment(start, previous + 1))
      start = current
    }
    previous = current
  }
  return segments
}

function buildTimelineSegment(startHour, endHour) {
  const totalHours = Math.max(1, timelineMeta.value.totalHours)
  const startOffset = startHour - timelineMeta.value.startHour
  const duration = Math.max(1, endHour - startHour)
  return {
    startHour,
    endHour,
    label: `${formatHour(startHour)}-${formatHour(endHour)}`,
    segmentKey: `${startHour}-${endHour}`,
    style: {
      left: `${(startOffset / totalHours) * 100}%`,
      width: `${(duration / totalHours) * 100}%`,
    },
  }
}

function buildDemandBands(slots) {
  const active = slots.filter(slot => slot.status !== 'ok')
  if (!active.length) return []
  const bands = []
  let start = active[0].hour
  let previous = active[0].hour
  let status = active[0].status
  for (let index = 1; index <= active.length; index += 1) {
    const current = active[index]
    if (!current || current.hour !== previous + 1 || current.status !== status) {
      bands.push({ ...buildTimelineSegment(start, previous + 1), status })
      start = current?.hour
      status = current?.status
    }
    previous = current?.hour ?? previous
  }
  return bands
}

function buildHourBounds(openTime, closeTime) {
  const [openHour, openMinute] = String(openTime || '09:00').split(':').map(Number)
  const [closeHour, closeMinute] = String(closeTime || '23:00').split(':').map(Number)
  const startHour = openHour + (openMinute > 0 ? 1 : 0)
  const endHour = closeHour - (closeMinute === 0 ? 1 : 0)
  return { startHour: Math.max(0, startHour), endHour: Math.max(startHour, endHour) }
}

function selectSlot(date, hour) {
  selectedSlot.value = { date, hour }
}

function openShiftEditor(date, bar) {
  if (!canEditShifts.value) return
  shiftEditorMode.value = 'edit'
  creatingShiftDate.value = ''
  selectedDayDate.value = date
  selectedSlot.value = { date, hour: bar.startHour }
  selectedShiftKey.value = `${date}-${bar.employee.id}-${bar.segmentKey}`
}

function openCreateShiftEditor(date, preferredHour = null) {
  if (!canEditShifts.value) return
  shiftEditorMode.value = 'create'
  creatingShiftDate.value = date
  selectedShiftKey.value = ''
  selectedDayDate.value = date

  const firstHour = hourSlots.value[0]?.hour ?? 9
  const lastHour = (hourSlots.value[hourSlots.value.length - 1]?.hour ?? firstHour) + 1
  const seedHour = Number.isFinite(preferredHour) ? Number(preferredHour) : (selectedSlot.value?.date === date ? Number(selectedSlot.value.hour) : firstHour)
  const startHour = Math.min(Math.max(seedHour, firstHour), Math.max(firstHour, lastHour - 1))
  const endHour = Math.min(startHour + 1, lastHour)

  selectedSlot.value = { date, hour: startHour }
  shiftEditor.value = {
    employeeId: null,
    startHour,
    endHour,
  }
}

function handleDayClick(date) {
  selectedDayDate.value = date
  if (allowDailyView.value) {
    viewMode.value = 'daily'
  }
}

function closeShiftEditor() {
  selectedShiftKey.value = ''
  shiftEditorMode.value = 'edit'
  creatingShiftDate.value = ''
  shiftEditor.value = { employeeId: null, startHour: null, endHour: null }
}

function handleGlobalPointerDown(event) {
  if (!selectedShiftKey.value) return
  const target = event.target
  if (!(target instanceof Element)) return
  if (target.closest('.inline-shift-panel')) return
  if (target.closest('.calendar-bar-row')) return
  if (target.closest('.lane-bar')) return
  if (target.closest('.shift-create-trigger')) return
  closeShiftEditor()
}

function buildCoverageCandidate(employee, { date, startHour, endHour, excludedSegment = null }) {
  const storeSetting = (employee.store_settings || []).find(item => Number(item.store_id) === Number(selectedStore.value?.id))
  const availabilityWindow = getAvailabilityWindowForDate(employee, date)
  const available = isRangeInsideWindow(availabilityWindow, startHour, endHour)
  const hasConflict = hasScheduleConflict(employee.id, date, startHour, endHour, excludedSegment)
  const priority = Number(storeSetting?.priority ?? 99)
  const assignedToday = scheduleItems.value.filter(item => item.date === date && Number(item.employee_id) === employee.id).length
  return {
    employee,
    canCover: available && !hasConflict,
    reasonText: !availabilityWindow
      ? '当天未配置可上班时段'
      : !available
        ? `可排 ${availabilityWindow.start_time}-${availabilityWindow.end_time}`
        : hasConflict
          ? '该时段已有其他排班'
          : `可完整覆盖 ${formatHour(startHour)}-${formatHour(endHour)}`,
    sortScore: priority * 100 + assignedToday,
  }
}

function getAvailabilityWindowForDate(employee, dateText) {
  const targetDate = new Date(`${dateText}T00:00:00`)
  const dayOfWeek = (targetDate.getDay() + 6) % 7
  const anchorText = employee.availability_anchor_monday || weekStart.value
  const anchorDate = new Date(`${anchorText}T00:00:00`)
  const diffWeeks = Math.round((targetDate.getTime() - anchorDate.getTime()) / (7 * 24 * 60 * 60 * 1000))
  const normalizedWeekOffset = ((diffWeeks % 2) + 2) % 2
  const availabilities = Array.isArray(employee.availabilities) ? employee.availabilities : []
  return availabilities.find(item => Number(item.day_of_week) === dayOfWeek && Number(item.week_offset) === normalizedWeekOffset) || null
}

function isRangeInsideWindow(window, startHour, endHour) {
  if (!window) return false
  const start = parseHourText(window.start_time)
  const end = parseHourText(window.end_time)
  return start <= startHour && end >= endHour
}

function parseHourText(value) {
  const [hours, minutes] = String(value || '00:00').split(':').map(Number)
  return hours + (minutes >= 30 ? 1 : 0)
}

function hasScheduleConflict(employeeId, dateText, startHour, endHour, excludedSegment = null) {
  const excludedHours = new Set()
  if (excludedSegment && Number(excludedSegment.employeeId) === Number(employeeId)) {
    for (let hour = excludedSegment.startHour; hour < excludedSegment.endHour; hour += 1) excludedHours.add(hour)
  }
  return scheduleItems.value.some(item => {
    if (Number(item.employee_id) !== Number(employeeId) || item.date !== dateText) return false
    const hour = Number(item.hour)
    if (excludedHours.has(hour)) return false
    return hour >= startHour && hour < endHour
  })
}

function setReplacementCandidate(employeeId) {
  shiftEditor.value = { ...shiftEditor.value, employeeId }
}

function dedupeScheduleItems(items) {
  const map = new Map()
  for (const item of items) {
    const normalized = { date: item.date, hour: Number(item.hour), employee_id: Number(item.employee_id) }
    map.set(`${normalized.date}-${normalized.hour}-${normalized.employee_id}`, normalized)
  }
  return [...map.values()].sort((a, b) => {
    if (a.date !== b.date) return a.date.localeCompare(b.date)
    if (a.hour !== b.hour) return a.hour - b.hour
    return a.employee_id - b.employee_id
  })
}

async function saveShiftEdit() {
  const shift = selectedShiftBar.value
  const isCreateMode = isCreatingShift.value
  const targetDate = isCreateMode ? creatingShiftDate.value : shift?.date
  if ((!isCreateMode && !shift) || !selectedStore.value || !targetDate) return
  const employeeId = Number(shiftEditor.value.employeeId)
  const startHour = Number(shiftEditor.value.startHour)
  const endHour = Number(shiftEditor.value.endHour)
  if (!employeeId || !Number.isFinite(startHour) || !Number.isFinite(endHour) || endHour <= startHour) {
    errorMsg.value = '请先选择有效的员工与开始/结束时间'
    return
  }

  const targetEmployee = employeeMap.value[employeeId]
  if (!targetEmployee) {
    errorMsg.value = '未找到要安排的员工'
    return
  }

  const canCover = isCreateMode
    ? buildCoverageCandidate(targetEmployee, { date: targetDate, startHour, endHour }).canCover
    : employeeId === shift.employee.id
      ? isRangeInsideWindow(getAvailabilityWindowForDate(targetEmployee, targetDate), startHour, endHour)
        && !hasScheduleConflict(employeeId, targetDate, startHour, endHour, {
          employeeId: shift.employee.id,
          startHour: shift.startHour,
          endHour: shift.endHour,
        })
      : buildCoverageCandidate(targetEmployee, {
        date: targetDate,
        startHour,
        endHour,
        excludedSegment: {
          employeeId: shift.employee.id,
          startHour: shift.startHour,
          endHour: shift.endHour,
        },
      }).canCover

  if (!canCover) {
    errorMsg.value = '当前员工无法完整覆盖这个时间段，请从候选人员中重新选择'
    return
  }

  const nextItems = isCreateMode
    ? [...scheduleItems.value]
    : scheduleItems.value.filter(item => {
      const sameDate = item.date === shift.date
      const sameEmployee = Number(item.employee_id) === Number(shift.employee.id)
      const hour = Number(item.hour)
      return !(sameDate && sameEmployee && hour >= shift.startHour && hour < shift.endHour)
    })

  for (let hour = startHour; hour < endHour; hour += 1) {
    nextItems.push({ date: targetDate, hour, employee_id: employeeId })
  }

  isSavingShift.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    const response = await api.saveSchedule({
      store_id: selectedStore.value.id,
      week_start: weekStart.value,
      items: dedupeScheduleItems(nextItems),
    })
    scheduleItems.value = response?.items || []
    anomalyItems.value = response?.anomalies || []
    successMsg.value = isCreateMode ? '新增排班已保存' : '班次调整已保存'
    selectedSlot.value = { date: targetDate, hour: startHour }
    if (isCreateMode) {
      closeShiftEditor()
    } else {
      selectedShiftKey.value = `${targetDate}-${employeeId}-${startHour}-${endHour}`
    }
  } catch (error) {
    errorMsg.value = `保存班次调整失败：${error.message}`
  } finally {
    isSavingShift.value = false
  }
}

async function deleteShiftEdit() {
  const shift = selectedShiftBar.value
  if (!shift || !selectedStore.value) return

  const nextItems = scheduleItems.value.filter(item => {
    const sameDate = item.date === shift.date
    const sameEmployee = Number(item.employee_id) === Number(shift.employee.id)
    const hour = Number(item.hour)
    return !(sameDate && sameEmployee && hour >= shift.startHour && hour < shift.endHour)
  })

  isDeletingShift.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    const response = await api.saveSchedule({
      store_id: selectedStore.value.id,
      week_start: weekStart.value,
      items: dedupeScheduleItems(nextItems),
    })
    scheduleItems.value = response?.items || []
    anomalyItems.value = response?.anomalies || []
    successMsg.value = '当前员工排班已删除'
    closeShiftEditor()
    syncSelectedSlot()
  } catch (error) {
    errorMsg.value = `删除排班失败：${error.message}`
  } finally {
    isDeletingShift.value = false
  }
}

async function loadBaseData() {
  isBootstrapping.value = true
  errorMsg.value = ''
  try {
    const [me, storeData, employeeData] = await Promise.all([api.getMe(), api.getStores(), api.getEmployees()])
    currentRole.value = me?.role || ''
    stores.value = storeData || []
    employees.value = employeeData || []
    const details = await Promise.all(stores.value.map(async store => {
      const [ruleConfig, staffingDemand] = await Promise.all([api.getStoreRuleConfig(store.id), api.getStoreStaffingDemand(store.id)])
      return { storeId: store.id, ruleConfig, staffingDemand }
    }))
    ruleConfigMap.value = Object.fromEntries(details.map(item => [item.storeId, item.ruleConfig]))
    demandMap.value = Object.fromEntries(details.map(item => [item.storeId, item.staffingDemand]))
    if (!selectedStoreId.value && stores.value.length) selectedStoreId.value = stores.value[0].id
    if (selectedStoreId.value) await loadSchedule()
  } catch (error) {
    errorMsg.value = `加载排班数据失败：${error.message}`
  } finally {
    isBootstrapping.value = false
  }
}

async function loadSchedule() {
  if (!selectedStoreId.value || !weekStart.value) return
  isScheduleLoading.value = true
  errorMsg.value = ''
  try {
    const data = await api.getSchedule(selectedStoreId.value, weekStart.value)
    scheduleItems.value = data?.items || []
    anomalyItems.value = data?.anomalies || []
    syncSelectedSlot()
  } catch (error) {
    scheduleItems.value = []
    anomalyItems.value = []
    errorMsg.value = `加载排班失败：${error.message}`
  } finally {
    isScheduleLoading.value = false
  }
}

async function generateSchedules() {
  if (!selectedStore.value) return
  isGenerating.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    const result = await api.generateAndSaveStoreSchedule({
      store_id: selectedStore.value.id,
      week_start: weekStart.value,
      algorithm: 'default_schedule',
      cycle_days: 7,
    })
    successMsg.value = result?.message || `已生成 ${selectedStore.value.name} 的周排班：${weekStart.value}`
    await loadSchedule()
  } catch (error) {
    errorMsg.value = `生成排班失败：${error.message}`
  } finally {
    isGenerating.value = false
  }
}

async function generateAllSchedules() {
  isGeneratingAll.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    const result = await api.generateAndSaveAllSchedules({ week_start: weekStart.value, algorithm: 'default_schedule', cycle_days: 7 })
    successMsg.value = result?.message || `已批量生成该周排班：${weekStart.value}`
    await loadSchedule()
  } catch (error) {
    errorMsg.value = `批量生成排班失败：${error.message}`
  } finally {
    isGeneratingAll.value = false
  }
}

async function repairAnomalies() {
  if (!selectedStore.value || !alertCards.value.length) return
  isRepairing.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    const result = await api.repairScheduleAnomalies({
      store_id: selectedStoreId.value,
      week_start: weekStart.value,
      algorithm: 'default_schedule',
      slots: alertCards.value.map(alert => ({ date: alert.date, hour: alert.hour })),
    })
    successMsg.value = result.unresolved_slots > 0
      ? `修复完成，仍有 ${result.unresolved_slots} 个时段未覆盖。`
      : '修复完成，目标异常时段已全部覆盖。'
    await loadSchedule()
  } catch (error) {
    errorMsg.value = `修复排班失败：${error.message}`
  } finally {
    isRepairing.value = false
  }
}

function syncSelectedSlot() {
  const firstAlert = alertCards.value[0]
  if (firstAlert) {
    selectedSlot.value = { date: firstAlert.date, hour: firstAlert.hour }
    selectedDayDate.value = firstAlert.date
    return
  }
  const firstDay = dayBoards.value[0]
  const firstSlot = firstDay?.slots[0]
  selectedSlot.value = firstDay && firstSlot ? { date: firstDay.date, hour: firstSlot.hour } : null
  selectedDayDate.value = firstDay?.date || ''
}

function shiftWeek(days) {
  const date = new Date(`${weekStart.value}T00:00:00`)
  date.setDate(date.getDate() + days)
  weekStart.value = getMonday(date)
}

function jumpToCurrentWeek() {
  weekStart.value = getMonday(new Date())
}

async function downloadWeeklyCalendar() {
  if (!selectedStore.value || !dayBoards.value.length || !weeklyPanelRef.value) return
  try {
    const target = weeklyPanelRef.value
    const rect = target.getBoundingClientRect()
    const cloned = cloneNodeWithComputedStyles(target)
    cloned.style.margin = '0'
    cloned.style.width = `${Math.ceil(rect.width)}px`
    cloned.style.height = `${Math.ceil(rect.height)}px`

    const heading = cloned.querySelector('.panel-head h2')
    if (heading) heading.textContent = selectedStore.value.name

    const serialized = new XMLSerializer().serializeToString(cloned)
    const escapedMarkup = serialized
      .replace(/#/g, '%23')
      .replace(/\n/g, '%0A')

    const svg = `
      <svg xmlns="http://www.w3.org/2000/svg" width="${Math.ceil(rect.width)}" height="${Math.ceil(rect.height)}">
        <foreignObject width="100%" height="100%">
          <div xmlns="http://www.w3.org/1999/xhtml" style="width:${Math.ceil(rect.width)}px;height:${Math.ceil(rect.height)}px;">
            ${escapedMarkup}
          </div>
        </foreignObject>
      </svg>
    `

    const image = new Image()
    const url = `data:image/svg+xml;charset=utf-8,${svg}`
    await new Promise((resolve, reject) => {
      image.onload = resolve
      image.onerror = reject
      image.src = url
    })

    const canvas = document.createElement('canvas')
    const scale = Math.max(window.devicePixelRatio || 1, 2)
    canvas.width = Math.ceil(rect.width * scale)
    canvas.height = Math.ceil(rect.height * scale)
    const context = canvas.getContext('2d')
    if (!context) throw new Error('无法创建导出画布')
    context.scale(scale, scale)
    context.drawImage(image, 0, 0, rect.width, rect.height)

    const pngUrl = canvas.toDataURL('image/png')
    const link = document.createElement('a')
    link.href = pngUrl
    link.download = `${selectedStore.value.name}-${weekStart.value}-周历排班.png`
    document.body.appendChild(link)
    link.click()
    link.remove()
  } catch (error) {
    errorMsg.value = `下载周历视图失败：${error.message || error}`
  }
}

function cloneNodeWithComputedStyles(sourceNode) {
  const clonedNode = sourceNode.cloneNode(false)
  if (sourceNode.nodeType !== Node.ELEMENT_NODE) return clonedNode

  const sourceElement = sourceNode
  const clonedElement = clonedNode
  const computedStyle = window.getComputedStyle(sourceElement)

  for (const propertyName of computedStyle) {
    clonedElement.style.setProperty(
      propertyName,
      computedStyle.getPropertyValue(propertyName),
      computedStyle.getPropertyPriority(propertyName),
    )
  }

  for (const childNode of sourceNode.childNodes) {
    clonedElement.appendChild(cloneNodeWithComputedStyles(childNode))
  }

  return clonedElement
}

function formatHour(hour) {
  return `${String(Number(hour) % 24).padStart(2, '0')}:00`
}

function formatDate(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatDisplayDate(date) {
  const weekdayNames = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  return `${date.getMonth() + 1}/${date.getDate()} ${weekdayNames[(date.getDay() + 6) % 7]}`
}

function getMonday(date) {
  const cloned = new Date(date)
  const day = cloned.getDay() || 7
  cloned.setHours(0, 0, 0, 0)
  cloned.setDate(cloned.getDate() - day + 1)
  return formatDate(cloned)
}

function employmentLabel(value) {
  if (value === 'full_time') return '全职'
  if (value === 'part_time') return '兼职'
  return value || '未知'
}
</script>

<style scoped>
.schedule-page { display: grid; gap: 18px; }
.hero-panel, .panel-shell, .metric-card, .alert-card, .employee-lane { border: 1px solid var(--color-border); background: rgba(255, 255, 255, 0.9); box-shadow: 0 18px 40px var(--theme-shadow); }
.hero-panel { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(300px, 0.78fr); gap: 18px; align-items: stretch; padding: 22px; border-radius: 28px; }
.schedule-hero { background:
  radial-gradient(circle at top right, rgba(244, 123, 76, 0.12), transparent 24%),
  linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(250, 243, 233, 0.96)); }
.hero-panel h1, .panel-head h2, .panel-head h3, .day-summary h3 { margin: 0; color: var(--color-heading); }
.hero-copy { margin-top: 10px; max-width: 72ch; color: var(--color-text-soft); }
.hero-main { display: grid; gap: 14px; }
.hero-highlights { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.hero-highlight { display: grid; gap: 4px; padding: 12px 14px; border-radius: 16px; background: rgba(255, 251, 245, 0.88); border: 1px solid rgba(244, 123, 76, 0.12); }
.hero-highlight small { color: var(--color-text-soft); font-size: 12px; }
.hero-highlight strong { color: var(--color-heading); font-size: 14px; }
.hero-actions, .action-row, .week-actions, .view-toggle, .chips-row { display: flex; gap: 10px; flex-wrap: wrap; }
.hero-actions, .action-row { justify-content: space-between; }
.hero-control-card { align-content: start; padding: 16px; border-radius: 22px; border: 1px solid rgba(244, 123, 76, 0.14); background: rgba(255, 251, 245, 0.84); box-shadow: inset 0 1px 0 rgba(255,255,255,0.7); }
.field { display: grid; gap: 6px; min-width: 180px; }
.field span { font-size: 12px; font-weight: 700; color: var(--color-text-soft); text-transform: uppercase; }
input, select { width: 100%; min-height: 42px; border: 1px solid var(--color-border); border-radius: 14px; padding: 0 12px; background: rgba(255, 251, 245, 0.92); }
.compact-field { flex: 1 1 180px; }
.notice { padding: 14px 16px; border-radius: 18px; font-weight: 600; }
.notice.error { background: rgba(253, 236, 233, 0.92); color: #933a2f; }
.notice.success { background: rgba(234, 248, 238, 0.92); color: #2f6d47; }
.control-strip { padding: 14px 16px; border-radius: 20px; background: rgba(255, 255, 255, 0.82); border: 1px solid rgba(221, 199, 174, 0.4); box-shadow: 0 14px 30px rgba(20, 35, 31, 0.05); }
.metrics-grid { display: grid; grid-template-columns: 1.4fr repeat(3, minmax(0, 1fr)); gap: 12px; }
.metric-card { padding: 18px; border-radius: 22px; }
.metric-card.feature { background: linear-gradient(145deg, rgba(255, 248, 239, 0.96), rgba(248, 233, 215, 0.92)); }
.metric-label { display: block; color: var(--color-text-soft); font-size: 13px; }
.metric-value { display: block; margin-top: 8px; font-size: 32px; color: var(--color-heading); }
.metric-value.small { font-size: 22px; }
.metric-card small { display: block; margin-top: 8px; color: var(--color-text-soft); }
.workspace-grid { display: grid; }
.main-stack { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(320px, 0.78fr); gap: 18px; align-items: start; }
.main-stack.full-width { grid-template-columns: minmax(0, 1fr); }
.panel-shell { padding: 18px; border-radius: 24px; }
.panel-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 14px; }
.inline-panel-head { margin-bottom: 12px; }
.panel-head p, .day-summary p, .alert-card p, .alert-card small, .detail-label { color: var(--color-text-soft); }
.weekly-calendar-wrap { overflow-x: auto; }
.weekly-calendar { min-width: 980px; display: grid; gap: 10px; }
.weekly-header, .calendar-row { display: grid; grid-template-columns: 160px minmax(0, 1fr); gap: 10px; align-items: start; }
.calendar-day-column, .calendar-row-body { display: grid; gap: 10px; }
.calendar-hours { display: grid; grid-template-columns: repeat(var(--slot-count, 1), minmax(0, 1fr)); gap: 0; padding-left: calc(var(--timeline-inner-padding) + var(--timeline-label-width) + var(--timeline-track-gap)); padding-right: var(--timeline-inner-padding); box-sizing: border-box; }
.calendar-hours span { display: flex; align-items: center; justify-content: center; min-height: 48px; border-left: 1px solid rgba(221, 199, 174, 0.35); background: rgba(248, 239, 228, 0.42); color: var(--color-heading); font-weight: 700; }
.calendar-hours span:last-child { border-right: 1px solid rgba(221, 199, 174, 0.35); }
.calendar-corner, .calendar-day-label { padding: 14px; border-radius: 18px; background: rgba(248, 239, 228, 0.72); color: var(--color-heading); text-align: left; }
.calendar-day-label { display: grid; gap: 4px; border: 1px solid transparent; }
.calendar-day-label.active { border-color: rgba(244, 123, 76, 0.35); }
.calendar-day-label.alert { background: rgba(253, 236, 233, 0.92); }
.calendar-day-label small { color: var(--color-text-soft); }
.day-create-trigger { width: 100%; justify-content: center; }
.calendar-slots { position: relative; display: grid; gap: 10px; padding: 14px; border-radius: 20px; background: rgba(255, 255, 255, 0.78); border: 1px solid rgba(221, 199, 174, 0.35); overflow: hidden; }
.inline-shift-panel { padding: 16px; border-radius: 20px; background: rgba(255, 251, 245, 0.96); border: 1px solid rgba(221, 199, 174, 0.35); }
.calendar-track-grid, .lane-track-grid { position: absolute; inset: 0; display: grid; grid-template-columns: repeat(var(--slot-count, 1), minmax(0, 1fr)); pointer-events: none; }
.calendar-slots > .calendar-track-grid, .calendar-slots > .track-bands { top: var(--timeline-inner-padding); bottom: var(--timeline-inner-padding); left: calc(var(--timeline-inner-padding) + var(--timeline-label-width) + var(--timeline-track-gap)); right: var(--timeline-inner-padding); }
.calendar-track-grid span, .lane-track-grid span { border-left: 1px solid rgba(221, 199, 174, 0.28); }
.calendar-track-grid span:first-child, .lane-track-grid span:first-child { border-left: none; }
.track-bands { position: absolute; inset: 0; pointer-events: none; }
.track-band { position: absolute; top: 0; bottom: 0; opacity: 0.42; }
.track-band.shortage { background: rgba(235, 184, 82, 0.16); }
.track-band.empty { background: rgba(203, 87, 78, 0.16); }
.calendar-bar-row { position: relative; z-index: 1; display: grid; grid-template-columns: var(--timeline-label-width) minmax(0, 1fr); gap: var(--timeline-track-gap); align-items: center; text-align: left; background: transparent; padding: 0; border: none; }
.calendar-bar-row.active .calendar-bar-track { outline: 2px solid rgba(244, 123, 76, 0.28); }
.calendar-bar-meta { display: grid; gap: 2px; }
.calendar-bar-meta small { color: var(--color-text-soft); }
.calendar-bar-track, .lane-track { position: relative; min-height: 42px; border-radius: 14px; background: rgba(248, 239, 228, 0.42); }
.calendar-bar-fill, .lane-bar { position: absolute; top: 5px; bottom: 5px; display: inline-flex; align-items: center; padding: 0 12px; border-radius: 12px; color: #fff; background: linear-gradient(135deg, #f47b4c, #ef9f5a); box-shadow: 0 10px 22px rgba(244, 123, 76, 0.22); overflow: hidden; white-space: nowrap; }
.calendar-bar-fill.full-time, .lane-bar.full-time { background: linear-gradient(135deg, #f47b4c, #ef9f5a); }
.calendar-bar-fill.part-time, .lane-bar.part-time { background: linear-gradient(135deg, #4e8f76, #68b090); }
.calendar-bar-fill strong, .lane-bar strong { overflow: hidden; text-overflow: ellipsis; }
.lane-bar.active { outline: 2px solid rgba(244, 123, 76, 0.28); }
.timeline-empty { position: relative; z-index: 1; padding: 10px 12px; border-radius: 14px; color: var(--color-text-soft); background: rgba(248, 239, 228, 0.56); }
.day-layout, .employee-lanes, .alert-list, .slot-detail, .shift-editor, .candidate-list { display: grid; gap: 12px; }
.hour-table-wrap { overflow: auto; }
.hour-table { width: 100%; min-width: 720px; border-collapse: collapse; }
.hour-table th, .hour-table td { padding: 10px 8px; border-bottom: 1px solid var(--color-border); text-align: left; }
.hour-table tbody tr { cursor: pointer; }
.status-dot { display: inline-block; width: 10px; height: 10px; border-radius: 999px; margin-right: 8px; background: rgba(35, 62, 54, 0.12); }
.status-dot.ok { background: rgba(76, 151, 107, 0.8); }
.status-dot.shortage { background: rgba(235, 184, 82, 0.9); }
.status-dot.empty { background: rgba(203, 87, 78, 0.9); }
.employee-lane { position: relative; padding: 14px; border-radius: 18px; background: rgba(255, 255, 255, 0.82); border: 1px solid rgba(221, 199, 174, 0.32); overflow: hidden; }
.lane-head { display: flex; justify-content: space-between; gap: 10px; }
.lane-head span { color: var(--color-text-soft); font-size: 13px; }
.lane-track-grid { top: 54px; bottom: 14px; left: 14px; right: 14px; }
.lane-track { margin-top: 12px; min-height: 52px; }
.lane-bar { border: none; text-align: left; }
.soft-tag { display: inline-flex; align-items: center; min-height: 28px; padding: 0 10px; border-radius: 999px; background: rgba(244, 123, 76, 0.1); color: var(--color-primary-dark); font-size: 12px; font-weight: 700; }
.alert-card { display: grid; gap: 6px; text-align: left; padding: 14px; border-radius: 18px; cursor: pointer; }
.alert-card.empty { background: rgba(253, 236, 233, 0.92); }
.alert-card.shortage { background: rgba(255, 244, 220, 0.92); }
.slot-detail .detail-row, .shift-editor .detail-row { display: flex; justify-content: space-between; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--color-border); }
.slot-detail .detail-row span, .shift-editor .detail-row span { color: var(--color-text-soft); }
.editor-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.editor-actions { display: flex; justify-content: flex-end; gap: 10px; }
.danger-btn { color: #9a302c; border-color: rgba(203, 87, 78, 0.28); background: rgba(253, 236, 233, 0.92); }
.shift-create-trigger { white-space: nowrap; }
.candidate-card { display: grid; gap: 4px; text-align: left; padding: 12px 14px; border-radius: 16px; border: 1px solid rgba(244, 123, 76, 0.18); background: rgba(255, 251, 245, 0.92); }
.candidate-card span, .candidate-card small { color: var(--color-text-soft); }
.name-list { margin: 8px 0 0; padding-left: 18px; }
.empty-block { padding: 14px; border-radius: 14px; background: rgba(248, 239, 228, 0.6); color: var(--color-text-soft); }
.switch-btn { min-height: 40px; border-radius: 12px; border: 1px solid var(--color-border); padding: 0 14px; background: rgba(255, 251, 245, 0.92); color: var(--color-heading); font-weight: 700; }
.switch-btn.active { background: rgba(244, 123, 76, 0.12); color: var(--color-primary-dark); border-color: rgba(244, 123, 76, 0.28); }
.alert-tag { background: rgba(203, 87, 78, 0.16); color: #8c312e; }
.warning-tag { background: rgba(235, 184, 82, 0.2); color: #89570b; }
@media (max-width: 1180px) { .metrics-grid, .main-stack, .hero-panel, .hero-highlights { grid-template-columns: 1fr; } }
@media (max-width: 768px) {
  .action-row, .hero-actions, .panel-head, .lane-head { flex-direction: column; align-items: stretch; }
  .metric-value { font-size: 28px; }
  .metric-value.small { font-size: 20px; }
  .weekly-calendar { --timeline-label-width: 88px; }
  .weekly-header, .calendar-row { grid-template-columns: 120px minmax(680px, 1fr); }
  .editor-grid { grid-template-columns: 1fr; }
}
</style>
