import { createApp } from 'vue'
import './assets/style/global.css'
import './assets/style/ui.css'
import App from './App.vue'
import router from './router'

createApp(App).use(router).mount('#app')
