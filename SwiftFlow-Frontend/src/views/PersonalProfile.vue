<template>
  <section class="profile-page">
    <div class="profile-copy">
      <div>
        <p class="eyebrow">个人信息</p>
        <h1>维护你的登录资料与基础信息</h1>
        <p class="lead">
          这里展示的字段与注册页面保持一致。你可以在当前页面维护姓名、身份类别、手机号以及登录密码。
        </p>
      </div>

      <div class="copy-points">
        <article>
          <strong>手机号登录</strong>
          <p>手机号仍作为登录账号使用，修改后请在下次登录时使用新的手机号。</p>
        </article>
        <article>
          <strong>资料自动同步</strong>
          <p>这里保存的信息会同步更新到员工档案，保持账号资料与员工信息一致。</p>
        </article>
        <article>
          <strong>密码自行维护</strong>
          <p>如需修改密码，可在下方直接输入新密码；留空则保留当前密码。</p>
        </article>
      </div>
    </div>

    <div class="profile-card">
      <div>
        <p class="eyebrow">资料设置</p>
        <h2>更新个人信息</h2>
        <p class="hint">当前登录账号：{{ profile.username || '--' }}</p>
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
        新密码
        <input v-model="form.password" type="password" placeholder="留空则不修改" />
      </label>

      <label>
        确认新密码
        <input v-model="form.password_confirm" type="password" placeholder="请再次输入新密码" />
      </label>

      <button :disabled="isSubmitting" @click="saveProfile">
        {{ isSubmitting ? '保存中...' : '保存个人信息' }}
      </button>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api, setCurrentUser } from '@/lib/apiClient'

const isSubmitting = ref(false)
const isError = ref(false)
const message = ref('')
const profile = reactive({
  username: '',
  role: '',
  employee_id: null
})
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

function applyProfile(data) {
  profile.username = data?.username || ''
  profile.role = data?.role || ''
  profile.employee_id = data?.employee_id ?? null
  form.name = data?.name || ''
  form.nationality_status = data?.nationality_status || 'other'
  form.phone_country_code = data?.phone_country_code || '+65'
  form.phone_number = data?.phone_number || ''
  form.password = ''
  form.password_confirm = ''
}

async function loadProfile() {
  notify('')
  try {
    const data = await api.getMyProfile()
    applyProfile(data)
  } catch (error) {
    notify(`加载个人信息失败：${error.message}`, true)
  }
}

async function saveProfile() {
  if (!form.name.trim()) return notify('请输入姓名', true)
  if (!form.phone_number.trim()) return notify('请输入手机号', true)
  if (form.password || form.password_confirm) {
    if (form.password !== form.password_confirm) return notify('两次输入的密码不一致', true)
  }

  isSubmitting.value = true
  notify('')
  try {
    const data = await api.updateMyProfile({
      name: form.name.trim(),
      nationality_status: form.nationality_status,
      phone_country_code: form.phone_country_code,
      phone_number: form.phone_number.trim(),
      password: form.password,
      password_confirm: form.password_confirm
    })
    applyProfile(data)
    setCurrentUser(data.username)
    notify('个人信息已更新。')
  } catch (error) {
    notify(`保存个人信息失败：${error.message}`, true)
  } finally {
    isSubmitting.value = false
  }
}

onMounted(loadProfile)
</script>

<style scoped>
.profile-page {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(340px, 460px);
  gap: 24px;
  align-items: stretch;
}

.profile-copy {
  padding: clamp(24px, 4vw, 40px);
  border-radius: 32px;
  background: linear-gradient(155deg, rgba(255, 253, 248, 0.9), rgba(248, 233, 215, 0.78));
  border: 1px solid rgba(32, 51, 45, 0.08);
  box-shadow: 0 24px 60px rgba(20, 35, 31, 0.08);
  display: grid;
  align-content: space-between;
  gap: 28px;
}

.profile-card {
  padding: 24px;
  display: grid;
  gap: 14px;
  align-content: start;
  background: rgba(255, 253, 248, 0.82);
  border: 1px solid rgba(32, 51, 45, 0.1);
  border-radius: 24px;
  box-shadow: 0 18px 40px rgba(20, 35, 31, 0.08);
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--color-primary-dark);
}

.profile-copy h1 {
  margin: 0;
  max-width: 16ch;
  font-size: clamp(32px, 4vw, 52px);
  line-height: 1.06;
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

.copy-points article {
  padding: 16px;
  background: rgba(255, 253, 248, 0.82);
  border: 1px solid rgba(32, 51, 45, 0.1);
  border-radius: 24px;
  box-shadow: 0 18px 40px rgba(20, 35, 31, 0.08);
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

.profile-card h2 {
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
  grid-template-columns: 160px minmax(0, 1fr);
  gap: 12px;
}

.status {
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(55, 125, 88, 0.1);
  color: #285d41;
}

.status.error {
  background: rgba(185, 62, 62, 0.1);
  color: #9f2a2a;
}

@media (max-width: 1080px) {
  .profile-page {
    grid-template-columns: 1fr;
  }

  .copy-points {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .profile-copy,
  .profile-card {
    padding: 18px;
    border-radius: 24px;
  }

  .phone-grid {
    grid-template-columns: 1fr;
  }

  .profile-copy h1 {
    max-width: none;
    font-size: 34px;
  }
}
</style>
