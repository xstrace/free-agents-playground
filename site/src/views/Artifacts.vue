<template>
  <div class="art-layout">
    <div class="art-tree">
      <el-tree
        :data="treeData"
        node-key="key"
        :props="{ label: 'name', children: 'children' }"
        :default-expanded-keys="expanded"
        @node-click="onNode"
      >
        <template #default="{ data }">
          <span v-if="data.type === 'dir'">📁 {{ data.name || '/' }}</span>
          <span v-else>
            {{ icon(data.kind) }} {{ data.name }}
            <span style="color:var(--dim);font-size:10px;margin-left:8px">{{ sizeText(data.size) }}</span>
          </span>
        </template>
      </el-tree>
    </div>
    <div class="art-view" v-loading="loading">
      <div v-if="!content && !imgUrl" class="page-sub">← 从左侧文件树选择文件预览(可下载原文件)</div>
      <template v-else>
        <h2 class="page-title">{{ name }} <a v-if="imgUrl || raw" :href="'artifacts/' + raw" download style="font-size:12px;color:var(--accent)">下载</a></h2>
        <img v-if="imgUrl" :src="imgUrl" :alt="name" />
        <div v-else-if="kind === 'md'" class="md" v-html="renderMd(content)"></div>
        <div v-else class="md"><pre>{{ content }}</pre></div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { fetchText } from '../api'
import { renderMd, esc } from '../md'

const props = defineProps({ meta: Object })

const treeData = computed(() => props.meta.artifacts.children || [])
const expanded = computed(() =>
  (props.meta.artifacts.children || []).filter(c => c.type === 'dir').map(c => c.key))

const loading = ref(false)
const content = ref(null)
const imgUrl = ref(null)
const kind = ref('')
const name = ref('')
const raw = ref('')

function icon(k) { return { md: '📄', img: '🖼', code: '⚙️', bin: '🗜' }[k] || '🗜' }
function sizeText(s) { return s >= 1024 ? (s / 1024).toFixed(1) + ' KB' : s + ' B' }

async function onNode(node) {
  if (node.type === 'dir') return
  loading.value = true
  kind.value = node.kind
  name.value = node.name
  raw.value = node.url.replace('artifacts/', '')
  content.value = null
  imgUrl.value = null
  try {
    if (node.kind === 'img') imgUrl.value = node.url
    else content.value = await fetchText(node.url)
  } catch (e) {
    content.value = '加载失败: ' + e.message
  }
  loading.value = false
}
</script>
