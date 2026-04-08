<template>
  <div class="home-page">
    <section class="hero-panel dashboard-hero">
      <div class="hero-copy">
        <p class="eyebrow">{{ hero.eyebrow }}</p>
        <h1>{{ hero.title }}</h1>
        <p>{{ hero.description }}</p>
      </div>

      <div class="hero-side">
        <article class="role-card">
          <span class="role-label">当前角色</span>
          <strong>{{ roleLabel }}</strong>
          <p>{{ roleSummary }}</p>
        </article>

        <div class="hero-actions">
          <RouterLink
            v-for="action in heroActions"
            :key="action.to"
            class="ghost-btn"
            :to="action.to"
          >
            {{ action.label }}
          </RouterLink>
          <button class="primary-btn" :disabled="isLoading" @click="loadData">
            {{ isLoading ? '刷新中...' : '刷新工作台' }}
          </button>
        </div>
      </div>
    </section>

    <div v-if="errorMsg" class="notice error">{{ errorMsg }}</div>

    <section class="overview-grid">
      <article v-for="card in overviewCards" :key="card.label" class="metric-card">
        <span class="metric-label">{{ card.label }}</span>
        <strong class="metric-value">{{ card.value }}</strong>
        <small>{{ card.hint }}</small>
      </article>
    </section>

    <section class="permission-strip">
      <article class="permission-card">
        <p class="section-kicker">可见功能</p>
        <div class="chip-row">
          <span v-for="item in visibilityItems" :key="item" class="soft-chip">{{ item }}</span>
        </div>
      </article>

      <article class="permission-card">
        <p class="section-kicker">可执行操作</p>
        <div class="chip-row">
          <span v-for="item in capabilityItems" :key="item" class="soft-chip accent">{{ item }}</span>
        </div>
      </article>
    </section>

    <section class="content-grid">
      <article class="panel-shell main-panel">
        <div class="section-head">
          <div>
            <p class="section-kicker">{{ primarySection.kicker }}</p>
            <h2>{{ primarySection.title }}</h2>
          </div>
          <span class="section-note">{{ primarySection.note }}</span>
        </div>

        <div class="spotlight-grid">
          <article v-for="item in primarySection.items" :key="item.title" class="spotlight-card">
            <div class="spotlight-top">
              <strong>{{ item.title }}</strong>
              <span v-if="item.badge" class="soft-chip">{{ item.badge }}</span>
            </div>
            <p>{{ item.description }}</p>
            <small>{{ item.meta }}</small>
          </article>
        </div>
      </article>

      <article class="panel-shell side-panel">
        <div class="section-head compact">
          <div>
            <p class="section-kicker">{{ sideSection.kicker }}</p>
            <h2>{{ sideSection.title }}</h2>
          </div>
        </div>

        <div class="focus-list">
          <article v-for="item in sideSection.items" :key="item.title" class="focus-card">
            <div class="focus-top">
              <strong>{{ item.title }}</strong>
              <span v-if="item.badge" class="mini-badge">{{ item.badge }}</span>
            </div>
            <p>{{ item.description }}</p>
            <small>{{ item.meta }}</small>
          </article>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '@/lib/apiClient'

const summary = ref({})
const stores = ref([])
const employees = ref([])
const ruleConfigMap = ref({})
const demandMap = ref({})
const isLoading = ref(false)
const errorMsg = ref('')

const currentRole = computed(() => summary.value.role || '')
const isAdmin = computed(() => ['super_admin', 'admin'].includes(currentRole.value))
const isAreaManager = computed(() => currentRole.value === 'area_manager')
const isStoreManager = computed(() => currentRole.value === 'store_manager')

const roleLabel = computed(() => {
  if (isAdmin.value) return '系统管理员'
  if (isAreaManager.value) return '区域经理'
  if (isStoreManager.value) return '店长'
  return '运营成员'
})

const roleSummary = computed(() => {
  if (isAdmin.value) return '负责系统级主数据、区域结构与角色配置。'
  if (isAreaManager.value) return '负责所属区域的门店排班、员工管理与店长协作。'
  if (isStoreManager.value) return '负责本门店的排班执行、员工安排、规则与人力需求维护。'
  return '查看当前职责范围内的门店与员工信息。'
})

