import { useState, useCallback, useRef } from 'react'
import { buildCurrentDevice, isDuplicateDevice } from '../utils/deviceUtils'
import type { FlowState } from '../types'

export function useDeviceManager(
  flowState: FlowState,
  updateFlowState: (updater: (prev: FlowState) => FlowState) => void,
  initialDevices: any[] = []
) {
  const [collectedDevices, setCollectedDevices] = useState<any[]>(initialDevices)
  const isManuallyAddingDevice = useRef(false)

  const addCurrentDevice = useCallback(() => {
    const currentDevice = buildCurrentDevice(flowState)
    if (currentDevice && !isDuplicateDevice(currentDevice, collectedDevices)) {
      setCollectedDevices(prev => [...prev, currentDevice])
      return true
    }
    return false
  }, [flowState, collectedDevices])

  const removeDevice = useCallback((index: number) => {
    setCollectedDevices(prev => prev.filter((_, i) => i !== index))
  }, [])

  const clearLoopForms = useCallback(
    (loopSteps: string[]) => {
      updateFlowState(prev => {
        const newForm = { ...prev.form }
        loopSteps.forEach(stepId => {
          delete newForm[stepId]
        })
        return { ...prev, form: newForm }
      })
    },
    [updateFlowState]
  )

  const editDevice = useCallback(
    (index: number) => {
      const deviceToEdit = collectedDevices[index]
      if (!deviceToEdit) return

      // Pre-fill forms
      const ipFormData = {
        ip: deviceToEdit.ip,
        port: deviceToEdit.port || 55443
      }

      const deviceConfigData = {
        friendly_name: deviceToEdit.name,
        ...deviceToEdit
      }

      updateFlowState(prev => ({
        ...prev,
        form: {
          ...prev.form,
          ip_form: ipFormData,
          device_config: deviceConfigData
        }
      }))

      // Remove from list (will be re-added)
      removeDevice(index)
      isManuallyAddingDevice.current = true
    },
    [collectedDevices, updateFlowState, removeDevice]
  )

  return {
    collectedDevices,
    setCollectedDevices,
    isManuallyAddingDevice,
    addCurrentDevice,
    removeDevice,
    editDevice,
    clearLoopForms
  }
}
