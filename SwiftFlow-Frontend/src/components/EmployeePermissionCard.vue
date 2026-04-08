<template>
  <section class="permission-card">
    <div class="card-head">
      <div>
        <h3>员工账户授权</h3>
        <p>员工通过注册创建自己的登录账号。这里用于调整该账号的权限等级、负责区域或门店范围，并在需要时重置密码。</p>
      </div>
      <div class="head-actions">
        <button
          v-if="canResetPassword"
          class="ghost-btn danger-btn"
          :disabled="isSavingReset"
          @click="resetPassword"
        >
          {{ isSavingReset ? '重置中...' : '重置密码' }}
        </button>
        <button
          v-if="canEditRole"
          class="primary-btn"
          :disabled="isSaving || !canSave"
          @click="save"
        >
          {{ isSaving ? '保存中...' : '保存业务权限' }}
        </button>
      </div>
    </div>

    <div v-if="message" class="status-banner" :class="{ error: isError }">{{ message }}</div>

    <div class="summary-row">
      <span class="soft-tag">当前员工：{{ employeeName || `#${employeeId}` }}</span>
      <span class="soft-tag">
        员工登录账号：{{ linkedUser ? `${linkedUser.full_name}（@${linkedUser.username}）` : '该员工尚未注册账号' }}
      </span>
      <span class="soft-tag">当前角色：{{ roleLabel(linkedUser?.role || 'staff') }}</span>
    </div>

    <div v-if="!linkedUser" class="inline-warning">
      该员工目前还没有自己的登录账号。请先让员工完成注册，系统会自动将该账号关联到员工档案。
    </div>

    <template v-else>
      <div v-if="isCurrentUserCard" class="inline-warning">
        当前登录账号的员工授权仅可查看，不可由本人自行修改。
      </div>

      <div class="readonly-row">
        <label>
          员工登录账号
          <input :value="linkedUser.username" disabled />
        </label>
        <label>
          账户权限等级
          <select v-model="editor.role" :disabled="!canEditRole">
            <option v-for="option in roleOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>
      </div>

      <div v-if="showAreaScope" class="scope-card">
        <div class="scope-head">
          <strong>负责区域</strong>
          <button
            v-if="editor.areaIds.length && canEditRole"
            type="button"
            class="ghost-btn mini-btn"
            @click="editor.areaIds = []"
          >
            清空区域
          </button>
        </div>
        <div class="chip-grid">
          <button
            v-for="area in areas"
            :key="area.id"
            type="button"
            class="scope-chip"
            :class="{ active: editor.areaIds.includes(area.id) }"
            :disabled="!canEditRole"
            @click="toggleArea(area.id)"
          >
            {{ area.name }}
          </button>
        </div>
      </div>

      <div v-if="showStoreScope" class="scope-card">
        <div class="scope-head">
          <strong>负责门店</strong>
          <button
            v-if="editor.storeIds.length && canEditRole"
            type="button"
            class="ghost-btn mini-btn"
            @click="editor.storeIds = []"
          >
            清空门店
          </button>
        </div>
        <div class="chip-grid">
          <button
            v-for="store in stores"
            :key="store.id"
            type="button"
            class="scope-chip"
            :class="{ active: editor.storeIds.includes(store.id) }"
            :disabled="!canEditRole"
            @click="toggleStore(store.id)"
          >
            {{ store.name }}
          </button>
        </div>
        <div v-if="storeScopeRequiredButEmpty" class="inline-warning">
          当前角色至少需要选择 1 家门店后才能保存。
        </div>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '@/lib/apiClient'

const props = defineProps({
  employeeId: {
    type: Number,
    required: true
  },
  employeeName: {
    type: String,
    default: ''
  }
})

const currentRole = ref('staff')
const currentUserId = ref(0)
const users = ref([])
const stores = ref([])
const areas = ref([])
const isSaving = ref(false)
const isSavingReset = ref(false)
const message = ref('')
const isError = ref(false)

const editor = reactive({
  role: 'staff',
  storeIds: [],
  areaIds: []
})

const linkedUser = computed(() => users.value.find(user => user.employee_id === props.employeeId) || null)
const isCurrentUserCard = computed(() => Number(linkedUser.value?.id || 0) === Number(currentUserId.value || 0))
const canManageAreas = computed(() => ['super_admin', 'admin'].includes(currentRole.value))
const canEditRole = computed(() =>
  ['super_admin', 'admin', 'area_manager'].includes(currentRole.value) &&
  Boolean(linkedUser.value) &&
  !isCurrentUserCard.value
)
const canResetPassword = computed(() =>
  ['super_admin', 'admin', 'area_manager', 'store_manager'].includes(currentRole.value) &&
  Boolean(linkedUser.value) &&
  !isCurrentUserCard.value
)
const showAreaScope = computed(() => Boolean(linkedUser.value) && editor.role === 'area_manager' && canManageAreas.value)
const showStoreScope = computed(() => Boolean(linkedUser.value) && editor.role === 'store_manager')
const storeScopeRequiredButEmpty = computed(() => currentRole.value === 'area_manager' && editor.role === 'store_manager' && !editor.storeIds.length)
const canSave = computed(() => Boolean(linkedUser.value) && canEditRole.value && !storeScopeRequiredButEmpty.value)

