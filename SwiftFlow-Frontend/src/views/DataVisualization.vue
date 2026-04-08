<template>
  <div class="viz-page">
    <header class="hero">
      <div>
        <p class="eyebrow">Database Visualization</p>
        <h1>运营数据展示面板</h1>
        <p class="subtitle">基于现有门店、员工、关系、规则和需求数据生成的可视化展示页。</p>
      </div>
      <button class="refresh-btn" :disabled="isLoading" @click="loadData">
        {{ isLoading ? '加载中...' : '刷新数据' }}
      </button>
    </header>

    <div v-if="errorMsg" class="error">{{ errorMsg }}</div>

    <section class="stats-grid">
      <article class="stat-card">
        <span class="stat-label">门店数</span>
        <strong class="stat-value">{{ stores.length }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">员工数</span>
        <strong class="stat-value">{{ employees.length }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">员工店铺授权</span>
        <strong class="stat-value">{{ storeAssignments }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">持钥匙授权</span>
        <strong class="stat-value">{{ keyHolderAssignments }}</strong>
      </article>
      <article class="stat-card accent">
        <span class="stat-label">员工关系记录</span>
        <strong class="stat-value">{{ relations.length }}</strong>
      </article>
    </section>

    <section class="panel">
      <div class="section-head">
        <div>
          <p class="section-kicker">Entity Map</p>
          <h2>数据结构概览</h2>
        </div>
      </div>

      <div class="schema-flow">
        <article class="schema-card">
          <span class="schema-tag">实体</span>
          <h3>Stores</h3>
          <p>{{ stores.length }} 条记录</p>
          <ul>
            <li>基础字段：名称、营业时间</li>
            <li>驱动规则与需求配置</li>
          </ul>
        </article>
        <article class="schema-card bridge">
          <span class="schema-tag">关联</span>
          <h3>EmployeeStoreAccess</h3>
          <p>{{ storeAssignments }} 条授权</p>
          <ul>
            <li>优先级 priority</li>
            <li>持钥匙 has_key</li>
          </ul>
        </article>
        <article class="schema-card">
          <span class="schema-tag">实体</span>
          <h3>Employees</h3>
          <p>{{ employees.length }} 条记录</p>
          <ul>
            <li>雇佣类型、国籍、工时</li>
            <li>技能与可用时间窗口</li>
          </ul>
        </article>
        <article class="schema-card">
          <span class="schema-tag">规则</span>
          <h3>Rule Config</h3>
          <p>{{ configuredStores }} 家门店已配置</p>
          <ul>
            <li>平日/周末总工时上限</li>
            <li>80h / 160h 目标参数</li>
          </ul>
        </article>
        <article class="schema-card">
          <span class="schema-tag">需求</span>
          <h3>Staffing Demand</h3>
          <p>{{ demandProfilesCount }} 组需求画像</p>
          <ul>
            <li>按小时最少人数</li>
            <li>支持 weekday / weekend</li>
          </ul>
        </article>
        <article class="schema-card bridge danger">
          <span class="schema-tag">关系</span>
          <h3>EmployeeRelation</h3>
          <p>{{ relations.length }} 条约束</p>
          <ul>
            <li>当前主要用于 bad relation</li>
            <li>严重度 severity</li>
          </ul>
        </article>
      </div>
    </section>

    <section class="panel">
      <div class="section-head">
        <div>
          <p class="section-kicker">Store Demand</p>
          <h2>门店需求热力图</h2>
        </div>
      </div>

      <div class="store-grid">
        <article v-for="store in storePanels" :key="store.id" class="store-card">
          <div class="store-header">
            <div>
              <h3>{{ store.name }}</h3>
              <p>{{ store.open_time }} - {{ store.close_time }}</p>
            </div>
            <div class="store-meta">
              <span>{{ store.employeeCount }} 名员工</span>
              <span>{{ store.keyHolderCount }} 名持钥匙</span>
            </div>
          </div>

          <div class="rule-badges">
            <span class="badge">工作日上限 {{ formatNumber(store.rule.weekday_total_hours_limit) }}h</span>
            <span class="badge">周末上限 {{ formatNumber(store.rule.weekend_total_hours_limit) }}h</span>
            <span class="badge">PT 保底 {{ formatNumber(store.rule.sg_part_time_min_hours) }}h</span>
          </div>

          <div class="heatmap">
            <div class="heatmap-row">
              <span class="row-label">Weekday</span>
              <div class="cells">
                <div
                  v-for="cell in store.weekdayProfile"
                  :key="`wd-${store.id}-${cell.hour}`"
                  class="heat-cell"
                  :style="{ '--level': cell.level }"
                >
                  <span class="hour">{{ cell.hour }}</span>
                  <strong>{{ cell.value }}</strong>
                </div>
              </div>
            </div>
            <div class="heatmap-row">
              <span class="row-label">Weekend</span>
              <div class="cells">
                <div
                  v-for="cell in store.weekendProfile"
                  :key="`we-${store.id}-${cell.hour}`"
                  class="heat-cell weekend"
                  :style="{ '--level': cell.level }"
                >
                  <span class="hour">{{ cell.hour }}</span>
                  <strong>{{ cell.value }}</strong>
                </div>
              </div>
            </div>
          </div>

          <div class="peak-line">
            高峰时段：{{ store.peakHours.length ? store.peakHours.join(' / ') : '暂无' }}
          </div>
        </article>
      </div>
    </section>

    <section class="panel">
      <div class="section-head">
        <div>
          <p class="section-kicker">Access Matrix</p>
          <h2>员工与店铺授权矩阵</h2>
        </div>
      </div>

      <div class="matrix-wrap">
        <table class="matrix">
          <thead>
            <tr>
              <th>员工</th>
              <th>类型</th>
              <th v-for="store in stores" :key="`head-${store.id}`">{{ store.name }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in employeeRows" :key="row.id">
              <td>{{ row.name }}</td>
              <td>{{ row.employment_type }}</td>
              <td v-for="store in stores" :key="`${row.id}-${store.id}`">
                <span v-if="row.storeMap[store.id]" class="pill" :class="{ key: row.storeMap[store.id].has_key }">
                  P{{ row.storeMap[store.id].priority ?? '-' }}{{ row.storeMap[store.id].has_key ? ' / KEY' : '' }}
                </span>
                <span v-else class="empty-mark">-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <div class="section-head">
        <div>
          <p class="section-kicker">Relation Watch</p>
          <h2>员工关系约束</h2>
        </div>
      </div>

      <div v-if="relations.length" class="relation-list">
        <article v-for="relation in relationCards" :key="relation.key" class="relation-card">
          <div>
            <h3>{{ relation.left }} × {{ relation.right }}</h3>
            <p>{{ relation.type }}</p>
          </div>
          <strong>{{ relation.severityLabel }}</strong>
        </article>
      </div>
      <div v-else class="empty-state">当前没有员工关系约束。</div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '@/lib/apiClient'

const stores = ref([])
const employees = ref([])
const relations = ref([])
const ruleConfigMap = ref({})
const demandMap = ref({})
const isLoading = ref(false)
const errorMsg = ref('')

const storeAssignments = computed(() =>
  employees.value.reduce((total, employee) => total + (employee.store_settings?.length || 0), 0)
)

const keyHolderAssignments = computed(() =>
  employees.value.reduce(
    (total, employee) => total + (employee.store_settings || []).filter(item => item.has_key).length,
    0,
  )
)

const configuredStores = computed(() =>
  stores.value.filter(store => ruleConfigMap.value[store.id]).length
)

const demandProfilesCount = computed(() =>
  stores.value.reduce((total, store) => {
    const response = demandMap.value[store.id]
    return total + ((response?.profiles?.length || 0) ? 1 : 0)
  }, 0)
)

const employeeMap = computed(() =>
  Object.fromEntries(employees.value.map(employee => [employee.id, employee]))
)

const relationCards = computed(() =>
  relations.value.map(item => {
    const left = employeeMap.value[item.employee_id_a]?.name || `#${item.employee_id_a}`
    const right = employeeMap.value[item.employee_id_b]?.name || `#${item.employee_id_b}`
    return {
      key: `${item.employee_id_a}-${item.employee_id_b}`,
      left,
      right,
      type: item.relation_type,
      severityLabel: `severity ${Number(item.severity || 0).toFixed(2)}`,
    }
  })
)

const employeeRows = computed(() =>
  [...employees.value]
    .sort((a, b) => a.name.localeCompare(b.name, 'zh-Hans-CN'))
    .map(employee => ({
      ...employee,
      storeMap: Object.fromEntries((employee.store_settings || []).map(item => [item.store_id, item])),
    }))
)

const storePanels = computed(() =>
  stores.value.map(store => {
    const rule = ruleConfigMap.value[store.id] || {}
    const demandResponse = demandMap.value[store.id] || { profiles: [], items: [] }
    const weekdayProfile = buildProfile(demandResponse, 'weekday')
    const weekendProfile = buildProfile(demandResponse, 'weekend')
    return {
      ...store,
      rule: {
        weekday_total_hours_limit: Number(rule.weekday_total_hours_limit || 0),
        weekend_total_hours_limit: Number(rule.weekend_total_hours_limit || 0),
        sg_part_time_min_hours: Number(rule.sg_part_time_min_hours || 0),
      },
      employeeCount: employees.value.filter(employee =>
        (employee.store_settings || []).some(item => item.store_id === store.id)
      ).length,
      keyHolderCount: employees.value.filter(employee =>
        (employee.store_settings || []).some(item => item.store_id === store.id && item.has_key)
      ).length,
      weekdayProfile,
      weekendProfile,
      peakHours: buildPeakHours(weekdayProfile, weekendProfile),
    }
  })
)

function normalizeType(value) {
  return value === 'full_time' ? '全职' : value === 'part_time' ? '兼职' : value
}

function buildProfile(response, dayType) {
  const profileRows = response?.profiles?.filter(item => item.day_type === dayType) || []
  const fallbackRows = (response?.items || []).filter(item => {
    if (dayType === 'weekday') {
      return item.day_type === 'weekday' || [0, 1, 2, 3, 4].includes(item.day_of_week)
    }
    return item.day_type === 'weekend' || [5, 6].includes(item.day_of_week)
  })

  const sourceRows = profileRows.length ? profileRows : fallbackRows
  const maxValue = Math.max(1, ...sourceRows.map(item => Number(item.min_staff || 0)))

  return sourceRows
    .slice()
    .sort((a, b) => Number(a.hour) - Number(b.hour))
    .map(item => ({
      hour: `${String(item.hour).padStart(2, '0')}:00`,
      value: Number(item.min_staff || 0),
      level: Number(item.min_staff || 0) / maxValue,
    }))
}

function buildPeakHours(weekdayProfile, weekendProfile) {
  const merged = [...weekdayProfile, ...weekendProfile]
  const maxValue = Math.max(0, ...merged.map(item => item.value))
  return merged.filter(item => item.value === maxValue).map(item => item.hour)
}

function formatNumber(value) {
  return Number(value || 0).toFixed(value % 1 === 0 ? 0 : 1)
}

async function loadData() {
  isLoading.value = true
  errorMsg.value = ''
  try {
    const [storeData, employeeData, relationData] = await Promise.all([
      api.getStores(),
      api.getEmployees(),
      api.getEmployeeRelations(),
    ])

    stores.value = storeData || []
    employees.value = (employeeData || []).map(item => ({
      ...item,
      employment_type: normalizeType(item.employment_type),
    }))
    relations.value = relationData || []

    const storeDetails = await Promise.all(
      stores.value.map(async store => {
        const [ruleConfig, staffingDemand] = await Promise.all([
          api.getStoreRuleConfig(store.id),
          api.getStoreStaffingDemand(store.id),
        ])
        return {
          storeId: store.id,
          ruleConfig,
          staffingDemand,
        }
      })
    )

    ruleConfigMap.value = Object.fromEntries(storeDetails.map(item => [item.storeId, item.ruleConfig]))
    demandMap.value = Object.fromEntries(storeDetails.map(item => [item.storeId, item.staffingDemand]))
  } catch (error) {
    errorMsg.value = `加载可视化数据失败：${error.message}`
  } finally {
    isLoading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.viz-page {
  min-height: 100vh;
  padding: clamp(16px, 2vw, 28px);
  background:
    radial-gradient(circle at top left, rgba(242, 138, 76, 0.18), transparent 28%),
    linear-gradient(150deg, var(--color-background), var(--color-background-mute));
}

.hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.eyebrow,
.section-kicker {
  margin: 0 0 6px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--color-primary-dark);
}

.hero h1,
.section-head h2 {
  margin: 0;
  font-size: clamp(24px, 3vw, 34px);
  color: var(--color-heading);
}

.subtitle {
  margin: 8px 0 0;
  max-width: 720px;
  color: var(--color-text-soft);
}

.refresh-btn {
  border: none;
  border-radius: 999px;
  padding: 12px 18px;
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-dark));
  color: #fff;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 8px 20px rgba(230, 106, 50, 0.28);
}

.refresh-btn:disabled {
  opacity: 0.7;
  cursor: wait;
}

.error,
.empty-state {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--color-danger-border);
  background: var(--color-danger-bg);
  color: var(--color-danger-text);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.stat-card,
.panel {
  background: rgba(255, 252, 247, 0.9);
  border: 1px solid rgba(210, 186, 168, 0.6);
  border-radius: 22px;
  box-shadow: 0 14px 32px rgba(81, 48, 28, 0.08);
  backdrop-filter: blur(14px);
}

.stat-card {
  padding: 18px;
}

.stat-card.accent {
  background: linear-gradient(145deg, rgba(248, 233, 221, 0.98), rgba(255, 246, 236, 0.98));
}

.stat-label {
  display: block;
  font-size: 13px;
  color: var(--color-text-soft);
}

.stat-value {
  display: block;
  margin-top: 10px;
  font-size: 36px;
  line-height: 1;
  color: var(--color-heading);
}

.panel {
  padding: 20px;
  margin-bottom: 18px;
}

.section-head {
  margin-bottom: 16px;
}

.schema-flow {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.schema-card {
  position: relative;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid rgba(214, 192, 173, 0.8);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.86), rgba(249, 240, 232, 0.86));
}

.schema-card.bridge {
  background: linear-gradient(180deg, rgba(252, 244, 228, 0.95), rgba(248, 233, 208, 0.95));
}

.schema-card.danger {
  background: linear-gradient(180deg, rgba(255, 243, 239, 0.95), rgba(255, 231, 224, 0.95));
}

.schema-tag {
  display: inline-flex;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  background: rgba(81, 48, 28, 0.08);
  color: var(--color-primary-dark);
}

.schema-card h3,
.store-card h3,
.relation-card h3 {
  margin: 10px 0 6px;
}

.schema-card p,
.store-card p,
.relation-card p,
.peak-line {
  margin: 0;
  color: var(--color-text-soft);
}

.schema-card ul {
  margin: 12px 0 0;
  padding-left: 18px;
  color: var(--color-text-soft);
}

.store-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.store-card {
  padding: 18px;
  border-radius: 18px;
  border: 1px solid rgba(214, 192, 173, 0.8);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(246, 237, 230, 0.88));
}

.store-header,
.store-meta,
.rule-badges,
.heatmap-row {
  display: flex;
  gap: 10px;
}

.store-header,
.heatmap-row {
  justify-content: space-between;
}

.store-meta {
  flex-direction: column;
  align-items: flex-end;
  color: var(--color-text-soft);
  font-size: 13px;
}

.rule-badges {
  flex-wrap: wrap;
  margin: 14px 0;
}

.badge {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(230, 106, 50, 0.1);
  color: var(--color-primary-dark);
  font-size: 12px;
  font-weight: 700;
}

.heatmap {
  display: grid;
  gap: 10px;
}

.row-label {
  width: 74px;
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
  color: var(--color-text-soft);
  padding-top: 10px;
}

.cells {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(46px, 1fr));
  gap: 6px;
}

