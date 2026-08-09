import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

export function renderMd(text, compact = false) {
  let html = md.render(text || '')
  if (compact) {
    html = html.replace(/<h([1-4])>/g, '<p class="md-h">').replace(/<\/h[1-4]>/g, '</p>')
  }
  return html
}

export function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}
