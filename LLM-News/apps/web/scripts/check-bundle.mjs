import { readdir, stat } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../dist/assets/', import.meta.url))
const files = await readdir(root)
const scripts = await Promise.all(files.filter((name) => name.endsWith('.js')).map(async (name) => ({ name, bytes: (await stat(join(root, name))).size })))
const largest = scripts.reduce((max, file) => file.bytes > max.bytes ? file : max, { name: '', bytes: 0 })
const total = scripts.reduce((sum, file) => sum + file.bytes, 0)
const kb = (bytes) => Math.round(bytes / 1024)
console.log(`JavaScript budget: ${kb(total)} KiB total; largest chunk ${largest.name} is ${kb(largest.bytes)} KiB`)
if (largest.bytes > 575 * 1024 || total > 1300 * 1024) {
  console.error('JavaScript bundle exceeds the launch performance budget.')
  process.exit(1)
}
