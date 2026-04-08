<template>
  <section class="auth-page">
    <div class="auth-copy">
      <div>
        <p class="eyebrow">员工注册</p>
        <h1>创建你的 SwiftFlow 账号</h1>
        <p class="lead">
          注册后将自动创建员工档案，并同步基础信息。登录账号使用手机号，初始角色默认为员工。
        </p>
      </div>

      <div class="copy-points">
        <article>
          <strong>手机号注册</strong>
          <p>支持新加坡与马来西亚区号，完整手机号将作为后续登录账号。</p>
        </article>
        <article>
          <strong>资料自动同步</strong>
          <p>姓名、身份类别和手机号会自动进入员工管理模块的对应档案字段。</p>
        </article>
        <article>
          <strong>密码自行设置</strong>
          <p>注册时需输入并确认密码，后续可在个人信息页面中自行更新。</p>
        </article>
      </div>
    </div>

    <div class="auth-card">
      <div>
        <p class="eyebrow">注册</p>
        <h2>创建员工账号</h2>
        <p class="hint">请填写基础资料完成注册。</p>
      </div>

      <div v-if="message" class="status" :class="{ error: isError }">{{ message }}</div>

      <label>
        姓名
        <input v-model="form.name" placeholder="例如：员工A" />
      </label>

      <label>
        身份类别
        <select v-model="form.nationality_status">
          <option value="sg_citizen">新加坡公民</option>
          <option value="sg_pr">新加坡 PR</option>
          <option value="other">其他</option>
        </select>
      </label>

      <div class="phone-grid">
        <label>
          区号
          <select v-model="form.phone_country_code">
            <option value="+65">新加坡（+65）</option>
            <option value="+60">马来西亚（+60）</option>
          </select>
        </label>

        <label>
          手机号
          <input v-model="form.phone_number" inputmode="numeric" placeholder="91234567" />
        </label>
      </div>

      <label>
        密码
        <input v-model="form.password" type="password" placeholder="请输入密码" />
      </label>

      <label>
        确认密码
        <input v-model="form.password_confirm" type="password" placeholder="请再次输入密码" />
      </label>

      <button :disabled="isSubmitting" @click="submitRegister">
        {{ isSubmitting ? '注册中...' : '完成注册' }}
      </button>

      <div class="auth-footer">
        <span>已有账号？</span>
        <RouterLink to="/login">返回登录</RouterLink>
      </div>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { api } from '@/lib/apiClient'

const router = useRouter()
const isSubmitting = ref(false)
const isError = ref(false)
const message = ref('')
const form = reactive({
  name: '',
  nationality_status: 'other',
  phone_country_code: '+65',
  phone_number: '',
  password: '',
  password_confirm: ''
})

function notify(text, error = false) {
  message.value = text
  isError.value = error
}

async function submitRegister() {
  if (!form.name.trim()) return notify('请输入姓名', true)
  if (!form.phone_number.trim()) return notify('请输入手机号', true)
  if (!form.password) return notify('请输入密码', true)
  if (form.password !== form.password_confirm) return notify('两次输入的密码不一致', true)

  isSubmitting.value = true
  notify('')
  try {
    const data = await api.register({
      name: form.name.trim(),
      nationality_status: form.nationality_status,
      phone_country_code: form.phone_country_code,
      phone_number: form.phone_number.trim(),
      password: form.password,
      password_confirm: form.password_confirm
    })

    await router.replace({
      path: '/login',
      query: { username: data?.username || `${form.phone_country_code}${form.phone_number.trim()}` }
    })
  } catch (error) {
    notify(`注册失败：${error.message}`, true)
  } finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(340px, 440px);
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

.phone-grid {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr);
  gap: 12px;
}

.status {
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(55, 125, 88, 0.1);
  color: #285d41;
}

.status.error {
  background: rgba(253, 236, 233, 0.92);
  color: #933a2f;
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

  .phone-grid {
    grid-template-columns: 1fr;
  }

  .auth-copy h1 {
    max-width: none;
    font-size: 34px;
  }
}
</style>