.heat-cell {
  padding: 8px 6px;
  border-radius: 12px;
  text-align: center;
  background: rgba(230, 106, 50, calc(0.12 + var(--level) * 0.58));
  color: #5e2f12;
}

.heat-cell.weekend {
  background: rgba(158, 93, 55, calc(0.12 + var(--level) * 0.48));
  color: #fff7f0;
}

.heat-cell .hour {
  display: block;
  font-size: 10px;
  opacity: 0.85;
}

.heat-cell strong {
  font-size: 18px;
}

.peak-line {
  margin-top: 12px;
  font-size: 13px;
}

.matrix-wrap {
  overflow-x: auto;
}

.matrix {
  width: 100%;
  border-collapse: collapse;
  min-width: 760px;
}

.matrix th,
.matrix td {
  padding: 12px 10px;
  border-bottom: 1px solid rgba(214, 192, 173, 0.6);
  text-align: left;
}

.matrix th {
  color: var(--color-text-soft);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.pill {
  display: inline-flex;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(81, 48, 28, 0.08);
  color: var(--color-heading);
  font-size: 12px;
  font-weight: 700;
}

.pill.key {
  background: rgba(230, 106, 50, 0.16);
  color: var(--color-primary-dark);
}

.empty-mark {
  color: var(--color-text-soft);
}

.relation-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.relation-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(214, 192, 173, 0.8);
  background: linear-gradient(180deg, rgba(255, 249, 247, 0.95), rgba(255, 239, 233, 0.95));
}

@media (max-width: 1180px) {
  .stats-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .schema-flow,
  .store-grid,
  .relation-list {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .viz-page {
    padding: 12px;
  }

  .hero {
    flex-direction: column;
  }

  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .store-header,
  .heatmap-row {
    flex-direction: column;
  }

  .store-meta {
    align-items: flex-start;
  }

  .row-label {
    width: auto;
    padding-top: 0;
  }
}

@media (max-width: 520px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
