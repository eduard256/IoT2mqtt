# Changelog

All notable changes to IoT2MQTT will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Development happens in `develop` branch

## [0.2.0] - 2025-10-22

### About This Release

This release introduces **IP camera support** as a major new feature, along with significant architecture improvements and MQTT enhancements. The project remains in **alpha/beta** status with an **unstable API**.

### ✨ Features

#### 🎥 Camera Connector (New)
- **IP Camera Support** - Full connector for IP cameras with RTSP/HTTP streams
- **go2rtc Integration** - Stream proxying and transcoding via embedded go2rtc
- **ONVIF Support** - Auto-discovery and configuration for ONVIF-compatible cameras
- **Stream Discovery** - Advanced scanner with 1200+ camera model patterns
- **Stream Validation** - HTTP Basic Auth and credential injection for secure streams
- **Multi-Stream Support** - Main, sub, and snapshot streams with intelligent detection
- **Camera Brands Database** - Extensive database of camera models and stream patterns
- **Modern UI** - Camera model picker with search and stream scanner component

#### 📡 MQTT Improvements
- **mqtt_device_picker Component** - Universal reusable device picker for any connector
- **Home Assistant MQTT Discovery** - Automatic device registration in Home Assistant

#### 🏗️ Architecture
- **Universal Port Management** - Automatic port allocation system for connectors
- **setup.json Migration** - Single source of truth (deprecated manifest.json)
- **Plugin-based Forms** - Modular, extensible FlowSetupForm architecture
- **Custom Field System** - Extensible field types with API and documentation
- **Backend instance_id Generation** - Centralized ID generation logic

#### 🔧 Developer Experience
- **Comprehensive Custom Fields Docs** - API reference, examples, and best practices
- **Rebuild Button** - Ability to rebuild connector instances from UI
- **Template Variable Resolution** - Dynamic form field configuration
- **IP-based Device Naming** - Automatic device_id generation for network devices

### 🐛 Bug Fixes

#### Camera Connector
- Fixed ONVIF username hardcoding
- Added missing imports and dependencies (urlparse, ffmpeg, stream_validator.py)
- Fixed camera model picker dropdown behavior
- Improved stream URL placeholder replacement
- Fixed Docker builds for camera connector

#### Core System
- Restored instance_id auto-generation
- Fixed template variable resolution in form configs
- Resolved React hooks violations in FormStep
- Fixed asyncio timeout issues (1s → 30s)
- Improved error handling in stream validation

#### UI/UX
- Fixed mqtt_device_picker card layout
- Removed debug console logging from production
- Added missing Table component for stream scanner
- Fixed multi-device display support
- Fixed install scripts git checkout

### ♻️ Refactoring

- **Camera Stream Scanner** - Complete rewrite for stability and performance
- **FlowSetupForm** - Modularized into plugin-based architecture (1600+ lines → modular)
- **SSE Endpoint** - Simplified async architecture
- **Form Field Types** - Support for custom field and step types

### 📝 Documentation

- Added comprehensive custom fields documentation
- Camera stream detection documentation
- Database format documentation
- MQTT device picker usage guide

### ⚡ Performance

- Reduced concurrent stream tests from 12 to 4 for stability
- Optimized camera stream discovery timeouts
- Improved camera search with intelligent scoring

### 🔒 Security

- Credential injection for camera streams
- HTTP Basic Auth for stream validation
- Environment variable usage for sensitive paths

### Known Limitations

- ⚠️ **API Instability** - Breaking changes expected in 0.x releases
- 🎥 **Camera Connector** - Beta quality, may require configuration tuning
- 📚 **Limited Connectors** - Only Yeelight and Camera connectors fully implemented
- 🔄 **Migration** - setup.json format may change in future releases

### Migration Notes

#### setup.json Migration
If you have custom connectors using `manifest.json`, you should migrate to `setup.json` format. The system still supports both, but `manifest.json` is deprecated.

#### Port Management
Connectors using custom ports should now use the universal port management system. See updated documentation for details.

### Technical Details

