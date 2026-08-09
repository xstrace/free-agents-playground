export async function fetchMeta() {
  const r = await fetch('data/meta.json')
  if (!r.ok) throw new Error('meta ' + r.status)
  return r.json()
}
export async function fetchJson(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(url + ' ' + r.status)
  return r.json()
}
export async function fetchText(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(url + ' ' + r.status)
  return r.text()
}
