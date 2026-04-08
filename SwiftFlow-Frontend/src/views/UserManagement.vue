<template>
  <div class="user-admin-page">
    <section class="hero-panel user-hero">
      <div class="hero-copy">
        <p class="eyebrow">权限管理</p>
        <h1>统一设置账号角色、区域范围、门店范围与员工绑定</h1>
        <p>
          当前页支持重新设置权限。管理员可以直接清空并重配区域或门店授权；区域经理只能在自己负责的范围内，把账号设为店长并分配门店。
        </p>
      </div>
      <div class="hero-actions">
        <span class="role-chip">{{ currentRoleLabel }}</span>
        <button class="ghost-btn" :disabled="isLoading" @click="loadData">
          {{ isLoading ? '刷新中...' : '刷新数据' }}
        </button>
      </div>
    </section>

    <div v-if="message" class="status-banner" :class="{ error: isError }">
      {{ message }}
    </div>

    <section class="metrics-grid">
      <article class="metric-card">
        <span class="metric-label">账号总数</span>
        <strong class="metric-value">{{ users.length }}</strong>
      </article>
      <article class="metric-card">
        <span class="metric-label">区域经理</span>
        <strong class="metric-value">{{ roleCount('area_manager') }}</strong>
      </article>
      <article class="metric-card">
        <span class="metric-label">店长</span>
        <strong class="metric-value">{{ roleCount('store_manager') }}</strong>
      </article>
      <article class="metric-card accent">
        <span class="metric-label">已绑定员工</span>
        <strong class="metric-value">{{ boundEmployeeCount }}</strong>
      </article>
    </section>

    <section class="workspace-grid">
      <aside class="panel-shell user-list-panel">
        <div class="panel-head stacked">
          <div>
            <h2>账号列表</h2>
            <p>按姓名、账号和角色筛选，先选中账号，再在右侧调整权限。</p>
          </div>

          <div class="quick-filters">
            <input
              v-model.trim="searchText"
              class="search-input"
              placeholder="搜索账号或姓名"
            />
            <select v-model="roleFilter">
              <option value="all">全部角色</option>
              <option value="admin">系统管理员</option>
              <option value="area_manager">区域经理</option>
              <option value="store_manager">店长</option>
              <option value="staff">员工</option>
              <option value="developer">开发维护</option>
            </select>
          </div>
        </div>

        <div class="role-overview">
          <button
            v-for="group in roleGroups"
            :key="group.value"
            class="mini-filter"
            :class="{ active: roleFilter === group.value }"
            @click="roleFilter = group.value"
          >
            <strong>{{ group.label }}</strong>
            <span>{{ group.count }}</span>
          </button>
        </div>

        <div class="user-list">
          <button
            v-for="user in filteredUsers"
            :key="user.id"
            class="user-card"
            :class="{ active: user.id === selectedUserId }"
            @click="selectUser(user)"
          >
            <div class="user-card-top">
              <div>
                <strong>{{ user.full_name }}</strong>
                <p>@{{ user.username }}</p>
              </div>
              <span class="role-badge" :class="user.role">{{ roleLabel(user.role) }}</span>
            </div>
            <div class="user-scope">
              <span>区域 {{ user.area_ids?.length || 0 }}</span>
              <span>门店 {{ user.store_ids?.length || 0 }}</span>
              <span>{{ user.employee_id ? '已绑定员工' : '未绑定员工' }}</span>
            </div>
          </button>

          <div v-if="!filteredUsers.length" class="empty-block">当前筛选条件下没有匹配账号。</div>
        </div>
      </aside>

      <main class="panel-shell editor-panel">
        <div class="panel-head">
          <div>
            <h2>{{ selectedUser ? `编辑账号：${selectedUser.full_name}` : '选择一个账号开始设置' }}</h2>
            <p>如果需要重新设置权限，可以先清空区域或门店授权，再按新的范围重新勾选并保存。</p>
          </div>
          <button v-if="selectedUser" class="ghost-btn" @click="resetEditor">恢复当前保存状态</button>
        </div>

        <template v-if="selectedUser">
          <section class="section-card">
            <div class="section-head">
              <div>
                <h3>账号概览</h3>
                <p>先确认当前角色和覆盖范围，再决定是重设角色还是只调整授权范围。</p>
              </div>
              <span class="soft-tag">{{ selectedUser.username }}</span>
            </div>

            <div class="summary-grid">
              <div>
                <span class="summary-label">当前角色</span>
                <strong>{{ roleLabel(selectedUser.role) }}</strong>
              </div>
              <div>
                <span class="summary-label">区域授权</span>
                <strong>{{ formatNames(selectedAreaNames) }}</strong>
              </div>
              <div>
                <span class="summary-label">门店授权</span>
                <strong>{{ formatNames(selectedStoreNames) }}</strong>
              </div>
              <div>
                <span class="summary-label">员工绑定</span>
                <strong>{{ selectedEmployeeName || '未绑定' }}</strong>
              </div>
            </div>
          </section>

          <section class="section-card">
            <div class="section-head">
              <div>
                <h3>角色与权限范围</h3>
                <p>管理员可清空后重配；区域经理仅能在自己的范围内设置店长并分配门店。</p>
              </div>
              <button class="primary-btn" :disabled="isSavingRole || !canSaveRoleSection" @click="saveRoleSection">
                {{ isSavingRole ? '保存中...' : '保存角色与范围' }}
              </button>
            </div>

            <div class="form-grid one-col">
              <label>
                角色
                <select v-model="editor.role" :disabled="!canEditRole">
                  <option v-for="option in roleOptions" :key="option.value" :value="option.value">
                    {{ option.label }}
                  </option>
                </select>
              </label>
            </div>

            <div class="helper-strip">
              <span class="helper-chip">可分配区域 {{ availableAreas.length }}</span>
              <span class="helper-chip">可分配门店 {{ availableStores.length }}</span>
            </div>

            <div v-if="showAreaScope" class="scope-card">
              <div class="scope-head">
                <div>
                  <h4>区域授权</h4>
                  <p>点击卡片即可选中或取消。管理员可先清空，再重新分配新的区域范围。</p>
                </div>
                <button
                  v-if="editor.areaIds.length"
                  type="button"
                  class="ghost-btn small-btn"
                  @click="clearAreas"
                >
                  清空区域授权
                </button>
              </div>

              <div class="chip-grid">
                <button
                  v-for="area in availableAreas"
                  :key="area.id"
                  class="scope-chip"
                  :class="{ active: editor.areaIds.includes(area.id) }"
                  type="button"
                  @click="toggleArea(area.id)"
                >
                  <span>{{ area.name }}</span>
                </button>
              </div>

              <div v-if="!availableAreas.length" class="inline-empty">当前没有可分配的区域。</div>
            </div>

            <div v-if="showStoreScope" class="scope-card">
              <div class="scope-head">
                <div>
                  <h4>门店授权</h4>
                  <p>点击卡片即可选中或取消。若要重设店长权限，可先清空门店，再按新的范围重选。</p>
                </div>
                <button
                  v-if="editor.storeIds.length"
                  type="button"
                  class="ghost-btn small-btn"
                  @click="clearStores"
                >
                  清空门店授权
                </button>
              </div>

              <div class="chip-grid">
                <button
                  v-for="store in availableStores"
                  :key="store.id"
                  class="scope-chip"
                  :class="{ active: editor.storeIds.includes(store.id) }"
                  type="button"
                  @click="toggleStore(store.id)"
                >
                  <span>{{ store.name }}</span>
                </button>
              </div>

              <div v-if="!availableStores.length" class="inline-empty">当前范围下没有可分配门店。</div>
            </div>

            <div v-if="storeScopeRequiredButEmpty" class="inline-warning">
              当前角色下至少需要选择 1 家门店后才能保存。
            </div>
          </section>

          <section v-if="canBindEmployee" class="section-card">
            <div class="section-head">
              <div>
                <h3>员工档案绑定</h3>
                <p>绑定后，该账号即可与员工档案关联，用于员工自助查看排班与修改可上班时间。</p>
              </div>
              <button class="primary-btn" :disabled="isSavingBinding" @click="saveEmployeeBinding">
                {{ isSavingBinding ? '保存中...' : '保存员工绑定' }}
              </button>
            </div>

            <div class="form-grid one-col">
              <label>
                绑定员工
                <select v-model="editor.employeeId">
                  <option :value="null">未绑定</option>
                  <option v-for="employee in employeeOptions" :key="employee.id" :value="employee.id">
                    {{ employee.name }}
                  </option>
                </select>
              </label>
            </div>
          </section>
        </template>

        <div v-else class="empty-state">
          <h3>还没有选中账号</h3>
          <p>请先从左侧选择一个账号，再在这里调整角色、区域、门店或员工绑定。</p>
        </div>
      </main>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api, getCurrentRole } from '@/lib/apiClient'

