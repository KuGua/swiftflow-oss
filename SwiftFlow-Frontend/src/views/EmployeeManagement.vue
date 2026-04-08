<template>
  <div class="employee-workspace">
    <header class="hero-panel">
      <div>
        <p class="eyebrow">员工管理</p>
        <h1>面向多门店运营的员工档案与能力配置台</h1>
        <p class="hero-copy">
          在这里集中维护员工基础资料、门店授权、技能矩阵、钥匙信息、可排时间和员工关系约束，减少排班前的配置遗漏。
        </p>
      </div>
      <div class="hero-actions">
        <span class="role-chip">{{ roleLabel }}</span>
        <button class="ghost-btn" @click="loadData">刷新数据</button>
      </div>
    </header>

    <div v-if="message" class="status-banner" :class="{ error: isError }">{{ message }}</div>

    <section class="metrics-grid">
      <article class="metric-card"><span class="metric-label">员工总数</span><strong class="metric-value">{{ employees.length }}</strong></article>
      <article class="metric-card"><span class="metric-label">全职 / 兼职</span><strong class="metric-value">{{ fullTimeCount }} / {{ partTimeCount }}</strong></article>
      <article class="metric-card"><span class="metric-label">后场覆盖人数</span><strong class="metric-value">{{ backroomCapableCount }}</strong></article>
      <article class="metric-card accent"><span class="metric-label">可开店人数</span><strong class="metric-value">{{ openingReadyCount }}</strong></article>
    </section>

    <section class="workspace-grid">
      <aside class="roster-panel panel-shell" :style="rosterPanelStyle">
        <div class="panel-head stacked">
          <div>
            <h2>员工列表</h2>
            <p>支持按姓名、类型、状态和门店快速筛选，适合大规模员工场景。</p>
          </div>
          <div class="quick-filters">
            <input v-model.trim="searchText" class="search-input" placeholder="搜索姓名或技能" />
            <select v-model="typeFilter"><option value="all">全部类型</option><option value="full_time">全职</option><option value="part_time">兼职</option></select>
            <select v-model="statusFilter"><option value="all">全部状态</option><option value="active">在职</option><option value="inactive">停用</option></select>
            <select v-model.number="storeFilter"><option :value="0">全部门店</option><option v-for="store in stores" :key="store.id" :value="store.id">{{ store.name }}</option></select>
          </div>
        </div>

        <div class="list-toolbar">
          <span class="list-summary">共 {{ filteredEmployees.length }} 人，默认按全职在前、兼职在后展示</span>
        </div>

        <div class="roster-list">
          <section v-for="group in groupedEmployees" :key="group.key" class="roster-group">
            <div class="group-head">
              <strong>{{ group.label }}</strong>
              <span>{{ group.items.length }} 人</span>
            </div>
            <button v-for="employee in group.items" :key="employee.id" class="roster-card" :class="{ active: employee.id === editingId }" @click="startEdit(employee)">
              <div class="roster-topline">
                <strong>{{ employee.name }}</strong>
                <span :class="['status-pill', employee.employment_status]">{{ employee.employment_status === 'active' ? '在职' : '停用' }}</span>
              </div>
              <div class="roster-meta">
                <span>{{ employee.employment_type === 'full_time' ? '全职' : '兼职' }}</span>
                <span>{{ formatNationality(employee.nationality_status) }}</span>
                <span>{{ employee.monthly_worked_hours }}h</span>
              </div>
              <div class="roster-tags"><span v-for="tag in summarizeEmployeeTags(employee)" :key="tag" class="soft-tag">{{ tag }}</span></div>
            </button>
          </section>
          <div v-if="!filteredEmployees.length" class="empty-block">当前筛选条件下没有匹配员工。</div>
        </div>

      </aside>

      <main ref="editorPanelRef" class="editor-panel panel-shell">
        <div class="panel-head">
          <div>
            <h2>{{ editingId ? '编辑员工' : '员工信息' }}</h2>
            <p>将基础信息、门店授权、技能与可排时间集中维护，方便排班算法正确读取。</p>
          </div>
          <div class="editor-actions">
            <button class="ghost-btn" @click="resetForm">重置</button>
            <button class="primary-btn" :disabled="isSaving || !canSubmit" @click="saveEmployee">{{ isSaving ? '保存中...' : '保存修改' }}</button>
          </div>
        </div>

        <section class="section-card">
          <div class="section-head"><h3>基础档案</h3><p>姓名、用工类型与员工基础信息在一个区域内集中维护。</p></div>
          <div class="form-grid basic-grid">
            <label>姓名<input v-model="form.name" :disabled="!canEditEmployeeName" placeholder="例如：员工A" /></label>
            <label>状态<select v-model="form.employment_status" :disabled="!canEditStatusFields"><option value="active">在职</option><option value="inactive">停用</option></select></label>
            <label>用工类型<select v-model="form.employment_type" :disabled="!canEditStatusFields"><option value="full_time">全职</option><option value="part_time">兼职</option></select></label>
            <label v-if="!isAdminView">班次偏好<select v-model="form.preferred_shift" :disabled="!canEditEmployeeDetails"><option value="no_preference">无偏好</option><option value="opening">早班</option><option value="midday">中班</option><option value="closing">晚班</option></select></label>
            <label>身份类型<select v-model="form.nationality_status" :disabled="!canEditEmployeeDetails"><option value="other">其他</option><option value="sg_citizen">新加坡公民</option><option value="sg_pr">新加坡 PR</option></select></label>
            <label v-if="!isAdminView">工作技能分<input v-model.number="form.work_skill_score" :disabled="!canEditEmployeeDetails" type="number" min="0" max="100" /></label>
            <label v-if="!isAdminView">管理能力分<input v-model.number="form.management_skill_score" :disabled="!canEditEmployeeDetails" type="number" min="0" max="100" /></label>
          </div>
        </section>

        <section class="section-card">
          <div class="section-head"><h3>门店授权与钥匙</h3><p>在同一处维护员工可去哪些门店、优先级和是否持钥匙。</p></div>
          <div class="store-matrix">
            <article v-for="item in form.store_settings" :key="item.store_id" class="store-tile" :class="{ enabled: item.enabled }">
              <div class="store-tile-top">
                <div class="store-tile-title">
                  <strong>{{ getStoreName(item.store_id) }}</strong>
                  <span class="mini-status" :class="{ active: item.enabled }">{{ item.enabled ? '已启用' : '未启用' }}</span>
                </div>
                <label class="switch-line store-toggle-line"><input v-model="item.enabled" :disabled="!canEditEmployeeDetails" type="checkbox" /><span>{{ item.enabled ? '参与排班' : '暂不参与' }}</span></label>
              </div>
              <div class="store-tile-fields">
                <label>优先级<input v-model.number="item.priority" :disabled="!canEditEmployeeDetails || !item.enabled" type="number" min="1" placeholder="1 为最高优先级" /></label>
                <label class="switch-line compact key-toggle"><input v-model="item.has_key" :disabled="!canEditEmployeeDetails || !item.enabled" type="checkbox" /><span>{{ item.has_key ? '持钥匙' : '无钥匙' }}</span></label>
              </div>
            </article>
          </div>
        </section>

        <section v-if="!isAdminView" class="section-card">
          <div class="section-head"><h3>技能矩阵</h3><p>清晰记录前场、后场与收尾能力，帮助排班算法更贴近真实运营。</p></div>
          <div class="skill-groups">
            <article v-for="group in skillGroups" :key="group.key" class="skill-group-card">
              <div class="skill-group-head"><h4>{{ group.title }}</h4><p>{{ group.description }}</p></div>
              <div class="skill-grid">
                <div v-for="skill in group.skills" :key="skill.code" class="skill-tile">
                  <div><strong>{{ skill.label }}</strong><p>{{ skill.hint }}</p></div>
                  <select :value="skillLevel(skill.code)" :disabled="!canEditEmployeeDetails" @change="setSkillLevel(skill.code, $event.target.value)">
                    <option value="none">不会</option><option value="basic">基础</option><option value="proficient">熟练</option>
                  </select>
                </div>
              </div>
            </article>
          </div>
          <div class="custom-skill-block">
            <div class="section-head compact-head"><h4>扩展技能</h4><button class="ghost-btn mini" :disabled="!canEditEmployeeDetails" @click="addCustomSkill">新增技能</button></div>
            <div class="custom-skill-list">
              <div v-for="(skill, index) in customSkills" :key="`${skill.skill_code}-${index}`" class="custom-skill-row">
                <input :value="skill.skill_code" :disabled="!canEditEmployeeDetails" placeholder="输入 skill_code" @input="updateCustomSkill(index, 'skill_code', $event.target.value)" />
                <select :value="skill.level" :disabled="!canEditEmployeeDetails" @change="updateCustomSkill(index, 'level', $event.target.value)"><option value="none">不会</option><option value="basic">基础</option><option value="proficient">熟练</option></select>
                <button class="mini-btn danger" :disabled="!canEditEmployeeDetails" @click="removeCustomSkill(index)">删除</button>
              </div>
              <div v-if="!customSkills.length" class="empty-inline">当前没有扩展技能。</div>
            </div>
          </div>
        </section>

        <section class="section-card availability-section">
          <div class="section-head">
            <div>
              <h3>可排时间编辑</h3>
              <p>按本周与下周分别维护员工可上班时间，仅保留星期开关与起止时间输入。</p>
            </div>
            <div class="availability-summary-chips">
              <span class="soft-tag">左侧本周</span>
              <span class="soft-tag">右侧下周</span>
            </div>
          </div>
          <div class="availability-panels board-mode">
            <article v-for="weekOffset in [0, 1]" :key="weekOffset" class="availability-card weekly-board-card">
              <div class="availability-card-head">
                <h4>{{ weekOffset === 0 ? '本周' : '下周' }}</h4>
                <span class="availability-legend">点击星期可切换当天是否可上班。</span>
              </div>
              <div class="weekly-board-shell">
                <div class="weekly-board-header">
                  <span class="weekly-board-day-head">星期</span>
                  <span class="weekly-board-day-head">时间</span>
                </div>
                <div class="weekly-board-body">
                  <div v-for="item in availabilityRowsByWeek(weekOffset)" :key="`${weekOffset}-${item.day_of_week}`" class="weekly-board-row">
                    <div class="weekly-board-day-cell">
                      <button type="button" class="day-toggle" :class="{ active: isAvailabilityEnabled(item) }" :disabled="!canEditAvailability" @click="toggleAvailability(item)">{{ dayLabels[item.day_of_week] }}</button>
                    </div>
                    <div class="weekly-board-editors">
                      <input v-model="item.start_time" :disabled="!canEditAvailability || !isAvailabilityEnabled(item)" type="time" />
                      <span>至</span>
                      <input v-model="item.end_time" :disabled="!canEditAvailability || !isAvailabilityEnabled(item)" type="time" />
                    </div>
                  </div>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section v-if="editingId && canManagePermissions" class="section-card">
          <EmployeePermissionCard :employee-id="editingId" :employee-name="form.name" />
        </section>
      </main>
    </section>

    <section v-if="canManageRelations && !isAdminView" class="section-card relations-panel">
      <div class="section-head"><h3>关系约束</h3><p>用于记录搭班冲突或特殊排班关系，避免在主要流程中被忽略。</p></div>
      <div class="relation-toolbar">
        <select v-model.number="relationForm.employee_id_a"><option :value="0" disabled>员工 A</option><option v-for="employee in employees" :key="employee.id" :value="employee.id">{{ employee.name }}</option></select>
        <select v-model.number="relationForm.employee_id_b"><option :value="0" disabled>员工 B</option><option v-for="employee in employees" :key="employee.id" :value="employee.id">{{ employee.name }}</option></select>
        <select v-model="relationForm.relation_type"><option value="bad">避免同班</option><option value="prefer">优先同班</option></select>
        <input v-model.number="relationForm.severity" type="number" min="0" max="1" step="0.1" />
        <button class="primary-btn" @click="saveRelation">保存关系</button>
      </div>
      <div class="relation-list">
        <article v-for="relation in relations" :key="relation.id" class="relation-card">
          <div class="relation-card-main">
            <div class="relation-people">
              <strong>{{ employeeName(relation.employee_id_a) }}</strong>
              <span class="relation-link">{{ relation.relation_type === 'prefer' ? '优先搭班' : '避免同班' }}</span>
              <strong>{{ employeeName(relation.employee_id_b) }}</strong>
            </div>
            <p>关系强度 {{ relation.severity }}</p>
          </div>
          <button class="mini-btn danger" @click="removeRelation(relation)">删除</button>
        </article>
        <div v-if="!relations.length" class="empty-inline">当前没有关系约束。</div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '@/lib/apiClient'
