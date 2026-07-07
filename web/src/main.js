import { createApp } from 'vue'
import App from './App.vue'
import { vTip } from './directives/tip.js'
import './styles/global.css'

const app = createApp(App)
app.directive('tip', vTip)
app.mount('#app')
