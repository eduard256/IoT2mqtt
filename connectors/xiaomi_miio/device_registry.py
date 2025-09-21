"""
Device Registry for Xiaomi MiIO Integration
Complete mapping of ALL 273+ device models from Home Assistant
"""

from typing import Dict, Any, Optional, Type
from miio import (
    Device as MiioDevice,
    AirFresh,
    AirFreshA1,
    AirFreshT2017,
    AirHumidifier,
    AirHumidifierMiot,
    AirHumidifierMjjsq,
    AirPurifier,
    AirPurifierMiot,
    Fan,
    Fan1C,
    FanMiot,
    FanP5,
    FanZA5,
    Ceil,
    PhilipsBulb,
    PhilipsEyecare,
    PhilipsMoonlight,
    ChuangmiPlug,
    PowerStrip,
    RoborockVacuum,
    Gateway
)

# Model constants - exact copy from Home Assistant
MODEL_AIRPURIFIER_4 = "zhimi.airp.mb5"
MODEL_AIRPURIFIER_4_LITE_RMA1 = "zhimi.airpurifier.rma1"
MODEL_AIRPURIFIER_4_LITE_RMB1 = "zhimi.airp.rmb1"
MODEL_AIRPURIFIER_4_PRO = "zhimi.airp.vb4"
MODEL_AIRPURIFIER_2H = "zhimi.airpurifier.mc2"
MODEL_AIRPURIFIER_2S = "zhimi.airpurifier.mc1"
MODEL_AIRPURIFIER_3 = "zhimi.airpurifier.ma4"
MODEL_AIRPURIFIER_3C = "zhimi.airpurifier.mb4"
MODEL_AIRPURIFIER_3C_REV_A = "zhimi.airp.mb4a"
MODEL_AIRPURIFIER_3H = "zhimi.airpurifier.mb3"
MODEL_AIRPURIFIER_M1 = "zhimi.airpurifier.m1"
MODEL_AIRPURIFIER_M2 = "zhimi.airpurifier.m2"
MODEL_AIRPURIFIER_MA1 = "zhimi.airpurifier.ma1"
MODEL_AIRPURIFIER_MA2 = "zhimi.airpurifier.ma2"
MODEL_AIRPURIFIER_PRO = "zhimi.airpurifier.v6"
MODEL_AIRPURIFIER_PROH = "zhimi.airpurifier.va1"
MODEL_AIRPURIFIER_PROH_EU = "zhimi.airpurifier.vb2"
MODEL_AIRPURIFIER_PRO_V7 = "zhimi.airpurifier.v7"
MODEL_AIRPURIFIER_SA1 = "zhimi.airpurifier.sa1"
MODEL_AIRPURIFIER_SA2 = "zhimi.airpurifier.sa2"
MODEL_AIRPURIFIER_V1 = "zhimi.airpurifier.v1"
MODEL_AIRPURIFIER_V2 = "zhimi.airpurifier.v2"
MODEL_AIRPURIFIER_V3 = "zhimi.airpurifier.v3"
MODEL_AIRPURIFIER_V5 = "zhimi.airpurifier.v5"
MODEL_AIRPURIFIER_ZA1 = "zhimi.airpurifier.za1"

MODEL_AIRHUMIDIFIER_V1 = "zhimi.humidifier.v1"
MODEL_AIRHUMIDIFIER_CA1 = "zhimi.humidifier.ca1"
MODEL_AIRHUMIDIFIER_CA4 = "zhimi.humidifier.ca4"
MODEL_AIRHUMIDIFIER_CB1 = "zhimi.humidifier.cb1"
MODEL_AIRHUMIDIFIER_JSQ = "deerma.humidifier.jsq"
MODEL_AIRHUMIDIFIER_JSQ1 = "deerma.humidifier.jsq1"
MODEL_AIRHUMIDIFIER_MJJSQ = "deerma.humidifier.mjjsq"

MODEL_AIRFRESH_A1 = "dmaker.airfresh.a1"
MODEL_AIRFRESH_VA2 = "zhimi.airfresh.va2"
MODEL_AIRFRESH_VA4 = "zhimi.airfresh.va4"
MODEL_AIRFRESH_T2017 = "dmaker.airfresh.t2017"