import EmployeePermissionCard from '@/components/EmployeePermissionCard.vue'

const stores = ref([])
const employees = ref([])
const relations = ref([])
const currentRole = ref('store_manager')
const message = ref('')
const isError = ref(false)
const isSaving = ref(false)
const editingId = ref(null)
const isApplyingFormState = ref(false)
const currentUserEmployeeId = ref(null)
const originalAvailabilitySignature = ref('')
const searchText = ref('')
const typeFilter = ref('all')
const statusFilter = ref('all')
const storeFilter = ref(0)
const relationForm = ref({ employee_id_a: 0, employee_id_b: 0, relation_type: 'bad', severity: 0.8 })
const editorPanelRef = ref(null)
const rosterPanelHeight = ref(null)
let editorPanelObserver = null
const dayLabels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const presetSkillCodes = new Set(['front_service', 'cashier', 'floor', 'customer_service', 'backroom', 'inventory', 'close_backroom_clean', 'close_machine_clean', 'close_settlement'])
const skillGroups = [
  { key: 'coverage', title: '基础覆盖能力', description: '用于开店、小时级补位和前后场轮转判断。', skills: [{ code: 'front_service', label: '前场服务', hint: '可独立承担前场接待与服务。' }, { code: 'backroom', label: '后场', hint: '可承担后场制作、清洗或备料。' }, { code: 'inventory', label: '库存/后仓', hint: '可补货、盘点并支援后仓工作。' }] },
  { key: 'floor', title: '细分岗位能力', description: '保留更细粒度的岗位信息，便于后续排班规则扩展。', skills: [{ code: 'cashier', label: '收银', hint: '能处理 POS、结算与钱箱操作。' }, { code: 'floor', label: '楼面支援', hint: '能负责楼面、传菜与前场支援。' }, { code: 'customer_service', label: '顾客服务', hint: '能处理顾客沟通与基础服务问题。' }] },
  { key: 'closing', title: '晚间收尾能力', description: '决定晚间 closing support 是否真的能完成收尾工作。', skills: [{ code: 'close_backroom_clean', label: '后场清洗', hint: '负责后场清洗与后场收尾。' }, { code: 'close_machine_clean', label: '机器清洗', hint: '负责冰淇淋机或设备清洗。' }, { code: 'close_settlement', label: '结算', hint: '负责夜间结算、对账和关账。' }] },
]

