<script setup>
import { computed } from 'vue'
const props = defineProps({ stats: { type: Object, default: () => ({}) } })

// AI 态势总结：后端 Step 7 写入 stats.ai_summary；没有则占位（不报错）
const summary = computed(() => (props.stats.ai_summary || '').trim())
</script>

<template>
  <div class="card">
    <h3>📈 AI 态势总结</h3>
    <div class="summary">
      <template v-if="summary">{{ summary }}</template>
      <span v-else class="placeholder">分析中 / 开发中：接入 AI 分析层（Step 7）后，这里展示当日舆情态势的文字总结。</span>
    </div>
  </div>
</template>
