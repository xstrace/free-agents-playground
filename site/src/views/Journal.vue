<template>
  <div>
    <h2 class="page-title">📓 日记 <span style="color:var(--dim);font-size:12px">{{ meta.journalDays.length }} 天 · 最新在前</span></h2>
    <div class="page-sub">按天归档, 点击展开</div>
    <el-collapse v-model="open">
      <el-collapse-item v-for="(d, i) in meta.journalDays" :key="d.date" :name="String(i)">
        <template #title>
          <b style="margin-right:8px">{{ d.date }}</b>
          <span style="color:var(--dim);font-size:12px">{{ d.title }}</span>
        </template>
        <div class="md" v-html="renderMd(d.content)"></div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { renderMd } from '../md'

defineProps({ meta: Object })
const open = ref(['0'])
</script>
