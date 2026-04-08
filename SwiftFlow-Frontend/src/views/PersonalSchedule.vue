<template>
  <div class="personal-page">
    <section class="hero-panel personal-hero">
      <div class="hero-intro">
        <p class="eyebrow clean-eyebrow">员工自助</p>
        <h1 class="clean-title">查看我的排班，并维护个人可上班时间</h1>
        <p class="hero-copy clean-copy">
          这里会展示你本周实际参与的门店和对应整周排班。你也可以直接维护本周、下周的可上班时间，方便店长和区域经理后续排班。
        </p>
        <p class="eyebrow">员工自助</p>
        <h1>查看我的排班，并维护个人可上班时间</h1>
        <p class="hero-copy">
          这里会展示你本周实际参与的门店和对应整周排班。你也可以直接维护本周、下周的可上班时间，方便店长和区域经理排班。
        </p>
      </div>
      <div class="hero-actions">
        <div class="week-info-card">
          <span class="week-info-label">周起始日</span>
          <strong class="week-info-value">{{ weekStart }}</strong>
          <small>固定显示当前查看周的周一</small>
        </div>
        <label class="field compact-field">
          <span>周起始日</span>
          <input :value="weekStart" type="date" disabled />
        </label>
        <button class="ghost-btn" :disabled="isLoading" @click="loadPage">{{ isLoading ? '刷新中...' : '刷新数据' }}</button>
      </div>
    </section>

    <div v-if="message" class="status-banner" :class="{ error: isError }">{{ message }}</div>

    <section class="summary-grid">
      <article class="metric-card accent">
        <span class="metric-label">我的姓名</span>
        <strong class="metric-value small">{{ employee?.name || '--' }}</strong>
        <small>{{ employmentLabel(employee?.employment_type) }}</small>
      </article>
      <article class="metric-card">
        <span class="metric-label">本周参与门店</span>
        <strong class="metric-value">{{ myStores.length }}</strong>
        <small>仅展示本周被安排上班的门店</small>
      </article>
      <article class="metric-card">
        <span class="metric-label">本周总工时</span>
        <strong class="metric-value">{{ totalAssignedHours }}</strong>
        <small>按当前已生成排班统计</small>
      </article>
      <article class="metric-card">
        <span class="metric-label">当前查看门店</span>
        <strong class="metric-value small">{{ selectedStore?.name || '未选择' }}</strong>
        <small>{{ selectedStore ? `${selectedStore.open_time} - ${selectedStore.close_time}` : '请先选择门店' }}</small>
      </article>
    </section>

    <section class="workspace-grid">
      <aside class="panel-shell store-panel">
        <div class="panel-head stacked">
          <div>
            <h2>本周参与门店</h2>
            <p>只显示你本周实际参与工作的门店。点击后可查看该门店整周排班。</p>
          </div>
        </div>

        <div class="store-list">
          <button
            v-for="store in myStores"
            :key="store.id"
            class="store-card"
            :class="{ active: store.id === selectedStoreId }"
            @click="selectedStoreId = store.id"
          >
            <div class="store-card-top">
              <strong>{{ store.name }}</strong>
              <span class="soft-tag">{{ store.assigned_hours }}h</span>
            </div>
            <p>{{ store.open_time }} - {{ store.close_time }}</p>
          </button>
          <div v-if="!myStores.length" class="empty-block">本周还没有安排到任何门店。</div>
        </div>
      </aside>

      <main class="content-stack">
        <section class="panel-shell">
          <div class="panel-head">
            <div>
              <h2>我的可上班时间</h2>
              <p>维护本周和下周的可上班时间，供后续排班使用。</p>
            </div>
            <button class="primary-btn" :disabled="isSavingAvailability || !employee" @click="saveAvailability">
              {{ isSavingAvailability ? '保存中...' : '保存可排时间' }}
            </button>
          </div>

          <div class="availability-panels">
            <article v-for="weekOffset in [0, 1]" :key="weekOffset" class="availability-card">
              <div class="availability-card-head">
                <h3>{{ weekOffset === 0 ? '本周' : '下周' }}</h3>
                <span>{{ weekOffset === 0 ? '当前自然周' : '下一自然周' }}</span>
              </div>

              <div class="availability-list">
                <div v-for="day in weekDays" :key="`${weekOffset}-${day.dayOfWeek}`" class="availability-row">
                  <button class="day-meta day-meta-button" type="button" @click="markDayAvailable(weekOffset, day.dayOfWeek)">
                    <strong>{{ day.weekdayLabel }}</strong>
                    <small>{{ offsetDateLabel(day.date, weekOffset) }}</small>
                  </button>
                  <label class="time-field">
                    <span>开始</span>
                    <input v-model="availabilityDraft[weekOffset][day.dayOfWeek].start_time" type="time" />
                  </label>
                  <label class="time-field">
                    <span>结束</span>
                    <input v-model="availabilityDraft[weekOffset][day.dayOfWeek].end_time" type="time" />
                  </label>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section class="panel-shell">
          <div class="panel-head">
            <div>
              <h2>门店整周排班</h2>
              <p>这里展示你当前选中门店的整周排班，帮助你了解同店同周的整体安排。</p>
            </div>
            <span class="soft-tag">{{ weekRangeLabel }}</span>
          </div>

          <div v-if="selectedStore" class="week-board">
            <div class="week-header">
              <div class="name-col">员工 / 日期</div>
              <div v-for="day in weekDays" :key="day.date" class="day-col-head">
                <strong>{{ day.weekdayLabel }}</strong>
                <small>{{ day.displayDate }}</small>
              </div>
            </div>

            <div v-for="row in scheduleRows" :key="row.employee.id" class="week-row" :class="{ mine: row.employee.id === employee?.id }">
              <div class="name-col">
                <strong>{{ row.employee.name }}</strong>
                <small>{{ employmentLabel(row.employee.employment_type) }}</small>
              </div>
              <div v-for="day in row.days" :key="`${row.employee.id}-${day.date}`" class="day-cell">
                <div class="time-track">
                  <span v-for="segment in day.segments" :key="segment.key" class="shift-bar" :style="segment.style">
                    {{ segment.label }}
                  </span>
                </div>
              </div>
            </div>

            <div v-if="!scheduleRows.length" class="empty-block">当前门店本周还没有排班数据。</div>
          </div>
          <div v-else class="empty-block">请先从左侧选择一个本周参与的门店。</div>
        </section>
      </main>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '@/lib/apiClient'

