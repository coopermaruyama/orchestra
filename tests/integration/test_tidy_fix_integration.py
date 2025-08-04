"""
Integration tests for TidyFixCommand

Tests the command with realistic scenarios and edge cases.
"""

import logging
from unittest.mock import Mock, patch

import pytest

from orchestra.common.claude_cli_wrapper import ClaudeResponse
from orchestra.extensions.tidy.commands.fix import TidyFixCommand


class TestTidyFixIntegration:
    """Integration tests for TidyFixCommand"""

    @pytest.fixture
    def command(self):
        """Create command instance with custom logger"""
        logger = logging.getLogger("test_tidy_fix")
        return TidyFixCommand(model="haiku", logger=logger)

    @pytest.fixture
    def messy_python_code(self):
        """Real-world example of messy Python code"""
        return """import os,sys,json
from typing import List,Dict,Optional
import requests


def fetch_data(url,headers = None,timeout= 30):
    '''Fetches data from url'''
    if headers == None:
        headers={}
    
    try:
        response= requests.get(url,headers = headers,timeout = timeout)
        if response.status_code ==200:
            return response.json()
        else:
            print(f"Error: {response.status_code}")
            return None
    except Exception as e:
        print(f"Failed: {e}")
        return None

class DataProcessor:
    def __init__(self,config: dict):
        self.config=config
        
    def process(self,data):
        if data == None:
            return []
        
        results=[]
        for item in data:
            if item['active'] == True:
                results.append(item)
        return results
"""

    @pytest.fixture
    def messy_javascript_code(self):
        """Real-world example of messy JavaScript code"""
        return """const express=require('express');
const app=express();

function setupRoutes(){
  app.get('/',function(req,res){
    res.send('Hello World')
  });
  
  app.post('/data',async(req,res)=>{
    const data=req.body
    if(data==null||data==undefined){
      res.status(400).send({error:"No data"})
      return
    }
    
    // Process data
    const result=await processData(data)
    res.json({success:true,result:result})
  })
}

async function processData(data){
  return new Promise((resolve,reject)=>{
    setTimeout(()=>{
      if(data.length>0)
        resolve(data.map(x=>x*2))
      else
        reject('Empty data')
    },1000)
  })
}"""

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_fixes_complex_python_code(self, mock_invoke, command, messy_python_code):
        """Test fixing complex Python code with multiple issues"""
        # Mock Claude's fixed response
        fixed_code = """import os
import sys
import json
from typing import List, Dict, Optional

import requests


def fetch_data(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> Optional[Dict]:
    \"\"\"Fetches data from url.\"\"\"
    if headers is None:
        headers = {}
    
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code}")
            return None
    except Exception as e:
        print(f"Failed: {e}")
        return None


class DataProcessor:
    def __init__(self, config: dict):
        self.config = config
        
    def process(self, data: Optional[List[Dict]]) -> List[Dict]:
        if data is None:
            return []
        
        results = []
        for item in data:
            if item['active'] is True:
                results.append(item)
        return results"""

        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = fixed_code
        mock_invoke.return_value = mock_response

        result = command.execute(
            {
                "file_content": messy_python_code,
                "file_path": "/app.py",
                "project_rules": {
                    "linter": "ruff",
                    "formatter": "black",
                    "type_checker": "mypy",
                    "custom_rules": ["Use logging instead of print"],
                },
                "file_type": "python",
            }
        )

        assert result["success"] is True
        assert result["fixed"] is True

        # Check various fixes were applied
        fixed = result["fixed_content"]
        assert "import os\nimport sys" in fixed  # Split imports
        assert "Optional[Dict[str, str]]" in fixed  # Type hints
        assert "if headers is None:" in fixed  # is None instead of == None
        assert '"""Fetches data from url."""' in fixed  # Proper docstring

        # Check changes were detected
        assert len(result["changes_made"]) >= 5
        assert any(
            "import" in change["issue"].lower() for change in result["changes_made"]
        )
        assert any(
            "type" in change["issue"].lower() for change in result["changes_made"]
        )

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_fixes_complex_javascript_code(
        self, mock_invoke, command, messy_javascript_code
    ):
        """Test fixing complex JavaScript code"""
        fixed_code = """const express = require('express');
const app = express();

function setupRoutes() {
  app.get('/', function(req, res) {
    res.send('Hello World');
  });
  
  app.post('/data', async (req, res) => {
    const data = req.body;
    if (data == null || data === undefined) {
      res.status(400).send({ error: "No data" });
      return;
    }
    
    // Process data
    const result = await processData(data);
    res.json({ success: true, result: result });
  });
}

async function processData(data) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (data.length > 0) {
        resolve(data.map(x => x * 2));
      } else {
        reject('Empty data');
      }
    }, 1000);
  });
}"""

        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = fixed_code
        mock_invoke.return_value = mock_response

        result = command.execute(
            {
                "file_content": messy_javascript_code,
                "file_path": "/server.js",
                "project_rules": {
                    "linter": "eslint",
                    "formatter": "prettier",
                    "custom_rules": ["Use semicolons", "Consistent spacing"],
                },
                "file_type": "javascript",
            }
        )

        assert result["success"] is True
        assert result["fixed"] is True

        # Check formatting fixes
        fixed = result["fixed_content"]
        assert "const express = require" in fixed  # Spacing
        assert "res.send('Hello World');" in fixed  # Semicolon
        assert '{ error: "No data" }' in fixed  # Consistent quotes

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_handles_unfixable_issues(self, mock_invoke, command):
        """Test handling of issues that can't be automatically fixed"""
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = """import math

def calculate_risk(value):
    # TODO: Implement proper risk calculation
    # This needs domain knowledge to fix properly
    return value * 0.1  # Placeholder calculation"""
        mock_invoke.return_value = mock_response

        result = command.execute(
            {
                "file_content": "import math\n\ndef calculate_risk(value):\n    # FIXME: Wrong formula\n    return value * 0.1",
                "file_path": "/risk.py",
                "project_rules": {"linter": "ruff"},
                "file_type": "python",
            }
        )

        assert result["success"] is True
        assert len(result.get("unfixable_issues", [])) > 0
        assert any(
            "domain knowledge" in issue["reason"].lower()
            for issue in result.get("unfixable_issues", [])
        )

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_preserves_comments_and_docstrings(self, mock_invoke, command):
        """Test that important comments and docstrings are preserved"""
        original = '''"""Module for user authentication.

This module handles all authentication logic including
OAuth, JWT tokens, and session management.
"""

def authenticate(username, password):
    """Authenticate user with credentials.
    
    Args:
        username: User's username
        password: User's password
        
    Returns:
        dict: Authentication token and user info
    """
    # Important: Rate limit to 3 attempts per minute
    # See security audit #1234
    
    # Validate inputs
    if not username or not password:
        return None
    
    # TODO: Add MFA support (ticket #5678)
    return {"token": "dummy"}'''

        # Mock response preserves important elements
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = original.replace(
            "if not username or not password:", "if not username or not password:"
        )
        mock_invoke.return_value = mock_response

        result = command.execute(
            {
                "file_content": original,
                "file_path": "/auth.py",
                "project_rules": {"formatter": "black"},
                "file_type": "python",
            }
        )

        # Verify important elements preserved
        fixed = result["fixed_content"]
        assert "Module for user authentication" in fixed
        assert "Rate limit to 3 attempts" in fixed
        assert "security audit #1234" in fixed
        assert "TODO: Add MFA support" in fixed

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_respects_project_specific_rules(self, mock_invoke, command):
        """Test that project-specific rules are applied"""
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = """import logging

logger = logging.getLogger(__name__)

MAX_LINE_LENGTH = 80


def process_data(data):
    if not data:
        logger.warning("No data provided")
        return []
    
    return [
        item for item in data 
        if item.get('active')
    ]"""
        mock_invoke.return_value = mock_response

        result = command.execute(
            {
                "file_content": "def process_data(data):\n    print('Processing...')\n    return [item for item in data if item.get('active')]",
                "file_path": "/processor.py",
                "project_rules": {
                    "custom_rules": [
                        "Use logging instead of print",
                        "Max line length 80 characters",
                        "Constants in UPPER_CASE",
                    ]
                },
                "file_type": "python",
            }
        )

        assert result["fixed"] is True
        fixed = result["fixed_content"]
        assert "logger" in fixed
        assert "print" not in fixed
        assert "MAX_LINE_LENGTH" in fixed

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_handles_syntax_errors(self, mock_invoke, command):
        """Test handling of code with syntax errors"""
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = """def calculate(x, y):
    if x > 0:
        return x + y
    else:
        return x - y"""
        mock_invoke.return_value = mock_response

        result = command.execute(
            {
                "file_content": "def calculate(x, y)\n    if x > 0\n        return x + y\n    else:\n        return x - y",
                "file_path": "/calc.py",
                "project_rules": {"linter": "ruff"},
                "file_type": "python",
            }
        )

        assert result["fixed"] is True
        assert "Syntax error" in str(result["changes_made"])

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_timeout_handling(self, mock_invoke, command):
        """Test handling of timeouts with large files"""
        import subprocess

        mock_invoke.side_effect = subprocess.TimeoutExpired("claude", 120)

        # Create a very large file content
        large_content = "\n".join(
            [f"def function_{i}():\n    pass" for i in range(1000)]
        )

        result = command.execute(
            {
                "file_content": large_content,
                "file_path": "/large.py",
                "project_rules": {"formatter": "black"},
                "file_type": "python",
            }
        )

        assert result["success"] is False
        assert "error" in result

    def test_diff_generation(self, command):
        """Test that meaningful diffs are generated"""
        original = "def hello( ):\n  print('hi')"
        fixed = "def hello():\n    print('hi')"

        changes = command._detect_changes(original, fixed)

        assert len(changes) >= 1
        # Should detect both spacing and indentation
        assert any("spacing" in str(change).lower() for change in changes)

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_incremental_fixes(self, mock_invoke, command):
        """Test that fixes can be applied incrementally"""
        # First pass fixes formatting
        mock_response1 = Mock(spec=ClaudeResponse)
        mock_response1.success = True
        mock_response1.content = "def hello():\n    print('hi')"

        # Second pass adds type hints
        mock_response2 = Mock(spec=ClaudeResponse)
        mock_response2.success = True
        mock_response2.content = "def hello() -> None:\n    print('hi')"

        mock_invoke.side_effect = [mock_response1, mock_response2]

        # First fix
        result1 = command.execute(
            {
                "file_content": "def hello( ):\n  print('hi')",
                "file_path": "/test.py",
                "project_rules": {"formatter": "black"},
                "file_type": "python",
            }
        )

        assert result1["fixed"] is True

        # Second fix on already-fixed code
        result2 = command.execute(
            {
                "file_content": result1["fixed_content"],
                "file_path": "/test.py",
                "project_rules": {"type_checker": "mypy"},
                "file_type": "python",
            }
        )

        assert result2["fixed"] is True
        assert "-> None:" in result2["fixed_content"]
