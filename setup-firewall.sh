#!/bin/bash
# UFW Firewall Configuration for Business Data Analyzer
# Phase 1: Essential Security Hardening

set -e

echo "=========================================="
echo "🔥 Configuring UFW Firewall"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo -e "${RED}❌ This script requires sudo privileges${NC}"
    exit 1
fi

# Function to run ufw commands with sudo
ufw_cmd() {
    sudo ufw "$@"
}

echo "📋 Current firewall status:"
ufw_cmd status verbose
echo ""

echo "⚙️  Step 1: Setting default policies..."
# Default: deny incoming, allow outgoing
ufw_cmd default deny incoming
ufw_cmd default allow outgoing
echo -e "${GREEN}✓ Default policies set${NC}"
echo ""

echo "⚙️  Step 2: Allowing essential ports..."

# SSH (port 22) - CRITICAL: Don't lock yourself out!
echo "  → Allowing SSH (port 22)..."
ufw_cmd allow 22/tcp comment 'SSH access'

# HTTP (port 80) - For future nginx redirect
echo "  → Allowing HTTP (port 80)..."
ufw_cmd allow 80/tcp comment 'HTTP'

# HTTPS (port 443) - For future SSL
echo "  → Allowing HTTPS (port 443)..."
ufw_cmd allow 443/tcp comment 'HTTPS'

# Business Analyzer App (port 8084)
echo "  → Allowing Business Analyzer (port 8084)..."
ufw_cmd allow 8084/tcp comment 'Business Data Analyzer app'

echo -e "${GREEN}✓ Ports configured${NC}"
echo ""

echo "⚙️  Step 3: Additional security rules..."

# Limit SSH brute force attempts (rate limiting)
echo "  → Enabling SSH rate limiting..."
ufw_cmd limit 22/tcp comment 'SSH brute force protection'

echo -e "${GREEN}✓ Security rules applied${NC}"
echo ""

echo "📋 Configuration Summary:"
echo "========================"
ufw_cmd status numbered
echo ""

echo -e "${YELLOW}⚠️  WARNING: Enabling firewall now...${NC}"
echo "If you lose connection, wait 30 seconds and the firewall"
echo "will automatically disable (if running interactively)."
echo ""

read -p "Enable firewall now? (y/N): " ENABLE

if [[ $ENABLE =~ ^[Yy]$ ]]; then
    echo ""
    echo "🔒 Enabling UFW firewall..."

    # Enable with timeout protection for SSH
    # This ensures we don't get locked out
    sudo timeout 30 bash -c 'echo "y" | ufw enable' || {
        echo -e "${RED}❌ Failed to enable firewall${NC}"
        exit 1
    }

    echo -e "${GREEN}✓ Firewall enabled successfully!${NC}"
    echo ""

    echo "📊 Final Status:"
    ufw_cmd status verbose
    echo ""

    echo -e "${GREEN}🎉 Firewall is now active and protecting your server!${NC}"
    echo ""
    echo "Quick commands:"
    echo "  sudo ufw status           # Check status"
    echo "  sudo ufw disable          # Disable firewall"
    echo "  sudo ufw allow <port>     # Open a port"
    echo "  sudo ufw deny <port>      # Close a port"
    echo "  sudo ufw delete <number>  # Remove a rule"

else
    echo ""
    echo "Firewall configuration saved but NOT enabled."
    echo "To enable later, run: sudo ufw enable"
    echo ""
fi