function createAvailabilityRangeForType(employmentType) { return employmentType === 'part_time' ? { start_time: '', end_time: '' } : { start_time: '00:00', end_time: '23:59' } }
function suggestedAvailabilityRangeForType(employmentType) { return employmentType === 'part_time' ? { start_time: '12:00', end_time: '18:00' } : { start_time: '00:00', end_time: '23:59' } }
function createDefaultAvailabilities(employmentType = 'full_time') { return Array.from({ length: 14 }, (_, index) => ({ week_offset: index < 7 ? 0 : 1, day_of_week: index % 7, ...createAvailabilityRangeForType(employmentType) })) }
function normalizeAvailabilities(items = [], employmentType = 'full_time') {
  const availabilityMap = new Map(items.map(item => [`${Number(item.week_offset)}-${Number(item.day_of_week)}`, { ...item }]))
  return createDefaultAvailabilities(employmentType).map(item => {
    const existing = availabilityMap.get(`${item.week_offset}-${item.day_of_week}`)
    return existing ? { week_offset: item.week_offset, day_of_week: item.day_of_week, start_time: typeof existing.start_time === 'string' ? existing.start_time : item.start_time, end_time: typeof existing.end_time === 'string' ? existing.end_time : item.end_time } : item
  })
}
const emptyForm = () => ({ name: '', employment_status: 'active', employment_type: 'full_time', preferred_shift: 'no_preference', nationality_status: 'other', work_skill_score: 50, management_skill_score: 50, store_settings: [], skills: [{ skill_code: 'front_service', level: 'none' }, { skill_code: 'backroom', level: 'none' }], availabilities: createDefaultAvailabilities('full_time') })
const form = ref(emptyForm())
const canManageCoreFields = computed(() => ['super_admin', 'area_manager', 'store_manager'].includes(currentRole.value))
const canManageAdminFields = computed(() => ['admin'].includes(currentRole.value))
const isAdminView = computed(() => currentRole.value === 'admin')
const canCreateEmployee = computed(() => ['super_admin'].includes(currentRole.value))
const canManageRelations = computed(() => ['area_manager', 'store_manager'].includes(currentRole.value))
const canManagePermissions = computed(() => ['super_admin', 'admin', 'area_manager'].includes(currentRole.value))
const canEditEmployeeName = computed(() => currentRole.value === 'super_admin')
const canEditEmployeeDetails = computed(() => canManageCoreFields.value)
const canEditStatusFields = computed(() => canEditEmployeeDetails.value || canManageAdminFields.value)
const canEditAvailability = computed(() => ['super_admin', 'area_manager', 'store_manager'].includes(currentRole.value))
const roleLabel = computed(() => currentRole.value === 'super_admin' ? '平台负责人' : currentRole.value === 'admin' ? '运营管理员' : '店长')
const canSubmit = computed(() => !isSaving.value && (editingId.value ? (canEditEmployeeDetails.value || canEditStatusFields.value || canEditAvailability.value) : (canCreateEmployee.value && Boolean(form.value.name.trim()))))
const fullTimeCount = computed(() => employees.value.filter(item => item.employment_type === 'full_time').length)
const partTimeCount = computed(() => employees.value.filter(item => item.employment_type === 'part_time').length)
const backroomCapableCount = computed(() => employees.value.filter(employee => employeeHasAnySkill(employee, ['backroom', 'inventory'])).length)
const openingReadyCount = computed(() => employees.value.filter(employee => employeeHasAnySkill(employee, ['front_service', 'cashier', 'floor', 'customer_service']) && employeeHasAnySkill(employee, ['backroom', 'inventory'])).length)
const filteredEmployees = computed(() => {
  const keyword = searchText.value.toLowerCase()
  return [...employees.value].filter(employee => {
    if (typeFilter.value !== 'all' && employee.employment_type !== typeFilter.value) return false
    if (statusFilter.value !== 'all' && employee.employment_status !== statusFilter.value) return false
    if (storeFilter.value && !(employee.store_settings || []).some(item => item.store_id === storeFilter.value)) return false
    if (!keyword) return true
    const skillText = (employee.skills || []).map(item => item.skill_code).join(' ')
    return `${employee.name} ${skillText}`.toLowerCase().includes(keyword)
  }).sort((a, b) => (a.employment_status !== b.employment_status ? (a.employment_status === 'active' ? -1 : 1) : a.name.localeCompare(b.name, 'zh-Hans-CN')))
})
const groupedEmployees = computed(() => {
  const unassignedEmployees = filteredEmployees.value.filter(employee => !employeeHasAssignedStores(employee))
  const assignedEmployees = filteredEmployees.value.filter(employee => employeeHasAssignedStores(employee))
  const groups = [
    { key: 'unassigned', label: '未分配门店员工', items: unassignedEmployees },
    { key: 'full_time', label: '全职员工', items: assignedEmployees.filter(employee => employee.employment_type === 'full_time') },
    { key: 'part_time', label: '兼职员工', items: assignedEmployees.filter(employee => employee.employment_type === 'part_time') },
  ]
  return groups.filter(group => group.items.length)
})
const customSkills = computed(() => (form.value.skills || []).filter(skill => !presetSkillCodes.has(String(skill.skill_code || '').trim().toLowerCase())))
function notify(text, error = false) { message.value = text; isError.value = error }
function formatNationality(code) { return code === 'sg_citizen' ? '新加坡公民' : code === 'sg_pr' ? '新加坡 PR' : '其他' }
function employeeHasAnySkill(employee, codes) {
  const map = Object.fromEntries((employee.skills || []).map(skill => [String(skill.skill_code).toLowerCase(), String(skill.level).toLowerCase()]))
  return codes.some(code => ['basic', 'proficient'].includes(map[String(code).toLowerCase()] || 'none'))
}
function summarizeEmployeeTags(employee) {
  const tags = []
  if (employeeHasAnySkill(employee, ['front_service', 'cashier', 'floor', 'customer_service'])) tags.push('前场')
  if (employeeHasAnySkill(employee, ['backroom', 'inventory'])) tags.push('后场')
  if (employeeHasAnySkill(employee, ['front_service', 'cashier', 'floor', 'customer_service']) && employeeHasAnySkill(employee, ['backroom', 'inventory'])) tags.push('可开店')
  if (employeeHasAnySkill(employee, ['close_backroom_clean', 'close_machine_clean', 'close_settlement'])) tags.push('会收尾')
  if ((employee.store_settings || []).some(item => item.has_key)) tags.push('持钥匙')
  return tags.slice(0, 4)
}
function relationTypeLabel(type) { return type === 'prefer' ? '优先同班' : '避免同班' }
function getStoreName(storeId) { return stores.value.find(item => item.id === storeId)?.name || `门店 #${storeId}` }
function employeeHasAssignedStores(employee) {
  if (Array.isArray(employee?.store_ids) && employee.store_ids.length > 0) return true
  return Array.isArray(employee?.store_settings) && employee.store_settings.length > 0
}
function syncStoreSettings(defaultFromStores = true) {
  const current = new Map(form.value.store_settings.map(item => [item.store_id, item]))
  form.value.store_settings = stores.value.map(store => current.get(store.id) ? { ...current.get(store.id) } : { store_id: store.id, enabled: defaultFromStores ? false : true, priority: null, has_key: false })
}
function syncAvailabilityDefaultsByEmploymentType(employmentType) { form.value.availabilities = createDefaultAvailabilities(employmentType) }
function isAvailabilityEnabled(item) { return Boolean(item.start_time && item.end_time) }
function toggleAvailability(item) { if (!canEditAvailability.value) return; if (isAvailabilityEnabled(item)) { item.start_time = ''; item.end_time = '' } else { const suggestion = suggestedAvailabilityRangeForType(form.value.employment_type); item.start_time = suggestion.start_time; item.end_time = suggestion.end_time } }
function availabilityRowsByWeek(weekOffset) { return form.value.availabilities.filter(item => item.week_offset === weekOffset) }
function toDisplayEndTime(value) {
  if (!value) return ''
  return value === '23:59' ? '24:00' : value
}
function serializeAvailabilities(items = []) {
  return JSON.stringify(
    (items || []).map(item => ({
      week_offset: Number(item.week_offset),
      day_of_week: Number(item.day_of_week),
      start_time: item.start_time || '',
      end_time: item.end_time || '',
    })),
  )
}
function availabilityRangeLabel(item) {
  if (!item?.start_time || !item?.end_time) return '未设置'
  return `${item.start_time} - ${toDisplayEndTime(item.end_time)}`
}
function skillLevel(skillCode) { return (form.value.skills || []).find(item => String(item.skill_code).toLowerCase() === String(skillCode).toLowerCase())?.level || 'none' }
function setSkillLevel(skillCode, level) {
  if (!canEditEmployeeDetails.value) return
  const normalized = String(skillCode).toLowerCase()
  const nextSkills = [...form.value.skills]
  const existing = nextSkills.find(item => String(item.skill_code).toLowerCase() === normalized)
  if (existing) existing.level = level
  else nextSkills.push({ skill_code: normalized, level })
  form.value.skills = nextSkills
}
function addCustomSkill() { if (canEditEmployeeDetails.value) form.value.skills.push({ skill_code: '', level: 'none' }) }
function updateCustomSkill(index, field, value) {
  if (!canEditEmployeeDetails.value) return
  const custom = [...customSkills.value]
  custom[index] = { ...custom[index], [field]: field === 'skill_code' ? String(value || '').trim().toLowerCase() : value }
  form.value.skills = [...(form.value.skills || []).filter(skill => presetSkillCodes.has(String(skill.skill_code || '').trim().toLowerCase())), ...custom]
}
function removeCustomSkill(index) {
  if (!canEditEmployeeDetails.value) return
  const custom = [...customSkills.value]
  custom.splice(index, 1)
  form.value.skills = [...(form.value.skills || []).filter(skill => presetSkillCodes.has(String(skill.skill_code || '').trim().toLowerCase())), ...custom]
}
function normalizeEmployeePayloadForRole() {
  if (!editingId.value || canEditEmployeeDetails.value) {
    const activeStoreSettings = form.value.store_settings.filter(item => item.enabled).map(item => ({ store_id: item.store_id, priority: item.priority ? Number(item.priority) : null, has_key: Boolean(item.has_key) }))
    return {
      name: form.value.name.trim(), employment_status: form.value.employment_status, employment_type: form.value.employment_type, preferred_shift: form.value.preferred_shift, nationality_status: form.value.nationality_status, work_skill_score: Number(form.value.work_skill_score), management_skill_score: Number(form.value.management_skill_score),
      store_ids: activeStoreSettings.map(item => item.store_id), store_settings: activeStoreSettings,
      skills: form.value.skills.map(item => ({ skill_code: String(item.skill_code || '').trim().toLowerCase(), level: item.level })).filter(item => item.skill_code),
      availabilities: form.value.availabilities.map(item => ({ ...item, start_time: item.start_time || '', end_time: item.end_time === '23:59' ? '24:00' : item.end_time || '' }))
    }
  }
  if (canManageAdminFields.value) {
    return {
      employment_status: form.value.employment_status,
      employment_type: form.value.employment_type,
    }
  }
  return { availabilities: form.value.availabilities.map(item => ({ ...item, start_time: item.start_time || '', end_time: item.end_time === '23:59' ? '24:00' : item.end_time || '' })) }
}
const rosterPanelStyle = computed(() => rosterPanelHeight.value ? { height: `${rosterPanelHeight.value}px` } : {})
function syncRosterPanelHeight() {
  if (!editorPanelRef.value) {
    rosterPanelHeight.value = null
    return
  }
  rosterPanelHeight.value = Math.ceil(editorPanelRef.value.getBoundingClientRect().height)
}
function setupEditorPanelObserver() {
  if (editorPanelObserver) {
    editorPanelObserver.disconnect()
    editorPanelObserver = null
  }
  if (!editorPanelRef.value) {
    rosterPanelHeight.value = null
    return
  }
  if (typeof ResizeObserver === 'undefined') {
    syncRosterPanelHeight()
    return
  }
  editorPanelObserver = new ResizeObserver(() => syncRosterPanelHeight())
  editorPanelObserver.observe(editorPanelRef.value)
  syncRosterPanelHeight()
}
function selectDefaultEmployee() {
  const preferredEmployee = employees.value.find(item => item.id === currentUserEmployeeId.value)
  const fallbackEmployee = preferredEmployee || employees.value[0]
  if (fallbackEmployee) {
    startEdit(fallbackEmployee)
    return
  }
  isApplyingFormState.value = true
  editingId.value = null
  form.value = emptyForm()
  originalAvailabilitySignature.value = serializeAvailabilities(form.value.availabilities)
  syncStoreSettings()
  nextTick(() => {
    isApplyingFormState.value = false
    syncRosterPanelHeight()
  })
}
async function loadMe() {
  const me = await api.getMe()
  currentRole.value = me.role
  currentUserEmployeeId.value = me.employee_id ?? null
}
async function loadData() {
  try {
    notify('')
    const [storeData, employeeData] = await Promise.all([api.getStores(), api.getEmployees()])
    stores.value = storeData || []
    employees.value = employeeData || []
    if (!editingId.value || !employees.value.some(item => item.id === editingId.value)) selectDefaultEmployee()
    if (canManageRelations.value) relations.value = await api.getEmployeeRelations()
    nextTick(() => syncRosterPanelHeight())
  } catch (error) { notify(`加载员工数据失败：${error.message}`, true) }
}
function resetForm() {
  selectDefaultEmployee()
}
function startCreate() {
  if (!canCreateEmployee.value) return notify('当前角色无权创建员工。', true)
  isApplyingFormState.value = true
  editingId.value = null
  form.value = emptyForm()
  originalAvailabilitySignature.value = serializeAvailabilities(form.value.availabilities)
  syncStoreSettings()
  nextTick(() => {
    isApplyingFormState.value = false
    syncRosterPanelHeight()
  })
}
function startEdit(employee) {
  isApplyingFormState.value = true
  editingId.value = employee.id
  const settingMap = new Map((employee.store_settings || []).map(item => [item.store_id, item]))
  form.value = {
    name: employee.name, employment_status: employee.employment_status, employment_type: employee.employment_type, preferred_shift: employee.preferred_shift || 'no_preference', nationality_status: employee.nationality_status || 'other', work_skill_score: employee.work_skill_score ?? 50, management_skill_score: employee.management_skill_score ?? 50,
    store_settings: stores.value.map(store => ({ store_id: store.id, enabled: Boolean(settingMap.get(store.id)) || employee.store_ids.includes(store.id), priority: settingMap.get(store.id)?.priority ?? null, has_key: Boolean(settingMap.get(store.id)?.has_key) })),
    skills: (employee.skills || []).length ? employee.skills.map(item => ({ ...item })) : emptyForm().skills,
    availabilities: normalizeAvailabilities(employee.availabilities || [], employee.employment_type)
  }
  originalAvailabilitySignature.value = serializeAvailabilities(form.value.availabilities)
  nextTick(() => {
    isApplyingFormState.value = false
    syncRosterPanelHeight()
  })
}
async function saveEmployee() {
  if (!canSubmit.value) return
  const availabilityChanged = editingId.value !== null && serializeAvailabilities(form.value.availabilities) !== originalAvailabilitySignature.value
  if (availabilityChanged && ['area_manager', 'store_manager'].includes(currentRole.value)) {
    const confirmed = window.confirm('确认修改该员工的可排班时间吗？')
    if (!confirmed) return
  }
  isSaving.value = true
  try {
    const payload = normalizeEmployeePayloadForRole()
    if (editingId.value) { await api.updateEmployee(editingId.value, payload); notify('员工信息已更新。') }
    else { await api.createEmployee(payload); notify('员工已创建。') }
    await loadData(); resetForm()
  } catch (error) { notify(`保存员工失败：${error.message}`, true) }
  finally { isSaving.value = false }
}
function employeeName(employeeId) { return employees.value.find(item => item.id === employeeId)?.name || `#${employeeId}` }
async function saveRelation() {
  if (!canManageRelations.value) return
  try { await api.upsertEmployeeRelation({ employee_id_a: Number(relationForm.value.employee_id_a), employee_id_b: Number(relationForm.value.employee_id_b), relation_type: relationForm.value.relation_type, severity: Number(relationForm.value.severity) }); relations.value = await api.getEmployeeRelations(); notify('员工关系已保存。') } catch (error) { notify(`保存员工关系失败：${error.message}`, true) }
}
async function removeRelation(relation) {
  if (!canManageRelations.value) return
  try { await api.deleteEmployeeRelation(relation.employee_id_a, relation.employee_id_b); relations.value = await api.getEmployeeRelations(); notify('员工关系已删除。') } catch (error) { notify(`删除员工关系失败：${error.message}`, true) }
}
onMounted(async () => {
  await loadMe()
  await loadData()
  nextTick(() => setupEditorPanelObserver())
})
onBeforeUnmount(() => {
  if (editorPanelObserver) {
    editorPanelObserver.disconnect()
    editorPanelObserver = null
  }
})
watch(() => form.value.employment_type, employmentType => { if (!isApplyingFormState.value) syncAvailabilityDefaultsByEmploymentType(employmentType) })
</script><style scoped>
.employee-workspace { display: grid; gap: 18px; }
.hero-panel, .panel-shell, .metric-card, .section-card, .skill-group-card, .availability-card, .store-tile, .relation-card, .roster-card { border: 1px solid var(--color-border); background: rgba(255, 255, 255, 0.9); box-shadow: 0 16px 38px var(--theme-shadow); }
.hero-panel { display: grid; grid-template-columns: minmax(0, 1.3fr) auto; gap: 18px; align-items: stretch; padding: 22px; border-radius: 28px; background:
  radial-gradient(circle at top right, rgba(244, 123, 76, 0.12), transparent 24%),
  linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(250, 243, 233, 0.96)); }