const users = ref([])
const stores = ref([])
const employees = ref([])
const areas = ref([])
const selectedUserId = ref(null)
const searchText = ref('')
const roleFilter = ref('all')
const isLoading = ref(false)
const isSavingRole = ref(false)
const isSavingBinding = ref(false)
const message = ref('')
const isError = ref(false)

const editor = reactive({
  role: 'staff',
  storeIds: [],
  areaIds: [],
  employeeId: null
})

const currentRole = computed(() => getCurrentRole() || 'staff')
const canBindEmployee = computed(() => ['super_admin', 'admin'].includes(currentRole.value))
const canEditRole = computed(() => ['super_admin', 'admin', 'area_manager'].includes(currentRole.value))
const currentRoleLabel = computed(() => roleLabel(currentRole.value))

const roleGroups = computed(() => [
  { value: 'all', label: '全部', count: users.value.length },
  { value: 'admin', label: '管理员', count: roleCount('admin') + roleCount('super_admin') },
  { value: 'area_manager', label: '区域经理', count: roleCount('area_manager') },
  { value: 'store_manager', label: '店长', count: roleCount('store_manager') },
  { value: 'staff', label: '员工', count: roleCount('staff') },
  { value: 'developer', label: '开发维护', count: roleCount('developer') }
])

const filteredUsers = computed(() =>
  users.value.filter(user => {
    if (roleFilter.value !== 'all' && user.role !== roleFilter.value) return false
    const keyword = searchText.value.trim().toLowerCase()
    if (!keyword) return true
    return `${user.username} ${user.full_name}`.toLowerCase().includes(keyword)
  })
)

