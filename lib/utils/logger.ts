export function logInfo(event: string, data: Record<string, unknown> = {}) {
  console.log(JSON.stringify({ level: "info", event, ...data }));
}

export function logWarn(event: string, data: Record<string, unknown> = {}) {
  console.warn(JSON.stringify({ level: "warn", event, ...data }));
}

export function logError(event: string, data: Record<string, unknown> = {}) {
  console.error(JSON.stringify({ level: "error", event, ...data }));
}
