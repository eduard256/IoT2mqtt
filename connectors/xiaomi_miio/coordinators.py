"""
Update Coordinators for Xiaomi MiIO Integration
Manages periodic device state updates following Home Assistant patterns
"""

import threading
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from miio import Device as MiioDevice, DeviceException, RoborockVacuum

logger = logging.getLogger(__name__)


@dataclass
class VacuumCoordinatorData:
    """Data structure for vacuum coordinator - exact from HA"""
    status: Any
    dnd_status: Any
    last_clean_details: Any
    consumable_status: Any
    clean_history_status: Any
    timers: list
    fan_speeds: dict
    fan_speeds_reverse: dict


class DeviceCoordinator:
    """Base coordinator for device state updates"""
    
    def __init__(self, device: MiioDevice, update_interval: int = 15):
        """
        Initialize coordinator
        
        Args:
            device: MiIO device instance
            update_interval: Update interval in seconds
        """
        self.device = device
        self.update_interval = update_interval
        self.data = None
        self.last_update = None
        self.last_error = None
        self.error_count = 0
        self.max_errors = 3
        
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        
        logger.info(f"Initialized coordinator with {update_interval}s interval")
    
    def start(self):
        """Start the coordinator"""
        if self._thread and self._thread.is_alive():
            logger.warning("Coordinator already running")
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._update_loop, daemon=True)
        self._thread.start()
        logger.info("Coordinator started")
    
    def stop(self):
        """Stop the coordinator"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Coordinator stopped")
    
    def _update_loop(self):
        """Main update loop"""
        while not self._stop_event.is_set():
            try:
                # Perform update
                self._update_data()
                
                # Wait for next update
                self._stop_event.wait(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in coordinator loop: {e}")
                self._stop_event.wait(5)  # Short wait on error
    
    def _update_data(self):
        """Update device data"""
        try:
            # Get device status
            data = self._fetch_data()
            
            if data is not None:
                with self._lock:
                    self.data = data
                    self.last_update = datetime.now()
                    self.error_count = 0
                    self.last_error = None
                
                logger.debug("Updated device data successfully")
            
        except DeviceException as e:
            self.error_count += 1
            self.last_error = str(e)
            
            # Handle -9999 error with retry
            if getattr(e, "code", None) == -9999 and self.error_count < 2:
                logger.warning("Network issue, retrying...")
                time.sleep(1)
                try:
                    data = self._fetch_data()
                    if data:
                        with self._lock:
                            self.data = data
                            self.last_update = datetime.now()
                            self.error_count = 0
                            self.last_error = None
                except:
                    pass
            else:
                logger.error(f"Device error: {e}")
                
        except Exception as e:
            self.error_count += 1
            self.last_error = str(e)
            logger.error(f"Unexpected error updating data: {e}")
    
    def _fetch_data(self) -> Any:
        """Fetch data from device - override in subclasses"""
        return self.device.status()
    
    def get_state(self) -> Optional[Dict[str, Any]]:
        """Get current state"""
        with self._lock:
            if self.data is None:
                return None
            
            # Convert to dict
            state = {}
            if hasattr(self.data, '__dict__'):
                state = {k: v for k, v in self.data.__dict__.items() if not k.startswith('_')}
            else:
                state = {'status': self.data}
            
            # Add metadata
            state['last_update'] = self.last_update.isoformat() if self.last_update else None
            state['online'] = self.error_count < self.max_errors
            
            if self.last_error:
                state['error'] = self.last_error
            
            return state
    
    def force_update(self):
        """Force an immediate update"""
        self._update_data()


class VacuumCoordinator(DeviceCoordinator):
    """Specialized coordinator for vacuum devices"""
    
    def __init__(self, device: RoborockVacuum, update_interval: int = 15):
        """Initialize vacuum coordinator"""
        super().__init__(device, update_interval)
        self.device: RoborockVacuum = device  # Type hint for IDE
    
    def _fetch_data(self) -> VacuumCoordinatorData:
        """Fetch comprehensive vacuum data"""
        # Get timers separately (may fail on some devices)
        timers = []
        try:
            timers = self.device.timer()
        except DeviceException as e:
            logger.debug(f"Unable to fetch timers: {e}")
        
        # Get fan speed presets
        fan_speeds = self.device.fan_speed_presets()
        
        # Build coordinator data
        return VacuumCoordinatorData(
            status=self.device.status(),
            dnd_status=self.device.dnd_status(),
            last_clean_details=self.device.last_clean_details(),
            consumable_status=self.device.consumable_status(),
            clean_history_status=self.device.clean_history(),
            timers=timers,
            fan_speeds=fan_speeds,
            fan_speeds_reverse={v: k for k, v in fan_speeds.items()}
        )
    
    def get_state(self) -> Optional[Dict[str, Any]]:
        """Get vacuum state"""
        with self._lock:
            if self.data is None:
                return None
            
            data: VacuumCoordinatorData = self.data
            
            # Build state dict
            state = {
                'state': data.status.state,
                'state_code': data.status.state_code,
                'battery': data.status.battery,
                'fan_speed': data.status.fanspeed,
                'error': data.status.error if data.status.got_error else None,
                'cleaning_time': data.status.clean_time,
                'cleaned_area': data.status.clean_area,
                'dnd_enabled': data.status.dnd,
                'map_present': data.status.map_present,
                'in_cleaning': data.status.is_on,
                'is_charging': data.status.is_charging,
                'is_paused': data.status.is_paused,
                'water_tank_attached': getattr(data.status, 'water_tank_attached', None),
                'mop_attached': getattr(data.status, 'mop_attached', None)
            }
            
            # Add DND status
            if data.dnd_status:
                state['dnd'] = {
                    'enabled': data.dnd_status.enabled,
                    'start': str(data.dnd_status.start),
                    'end': str(data.dnd_status.end)
                }
            
            # Add consumables
            if data.consumable_status:
                state['consumables'] = {
                    'main_brush': data.consumable_status.main_brush,
                    'main_brush_left': data.consumable_status.main_brush_left,
                    'side_brush': data.consumable_status.side_brush,
                    'side_brush_left': data.consumable_status.side_brush_left,
                    'filter': data.consumable_status.filter,
                    'filter_left': data.consumable_status.filter_left,
                    'sensor_dirty': data.consumable_status.sensor_dirty,
                    'sensor_dirty_left': data.consumable_status.sensor_dirty_left
                }
            
            # Add last clean details
            if data.last_clean_details:
                state['last_clean'] = {
                    'start': data.last_clean_details.start.isoformat() if data.last_clean_details.start else None,
                    'end': data.last_clean_details.end.isoformat() if data.last_clean_details.end else None,
                    'duration': data.last_clean_details.duration,
                    'area': data.last_clean_details.area,
                    'completed': data.last_clean_details.completed
                }
            
            # Add clean history summary
            if data.clean_history_status:
                state['clean_history'] = {
                    'count': data.clean_history_status.count,
                    'total_duration': data.clean_history_status.total_duration,
                    'total_area': data.clean_history_status.total_area,
                    'dust_collection_count': getattr(data.clean_history_status, 'dust_collection_count', None)
                }
            
            # Add timers
            if data.timers:
                state['timers'] = []
                for timer in data.timers:
                    state['timers'].append({
                        'enabled': timer.enabled,
                        'cron': timer.cron,
                        'next_schedule': timer.next_schedule.isoformat() if timer.next_schedule else None
                    })
            
            # Add fan speed info
            state['fan_speeds'] = list(data.fan_speeds.keys()) if data.fan_speeds else []
            state['fan_speed_values'] = data.fan_speeds
            
            # Add metadata
            state['last_update'] = self.last_update.isoformat() if self.last_update else None
            state['online'] = self.error_count < self.max_errors
            
            if self.last_error:
                state['error_message'] = self.last_error
            
            return state


class GatewayCoordinator(DeviceCoordinator):
    """Coordinator for gateway devices with sub-devices"""
    
    def __init__(self, device: MiioDevice, update_interval: int = 15):
        """Initialize gateway coordinator"""
        super().__init__(device, update_interval)
        self.sub_device_coordinators = {}
    
    def add_sub_device(self, sid: str, sub_device: Any):
        """Add a sub-device coordinator"""
        coordinator = SubDeviceCoordinator(sub_device, self.update_interval)
        self.sub_device_coordinators[sid] = coordinator
        coordinator.start()
    
    def stop(self):
        """Stop coordinator and all sub-device coordinators"""
        super().stop()
        for coordinator in self.sub_device_coordinators.values():
            coordinator.stop()
    
    def get_sub_device_state(self, sid: str) -> Optional[Dict[str, Any]]:
        """Get state of a specific sub-device"""
        if sid in self.sub_device_coordinators:
            return self.sub_device_coordinators[sid].get_state()
        return None


class SubDeviceCoordinator(DeviceCoordinator):
    """Coordinator for gateway sub-devices"""
    
    def _fetch_data(self) -> Any:
        """Fetch sub-device data"""
        # Sub-devices update differently
        self.device.update()
        return {
            'status': self.device.status,
            'available': True
        }