const selectedUser = computed(() => users.value.find(item => item.id === selectedUserId.value) || null)
const boundEmployeeCount = computed(() => users.value.filter(user => user.employee_id).length)

const roleOptions = computed(() => {
  if (['super_admin', 'admin'].includes(currentRole.value)) {
    return [
      { value: 'admin', label: '系统管理员' },
      { value: 'area_manager', label: '区域经理' },
      { value: 'store_manager', label: '店长' },
      { value: 'staff', label: '员工' },
      { value: 'developer', label: '开发维护' }
    ]
  }

  return [
    { value: 'store_manager', label: '店长' },
    { value: 'staff', label: '员工' }
  ]
})

const showAreaScope = computed(
  () => ['super_admin', 'admin'].includes(currentRole.value) && editor.role === 'area_manager'
)

const showStoreScope = computed(
  () => ['super_admin', 'admin', 'area_manager'].includes(currentRole.value) && editor.role === 'store_manager'
)

const availableAreas = computed(() => areas.value)
const availableStores = computed(() => stores.value)

const storeScopeRequiredButEmpty = computed(
  () => currentRole.value === 'area_manager' && editor.role === 'store_manager' && !editor.storeIds.length
)

const canSaveRoleSection = computed(() => {
  if (!selectedUser.value || !canEditRole.value) return false
  if (storeScopeRequiredButEmpty.value) return false
  return true
})

