<script setup>
import { computed } from 'vue'
import { splitLinks } from '../api/links.js'
const props = defineProps({ text: String })
const parts = computed(() => splitLinks(props.text))
</script>

<template>
  <div class="message-text"><template v-for="(part, index) in parts" :key="index"><a v-if="part.url" :href="part.url" target="_blank" rel="noopener noreferrer">{{ part.text }}</a><template v-else>{{ part.text }}</template></template></div>
</template>
