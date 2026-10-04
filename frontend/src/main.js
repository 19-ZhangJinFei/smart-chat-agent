import { createApp } from 'vue'
import { ElButton, ElInput, ElIcon, ElSwitch, ElRadioGroup, ElRadioButton } from 'element-plus'
import 'element-plus/dist/index.css'
import './style.css'
import App from './App.vue'

const app = createApp(App)
for (const component of [ElButton, ElInput, ElIcon, ElSwitch, ElRadioGroup, ElRadioButton]) {
  app.component(component.name, component)
}
app.mount('#app')