const selectedAreaNames = computed(() =>
  areas.value.filter(area => selectedUser.value?.area_ids?.includes(area.id)).map(area => area.name)
)

const selectedStoreNames = computed(() =>
  stores.value.filter(store => selectedUser.value?.store_ids?.includes(store.id)).map(store => store.name)
)

const selectedEmployeeName = computed(
  () => employees.value.find(employee => employee.id === selectedUser.value?.employee_id)?.name || ''
)

const employeeOptions = computed(() =>
  employees.value
    .filter(employee => !users.value.some(user => user.employee_id === employee.id && user.id !== selectedUser.value?.id))
    .sort((a, b) => a.name.localeCompare(b.name, 'zh-Hans-CN'))
)

function roleCount(roleCode) {
  return users.value.filter(user => user.role === roleCode).length
}

function roleLabel(roleCode) {
  if (roleCode === 'super_admin' || roleCode === 'admin') return '系统管理员'
  if (roleCode === 'area_manager') return '区域经理'
  if (roleCode === 'store_manager') return '店长'
  if (roleCode === 'staff') return '员工'
  if (roleCode === 'developer') return '开发维护'
  return roleCode || '未知角色'
}

function formatNames(names) {
  return names?.length ? names.join('、') : '未设置'
}

function setMessage(text, error = false) {
  message.value = text
  isError.value = error
}

function hydrateEditor(user) {
  editor.role = user.role
  editor.storeIds = [...(user.store_ids || [])]
  editor.areaIds = [...(user.area_ids || [])]
  editor.employeeId = user.employee_id ?? null
}

function selectUser(user) {
  selectedUserId.value = user.id
  hydrateEditor(user)
}

function resetEditor() {
  if (!selectedUser.value) return
  hydrateEditor(selectedUser.value)
  setMessage('已恢复为当前账号的保存状态。')
}

function toggleStore(storeId) {
  const numericId = Number(storeId)
  editor.storeIds = editor.storeIds.includes(numericId)
    ? editor.storeIds.filter(id => Number(id) !== numericId)
    : [...editor.storeIds, numericId]
}

function toggleArea(areaId) {
  const numericId = Number(areaId)
  editor.areaIds = editor.areaIds.includes(numericId)
    ? editor.areaIds.filter(id => Number(id) !== numericId)
    : [...editor.areaIds, numericId]
}

function clearStores() {
  editor.storeIds = []
}

function clearAreas() {
  editor.areaIds = []
}

async function loadData() {
  isLoading.value = true
  setMessage('')
  try {
    const requests = [api.getUsers(), api.getStores(), api.getEmployees()]
    if (['super_admin', 'admin', 'area_manager'].includes(currentRole.value)) {
      requests.push(api.getAreas())
    } else {
      requests.push(Promise.resolve([]))
    }

    const [userData, storeData, employeeData, areaData] = await Promise.all(requests)
    users.value = userData || []
    stores.value = storeData || []
    employees.value = employeeData || []
    areas.value = areaData || []

    if (selectedUserId.value) {
      const refreshed = users.value.find(user => user.id === selectedUserId.value)
      if (refreshed) {
        hydrateEditor(refreshed)
      } else {
        selectedUserId.value = null
      }
    }

    if (!selectedUserId.value && users.value.length) {
      selectUser(users.value[0])
    }
  } catch (error) {
    setMessage(error.message || '加载权限数据失败。', true)
  } finally {
    isLoading.value = false
  }
}

