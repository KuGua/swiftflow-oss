// src/i18n/index.js
import { createI18n } from 'vue-i18n'
import zh from '../locales/zh.json'
import en from '../locales/en.json'

const messages = {
  zh,
  en
}

const i18n = createI18n({
  locale: 'zh', // 默认语言
  fallbackLocale: 'zh',
  messages
})

export default i18n