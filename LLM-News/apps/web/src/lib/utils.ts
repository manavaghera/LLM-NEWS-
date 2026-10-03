import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** localStorage that never throws (private windows and blocked storage just skip saving). */
export const storage = {
  get(key: string): string | null {
    try {
      return window.localStorage.getItem(key)
    } catch {
      return null
    }
  },
  set(key: string, value: string) {
    try {
      window.localStorage.setItem(key, value)
    } catch {
      // storage unavailable; the app works without it
    }
  },
  remove(key: string) {
    try {
      window.localStorage.removeItem(key)
    } catch {
      // ignore
    }
  },
}
