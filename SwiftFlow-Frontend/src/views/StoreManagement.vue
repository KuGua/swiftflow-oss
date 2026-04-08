<template>
  <div class="store-page">
    <section class="hero panel-shell">
      <div>
        <p class="eyebrow">店铺管理</p>
        <h1>把门店、区域、需求和规则放进同一个工作台</h1>
        <p class="muted">支持把门店卡片拖到区域区块里完成归属调整，也支持新建区域区块。</p>
      </div>
      <div class="hero-actions">
        <span class="role-chip">{{ roleLabel }}</span>
        <button class="btn ghost" @click="refreshWorkspace">刷新</button>
              <button v-if="canCreateStore" class="btn primary" @click="startCreate">新增门店</button>
      </div>
    </section>

    <div v-if="message" class="status-banner" :class="{ error: isError }">{{ message }}</div>

    <section class="metrics-grid">
      <article class="metric-card panel-shell"><span>门店数量</span><strong>{{ stores.length }}</strong></article>
      <article class="metric-card panel-shell"><span>区域数量</span><strong>{{ areas.length }}</strong></article>
      <article class="metric-card panel-shell"><span>当前门店</span><strong class="small">{{ selectedStore?.name || '未选择' }}</strong></article>
    </section>

    <section v-if="canManageStore" class="panel-shell">
      <div class="panel-head">
        <div>
          <h2>区域看板</h2>
          <p class="muted">拖拽门店卡片到区域区块，或先选中门店后点击区域区块完成归属调整。</p>
        </div>
        <div v-if="canManageStore" class="inline-create">
          <input v-model.trim="newAreaName" maxlength="40" placeholder="输入新区域名称" @keyup.enter="createArea" />
          <button class="btn primary inline-create-btn" :disabled="isSavingArea || !newAreaName" @click="createArea">{{ isSavingArea ? '创建中...' : '新建区域' }}</button>
        </div>
      </div>

      <div class="area-board">
        <article class="area-zone" :class="{ active: activeAreaId === 'unassigned', disabled: !canEditProfile }" @dragover.prevent @drop="onAreaDrop(null)" @click="selectedStore && assignStoreArea(selectedStore, null)">
          <div class="zone-head"><div><strong>未分配区域</strong><p>适合新店或待归类门店</p></div><span class="area-count">{{ unassignedStores.length }}</span></div>
          <div class="chip-list">
            <button v-for="store in unassignedStores" :key="`u-${store.id}`" class="store-chip" :class="{ selected: String(store.id) === selectedStoreId }" draggable="true" @dragstart="onStoreDragStart(store)" @click.stop="selectStore(store.id)">{{ store.name }}</button>
            <span v-if="!unassignedStores.length" class="empty-inline">暂无门店</span>
          </div>
        </article>

        <article v-for="area in areas" :key="area.id" class="area-zone" :class="{ active: String(activeAreaId) === String(area.id), disabled: !canEditProfile }" @dragover.prevent @drop="onAreaDrop(area.id)" @click="selectedStore && assignStoreArea(selectedStore, area.id)">
          <div class="zone-head">
            <div><strong>{{ area.name }}</strong><p>拖拽或点击为当前门店分配</p></div>
            <div class="zone-tools">
              <span class="area-count">{{ storesInArea(area.id).length }}</span>
              <button v-if="canManageStore" class="zone-icon-btn" title="编辑区域" @click.stop="editArea(area)">编辑</button>
              <button v-if="canManageStore" class="zone-icon-btn danger" title="删除区域" @click.stop="removeArea(area)">删除</button>
            </div>
          </div>
          <div class="chip-list">
            <button v-for="store in storesInArea(area.id)" :key="`${area.id}-${store.id}`" class="store-chip" :class="{ selected: String(store.id) === selectedStoreId }" draggable="true" @dragstart="onStoreDragStart(store)" @click.stop="selectStore(store.id)">{{ store.name }}</button>
            <span v-if="!storesInArea(area.id).length" class="empty-inline">将门店拖到这里</span>
          </div>
        </article>
      </div>
    </section>

    <section class="workspace-grid" :class="{ 'admin-workspace': isAdminView }">
      <aside class="panel-shell roster-shell" :class="{ 'admin-roster-shell': isAdminView }" :style="adminRosterShellStyle">
        <div class="panel-head stacked">
          <div><h2>门店目录</h2><p class="muted">列表卡片可直接拖动到上方区域看板。</p></div>
          <div class="filter-bar">
            <select v-model="areaFilter">
              <option value="all">全部区域</option>
              <option value="unassigned">未分配区域</option>
              <option v-for="area in areas" :key="area.id" :value="String(area.id)">{{ area.name }}</option>
            </select>
            <input v-model.trim="storeSearch" placeholder="搜索门店名称" />
          </div>
        </div>
        <div class="store-list">
          <button v-for="store in filteredStores" :key="store.id" class="store-card" :class="{ active: String(store.id) === selectedStoreId }" draggable="true" @dragstart="onStoreDragStart(store)" @click="selectStore(store.id)">
            <div class="row between"><strong>{{ store.name }}</strong><span class="soft-tag">{{ store.open_time }} - {{ store.close_time }}</span></div>
            <div class="row between muted small-text"><span>{{ getAreaName(store.area_id) }}</span><span>{{ demandSlotCountForStore(store) }} 个需求时段</span></div>
          </button>
          <div v-if="!filteredStores.length" class="empty-block">当前筛选条件下没有门店。</div>
        </div>
      </aside>

      <main class="editor-stack" :class="{ 'admin-editor-stack': isAdminView }">
        <section ref="adminEditorCard" class="panel-shell">
          <div class="panel-head">
            <div><h2>{{ editingId ? '编辑门店' : '新建门店草稿' }}</h2><p class="muted">区域归属可从上方看板拖拽调整，这里维护门店基础信息和营业时间。</p></div>
            <div class="editor-actions">
              <button v-if="editingId && canCreateStore" class="btn ghost danger" @click="removeStore(selectedStore)">删除</button>
              <button class="btn ghost" @click="resetForm">重置</button>
              <button class="btn primary" :disabled="isSaving || !canSubmit" @click="saveStore">{{ isSaving ? '保存中...' : editingId ? '保存门店信息' : '创建门店' }}</button>
            </div>
          </div>

          <div class="form-grid">
            <label>店铺名称<input v-model="form.name" :disabled="!canEditStoreNameField" placeholder="例如：示例店A" /></label>
            <label>所属区域<select v-model="form.area_id" :disabled="!canEditStoreArea"><option :value="null">未分配区域</option><option v-for="area in areas" :key="area.id" :value="area.id">{{ area.name }}</option></select></label>
            <label>开店时间<input v-model="form.open_time" type="time" :disabled="!canEditStoreHours" /></label>
            <label>关店时间<input v-model="form.close_time" type="time" :disabled="!canEditStoreHours" /></label>
          </div>

          <div class="summary-strip compact-summary">
            <div class="summary-chip"><span>当前区域</span><strong>{{ getAreaName(form.area_id) }}</strong></div>
          </div>
        </section>

        <section v-if="showDemandSection" class="panel-shell">
          <div class="panel-head">
            <div><h2>人力需求基线</h2><p class="muted">工作日与周末共用一张矩阵，按营业时段填写每小时最低需求。</p></div>
            <div class="editor-actions">
              <button class="btn ghost" :disabled="!selectedStoreId" @click="loadStaffingDemand">重载需求</button>
              <button class="btn primary" :disabled="!selectedStoreId || !canEditConfig || isSavingDemand" @click="saveStaffingDemand">{{ isSavingDemand ? '保存中...' : '保存需求' }}</button>
            </div>
          </div>
          <div v-if="!selectedStore" class="empty-block">请先从左侧选择门店。</div>
          <div v-else class="demand-wrap">
            <table class="demand-table">
              <thead><tr><th>日期类型</th><th v-for="hour in demandHours" :key="hour">{{ formatHourSlot(hour) }}</th></tr></thead>
              <tbody>
                <tr v-for="dayType in dayTypes" :key="dayType.key">
                  <td class="day-cell">{{ dayType.label }}</td>
                  <td v-for="hour in demandHours" :key="`${dayType.key}-${hour}`"><input v-model.number="demandGrid[dayType.key][hour]" class="demand-input" type="number" min="0" step="1" :disabled="!canEditConfig" /></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section v-if="showRuleSection" class="panel-shell">
          <div class="panel-head">
            <div><h2>排班规则</h2><p class="muted">把算法关键约束配置到门店层级，便于不同门店按实际运营方式运转。</p></div>
            <div class="editor-actions">
              <button class="btn ghost" :disabled="!selectedStoreId" @click="loadRuleConfig">閲嶈浇瑙勫垯</button>
              <button class="btn primary" :disabled="!selectedStoreId || !canEditConfig || isSavingRuleConfig" @click="saveRuleConfig">{{ isSavingRuleConfig ? '保存中...' : '保存规则' }}</button>
            </div>
          </div>
          <div v-if="!selectedStore" class="empty-block">请先从左侧选择门店。</div>
          <div v-else class="rules-grid">
            <label>排班原型<select v-model="ruleConfig.schedule_archetype" :disabled="!canEditConfig"><option value="auto">自动识别</option><option value="peak_dual_core">高峰双核心</option><option value="light_single_core">轻量核心</option><option value="standard_dual_shift">标准双班</option><option value="flex_grid">弹性网格</option><option value="midweight_dual_role">中量双岗</option><option value="weekend_peak">周末高峰型</option></select></label>
            <label>工作日总工时上限<input v-model.number="ruleConfig.weekday_total_hours_limit" type="number" min="1" step="1" :disabled="!canEditConfig" /></label>
            <label>周末总工时上限<input v-model.number="ruleConfig.weekend_total_hours_limit" type="number" min="1" step="1" :disabled="!canEditConfig" /></label>
            <label>每小时最少后场人数<input v-model.number="ruleConfig.min_backroom_per_hour" type="number" min="0" step="1" :disabled="!canEditConfig" /></label>
            <label>开店最少钥匙人数<input v-model.number="ruleConfig.min_opening_keyholders" type="number" min="0" step="1" :disabled="!canEditConfig" /></label>
            <label>关店最少钥匙人数<input v-model.number="ruleConfig.min_closing_keyholders" type="number" min="0" step="1" :disabled="!canEditConfig" /></label>
            <label>门店钥匙总数<input v-model.number="ruleConfig.store_key_count" type="number" min="0" step="1" :disabled="!canEditConfig" /></label>
            <label class="toggle-card full-span"><div><strong>开店要求前后场双技能</strong><small>开启后，开店班至少需要一名同时具备前场与后场能力的员工。</small></div><span class="toggle-state" :class="{ active: ruleConfig.require_opening_dual_skill }">{{ ruleConfig.require_opening_dual_skill ? '已开启' : '未开启' }}</span><input v-model="ruleConfig.require_opening_dual_skill" type="checkbox" :disabled="!canEditConfig" /></label>
          </div>
        </section>
      </main>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '@/lib/apiClient'

