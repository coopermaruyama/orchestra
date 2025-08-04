# ruff: noqa: SLF001
"""
Integration tests for TesterAnalyzeCommand

Tests the command with realistic scenarios and edge cases.
"""

import json
import logging
from unittest.mock import Mock, patch

import pytest

from orchestra.common.claude_cli_wrapper import ClaudeResponse
from orchestra.extensions.tester.commands.analyze import TesterAnalyzeCommand


class TestTesterAnalyzeIntegration:
    """Integration tests for TesterAnalyzeCommand"""

    @pytest.fixture
    def command(self):
        """Create command instance with custom logger"""
        logger = logging.getLogger("test_tester_analyze")
        return TesterAnalyzeCommand(model="haiku", logger=logger)

    @pytest.fixture
    def real_world_python_changes(self):
        """Real-world Python code changes"""
        return {
            "code_changes": {
                "files": ["auth/manager.py", "auth/validators.py"],
                "diff": """
diff --git a/auth/manager.py b/auth/manager.py
index abc123..def456 100644
--- a/auth/manager.py
+++ b/auth/manager.py
@@ -15,6 +15,25 @@ class AuthManager:
         self.token_expiry = timedelta(hours=24)
         
+    async def register_user(self, email: str, password: str, username: str) -> User:
+        \"\"\"Register a new user with validation.\"\"\"
+        # Validate inputs
+        if not validate_email(email):
+            raise ValueError("Invalid email format")
+        
+        if not validate_password(password):
+            raise ValueError("Password does not meet requirements")
+        
+        # Check if user exists
+        existing = await self.db.get_user_by_email(email)
+        if existing:
+            raise ValueError("User already exists")
+        
+        # Create user
+        hashed_password = await hash_password(password)
+        user = await self.db.create_user(email, hashed_password, username)
+        
+        return user
+
diff --git a/auth/validators.py b/auth/validators.py
index 789012..345678 100644
--- a/auth/validators.py
+++ b/auth/validators.py
@@ -5,3 +5,15 @@ def validate_email(email: str) -> bool:
     pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
     return bool(re.match(pattern, email))
+
+def validate_password(password: str) -> bool:
+    \"\"\"Validate password meets security requirements.\"\"\"
+    if len(password) < 8:
+        return False
+    
+    has_upper = any(c.isupper() for c in password)
+    has_lower = any(c.islower() for c in password)
+    has_digit = any(c.isdigit() for c in password)
+    has_special = any(c in '!@#$%^&*()' for c in password)
+    
+    return all([has_upper, has_lower, has_digit, has_special])
""",
            },
            "test_context": {
                "framework": "pytest",
                "test_patterns": ["test_*.py", "*_test.py"],
                "coverage_requirements": 0.85,
            },
            "calibration_data": {
                "test_commands": {
                    "unit": "pytest -xvs",
                    "integration": "pytest -xvs -m integration",
                    "coverage": "pytest --cov=auth --cov-report=term-missing",
                },
                "test_file_patterns": [
                    "tests/unit/test_*.py",
                    "tests/integration/test_*.py",
                ],
                "assertion_style": "assert",
            },
        }

    @pytest.fixture
    def real_world_javascript_changes(self):
        """Real-world JavaScript/React code changes"""
        return {
            "code_changes": {
                "files": ["components/ShoppingCart.jsx", "hooks/useCart.js"],
                "diff": """
diff --git a/components/ShoppingCart.jsx b/components/ShoppingCart.jsx
+export const ShoppingCart = () => {
+  const { items, total, addItem, removeItem, clearCart } = useCart();
+  const [isProcessing, setIsProcessing] = useState(false);
+  
+  const handleCheckout = async () => {
+    setIsProcessing(true);
+    try {
+      const result = await processPayment(total);
+      if (result.success) {
+        clearCart();
+        navigate('/success');
+      }
+    } catch (error) {
+      showError(error.message);
+    } finally {
+      setIsProcessing(false);
+    }
+  };
+
+  return (
+    <div className="shopping-cart">
+      {items.map(item => (
+        <CartItem key={item.id} {...item} onRemove={removeItem} />
+      ))}
+      <div className="total">Total: ${total}</div>
+      <button onClick={handleCheckout} disabled={isProcessing || items.length === 0}>
+        {isProcessing ? 'Processing...' : 'Checkout'}
+      </button>
+    </div>
+  );
+};

diff --git a/hooks/useCart.js b/hooks/useCart.js
+export const useCart = () => {
+  const [items, setItems] = useState([]);
+  
+  const addItem = useCallback((product) => {
+    setItems(prev => {
+      const existing = prev.find(item => item.id === product.id);
+      if (existing) {
+        return prev.map(item => 
+          item.id === product.id 
+            ? { ...item, quantity: item.quantity + 1 }
+            : item
+        );
+      }
+      return [...prev, { ...product, quantity: 1 }];
+    });
+  }, []);
+  
+  const removeItem = useCallback((productId) => {
+    setItems(prev => prev.filter(item => item.id !== productId));
+  }, []);
+  
+  const clearCart = useCallback(() => {
+    setItems([]);
+  }, []);
+  
+  const total = useMemo(() => {
+    return items.reduce((sum, item) => sum + (item.price * item.quantity), 0);
+  }, [items]);
+  
+  return { items, total, addItem, removeItem, clearCart };
+};
""",
            },
            "test_context": {
                "framework": "jest",
                "test_patterns": ["*.test.js", "*.spec.js"],
                "coverage_requirements": 0.8,
            },
            "calibration_data": {
                "test_commands": {
                    "unit": "npm test",
                    "watch": "npm test -- --watch",
                    "coverage": "npm test -- --coverage",
                },
                "test_file_patterns": ["__tests__/*.test.js"],
                "assertion_style": "expect",
            },
        }

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_analyzes_python_auth_changes(
        self, mock_invoke, command, real_world_python_changes
    ):
        """Test analysis of authentication system changes"""
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps(
            {
                "tests_needed": [
                    {
                        "file": "tests/unit/test_auth_manager.py",
                        "test_name": "test_register_user_success",
                        "test_type": "unit",
                        "reason": "Test successful user registration with valid inputs",
                    },
                    {
                        "file": "tests/unit/test_auth_manager.py",
                        "test_name": "test_register_user_invalid_email",
                        "test_type": "unit",
                        "reason": "Test error handling for invalid email format",
                    },
                    {
                        "file": "tests/unit/test_auth_manager.py",
                        "test_name": "test_register_user_weak_password",
                        "test_type": "unit",
                        "reason": "Test error handling for weak passwords",
                    },
                    {
                        "file": "tests/unit/test_auth_manager.py",
                        "test_name": "test_register_user_duplicate",
                        "test_type": "unit",
                        "reason": "Test error when user already exists",
                    },
                    {
                        "file": "tests/unit/test_validators.py",
                        "test_name": "test_validate_password_requirements",
                        "test_type": "unit",
                        "reason": "Test all password validation rules",
                    },
                    {
                        "file": "tests/integration/test_auth_flow.py",
                        "test_name": "test_complete_registration_flow",
                        "test_type": "integration",
                        "reason": "Test full registration with database",
                    },
                ],
                "suggested_commands": [
                    "pytest tests/unit/test_auth_manager.py -xvs",
                    "pytest tests/unit/test_validators.py -xvs",
                    "pytest -xvs -m integration",
                    "pytest --cov=auth --cov-report=term-missing",
                ],
                "coverage_gaps": [
                    "Edge cases for password validation (unicode, very long passwords)",
                    "Concurrent registration attempts",
                    "Database connection failures",
                ],
                "existing_tests_to_update": [],
            }
        )
        mock_invoke.return_value = mock_response

        result = command.execute(real_world_python_changes)

        assert result["success"] is True
        assert len(result["tests_needed"]) >= 5

        # Should identify different test types
        test_types = {test["test_type"] for test in result["tests_needed"]}
        assert "unit" in test_types
        assert "integration" in test_types

        # Should suggest appropriate test files
        test_files = {test["file"] for test in result["tests_needed"]}
        assert any("test_auth_manager" in f for f in test_files)
        assert any("test_validators" in f for f in test_files)

        # Should include coverage command
        assert any("--cov" in cmd for cmd in result["suggested_commands"])

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_analyzes_react_component_changes(
        self, mock_invoke, command, real_world_javascript_changes
    ):
        """Test analysis of React component and hook changes"""
        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps(
            {
                "tests_needed": [
                    {
                        "file": "__tests__/ShoppingCart.test.js",
                        "test_name": "renders cart items correctly",
                        "test_type": "unit",
                        "reason": "Test component renders all cart items",
                    },
                    {
                        "file": "__tests__/ShoppingCart.test.js",
                        "test_name": "handles checkout process",
                        "test_type": "unit",
                        "reason": "Test checkout flow with mocked payment",
                    },
                    {
                        "file": "__tests__/ShoppingCart.test.js",
                        "test_name": "disables checkout when cart empty",
                        "test_type": "unit",
                        "reason": "Test button disabled state",
                    },
                    {
                        "file": "__tests__/useCart.test.js",
                        "test_name": "adds items to cart",
                        "test_type": "unit",
                        "reason": "Test addItem increases quantity for existing items",
                    },
                    {
                        "file": "__tests__/useCart.test.js",
                        "test_name": "calculates total correctly",
                        "test_type": "unit",
                        "reason": "Test total calculation with multiple items",
                    },
                    {
                        "file": "__tests__/integration/checkout.test.js",
                        "test_name": "complete checkout flow",
                        "test_type": "e2e",
                        "reason": "Test full user checkout journey",
                    },
                ],
                "suggested_commands": [
                    "npm test ShoppingCart",
                    "npm test useCart",
                    "npm test -- --coverage",
                    "npm run test:e2e",
                ],
                "coverage_gaps": [
                    "Error handling for payment failures",
                    "Loading states during checkout",
                    "Cart persistence across sessions",
                ],
                "existing_tests_to_update": ["__tests__/App.test.js"],
            }
        )
        mock_invoke.return_value = mock_response

        result = command.execute(real_world_javascript_changes)

        assert result["success"] is True

        # Should test both component and hook
        test_files = {test["file"] for test in result["tests_needed"]}
        assert any("ShoppingCart.test" in f for f in test_files)
        assert any("useCart.test" in f for f in test_files)

        # Should include E2E test
        assert any(test["test_type"] == "e2e" for test in result["tests_needed"])

        # Should follow Jest conventions
        assert "expect" in command.build_system_prompt(real_world_javascript_changes)

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_handles_api_endpoint_changes(self, mock_invoke, command):
        """Test analysis of API endpoint changes"""
        input_data = {
            "code_changes": {
                "files": ["api/routes/products.py"],
                "diff": """
+@router.get("/products/search")
+async def search_products(
+    q: str = Query(..., min_length=1),
+    category: Optional[str] = None,
+    min_price: Optional[float] = None,
+    max_price: Optional[float] = None,
+    sort_by: str = Query("relevance", regex="^(relevance|price|rating)$"),
+    limit: int = Query(20, ge=1, le=100),
+    db: Session = Depends(get_db)
+):
+    \"\"\"Search products with filters.\"\"\"
+    query = db.query(Product).filter(Product.name.contains(q))
+    
+    if category:
+        query = query.filter(Product.category == category)
+    
+    if min_price is not None:
+        query = query.filter(Product.price >= min_price)
+    
+    if max_price is not None:
+        query = query.filter(Product.price <= max_price)
+    
+    # Apply sorting
+    if sort_by == "price":
+        query = query.order_by(Product.price)
+    elif sort_by == "rating":
+        query = query.order_by(Product.rating.desc())
+    
+    products = query.limit(limit).all()
+    return {"results": products, "count": len(products)}
""",
            },
            "test_context": {
                "framework": "pytest",
                "test_patterns": ["test_*.py"],
                "coverage_requirements": 0.9,
            },
            "calibration_data": {
                "test_commands": {"api": "pytest tests/api -xvs"},
                "test_file_patterns": ["tests/api/test_*.py"],
            },
        }

        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps(
            {
                "tests_needed": [
                    {
                        "file": "tests/api/test_products.py",
                        "test_name": "test_search_products_basic",
                        "test_type": "integration",
                        "reason": "Test basic search functionality",
                    },
                    {
                        "file": "tests/api/test_products.py",
                        "test_name": "test_search_with_filters",
                        "test_type": "integration",
                        "reason": "Test all filter combinations",
                    },
                    {
                        "file": "tests/api/test_products.py",
                        "test_name": "test_search_validation",
                        "test_type": "integration",
                        "reason": "Test input validation (empty query, invalid sort)",
                    },
                    {
                        "file": "tests/api/test_products.py",
                        "test_name": "test_search_pagination",
                        "test_type": "integration",
                        "reason": "Test limit parameter boundaries",
                    },
                ],
                "suggested_commands": [
                    "pytest tests/api/test_products.py::test_search* -xvs"
                ],
                "coverage_gaps": [
                    "SQL injection testing",
                    "Performance with large datasets",
                    "Unicode search queries",
                ],
                "existing_tests_to_update": [],
            }
        )
        mock_invoke.return_value = mock_response

        result = command.execute(input_data)

        # Should focus on API/integration tests
        assert all(
            test["test_type"] == "integration" for test in result["tests_needed"]
        )
        assert "validation" in str(result["tests_needed"])
        assert "SQL injection" in str(result["coverage_gaps"])

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_identifies_performance_test_needs(self, mock_invoke, command):
        """Test identification of performance testing needs"""
        input_data = {
            "code_changes": {
                "files": ["data/processor.py"],
                "diff": """
+def process_large_dataset(data: List[Dict]) -> Dict[str, Any]:
+    \"\"\"Process large datasets with aggregation.\"\"\"
+    results = defaultdict(list)
+    
+    # Group by category
+    for item in data:
+        category = item.get('category', 'unknown')
+        results[category].append(item)
+    
+    # Calculate statistics per category
+    stats = {}
+    for category, items in results.items():
+        values = [item['value'] for item in items if 'value' in item]
+        stats[category] = {
+            'count': len(items),
+            'sum': sum(values),
+            'avg': sum(values) / len(values) if values else 0,
+            'min': min(values) if values else 0,
+            'max': max(values) if values else 0
+        }
+    
+    return {'grouped': dict(results), 'statistics': stats}
""",
            },
            "test_context": {"framework": "pytest", "coverage_requirements": 0.8},
            "calibration_data": {},
        }

        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps(
            {
                "tests_needed": [
                    {
                        "file": "tests/test_processor.py",
                        "test_name": "test_process_empty_dataset",
                        "test_type": "unit",
                        "reason": "Test edge case with empty data",
                    },
                    {
                        "file": "tests/test_processor.py",
                        "test_name": "test_process_missing_values",
                        "test_type": "unit",
                        "reason": "Test handling of missing 'value' fields",
                    },
                    {
                        "file": "tests/performance/test_processor_perf.py",
                        "test_name": "test_large_dataset_performance",
                        "test_type": "performance",
                        "reason": "Test performance with 100k+ items",
                    },
                ],
                "suggested_commands": [
                    "pytest tests/test_processor.py",
                    "pytest tests/performance -xvs",
                ],
                "coverage_gaps": ["Memory usage profiling", "Concurrent processing"],
                "existing_tests_to_update": [],
            }
        )
        mock_invoke.return_value = mock_response

        result = command.execute(input_data)

        # Should identify performance testing need
        assert any(
            test["test_type"] == "performance" for test in result["tests_needed"]
        )
        assert "Memory usage" in str(result["coverage_gaps"])

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_suggests_test_refactoring(self, mock_invoke, command):
        """Test when existing tests need updates"""
        input_data = {
            "code_changes": {
                "files": ["models/user.py"],
                "diff": """
-    def __init__(self, email: str, username: str):
+    def __init__(self, email: str, username: str, role: str = "user"):
         self.email = email
         self.username = username
+        self.role = role
         self.created_at = datetime.utcnow()
         
-    def to_dict(self) -> Dict[str, Any]:
+    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
         return {
             'id': self.id,
             'email': self.email,
             'username': self.username,
+            'role': self.role,
             'created_at': self.created_at.isoformat()
         }
""",
            },
            "test_context": {"framework": "pytest"},
            "calibration_data": {},
        }

        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps(
            {
                "tests_needed": [
                    {
                        "file": "tests/test_user_model.py",
                        "test_name": "test_user_with_custom_role",
                        "test_type": "unit",
                        "reason": "Test new role parameter",
                    }
                ],
                "suggested_commands": ["pytest tests/test_user_model.py -xvs"],
                "coverage_gaps": [],
                "existing_tests_to_update": [
                    "tests/test_user_model.py::test_user_creation",
                    "tests/test_user_model.py::test_to_dict",
                    "tests/integration/test_user_api.py",
                ],
            }
        )
        mock_invoke.return_value = mock_response

        result = command.execute(input_data)

        # Should identify tests needing updates
        assert len(result["existing_tests_to_update"]) >= 3
        assert "test_user_creation" in str(result["existing_tests_to_update"])
        assert "test_to_dict" in str(result["existing_tests_to_update"])

    @patch("orchestra.common.claude_cli_wrapper.ClaudeCLIWrapper.invoke")
    def test_handles_test_framework_migration(self, mock_invoke, command):
        """Test when codebase is migrating test frameworks"""
        input_data = {
            "code_changes": {
                "files": ["tests/conftest.py"],
                "diff": """
+import pytest
+from unittest import mock
+
+# Migrating from unittest to pytest
+
+@pytest.fixture
+def mock_database():
+    \"\"\"Mock database for testing.\"\"\"
+    with mock.patch('app.db.get_connection') as mock_conn:
+        yield mock_conn
+
+@pytest.fixture
+def client():
+    \"\"\"Test client fixture.\"\"\"
+    from app import create_app
+    app = create_app('testing')
+    with app.test_client() as client:
+        yield client
""",
            },
            "test_context": {"framework": "pytest", "test_patterns": ["test_*.py"]},
            "calibration_data": {
                "test_commands": {"migrate": "pytest --co -q | grep unittest"},
                "assertion_style": "assert",
            },
        }

        mock_response = Mock(spec=ClaudeResponse)
        mock_response.success = True
        mock_response.content = json.dumps(
            {
                "tests_needed": [],
                "suggested_commands": ["pytest --co -q | grep unittest", "pytest -xvs"],
                "coverage_gaps": ["Tests still using unittest.TestCase"],
                "existing_tests_to_update": [
                    "All tests using self.assertEqual",
                    "Tests inheriting from unittest.TestCase",
                ],
            }
        )
        mock_invoke.return_value = mock_response

        result = command.execute(input_data)

        # Should recognize migration scenario
        assert "unittest" in str(result["coverage_gaps"])
        assert "assertEqual" in str(result["existing_tests_to_update"])

    def test_prompt_includes_framework_specifics(self, command):
        """Test that prompts include framework-specific details"""
        frameworks = [
            ("pytest", "assert", "test_*.py"),
            ("jest", "expect", "*.test.js"),
            ("mocha", "chai", "*.spec.js"),
            ("rspec", "expect", "*_spec.rb"),
            ("junit", "@Test", "*Test.java"),
        ]

        for framework, assertion, pattern in frameworks:
            input_data = {
                "code_changes": {"files": ["app.py"], "diff": "+def func(): pass"},
                "test_context": {"framework": framework, "test_patterns": [pattern]},
                "calibration_data": {"assertion_style": assertion},
            }

            system_prompt = command.build_system_prompt(input_data)

            assert framework in system_prompt
            assert assertion in system_prompt or pattern in system_prompt
