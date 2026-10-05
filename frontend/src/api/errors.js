export class ApiError extends Error {
  constructor(message, status = 0, retryAfter = 0) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.retryAfter = retryAfter
    // 这些状态在生成和保存之前返回；网络中断仍需核对服务端记录。
    this.notAccepted = [404, 409, 422, 429].includes(status)
  }
}

export function responseError(status, data = {}, retryHeader) {
  const raw = retryHeader ?? data.data?.retry_after
  let seconds = Number(raw)
  if (!Number.isFinite(seconds) && raw) seconds = Math.ceil((Date.parse(raw) - Date.now()) / 1000)
  if (!Number.isFinite(seconds) || seconds <= 0) seconds = 60
  return new ApiError(data.message || `服务返回 ${status}`, status,
    status === 429 ? Math.ceil(seconds) : 0)
}

export function createCooldown(clock = () => performance.now()) {
  let until = 0
  return {
    remaining: () => Math.max(0, Math.ceil((until - clock()) / 1000)),
    block(seconds) { until = Math.max(until, clock() + seconds * 1000) },
    ensureAvailable() {
      const seconds = this.remaining()
      if (seconds) throw new ApiError(`请等待 ${seconds} 秒后再试`, 429, seconds)
    },
  }
}

export const cooldown = createCooldown()
