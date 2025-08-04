# ruff: noqa: SLF001
"""
End-to-end tests for TidyFixCommand

These tests run against real Claude instances and require:
- CLAUDECODE environment variable set
- Valid Claude CLI installation
"""

import os

import pytest

from orchestra.extensions.tidy.commands.fix import TidyFixCommand


@pytest.mark.skipif(
    not os.environ.get("CLAUDECODE"), reason="E2E tests require Claude Code environment"
)
class TestTidyFixE2E:
    """End-to-end tests using real Claude instances"""

    def test_real_python_formatting_fix(self):
        """Test actual Claude fixing of Python formatting issues"""
        command = TidyFixCommand(model="haiku")

        messy_code = """import os,sys
def calculate(x,y,z):
    result=x+y*z
    if result>100:
        print("Large result")
        return result
    else:
        print("Small result") 
        return result"""

        result = command.execute(
            {
                "file_content": messy_code,
                "file_path": "/calc.py",
                "project_rules": {"formatter": "black", "linter": "ruff"},
                "file_type": "python",
            }
        )

        assert result["success"] is True
        assert result["fixed"] is True

        fixed = result["fixed_content"]
        # Should fix import formatting
        assert "import os\nimport sys" in fixed or "import os, sys" not in fixed
        # Should fix spacing
        assert "def calculate(x, y, z):" in fixed
        assert "result = x + y * z" in fixed
        # Should maintain logic
        assert "Large result" in fixed
        assert "Small result" in fixed

    def test_real_javascript_eslint_fix(self):
        """Test actual Claude fixing of JavaScript linting issues"""
        command = TidyFixCommand(model="haiku")

        messy_js = """const data=[1,2,3]
function processData(){
  for(var i=0;i<data.length;i++){
    console.log(data[i])
  }
  return data.map(x=>x*2)
}
const result=processData()"""

        result = command.execute(
            {
                "file_content": messy_js,
                "file_path": "/process.js",
                "project_rules": {
                    "linter": "eslint",
                    "formatter": "prettier",
                    "custom_rules": ["prefer const over var", "use semicolons"],
                },
                "file_type": "javascript",
            }
        )

        assert result["success"] is True
        assert result["fixed"] is True

        fixed = result["fixed_content"]
        # Should not use var
        assert "var i" not in fixed or "let i" in fixed or "const" in fixed
        # Should have consistent spacing
        assert "= [" in fixed or "= processData()" in fixed
        # Should add semicolons
        assert ";" in fixed

    def test_real_type_annotation_addition(self):
        """Test actual Claude adding type annotations"""
        command = TidyFixCommand(model="haiku")

        untyped_code = """def process_user_data(users, filter_active):
    filtered = []
    for user in users:
        if filter_active and user.get('active'):
            filtered.append(user)
        elif not filter_active:
            filtered.append(user)
    return filtered

def calculate_average(numbers):
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)"""

        result = command.execute(
            {
                "file_content": untyped_code,
                "file_path": "/users.py",
                "project_rules": {"type_checker": "mypy", "formatter": "black"},
                "file_type": "python",
            }
        )

        assert result["success"] is True

        fixed = result["fixed_content"]
        # Should add type hints
        assert ("List" in fixed or "list" in fixed) and ":" in fixed
        # Should preserve logic
        assert "filter_active" in fixed
        assert "sum(numbers) / len(numbers)" in fixed

    def test_real_custom_rules_enforcement(self):
        """Test actual Claude enforcing custom project rules"""
        command = TidyFixCommand(model="haiku")

        code_violating_rules = """import json

def load_config():
    print("Loading configuration...")
    config = json.load(open('config.json'))
    print(f"Loaded config: {config}")
    return config

def save_data(data):
    f = open('output.txt', 'w')
    f.write(str(data))
    f.close()
    print("Data saved")"""

        result = command.execute(
            {
                "file_content": code_violating_rules,
                "file_path": "/config.py",
                "project_rules": {
                    "linter": "ruff",
                    "custom_rules": [
                        "Use logging instead of print statements",
                        "Use context managers (with statements) for file operations",
                        "No hardcoded file paths",
                    ],
                },
                "file_type": "python",
            }
        )

        assert result["success"] is True
        assert result["fixed"] is True

        fixed = result["fixed_content"]
        # Should replace print with logging
        assert "print(" not in fixed or "logger" in fixed or "logging" in fixed
        # Should use context managers
        assert "with open" in fixed
        # Original logic preserved
        assert "config.json" in fixed or "config" in fixed

    def test_real_complex_refactoring(self):
        """Test actual Claude handling complex code improvements"""
        command = TidyFixCommand(model="haiku")

        complex_code = """class UserManager:
    def __init__(self):
        self.users = []
    
    def add_user(self, name, email, age):
        if name == None or email == None:
            return False
        
        for user in self.users:
            if user['email'] == email:
                print("User already exists")
                return False
        
        self.users.append({'name': name, 'email': email, 'age': age})
        return True
    
    def get_users_by_age(self, min_age, max_age):
        result = []
        for user in self.users:
            if user['age'] >= min_age and user['age'] <= max_age:
                result.append(user)
        return result"""

        result = command.execute(
            {
                "file_content": complex_code,
                "file_path": "/user_manager.py",
                "project_rules": {
                    "linter": "ruff",
                    "formatter": "black",
                    "type_checker": "mypy",
                    "custom_rules": [
                        "Use 'is None' instead of '== None'",
                        "Use list comprehensions where appropriate",
                        "Add type hints to all methods",
                    ],
                },
                "file_type": "python",
            }
        )

        assert result["success"] is True

        if result["fixed"]:
            fixed = result["fixed_content"]
            # Should fix None comparison
            assert "is None" in fixed or "== None" not in fixed
            # Should maintain all functionality
            assert "add_user" in fixed
            assert "get_users_by_age" in fixed
            assert "email" in fixed

    def test_real_syntax_error_recovery(self):
        """Test actual Claude fixing syntax errors"""
        command = TidyFixCommand(model="haiku")

        broken_code = """def calculate_total(items)
    total = 0
    for item in items
        if item.price > 0
            total += item.price * item.quantity
    return total

class ShoppingCart
    def __init__(self):
        self.items = []
    
    def add_item(self, item)
        self.items.append(item)"""

        result = command.execute(
            {
                "file_content": broken_code,
                "file_path": "/cart.py",
                "project_rules": {"linter": "ruff"},
                "file_type": "python",
            }
        )

        assert result["success"] is True
        assert result["fixed"] is True

        fixed = result["fixed_content"]
        # Should add missing colons
        assert "def calculate_total(items):" in fixed
        assert "for item in items:" in fixed
        assert "if item.price > 0:" in fixed
        assert "class ShoppingCart:" in fixed
        # Logic preserved
        assert "total += item.price * item.quantity" in fixed

    def test_real_mixed_issues(self):
        """Test actual Claude fixing multiple types of issues"""
        command = TidyFixCommand(model="haiku")

        problematic_code = """import requests,json
from datetime import datetime
import os

API_KEY="secret123"

def fetch_data(endpoint):
    '''Gets data from API'''
    headers={'Authorization':f'Bearer {API_KEY}'}
    
    try:
        resp=requests.get(f"https://api.example.com/{endpoint}",headers=headers)
        if resp.status_code==200:
            data=resp.json()
            print(f"Success: {len(data)} items")
            return data
        else:
            print(f"Error: {resp.status_code}")
    except Exception as e:
        print(f"Failed: {e}")
    
    return None"""

        result = command.execute(
            {
                "file_content": problematic_code,
                "file_path": "/api_client.py",
                "project_rules": {
                    "linter": "ruff",
                    "formatter": "black",
                    "custom_rules": [
                        "Don't hardcode secrets",
                        "Use proper logging",
                        "Use consistent quote style (double quotes)",
                    ],
                },
                "file_type": "python",
            }
        )

        assert result["success"] is True
        assert result["fixed"] is True

        fixed = result["fixed_content"]
        # Multiple issues should be addressed
        assert len(result["changes_made"]) > 3
        # API key issue should be noted or fixed
        assert "secret123" not in fixed or any(
            "secret" in issue["issue"].lower()
            for issue in result.get("unfixable_issues", [])
        )

    @pytest.mark.slow
    def test_real_large_file_performance(self):
        """Test performance with large files"""
        command = TidyFixCommand(model="haiku")

        # Generate a large but realistic file
        large_code = """import datetime
import json

class DataProcessor:
    def __init__(self):
        self.data = []
        
"""
        # Add many similar methods
        for i in range(50):
            large_code += f"""
    def process_type_{i}(self, input_data):
        result=[]
        for item in input_data:
            if item['type']=={i}:
                result.append(item)
        return result
"""

        import time

        start = time.time()

        result = command.execute(
            {
                "file_content": large_code,
                "file_path": "/processor.py",
                "project_rules": {"formatter": "black", "linter": "ruff"},
                "file_type": "python",
            }
        )

        elapsed = time.time() - start

        assert result["success"] is True
        assert elapsed < 30  # Should complete within 30 seconds

        if result["fixed"]:
            # Should fix spacing issues
            assert "result = []" in result["fixed_content"]
            assert "== " in result["fixed_content"]

    def test_real_no_changes_needed(self):
        """Test when code is already clean"""
        command = TidyFixCommand(model="haiku")

        clean_code = """\"\"\"Well-formatted module.\"\"\"

from typing import List, Optional


def calculate_average(numbers: List[float]) -> Optional[float]:
    \"\"\"Calculate the average of a list of numbers.
    
    Args:
        numbers: List of numbers to average.
        
    Returns:
        The average, or None if the list is empty.
    \"\"\"
    if not numbers:
        return None
    return sum(numbers) / len(numbers)
"""

        result = command.execute(
            {
                "file_content": clean_code,
                "file_path": "/stats.py",
                "project_rules": {
                    "formatter": "black",
                    "linter": "ruff",
                    "type_checker": "mypy",
                },
                "file_type": "python",
            }
        )

        assert result["success"] is True
        # Should recognize no changes needed
        assert (
            not result["fixed"] or result["fixed_content"].strip() == clean_code.strip()
        )
        assert len(result.get("changes_made", [])) == 0
