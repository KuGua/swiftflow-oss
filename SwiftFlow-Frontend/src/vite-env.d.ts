/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>
  export default component
}

declare module '@/lib/apiClient'
declare module './i18n'
declare module '@/views/ShiftSchedule.vue'
declare module '@/views/EmployeeManagement.vue'
declare module '@/views/StoreManagement.vue'
declare module '@/views/LoginView.vue'