const employee = ref(null)
const myStores = ref([])
const visibleEmployees = ref([])
const scheduleItems = ref([])
const selectedStoreId = ref(null)
const weekStart = ref(getMonday(new Date()))
const isLoading = ref(false)
const isSavingAvailability = ref(false)
const message = ref('')
const isError = ref(false)

const availabilityDraft = reactive({
  0: createEmptyWeekAvailability(),
  1: createEmptyWeekAvailability()
})

const selectedStore = computed(() => myStores.value.find(item => item.id === Number(selectedStoreId.value)) || null)
const weekDays = computed(() => {
  const monday = new Date(`${weekStart.value}T00:00:00`)
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(monday)
    date.setDate(monday.getDate() + index)
    return {
      date: formatDate(date),
      displayDate: formatDisplayDate(date),
      weekdayLabel: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][index],
      dayOfWeek: index
    }
  })
})

const weekRangeLabel = computed(() => {
  if (!weekDays.value.length) return '--'
  return `${weekDays.value[0].displayDate} 至 ${weekDays.value[weekDays.value.length - 1].displayDate}`
})

const totalAssignedHours = computed(() => myStores.value.reduce((sum, item) => sum + Number(item.assigned_hours || 0), 0))

const scheduleRows = computed(() => {
  const employeeMap = Object.fromEntries(visibleEmployees.value.map(item => [item.id, item]))
  const grouped = {}
  for (const item of scheduleItems.value) {
    const employeeId = Number(item.employee_id)
    const date = item.date
    grouped[employeeId] ||= {}
    grouped[employeeId][date] ||= []
    grouped[employeeId][date].push(Number(item.hour))
  }

  return Object.keys(grouped)
    .map(key => {
      const employeeId = Number(key)
      const employeeInfo = employeeMap[employeeId] || {
        id: employeeId,
        name: `员工 ${employeeId}`,
        employment_type: 'part_time'
      }
      return {
        employee: employeeInfo,
        days: weekDays.value.map(day => ({
          date: day.date,
          segments: buildSegments(grouped[employeeId][day.date] || [])
        }))
      }
    })
    .sort((a, b) => {
      if (a.employee.id === employee.value?.id) return -1
      if (b.employee.id === employee.value?.id) return 1
      return a.employee.name.localeCompare(b.employee.name, 'zh-Hans-CN')
    })
})

