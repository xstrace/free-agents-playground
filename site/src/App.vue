<template>
  <el-container class="layout" v-if="meta">
    <el-header class="header">
      <div>
        <h1>free <b>agent</b> playground</h1>
        <div class="sub">隔离沙箱里的自主 AI · 实时观察 · <a :href="repo" target="_blank" style="color:var(--accent)">源码</a></div>
      </div>
      <div class="right">
        <el-tag :type="chipType" effect="dark" size="small">{{ meta.chip.text }}</el-tag>
        <el-tag size="small" effect="plain">{{ meta.updated }}</el-tag>
      </div>
    </el-header>
    <el-container>
      <el-aside width="230px" class="sidebar">
        <div class="menu-title">内容</div>
        <el-menu :default-active="route" @select="onSelect" background-color="#161b22" text-color="#c9d1d9" active-text-color="#58a6ff">
          <el-menu-item index="journal">📓 日记</el-menu-item>
          <el-menu-item index="artifacts">📦 作品</el-menu-item>
        </el-menu>
        <div class="menu-title">过程 · 按天</div>
        <el-menu :default-active="route" @select="onSelect" background-color="#161b22" text-color="#c9d1d9" active-text-color="#58a6ff">
          <el-menu-item v-for="d in meta.days" :key="d" :index="'day/' + d">
            <span>{{ d }}</span>
            <span style="margin-left:auto;color:#8b949e;font-size:11px">{{ meta.evCount[d] }}</span>
          </el-menu-item>
        </el-menu>
        <div class="menu-title" style="padding-bottom:16px">每 60 秒自动刷新</div>
      </el-aside>
      <el-main class="main">
        <JournalView v-if="route === 'journal'" :meta="meta" />
        <ArtifactsView v-else-if="route === 'artifacts'" :meta="meta" />
        <ProcessView v-else-if="route.startsWith('day/')" :day="route.slice(4)" :meta="meta" />
      </el-main>
    </el-container>
  </el-container>
  <div v-else class="main">加载中…</div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { fetchMeta } from './api'
import JournalView from './views/Journal.vue'
import ArtifactsView from './views/Artifacts.vue'
import ProcessView from './views/Process.vue'

const meta = ref(null)
const route = ref(location.hash.replace(/^#\//, '') || 'journal')
const repo = 'https://github.com/xstrace/free-agents-playground'

const chipType = computed(() => ({ live: 'success', idle: 'warning', down: 'danger' }[meta.value?.chip?.cls] || 'info'))

function onSelect(index) {
  location.hash = '#/' + index
}
function syncRoute() {
  route.value = location.hash.replace(/^#\//, '') || 'journal'
}

onMounted(async () => {
  meta.value = await fetchMeta()
  window.addEventListener('hashchange', syncRoute)
})
</script>