.hero-panel h1 { margin: 0; font-size: clamp(28px, 4vw, 40px); color: var(--color-heading); }
.hero-copy { margin-top: 10px; max-width: 72ch; color: var(--color-text-soft); }
.hero-actions, .quick-filters, .editor-actions, .relation-toolbar, .availability-summary-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.hero-actions { align-content: start; padding: 14px; border-radius: 20px; border: 1px solid rgba(244, 123, 76, 0.14); background: rgba(255, 251, 245, 0.78); }
.role-chip, .soft-tag, .mini-status, .status-pill { display: inline-flex; align-items: center; border-radius: 999px; font-size: 12px; font-weight: 800; }
.role-chip { padding: 10px 14px; background: rgba(244, 123, 76, 0.12); color: var(--color-primary-dark); }
.status-banner { padding: 12px 14px; border-radius: 14px; background: rgba(234, 248, 238, 0.92); color: #2f6d47; }
.status-banner.error { background: rgba(253, 236, 233, 0.92); color: #933a2f; }
.metrics-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.metric-card { padding: 16px 18px; border-radius: 20px; }
.metric-card.accent { background: linear-gradient(145deg, rgba(244, 123, 76, 0.16), rgba(248, 233, 215, 0.92)); }
.metric-label { display: block; color: var(--color-text-soft); font-size: 13px; }
.metric-value { display: block; margin-top: 8px; font-size: 30px; color: var(--color-heading); }
.workspace-grid { display: grid; grid-template-columns: minmax(300px, 360px) minmax(0, 1fr); gap: 16px; align-items: start; }
.panel-shell { border-radius: 24px; padding: 18px; }
.roster-panel { display: flex; flex-direction: column; min-height: 0; }
.editor-panel { min-width: 0; }
.panel-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 14px; }
.panel-head.stacked { flex-direction: column; }
.panel-head h2, .section-head h3, .skill-group-head h4 { margin: 0; color: var(--color-heading); }
.panel-head p, .section-head p, .skill-group-head p { margin: 4px 0 0; color: var(--color-text-soft); font-size: 13px; }
.search-input, select, input { width: 100%; min-height: 42px; border: 1px solid var(--color-border); border-radius: 14px; padding: 0 12px; background: rgba(255, 251, 245, 0.92); }
.quick-filters > * { flex: 1 1 150px; }
.list-toolbar, .page-size, .group-head, .pagination { display: flex; align-items: center; gap: 10px; }
.list-toolbar, .group-head, .pagination { justify-content: space-between; }
.page-size select { width: 84px; }
.roster-list, .skill-groups, .custom-skill-list, .relation-list, .roster-group { display: grid; gap: 10px; }
.relation-toolbar { margin-bottom: 16px; }
.relation-list { margin-top: 6px; }
.roster-list { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding-right: 4px; }
.roster-card { display: grid; gap: 8px; width: 100%; text-align: left; border-radius: 18px; padding: 14px; cursor: pointer; transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease; }
.roster-card:hover, .roster-card.active { transform: translateY(-1px); border-color: rgba(244, 123, 76, 0.4); box-shadow: 0 20px 32px rgba(20, 35, 31, 0.1); }
.group-head { padding: 4px 2px; color: var(--color-text-soft); font-size: 13px; }
.group-head strong { color: var(--color-heading); }
.roster-topline, .roster-meta, .roster-tags, .store-tile-top, .switch-line, .skill-tile, .custom-skill-row, .availability-row, .relation-card { display: flex; align-items: center; }
.roster-topline, .store-tile-top, .relation-card { justify-content: space-between; gap: 12px; }
.roster-meta, .roster-tags { gap: 8px; flex-wrap: wrap; color: var(--color-text-soft); font-size: 13px; }
.status-pill, .soft-tag, .mini-status { padding: 4px 10px; }
.status-pill.active { background: rgba(76, 151, 107, 0.14); color: #275d3f; }
.status-pill.inactive { background: rgba(203, 87, 78, 0.16); color: #8c312e; }
.soft-tag, .mini-status { background: rgba(244, 123, 76, 0.1); color: var(--color-primary-dark); }
.section-card { border-radius: 20px; padding: 16px; }
.section-card + .section-card { margin-top: 14px; }
.relations-panel { margin-top: 10px; }
.basic-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.basic-grid label, .store-tile label, .skill-tile p, .custom-skill-row, .availability-row, .relation-card p { font-size: 13px; }
.basic-grid label, .store-tile-fields { display: grid; gap: 6px; }
.store-matrix { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.store-tile { border-radius: 18px; padding: 14px; background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 239, 228, 0.72)); border: 1px solid rgba(244, 123, 76, 0.12); }
.store-tile.enabled { background: linear-gradient(180deg, rgba(255, 248, 239, 0.98), rgba(248, 233, 215, 0.92)); border-color: rgba(244, 123, 76, 0.28); box-shadow: inset 0 1px 0 rgba(255,255,255,0.88), 0 12px 24px rgba(20, 35, 31, 0.05); }
.store-tile-title { display: grid; gap: 6px; }
.store-tile-title strong { color: var(--color-heading); }
.store-tile-fields { margin-top: 12px; gap: 8px; }
.switch-line { gap: 8px; }
.switch-line input[type="checkbox"] { width: 16px; min-width: 16px; height: 16px; min-height: 16px; margin: 0; accent-color: var(--color-primary); }
.store-toggle-line, .key-toggle { padding: 6px 9px; border-radius: 12px; background: rgba(255, 251, 245, 0.78); border: 1px solid rgba(244, 123, 76, 0.12); font-size: 12px; line-height: 1.3; }
.store-toggle-line span, .key-toggle span { display: inline-flex; align-items: center; }
.key-toggle { justify-content: flex-start; }
.key-toggle::before { content: '🔑'; font-size: 12px; line-height: 1; margin-right: 6px; opacity: 0.72; }
.key-toggle input[type="checkbox"] { margin-right: 2px; }
.mini-status.active { background: rgba(76, 151, 107, 0.14); color: #275d3f; }
.skill-group-card { border-radius: 18px; padding: 14px; }
.skill-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 12px; }
.skill-tile { justify-content: space-between; gap: 12px; padding: 12px; border-radius: 14px; background: rgba(248, 239, 228, 0.6); }
.skill-tile strong, .relation-card strong { font-weight: 800; }
.skill-tile p { margin: 4px 0 0; color: var(--color-text-soft); }
.custom-skill-block { margin-top: 14px; }
.compact-head { margin-bottom: 10px; }
.custom-skill-row { gap: 8px; }
.custom-skill-row > * { flex: 1 1 0; }
.availability-section { background: linear-gradient(180deg, rgba(255, 252, 248, 0.96), rgba(248, 239, 228, 0.62)); }
.availability-panels { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.availability-panels.board-mode { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.availability-card { border-radius: 18px; padding: 14px; }
.weekly-board-card { overflow: hidden; background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(250, 243, 233, 0.9)); border: 1px solid rgba(244, 123, 76, 0.16); box-shadow: inset 0 1px 0 rgba(255,255,255,0.9), 0 18px 32px rgba(20, 35, 31, 0.06); }
.availability-card-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 12px; }
.availability-card h4 { margin: 0; font-weight: 800; color: var(--color-heading); }
.availability-legend { font-size: 12px; color: var(--color-text-soft); }
.weekly-board-shell { display: grid; gap: 10px; }
.weekly-board-header, .weekly-board-row { display: grid; grid-template-columns: 76px minmax(0, 1fr); gap: 12px; align-items: center; }
.weekly-board-header { padding: 0 2px 6px; border-bottom: 1px solid rgba(244, 123, 76, 0.12); }
.weekly-board-body { display: grid; gap: 10px; padding-top: 6px; }
.weekly-board-day-head { color: var(--color-text-soft); font-size: 12px; font-weight: 700; }
.weekly-board-day-cell { display: flex; align-items: center; }
.weekly-board-editors { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); gap: 8px; align-items: center; min-height: 52px; }
.weekly-board-editors span { color: var(--color-text-soft); font-size: 12px; text-align: center; }
.availability-list { display: grid; gap: 12px; }
.availability-row { gap: 10px; align-items: flex-start; }
.availability-main { flex: 1 1 auto; display: grid; gap: 8px; }
.day-toggle { min-width: 72px; min-height: 40px; border-radius: 12px; border: 1px solid var(--color-border); background: rgba(255, 251, 245, 0.92); }
.day-toggle.active { background: linear-gradient(135deg, var(--color-primary), var(--color-primary-dark)); color: #fff; border-color: transparent; }
.relation-card-main { display: grid; gap: 6px; }
.relation-people { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.relation-link { display: inline-flex; align-items: center; min-height: 28px; padding: 0 10px; border-radius: 999px; background: rgba(244, 123, 76, 0.12); color: var(--color-primary-dark); font-size: 12px; font-weight: 800; }
.relation-card { padding: 14px 16px; border-radius: 16px; background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 239, 228, 0.82)); border: 1px solid rgba(244, 123, 76, 0.12); }
.relation-card p { margin: 0; color: var(--color-text-soft); }
.empty-block, .empty-inline { padding: 14px; border-radius: 14px; background: rgba(248, 239, 228, 0.6); color: var(--color-text-soft); }
.primary-btn, .ghost-btn, .mini-btn { min-height: 40px; border-radius: 12px; border: none; padding: 0 14px; font-weight: 800; cursor: pointer; }
.primary-btn { background: linear-gradient(135deg, var(--color-primary), var(--color-primary-dark)); color: #fff; }
.ghost-btn, .mini-btn { background: rgba(244, 123, 76, 0.1); color: var(--color-primary-dark); }
.mini-btn { min-height: 34px; padding: 0 12px; }
.mini-btn.danger { background: rgba(203, 87, 78, 0.16); color: #8c312e; }
.page-pill { min-width: 36px; min-height: 36px; border: 1px solid var(--color-border); border-radius: 999px; background: rgba(255, 251, 245, 0.92); color: var(--color-heading); font-weight: 700; }
.page-pill.active { background: rgba(244, 123, 76, 0.12); color: var(--color-primary-dark); border-color: rgba(244, 123, 76, 0.28); }
button:disabled, input:disabled, select:disabled { opacity: 0.55; cursor: not-allowed; }
@media (max-width: 1180px) { .workspace-grid, .metrics-grid, .store-matrix, .availability-panels, .availability-panels.board-mode, .skill-grid, .basic-grid { grid-template-columns: 1fr; } .weekly-board-row { grid-template-columns: 80px minmax(0, 1fr); } .weekly-board-header { grid-template-columns: 80px minmax(0, 1fr); } .weekly-board-editors { grid-column: 2; } .team-board-header, .team-board-row { grid-template-columns: 1fr; } }
@media (max-width: 768px) { .hero-panel, .hero-actions, .panel-head, .editor-actions, .relation-toolbar, .availability-row, .skill-tile, .custom-skill-row, .store-tile-top, .relation-card, .availability-card-head, .availability-editors, .weekly-board-editors, .availability-summary-chips { flex-direction: column; align-items: stretch; } .availability-event-bar { justify-content: flex-start; } .weekly-board-header, .weekly-board-row { grid-template-columns: 1fr; } .weekly-board-editors { grid-column: auto; } .weekly-board-day-head { display: none; } .team-board-days-head, .team-board-days-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .team-board-name-head { display: none; } }
</style>