const stores = ref([]), areas = ref([]), currentRole = ref('store_manager'), message = ref(''), isError = ref(false)
const isSaving = ref(false), isSavingArea = ref(false), isSavingDemand = ref(false), isSavingRuleConfig = ref(false), isAssigningArea = ref(false)
const editingId = ref(null), selectedStoreId = ref(''), areaFilter = ref('all'), storeSearch = ref(''), draggingStoreId = ref(null), newAreaName = ref('')
const adminEditorCard = ref(null)
const adminRosterHeight = ref(null)
let adminEditorObserver = null
const dayTypes = [{ key: 'weekday', label: '工作日' }, { key: 'weekend', label: '周末' }]
const emptyForm = () => ({ name: '', area_id: null, open_time: '09:00', close_time: '23:00' })
const defaultRuleConfig = () => ({ schedule_archetype: 'auto', weekday_total_hours_limit: 40, weekend_total_hours_limit: 45, sg_part_time_min_hours: 80, sg_part_time_target_hours: 160, target_160_last_week_days: 7, min_backroom_per_hour: 1, require_opening_dual_skill: true, min_opening_keyholders: 1, min_closing_keyholders: 1, store_key_count: 0 })
const form = ref(emptyForm()), ruleConfig = ref(defaultRuleConfig()), demandGrid = ref({ weekday: {}, weekend: {} })
const isAdminView = computed(() => currentRole.value === 'admin')
const canManageStore = computed(() => ['super_admin', 'admin'].includes(currentRole.value))
const canCreateStore = computed(() => ['super_admin', 'admin'].includes(currentRole.value))
const canEditStoreName = computed(() => ['super_admin'].includes(currentRole.value))
const canEditStoreNameField = computed(() => canEditStoreName.value || (!editingId.value && canCreateStore.value))
const canEditStoreArea = computed(() => ['super_admin', 'admin'].includes(currentRole.value))
const canEditStoreHours = computed(() => ['super_admin', 'admin', 'area_manager'].includes(currentRole.value))
const canEditProfile = computed(() => canEditStoreNameField.value || canEditStoreHours.value)
const canEditConfig = computed(() => ['area_manager', 'store_manager'].includes(currentRole.value))
const showDemandSection = computed(() => !isAdminView.value)
const showRuleSection = computed(() => !isAdminView.value)
const adminRosterShellStyle = computed(() => {
  if (!isAdminView.value || !adminRosterHeight.value) return {}
  return { height: `${adminRosterHeight.value}px` }
})
const roleLabel = computed(() => currentRole.value === 'area_manager' ? '区域经理' : (currentRole.value === 'super_admin' || currentRole.value === 'admin') ? '系统管理员' : '店长')
const filteredStores = computed(() => stores.value.filter(store => (areaFilter.value === 'all' ? true : areaFilter.value === 'unassigned' ? store.area_id == null : String(store.area_id ?? '') === areaFilter.value) && (!storeSearch.value.trim() || String(store.name || '').toLowerCase().includes(storeSearch.value.trim().toLowerCase()))))
const selectedStore = computed(() => stores.value.find(item => String(item.id) === String(selectedStoreId.value)))
const activeAreaId = computed(() => selectedStore.value?.area_id ?? 'unassigned')
const hasPendingBusinessHourChange = computed(() => Boolean(selectedStore.value && (selectedStore.value.open_time !== form.value.open_time || selectedStore.value.close_time !== form.value.close_time || Number(selectedStore.value.area_id ?? 0) !== Number(form.value.area_id ?? 0))))
const canSubmit = computed(() => (canEditStoreNameField.value || canEditStoreHours.value) && (editingId.value || (canCreateStore.value && form.value.name.trim().length > 0)))
const previewDemandRange = computed(() => parseBusinessHourRange(form.value.open_time, form.value.close_time))
const previewDemandRangeLabel = computed(() => `${formatHour(previewDemandRange.value.start)} 至 ${formatHour(previewDemandRange.value.end + 1)}`)
const demandHours = computed(() => { if (!selectedStore.value) return []; const { start, end } = parseBusinessHourRange(selectedStore.value.open_time, selectedStore.value.close_time); return Array.from({ length: end - start + 1 }, (_, i) => start + i) })
const demandRangeLabel = computed(() => demandHours.value.length ? `${formatHour(demandHours.value[0])} 至 ${formatHour(Number(demandHours.value.at(-1)) + 1)}` : '--')
const unassignedStores = computed(() => stores.value.filter(store => store.area_id == null))
const storesInArea = areaId => stores.value.filter(store => Number(store.area_id) === Number(areaId))
const notify = (text, error = false) => { message.value = text; isError.value = error }
function parseBusinessHourRange(openTime, closeTime) { const [oh='9', om='0'] = String(openTime || '09:00').split(':'), [ch='23', cm='0'] = String(closeTime || '23:00').split(':'); const start = Math.max(0, Math.min(23, Number(oh) + (Number(om) > 0 ? 1 : 0))); const end = Math.max(start, Math.min(23, Number(cm) > 0 ? Number(ch) : Number(ch) - 1)); return { start, end } }
const formatHourSlot = hour => `${String(hour).padStart(2, '0')}:00-${String(Math.min(24, Number(hour) + 1)).padStart(2, '0')}:00`
const formatHour = hour => `${String(Math.max(0, Math.min(24, Number(hour)))).padStart(2, '0')}:00`
const getAreaName = areaId => areaId == null ? '未分配区域' : areas.value.find(area => Number(area.id) === Number(areaId))?.name || `区域 ${areaId}`
function buildEmptyDemandGrid() { const previous = demandGrid.value, grid = { weekday: {}, weekend: {} }; for (const hour of demandHours.value) { grid.weekday[hour] = Number(previous.weekday?.[hour]) || 0; grid.weekend[hour] = Number(previous.weekend?.[hour]) || 0 } demandGrid.value = grid }
const resetRuleConfig = () => { ruleConfig.value = defaultRuleConfig() }
function applyStoreToForm(store) { if (!store) return; editingId.value = store.id; form.value = { name: store.name, area_id: store.area_id ?? null, open_time: store.open_time, close_time: store.close_time } }
function selectStore(storeId) { selectedStoreId.value = String(storeId); applyStoreToForm(stores.value.find(item => String(item.id) === String(storeId))) }
const demandSlotCountForStore = store => Math.max(0, parseBusinessHourRange(store.open_time, store.close_time).end - parseBusinessHourRange(store.open_time, store.close_time).start + 1)
const onStoreDragStart = store => { draggingStoreId.value = store.id }
async function onAreaDrop(areaId) {
  if (!draggingStoreId.value) return
  const store = stores.value.find(item => Number(item.id) === Number(draggingStoreId.value))
  draggingStoreId.value = null
  if (store) await assignStoreArea(store, areaId)
}
async function assignStoreArea(store, areaId) {
  if (!store || !canEditStoreArea.value || isAssigningArea.value) return
  const nextAreaId = areaId == null ? null : Number(areaId)
  if (Number(store.area_id ?? -1) === Number(nextAreaId ?? -1)) return
  isAssigningArea.value = true
  try {
    const updated = await api.updateStoreHours(store.id, {
      area_id: nextAreaId,
      open_time: store.open_time,
      close_time: store.close_time
    })
    notify(`已将 ${store.name} 调整到 ${getAreaName(nextAreaId)}。`)
    await loadStores()
    if (updated?.id) selectStore(updated.id)
  } catch (error) {
    notify(`调整区域失败：${error.message}`, true)
  } finally {
    isAssigningArea.value = false
  }
}
async function createArea() {
  if (!canManageStore.value || !newAreaName.value) return
  isSavingArea.value = true
  try {
    const area = await api.createArea({ name: newAreaName.value })
    newAreaName.value = ''
    await loadAreas()
    notify(`已创建区域：${area.name}`)
  } catch (error) {
    notify(`创建区域失败：${error.message}`, true)
  } finally {
    isSavingArea.value = false
  }
}
async function editArea(area) {
  if (!canManageStore.value || !area) return
  const nextName = window.prompt('请输入新的区域名称', area.name)
  if (nextName == null) return
  const name = nextName.trim()
  if (!name || name === area.name) return
  try {
    const updated = await api.updateArea(area.id, { name })
    await loadAreas()
    notify(`已更新区域：${updated.name}`)
  } catch (error) {
    notify(`更新区域失败：${error.message}`, true)
  }
}
async function removeArea(area) {
  if (!canManageStore.value || !area) return
  if (!window.confirm(`确认删除区域“${area.name}”吗？该区域下门店会转为未分配区域。`)) return
  try {
    await api.deleteArea(area.id)
    if (selectedStore.value && Number(selectedStore.value.area_id) === Number(area.id)) {
      form.value.area_id = null
    }
    await loadAreas()
    await loadStores()
    notify(`已删除区域：${area.name}`)
  } catch (error) {
    notify(`删除区域失败：${error.message}`, true)
  }
}
async function loadMe() { currentRole.value = (await api.getMe()).role }
async function loadAreas() { try { areas.value = await api.getAreas() } catch { areas.value = [] } }
async function loadStores() { try { stores.value = await api.getStores() || []; if (!selectedStoreId.value && stores.value.length) return selectStore(stores.value[0].id); if (selectedStoreId.value) { const exists = stores.value.some(item => String(item.id) === String(selectedStoreId.value)); if (!exists) { if (stores.value.length) selectStore(stores.value[0].id); else { selectedStoreId.value = ''; editingId.value = null } return } applyStoreToForm(stores.value.find(item => String(item.id) === String(selectedStoreId.value))) } } catch (error) { notify(`加载门店失败：${error.message}`, true) } }
async function loadStaffingDemand() { if (!selectedStoreId.value) return buildEmptyDemandGrid(); try { buildEmptyDemandGrid(); const data = await api.getStoreStaffingDemand(selectedStoreId.value); if (Array.isArray(data.profiles) && data.profiles.length) { for (const item of data.profiles) { const dayType = String(item.day_type || '').toLowerCase(), hour = Number(item.hour); if ((dayType === 'weekday' || dayType === 'weekend') && Object.prototype.hasOwnProperty.call(demandGrid.value[dayType], hour)) demandGrid.value[dayType][hour] = Number(item.min_staff) || 0 } return } for (const item of data.items || []) { const dayType = Number(item.day_of_week) <= 4 ? 'weekday' : 'weekend', hour = Number(item.hour); if (Object.prototype.hasOwnProperty.call(demandGrid.value[dayType], hour)) demandGrid.value[dayType][hour] = Math.max(Number(demandGrid.value[dayType][hour]) || 0, Number(item.min_staff) || 0) } } catch (error) { notify(`加载人力需求失败：${error.message}`, true) } }
async function loadRuleConfig() { if (!selectedStoreId.value) return resetRuleConfig(); try { const data = await api.getStoreRuleConfig(selectedStoreId.value); ruleConfig.value = { schedule_archetype: String(data.schedule_archetype || 'auto'), weekday_total_hours_limit: Number(data.weekday_total_hours_limit) || 40, weekend_total_hours_limit: Number(data.weekend_total_hours_limit) || 45, sg_part_time_min_hours: Number(data.sg_part_time_min_hours) || 80, sg_part_time_target_hours: Number(data.sg_part_time_target_hours) || 160, target_160_last_week_days: Number(data.target_160_last_week_days) || 7, min_backroom_per_hour: Number(data.min_backroom_per_hour) || 0, require_opening_dual_skill: Boolean(data.require_opening_dual_skill), min_opening_keyholders: Number(data.min_opening_keyholders) || 0, min_closing_keyholders: Number(data.min_closing_keyholders) || 0, store_key_count: Number(data.store_key_count) || 0 } } catch (error) { notify(`加载排班规则失败：${error.message}`, true) } }
function resetForm() { if (selectedStore.value) { applyStoreToForm(selectedStore.value); return notify('已恢复为当前门店已保存配置。') } editingId.value = null; form.value = emptyForm() }
function startCreate() { if (!canCreateStore.value) return notify('当前角色无法创建门店。', true); selectedStoreId.value = ''; editingId.value = null; form.value = emptyForm(); buildEmptyDemandGrid(); resetRuleConfig() }
async function saveStore() { if (!canSubmit.value) return; isSaving.value = true; try { let savedStore = null; if (editingId.value) { savedStore = await api.updateStoreHours(editingId.value, { name: form.value.name.trim(), area_id: form.value.area_id, open_time: form.value.open_time, close_time: form.value.close_time }); notify('门店信息已更新。') } else { savedStore = await api.createStore({ name: form.value.name.trim(), area_id: form.value.area_id, open_time: form.value.open_time, close_time: form.value.close_time }); notify('门店已创建。') } await loadStores(); if (savedStore?.id) selectStore(savedStore.id); await loadStaffingDemand(); await loadRuleConfig() } catch (error) { notify(`保存失败：${error.message}`, true) } finally { isSaving.value = false } }
async function removeStore(store) { if (!store || !canCreateStore.value || !window.confirm(`确认删除门店“${store.name}”吗？`)) return; try { await api.deleteStore(store.id); notify('门店已删除。'); selectedStoreId.value = ''; editingId.value = null; await loadStores(); await loadStaffingDemand(); await loadRuleConfig() } catch (error) { notify(`删除失败：${error.message}`, true) } }
async function saveStaffingDemand() { if (!selectedStoreId.value || !canEditConfig.value) return; if (hasPendingBusinessHourChange.value) return notify(`请先保存营业时间，再保存人力需求。草稿范围：${previewDemandRangeLabel.value}。`, true); if (!demandHours.value.length) return notify('当前门店没有合法的人力需求时段，请先检查营业时间。', true); isSavingDemand.value = true; try { const profiles = []; for (const dayType of ['weekday', 'weekend']) { for (const hour of demandHours.value) { const value = Number(demandGrid.value[dayType]?.[hour] ?? 0); profiles.push({ day_type: dayType, hour, min_staff: Number.isFinite(value) && value >= 0 ? Math.floor(value) : 0 }) } } await api.updateStoreStaffingDemand(selectedStoreId.value, { store_id: Number(selectedStoreId.value), profiles, items: [] }); notify(`人力需求已保存。当前可编辑范围：${demandRangeLabel.value}。`); await loadStaffingDemand() } catch (error) { notify(`保存人力需求失败：${error.message}`, true) } finally { isSavingDemand.value = false } }
async function saveRuleConfig() { if (!selectedStoreId.value || !canEditConfig.value) return; isSavingRuleConfig.value = true; try { await api.updateStoreRuleConfig(selectedStoreId.value, { store_id: Number(selectedStoreId.value), schedule_archetype: String(ruleConfig.value.schedule_archetype || 'auto'), weekday_total_hours_limit: Math.max(1, Number(ruleConfig.value.weekday_total_hours_limit) || 40), weekend_total_hours_limit: Math.max(1, Number(ruleConfig.value.weekend_total_hours_limit) || 45), sg_part_time_min_hours: Math.max(1, Number(ruleConfig.value.sg_part_time_min_hours) || 80), sg_part_time_target_hours: Math.max(1, Number(ruleConfig.value.sg_part_time_target_hours) || 160), target_160_last_week_days: Math.max(1, Number(ruleConfig.value.target_160_last_week_days) || 7), min_backroom_per_hour: Math.max(0, Number(ruleConfig.value.min_backroom_per_hour) || 0), require_opening_dual_skill: Boolean(ruleConfig.value.require_opening_dual_skill), min_opening_keyholders: Math.max(0, Number(ruleConfig.value.min_opening_keyholders) || 0), min_closing_keyholders: Math.max(0, Number(ruleConfig.value.min_closing_keyholders) || 0), store_key_count: Math.max(0, Number(ruleConfig.value.store_key_count) || 0) }); notify('排班规则已保存。'); await loadRuleConfig() } catch (error) { notify(`保存排班规则失败：${error.message}`, true) } finally { isSavingRuleConfig.value = false } }
const refreshWorkspace = async () => { await loadAreas(); await loadStores(); await loadStaffingDemand(); await loadRuleConfig() }
watch(demandHours, () => buildEmptyDemandGrid())
watch(selectedStoreId, async () => { await loadStaffingDemand(); await loadRuleConfig() })

