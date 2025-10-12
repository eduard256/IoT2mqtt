#!/usr/bin/env bash

# IoT2MQTT Proxmox LXC Installer
# This script creates an Ubuntu LXC container and installs IoT2MQTT inside it
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/eduard256/IoT2mqtt/main/scripts/install_proxmox.sh)

set -euo pipefail

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Container configuration defaults
DISK_SIZE="8"
RAM_SIZE="2048"
CORES="2"
OS_TEMPLATE="ubuntu-22.04-standard"
BRIDGE="vmbr0"
GATEWAY=""
HOSTNAME="iot2mqtt"
USE_DHCP=false
CTID=""
IP_ADDR=""

# Detect dialog tool
if command -v whiptail &> /dev/null; then
    DIALOG="whiptail"
elif command -v dialog &> /dev/null; then
    DIALOG="dialog"
else
    DIALOG=""
fi

# Dialog dimensions
HEIGHT=20
WIDTH=70
CHOICE_HEIGHT=10

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

draw_header() {
    clear
    echo -e "${MAGENTA}${BOLD}"
    cat <<"EOF"
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║   ██╗ ██████╗ ████████╗██████╗ ███╗   ███╗ ██████╗ ████████╗████████╗   ║
║   ██║██╔═══██╗╚══██╔══╝╚════██╗████╗ ████║██╔═══██╗╚══██╔══╝╚══██╔══╝   ║
║   ██║██║   ██║   ██║    █████╔╝██╔████╔██║██║   ██║   ██║      ██║      ║
║   ██║██║   ██║   ██║   ██╔═══╝ ██║╚██╔╝██║██║▄▄ ██║   ██║      ██║      ║
║   ██║╚██████╔╝   ██║   ███████╗██║ ╚═╝ ██║╚██████╔╝   ██║      ██║      ║
║   ╚═╝ ╚═════╝    ╚═╝   ╚══════╝╚═╝     ╚═╝ ╚══▀▀═╝    ╚═╝      ╚═╝      ║
║                                                                           ║
║                     🐳 Proxmox LXC Installer v2.0 🐳                      ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
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

get_next_free_ctid() {
    # Find first available container ID starting from 100
    local ctid=100
    while pct status "$ctid" &>/dev/null; do
        ctid=$((ctid + 1))
    done
    echo "$ctid"
}

msgbox() {
    local title="$1"
    local message="$2"

    if [ -n "$DIALOG" ]; then
        $DIALOG --title "$title" --msgbox "$message" $HEIGHT $WIDTH
    else
        echo -e "\n${CYAN}${BOLD}$title${NC}"
        echo -e "$message\n"
        read -p "Press Enter to continue..."
    fi
}

yesno() {
    local title="$1"
    local message="$2"

    if [ -n "$DIALOG" ]; then
        $DIALOG --title "$title" --yesno "$message" $HEIGHT $WIDTH
        return $?
    else
        echo -e "\n${CYAN}${BOLD}$title${NC}"
        echo -e "$message"
        read -p "Continue? (y/n): " answer
        [[ "$answer" =~ ^[Yy] ]]
        return $?
    fi
}

inputbox() {
    local title="$1"
    local message="$2"
    local default="$3"
    local result

    if [ -n "$DIALOG" ]; then
        result=$($DIALOG --title "$title" --inputbox "$message" $HEIGHT $WIDTH "$default" 3>&1 1>&2 2>&3)
        echo "$result"
    else
        if [ -n "$default" ]; then
            read -p "$message [$default]: " result
            echo "${result:-$default}"
        else
            read -p "$message: " result
            echo "$result"
        fi
    fi
}

menu() {
    local title="$1"
    local message="$2"
    shift 2
    local options=("$@")
    local result

    if [ -n "$DIALOG" ]; then
        result=$($DIALOG --title "$title" --menu "$message" $HEIGHT $WIDTH $CHOICE_HEIGHT "${options[@]}" 3>&1 1>&2 2>&3)
        echo "$result"
    else
        echo -e "\n${CYAN}${BOLD}$title${NC}"
        echo -e "$message\n"
        for ((i=0; i<${#options[@]}; i+=2)); do
            echo "  ${options[i]}) ${options[i+1]}"
        done
        read -p "Select option: " result
        echo "$result"
    fi
}

gauge() {
    local title="$1"
    local message="$2"
    local percent="$3"

    if [ -n "$DIALOG" ]; then
        echo "$percent" | $DIALOG --title "$title" --gauge "$message" 8 $WIDTH 0
    else
        echo -e "${CYAN}[$percent%] $message${NC}"
    fi
}

download_template() {
    local template="$1"

    if pveam list local | grep -q "$template"; then
        return 0
    fi

    if [ -n "$DIALOG" ]; then
        (
            echo "10"
            echo "XXX"
            echo "Updating template list..."
            echo "XXX"
            sleep 1

            echo "30"
            echo "XXX"
            echo "Downloading Ubuntu 22.04 template..."
            echo "XXX"

            pveam download local "$template" 2>&1 | while read line; do
                echo "50"
            done

            echo "100"
            echo "XXX"
            echo "Download complete!"
            echo "XXX"
            sleep 1
        ) | $DIALOG --title "Downloading Template" --gauge "Please wait..." 8 $WIDTH 0
    else
        info "Downloading Ubuntu 22.04 template..."
        pveam download local "$template" || error "Failed to download template"
        success "Template downloaded"
    fi
}

create_container() {
    local ctid="$1"
    local ip="$2"
    local template_path="local:vztmpl/${OS_TEMPLATE}_amd64.tar.zst"

    # Network configuration
    local net_config
    if [ "$USE_DHCP" = true ]; then
        net_config="name=eth0,bridge=${BRIDGE},ip=dhcp"
    else
        GATEWAY=$(get_gateway "$ip")
        net_config="name=eth0,bridge=${BRIDGE},ip=${ip},gw=${GATEWAY}"
    fi

    if [ -n "$DIALOG" ]; then
        (
            echo "20"
            echo "XXX"
            echo "Creating LXC container $ctid..."
            echo "XXX"

            pct create "$ctid" "$template_path" \
                --hostname "$HOSTNAME" \
                --cores "$CORES" \
                --memory "$RAM_SIZE" \
                --swap 512 \
                --rootfs local-lvm:${DISK_SIZE} \
                --net0 "$net_config" \
                --features nesting=1 \
                --unprivileged 1 \
                --onboot 1 \
                --start 1 \
                2>&1 | while read line; do
                    echo "50"
                done

            echo "100"
            echo "XXX"
            echo "Container created successfully!"
            echo "XXX"
            sleep 1
        ) | $DIALOG --title "Creating Container" --gauge "Please wait..." 8 $WIDTH 0
    else
        info "Creating LXC container $ctid..."
        pct create "$ctid" "$template_path" \
            --hostname "$HOSTNAME" \
            --cores "$CORES" \
            --memory "$RAM_SIZE" \
            --swap 512 \
            --rootfs local-lvm:${DISK_SIZE} \
            --net0 "$net_config" \
            --features nesting=1 \
            --unprivileged 1 \
            --onboot 1 \
            --start 1 \
            || error "Failed to create container"
        success "Container $ctid created"
    fi
}

wait_for_container() {
    local ctid="$1"
    local max_wait=60
    local count=0

    if [ -n "$DIALOG" ]; then
        (
            while [ $count -lt $max_wait ]; do
                if pct status "$ctid" | grep -q "running"; then
                    sleep 5
                    echo "100"
                    echo "XXX"
                    echo "Container is running!"
                    echo "XXX"
                    sleep 1
                    exit 0
                fi
                sleep 2
                count=$((count + 2))
                percent=$((count * 100 / max_wait))
                echo "$percent"
                echo "XXX"
                echo "Waiting for container to start... ($count/$max_wait seconds)"
                echo "XXX"
            done
            error "Container failed to start"
        ) | $DIALOG --title "Starting Container" --gauge "Please wait..." 8 $WIDTH 0
    else
        info "Waiting for container to start..."
        while [ $count -lt $max_wait ]; do
            if pct status "$ctid" | grep -q "running"; then
                sleep 5
                success "Container is running"
                return 0
            fi
            sleep 2
            count=$((count + 2))
        done
        error "Container failed to start"
    fi
}

install_iot2mqtt() {
    local ctid="$1"

    if [ -n "$DIALOG" ]; then
        (
            echo "10"
            echo "XXX"
            echo "Installing IoT2MQTT inside container..."
            echo "XXX"

            pct exec "$ctid" -- bash -c "curl -fsSL https://raw.githubusercontent.com/eduard256/IoT2mqtt/main/install.sh | bash" 2>&1 | while read line; do
                echo "50"
            done

            echo "100"
            echo "XXX"
            echo "IoT2MQTT installed successfully!"
            echo "XXX"
            sleep 1
        ) | $DIALOG --title "Installing IoT2MQTT" --gauge "Please wait..." 8 $WIDTH 0
    else
        info "Installing IoT2MQTT inside container..."
        echo
        pct exec "$ctid" -- bash -c "curl -fsSL https://raw.githubusercontent.com/eduard256/IoT2mqtt/main/install.sh | bash" \
            || error "Failed to install IoT2MQTT"
        echo
        success "IoT2MQTT installed successfully"
    fi
}

get_container_ip() {
    local ctid="$1"
    pct exec "$ctid" -- hostname -I 2>/dev/null | awk '{print $1}' || echo "unknown"
}

show_completion_screen() {
    local container_ip="$1"
    local message="
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║                    ✨ INSTALLATION COMPLETE! ✨                       ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝

📋 Container Details:
   • Container ID:    $CTID
   • Hostname:        $HOSTNAME
   • IP Address:      $container_ip
   • Web Interface:   http://${container_ip}:8765

💻 Useful Commands:
   • Enter container:  pct enter $CTID
   • Stop container:   pct stop $CTID
   • Start container:  pct start $CTID
   • Check status:     pct status $CTID

🎉 Your IoT2MQTT instance is ready to use!
   Visit the web interface to start configuring your devices.
"

    if [ -n "$DIALOG" ]; then
        msgbox "Installation Complete" "$message"
    fi

    clear
    draw_header
    echo -e "${GREEN}${BOLD}$message${NC}"
}

configure_automatic_mode() {
    USE_DHCP=true
    CTID=$(get_next_free_ctid)
    HOSTNAME="iot2mqtt"
    IP_ADDR="dhcp"
    DISK_SIZE="8"
    RAM_SIZE="2048"
    CORES="2"
    BRIDGE="vmbr0"
}

configure_advanced_mode() {
    USE_DHCP=false

    # Get automatic defaults
    local auto_ctid=$(get_next_free_ctid)
    local auto_hostname="iot2mqtt"

    # Hostname
    HOSTNAME=$(inputbox "Container Hostname" "Enter container hostname (Empty = auto: $auto_hostname):" "")
    [ -z "$HOSTNAME" ] && HOSTNAME="$auto_hostname"

    # Container ID
    while true; do
        CTID=$(inputbox "Container ID" "Enter container ID (Empty = auto: $auto_ctid):" "")
        [ -z "$CTID" ] && CTID="$auto_ctid"

        if [[ ! "$CTID" =~ ^[0-9]+$ ]]; then
            msgbox "Error" "Container ID must be a number!"
            continue
        fi

        if pct status "$CTID" &>/dev/null; then
            if ! yesno "Container Exists" "Container $CTID already exists!\n\nDo you want to continue anyway?"; then
                continue
            fi
        fi
        break
    done

    # IP Address
    while true; do
        IP_ADDR=$(inputbox "IP Address" "Enter IP address with CIDR\n(Empty = DHCP)\nExample: 192.168.1.50/24" "")

        if [ -z "$IP_ADDR" ]; then
            USE_DHCP=true
            IP_ADDR="dhcp"
            break
        fi

        if [[ ! "$IP_ADDR" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/[0-9]{1,2}$ ]]; then
            msgbox "Error" "Invalid IP format!\nUse format: 192.168.1.50/24"
            continue
        fi
        break
    done

    # Gateway (only if not DHCP)
    if [ "$USE_DHCP" = false ]; then
        local default_gw=$(get_gateway "$IP_ADDR")
        GATEWAY=$(inputbox "Gateway" "Enter gateway (Empty = auto: $default_gw):" "")
        [ -z "$GATEWAY" ] && GATEWAY="$default_gw"
    fi

    # Bridge
    BRIDGE=$(inputbox "Network Bridge" "Enter network bridge (Empty = auto: vmbr0):" "")
    [ -z "$BRIDGE" ] && BRIDGE="vmbr0"

    # Disk Size
    DISK_SIZE=$(inputbox "Disk Size" "Enter disk size in GB (Empty = auto: 8):" "")
    [ -z "$DISK_SIZE" ] && DISK_SIZE="8"

    # RAM Size
    RAM_SIZE=$(inputbox "RAM Size" "Enter RAM size in MB (Empty = auto: 2048):" "")
    [ -z "$RAM_SIZE" ] && RAM_SIZE="2048"

    # CPU Cores
    CORES=$(inputbox "CPU Cores" "Enter number of CPU cores (Empty = auto: 2):" "")
    [ -z "$CORES" ] && CORES="2"
}

show_configuration_summary() {
    local summary="
╔════════════════════════════════════════╗
║      CONFIGURATION SUMMARY             ║
╚════════════════════════════════════════╝

Container Settings:
  • Hostname:     $HOSTNAME
  • Container ID: $CTID
  • Network:      $([ "$USE_DHCP" = true ] && echo "DHCP (automatic)" || echo "$IP_ADDR")
  $([ "$USE_DHCP" = false ] && echo "• Gateway:      $GATEWAY")
  • Bridge:       $BRIDGE

Resources:
  • Disk:         ${DISK_SIZE}GB
  • RAM:          ${RAM_SIZE}MB
  • CPU Cores:    $CORES
  • OS:           Ubuntu 22.04 LTS

Ready to proceed with installation?
"

    yesno "Confirm Configuration" "$summary"
    return $?
}

# Main script
main() {
    draw_header
    check_proxmox

    sleep 1

    # Welcome message
    msgbox "Welcome to IoT2MQTT Installer" "This installer will create a Proxmox LXC container\nand install IoT2MQTT inside it.\n\nFeatures:\n  • Automatic or Custom configuration\n  • DHCP or Static IP\n  • Beautiful interactive interface\n\nPress OK to continue..."

    # Select installation mode
    mode=$(menu "Installation Mode" "Choose your installation mode:" \
        "1" "🚀 Automatic Setup (DHCP, auto ID, defaults)" \
        "2" "⚙️  Advanced Setup (full customization)")

    case $mode in
        1)
            configure_automatic_mode
            ;;
        2)
            configure_advanced_mode
            ;;
        *)
            error "Invalid selection"
            ;;
    esac

    # Show configuration summary and confirm
    if ! show_configuration_summary; then
        msgbox "Installation Cancelled" "Installation has been cancelled by user."
        exit 0
    fi

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

    # Show completion screen
    show_completion_screen "$CONTAINER_IP"
}

# Run main
main "$@"