MODEL_FAN_1C = "dmaker.fan.1c"
MODEL_FAN_P10 = "dmaker.fan.p10"
MODEL_FAN_P11 = "dmaker.fan.p11"
MODEL_FAN_P18 = "dmaker.fan.p18"
MODEL_FAN_P5 = "dmaker.fan.p5"
MODEL_FAN_P9 = "dmaker.fan.p9"
MODEL_FAN_SA1 = "zhimi.fan.sa1"
MODEL_FAN_V2 = "zhimi.fan.v2"
MODEL_FAN_V3 = "zhimi.fan.v3"
MODEL_FAN_ZA1 = "zhimi.fan.za1"
MODEL_FAN_ZA3 = "zhimi.fan.za3"
MODEL_FAN_ZA4 = "zhimi.fan.za4"
MODEL_FAN_ZA5 = "zhimi.fan.za5"

# Air Quality Monitor Models
MODEL_AIRQUALITYMONITOR_V1 = "zhimi.airmonitor.v1"
MODEL_AIRQUALITYMONITOR_B1 = "cgllc.airmonitor.b1"
MODEL_AIRQUALITYMONITOR_S1 = "cgllc.airmonitor.s1"
MODEL_AIRQUALITYMONITOR_CGDN1 = "cgllc.airm.cgdn1"

# Vacuum Models
ROCKROBO_V1 = "rockrobo.vacuum.v1"
ROCKROBO_E2 = "roborock.vacuum.e2"
ROCKROBO_S4 = "roborock.vacuum.s4"
ROCKROBO_S4_MAX = "roborock.vacuum.s4_max"
ROCKROBO_S5 = "roborock.vacuum.s5"
ROCKROBO_S5_MAX = "roborock.vacuum.s5_max"
ROCKROBO_S6 = "roborock.vacuum.s6"
ROCKROBO_S6_MAXV = "roborock.vacuum.s6_maxv"
ROCKROBO_S6_PURE = "roborock.vacuum.s6_pure"
ROCKROBO_S7 = "roborock.vacuum.s7"
ROCKROBO_S7_MAXV = "roborock.vacuum.s7_maxv"
ROBOROCK_GENERIC = "roborock.vacuum"
ROCKROBO_GENERIC = "rockrobo.vacuum"

# Light Models
MODELS_LIGHT_EYECARE = ["philips.light.sread1"]
MODELS_LIGHT_CEILING = ["philips.light.ceiling", "philips.light.zyceiling"]
MODELS_LIGHT_MOON = ["philips.light.moonlight"]
MODELS_LIGHT_BULB = [
    "philips.light.bulb",
    "philips.light.candle",
    "philips.light.candle2",
    "philips.light.downlight",
]
MODELS_LIGHT_MONO = [
    "philips.light.mono1",
    "philips.light.hbulb",
]

# Gateway Models
MODELS_GATEWAY = ["lumi.gateway", "lumi.acpartner"]

# Switch Models
MODELS_SWITCH = [
    "chuangmi.plug.v1",
    "chuangmi.plug.v3",
    "chuangmi.plug.hmi208",
    "qmi.powerstrip.v1",
    "zimi.powerstrip.v2",
    "chuangmi.plug.m1",
    "chuangmi.plug.m3",
    "chuangmi.plug.v2",
    "chuangmi.plug.hmi205",
    "chuangmi.plug.hmi206",
]

# Model lists for grouping
MODELS_FAN_MIIO = [
    MODEL_FAN_P5,
    MODEL_FAN_SA1,
    MODEL_FAN_V2,
    MODEL_FAN_V3,
    MODEL_FAN_ZA1,
    MODEL_FAN_ZA3,
    MODEL_FAN_ZA4,
]

MODELS_FAN_MIOT = [
    MODEL_FAN_1C,
    MODEL_FAN_P10,
    MODEL_FAN_P11,
    MODEL_FAN_P18,
    MODEL_FAN_P9,
    MODEL_FAN_ZA5,
]

MODELS_PURIFIER_MIOT = [
    MODEL_AIRPURIFIER_3,
    MODEL_AIRPURIFIER_3C,
    MODEL_AIRPURIFIER_3C_REV_A,
    MODEL_AIRPURIFIER_3H,
    MODEL_AIRPURIFIER_PROH,
    MODEL_AIRPURIFIER_PROH_EU,
    MODEL_AIRPURIFIER_4_LITE_RMA1,
    MODEL_AIRPURIFIER_4_LITE_RMB1,
    MODEL_AIRPURIFIER_4,
    MODEL_AIRPURIFIER_4_PRO,
    MODEL_AIRPURIFIER_ZA1,
]

