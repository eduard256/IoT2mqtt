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
  // Try standard pattern (Yeelight, etc)
  const ipForm = flowState.form.ip_form || flowState.form.connection_form
  const deviceConfig = flowState.form.device_config || flowState.form.device_form

  if ((ipForm?.ip || ipForm?.host) && (deviceConfig?.friendly_name || deviceConfig?.name)) {
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

  // Try camera pattern
  const cameraForm = flowState.form.camera_form
  const networkForm = flowState.form.network_form
  const streamScan = flowState.form.stream_scan?.selected_stream

  if (cameraForm && networkForm?.address && streamScan) {
    // Parse model JSON
    let brandModel = 'Camera'
    let brand: string | undefined
    let model: string | undefined

    try {
      const modelData = JSON.parse(cameraForm.model)
      brandModel = modelData.display || `${modelData.brand} ${modelData.model}`
      brand = modelData.brand
      model = modelData.model
    } catch (e) {
      // If not JSON, use as is
      brandModel = cameraForm.model
    }

    // Parse IP from address
    const ip = parseIpFromAddress(networkForm.address)

    return {
      device_id: normalizeDeviceId(brandModel),
      ip: ip,
      port: streamScan.port || 554,
      name: brandModel,
      enabled: true,
      // Additional camera-specific fields
      stream_url: streamScan.full_url,
      stream_type: streamScan.type,
      username: cameraForm.username,
      password: cameraForm.password,
      channel: cameraForm.channel || 0,
      brand,
      model
    }
  }

  return null
}

function parseIpFromAddress(address: string): string {
  try {
    const url = new URL(address)
    return url.hostname
  } catch {
    // If not a valid URL, try to extract IP with regex
    const match = address.match(/(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/)
    return match ? match[1] : address
  }
}

export function isDuplicateDevice(device: any, devices: any[]): boolean {
  return devices.some(d => d.ip === device.ip || d.device_id === device.device_id)
}