function syncAdminRosterHeight() {
  if (!isAdminView.value || !adminEditorCard.value) {
    adminRosterHeight.value = null
    return
  }
  adminRosterHeight.value = Math.ceil(adminEditorCard.value.getBoundingClientRect().height)
}

function setupAdminRosterObserver() {
  adminEditorObserver?.disconnect()
  adminEditorObserver = null
  if (!isAdminView.value || !adminEditorCard.value || typeof ResizeObserver === 'undefined') {
    syncAdminRosterHeight()
    return
  }
  adminEditorObserver = new ResizeObserver(() => syncAdminRosterHeight())
  adminEditorObserver.observe(adminEditorCard.value)
  syncAdminRosterHeight()
}

watch(isAdminView, async () => {
  await nextTick()
  setupAdminRosterObserver()
})

watch([selectedStoreId, editingId], async () => {
  await nextTick()
  syncAdminRosterHeight()
})

onMounted(async () => {
  await loadMe()
  await loadAreas()
  await loadStores()
  await loadStaffingDemand()
  await loadRuleConfig()
  await nextTick()
  setupAdminRosterObserver()
})

onBeforeUnmount(() => {
  adminEditorObserver?.disconnect()
  adminEditorObserver = null
})
</script>

<style scoped>
.store-page,
.workspace-grid,
.editor-stack,
.store-list,
.form-grid,
.rules-grid,
.metrics-grid,
.area-board {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.workspace-grid {
  grid-template-columns: minmax(280px, 340px) minmax(0, 1fr);
  gap: 22px;
}

.workspace-grid.admin-workspace {
  align-items: start;
}

.panel-shell,
.metric-card,
.store-card,
.area-zone {
  padding: 20px;
  border-radius: 24px;
  border: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 18px 40px var(--theme-shadow);
  min-width: 0;
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) auto;
  gap: 18px;
  background:
    radial-gradient(circle at top right, rgba(244, 123, 76, 0.12), transparent 24%),
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(250, 243, 233, 0.96));
}