const roleOptions = computed(() => {
  if (canManageAreas.value) {
    return [
      { value: 'staff', label: '员工' },
      { value: 'store_manager', label: '店长' },
      { value: 'area_manager', label: '区域经理' }
    ]
  }
  return [
    { value: 'staff', label: '员工' },
    { value: 'store_manager', label: '店长' }
  ]
})

function setMessage(text, error = false) {
  message.value = text
  isError.value = error
}

function roleLabel(role) {
  if (role === 'area_manager') return '区域经理'
  if (role === 'store_manager') return '店长'
  if (role === 'staff') return '员工'
  if (role === 'admin' || role === 'super_admin') return '系统管理员'
  return role || '未设置'
}

function hydrateEditor() {
  editor.role = linkedUser.value?.role || 'staff'
  editor.storeIds = [...(linkedUser.value?.store_ids || [])]
  editor.areaIds = [...(linkedUser.value?.area_ids || [])]
}

function toggleStore(storeId) {
  if (!canEditRole.value) return
  const numericId = Number(storeId)
  editor.storeIds = editor.storeIds.includes(numericId)
    ? editor.storeIds.filter(id => id !== numericId)
    : [...editor.storeIds, numericId]
}

function toggleArea(areaId) {
  if (!canEditRole.value) return
  const numericId = Number(areaId)
  editor.areaIds = editor.areaIds.includes(numericId)
    ? editor.areaIds.filter(id => id !== numericId)
    : [...editor.areaIds, numericId]
}

async function loadData() {
  setMessage('')
  try {
    const me = await api.getMe()
    currentRole.value = me.role
    currentUserId.value = Number(me.id || 0)
    const requests = [api.getUsers(), api.getStores()]
    requests.push(canManageAreas.value ? api.getAreas() : Promise.resolve([]))
    const [userData, storeData, areaData] = await Promise.all(requests)
    users.value = userData || []
    stores.value = storeData || []
    areas.value = areaData || []
    hydrateEditor()
  } catch (error) {
    setMessage(error.message || '加载授权数据失败。', true)
  }
}

async function save() {
  if (!canSave.value || !linkedUser.value) return
  isSaving.value = true
  setMessage('')
  try {
    const userId = linkedUser.value.id
    const previousRole = linkedUser.value.role
    const storeIds = editor.storeIds.map(Number)
    const areaIds = editor.areaIds.map(Number)

    if (canManageAreas.value && previousRole === 'area_manager' && editor.role !== 'area_manager') {
      await api.updateUserAreaAccess(userId, { area_ids: [] })
    }

    await api.updateUserRole(userId, {
      role: editor.role,
      store_ids: editor.role === 'store_manager' ? storeIds : []
    })

    if (canManageAreas.value && editor.role === 'area_manager') {
      await api.updateUserAreaAccess(userId, { area_ids: areaIds })
    }

    await loadData()
    setMessage('员工业务权限已更新。')
  } catch (error) {
    setMessage(error.message || '保存业务权限失败。', true)
  } finally {
    isSaving.value = false
  }
}

async function resetPassword() {
  if (!canResetPassword.value || !linkedUser.value) return
  const confirmed = window.confirm('是否确认将该员工密码重置为默认密码（Qwerty1234）？')
  if (!confirmed) return
  isSavingReset.value = true
  setMessage('')
  try {
    const result = await api.resetUserPassword(linkedUser.value.id)
    setMessage(result.message || '密码已重置为默认密码 Qwerty1234')
  } catch (error) {
    setMessage(error.message || '重置密码失败。', true)
  } finally {
    isSavingReset.value = false
  }
}

watch(() => props.employeeId, loadData)
onMounted(loadData)
</script>

<style scoped>
.permission-card {
  display: grid;
  gap: 14px;
}

.card-head,
.scope-head,
.summary-row,
.head-actions {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
  flex-wrap: wrap;
}

.card-head h3 {
  margin: 0;
  color: var(--color-heading);
}

.card-head p {
  margin: 4px 0 0;
  color: var(--color-text-soft);
  font-size: 13px;
}

.status-banner {
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(234, 248, 238, 0.92);
  color: #2f6d47;
}

.status-banner.error {
  background: rgba(253, 236, 233, 0.92);
  color: #933a2f;
}

.soft-tag {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(244, 123, 76, 0.1);
  color: var(--color-primary-dark);
  font-size: 12px;
  font-weight: 700;
}

.readonly-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.readonly-row label {
  display: grid;
  gap: 6px;
  color: var(--color-text-soft);
  font-size: 13px;
}

.scope-card {
  display: grid;
  gap: 10px;
  padding: 14px;
  border-radius: 16px;
  background: rgba(255, 252, 248, 0.95);
  border: 1px solid rgba(244, 123, 76, 0.14);
}

.chip-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.scope-chip {
  display: inline-flex;
  align-items: center;
  padding: 10px 12px;
  border-radius: 999px;
  border: 1px solid rgba(223, 200, 171, 0.85);
  background: rgba(248, 240, 230, 0.94);
}

.scope-chip.active {
  background: rgba(255, 232, 209, 0.96);
  border-color: rgba(238, 117, 52, 0.4);
}

.inline-warning {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 245, 235, 0.92);
  color: var(--color-text-soft);
}

.mini-btn {
  min-height: 34px;
  padding: 0 12px;
}

@media (max-width: 900px) {
  .readonly-row {
    grid-template-columns: 1fr;
  }
}
</style>