const fullTimeCount = computed(() => employees.value.filter(item => item.employment_type === 'full_time').length)
const partTimeCount = computed(() => employees.value.filter(item => item.employment_type === 'part_time').length)
const openingReadyCount = computed(() =>
  employees.value.filter(employee =>
    hasAnySkill(employee, ['front_service', 'cashier', 'floor', 'customer_service']) &&
    hasAnySkill(employee, ['backroom', 'inventory']),
  ).length,
)
const backroomCapableCount = computed(() =>
  employees.value.filter(employee => hasAnySkill(employee, ['backroom', 'inventory'])).length,
)
const keyHolderAssignments = computed(() =>
  employees.value.reduce(
    (total, employee) => total + (employee.store_settings || []).filter(item => item.has_key).length,
    0,
  ),
)
const assignedAreaStoreCount = computed(() => stores.value.filter(store => Number(store.area_id || 0) > 0).length)
const unassignedAreaStoreCount = computed(() => stores.value.filter(store => !Number(store.area_id || 0)).length)

const storePanels = computed(() =>
  stores.value.map(store => {
    const rule = ruleConfigMap.value[store.id] || {}
    const demandResponse = demandMap.value[store.id] || { profiles: [], items: [] }
    const weekdayProfile = buildProfile(demandResponse, 'weekday')
    const weekendProfile = buildProfile(demandResponse, 'weekend')
    const employeeCount = employees.value.filter(employee =>
      (employee.store_settings || []).some(item => item.store_id === store.id),
    ).length
    const keyHolderCount = employees.value.filter(employee =>
      (employee.store_settings || []).some(item => item.store_id === store.id && item.has_key),
    ).length

    return {
      id: store.id,
      name: store.name,
      open_time: store.open_time,
      close_time: store.close_time,
      employeeCount,
      keyHolderCount,
      weekdayPeakLabel: buildPeakLabel(weekdayProfile),
      weekendPeakLabel: buildPeakLabel(weekendProfile),
      minBackroomLabel: Number(rule.min_backroom_per_hour || 0) > 0 ? `${Number(rule.min_backroom_per_hour)} 人/小时` : '未设置',
      weekdayHours: Number(rule.weekday_total_hours_limit || 0),
      weekendHours: Number(rule.weekend_total_hours_limit || 0),
    }
  }),
)

const hero = computed(() => {
  if (isAdmin.value) {
    return {
      eyebrow: 'Admin Workspace',
      title: '查看系统级主数据与权限结构',
      description: '聚焦区域归属、门店主数据与组织角色设置，帮助你从治理视角掌握系统整体状态。',
    }
  }
  if (isAreaManager.value) {
    return {
      eyebrow: 'Area Operations',
      title: '掌握区域内门店、人力与排班准备度',
      description: '优先展示你负责区域内的门店数量、员工结构和重点执行入口，方便快速进入区域管理。',
    }
  }
  return {
    eyebrow: 'Store Operations',
    title: '查看门店执行状态并进入排班处理',
    description: '聚焦当前负责门店的人员安排、后场覆盖与当周排班执行，帮助快速进入日常运营操作。',
  }
})

const heroActions = computed(() => {
  if (isAdmin.value) {
    return [
      { label: '查看店铺管理', to: '/stores' },
      { label: '查看员工管理', to: '/employees' },
    ]
  }
  if (isAreaManager.value) {
    return [
      { label: '进入排班中心', to: '/shift-schedule' },
      { label: '查看员工管理', to: '/employees' },
      { label: '查看店铺管理', to: '/stores' },
    ]
  }
  return [
    { label: '进入排班中心', to: '/shift-schedule' },
    { label: '查看员工管理', to: '/employees' },
  ]
})

