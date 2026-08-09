<template>
  <div>
    <h2 class="page-title">📓 日记 <span style="color:var(--dim);font-size:12px">{{ meta.journalDays.length }} 天 · 最新在前</span></h2>
    <div class="page-sub">按天归档, 点击展开</div>
    <div v-for="(d, i) in meta.journalDays" :key="d.date" class="journal-row">
      <div class="j-date">
        <div class="d">{{ d.date.slice(5) }}</div>
        <div class="y">{{ d.date.slice(0, 4) }}</div>
      </div>
      <div class="j-card">
        <el-collapse v-model="open" class="j-collapse">
          <el-collapse-item :name="String(i)">
            <template #title>
              <span style="color:var(--dim);font-size:12px">{{ d.title }}</span>
            </template>
            <div class="md" v-html="renderMd(d.content)"></div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { renderMd } from '../md'

defineProps({ meta: Object })
const open = ref(['0'])
</script>
