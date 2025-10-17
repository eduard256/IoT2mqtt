export function normalizeDeviceId(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s_-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
}

export function generateInstanceId(integrationName: string): string {
  const randomSuffix = Math.random().toString(36).substring(2, 8).toLowerCase()
  return `${integrationName}_${randomSuffix}`
}

export function buildCurrentDevice(flowState: any): any | null {
  const ipForm = flowState.form.ip_form || flowState.form.connection_form
  const deviceConfig = flowState.form.device_config || flowState.form.device_form

  if (!ipForm?.ip && !ipForm?.host) return null
  if (!deviceConfig?.friendly_name && !deviceConfig?.name) return null

  const deviceName = deviceConfig.friendly_name || deviceConfig.name
  const deviceIp = ipForm.ip || ipForm.host

  return {
    device_id: normalizeDeviceId(deviceName),
    ip: deviceIp,
    port: ipForm.port || 55443,
    name: deviceName,
    enabled: true
  }
}

export function isDuplicateDevice(device: any, devices: any[]): boolean {
  return devices.some(d => d.ip === device.ip || d.device_id === device.device_id)
}
