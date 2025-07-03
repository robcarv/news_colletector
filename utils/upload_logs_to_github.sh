#!/bin/bash
# upload_logs_to_github.sh - Complete version with robust log handling

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level=$1
    local message=$2
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    
    case $level in
        "INFO") color=$BLUE ;;
        "SUCCESS") color=$GREEN ;;
        "WARNING") color=$YELLOW ;;
        "ERROR") color=$RED ;;
        *) color=$NC ;;
    esac
    
    echo -e "[${timestamp}] [${level}] ${color}${message}${NC}"
}

# Configuration
REPO_DIR="/home/robert/Documents/vscode_projects/news_colletector"
DATA_DIR="${REPO_DIR}/data"
LOG_DIR="${REPO_DIR}/logs"
BRANCH="main"
MAX_LOG_FILES=5

# Git configuration
export GIT_SSH_COMMAND="ssh -i /home/robert/.ssh/id_rsa -o StrictHostKeyChecking=no"
export GIT_AUTHOR_NAME="robcarv"
export GIT_AUTHOR_EMAIL="robert_carvalho@hotmail.com"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

# Clean old logs function
clean_old_logs() {
    log "INFO" "Cleaning old log files (keeping ${MAX_LOG_FILES} newest)..."
    cd "$LOG_DIR" || return
    
    # Keep only the newest log files
    ls -t output_*.log 2>/dev/null | tail -n +$(($MAX_LOG_FILES + 1)) | while read -r old_log; do
        log "INFO" "Removing old log: $old_log"
        rm -f "$old_log"
    done
    
    cd - >/dev/null || return
}

# Main upload function
upload_to_github() {
    log "INFO" "${BOLD}=== Starting GitHub upload process ===${NC}"
    
    # Verify repository directory exists
    if [ ! -d "$REPO_DIR" ]; then
        log "ERROR" "Repository directory not found: $REPO_DIR"
        return 1
    fi
    
    # Ensure logs directory exists
    mkdir -p "$LOG_DIR"
    
    cd "$REPO_DIR" || {
        log "ERROR" "Failed to enter repository directory"
        return 1
    }

    # Sync with remote
    log "INFO" "Syncing with remote repository..."
    git config pull.rebase false
    git pull origin "$BRANCH" 2>&1 | while read -r line; do log "GIT" "$line"; done
    
    # Track the logs directory if not already tracked
    if ! git ls-files --error-unmatch "$LOG_DIR" >/dev/null 2>&1; then
        log "INFO" "Adding logs directory to Git tracking"
        touch "$LOG_DIR"/.gitkeep
        git add "$LOG_DIR"/.gitkeep
    fi

    # Add all modified files
    local changes=false
    
    # Add JSON files
    if [ -d "$DATA_DIR" ]; then
        json_files=($(find "$DATA_DIR" -maxdepth 1 -name "*.json"))
        if [ ${#json_files[@]} -gt 0 ]; then
            git add "data/"*.json
            changes=true
            log "INFO" "Added ${#json_files[@]} JSON files"
        fi
    fi
    
    # Add log files (force add to override .gitignore if needed)
    if [ -d "$LOG_DIR" ]; then
        log_files=($(find "$LOG_DIR" -maxdepth 1 -name "output_*.log"))
        if [ ${#log_files[@]} -gt 0 ]; then
            git add -f "logs/"output_*.log
            changes=true
            log "INFO" "Added ${#log_files[@]} log files"
        fi
    fi
    
    if ! $changes; then
        log "WARNING" "No changes detected to commit"
        return 0
    fi
    
    # Create commit
    local commit_msg="Auto-update: $(date +'%d/%m/%Y %H:%M:%S')
    
Files updated:"
    
    git diff --name-only --cached | while read -r file; do
        commit_msg+=$'\n- '"$file"
    done
    
    log "INFO" "Creating commit..."
    if ! git commit -m "$commit_msg" 2>&1 | while read -r line; do log "GIT" "$line"; done; then
        log "ERROR" "Failed to create commit"
        return 1
    fi
    
    # Push changes
    log "INFO" "Pushing to GitHub..."
    if git push origin "$BRANCH" 2>&1 | while read -r line; do log "GIT" "$line"; done; then
        log "SUCCESS" "${GREEN}Successfully pushed data and logs to GitHub!${NC}"
        clean_old_logs
    else
        log "ERROR" "Push failed. Attempting recovery..."
        git pull --rebase origin "$BRANCH" && git push origin "$BRANCH" || {
            log "ERROR" "${RED}Recovery failed. Please resolve conflicts manually.${NC}"
            return 1
        }
    fi
    
    cd - >/dev/null || return
    log "INFO" "${BOLD}=== Upload process completed ===${NC}"
}

# Execute main function
upload_to_github

# Exit with appropriate status
if [ $? -eq 0 ]; then
    exit 0
else
    exit 1
fi