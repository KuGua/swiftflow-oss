<template>
  <div class="shell" :class="{ 'shell-login': isLoginPage }">
    <template v-if="!isLoginPage">
      <aside class="sidebar" :class="{ open: mobileNavOpen }">
        <div class="brand-block">
          <div class="brand-mark">SF</div>
          <div>
            <p class="brand-kicker">智能零售排班</p>
            <h1 class="brand-title">SwiftFlow</h1>
          </div>
        </div>

        <nav class="nav-list">
          <RouterLink
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="nav-item"
            @click="mobileNavOpen = false"
          >
            <span class="nav-icon">{{ item.icon }}</span>
            <span>
              <strong>{{ item.label }}</strong>
              <small>{{ item.hint }}</small>
            </span>
          </RouterLink>
        </nav>

        <div class="sidebar-footer">
          <div class="user-card">
            <span class="user-chip">{{ currentUserLabel }}</span>
            <p>{{ pageSubtitle }}</p>
          </div>
          <button class="sidebar-logout" @click="logout">退出登录</button>
        </div>
      </aside>

      <div v-if="mobileNavOpen" class="mobile-backdrop" @click="mobileNavOpen = false"></div>

      <div class="shell-main">
        <header class="topbar">
          <div class="topbar-main">
            <button class="menu-toggle" @click="mobileNavOpen = !mobileNavOpen">菜单</button>
            <div>
              <p class="topbar-kicker">{{ pageEyebrow }}</p>
              <h2 class="topbar-title">{{ pageTitle }}</h2>
            </div>
          </div>
          <div class="topbar-side">
            <span class="context-pill">{{ currentUserLabel }}</span>
            <span class="context-note">{{ currentDateLabel }}</span>
          </div>
        </header>

        <main class="content">
          <RouterView />
        </main>
      </div>

      <nav class="mobile-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="mobile-nav-item"
        >
          <span>{{ item.icon }}</span>
          <small>{{ item.label }}</small>
        </RouterLink>
      </nav>
    </template>

    <main v-else class="login-shell">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { clearAuth, getCurrentRole, getCurrentUser } from '@/lib/apiClient'

const route = useRoute()
const router = useRouter()
const mobileNavOpen = ref(false)
const currentRoleValue = ref('')
const currentUsername = ref('')

const navDefinitions = [
  { to: '/', label: '工作台', hint: '总览与重点事项', icon: '总览' },
  { to: '/shift-schedule', label: '排班中心', hint: '周历与班次调整', icon: '排班' },
  { to: '/my-schedule', label: '我的排班', hint: '个人班表与可排时间', icon: '我的' },
  { to: '/stores', label: '店铺管理', hint: '营业时间、需求与规则', icon: '门店' },
  { to: '/employees', label: '员工管理', hint: '员工档案与业务权限', icon: '员工' },
  { to: '/profile', label: '个人信息', hint: '维护注册资料与登录密码', icon: '账号' }
]

function syncAuthSnapshot() {
  currentRoleValue.value = getCurrentRole()
  currentUsername.value = getCurrentUser()
}

const currentRole = computed(() => currentRoleValue.value)
const navItems = computed(() => {
  if (currentRole.value === 'staff') {
    return navDefinitions.filter(item => item.to === '/my-schedule' || item.to === '/profile')
  }
  if (currentRole.value === 'area_manager' || currentRole.value === 'store_manager') {
    return navDefinitions.filter(item => item.to !== '/my-schedule')
  }
  return navDefinitions.filter(item => item.to !== '/my-schedule' && item.to !== '/profile')
})

const isLoginPage = computed(() => route.path === '/login' || route.path === '/register')
const currentUserLabel = computed(() => {
  const username = currentUsername.value
  const role = currentRole.value
  if (role === 'admin' || role === 'super_admin') return '系统管理员'
  if (role === 'area_manager') return '区域经理'
  if (role === 'store_manager') return '店长'
  if (role === 'staff') return '员工'
  if (role === 'developer') return '开发维护'
  return username || '当前用户'
})

