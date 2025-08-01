#!/usr/bin/env python3
"""
Tests for Orchestra extension management
"""

import unittest
import sys
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add the src directory to path to import orchestra
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from orchestra import Orchestra
    RICH_AVAILABLE = True
except ImportError as e:
    print(f"Import error in test: {e}")
    RICH_AVAILABLE = False


@unittest.skipUnless(RICH_AVAILABLE, "Rich library not available")
class TestOrchestra(unittest.TestCase):
    """Test Orchestra extension manager"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Create test directory structure
        self.extensions_dir = Path(self.temp_dir) / "extensions" / "task-monitor"
        self.extensions_dir.mkdir(parents=True)
        
        # Create mock task_monitor.py
        (self.extensions_dir / "task_monitor.py").write_text("# Mock task monitor")
        
        # Create mock agents directory
        agents_dir = self.extensions_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "test-agent.md").write_text("# Test agent")
        
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)
    
    def test_bootstrap_installation(self):
        """Test that bootstrap script is installed with task-monitor extension"""
        orchestra = Orchestra()
        orchestra.console = MagicMock()
        
        # Install task-monitor extension locally
        orchestra.install("task-monitor", "local")
        
        # Check that bootstrap script was created
        bootstrap_path = Path(".claude") / "orchestra" / "bootstrap.py"
        self.assertTrue(bootstrap_path.exists(), "Bootstrap script should be created")
        
        # Check that commands directory was created
        commands_dir = Path(".claude") / "commands"
        self.assertTrue(commands_dir.exists(), "Commands directory should be created")
        
        # Check that task commands were created
        task_dir = commands_dir / "task"
        self.assertTrue(task_dir.exists(), "Task commands directory should be created")
        self.assertTrue((task_dir / "start.md").exists(), "Start command should exist")
        
        # Check that console showed installation message
        console_calls = [str(call) for call in orchestra.console.print.call_args_list]
        install_message = any("installed task-monitor" in call.lower() for call in console_calls)
        self.assertTrue(install_message, "Should display installation message")
    
    def test_global_bootstrap_installation(self):
        """Test that bootstrap is installed globally when requested"""
        orchestra = Orchestra()
        orchestra.console = MagicMock()
        
        # Mock the home directory to avoid modifying real system
        with patch.object(orchestra, 'home', Path(self.temp_dir)):
            # Install task-monitor extension globally
            orchestra.install("task-monitor", "global")
            
            # Check that global bootstrap was created
            global_bootstrap = Path(self.temp_dir) / ".claude" / "orchestra" / "bootstrap.py"
            self.assertTrue(global_bootstrap.exists(), "Global bootstrap should be created")
            
            # Verify the console showed global installation
            console_calls = [str(call) for call in orchestra.console.print.call_args_list]
            global_message = any("global" in call.lower() for call in console_calls)
            self.assertTrue(global_message, "Should indicate global installation")


class TestSubagentTemplates(unittest.TestCase):
    """Test that subagent templates are properly formatted"""
    
    def setUp(self):
        """Set up paths to actual subagent templates"""
        self.agents_dir = Path(__file__).parent.parent / "src" / "extensions" / "task-monitor" / "agents"
    
    def test_subagent_files_exist(self):
        """Test that all expected subagent template files exist"""
        expected_agents = [
            "scope-creep-detector.md",
            "over-engineering-detector.md", 
            "off-topic-detector.md"
        ]
        
        for agent_file in expected_agents:
            agent_path = self.agents_dir / agent_file
            self.assertTrue(agent_path.exists(), f"Missing subagent template: {agent_file}")
    
    def test_subagent_yaml_frontmatter(self):
        """Test that subagent files have proper YAML frontmatter"""
        for agent_file in self.agents_dir.glob("*.md"):
            with open(agent_file, 'r') as f:
                content = f.read()
            
            # Should start with YAML frontmatter
            self.assertTrue(content.startswith("---"), f"{agent_file.name} should start with YAML frontmatter")
            
            # Should have required fields
            self.assertIn("name:", content, f"{agent_file.name} should have 'name' field")
            self.assertIn("description:", content, f"{agent_file.name} should have 'description' field")
            self.assertIn("tools:", content, f"{agent_file.name} should have 'tools' field")
            
            # Should have closing frontmatter
            lines = content.split('\n')
            frontmatter_closes = [i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"]
            self.assertTrue(len(frontmatter_closes) > 0, f"{agent_file.name} should have closing frontmatter")
    
    def test_subagent_content_quality(self):
        """Test that subagent content is comprehensive"""
        for agent_file in self.agents_dir.glob("*.md"):
            with open(agent_file, 'r') as f:
                content = f.read()
            
            # Should have substantial content beyond frontmatter
            self.assertGreater(len(content), 500, f"{agent_file.name} should have substantial content")
            
            # Should mention JSON response format
            self.assertIn("JSON", content, f"{agent_file.name} should specify JSON response format")
            
            # Should have analysis framework or methodology
            self.assertTrue(
                any(keyword in content.lower() for keyword in ['analysis', 'framework', 'consider', 'evaluate']),
                f"{agent_file.name} should describe analysis methodology"
            )


if __name__ == '__main__':
    unittest.main()