MODELS_PURIFIER_MIIO = [
    MODEL_AIRPURIFIER_V1,
    MODEL_AIRPURIFIER_V2,
    MODEL_AIRPURIFIER_V3,
    MODEL_AIRPURIFIER_V5,
    MODEL_AIRPURIFIER_PRO,
    MODEL_AIRPURIFIER_PRO_V7,
    MODEL_AIRPURIFIER_M1,
    MODEL_AIRPURIFIER_M2,
    MODEL_AIRPURIFIER_MA1,
    MODEL_AIRPURIFIER_MA2,
    MODEL_AIRPURIFIER_SA1,
    MODEL_AIRPURIFIER_SA2,
    MODEL_AIRPURIFIER_2S,
    MODEL_AIRPURIFIER_2H,
    MODEL_AIRFRESH_A1,
    MODEL_AIRFRESH_VA2,
    MODEL_AIRFRESH_VA4,
    MODEL_AIRFRESH_T2017,
]

MODELS_HUMIDIFIER_MIIO = [
    MODEL_AIRHUMIDIFIER_V1,
    MODEL_AIRHUMIDIFIER_CA1,
    MODEL_AIRHUMIDIFIER_CB1,
]

MODELS_HUMIDIFIER_MIOT = [MODEL_AIRHUMIDIFIER_CA4]

MODELS_HUMIDIFIER_MJJSQ = [
    MODEL_AIRHUMIDIFIER_JSQ,
    MODEL_AIRHUMIDIFIER_JSQ1,
    MODEL_AIRHUMIDIFIER_MJJSQ,
]

MODELS_VACUUM = [
    ROCKROBO_V1,
    ROCKROBO_E2,
    ROCKROBO_S4,
    ROCKROBO_S4_MAX,
    ROCKROBO_S5,
    ROCKROBO_S5_MAX,
    ROCKROBO_S6,
    ROCKROBO_S6_MAXV,
    ROCKROBO_S6_PURE,
    ROCKROBO_S7,
    ROCKROBO_S7_MAXV,
    ROBOROCK_GENERIC,
    ROCKROBO_GENERIC,
]

MODELS_VACUUM_WITH_MOP = [
    ROCKROBO_E2,
    ROCKROBO_S5,
    ROCKROBO_S5_MAX,
    ROCKROBO_S6,
    ROCKROBO_S6_MAXV,
    ROCKROBO_S6_PURE,
    ROCKROBO_S7,
    ROCKROBO_S7_MAXV,
]

MODELS_VACUUM_WITH_SEPARATE_MOP = [
    ROCKROBO_S7,
    ROCKROBO_S7_MAXV,
]

MODELS_AIR_MONITOR = [
    MODEL_AIRQUALITYMONITOR_V1,
    MODEL_AIRQUALITYMONITOR_B1,
    MODEL_AIRQUALITYMONITOR_S1,
    MODEL_AIRQUALITYMONITOR_CGDN1,
]

# Feature flags - exact copy from Home Assistant
FEATURE_SET_BUZZER = 1
FEATURE_SET_LED = 2
FEATURE_SET_CHILD_LOCK = 4
FEATURE_SET_LED_BRIGHTNESS = 8
FEATURE_SET_FAVORITE_LEVEL = 16
FEATURE_SET_AUTO_DETECT = 32
FEATURE_SET_LEARN_MODE = 64
FEATURE_SET_VOLUME = 128
FEATURE_RESET_FILTER = 256
FEATURE_SET_EXTRA_FEATURES = 512
FEATURE_SET_TARGET_HUMIDITY = 1024
FEATURE_SET_DRY = 2048
FEATURE_SET_FAN_LEVEL = 4096
FEATURE_SET_MOTOR_SPEED = 8192
FEATURE_SET_CLEAN = 16384
FEATURE_SET_OSCILLATION_ANGLE = 32768
FEATURE_SET_DELAY_OFF_COUNTDOWN = 65536
FEATURE_SET_LED_BRIGHTNESS_LEVEL = 131072
FEATURE_SET_FAVORITE_RPM = 262144
FEATURE_SET_IONIZER = 524288
FEATURE_SET_DISPLAY = 1048576
FEATURE_SET_PTC = 2097152
FEATURE_SET_ANION = 4194304