const overviewCards = computed(() => {
  if (isAdmin.value) {
    return [
      { label: '系统门店数', value: stores.value.length, hint: '当前纳入系统管理的全部门店' },
      { label: '在册员工数', value: employees.value.length, hint: '员工档案总数' },
      { label: '已分配区域门店', value: assignedAreaStoreCount.value, hint: '已明确区域归属的门店' },
      { label: '未分配区域门店', value: unassignedAreaStoreCount.value, hint: '仍待归类到区域的门店' },
    ]
  }
  if (isAreaManager.value) {
    return [
      { label: '区域门店数', value: summary.value.managed_stores || stores.value.length, hint: '当前负责的门店数量' },
      { label: '区域员工数', value: summary.value.managed_employees || employees.value.length, hint: '所属区域内员工总数' },
      { label: '可开店员工', value: openingReadyCount.value, hint: '同时具备前后场能力的员工' },
      { label: '后场覆盖员工', value: backroomCapableCount.value, hint: '具备后场或库存能力的员工' },
    ]
  }
  return [
    { label: '负责门店数', value: summary.value.managed_stores || stores.value.length, hint: '当前负责的门店数量' },
    { label: '本店员工数', value: summary.value.managed_employees || employees.value.length, hint: '当前可管理的员工总数' },
    { label: '钥匙授权数', value: keyHolderAssignments.value, hint: '员工与门店之间的钥匙权限配置' },
    { label: '全职 / 兼职', value: `${fullTimeCount.value} / ${partTimeCount.value}`, hint: '当前门店的人力结构' },
  ]
})

const visibilityItems = computed(() => {
  if (isAdmin.value) return ['全部门店主数据', '全部员工档案', '区域结构', '角色与账号信息']
  if (isAreaManager.value) return ['所属区域门店', '区域排班信息', '区域员工档案', '区域店长信息']
  return ['负责门店信息', '本店排班', '本店员工档案', '本店规则与需求']
})

const capabilityItems = computed(() => {
  if (isAdmin.value) return ['调整区域归属', '维护门店主数据', '配置角色权限', '查看系统整体状态']
  if (isAreaManager.value) return ['编辑区域排班', '生成区域门店排班', '编辑员工资料', '分配区域内店长']
  return ['编辑本店排班', '生成本店排班', '编辑员工资料', '维护规则与人力需求']
})

const primarySection = computed(() => {
  if (isAdmin.value) {
    return {
      kicker: '治理重点',
      title: '系统级主数据与结构状态',
      note: '聚焦系统治理、区域结构与主数据完整度。',
      items: [
        {
          title: '区域归属完整度',
          badge: `${assignedAreaStoreCount.value}/${stores.value.length || 0}`,
          description: '优先检查门店是否已归属到对应区域，保证区域经理的管理范围清晰稳定。',
          meta: `未分配区域门店 ${unassignedAreaStoreCount.value} 家`,
        },
        {
          title: '账号与角色结构',
          badge: `${employees.value.length} 人`,
          description: '从员工与账号的对应关系出发，确认区域经理、店长和员工角色配置是否清晰。',
          meta: '角色调整与账号分配建议从员工管理入口完成。',
        },
        {
          title: '门店主数据',
          badge: `${stores.value.length} 家门店`,
          description: '检查门店名称、所属区域与营业时间是否完整，保证后续配置与使用稳定。',
          meta: '门店名称、区域与营业时间是当前主要维护内容。',
        },
      ],
    }
  }
  if (isAreaManager.value) {
    return {
      kicker: '区域门店',
      title: '你负责区域内的门店状态',
      note: '重点关注人力覆盖、营业时段与排班准备度。',
      items: storePanels.value.slice(0, 6).map(store => ({
        title: store.name,
        badge: `${store.employeeCount} 人`,
        description: `${store.open_time} - ${store.close_time} · 后场要求 ${store.minBackroomLabel}`,
        meta: `工作日高峰 ${store.weekdayPeakLabel} · 周末高峰 ${store.weekendPeakLabel}`,
      })),
    }
  }
  return {
    kicker: '门店执行',
    title: '当前负责门店的执行视图',
    note: '重点查看本店安排、关键覆盖与排班入口。',
    items: storePanels.value.slice(0, 4).map(store => ({
      title: store.name,
      badge: `${store.keyHolderCount} 位持钥匙`,
      description: `${store.open_time} - ${store.close_time} · ${store.employeeCount} 名员工`,
      meta: `工作日上限 ${formatNumber(store.weekdayHours)}h · 周末上限 ${formatNumber(store.weekendHours)}h`,
    })),
  }
})

