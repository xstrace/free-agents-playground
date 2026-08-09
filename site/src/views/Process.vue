<template>
  <div v-if="list">
    <h2 class="page-title">{{ day }} <span style="color:var(--dim);font-size:12px">{{ list.length }} 条事件</span></h2>
    <div class="page-sub">最新在前 · 宿主注入已折叠</div>
    <div v-for="(ev, i) in list" :key="i" class="ev">
      <div class="head">
        <span class="t">{{ (ev.timestamp || '').slice(11, 19) }}</span>
        <el-tag v-if="ev.type === 'error'" size="small" type="danger">错误</el-tag>
        <el-tag v-else-if="role(ev) === 'user'" size="small" type="primary">宿主</el-tag>
        <el-tag v-else-if="role(ev) === 'assistant'" size="small" type="success">Pi</el-tag>
        <el-tag v-else-if="role(ev)" size="small" type="warning">{{ role(ev) }}</el-tag>
        <el-tag v-else size="small" type="info">{{ ev.type }}</el-tag>
      </div>
      <template v-if="ev.type === 'message'">
        <div v-if="isSystemInjection(ev)" class="body">
          <el-collapse>
            <el-collapse-item title="展开系统提示词" name="1">
              <pre style="white-space:pre-wrap">{{ systemText(ev) }}</pre>
            </el-collapse-item>
          </el-collapse>
        </div>
        <div v-else class="body md" v-html="blocksHtml(ev.message.content)"></div>
      </template>
      <div v-else class="body md" v-html="otherHtml(ev)"></div>
    </div>
  </div>
  <div v-else class="page-sub">加载中…</div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { fetchJson } from '../api'
import { renderMd, esc } from '../md'

const props = defineProps({ day: String, meta: Object })
const events = ref(null)
// 事件 JSON 为旧→新, 展示时倒序(新→旧)
const list = computed(() => (events.value ? [...events.value].reverse() : null))

watch(() => props.day, load, { immediate: true })
onMounted(load)

async function load() {
  events.value = null
  const url = props.meta?.events?.[props.day]
  if (!url) return
  events.value = await fetchJson(url)
}

function role(ev) { return ev.message?.role }
function isSystemInjection(ev) {
  const c = ev.message?.content
  const text = Array.isArray(c) ? c.filter(b => b?.type === 'text').map(b => b.text).join('') : String(c || '')
  return text.trim().startsWith('# ') && text.length > 300
}
function systemText(ev) {
  const c = ev.message?.content
  return Array.isArray(c) ? c.filter(b => b?.type === 'text').map(b => b.text).join('') : String(c || '')
}
function blocksHtml(content) {
  if (typeof content === 'string') return renderMd(content, true)
  if (!Array.isArray(content)) return esc(content)
  return content.map(b => {
    if (!b || typeof b !== 'object') return esc(b)
    switch (b.type) {
      case 'text': return renderMd(b.text || '', true)
      case 'thinking':
      case 'reasoning':
        return `<details><summary>思考</summary><div style="padding:8px 12px;background:#1c2129;border-left:2px solid #30363d;white-space:pre-wrap">${esc(b.text || '')}</div></details>`
      case 'toolCall': {
        const name = b.name || b.toolName || '?'
        let args = b.arguments || b.args || {}
        if (typeof args === 'string') { try { args = JSON.parse(args) } catch { args = { raw: args } } }
        if (name === 'bash' && args.command) {
          const cmd = String(args.command).trim()
          return `<div class="cmd"><span class="prompt">$ </span>${esc(cmd.length <= 500 ? cmd : cmd.slice(0, 497) + '...')}</div>`
        }
        const keys = ['path', 'file', 'url', 'query', 'pattern', 'dir', 'filename', 'name']
        const summ = {}
        keys.forEach(k => { if (args[k] !== undefined) summ[k] = String(args[k]).slice(0, 120) })
        let extra = Object.keys(summ).length ? JSON.stringify(summ) : JSON.stringify(args)
        if (extra.length > 200) extra = extra.slice(0, 197) + '...'
        return `<div style="font-family:ui-monospace,monospace;font-size:12.5px">[${esc(name)}] ${esc(extra)}</div>`
      }
      case 'toolResult': {
        let data = b.data
        if (typeof data === 'object' && data !== null) data = JSON.stringify(data, null, 1)
        data = String(data)
        if (data.length > 800) data = data.slice(0, 797) + '...'
        return `<div style="font-family:ui-monospace,monospace;font-size:12.5px;color:#c9d4e5">${esc(data)}</div>`
      }
      default: return esc(JSON.stringify(b).slice(0, 300))
    }
  }).join('')
}
function otherHtml(ev) {
  if (ev.type === 'error') return esc(JSON.stringify(ev).slice(0, 400))
  if (ev.type === 'model_change') return esc(ev.model || '?')
  return esc(JSON.stringify(ev).slice(0, 300))
}
</script>