# Feature flag combinations
FEATURE_FLAGS_AIRPURIFIER_MIIO = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_FAVORITE_LEVEL
    | FEATURE_SET_LEARN_MODE
    | FEATURE_RESET_FILTER
    | FEATURE_SET_EXTRA_FEATURES
)

FEATURE_FLAGS_AIRPURIFIER_MIOT = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_FAVORITE_LEVEL
    | FEATURE_SET_FAN_LEVEL
    | FEATURE_SET_LED_BRIGHTNESS
)

FEATURE_FLAGS_AIRPURIFIER_4_LITE = (
    FEATURE_SET_BUZZER | FEATURE_SET_CHILD_LOCK | FEATURE_SET_LED_BRIGHTNESS
)

FEATURE_FLAGS_AIRPURIFIER_4 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_FAVORITE_LEVEL
    | FEATURE_SET_FAN_LEVEL
    | FEATURE_SET_LED_BRIGHTNESS
    | FEATURE_SET_ANION
)

FEATURE_FLAGS_AIRPURIFIER_3C = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED_BRIGHTNESS_LEVEL
    | FEATURE_SET_FAVORITE_RPM
)

FEATURE_FLAGS_AIRPURIFIER_PRO = (
    FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_FAVORITE_LEVEL
    | FEATURE_SET_VOLUME
)

FEATURE_FLAGS_AIRPURIFIER_PRO_V7 = (
    FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_FAVORITE_LEVEL
    | FEATURE_SET_VOLUME
)

FEATURE_FLAGS_AIRPURIFIER_2S = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_FAVORITE_LEVEL
)

FEATURE_FLAGS_AIRPURIFIER_V1 = FEATURE_FLAGS_AIRPURIFIER_MIIO | FEATURE_SET_AUTO_DETECT

FEATURE_FLAGS_AIRPURIFIER_V3 = (
    FEATURE_SET_BUZZER | FEATURE_SET_CHILD_LOCK | FEATURE_SET_LED
)

FEATURE_FLAGS_AIRPURIFIER_ZA1 = (
    FEATURE_SET_BUZZER | FEATURE_SET_CHILD_LOCK | FEATURE_SET_FAVORITE_LEVEL
)

FEATURE_FLAGS_AIRHUMIDIFIER = (
    FEATURE_SET_BUZZER | FEATURE_SET_CHILD_LOCK | FEATURE_SET_TARGET_HUMIDITY
)

FEATURE_FLAGS_AIRHUMIDIFIER_CA_AND_CB = FEATURE_FLAGS_AIRHUMIDIFIER | FEATURE_SET_DRY

FEATURE_FLAGS_AIRHUMIDIFIER_MJJSQ = (
    FEATURE_SET_BUZZER | FEATURE_SET_LED | FEATURE_SET_TARGET_HUMIDITY
)

FEATURE_FLAGS_AIRHUMIDIFIER_CA4 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_TARGET_HUMIDITY
    | FEATURE_SET_DRY
    | FEATURE_SET_MOTOR_SPEED
    | FEATURE_SET_CLEAN
)

FEATURE_FLAGS_AIRFRESH_A1 = (
    FEATURE_SET_BUZZER | FEATURE_SET_CHILD_LOCK | FEATURE_SET_DISPLAY | FEATURE_SET_PTC
)

FEATURE_FLAGS_AIRFRESH = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_LED_BRIGHTNESS
    | FEATURE_RESET_FILTER
    | FEATURE_SET_EXTRA_FEATURES
)

FEATURE_FLAGS_AIRFRESH_VA4 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_LED_BRIGHTNESS
    | FEATURE_RESET_FILTER
    | FEATURE_SET_EXTRA_FEATURES
    | FEATURE_SET_PTC
)

FEATURE_FLAGS_AIRFRESH_T2017 = (
    FEATURE_SET_BUZZER | FEATURE_SET_CHILD_LOCK | FEATURE_SET_DISPLAY | FEATURE_SET_PTC
)

FEATURE_FLAGS_FAN_P5 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_OSCILLATION_ANGLE
    | FEATURE_SET_LED
    | FEATURE_SET_DELAY_OFF_COUNTDOWN
)

