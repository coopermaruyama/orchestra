# Tester Extension Implementation Notes

## Issue Fixed
The tester extension was not being recognized when called via `orchestra tester <command>`. The bootstrap script was correctly set up, but the main orchestra.py file was missing the command handler.

## Solution
Added a `tester` command handler in orchestra.py (similar to existing `task` and `timemachine` handlers) that:
1. Shows help when no subcommand is provided
2. Finds the tester_monitor.py script (local or global)
3. Executes it with the subcommand and arguments

## Key Code Addition
```python
elif command == "tester":
    # Direct tester command execution
    if len(sys.argv) < 3:
        # Show help...
    
    subcommand = sys.argv[2]
    
    # Find the tester_monitor.py script
    local_script = Path(".claude") / "orchestra" / "tester" / "tester_monitor.py"
    global_script = Path.home() / ".claude" / "orchestra" / "tester" / "tester_monitor.py"
    
    # Execute the tester monitor script with the subcommand
    subprocess.run([sys.executable, str(script_path), subcommand] + sys.argv[3:])
```

## Bootstrap Flow
The bootstrap.sh script already supported tester correctly:
1. For hooks: Runs the Python monitor script directly
2. For regular commands: Executes `orchestra <args>` 

So `bootstrap.sh tester calibrate` → `orchestra tester calibrate` → `tester_monitor.py calibrate`

## Testing Commands
All three tester commands now work:
- `orchestra tester calibrate` - Interactive test setup
- `orchestra tester status` - Show calibration status  
- `orchestra tester test` - Run tests (requires calibration)

## Important Pattern
When adding new extensions to Orchestra:
1. Add extension info to the `extensions` dict in Orchestra class
2. Add command handler in main() function
3. Update help output to include the new commands
4. Bootstrap.sh automatically handles routing if following the standard pattern