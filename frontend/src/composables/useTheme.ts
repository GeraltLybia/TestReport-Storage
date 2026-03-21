import { onMounted, ref, watch } from 'vue'

export type Theme = 'dark' | 'light'

export function useTheme() {
  const theme = ref<Theme>('dark')

  function applyTheme(value: Theme) {
    document.documentElement.setAttribute('data-theme', value)
  }

  function toggleTheme() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  onMounted(() => {
    const saved = localStorage.getItem('theme')
    if (saved === 'dark' || saved === 'light') {
      theme.value = saved
    }
    applyTheme(theme.value)
  })

  watch(theme, (value) => {
    applyTheme(value)
    localStorage.setItem('theme', value)
  })

  return {
    theme,
    toggleTheme,
  }
}