.eyebrow {
  margin: 0 0 10px;
  color: var(--color-primary-dark);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.muted {
  margin: 10px 0 0;
  color: var(--color-text-soft);
  line-height: 1.6;
}

.hero h1,
.panel-head h2 {
  margin: 0;
  color: var(--color-heading);
}

.hero-actions,
.panel-head,
.editor-actions,
.filter-bar,
.inline-create,
.summary-strip,
.row,
.between,
.zone-head {
  display: flex;
  gap: 10px;
  justify-content: space-between;
}

.hero-actions,
.inline-create {
  flex-wrap: wrap;
  align-content: start;
}

.role-chip,
.soft-tag,
.area-count,
.toggle-state {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  font-weight: 700;
}

.role-chip {
  min-height: 34px;
  padding: 0 12px;
  background: rgba(244, 123, 76, 0.12);
  color: var(--color-primary-dark);
}

.soft-tag {
  min-height: 26px;
  padding: 0 10px;
  background: rgba(35, 62, 54, 0.08);
  font-size: 12px;
}

.btn {
  min-height: 34px;
  padding: 0 12px;
  border-radius: 12px;
  border: 1px solid transparent;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.btn.primary {
  background: linear-gradient(135deg, #f47b4c, #ff9659);
  color: #fff;
}

.btn.ghost {
  border-color: rgba(244, 123, 76, 0.16);
  background: rgba(255, 251, 245, 0.92);
  color: var(--color-heading);
}

.btn.danger {
  border-color: rgba(203, 87, 78, 0.18);
  color: #9a362d;
}

.status-banner {
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(234, 248, 238, 0.92);
  color: #2f6d47;
  font-weight: 600;
}

.status-banner.error {
  background: rgba(253, 236, 233, 0.92);
  color: #933a2f;
}

.metrics-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.metric-card span {
  display: block;
  color: var(--color-text-soft);
  font-size: 13px;
}

.metric-card strong {
  display: block;
  margin-top: 10px;
  color: var(--color-heading);
  font-size: 34px;
  line-height: 1.1;
}

.metric-card strong.small {
  font-size: 22px;
  overflow-wrap: anywhere;
}

.metric-card.accent {
  background: linear-gradient(145deg, rgba(244, 123, 76, 0.16), rgba(248, 233, 215, 0.92));
}

.inline-create-btn {
  flex: 0 0 auto;
}

.area-board {
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  margin-top: 16px;
  align-items: stretch;
}

.area-zone {
  position: relative;
  display: grid;
  gap: 14px;
  padding: 18px;
  border-radius: 24px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(250, 244, 236, 0.94)),
    radial-gradient(circle at top right, rgba(244, 123, 76, 0.1), transparent 42%);
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
  overflow: hidden;
}

.area-zone::before {
  content: "";
  position: absolute;
  inset: 0 0 auto 0;
  height: 5px;
  background: linear-gradient(90deg, rgba(244, 123, 76, 0.92), rgba(255, 185, 111, 0.72));
}

.area-zone.active,
.area-zone:hover,
.store-card.active,
.store-card:hover {
  border-color: rgba(244, 123, 76, 0.32);
  box-shadow: 0 22px 36px rgba(20, 35, 31, 0.1);
  transform: translateY(-2px);
}

.area-zone.disabled {
  opacity: 0.82;
}

.zone-head {
  align-items: flex-start;
}

.zone-tools {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.zone-head strong {
  font-size: 16px;
  color: var(--color-heading);
}

.zone-head p {
  margin: 6px 0 0;
  color: var(--color-text-soft);
  font-size: 13px;
  line-height: 1.5;
}

.area-count {
  min-width: 38px;
  min-height: 32px;
  padding: 0 12px;
  background: rgba(244, 123, 76, 0.14);
  color: var(--color-primary-dark);
  box-shadow: inset 0 0 0 1px rgba(244, 123, 76, 0.08);
}

.zone-icon-btn {
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid rgba(244, 123, 76, 0.14);
  background: rgba(255, 251, 245, 0.92);
  color: var(--color-heading);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.zone-icon-btn.danger {
  border-color: rgba(203, 87, 78, 0.18);
  color: #9a362d;
}

.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-content: flex-start;
  min-height: 46px;
}

.store-chip {
  min-height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid rgba(244, 123, 76, 0.14);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(255, 248, 241, 0.94));
  font-size: 12px;
  font-weight: 800;
  color: var(--color-heading);
  cursor: pointer;
  box-shadow: 0 8px 18px rgba(28, 42, 38, 0.06);
  transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
}

.store-chip:hover {
  transform: translateY(-1px);
  border-color: rgba(244, 123, 76, 0.28);
  box-shadow: 0 10px 20px rgba(28, 42, 38, 0.08);
}

.store-chip.selected {
  background: linear-gradient(180deg, rgba(255, 232, 220, 0.96), rgba(255, 244, 236, 0.94));
  border-color: rgba(244, 123, 76, 0.3);
  color: var(--color-primary-dark);
}

.empty-inline,
.small-text {
  font-size: 13px;
  color: var(--color-text-soft);
}

.empty-inline {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(248, 239, 228, 0.76);
}

.stacked {
  flex-direction: column;
}

.store-list {
  max-height: 960px;
  overflow: auto;
  padding-right: 4px;
  margin-top: 8px;
}

.admin-roster-shell {
  align-self: start;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.admin-roster-shell .store-list {
  flex: 1 1 auto;
  min-height: 0;
  max-height: none;
}

.admin-editor-stack {
  align-self: start;
}

.admin-editor-stack > .panel-shell:first-child {
  min-height: 0;
}

.store-card {
  width: 100%;
  display: grid;
  gap: 10px;
  text-align: left;
  padding: 16px;
  border-radius: 20px;
  cursor: pointer;
}

.summary-strip {
  flex-wrap: wrap;
  margin-top: 8px;
}

.compact-summary {
  margin-top: 14px;
}

.summary-chip {
  flex: 1 1 180px;
  padding: 14px;
  border-radius: 18px;
  background: rgba(248, 239, 228, 0.72);
}

.summary-chip span {
  display: block;
  color: var(--color-text-soft);
  font-size: 13px;
}

.summary-chip strong {
  display: block;
  margin-top: 8px;
  color: var(--color-heading);
  overflow-wrap: anywhere;
}

label {
  display: grid;
  gap: 6px;
  font-size: 13px;
  color: var(--color-heading);
  min-width: 0;
}

.form-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.rules-grid {
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

input,
select {
  width: 100%;
  min-height: 42px;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  padding: 0 12px;
  background: rgba(255, 251, 245, 0.92);
  box-sizing: border-box;
  min-width: 0;
}

.range-callout,
.empty-block,
.toggle-card {
  margin-top: 14px;
  padding: 14px;
  border-radius: 18px;
}

.range-callout,
.empty-block {
  background: rgba(248, 239, 228, 0.6);
}

.demand-wrap {
  overflow: auto;
}

.demand-table {
  width: 100%;
  min-width: 860px;
  border-collapse: collapse;
}

.demand-table th,
.demand-table td {
  padding: 10px 8px;
  border-bottom: 1px solid var(--color-border);
  text-align: center;
}

.demand-table th {
  position: sticky;
  top: 0;
  background: rgba(255, 253, 248, 0.98);
  z-index: 1;
}

.day-cell {
  text-align: left;
  white-space: nowrap;
  font-weight: 700;
}

.demand-input {
  min-width: 72px;
  text-align: center;
}

.toggle-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 14px;
  margin-top: 18px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 239, 228, 0.88));
  border: 1px solid rgba(244, 123, 76, 0.18);
}

.toggle-card small {
  display: block;
  color: var(--color-text-soft);
  margin-top: 4px;
}

.toggle-state {
  min-height: 30px;
  padding: 0 12px;
  background: rgba(203, 87, 78, 0.12);
  color: #8c312e;
  font-size: 12px;
  font-weight: 800;
}

.toggle-state.active {
  background: rgba(76, 151, 107, 0.14);
  color: #275d3f;
}

.full-span {
  grid-column: 1 / -1;
}

button:disabled,
input:disabled,
select:disabled {
  opacity: 0.56;
  cursor: not-allowed;
}

@media (max-width: 1180px) {
  .metrics-grid,
  .workspace-grid,
  .form-grid,
  .rules-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .hero,
  .hero-actions,
  .panel-head,
  .editor-actions,
  .summary-strip,
  .filter-bar,
  .inline-create,
  .toggle-card,
  .zone-head,
  .row,
  .between {
    flex-direction: column;
    align-items: stretch;
  }

  .metric-card strong {
    font-size: 28px;
  }

  .metric-card strong.small {
    font-size: 20px;
  }

  .area-board {
    grid-template-columns: 1fr;
  }
}
</style>

