#!/usr/bin/env bash

# IoT2MQTT Proxmox LXC Installer
# This script creates an Ubuntu LXC container and installs IoT2MQTT inside it
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/eduard256/IoT2mqtt/main/scripts/install_proxmox.sh)

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Container configuration (fixed)
DISK_SIZE="8"
RAM_SIZE="2048"
CORES="2"
OS_TEMPLATE="ubuntu-22.04-standard"
BRIDGE="vmbr0"
GATEWAY=""

# Functions
error() {
    echo -e "${RED}✗ Error: $*${NC}" >&2
    exit 1
}

success() {
    echo -e "${GREEN}✓ $*${NC}"
}

info() {
    echo -e "${CYAN}ℹ $*${NC}"
}

warning() {
    echo -e "${YELLOW}⚠ $*${NC}"
}

header() {
    clear
    cat <<"EOF"
  ██╗ ██████╗ ████████╗██████╗ ███╗   ███╗ ██████╗ ████████╗████████╗
  ██║██╔═══██╗╚══██╔══╝╚════██╗████╗ ████║██╔═══██╗╚══██╔══╝╚══██╔══╗
  ██║██║   ██║   ██║    █████╔╝██╔████╔██║██║   ██║   ██║      ██║
  ██║██║   ██║   ██║   ██╔═══╝ ██║╚██╔╝██║██║▄▄ ██║   ██║      ██║
  ██║╚██████╔╝   ██║   ███████╗██║ ╚═╝ ██║╚██████╔╝   ██║      ██║
  ╚═╝ ╚═════╝    ╚═╝   ╚══════╝╚═╝     ╚═╝ ╚══▀▀═╝    ╚═╝      ╚═╝

EOF
    echo -e "  ${BLUE}Proxmox LXC Installer${NC}"
    echo
}

check_proxmox() {
    if ! command -v pct &> /dev/null; then
        error "This script must be run on a Proxmox host"
    fi

    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root"
    fi
}

get_gateway() {
    local ip_cidr="$1"
    local ip="${ip_cidr%/*}"

    # Extract network part and set gateway as .1
    IFS='.' read -r i1 i2 i3 i4 <<< "$ip"
    echo "${i1}.${i2}.${i3}.1"
}

download_template() {
    local template="$1"

    info "Checking for Ubuntu 22.04 template..."

    # Check if template exists
    if pveam list local | grep -q "$template"; then
        success "Template already downloaded"
        return 0
    fi

    info "Downloading Ubuntu 22.04 template..."
    pveam download local "$template" || error "Failed to download template"
    success "Template downloaded"
}

create_container() {
    local ctid="$1"
    local ip="$2"
    local template_path="local:vztmpl/${OS_TEMPLATE}_amd64.tar.zst"

    info "Creating LXC container $ctid..."

    # Detect gateway from IP
    GATEWAY=$(get_gateway "$ip")

    pct create "$ctid" "$template_path" \
        --hostname "iot2mqtt" \
        --cores "$CORES" \
        --memory "$RAM_SIZE" \
        --swap 512 \
        --rootfs local-lvm:${DISK_SIZE} \
        --net0 name=eth0,bridge=${BRIDGE},ip=${ip},gw=${GATEWAY} \
        --features nesting=1 \
        --unprivileged 1 \
        --onboot 1 \
        --start 1 \
        || error "Failed to create container"

    success "Container $ctid created"
}

wait_for_container() {
    local ctid="$1"
    local max_wait=60
    local count=0

    info "Waiting for container to start..."

    while [ $count -lt $max_wait ]; do
        if pct status "$ctid" | grep -q "running"; then
            # Wait additional time for network
            sleep 5
            success "Container is running"
            return 0
        fi
        sleep 2
        count=$((count + 2))
    done

    error "Container failed to start"
}

install_iot2mqtt() {
    local ctid="$1"

    info "Installing IoT2MQTT inside container..."
    echo

    # Run our install script inside the container
    pct exec "$ctid" -- bash -c "curl -fsSL https://raw.githubusercontent.com/eduard256/IoT2mqtt/main/install.sh | bash" \
        || error "Failed to install IoT2MQTT"

    echo
    success "IoT2MQTT installed successfully"
}

get_container_ip() {
    local ctid="$1"
    pct exec "$ctid" -- hostname -I 2>/dev/null | awk '{print $1}' || echo "unknown"
}

# Main script
main() {
    header
    check_proxmox

    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo

    # Get container ID
    while true; do
        read -p "Enter container ID (e.g., 100): " CTID

        if [[ ! "$CTID" =~ ^[0-9]+$ ]]; then
            warning "Container ID must be a number"
            continue
        fi

        if pct status "$CTID" &>/dev/null; then
            warning "Container $CTID already exists"
            read -p "Do you want to continue anyway? (yes/no): " confirm
            if [[ "$confirm" != "yes" ]]; then
                continue
            fi
        fi

        break
    done

    # Get IP address
    while true; do
        read -p "Enter IP address with CIDR (e.g., 192.168.1.50/24): " IP_ADDR

        if [[ ! "$IP_ADDR" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/[0-9]{1,2}$ ]]; then
            warning "Invalid IP format. Use format: 192.168.1.50/24"
            continue
        fi

        break
    done

    echo
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo
    info "Configuration:"
    echo "  Container ID: $CTID"
    echo "  IP Address:   $IP_ADDR"
    echo "  Gateway:      $(get_gateway "$IP_ADDR")"
    echo "  Disk:         ${DISK_SIZE}GB"
    echo "  RAM:          ${RAM_SIZE}MB"
    echo "  CPU Cores:    $CORES"
    echo "  OS:           Ubuntu 22.04"
    echo

    read -p "Proceed with installation? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        info "Installation cancelled"
        exit 0
    fi

    echo
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo

    # Download template
    download_template "${OS_TEMPLATE}_amd64.tar.zst"

    # Create container
    create_container "$CTID" "$IP_ADDR"

    # Wait for container to be ready
    wait_for_container "$CTID"

    # Install IoT2MQTT
    install_iot2mqtt "$CTID"

    # Get container IP (actual)
    CONTAINER_IP=$(get_container_ip "$CTID")

    # Final message
    echo
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo
    echo -e "${GREEN}${BOLD}✓ Installation Complete!${NC}"
    echo
    echo -e "  ${CYAN}Web Interface:${NC} http://${CONTAINER_IP}:8765"
    echo -e "  ${CYAN}Container ID:${NC}  $CTID"
    echo
    echo -e "  ${YELLOW}Useful commands:${NC}"
    echo -e "    pct enter $CTID          # Enter container"
    echo -e "    pct stop $CTID           # Stop container"
    echo -e "    pct start $CTID          # Start container"
    echo -e "    pct status $CTID         # Check status"
    echo
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo
}

# Run main
main "$@"
