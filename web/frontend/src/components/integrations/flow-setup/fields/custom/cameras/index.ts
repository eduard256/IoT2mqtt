import { fieldRegistry } from '../../registry'
import { CameraModelPicker } from './CameraModelPicker'
import { StreamScannerField } from './StreamScannerField'

// Register camera model picker field
fieldRegistry.registerCustom({
  type: 'camera_model_picker',
  component: CameraModelPicker,
  connectors: ['cameras'],
  displayName: 'Camera Model Picker',
  description: 'Search and select camera brand and model from database',
  validate: (value, field) => {
    if (!value && field.required) {
      return `${field.label ?? field.name} is required`
    }
    return null
  }
})

// Register stream scanner field
fieldRegistry.registerCustom({
  type: 'camera_stream_scanner',
  component: StreamScannerField,
  connectors: ['cameras'],
  displayName: 'Camera Stream Scanner',
  description: 'Asynchronously scan and test camera stream URLs',
  validate: (value, field) => {
    if (!value && field.required) {
      return 'Please select a stream to continue'
    }
    return null
  }
})
