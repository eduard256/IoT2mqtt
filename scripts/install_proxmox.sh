#!/usr/bin/env bash

# IoT2MQTT Proxmox LXC Installer
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/eduard256/IoT2mqtt/main/scripts/install_proxmox.sh)

set -euo pipefail

# Colors
YW='\033[33m'
BL='\033[36m'
RD='\033[01;31m'
GN='\033[1;92m'
CL='\033[m'

function msg_info() {
    echo -e "${BL}[INFO]${CL} $1"
}

function msg_ok() {
    echo -e "${GN}[OK]${CL} $1"
}

function msg_error() {
    echo -e "${RD}[ERROR]${CL} $1"
    exit 1
}

function header_info {
clear
cat <<"EOF"
   ██╗ ██████╗ ████████╗██████╗ ███╗   ███╗ ██████╗ ████████╗████████╗
   ██║██╔═══██╗╚══██╔══╝╚════██╗████╗ ████║██╔═══██╗╚══██╔══╝╚══██╔══╝
   ██║██║   ██║   ██║    █████╔╝██╔████╔██║██║   ██║   ██║      ██║
   ██║██║   ██║   ██║   ██╔═══╝ ██║╚██╔╝██║██║▄▄ ██║   ██║      ██║
   ██║╚██████╔╝   ██║   ███████╗██║ ╚═╝ ██║╚██████╔╝   ██║      ██║
   ╚═╝ ╚═════╝    ╚═╝   ╚══════╝╚═╝     ╚═╝ ╚══▀▀═╝    ╚═╝      ╚═╝

                    Proxmox LXC Installer v3.0
EOF
}

# Check if running on Proxmox
function check_proxmox() {
    if ! command -v pct &> /dev/null; then
        msg_error "This script must be run on a Proxmox host"
    fi
    if [[ $EUID -ne 0 ]]; then
        msg_error "This script must be run as root"
    fi
}

# Get next free container/VM ID
function get_next_id() {
    local id=100
    while true; do
        if qm list 2>/dev/null | awk 'NR>1 {print $1}' | grep -q "^${id}$"; then
            id=$((id + 1))
            continue
        fi
        if pct list 2>/dev/null | awk 'NR>1 {print $1}' | grep -q "^${id}$"; then
            id=$((id + 1))
            continue
        fi
        echo "$id"
        break
    done
}

# Main installation
header_info
echo ""
check_proxmox

# Configuration
APP="IoT2MQTT"
CTID=$(get_next_id)
HOSTNAME="iot2mqtt"
DISK_SIZE="8"
RAM="2048"
CORES="2"
OS_TEMPLATE="ubuntu-22.04-standard"
BRIDGE="vmbr0"

msg_info "Configuration:"
echo "  Container ID: $CTID"
echo "  Hostname: $HOSTNAME"
echo "  Disk: ${DISK_SIZE}GB"
echo "  RAM: ${RAM}MB"
echo "  CPU Cores: $CORES"
echo "  Network: DHCP"
echo ""

read -p "Continue with installation? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    msg_error "Installation cancelled"
fi

# Check if template exists
msg_info "Checking for Ubuntu template..."
TEMPLATE_FILE="${OS_TEMPLATE}_amd64.tar.zst"
if ! pveam list local | grep -q "$TEMPLATE_FILE"; then
    msg_info "Downloading Ubuntu 22.04 template..."
    pveam download local "$TEMPLATE_FILE" || msg_error "Failed to download template"
fi
msg_ok "Template ready"

# Create container
msg_info "Creating LXC container $CTID..."
pct create "$CTID" "local:vztmpl/$TEMPLATE_FILE" \
    --hostname "$HOSTNAME" \
    --cores "$CORES" \
    --memory "$RAM" \
    --swap 512 \
    --rootfs local-lvm:${DISK_SIZE} \
    --net0 name=eth0,bridge=${BRIDGE},ip=dhcp \
    --features nesting=1 \
    --unprivileged 1 \
    --onboot 1 \
    --start 1 || msg_error "Failed to create container"
msg_ok "Container created"

# Wait for container to start
msg_info "Waiting for container to start..."
sleep 10

# Install IoT2MQTT
msg_info "Installing IoT2MQTT..."
pct exec "$CTID" -- bash -c "curl -fsSL https://raw.githubusercontent.com/eduard256/IoT2mqtt/main/install.sh | bash" || msg_error "Failed to install IoT2MQTT"
msg_ok "IoT2MQTT installed"

# Get container IP
CONTAINER_IP=$(pct exec "$CTID" -- hostname -I 2>/dev/null | awk '{print $1}')

# Show completion message
echo ""
msg_ok "Installation completed successfully!"
echo ""
echo "  Container ID: $CTID"
echo "  Hostname: $HOSTNAME"
echo "  IP Address: $CONTAINER_IP"
echo "  Web Interface: http://${CONTAINER_IP}:8765"
echo ""
echo "Useful commands:"
echo "  pct enter $CTID    - Enter container"
echo "  pct stop $CTID     - Stop container"
echo "  pct start $CTID    - Start container"
echo ""
