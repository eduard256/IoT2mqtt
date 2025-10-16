# Changelog

All notable changes to IoT2MQTT will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Development happens in `develop` branch

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

[Unreleased]: https://github.com/eduard256/IoT2mqtt/compare/v0.1.0...develop
[0.1.0]: https://github.com/eduard256/IoT2mqtt/releases/tag/v0.1.0