async function saveRoleSection() {
  if (!selectedUser.value) return

  isSavingRole.value = true
  setMessage('')
  try {
    const normalizedStoreIds = editor.storeIds.map(id => Number(id))
    const normalizedAreaIds = editor.areaIds.map(id => Number(id))

    const updatedUser = await api.updateUserRole(selectedUser.value.id, {
      role: editor.role,
      store_ids: editor.role === 'store_manager' ? normalizedStoreIds : []
    })

    if (['super_admin', 'admin'].includes(currentRole.value)) {
      if (editor.role === 'area_manager') {
        await api.updateUserAreaAccess(selectedUser.value.id, { area_ids: normalizedAreaIds })
      } else if (selectedUser.value.area_ids?.length) {
        await api.updateUserAreaAccess(selectedUser.value.id, { area_ids: [] })
      }
    }

    if (['super_admin', 'admin', 'area_manager'].includes(currentRole.value) && editor.role === 'store_manager') {
      await api.updateUserStoreAccess(selectedUser.value.id, { store_ids: normalizedStoreIds })
    }

    await loadData()
    selectedUserId.value = updatedUser.id
    setMessage('角色与权限范围已更新。')
  } catch (error) {
    setMessage(error.message || '保存角色权限失败。', true)
  } finally {
    isSavingRole.value = false
  }
}

async function saveEmployeeBinding() {
  if (!selectedUser.value) return
  isSavingBinding.value = true
  setMessage('')
  try {
    await api.updateUserEmployeeBinding(selectedUser.value.id, {
      employee_id: editor.employeeId ?? null
    })
    await loadData()
    setMessage('员工档案绑定已更新。')
  } catch (error) {
    setMessage(error.message || '保存员工绑定失败。', true)
  } finally {
    isSavingBinding.value = false
  }
}

watch(
  () => editor.role,
  (nextRole) => {
    if (nextRole !== 'area_manager') {
      editor.areaIds = []
    }
    if (nextRole !== 'store_manager') {
      editor.storeIds = []
    }
  }
)

onMounted(loadData)
</script>

