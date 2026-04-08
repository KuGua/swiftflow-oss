import { createRouter, createWebHistory } from 'vue-router'
import { getCurrentRole, isLoggedIn } from '@/lib/apiClient'
import HomeView from '@/views/HomeView.vue'

const ShiftScheduleView = () => import('@/views/ShiftSchedule.vue')
const PersonalScheduleView = () => import('@/views/PersonalSchedule.vue')
const PersonalProfileView = () => import('@/views/PersonalProfile.vue')
const EmployeeManagementView = () => import('@/views/EmployeeManagement.vue')
const StoreManagementView = () => import('@/views/StoreManagement.vue')
const LoginView = () => import('@/views/LoginView.vue')
const RegisterView = () => import('@/views/RegisterView.vue')

export function defaultRouteForRole(role: string | null | undefined) {
  return role === 'staff' ? '/my-schedule' : '/'
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
      meta: {
        requiresAuth: true,
        title: '工作台',
        eyebrow: '运营总览',
        subtitle: '在统一视图中查看门店规模、人力能力与排班重点。',
        allowedRoles: ['super_admin', 'admin', 'area_manager', 'store_manager', 'developer'],
      },
    },
    {
      path: '/my-schedule',
      name: 'PersonalSchedule',
      component: PersonalScheduleView,
      meta: {
        requiresAuth: true,
        title: '我的排班',
        eyebrow: '员工自助',
        subtitle: '查看本周参与门店的整周排班，并维护个人可上班时间。',
        allowedRoles: ['staff'],
      },
    },
    {
      path: '/profile',
      name: 'PersonalProfile',
      component: PersonalProfileView,
      meta: {
        requiresAuth: true,
        title: '个人信息',
        eyebrow: '账号设置',
        subtitle: '维护与注册信息一致的个人资料，包括姓名、手机号、身份类别和密码。',
        allowedRoles: ['area_manager', 'store_manager', 'staff'],
      },
    },
    {
      path: '/shift-schedule',
      name: 'ShiftSchedule',
      component: ShiftScheduleView,
      meta: {
        requiresAuth: true,
        title: '排班中心',
        eyebrow: '排班管理',
        subtitle: '以周历为主视图，统一查看排班、异常与操作入口。',
        allowedRoles: ['super_admin', 'admin', 'area_manager', 'store_manager', 'staff', 'developer'],
      },
    },
    {
      path: '/employees',
      name: 'EmployeeManagement',
      component: EmployeeManagementView,
      meta: {
        requiresAuth: true,
        title: '员工管理',
        eyebrow: '人员运营',
        subtitle: '维护员工资料、业务权限、门店分配与可排时间。',
        allowedRoles: ['super_admin', 'admin', 'area_manager', 'store_manager', 'developer'],
      },
    },
    {
      path: '/stores',
      name: 'StoreManagement',
      component: StoreManagementView,
      meta: {
        requiresAuth: true,
        title: '店铺管理',
        eyebrow: '门店运营',
        subtitle: '统一维护营业时间、人力需求与门店规则。',
        allowedRoles: ['super_admin', 'admin', 'area_manager', 'store_manager', 'developer'],
      },
    },
    {
      path: '/users',
      redirect: '/employees',
    },
    {
      path: '/data-visualization',
      redirect: '/',
    },
    {
      path: '/login',
      name: 'Login',
      component: LoginView,
      meta: {
        requiresAuth: false,
        title: '登录',
        eyebrow: '系统访问',
      },
    },
    {
      path: '/register',
      name: 'Register',
      component: RegisterView,
      meta: {
        requiresAuth: false,
        title: '注册',
        eyebrow: '员工注册',
      },
    },
  ],
})

router.beforeEach((to) => {
  const loggedIn = isLoggedIn()
  const needAuth = to.meta.requiresAuth !== false
  const currentRole = getCurrentRole()

  if (needAuth && !loggedIn) {
    return { path: '/login' }
  }

  if ((to.path === '/login' || to.path === '/register') && loggedIn) {
    return { path: defaultRouteForRole(currentRole) }
  }

  const allowedRoles = Array.isArray(to.meta.allowedRoles) ? to.meta.allowedRoles : null
  if (needAuth && allowedRoles?.length && currentRole && !allowedRoles.includes(currentRole)) {
    return { path: defaultRouteForRole(currentRole) }
  }

  return true
})

export default router