function setMessage(text, error = false) {
  message.value = text
  isError.value = error
}

function createEmptyWeekAvailability(isFullTime = false) {
  return Array.from({ length: 7 }, () => ({
    start_time: isFullTime ? '00:00' : '',
    end_time: isFullTime ? '23:59' : ''
  }))
}

function normalizeAvailabilityDraft(availabilities = [], employmentType = 'part_time') {
  const isFullTime = employmentType === 'full_time'
  const draft = {
    0: createEmptyWeekAvailability(isFullTime),
    1: createEmptyWeekAvailability(isFullTime)
  }
  for (const item of availabilities) {
    const weekOffset = Number(item.week_offset || 0)
    const dayOfWeek = Number(item.day_of_week || 0)
    if (!draft[weekOffset] || !draft[weekOffset][dayOfWeek]) continue
    draft[weekOffset][dayOfWeek] = {
      start_time: item.start_time || '',
      end_time: item.end_time || ''
    }
  }
  availabilityDraft[0] = draft[0]
  availabilityDraft[1] = draft[1]
}

function markDayAvailable(weekOffset, dayOfWeek) {
  if (!availabilityDraft[weekOffset]?.[dayOfWeek]) return
  const current = availabilityDraft[weekOffset][dayOfWeek]
  const isFullDay = current.start_time === '00:00' && current.end_time === '23:59'
  if (isFullDay) {
    current.start_time = ''
    current.end_time = ''
    return
  }
  current.start_time = '00:00'
  current.end_time = '23:59'
}

async function loadPage() {
  isLoading.value = true
  setMessage('')
  try {
    const [employeeData, storeData] = await Promise.all([
      api.getMyEmployeeProfile(),
      api.getMyScheduleStores(weekStart.value)
    ])
    employee.value = employeeData
    myStores.value = storeData || []
    normalizeAvailabilityDraft(employeeData?.availabilities || [], employeeData?.employment_type || 'part_time')

    if (!selectedStoreId.value || !myStores.value.some(item => item.id === selectedStoreId.value)) {
      selectedStoreId.value = myStores.value[0]?.id ?? null
    }
    if (selectedStoreId.value) {
      await loadSelectedStoreSchedule()
    } else {
      visibleEmployees.value = []
      scheduleItems.value = []
    }
  } catch (error) {
    setMessage(error.message || '加载个人排班信息失败', true)
  } finally {
    isLoading.value = false
  }
}

async function loadSelectedStoreSchedule() {
  if (!selectedStoreId.value) return
  try {
    const [scheduleData, employeeData] = await Promise.all([
      api.getSchedule(selectedStoreId.value, weekStart.value),
      api.getMyStoreEmployees(selectedStoreId.value, weekStart.value)
    ])
    scheduleItems.value = scheduleData?.items || []
    visibleEmployees.value = employeeData || []
  } catch (error) {
    setMessage(error.message || '加载门店整周排班失败', true)
  }
}

async function saveAvailability() {
  if (!employee.value) return
  isSavingAvailability.value = true
  setMessage('')
  try {
    const availabilities = []
    for (const weekOffset of [0, 1]) {
      availabilityDraft[weekOffset].forEach((item, dayOfWeek) => {
        if (!item.start_time || !item.end_time) return
        availabilities.push({
          week_offset: weekOffset,
          day_of_week: dayOfWeek,
          start_time: item.start_time,
          end_time: item.end_time
        })
      })
    }
    const employeeData = await api.updateMyAvailability({ availabilities })
    employee.value = employeeData
      normalizeAvailabilityDraft(employeeData?.availabilities || [], employeeData?.employment_type || 'part_time')
    setMessage('个人可排时间已保存。')
  } catch (error) {
    setMessage(error.message || '保存个人可排时间失败', true)
  } finally {
    isSavingAvailability.value = false
  }
}