**New Dependencies:**
- go2rtc (embedded in camera connector)
- ffmpeg (for camera stream processing)
- ONVIF libraries (for camera discovery)

**Camera Connector Architecture:**
- go2rtc runs as supervised process alongside connector
- Stream validation via HTTP requests
- Dynamic credential injection into stream URLs
- Port allocation via backend port management service

### Credits

Made with ❤️ for the Smart Home Community

Special thanks to the camera pattern database contributors!

---

## [0.1.0] - 2025-10-16

### About This Release

This is the initial pre-release version of IoT2MQTT. The project is functional but considered **alpha/beta** quality. API is **unstable** and breaking changes are expected in future releases.

### Bug Fixes

- **Fixed device not appearing on instance step** - When manually adding a device through the Yeelight setup flow, the device was not appearing on the final instance step, causing "Friendly name is required to auto-generate instance ID" error. Now devices are properly saved when advancing through setup steps.

### Features

#### Core Architecture
- 🐳 **100% Containerized** - Docker-in-Docker architecture with zero host dependencies
- 🎨 **Web Interface** - React-based frontend with FastAPI backend
- 🌍 **Multi-language Support** - English, Russian, and Chinese localization
- 📱 **PWA Support** - Progressive Web App capabilities

#### Installation
- ✨ One-line installer for Linux systems (Debian/Ubuntu, RHEL/CentOS/Fedora, Arch, Alpine)
- 🚀 Proxmox LXC automated installer with interactive setup
- 📦 Automatic Docker and Docker Compose installation
- 🔄 Safe update mechanism with user data preservation

#### Device Management
- 📱 Declarative setup flows via `setup.json` schema
- 🔌 Dynamic connector container creation and management
- 📊 Real-time container logs with color coding
- 🔍 Device discovery workflows
- 🔐 Encrypted secrets management

#### Connectors
- 💡 **Yeelight** - Full support for smart bulbs and LED strips
  - Device discovery
  - State control (on/off, brightness, color)
  - MQTT integration

#### MQTT Integration
- ⚡ Direct MQTT connection from each connector container
- 🎯 Configurable base topic
- 📡 Real-time state publishing
- 🔧 Connection management via web UI

#### Developer Experience
- 📝 Comprehensive documentation
- 🐛 Detailed logging system
- 🔧 Docker socket integration for container orchestration
- 🛠️ Test runner infrastructure

### Known Limitations

- ⚠️ **API Instability** - API endpoints and data structures may change
- 🔌 **Limited Connectors** - Only Yeelight is fully implemented
- 📚 **Documentation** - Some areas are work in progress
- 🧪 **Testing** - More automated tests needed
- 🔄 **Breaking Changes** - Expected in future releases

### Technical Details

**Architecture:**
- Main web container orchestrates connector containers via Docker socket
- Each connector instance runs in isolated container
- Shared network for inter-container communication
- Volume mounts for persistent data

**Dependencies:**
- Docker 20.10+
- Docker Compose 2.0+
- Linux kernel with container support

**Installation Path:**
- Default: `/opt/iot2mqtt`
- Web Interface: Port 8765 (configurable)

### Security Considerations

- 🔒 JWT-based authentication
- 🔐 Bcrypt password hashing
- 🔑 Encrypted secrets storage
- 🐳 Container isolation
- ⚠️ Docker socket access required (privileged operation)

### Migration Notes

This is the first release - no migration needed.

### Credits

Made with ❤️ for the Smart Home Community

---

## Release Types

- **Major.x.x** - Breaking changes, major new features
- **x.Minor.x** - New features, backwards compatible
- **x.x.Patch** - Bug fixes, minor improvements

**Pre-1.0.0 Warning:** During 0.x.x releases, minor version bumps may include breaking changes. API stability will be guaranteed starting from version 1.0.0.

[Unreleased]: https://github.com/eduard256/IoT2mqtt/compare/v0.2.0...develop
[0.2.0]: https://github.com/eduard256/IoT2mqtt/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/eduard256/IoT2mqtt/releases/tag/v0.1.0
