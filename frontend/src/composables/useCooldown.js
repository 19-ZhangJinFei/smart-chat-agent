import { ref, onMounted, onUnmounted } from 'vue'
import { cooldown } from '../api/errors.js'

export function useCooldown() {
  const retrySeconds = ref(cooldown.remaining())
  let timer
  onMounted(() => { timer = setInterval(() => { retrySeconds.value = cooldown.remaining() }, 250) })
  onUnmounted(() => clearInterval(timer))
  return retrySeconds
}
