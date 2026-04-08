const USER_KEY = 'swiftflow_current_user'
const TOKEN_KEY = 'swiftflow_access_token'
const ROLE_KEY = 'swiftflow_current_role'

export function getCurrentUser() {
  return localStorage.getItem(USER_KEY) || ''
}

export function setCurrentUser(username) {
  localStorage.setItem(USER_KEY, username)
}

export function getCurrentRole() {
  return localStorage.getItem(ROLE_KEY) || ''
}

export function setCurrentRole(role) {
  localStorage.setItem(ROLE_KEY, role)
}

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function isLoggedIn() {
  return Boolean(getAccessToken())
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  localStorage.removeItem(ROLE_KEY)
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {})
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json')
  }
  const token = getAccessToken()
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(path, {
    ...options,
    headers
  })

  let data = null
  try {
    data = await response.json()
  } catch {
    data = null
  }

  if (!response.ok) {
    const detail = data?.detail || data?.message || `HTTP ${response.status}`
    if (response.status === 401) {
      clearAuth()
    }
    throw new Error(detail)
  }
  return data
}

export const api = {
  login: async (username, password) => {
    const data = await request('/api/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    })
    localStorage.setItem(TOKEN_KEY, data.access_token)
    setCurrentUser(data.username)
    setCurrentRole(data.role)
    return data
  },
  register: payload =>
    request('/api/register', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  getMe: async () => {
    const data = await request('/api/me')
    if (data?.role) setCurrentRole(data.role)
    if (data?.username) setCurrentUser(data.username)
    return data
  },
  getMyEmployeeProfile: () => request('/api/me/employee'),
  getMyProfile: () => request('/api/me/profile'),
  updateMyProfile: payload =>
    request('/api/me/profile', {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  updateMyAvailability: payload =>
    request('/api/me/availability', {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  getMyScheduleStores: weekStart =>
    request(`/api/me/schedule-stores?week_start=${encodeURIComponent(weekStart)}`),
  getMyStoreEmployees: (storeId, weekStart) =>
    request(`/api/me/store-employees?store_id=${encodeURIComponent(storeId)}&week_start=${encodeURIComponent(weekStart)}`),
  getHomeSummary: () => request('/api/home-summary'),
  getSchedule: (storeId, weekStart) =>
    request(`/api/schedules?store_id=${encodeURIComponent(storeId)}&week_start=${encodeURIComponent(weekStart)}`),
  generateAndSaveStoreSchedule: payload =>
    request('/api/generate-and-save-store-schedule', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  generateAndSaveAllSchedules: payload =>
    request('/api/generate-and-save-all-schedules', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  repairScheduleAnomalies: payload =>
    request('/api/schedules/repair', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  saveSchedule: payload =>
    request('/api/schedules', {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  getUsers: () => request('/api/users'),
  updateUserRole: (userId, payload) =>
    request(`/api/users/${userId}/role`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  updateUserStoreAccess: (userId, payload) =>
    request(`/api/users/${userId}/store-access`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  updateUserAreaAccess: (userId, payload) =>
    request(`/api/users/${userId}/area-access`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  updateUserEmployeeBinding: (userId, payload) =>
    request(`/api/users/${userId}/employee-binding`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  resetUserPassword: userId =>
    request(`/api/users/${userId}/reset-password`, {
      method: 'PUT'
    }),
  getAreas: () => request('/api/areas'),
  createArea: payload =>
    request('/api/areas', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  updateArea: (areaId, payload) =>
    request(`/api/areas/${areaId}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  deleteArea: areaId =>
    request(`/api/areas/${areaId}`, {
      method: 'DELETE'
    }),
  getStores: () => request('/api/stores'),
  createStore: payload =>
    request('/api/stores', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  updateStoreHours: (storeId, payload) =>
    request(`/api/stores/${storeId}/hours`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  deleteStore: storeId =>
    request(`/api/stores/${storeId}`, {
      method: 'DELETE'
    }),
  getStoreRuleConfig: storeId =>
    request(`/api/stores/${storeId}/rule-config`),
  updateStoreRuleConfig: (storeId, payload) =>
    request(`/api/stores/${storeId}/rule-config`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  getStoreStaffingDemand: storeId =>
    request(`/api/stores/${storeId}/staffing-demand`),
  updateStoreStaffingDemand: (storeId, payload) =>
    request(`/api/stores/${storeId}/staffing-demand`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  getEmployees: () => request('/api/employees'),
  createEmployee: payload =>
    request('/api/employees', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  updateEmployee: (employeeId, payload) =>
    request(`/api/employees/${employeeId}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  getEmployeeRelations: () => request('/api/employees/relations'),
  upsertEmployeeRelation: payload =>
    request('/api/employees/relations', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  deleteEmployeeRelation: (employeeIdA, employeeIdB) =>
    request(
      `/api/employees/relations?employee_id_a=${encodeURIComponent(employeeIdA)}&employee_id_b=${encodeURIComponent(employeeIdB)}`,
      { method: 'DELETE' }
    ),
  deleteEmployee: employeeId =>
    request(`/api/employees/${employeeId}`, {
      method: 'DELETE'
    })
}