const pageTitle = computed(() => String(route.meta.title || 'SwiftFlow 工作台'))
const pageSubtitle = computed(() => String(route.meta.subtitle || '在同一界面中管理门店、员工和排班。'))
const pageEyebrow = computed(() => String(route.meta.eyebrow || '运营协同'))
const currentDateLabel = computed(
  () =>
    new Intl.DateTimeFormat('zh-SG', {
      month: 'short',
      day: 'numeric',
      weekday: 'short'
    }).format(new Date())
)

watch(
  () => route.fullPath,
  () => {
    syncAuthSnapshot()
    mobileNavOpen.value = false
  }
)

function handleStorageChange() {
  syncAuthSnapshot()
}

onMounted(() => {
  syncAuthSnapshot()
  window.addEventListener('storage', handleStorageChange)
})

onUnmounted(() => {
  window.removeEventListener('storage', handleStorageChange)
})

function logout() {
  clearAuth()
  syncAuthSnapshot()
  router.replace('/login')
}
</script>

<style scoped>
.shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
}

.shell-login {
  display: block;
}

.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  padding: 22px 18px;
  background: linear-gradient(180deg, #173029, #223e36 55%, #14231f);
  color: #f8efe4;
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: 20px;
  box-shadow: 8px 0 30px rgba(20, 35, 31, 0.18);
}

.brand-block {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-mark {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-dark));
  color: #fff;
  font-weight: 800;
}

.brand-kicker,
.topbar-kicker {
  margin: 0 0 4px;
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: rgba(248, 239, 228, 0.72);
}

.brand-title,
.topbar-title {
  margin: 0;
  color: inherit;
}

.nav-list {
  display: grid;
  gap: 8px;
  align-content: start;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 18px;
  color: rgba(248, 239, 228, 0.86);
  transition: background 0.2s ease, transform 0.2s ease, color 0.2s ease;
}

.nav-item small {
  display: block;
  color: rgba(248, 239, 228, 0.58);
}

.nav-item.router-link-exact-active {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  transform: translateX(2px);
}

.nav-icon {
  min-width: 44px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.08);
  font-size: 12px;
  font-weight: 700;
}

.sidebar-footer {
  display: grid;
  gap: 12px;
}

.user-card {
  padding: 14px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.08);
  color: rgba(248, 239, 228, 0.88);
}

.user-card p {
  margin: 8px 0 0;
  color: rgba(248, 239, 228, 0.68);
  font-size: 13px;
}

.user-chip,
.context-pill {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(244, 123, 76, 0.2);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.sidebar-logout,
.menu-toggle {
  min-height: 42px;
  border: none;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  font-weight: 700;
}

.shell-main {
  display: grid;
  grid-template-rows: auto 1fr;
  min-width: 0;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 18px 24px 10px;
  background: rgba(248, 239, 228, 0.84);
  backdrop-filter: blur(14px);
}

.topbar-main,
.topbar-side {
  display: flex;
  align-items: center;
  gap: 14px;
}

.context-note {
  color: var(--color-text-soft);
  font-size: 13px;
}

.content {
  padding: 8px 24px 24px;
}

.mobile-nav,
.mobile-backdrop {
  display: none;
}

.login-shell {
  min-height: 100vh;
}

@media (max-width: 980px) {
  .shell {
    grid-template-columns: 1fr;
  }

  .sidebar {
    position: fixed;
    inset: 0 auto 0 0;
    width: min(82vw, 320px);
    transform: translateX(-100%);
    transition: transform 0.22s ease;
    z-index: 40;
  }

  .sidebar.open {
    transform: translateX(0);
  }

  .mobile-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(20, 35, 31, 0.36);
    z-index: 30;
  }

  .mobile-nav {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(70px, 1fr));
    gap: 8px;
    padding: 10px 14px calc(10px + env(safe-area-inset-bottom));
    background: rgba(255, 255, 255, 0.94);
    position: sticky;
    bottom: 0;
    z-index: 20;
    border-top: 1px solid rgba(221, 199, 166, 0.65);
  }

  .mobile-nav-item {
    display: grid;
    gap: 4px;
    place-items: center;
    color: var(--color-text-soft);
    font-size: 12px;
  }

  .topbar {
    padding-inline: 16px;
  }

  .content {
    padding-inline: 16px;
    padding-bottom: 92px;
  }
}
</style>