const sideSection = computed(() => {
  if (isAdmin.value) {
    return {
      kicker: 'Admin 关注点',
      title: '建议优先处理',
      items: [
        {
          title: '未分配区域门店',
          badge: `${unassignedAreaStoreCount.value} 家`,
          description: '这部分门店建议优先补齐区域归属，便于后续区域化管理。',
          meta: '可前往店铺管理中的区域看板处理。',
        },
        {
          title: '员工结构总览',
          badge: `${fullTimeCount.value}/${partTimeCount.value}`,
          description: '快速了解系统内全职与兼职比例，确认新员工是否进入正确管理流程。',
          meta: `开店能力 ${openingReadyCount.value} 人 · 后场覆盖 ${backroomCapableCount.value} 人`,
        },
        {
          title: '常用入口',
          description: '通过员工管理和店铺管理持续维护组织结构与主数据完整度。',
          meta: '推荐入口：员工管理、店铺管理。',
        },
      ],
    }
  }
  if (isAreaManager.value) {
    return {
      kicker: '区域执行重点',
      title: '优先关注的人力信号',
      items: [
        {
          title: '区域可开店员工',
          badge: `${openingReadyCount.value} 人`,
          description: '确认早班所需的前后场双技能人员是否足够覆盖区域内高峰门店。',
          meta: '可在员工管理中继续核对门店归属与可排时间。',
        },
        {
          title: '区域后场覆盖',
          badge: `${backroomCapableCount.value} 人`,
          description: '后场或库存能力直接影响开店和收尾安排，应优先关注覆盖不足的门店。',
          meta: '重点检查钥匙权限与后场技能是否过度集中在少数员工。',
        },
        {
          title: '执行入口',
          description: '可以直接进入排班中心、员工管理与店铺管理处理区域内实际问题。',
          meta: '排班生成与编辑范围会按当前负责区域收口。',
        },
      ],
    }
  }
  return {
    kicker: '店长执行重点',
    title: '本店今日与本周优先项',
    items: [
      {
        title: '门店排班入口',
        badge: `${summary.value.managed_stores || stores.value.length} 家`,
        description: '优先进入排班中心查看周历、重点异常和班次调整。',
        meta: '如负责多家门店，可在排班中心逐店处理。',
      },
      {
        title: '员工可排时间',
        badge: `${employees.value.length} 人`,
        description: '可查看并编辑员工可排班时间，减少因沟通遗漏导致的排班冲突。',
        meta: '建议结合员工技能和门店授权一并检查。',
      },
      {
        title: '规则与人力需求',
        description: '持续维护本店排班规则与人力需求，用于支撑后续算法生成。',
        meta: '建议先核对营业时间、需求峰值与收尾能力覆盖。',
      },
    ],
  }
})

function buildProfile(response, dayType) {
  const profileRows = response?.profiles?.filter(item => item.day_type === dayType) || []
  const fallbackRows = (response?.items || []).filter(item => {
    if (dayType === 'weekday') return item.day_type === 'weekday' || [0, 1, 2, 3, 4].includes(item.day_of_week)
    return item.day_type === 'weekend' || [5, 6].includes(item.day_of_week)
  })
  const sourceRows = profileRows.length ? profileRows : fallbackRows
  return sourceRows
    .slice()
    .sort((a, b) => Number(a.hour) - Number(b.hour))
    .map(item => ({
      hour: `${String(item.hour).padStart(2, '0')}:00`,
      value: Number(item.min_staff || 0),
    }))
}

function buildPeakLabel(profile) {
  if (!profile.length) return '暂无数据'
  const maxValue = Math.max(...profile.map(item => item.value))
  return profile.filter(item => item.value === maxValue).map(item => item.hour).join(' / ')
}

function hasAnySkill(employee, codes) {
  const skillMap = Object.fromEntries(
    (employee.skills || []).map(skill => [String(skill.skill_code).toLowerCase(), String(skill.level).toLowerCase()]),
  )
  return codes.some(code => (skillMap[code] || 'none') !== 'none')
}

function formatNumber(value) {
  const numeric = Number(value || 0)
  return numeric.toFixed(numeric % 1 === 0 ? 0 : 1)
}

