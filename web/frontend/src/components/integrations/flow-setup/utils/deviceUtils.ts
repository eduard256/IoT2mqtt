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
  console.log('[buildCurrentDevice] Starting device build...')
  console.log('[buildCurrentDevice] flowState.form:', JSON.stringify(flowState.form, null, 2))

  // Try mqtt_device_picker pattern (parasitic connectors like cameras-motion)
  // Check all possible step IDs that might contain mqtt_device_picker field
  for (const stepId of Object.keys(flowState.form)) {
    const stepData = flowState.form[stepId]
    console.log(`[buildCurrentDevice] Checking stepId: ${stepId}`, stepData)

    // Look for any field that has the mqtt_device_picker structure
    for (const fieldName of Object.keys(stepData || {})) {
      const fieldValue = stepData[fieldName]
      console.log(`[buildCurrentDevice] Checking field: ${fieldName}`, fieldValue)

      if (
        fieldValue &&
        typeof fieldValue === 'object' &&
        fieldValue.mqtt_path &&
        fieldValue.device_id &&
        fieldValue.extracted_data
      ) {
        console.log('[buildCurrentDevice] ✅ Found mqtt_device_picker data!')
        console.log('[buildCurrentDevice] fieldValue:', fieldValue)

        // Found mqtt_device_picker data
        const extracted = fieldValue.extracted_data
        console.log('[buildCurrentDevice] extracted_data:', extracted)

        // Build device object with fallbacks for missing fields
        const device: any = {
          device_id: fieldValue.device_id,
          mqtt_path: fieldValue.mqtt_path,
          instance_id: fieldValue.instance_id,
          enabled: true
        }

        // Add extracted fields with proper fallbacks
        if (extracted.ip) device.ip = extracted.ip
        if (extracted.port) device.port = extracted.port
        if (extracted.name) device.name = extracted.name

        // If no name but have device_id, use device_id as fallback
        if (!device.name) device.name = fieldValue.device_id

        // Include all other extracted fields
        Object.keys(extracted).forEach(key => {
          if (!device[key]) {
            device[key] = extracted[key]
          }
        })

        console.log('[buildCurrentDevice] ✅ Built device:', device)
        return device
      }
    }
  }

  console.log('[buildCurrentDevice] No mqtt_device_picker found, trying standard pattern...')

  // Try standard pattern (Yeelight, etc)
  const ipForm = flowState.form.ip_form || flowState.form.connection_form
  const deviceConfig = flowState.form.device_config || flowState.form.device_form

  if ((ipForm?.ip || ipForm?.host) && (deviceConfig?.friendly_name || deviceConfig?.name)) {
    const deviceName = deviceConfig.friendly_name || deviceConfig.name
    const deviceIp = ipForm.ip || ipForm.host

    console.log('[buildCurrentDevice] ✅ Built device from standard pattern')
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
    let brand: string | undefined
    let model: string | undefined

    try {
      const modelData = JSON.parse(cameraForm.model)
      brand = modelData.brand
      model = modelData.model
    } catch (e) {
      // If not JSON, use as is
      brand = cameraForm.model
    }

    // Parse IP from address
    const ip = parseIpFromAddress(networkForm.address)
    const channel = cameraForm.channel || 0

    // Generate device_id (always IP-based for uniqueness)
    const deviceId = `${ip.replace(/\./g, '_')}_${channel}`

    // Use friendly_name if provided, otherwise use IP_channel format
    const deviceName = networkForm.friendly_name?.trim() || `${ip}_${channel}`

    return {
      device_id: deviceId,
      ip: ip,
      port: streamScan.port || 554,
      name: deviceName,
      enabled: true,
      // Additional camera-specific fields
      stream_url: streamScan.full_url,
      stream_type: streamScan.type,
      username: cameraForm.username,
      password: cameraForm.password,
      channel: channel,
      brand,
      model
    }
  }

  console.log('[buildCurrentDevice] ❌ No device pattern matched, returning null')
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
  return devices.some(d => d.device_id === device.device_id)
}