<style scoped>
.user-admin-page { display: grid; gap: 20px; }
.user-hero { display: flex; justify-content: space-between; gap: 20px; align-items: flex-start; }
.hero-copy { max-width: 820px; line-height: 1.7; color: var(--color-text-soft); }
.hero-actions { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.role-chip { display: inline-flex; align-items: center; padding: 8px 12px; border-radius: 999px; background: rgba(238, 117, 52, 0.14); color: var(--color-primary-dark); font-weight: 700; }
.metrics-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.metric-card { padding: 18px; border-radius: 22px; background: rgba(255, 255, 255, 0.85); border: 1px solid rgba(230, 207, 176, 0.8); box-shadow: 0 18px 34px rgba(170, 135, 94, 0.08); }
.metric-card.accent { background: linear-gradient(135deg, rgba(255, 173, 96, 0.18), rgba(255, 255, 255, 0.94)); }
.metric-label { display: block; color: var(--color-text-soft); font-size: 13px; }
.metric-value { display: block; margin-top: 6px; font-size: 32px; }
.workspace-grid { display: grid; grid-template-columns: 360px minmax(0, 1fr); gap: 18px; }
.panel-shell { background: rgba(255, 255, 255, 0.86); border: 1px solid rgba(230, 207, 176, 0.85); border-radius: 26px; box-shadow: 0 20px 40px rgba(165, 124, 77, 0.08); padding: 20px; }
.panel-head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 18px; }
.panel-head.stacked { flex-direction: column; }
.panel-head h2, .section-head h3, .scope-head h4 { margin: 0; }
.panel-head p, .section-head p, .scope-head p { margin: 6px 0 0; color: var(--color-text-soft); line-height: 1.6; }
.quick-filters { display: grid; gap: 10px; width: 100%; }
.role-overview { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; }
.mini-filter { display: inline-flex; align-items: center; gap: 8px; padding: 8px 10px; border: 1px solid rgba(223, 200, 171, 0.85); border-radius: 999px; background: rgba(248, 240, 230, 0.94); color: var(--color-text); }
.mini-filter.active { background: rgba(255, 232, 209, 0.96); border-color: rgba(238, 117, 52, 0.4); }
.search-input, select { width: 100%; border: 1px solid rgba(221, 199, 166, 0.95); border-radius: 14px; padding: 12px 14px; background: rgba(255, 252, 248, 0.92); color: var(--color-text); }
.user-list { display: grid; gap: 12px; }
.user-card { border: 1px solid rgba(225, 203, 174, 0.9); border-radius: 18px; padding: 14px; background: rgba(255, 251, 247, 0.94); text-align: left; display: grid; gap: 10px; }
.user-card.active { border-color: rgba(238, 117, 52, 0.55); box-shadow: 0 14px 26px rgba(238, 117, 52, 0.12); background: linear-gradient(180deg, rgba(255, 241, 230, 0.96), rgba(255, 255, 255, 0.96)); }
.user-card-top { display: flex; justify-content: space-between; gap: 12px; }
.user-card-top p { margin: 4px 0 0; color: var(--color-text-soft); }
.role-badge, .soft-tag, .helper-chip { display: inline-flex; align-items: center; padding: 6px 10px; border-radius: 999px; background: rgba(45, 104, 79, 0.1); color: #24543f; font-size: 12px; font-weight: 700; }
.role-badge.admin, .role-badge.super_admin { background: rgba(34, 93, 76, 0.12); }
.role-badge.area_manager { background: rgba(255, 188, 111, 0.22); color: #8a5317; }
.role-badge.store_manager { background: rgba(89, 138, 214, 0.18); color: #245289; }
.role-badge.staff { background: rgba(140, 153, 168, 0.18); color: #46505e; }
.role-badge.developer { background: rgba(147, 114, 236, 0.16); color: #5c3dac; }
.helper-strip, .user-scope { display: flex; gap: 10px; flex-wrap: wrap; }
.user-scope { color: var(--color-text-soft); font-size: 13px; }
.editor-panel, .section-card { display: grid; gap: 16px; }
.section-card { padding: 18px; border-radius: 22px; background: rgba(255, 252, 248, 0.92); border: 1px solid rgba(231, 208, 176, 0.82); }
.section-head, .scope-head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.summary-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.summary-grid > div { padding: 14px; border-radius: 16px; background: rgba(255, 255, 255, 0.88); border: 1px solid rgba(232, 212, 185, 0.8); }
.summary-label { display: block; color: var(--color-text-soft); font-size: 13px; margin-bottom: 6px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.form-grid.one-col { grid-template-columns: 1fr; }
.form-grid label { display: grid; gap: 8px; color: var(--color-text-soft); }
.scope-card { display: grid; gap: 14px; padding: 16px; border-radius: 18px; background: rgba(255, 255, 255, 0.82); border: 1px solid rgba(229, 210, 184, 0.85); }
.chip-grid { display: flex; flex-wrap: wrap; gap: 10px; }
.scope-chip { display: inline-flex; align-items: center; gap: 8px; padding: 10px 12px; border-radius: 999px; background: rgba(248, 240, 230, 0.94); border: 1px solid rgba(223, 200, 171, 0.85); cursor: pointer; }
.scope-chip.active { background: rgba(255, 232, 209, 0.96); border-color: rgba(238, 117, 52, 0.4); }
.small-btn { padding: 8px 12px; font-size: 12px; border-radius: 999px; white-space: nowrap; }
.inline-warning { padding: 12px 14px; border-radius: 14px; background: rgba(255, 235, 214, 0.9); color: #8a5317; border: 1px solid rgba(238, 117, 52, 0.18); }
.status-banner { padding: 14px 16px; border-radius: 16px; background: rgba(35, 106, 71, 0.1); color: #1f5c42; }
.status-banner.error { background: rgba(200, 68, 68, 0.12); color: #8f2f2f; }
.empty-block, .empty-state, .inline-empty { padding: 20px; border-radius: 18px; background: rgba(255, 250, 244, 0.92); color: var(--color-text-soft); text-align: center; }
.empty-state h3 { margin: 0 0 8px; }
@media (max-width: 1080px) {
  .metrics-grid,
  .workspace-grid,
  .summary-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }
  .user-hero,
  .section-head,
  .scope-head,
  .panel-head {
    flex-direction: column;
  }
}
</style>