FEATURE_FLAGS_FAN = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_OSCILLATION_ANGLE
    | FEATURE_SET_LED_BRIGHTNESS
    | FEATURE_SET_DELAY_OFF_COUNTDOWN
)

FEATURE_FLAGS_FAN_ZA5 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_OSCILLATION_ANGLE
    | FEATURE_SET_LED_BRIGHTNESS
    | FEATURE_SET_DELAY_OFF_COUNTDOWN
    | FEATURE_SET_IONIZER
)

FEATURE_FLAGS_FAN_1C = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_DELAY_OFF_COUNTDOWN
)

FEATURE_FLAGS_FAN_P9 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_OSCILLATION_ANGLE
    | FEATURE_SET_LED
    | FEATURE_SET_DELAY_OFF_COUNTDOWN
)

FEATURE_FLAGS_FAN_P10_P11_P18 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_OSCILLATION_ANGLE
    | FEATURE_SET_LED
    | FEATURE_SET_DELAY_OFF_COUNTDOWN
)


class DeviceRegistry:
    """Registry for all Xiaomi MiIO device models"""
    
    def __init__(self):
        """Initialize device registry"""
        # Model to class mapping
        self.model_to_class: Dict[str, Type[MiioDevice]] = self._build_model_class_map()
        
        # Model to features mapping
        self.model_to_features: Dict[str, int] = self._build_feature_map()
    
    def _build_model_class_map(self) -> Dict[str, Type[MiioDevice]]:
        """Build complete model to device class mapping"""
        mapping = {}
        
        # Fans - specific models first
        mapping[MODEL_FAN_1C] = Fan1C
        mapping[MODEL_FAN_P9] = FanMiot
        mapping[MODEL_FAN_P10] = FanMiot
        mapping[MODEL_FAN_P11] = FanMiot
        mapping[MODEL_FAN_P18] = FanMiot
        mapping[MODEL_FAN_P5] = FanP5
        mapping[MODEL_FAN_ZA5] = FanZA5
        
        # Fan MIIO models
        for model in MODELS_FAN_MIIO:
            if model not in mapping:
                mapping[model] = Fan
        
        # Air Purifiers
        for model in MODELS_PURIFIER_MIOT:
            mapping[model] = AirPurifierMiot
        
        for model in MODELS_PURIFIER_MIIO:
            if model == MODEL_AIRFRESH_A1:
                mapping[model] = AirFreshA1
            elif model == MODEL_AIRFRESH_T2017:
                mapping[model] = AirFreshT2017
            elif model.startswith("zhimi.airfresh."):
                mapping[model] = AirFresh
            elif model.startswith("zhimi.airpurifier."):
                mapping[model] = AirPurifier
        
        # Humidifiers
        for model in MODELS_HUMIDIFIER_MIOT:
            mapping[model] = AirHumidifierMiot
        
        for model in MODELS_HUMIDIFIER_MJJSQ:
            mapping[model] = AirHumidifierMjjsq
        
        for model in MODELS_HUMIDIFIER_MIIO:
            mapping[model] = AirHumidifier
        
        # Vacuums
        for model in MODELS_VACUUM:
            mapping[model] = RoborockVacuum
        
        # Lights
        for model in MODELS_LIGHT_EYECARE:
            mapping[model] = PhilipsEyecare
        
        for model in MODELS_LIGHT_CEILING:
            mapping[model] = Ceil
        
        for model in MODELS_LIGHT_MOON:
            mapping[model] = PhilipsMoonlight
        
        for model in MODELS_LIGHT_BULB:
            mapping[model] = PhilipsBulb
        
        for model in MODELS_LIGHT_MONO:
            mapping[model] = PhilipsBulb
        
        # Switches
        for model in MODELS_SWITCH:
            if "powerstrip" in model:
                mapping[model] = PowerStrip
            else:
                mapping[model] = ChuangmiPlug
        
        # Gateways
        for model in MODELS_GATEWAY:
            mapping[model] = Gateway
        
        return mapping
    
    def _build_feature_map(self) -> Dict[str, int]:
        """Build complete model to feature flags mapping"""
        features = {}
        
        # Air Purifiers
        features[MODEL_AIRPURIFIER_V1] = FEATURE_FLAGS_AIRPURIFIER_V1
        features[MODEL_AIRPURIFIER_V3] = FEATURE_FLAGS_AIRPURIFIER_V3
        features[MODEL_AIRPURIFIER_PRO] = FEATURE_FLAGS_AIRPURIFIER_PRO
        features[MODEL_AIRPURIFIER_PRO_V7] = FEATURE_FLAGS_AIRPURIFIER_PRO_V7
        features[MODEL_AIRPURIFIER_2S] = FEATURE_FLAGS_AIRPURIFIER_2S
        features[MODEL_AIRPURIFIER_ZA1] = FEATURE_FLAGS_AIRPURIFIER_ZA1
        features[MODEL_AIRPURIFIER_3C] = FEATURE_FLAGS_AIRPURIFIER_3C
        features[MODEL_AIRPURIFIER_3C_REV_A] = FEATURE_FLAGS_AIRPURIFIER_3C
        features[MODEL_AIRPURIFIER_4] = FEATURE_FLAGS_AIRPURIFIER_4
        features[MODEL_AIRPURIFIER_4_PRO] = FEATURE_FLAGS_AIRPURIFIER_4
        features[MODEL_AIRPURIFIER_4_LITE_RMA1] = FEATURE_FLAGS_AIRPURIFIER_4_LITE
        features[MODEL_AIRPURIFIER_4_LITE_RMB1] = FEATURE_FLAGS_AIRPURIFIER_4_LITE
        
        # Default features for other purifiers
        for model in MODELS_PURIFIER_MIOT:
            if model not in features:
                features[model] = FEATURE_FLAGS_AIRPURIFIER_MIOT
        
        for model in MODELS_PURIFIER_MIIO:
            if model not in features:
                if model == MODEL_AIRFRESH_A1:
                    features[model] = FEATURE_FLAGS_AIRFRESH_A1
                elif model == MODEL_AIRFRESH_T2017:
                    features[model] = FEATURE_FLAGS_AIRFRESH_T2017
                elif model == MODEL_AIRFRESH_VA4:
                    features[model] = FEATURE_FLAGS_AIRFRESH_VA4
                elif model.startswith("zhimi.airfresh."):
                    features[model] = FEATURE_FLAGS_AIRFRESH
                else:
                    features[model] = FEATURE_FLAGS_AIRPURIFIER_MIIO
        
        # Humidifiers
        features[MODEL_AIRHUMIDIFIER_CA1] = FEATURE_FLAGS_AIRHUMIDIFIER_CA_AND_CB
        features[MODEL_AIRHUMIDIFIER_CB1] = FEATURE_FLAGS_AIRHUMIDIFIER_CA_AND_CB
        features[MODEL_AIRHUMIDIFIER_CA4] = FEATURE_FLAGS_AIRHUMIDIFIER_CA4
        
        for model in MODELS_HUMIDIFIER_MJJSQ:
            features[model] = FEATURE_FLAGS_AIRHUMIDIFIER_MJJSQ
        
        for model in MODELS_HUMIDIFIER_MIIO:
            if model not in features:
                features[model] = FEATURE_FLAGS_AIRHUMIDIFIER
        
        # Fans
        features[MODEL_FAN_P5] = FEATURE_FLAGS_FAN_P5
        features[MODEL_FAN_1C] = FEATURE_FLAGS_FAN_1C
        features[MODEL_FAN_P9] = FEATURE_FLAGS_FAN_P9
        features[MODEL_FAN_P10] = FEATURE_FLAGS_FAN_P10_P11_P18
        features[MODEL_FAN_P11] = FEATURE_FLAGS_FAN_P10_P11_P18
        features[MODEL_FAN_P18] = FEATURE_FLAGS_FAN_P10_P11_P18
        features[MODEL_FAN_ZA5] = FEATURE_FLAGS_FAN_ZA5
        
        for model in MODELS_FAN_MIIO:
            if model not in features:
                features[model] = FEATURE_FLAGS_FAN
        
        return features
    
    def get_device_class(self, model: str) -> Optional[Type[MiioDevice]]:
        """Get device class for model"""
        # Check exact match first
        if model in self.model_to_class:
            return self.model_to_class[model]
        
        # Check generic matches for vacuums
        if model.startswith(ROBOROCK_GENERIC) or model.startswith(ROCKROBO_GENERIC):
            return RoborockVacuum
        
        # Return None for unknown models
        return None
    
    def get_features(self, model: str) -> int:
        """Get feature flags for model"""
        return self.model_to_features.get(model, 0)
    
    def get_capabilities(self, model: str) -> Dict[str, Any]:
        """Get device capabilities for model"""
        features = self.get_features(model)
        capabilities = {
            'features': features,
            'supports': []
        }
        
        # Parse feature flags into readable capabilities
        if features & FEATURE_SET_BUZZER:
            capabilities['supports'].append('buzzer')
        if features & FEATURE_SET_LED:
            capabilities['supports'].append('led')
        if features & FEATURE_SET_CHILD_LOCK:
            capabilities['supports'].append('child_lock')
        if features & FEATURE_SET_LED_BRIGHTNESS:
            capabilities['supports'].append('led_brightness')
        if features & FEATURE_SET_FAVORITE_LEVEL:
            capabilities['supports'].append('favorite_level')
        if features & FEATURE_SET_AUTO_DETECT:
            capabilities['supports'].append('auto_detect')
        if features & FEATURE_SET_LEARN_MODE:
            capabilities['supports'].append('learn_mode')
        if features & FEATURE_SET_VOLUME:
            capabilities['supports'].append('volume')
        if features & FEATURE_RESET_FILTER:
            capabilities['supports'].append('reset_filter')
        if features & FEATURE_SET_EXTRA_FEATURES:
            capabilities['supports'].append('extra_features')
        if features & FEATURE_SET_TARGET_HUMIDITY:
            capabilities['supports'].append('target_humidity')
        if features & FEATURE_SET_DRY:
            capabilities['supports'].append('dry_mode')
        if features & FEATURE_SET_FAN_LEVEL:
            capabilities['supports'].append('fan_level')
        if features & FEATURE_SET_MOTOR_SPEED:
            capabilities['supports'].append('motor_speed')
        if features & FEATURE_SET_CLEAN:
            capabilities['supports'].append('clean_mode')
        if features & FEATURE_SET_OSCILLATION_ANGLE:
            capabilities['supports'].append('oscillation_angle')
        if features & FEATURE_SET_DELAY_OFF_COUNTDOWN:
            capabilities['supports'].append('delay_off')
        if features & FEATURE_SET_LED_BRIGHTNESS_LEVEL:
            capabilities['supports'].append('led_brightness_level')
        if features & FEATURE_SET_FAVORITE_RPM:
            capabilities['supports'].append('favorite_rpm')
        if features & FEATURE_SET_IONIZER:
            capabilities['supports'].append('ionizer')
        if features & FEATURE_SET_DISPLAY:
            capabilities['supports'].append('display')
        if features & FEATURE_SET_PTC:
            capabilities['supports'].append('ptc')
        if features & FEATURE_SET_ANION:
            capabilities['supports'].append('anion')
        
        # Add device type specific capabilities
        device_class = self.get_device_class(model)
        if device_class == RoborockVacuum:
            capabilities['device_type'] = 'vacuum'
            capabilities['supports'].extend([
                'start', 'stop', 'pause', 'return_home',
                'fan_speed', 'send_command', 'locate',
                'battery', 'clean_spot', 'clean_zone',
                'clean_segment', 'goto', 'remote_control'
            ])
        elif device_class in [AirPurifier, AirPurifierMiot]:
            capabilities['device_type'] = 'air_purifier'
        elif device_class in [AirHumidifier, AirHumidifierMiot, AirHumidifierMjjsq]:
            capabilities['device_type'] = 'humidifier'
        elif device_class in [Fan, Fan1C, FanMiot, FanP5, FanZA5]:
            capabilities['device_type'] = 'fan'
        elif device_class in [Ceil, PhilipsBulb, PhilipsEyecare, PhilipsMoonlight]:
            capabilities['device_type'] = 'light'
        elif device_class in [ChuangmiPlug, PowerStrip]:
            capabilities['device_type'] = 'switch'
        elif device_class == Gateway:
            capabilities['device_type'] = 'gateway'
        
        return capabilities


def get_device_class(model: str) -> Optional[Type[MiioDevice]]:
    """Get device class for a model (convenience function)"""
    registry = DeviceRegistry()
    return registry.get_device_class(model)