#!/bin/bash
#
# Setup script for scheduling the AI Trends Reporter
# Supports both cron and macOS launchd
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH="${PYTHON_PATH:-$(which python3)}"
MAIN_SCRIPT="$SCRIPT_DIR/src/main.py"
LOG_DIR="$SCRIPT_DIR/logs"
PLIST_NAME="com.aitrends.reporter"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "AI Trends Reporter - Scheduler Setup"
echo "========================================"
echo ""

# Create logs directory
mkdir -p "$LOG_DIR"

# Check if Python exists
if [ ! -f "$PYTHON_PATH" ]; then
    echo -e "${RED}Error: Python not found at $PYTHON_PATH${NC}"
    echo "Please set PYTHON_PATH environment variable to your Python 3 executable"
    exit 1
fi

echo "Python path: $PYTHON_PATH"
echo "Main script: $MAIN_SCRIPT"
echo "Log directory: $LOG_DIR"
echo ""

# Function to setup using launchd (macOS preferred)
setup_launchd() {
    echo -e "${YELLOW}Setting up macOS launchd...${NC}"
    
    # Stop existing job if running
    if launchctl list | grep -q "$PLIST_NAME"; then
        echo "Stopping existing job..."
        launchctl unload "$PLIST_PATH" 2>/dev/null || true
    fi
    
    # Create plist file
    cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_PATH}</string>
        <string>${MAIN_SCRIPT}</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>0</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/output.log</string>
    
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/error.log</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF
    
    echo "Created plist at: $PLIST_PATH"
    
    # Load the job
    launchctl load "$PLIST_PATH"
    
    echo -e "${GREEN}launchd job installed successfully!${NC}"
    echo ""
    echo "The report will run daily at midnight (12:00 AM)."
    echo ""
    echo "Useful commands:"
    echo "  - Run now:    launchctl start $PLIST_NAME"
    echo "  - Stop:       launchctl unload $PLIST_PATH"
    echo "  - View logs:  tail -f $LOG_DIR/output.log"
}

# Function to setup using cron
setup_cron() {
    echo -e "${YELLOW}Setting up cron job...${NC}"
    
    CRON_CMD="0 0 * * * cd $SCRIPT_DIR && $PYTHON_PATH $MAIN_SCRIPT >> $LOG_DIR/output.log 2>> $LOG_DIR/error.log"
    
    # Check if job already exists
    if crontab -l 2>/dev/null | grep -q "$MAIN_SCRIPT"; then
        echo "Removing existing cron job..."
        crontab -l 2>/dev/null | grep -v "$MAIN_SCRIPT" | crontab -
    fi
    
    # Add new cron job
    (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
    
    echo -e "${GREEN}Cron job installed successfully!${NC}"
    echo ""
    echo "The report will run daily at midnight (12:00 AM)."
    echo ""
    echo "Useful commands:"
    echo "  - View cron:  crontab -l"
    echo "  - Remove:     crontab -l | grep -v '$MAIN_SCRIPT' | crontab -"
    echo "  - View logs:  tail -f $LOG_DIR/output.log"
}

# Function to remove all scheduled jobs
remove_jobs() {
    echo -e "${YELLOW}Removing scheduled jobs...${NC}"
    
    # Remove launchd
    if [ -f "$PLIST_PATH" ]; then
        launchctl unload "$PLIST_PATH" 2>/dev/null || true
        rm -f "$PLIST_PATH"
        echo "Removed launchd job"
    fi
    
    # Remove cron
    if crontab -l 2>/dev/null | grep -q "$MAIN_SCRIPT"; then
        crontab -l 2>/dev/null | grep -v "$MAIN_SCRIPT" | crontab -
        echo "Removed cron job"
    fi
    
    echo -e "${GREEN}All scheduled jobs removed.${NC}"
}

# Function to run test
run_test() {
    echo -e "${YELLOW}Running test...${NC}"
    cd "$SCRIPT_DIR"
    "$PYTHON_PATH" "$MAIN_SCRIPT" --dry-run
}

# Parse arguments
case "${1:-}" in
    --launchd)
        setup_launchd
        ;;
    --cron)
        setup_cron
        ;;
    --remove)
        remove_jobs
        ;;
    --test)
        run_test
        ;;
    *)
        echo "Usage: $0 [--launchd|--cron|--remove|--test]"
        echo ""
        echo "Options:"
        echo "  --launchd   Install using macOS launchd (recommended for macOS)"
        echo "  --cron      Install using cron"
        echo "  --remove    Remove all scheduled jobs"
        echo "  --test      Run a dry-run test"
        echo ""
        
        # Auto-detect best option
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo -e "${YELLOW}Detected macOS. Recommended: use --launchd${NC}"
            read -p "Install with launchd? [Y/n] " choice
            case "$choice" in
                n|N)
                    setup_cron
                    ;;
                *)
                    setup_launchd
                    ;;
            esac
        else
            echo -e "${YELLOW}Detected non-macOS. Using cron...${NC}"
            setup_cron
        fi
        ;;
esac

echo ""
echo "========================================"
echo "Setup complete!"
echo "========================================"
