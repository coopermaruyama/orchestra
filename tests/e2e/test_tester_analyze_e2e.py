"""
End-to-end tests for TesterAnalyzeCommand

These tests run against real Claude instances and require:
- CLAUDECODE environment variable set
- Valid Claude CLI installation
"""

import os
import pytest
from orchestra.extensions.tester.commands.analyze import TesterAnalyzeCommand


@pytest.mark.skipif(
    not os.environ.get("CLAUDECODE"),
    reason="E2E tests require Claude Code environment"
)
class TestTesterAnalyzeE2E:
    """End-to-end tests using real Claude instances"""
    
    def test_real_python_test_analysis(self):
        """Test actual Claude analysis of Python code changes"""
        command = TesterAnalyzeCommand(model="haiku")
        
        input_data = {
            "code_changes": {
                "files": ["calculator.py"],
                "diff": """
+class Calculator:
+    \"\"\"Simple calculator with basic operations.\"\"\"
+    
+    def add(self, a: float, b: float) -> float:
+        \"\"\"Add two numbers.\"\"\"
+        return a + b
+    
+    def subtract(self, a: float, b: float) -> float:
+        \"\"\"Subtract b from a.\"\"\"
+        return a - b
+    
+    def multiply(self, a: float, b: float) -> float:
+        \"\"\"Multiply two numbers.\"\"\"
+        return a * b
+    
+    def divide(self, a: float, b: float) -> float:
+        \"\"\"Divide a by b.\"\"\"
+        if b == 0:
+            raise ValueError("Cannot divide by zero")
+        return a / b
+    
+    def power(self, base: float, exponent: float) -> float:
+        \"\"\"Raise base to the power of exponent.\"\"\"
+        return base ** exponent
"""
            },
            "test_context": {
                "framework": "pytest",
                "test_patterns": ["test_*.py"],
                "coverage_requirements": 0.9
            },
            "calibration_data": {
                "test_commands": {"unit": "pytest -xvs"},
                "assertion_style": "assert"
            }
        }
        
        result = command.execute(input_data)
        
        assert result["success"] is True
        assert len(result["tests_needed"]) >= 4  # Should test each method
        
        # Should identify tests for all operations
        test_names = [test["test_name"] for test in result["tests_needed"]]
        assert any("add" in name.lower() for name in test_names)
        assert any("divide" in name.lower() or "zero" in name.lower() for name in test_names)
        
        # Should be unit tests
        assert all(test["test_type"] == "unit" for test in result["tests_needed"])
        
        # Should suggest pytest command
        assert any("pytest" in cmd for cmd in result["suggested_commands"])
    
    def test_real_javascript_react_analysis(self):
        """Test actual Claude analysis of React component"""
        command = TesterAnalyzeCommand(model="haiku")
        
        input_data = {
            "code_changes": {
                "files": ["components/TodoList.jsx"],
                "diff": """
+import React, { useState } from 'react';
+
+export const TodoList = ({ initialTodos = [] }) => {
+  const [todos, setTodos] = useState(initialTodos);
+  const [inputValue, setInputValue] = useState('');
+  
+  const addTodo = () => {
+    if (inputValue.trim()) {
+      setTodos([...todos, {
+        id: Date.now(),
+        text: inputValue,
+        completed: false
+      }]);
+      setInputValue('');
+    }
+  };
+  
+  const toggleTodo = (id) => {
+    setTodos(todos.map(todo =>
+      todo.id === id ? { ...todo, completed: !todo.completed } : todo
+    ));
+  };
+  
+  const deleteTodo = (id) => {
+    setTodos(todos.filter(todo => todo.id !== id));
+  };
+  
+  return (
+    <div className="todo-list">
+      <div className="todo-input">
+        <input
+          value={inputValue}
+          onChange={(e) => setInputValue(e.target.value)}
+          onKeyPress={(e) => e.key === 'Enter' && addTodo()}
+          placeholder="Add a todo..."
+        />
+        <button onClick={addTodo}>Add</button>
+      </div>
+      <ul>
+        {todos.map(todo => (
+          <li key={todo.id} className={todo.completed ? 'completed' : ''}>
+            <input
+              type="checkbox"
+              checked={todo.completed}
+              onChange={() => toggleTodo(todo.id)}
+            />
+            <span>{todo.text}</span>
+            <button onClick={() => deleteTodo(todo.id)}>Delete</button>
+          </li>
+        ))}
+      </ul>
+    </div>
+  );
+};
"""
            },
            "test_context": {
                "framework": "jest",
                "test_patterns": ["*.test.js", "*.spec.js"],
                "coverage_requirements": 0.8
            },
            "calibration_data": {
                "test_commands": {
                    "unit": "npm test",
                    "watch": "npm test -- --watch"
                },
                "test_file_patterns": ["__tests__/*.test.js"],
                "assertion_style": "expect"
            }
        }
        
        result = command.execute(input_data)
        
        assert result["success"] is True
        assert len(result["tests_needed"]) >= 3
        
        # Should identify key functionality tests
        test_reasons = [test["reason"] for test in result["tests_needed"]]
        assert any("add" in reason.lower() for reason in test_reasons)
        assert any("toggle" in reason.lower() or "complete" in reason.lower() for reason in test_reasons)
        assert any("delete" in reason.lower() or "remove" in reason.lower() for reason in test_reasons)
        
        # Should follow Jest conventions
        assert all(test["file"].endswith(".test.js") or test["file"].endswith(".spec.js") 
                  for test in result["tests_needed"])
    
    def test_real_api_endpoint_analysis(self):
        """Test actual Claude analysis of API endpoint"""
        command = TesterAnalyzeCommand(model="haiku")
        
        input_data = {
            "code_changes": {
                "files": ["api/users.py"],
                "diff": """
+from fastapi import APIRouter, HTTPException, Depends
+from sqlalchemy.orm import Session
+from typing import List, Optional
+
+router = APIRouter()
+
+@router.post("/users/")
+async def create_user(
+    user: UserCreate,
+    db: Session = Depends(get_db)
+) -> UserResponse:
+    \"\"\"Create a new user.\"\"\"
+    # Check if email already exists
+    existing = db.query(User).filter(User.email == user.email).first()
+    if existing:
+        raise HTTPException(status_code=400, detail="Email already registered")
+    
+    # Create new user
+    db_user = User(**user.dict())
+    db.add(db_user)
+    db.commit()
+    db.refresh(db_user)
+    
+    return UserResponse.from_orm(db_user)
+
+@router.get("/users/{user_id}")
+async def get_user(
+    user_id: int,
+    db: Session = Depends(get_db)
+) -> UserResponse:
+    \"\"\"Get user by ID.\"\"\"
+    user = db.query(User).filter(User.id == user_id).first()
+    if not user:
+        raise HTTPException(status_code=404, detail="User not found")
+    return UserResponse.from_orm(user)
"""
            },
            "test_context": {
                "framework": "pytest",
                "test_patterns": ["test_*.py"],
                "coverage_requirements": 0.85
            },
            "calibration_data": {
                "test_commands": {
                    "unit": "pytest tests/unit -xvs",
                    "integration": "pytest tests/integration -xvs"
                },
                "assertion_style": "assert"
            }
        }
        
        result = command.execute(input_data)
        
        assert result["success"] is True
        
        # Should identify both unit and integration tests
        test_types = {test["test_type"] for test in result["tests_needed"]}
        assert "integration" in test_types  # API tests are typically integration
        
        # Should test error cases
        test_names = [test["test_name"] for test in result["tests_needed"]]
        assert any("duplicate" in name.lower() or "existing" in name.lower() for name in test_names)
        assert any("not found" in name.lower() or "404" in name.lower() for name in test_names)
        
        # Should identify coverage gaps
        assert len(result["coverage_gaps"]) > 0
    
    def test_real_complex_business_logic(self):
        """Test actual Claude analysis of complex business logic"""
        command = TesterAnalyzeCommand(model="haiku")
        
        input_data = {
            "code_changes": {
                "files": ["services/pricing.py"],
                "diff": """
+class PricingService:
+    \"\"\"Calculate pricing with discounts and taxes.\"\"\"
+    
+    def __init__(self, tax_rate: float = 0.08):
+        self.tax_rate = tax_rate
+        self.discount_tiers = {
+            100: 0.05,   # 5% off for orders over $100
+            250: 0.10,   # 10% off for orders over $250
+            500: 0.15,   # 15% off for orders over $500
+            1000: 0.20   # 20% off for orders over $1000
+        }
+    
+    def calculate_subtotal(self, items: List[CartItem]) -> float:
+        \"\"\"Calculate subtotal of all items.\"\"\"
+        return sum(item.price * item.quantity for item in items)
+    
+    def get_discount_rate(self, subtotal: float) -> float:
+        \"\"\"Get applicable discount rate based on subtotal.\"\"\"
+        for threshold in sorted(self.discount_tiers.keys(), reverse=True):
+            if subtotal >= threshold:
+                return self.discount_tiers[threshold]
+        return 0.0
+    
+    def calculate_discount(self, subtotal: float, coupon_code: Optional[str] = None) -> float:
+        \"\"\"Calculate total discount including tier and coupon.\"\"\"
+        tier_discount = subtotal * self.get_discount_rate(subtotal)
+        
+        coupon_discount = 0.0
+        if coupon_code:
+            coupon = self.validate_coupon(coupon_code)
+            if coupon:
+                if coupon['type'] == 'percentage':
+                    coupon_discount = subtotal * coupon['value']
+                else:  # fixed amount
+                    coupon_discount = min(coupon['value'], subtotal)
+        
+        # Apply only the better discount
+        return max(tier_discount, coupon_discount)
+    
+    def calculate_total(self, items: List[CartItem], coupon_code: Optional[str] = None) -> Dict[str, float]:
+        \"\"\"Calculate complete pricing breakdown.\"\"\"
+        subtotal = self.calculate_subtotal(items)
+        discount = self.calculate_discount(subtotal, coupon_code)
+        discounted_total = subtotal - discount
+        tax = discounted_total * self.tax_rate
+        total = discounted_total + tax
+        
+        return {
+            'subtotal': round(subtotal, 2),
+            'discount': round(discount, 2),
+            'tax': round(tax, 2),
+            'total': round(total, 2)
+        }
"""
            },
            "test_context": {
                "framework": "pytest",
                "test_patterns": ["test_*.py"],
                "coverage_requirements": 0.95  # High coverage for pricing
            },
            "calibration_data": {
                "test_commands": {"unit": "pytest -xvs"},
                "assertion_style": "assert"
            }
        }
        
        result = command.execute(input_data)
        
        assert result["success"] is True
        assert len(result["tests_needed"]) >= 5  # Complex logic needs many tests
        
        # Should identify edge cases
        test_reasons = " ".join(test["reason"] for test in result["tests_needed"])
        assert any(keyword in test_reasons.lower() for keyword in 
                  ["boundary", "edge", "threshold", "tier", "zero", "empty"])
        
        # Should test discount logic
        assert any("discount" in test["test_name"].lower() for test in result["tests_needed"])
        
        # Should have high coverage requirement acknowledgment
        assert "95" in command.build_system_prompt(input_data)
    
    def test_real_data_validation_analysis(self):
        """Test actual Claude analysis of data validation code"""
        command = TesterAnalyzeCommand(model="haiku")
        
        input_data = {
            "code_changes": {
                "files": ["validators/user_input.py"],
                "diff": """
+import re
+from datetime import datetime, date
+from typing import Optional, Dict, Any
+
+class UserInputValidator:
+    \"\"\"Validate and sanitize user inputs.\"\"\"
+    
+    @staticmethod
+    def validate_email(email: str) -> bool:
+        \"\"\"Validate email format.\"\"\"
+        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
+        return bool(re.match(pattern, email.lower().strip()))
+    
+    @staticmethod
+    def validate_phone(phone: str, country_code: str = 'US') -> bool:
+        \"\"\"Validate phone number for given country.\"\"\"
+        # Remove all non-digits
+        digits = re.sub(r'\\D', '', phone)
+        
+        if country_code == 'US':
+            # US phone: 10 digits, optional 1 prefix
+            return len(digits) == 10 or (len(digits) == 11 and digits[0] == '1')
+        elif country_code == 'UK':
+            # UK phone: 11 digits starting with 0
+            return len(digits) == 11 and digits[0] == '0'
+        else:
+            # Generic: 7-15 digits
+            return 7 <= len(digits) <= 15
+    
+    @staticmethod
+    def validate_date_of_birth(dob: str) -> Optional[date]:
+        \"\"\"Validate and parse date of birth.\"\"\"
+        try:
+            # Try multiple date formats
+            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']:
+                try:
+                    parsed = datetime.strptime(dob, fmt).date()
+                    
+                    # Check reasonable age (0-150 years)
+                    today = date.today()
+                    age = today.year - parsed.year
+                    if age < 0 or age > 150:
+                        return None
+                    
+                    # Check not future date
+                    if parsed > today:
+                        return None
+                    
+                    return parsed
+                except ValueError:
+                    continue
+            
+            return None
+        except Exception:
+            return None
+    
+    @staticmethod  
+    def sanitize_input(text: str, max_length: int = 1000) -> str:
+        \"\"\"Sanitize text input.\"\"\"
+        # Remove control characters
+        sanitized = ''.join(char for char in text if ord(char) >= 32)
+        # Trim whitespace
+        sanitized = sanitized.strip()
+        # Limit length
+        return sanitized[:max_length]
"""
            },
            "test_context": {
                "framework": "pytest",
                "test_patterns": ["test_*.py"],
                "coverage_requirements": 0.9
            },
            "calibration_data": {}
        }
        
        result = command.execute(input_data)
        
        assert result["success"] is True
        assert len(result["tests_needed"]) >= 8  # Many edge cases for validation
        
        # Should test various validation scenarios
        test_names = " ".join(test["test_name"] for test in result["tests_needed"])
        assert any(keyword in test_names.lower() for keyword in 
                  ["invalid", "valid", "edge", "format", "boundary"])
        
        # Should test multiple countries for phone
        assert any("country" in test.get("reason", "").lower() or 
                  "UK" in test.get("reason", "") or
                  "US" in test.get("reason", "")
                  for test in result["tests_needed"])
        
        # Should identify security testing needs
        assert any("sanitize" in gap.lower() or "security" in gap.lower() 
                  for gap in result["coverage_gaps"])
    
    @pytest.mark.slow
    def test_real_large_codebase_changes(self):
        """Test performance with large code changes"""
        command = TesterAnalyzeCommand(model="haiku")
        
        # Generate large diff with multiple classes
        large_diff = ""
        for i in range(10):
            large_diff += f"""
+class Service{i}:
+    def method_a(self): pass
+    def method_b(self): pass
+    def method_c(self): pass
"""
        
        input_data = {
            "code_changes": {
                "files": [f"service{i}.py" for i in range(10)],
                "diff": large_diff
            },
            "test_context": {
                "framework": "pytest",
                "coverage_requirements": 0.8
            },
            "calibration_data": {}
        }
        
        import time
        start = time.time()
        result = command.execute(input_data)
        elapsed = time.time() - start
        
        assert result["success"] is True
        assert elapsed < 30  # Should complete within 30 seconds
        
        # Should provide reasonable number of tests, not overwhelming
        assert 5 <= len(result["tests_needed"]) <= 50
    
    def test_real_no_tests_needed_scenario(self):
        """Test when changes don't require new tests"""
        command = TesterAnalyzeCommand(model="haiku")
        
        input_data = {
            "code_changes": {
                "files": ["README.md", "docs/api.md"],
                "diff": """
+# API Documentation
+
+## Endpoints
+
+### GET /users
+Returns list of users.
+
+### POST /users  
+Creates a new user.
"""
            },
            "test_context": {
                "framework": "pytest",
                "coverage_requirements": 0.8
            },
            "calibration_data": {}
        }
        
        result = command.execute(input_data)
        
        assert result["success"] is True
        # Documentation changes shouldn't require tests
        assert len(result["tests_needed"]) == 0
        
    def test_real_test_framework_specific_suggestions(self):
        """Test framework-specific test suggestions"""
        command = TesterAnalyzeCommand(model="haiku")
        
        # Test with Go code and Go test framework
        input_data = {
            "code_changes": {
                "files": ["calculator.go"],
                "diff": """
+package calculator
+
+// Add returns the sum of two integers
+func Add(a, b int) int {
+    return a + b
+}
+
+// Divide returns a divided by b
+func Divide(a, b int) (int, error) {
+    if b == 0 {
+        return 0, errors.New("division by zero")
+    }
+    return a / b, nil
+}
"""
            },
            "test_context": {
                "framework": "go test",
                "test_patterns": ["*_test.go"],
                "coverage_requirements": 0.8
            },
            "calibration_data": {
                "test_commands": {"unit": "go test -v"},
                "assertion_style": "testify"
            }
        }
        
        result = command.execute(input_data)
        
        assert result["success"] is True
        
        # Should follow Go conventions
        assert all(test["file"].endswith("_test.go") for test in result["tests_needed"])
        assert any("go test" in cmd for cmd in result["suggested_commands"])
        
        # Should test error cases
        assert any("error" in test["reason"].lower() or "zero" in test["reason"].lower()
                  for test in result["tests_needed"])