function buildSegments(hours) {
  if (!hours.length) return []
  const sorted = [...hours].sort((a, b) => a - b)
  const segments = []
  let start = sorted[0]
  let prev = sorted[0]

  for (let index = 1; index < sorted.length; index += 1) {
    const hour = sorted[index]
    if (hour === prev + 1) {
      prev = hour
      continue
    }
    segments.push(buildSegment(start, prev + 1))
    start = hour
    prev = hour
  }
  segments.push(buildSegment(start, prev + 1))
  return segments
}

function buildSegment(startHour, endHour) {
  return {
    key: `${startHour}-${endHour}`,
    label: `${formatHour(startHour)}-${formatHour(endHour)}`,
    style: {
      left: `${(startHour / 24) * 100}%`,
      width: `${((endHour - startHour) / 24) * 100}%`
    }
  }
}

function employmentLabel(value) {
  return value === 'full_time' ? '全职' : value === 'part_time' ? '兼职' : value || '--'
}

function getMonday(date) {
  const value = new Date(date)
  const day = value.getDay()
  const delta = day === 0 ? -6 : 1 - day
  value.setDate(value.getDate() + delta)
  return formatDate(value)
}

function formatDate(date) {
  const value = new Date(date)
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatDisplayDate(date) {
  return new Intl.DateTimeFormat('zh-SG', { month: 'numeric', day: 'numeric' }).format(new Date(date))
}

function offsetDateLabel(baseDate, weekOffset) {
  const date = new Date(`${baseDate}T00:00:00`)
  date.setDate(date.getDate() + weekOffset * 7)
  return formatDisplayDate(date)
}

function formatHour(hour) {
  const normalized = ((Number(hour) % 24) + 24) % 24
  return `${String(normalized).padStart(2, '0')}:00`
}

watch(selectedStoreId, loadSelectedStoreSchedule)

onMounted(loadPage)
</script>

<style scoped>
.personal-page {
  display: grid;
  gap: 20px;
}

.personal-hero {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
  padding: 24px 26px;
}

.hero-intro {
  min-width: 0;
  display: grid;
  gap: 10px;
  padding-right: 10px;
}

.hero-intro > .eyebrow:not(.clean-eyebrow),
.hero-intro > h1:not(.clean-title),
.hero-intro > .hero-copy:not(.clean-copy) {
  display: none !important;
}

.clean-title {
  margin: 0;
  font-size: clamp(28px, 4vw, 40px);
  color: var(--color-heading);
}

.hero-copy {
  max-width: 780px;
  color: var(--color-text-soft);
  line-height: 1.7;
}

.hero-actions {
  display: grid;
  gap: 12px;
  flex-wrap: wrap;
  justify-items: stretch;
  min-width: 240px;
  align-self: stretch;
  padding-left: 8px;
}

.hero-actions .field.compact-field,
.hero-actions .compact-field {
  display: none !important;
}

.week-info-card {
  display: grid;
  gap: 4px;
  padding: 16px 18px;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255, 251, 245, 0.96), rgba(248, 239, 228, 0.82));
  border: 1px solid rgba(230, 207, 176, 0.82);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

.week-info-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-text-soft);
}

.week-info-value {
  font-size: 18px;
  font-weight: 800;
  color: var(--color-heading);
}

