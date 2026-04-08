<template>
  <section class="auth-page">
    <div class="auth-copy">
      <div>
        <p class="eyebrow">系统登录</p>
        <h1>进入 SwiftFlow 智能排班后台</h1>
        <p class="lead">
          使用账号密码登录系统。员工可通过手机号注册并登录，注册后的基础资料会同步到员工档案中。
        </p>
      </div>

      <div class="copy-points">
        <article>
          <strong>统一账号体系</strong>
          <p>每位员工都使用自己的账号登录，角色权限直接定义在该账号上。</p>
        </article>
        <article>
          <strong>多角色协作</strong>
          <p>支持管理员、区域经理、店长和员工等不同角色的协同使用。</p>
        </article>
        <article>
          <strong>排班与资料联动</strong>
          <p>员工注册后即可维护个人资料和可上班时间，后续会自动进入排班流程。</p>
        </article>
      </div>
    </div>

    <div class="auth-card">
      <div>
        <p class="eyebrow">欢迎回来</p>
        <h2>登录系统</h2>
        <p class="hint">请输入登录账号和密码。</p>
      </div>

      <div v-if="errorMsg" class="error">{{ errorMsg }}</div>

      <label>
        登录账号
        <input v-model="username" placeholder="请输入登录账号" />
      </label>

      <label>
        密码
        <input v-model="password" type="password" placeholder="请输入密码" />
      </label>

      <button :disabled="isSubmitting" @click="submitLogin">
        {{ isSubmitting ? '登录中...' : '登录' }}
      </button>

      <div class="auth-footer">
        <span>还没有账号？</span>
        <RouterLink to="/register">前往注册</RouterLink>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { api } from '@/lib/apiClient'
import { defaultRouteForRole } from '@/router'

const route = useRoute()
const router = useRouter()
const username = ref(String(route.query.username || ''))
const password = ref('')
const isSubmitting = ref(false)
const errorMsg = ref('')

watch(
  () => route.query.username,
  value => {
    username.value = String(value || '')
  }
)

async function submitLogin() {
  if (!username.value.trim() || !password.value) {
    errorMsg.value = '请输入登录账号和密码'
    return
  }

  isSubmitting.value = true
  errorMsg.value = ''
  try {
    const data = await api.login(username.value.trim(), password.value)
    await router.replace(defaultRouteForRole(data?.role))
  } catch (error) {
    errorMsg.value = `登录失败：${error.message}`
  } finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(340px, 420px);
  gap: 24px;
  align-items: stretch;
  padding: clamp(18px, 3vw, 32px);
  background:
    radial-gradient(circle at top left, rgba(244, 123, 76, 0.18), transparent 26%),
    radial-gradient(circle at bottom right, rgba(110, 167, 217, 0.14), transparent 24%),
    linear-gradient(145deg, #fffaf2, #f5eadf);
}

.auth-copy {
  padding: clamp(24px, 5vw, 56px);
  border-radius: 32px;
  background: linear-gradient(155deg, rgba(255, 253, 248, 0.9), rgba(248, 233, 215, 0.78));
  border: 1px solid rgba(32, 51, 45, 0.08);
  box-shadow: 0 24px 60px rgba(20, 35, 31, 0.08);
  display: grid;
  align-content: space-between;
  gap: 28px;
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--color-primary-dark);
}

.auth-copy h1 {
  margin: 0;
  max-width: 16ch;
  font-size: clamp(34px, 5vw, 58px);
  line-height: 1.04;
  color: var(--color-heading);
}

.lead {
  margin: 18px 0 0;
  max-width: 62ch;
  color: var(--color-text-soft);
  font-size: 16px;
}

.copy-points {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.copy-points article,
.auth-card {
  background: rgba(255, 253, 248, 0.82);
  border: 1px solid rgba(32, 51, 45, 0.1);
  border-radius: 24px;
  box-shadow: 0 18px 40px rgba(20, 35, 31, 0.08);
}

.copy-points article {
  padding: 16px;
}

.copy-points strong {
  display: block;
  margin-bottom: 8px;
  color: var(--color-heading);
}

.copy-points p,
.hint {
  margin: 0;
  color: var(--color-text-soft);
}

.auth-card {
  padding: 24px;
  display: grid;
  gap: 14px;
  align-content: center;
}

.auth-card h2 {
  margin: 0;
  font-size: 30px;
}

label {
  display: grid;
  gap: 8px;
  font-weight: 600;
  color: var(--color-heading);
}

.error {
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(253, 236, 233, 0.92);
  color: #933a2f;
  font-weight: 600;
}

.auth-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--color-text-soft);
  font-size: 14px;
}

.auth-footer a {
  color: var(--color-primary-dark);
  font-weight: 700;
}

@media (max-width: 1080px) {
  .auth-page {
    grid-template-columns: 1fr;
  }

  .copy-points {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .auth-page {
    padding: 12px;
  }

  .auth-copy,
  .auth-card {
    padding: 18px;
    border-radius: 24px;
  }

  .auth-copy h1 {
    max-width: none;
    font-size: 34px;
  }
}
</style>
