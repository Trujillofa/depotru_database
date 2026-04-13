#!/bin/bash
# Quick status check for Business Data Analyzer production deployment

echo "=========================================="
echo "📊 Business Data Analyzer - Status Check"
echo "=========================================="
echo ""

# Check service status
echo "🔍 Service Status:"
echo "-------------------"
if sudo systemctl is-active --quiet business-analyzer; then
    echo "✅ Service: RUNNING"
    sudo systemctl status business-analyzer --no-pager | grep -E "(Active:|Memory:|CPU:|Main PID:)"
else
    echo "❌ Service: NOT RUNNING"
fi
echo ""

# Check firewall status
echo "🔥 Firewall Status:"
echo "-------------------"
if sudo ufw status | grep -q "Status: active"; then
    echo "✅ Firewall: ACTIVE"
    echo ""
    echo "Open Ports:"
    sudo ufw status | grep -E "(22/tcp|80/tcp|443/tcp|8084/tcp)" | grep -v "(v6)"
else
    echo "❌ Firewall: INACTIVE"
fi
echo ""

# Check network connectivity
echo "🌐 Network Status:"
echo "-------------------"
if ss -tlnp | grep -q ":8084"; then
    echo "✅ Port 8084: LISTENING"
    ss -tlnp | grep "8084" | awk '{print "  Address: "$4"  Process: "$7}'
else
    echo "❌ Port 8084: NOT LISTENING"
fi
echo ""

# Check web response
echo "🌍 Web Interface:"
echo "------------------"
if curl -s http://localhost:8084 > /dev/null; then
    echo "✅ Web Server: RESPONDING"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8084)
    echo "  HTTP Status: $HTTP_CODE"
else
    echo "❌ Web Server: NOT RESPONDING"
fi
echo ""

# Check logs
echo "📝 Recent Logs:"
echo "---------------"
sudo journalctl -u business-analyzer --no-pager -n 3 2>/dev/null | tail -3 || echo "  No recent logs"
echo ""

echo "=========================================="
echo "🔗 Access URLs:"
echo "=========================================="
IP_ADDRESS=$(hostname -I | awk '{print $1}')
echo "  Local:   http://localhost:8084"
echo "  Network: http://$IP_ADDRESS:8084"
echo ""

echo "=========================================="
echo "🛠️  Management Commands:"
echo "=========================================="
echo ""
echo "Service Management:"
echo "  sudo systemctl status business-analyzer    # Check status"
echo "  sudo systemctl start business-analyzer     # Start service"
echo "  sudo systemctl stop business-analyzer      # Stop service"
echo "  sudo systemctl restart business-analyzer   # Restart service"
echo "  sudo systemctl disable business-analyzer   # Disable auto-start"
echo ""
echo "View Logs:"
echo "  sudo journalctl -u business-analyzer -f    # Follow logs"
echo "  sudo journalctl -u business-analyzer -n 50 # Last 50 lines"
echo ""
echo "Firewall Management:"
echo "  sudo ufw status                            # Check firewall"
echo "  sudo ufw disable                           # Disable firewall"
echo "  sudo ufw allow <port>                      # Open port"
echo "  sudo ufw deny <port>                       # Close port"
echo ""
