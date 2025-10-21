import { fieldRegistry } from '../../registry'
import { MqttDevicePickerField } from './MqttDevicePickerField'

// Register MQTT device picker field - universal component for all connectors
fieldRegistry.registerCustom({
  type: 'mqtt_device_picker',
  component: MqttDevicePickerField,
  connectors: undefined, // Available for all connectors
  displayName: 'MQTT Device Picker',
  description: 'Select devices from other connectors via MQTT discovery with search and pagination',
  validate: (value, field) => {
    if (!value && field.required) {
      return 'Please select a device to continue'
    }
    return null
  }
})
