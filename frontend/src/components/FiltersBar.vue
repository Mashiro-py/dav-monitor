<script setup>
import { reactive } from 'vue'
const emit = defineEmits(['change'])
const f = reactive({ source: '', sentiment: '', keyword: '', start: '', end: '' })

function apply() { emit('change', { ...f }) }
function reset() { f.source = ''; f.sentiment = ''; f.keyword = ''; f.start = ''; f.end = ''; apply() }
</script>

<template>
  <div class="card">
    <div class="filters">
      <select v-model="f.source" @change="apply">
        <option value="">全部来源</option>
        <option value="weibo">微博</option>
        <option value="x">X</option>
        <option value="wechat">公众号</option>
      </select>
      <select v-model="f.sentiment" @change="apply">
        <option value="">全部情感</option>
        <option value="positive">正面</option>
        <option value="negative">负面</option>
        <option value="neutral">中性</option>
      </select>
      <input class="grow" v-model="f.keyword" placeholder="关键词（标题/正文/账号）" @keyup.enter="apply" />
      <input type="date" v-model="f.start" @change="apply" title="起始发布日期" />
      <input type="date" v-model="f.end" @change="apply" title="结束发布日期" />
      <button @click="apply">筛选</button>
      <button class="ghost" @click="reset">重置</button>
    </div>
  </div>
</template>