async function loadData() {
  isLoading.value = true
  errorMsg.value = ''
  try {
    const [summaryData, storeData, employeeData] = await Promise.all([
      api.getHomeSummary(),
      api.getStores(),
      api.getEmployees(),
    ])

    summary.value = summaryData || {}
    stores.value = storeData || []
    employees.value = employeeData || []

    const storeDetails = await Promise.all(
      stores.value.map(async store => {
        const [ruleConfig, staffingDemand] = await Promise.all([
          api.getStoreRuleConfig(store.id),
          api.getStoreStaffingDemand(store.id),
        ])
        return { storeId: store.id, ruleConfig, staffingDemand }
      }),
    )

    ruleConfigMap.value = Object.fromEntries(storeDetails.map(item => [item.storeId, item.ruleConfig]))
    demandMap.value = Object.fromEntries(storeDetails.map(item => [item.storeId, item.staffingDemand]))
  } catch (error) {
    errorMsg.value = `加载工作台失败：${error.message}`
  } finally {
    isLoading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.home-page {
  display: grid;
  gap: 18px;
}

.dashboard-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(280px, 0.9fr);
  gap: 18px;
  padding: clamp(22px, 3vw, 30px);
}

.hero-copy h1 {
  margin: 0;
  max-width: 18ch;
  font-size: clamp(28px, 4vw, 46px);
  line-height: 1.05;
  color: var(--color-heading);
}

.hero-copy p:last-child {
  margin: 12px 0 0;
  max-width: 72ch;
  color: var(--color-text-soft);
  line-height: 1.7;
}

.eyebrow,
.section-kicker {
  margin: 0 0 8px;
  font-size: 12px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--color-primary-dark);
}

.hero-side {
  display: grid;
  gap: 12px;
}

.role-card,
.metric-card,
.permission-card,
.spotlight-card,
.focus-card {
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(230, 207, 176, 0.82);
  box-shadow: 0 18px 34px rgba(170, 135, 94, 0.08);
}

.role-card {
  padding: 18px;
  background: linear-gradient(135deg, rgba(255, 248, 239, 0.98), rgba(248, 233, 215, 0.98));
}

.role-label,
.metric-label {
  display: block;
  font-size: 13px;
  color: var(--color-text-soft);
}

.role-card strong {
  display: block;
  margin-top: 10px;
  font-size: 30px;
  color: var(--color-heading);
}

.role-card p {
  margin: 10px 0 0;
  color: var(--color-text-soft);
  line-height: 1.6;
}

.hero-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-content: flex-start;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  padding: 18px;
}

.metric-value {
  display: block;
  margin: 10px 0 6px;
  font-size: 34px;
  line-height: 1.05;
  color: var(--color-heading);
}

.metric-card small,
.section-note,
.spotlight-card p,
.focus-card p,
.focus-card small,
.spotlight-card small {
  color: var(--color-text-soft);
}

.permission-strip {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.permission-card {
  padding: 18px;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.soft-chip,
.mini-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(244, 123, 76, 0.1);
  color: var(--color-primary-dark);
  font-size: 12px;
  font-weight: 700;
}

.soft-chip.accent {
  background: rgba(76, 151, 107, 0.14);
  color: #275d3f;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.9fr);
  gap: 18px;
}

.panel-shell {
  padding: 18px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(230, 207, 176, 0.82);
  box-shadow: 0 18px 34px rgba(170, 135, 94, 0.08);
}

.main-panel,
.side-panel {
  display: grid;
  gap: 16px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.section-head h2 {
  margin: 0;
  color: var(--color-heading);
}

.spotlight-grid,
.focus-list {
  display: grid;
  gap: 12px;
}

.spotlight-grid {
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.spotlight-card,
.focus-card {
  padding: 16px;
}

.spotlight-top,
.focus-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.spotlight-card strong,
.focus-card strong {
  color: var(--color-heading);
}

.spotlight-card p,
.focus-card p {
  margin: 10px 0 6px;
  line-height: 1.6;
}

@media (max-width: 1180px) {
  .dashboard-hero,
  .overview-grid,
  .permission-strip,
  .content-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .hero-actions,
  .section-head,
  .spotlight-top,
  .focus-top {
    flex-direction: column;
    align-items: stretch;
  }

  .metric-value {
    font-size: 28px;
  }
}
</style>