.week-info-card small {
  color: var(--color-text-soft);
  line-height: 1.4;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.workspace-grid {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 18px;
}

.content-stack {
  display: grid;
  gap: 18px;
}

.panel-shell,
.metric-card {
  padding: 18px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(230, 207, 176, 0.82);
  box-shadow: 0 18px 34px rgba(170, 135, 94, 0.08);
}

.metric-card.accent {
  background: linear-gradient(135deg, rgba(255, 173, 96, 0.16), rgba(255, 255, 255, 0.94));
}

.metric-label {
  display: block;
  color: var(--color-text-soft);
  font-size: 13px;
}

.metric-value {
  display: block;
  margin-top: 8px;
  font-size: 32px;
}

.metric-value.small {
  font-size: 24px;
}

.metric-card small {
  display: block;
  margin-top: 6px;
  color: var(--color-text-soft);
}

.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.panel-head.stacked {
  flex-direction: column;
}

.panel-head h2,
.availability-card-head h3 {
  margin: 0;
}

.panel-head p {
  margin: 6px 0 0;
  color: var(--color-text-soft);
  line-height: 1.6;
}

.store-list {
  display: grid;
  gap: 12px;
}

.store-card {
  padding: 14px;
  border-radius: 18px;
  border: 1px solid rgba(226, 205, 176, 0.88);
  background: rgba(255, 251, 247, 0.94);
  text-align: left;
}

.store-card.active {
  border-color: rgba(238, 117, 52, 0.45);
  background: linear-gradient(180deg, rgba(255, 241, 230, 0.96), rgba(255, 255, 255, 0.96));
}

.store-card-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.store-card p {
  margin: 6px 0 0;
  color: var(--color-text-soft);
}

.availability-panels {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.availability-card {
  padding: 16px;
  border-radius: 20px;
  background: rgba(255, 252, 248, 0.92);
  border: 1px solid rgba(232, 211, 183, 0.86);
}

.availability-card-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
  margin-bottom: 12px;
}

.availability-card-head span {
  color: var(--color-text-soft);
  font-size: 13px;
}

.availability-list {
  display: grid;
  gap: 10px;
}

.availability-row {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr) minmax(0, 1fr);
  gap: 10px;
  align-items: end;
}

.day-meta small,
.time-field span {
  color: var(--color-text-soft);
  font-size: 12px;
}

.day-meta strong {
  display: block;
}

.day-meta-button {
  border: 1px solid rgba(229, 207, 179, 0.82);
  border-radius: 14px;
  padding: 10px 12px;
  background: rgba(255, 252, 248, 0.92);
  text-align: left;
  cursor: pointer;
}

.time-field {
  display: grid;
  gap: 6px;
}

.time-field input,
.field input {
  width: 100%;
  border: 1px solid rgba(221, 199, 166, 0.95);
  border-radius: 14px;
  padding: 12px 14px;
  background: rgba(255, 252, 248, 0.92);
  color: var(--color-text);
}

.field.compact-field {
  display: none;
  gap: 6px;
}

.field.compact-field span {
  color: var(--color-text-soft);
  font-size: 12px;
}

.week-board {
  display: grid;
  gap: 10px;
  overflow-x: auto;
}

.week-header,
.week-row {
  display: grid;
  grid-template-columns: 140px repeat(7, minmax(150px, 1fr));
  gap: 10px;
  min-width: 1240px;
}

.name-col,
.day-col-head,
.day-cell {
  padding: 12px;
  border-radius: 16px;
  background: rgba(255, 252, 248, 0.9);
  border: 1px solid rgba(229, 207, 179, 0.82);
}

.week-row.mine .name-col,
.week-row.mine .day-cell {
  background: rgba(255, 239, 223, 0.94);
  border-color: rgba(238, 117, 52, 0.32);
}

.day-col-head {
  display: grid;
  gap: 4px;
}

.name-col small,
.day-col-head small {
  color: var(--color-text-soft);
}

.time-track {
  position: relative;
  min-height: 42px;
  border-radius: 14px;
  background:
    repeating-linear-gradient(
      90deg,
      rgba(220, 199, 172, 0.24) 0,
      rgba(220, 199, 172, 0.24) calc(100% / 24 - 1px),
      transparent calc(100% / 24 - 1px),
      transparent calc(100% / 24)
    ),
    rgba(255, 255, 255, 0.84);
}

.shift-bar {
  position: absolute;
  top: 7px;
  height: 28px;
  border-radius: 10px;
  background: linear-gradient(135deg, #f58649, #df6e32);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding: 0 8px;
}

.soft-tag {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(238, 117, 52, 0.12);
  color: var(--color-primary-dark);
  font-size: 12px;
  font-weight: 700;
}

.status-banner {
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(35, 106, 71, 0.1);
  color: #1f5c42;
}

.status-banner.error {
  background: rgba(200, 68, 68, 0.12);
  color: #8f2f2f;
}

.empty-block {
  padding: 18px;
  border-radius: 16px;
  background: rgba(255, 250, 244, 0.94);
  color: var(--color-text-soft);
  text-align: center;
}

@media (max-width: 1080px) {
  .personal-hero,
  .panel-head {
    flex-direction: column;
  }

  .summary-grid,
  .workspace-grid,
  .availability-panels {
    grid-template-columns: 1fr;
  }
}
</style>
