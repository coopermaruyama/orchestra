# Orchestra Quick Test Reference

Quick commands to test Orchestra extensions without reading the full guide.

## 🚀 Quick Start Testing

### 1. Enable and Test Task Monitor

```bash
# Enable
orchestra enable task

# Start a task
orchestra task start

# Check status
orchestra task status

# Complete requirement
orchestra task complete

# Test in Claude Code
/task:start
/focus
```

### 2. Enable and Test TimeMachine

```bash
# Enable
orchestra enable timemachine

# View checkpoints
orchestra timemachine list

# Test in Claude Code
/timemachine:list
```

## 🧪 Quick Functionality Tests

### Test State Files

```bash
# Check new state location
ls -la .claude/orchestra/
# Should show: task.json, timemachine.json (after use)

# View task state
cat .claude/orchestra/task.json | jq .

# View timemachine state
cat .claude/orchestra/timemachine.json | jq .
```

### Test Git Integration

```bash
# Check for WIP branches
git show-ref | grep wip

# Check task branches
git branch | grep task-monitor
```

### Test Hooks

```bash
# Check hook configuration
cat ~/.claude/settings.json | jq .hooks

# View logs (new easy way!)
orchestra logs
orchestra logs task        # Just task monitor logs
orchestra logs --tail      # Follow logs real-time

# View logs (old way)
find /var/folders -name "*.log" -path "*claude*" 2>/dev/null | xargs tail -f
```

## 🔍 Quick Debug Commands

### Find Problems

```bash
# Extension not working?
ls ~/.claude/orchestra/*/
ls ~/.claude/commands/

# Hooks not firing?
cat ~/.claude/settings.json | grep -A 20 hooks

# Commands not found?
which orchestra
orchestra list

# State not saving?
ls -la .claude/orchestra/
cat .claude/orchestra/*.json
```

### Common Fixes

```bash
# Re-enable extension
orchestra disable task && orchestra enable task

# Clear state (careful!)
rm -rf .claude/orchestra/*.json

# Fix permissions
chmod +x ~/.claude/orchestra/bootstrap.sh

# Rebuild package
uv pip install -e .
```

## 📊 Quick Performance Test

```bash
# Time checkpoint creation
time orchestra timemachine list

# Count checkpoints
cat .claude/orchestra/timemachine.json | jq '.checkpoints | length'

# Check log size
du -h /var/folders/*/T/claude-*/
```

## ✅ Health Check Script

```bash
# Create health_check.sh
cat > health_check.sh << 'EOF'
#!/bin/bash
echo "=== Orchestra Health Check ==="
echo -n "Orchestra installed: "
which orchestra && echo "✓" || echo "✗"

echo -n "Task extension: "
[ -d ~/.claude/orchestra/task ] && echo "✓" || echo "✗"

echo -n "TimeMachine extension: "
[ -d ~/.claude/orchestra/timemachine ] && echo "✓" || echo "✗"

echo -n "Bootstrap script: "
[ -x ~/.claude/orchestra/bootstrap.sh ] && echo "✓" || echo "✗"

echo -n "State directory: "
[ -d .claude/orchestra ] && echo "✓" || echo "✗"

echo -n "Git repo: "
git rev-parse --git-dir &>/dev/null && echo "✓" || echo "✗"

echo "=== Extension Commands ==="
ls ~/.claude/commands/*/*.md 2>/dev/null | wc -l | xargs echo "Commands found:"

echo "=== Recent Logs ==="
find /var/folders -name "*.log" -path "*claude*" -mmin -60 2>/dev/null | head -5
EOF

chmod +x health_check.sh
./health_check.sh
```

## 🎯 Test Scenarios

### Scenario 1: Basic Task Workflow
```bash
orchestra task start        # Create task
orchestra task status       # Check progress  
orchestra task complete     # Mark done
orchestra task status       # Verify completion
```

### Scenario 2: TimeMachine Checkpoint
```bash
echo "test" > file.txt      # Make change
git add file.txt            # Stage change
# Wait for Claude Code to create checkpoint via hooks
orchestra timemachine list  # View checkpoints
```

### Scenario 3: Multi-Extension
```bash
orchestra install task
orchestra install timemachine
ls .claude/orchestra/       # Both configs should exist
```

## 🚨 Emergency Commands

```bash
# Remove all Orchestra data (nuclear option)
rm -rf ~/.claude/orchestra/
rm -rf ~/.claude/commands/{task,timemachine,focus.md}
rm -rf .claude/orchestra/

# Full reinstall
pip uninstall orchestra -y
pip install -e .
orchestra install task
orchestra install timemachine
```