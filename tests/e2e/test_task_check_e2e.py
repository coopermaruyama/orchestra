"""
End-to-end tests for TaskCheckCommand

These tests run against real Claude instances and require:
- CLAUDECODE environment variable set
- Valid Claude CLI installation
"""

import os

import pytest

from orchestra.extensions.task.commands.check import TaskCheckCommand


@pytest.mark.skipif(
    not os.environ.get("CLAUDECODE"), reason="E2E tests require Claude Code environment"
)
class TestTaskCheckE2E:
    """End-to-end tests using real Claude instances"""

    def test_real_scope_creep_detection(self):
        """Test actual Claude detection of scope creep"""
        command = TaskCheckCommand(model="haiku")  # Use fast model for tests

        input_data = {
            "transcript": """
            User: I need to fix the login bug where users get 500 errors
            Assistant: I'll help fix the login bug. Let me also add OAuth integration.
            User: Sure, that would be great!
            Assistant: I'll implement Google OAuth, Facebook OAuth, and GitHub OAuth.
            """,
            "diff": """
            diff --git a/auth.py b/auth.py
            index 1234567..abcdefg 100644
            --- a/auth.py
            +++ b/auth.py
            @@ -1,5 +1,45 @@
             import logging
            +from google.oauth2 import credentials
            +from facebook_sdk import OAuth as FBOAuth  
            +from github import GitHubOAuth
             
             def login(username, password):
                 # TODO: Fix 500 error here
                 pass
            +
            +class OAuthManager:
            +    def __init__(self):
            +        self.providers = {
            +            'google': GoogleOAuthProvider(),
            +            'facebook': FacebookOAuthProvider(),
            +            'github': GitHubOAuthProvider()
            +        }
            +    
            +    def authenticate(self, provider, token):
            +        return self.providers[provider].validate(token)
            """,
            "memory": {
                "task": "Fix login 500 error bug",
                "requirements": [
                    "Find root cause of 500 errors",
                    "Add error handling to prevent crashes",
                    "Add logging for debugging",
                ],
                "forbidden_patterns": ["new features", "refactoring", "OAuth"],
            },
        }

        result = command.execute(input_data)

        # Claude should detect scope creep
        assert result["success"] is True
        assert result["deviation_detected"] is True
        assert result["deviation_type"] in [
            "scope_creep",
            "off_topic",
            "over_engineering",
            "missing_requirement",
            "unnecessary_work",
        ]
        assert result["severity"] in ["medium", "high"]
        # Check for relevant keywords in recommendation
        recommendation_lower = result["recommendation"].lower()
        assert any(
            keyword in recommendation_lower
            for keyword in ["oauth", "scope", "authentication", "500", "error", "login"]
        )
        assert len(result.get("specific_issues", [])) > 0

    def test_real_over_engineering_detection(self):
        """Test actual Claude detection of over-engineering"""
        command = TaskCheckCommand(model="haiku")

        input_data = {
            "transcript": """
            User: Add a simple cache for user preferences
            Assistant: I'll implement a distributed caching system with Redis
            """,
            "diff": """
            +import redis
            +from abc import ABC, abstractmethod
            +
            +class CacheInterface(ABC):
            +    @abstractmethod
            +    def get(self, key): pass
            +    
            +    @abstractmethod  
            +    def set(self, key, value): pass
            +
            +class RedisCache(CacheInterface):
            +    def __init__(self):
            +        self.client = redis.Redis(
            +            host='localhost',
            +            port=6379,
            +            decode_responses=True
            +        )
            +
            +class CacheFactory:
            +    @staticmethod
            +    def create_cache(cache_type='redis'):
            +        if cache_type == 'redis':
            +            return RedisCache()
            +        # Add more cache types here
            """,
            "memory": {
                "task": "Add simple in-memory cache for user preferences",
                "requirements": [
                    "Cache should store up to 100 user preferences",
                    "Use dict or simple structure",
                ],
            },
        }

        result = command.execute(input_data)

        assert result["success"] is True
        assert result["deviation_detected"] is True
        assert result["deviation_type"] in ["over_engineering", "scope_creep"]
        assert (
            "simple" in result["recommendation"].lower()
            or "complex" in result["recommendation"].lower()
        )

    def test_real_off_topic_detection(self):
        """Test actual Claude detection of off-topic work"""
        command = TaskCheckCommand(model="haiku")

        input_data = {
            "transcript": """
            User: Update the README with installation instructions
            Assistant: I'll add a machine learning model for text generation
            """,
            "diff": """
            +import torch
            +import transformers
            +
            +class TextGenerator:
            +    def __init__(self):
            +        self.model = transformers.AutoModel.from_pretrained('gpt2')
            +        self.tokenizer = transformers.AutoTokenizer.from_pretrained('gpt2')
            """,
            "memory": {
                "task": "Update README.md with installation instructions",
                "requirements": [
                    "Add pip install command",
                    "Add usage examples",
                    "Add requirements list",
                ],
            },
        }

        result = command.execute(input_data)

        assert result["success"] is True
        assert result["deviation_detected"] is True
        assert result["deviation_type"] in ["off_topic", "over_engineering"]
        assert result["severity"] == "high"

    def test_real_aligned_work(self):
        """Test when work is properly aligned with task"""
        command = TaskCheckCommand(model="haiku")

        input_data = {
            "transcript": """
            User: Add input validation to the form
            Assistant: I'll add validation for required fields and email format
            """,
            "diff": """
            +def validate_form(data):
            +    errors = []
            +    
            +    if not data.get('name'):
            +        errors.append('Name is required')
            +    
            +    if not data.get('email'):
            +        errors.append('Email is required')
            +    elif '@' not in data['email']:
            +        errors.append('Invalid email format')
            +    
            +    return errors
            """,
            "memory": {
                "task": "Add input validation to user registration form",
                "requirements": ["Validate required fields", "Check email format"],
            },
        }

        result = command.execute(input_data)

        assert result["success"] is True
        assert result["deviation_detected"] is False
        assert result["severity"] == "low"
        assert "recommendation" in result

    def test_real_subtle_scope_creep(self):
        """Test detection of subtle scope creep"""
        command = TaskCheckCommand(model="haiku")

        input_data = {
            "transcript": """
            User: Fix the performance issue in the search function
            Assistant: I'll optimize the search and also add fuzzy matching
            """,
            "diff": """
            +from fuzzywuzzy import fuzz
            +
             def search(query, items):
            -    return [i for i in items if query in i]
            +    # Optimized search with fuzzy matching
            +    results = []
            +    for item in items:
            +        if query in item:
            +            results.append((item, 100))
            +        else:
            +            ratio = fuzz.ratio(query, item)
            +            if ratio > 80:
            +                results.append((item, ratio))
            +    return sorted(results, key=lambda x: x[1], reverse=True)
            """,
            "memory": {
                "task": "Fix performance issue in search function",
                "requirements": [
                    "Search is too slow with large datasets",
                    "Optimize the algorithm",
                ],
            },
        }

        result = command.execute(input_data)

        # Claude should recognize fuzzy matching as scope creep
        assert result["success"] is True
        # May or may not detect depending on Claude's judgment
        if result["deviation_detected"]:
            assert "fuzzy" in str(result).lower()

    def test_real_complex_scenario(self):
        """Test complex real-world scenario with multiple issues"""
        command = TaskCheckCommand(model="haiku")

        input_data = {
            "transcript": """
            User: The app crashes when users upload large images. Can you fix it?
            Assistant: I'll fix the crash and implement a complete image processing pipeline
            User: Just need the crash fixed
            Assistant: I'm adding image compression, format conversion, and thumbnail generation
            """,
            "diff": """
            +import PIL
            +from celery import Celery
            +import boto3
            +
            +app = Celery('tasks', broker='redis://localhost:6379')
            +s3 = boto3.client('s3')
            +
            +class ImageProcessor:
            +    def __init__(self):
            +        self.formats = ['webp', 'jpg', 'png', 'avif']
            +        self.sizes = [(150, 150), (300, 300), (600, 600)]
            +    
            +    @app.task
            +    def process_image(self, image_path):
            +        # Generate multiple formats and sizes
            +        for format in self.formats:
            +            for size in self.sizes:
            +                self.convert_and_resize(image_path, format, size)
            +        
            +        # Upload to S3
            +        self.upload_to_s3(image_path)
            +
            +# Original fix for crash would be just:
            +# if image.size > MAX_SIZE:
            +#     raise ValueError("Image too large")
            """,
            "memory": {
                "task": "Fix app crash when uploading large images",
                "requirements": [
                    "Add size validation before processing",
                    "Return proper error message to user",
                    "Prevent memory overflow",
                ],
                "forbidden_patterns": [
                    "new infrastructure",
                    "external services",
                    "major features",
                ],
            },
        }

        result = command.execute(input_data)

        assert result["success"] is True
        assert result["deviation_detected"] is True
        # Should detect multiple issues
        assert result["severity"] == "high"
        assert len(result.get("specific_issues", [])) >= 2

    @pytest.mark.slow
    def test_real_performance_with_large_input(self):
        """Test performance with large inputs"""
        command = TaskCheckCommand(model="haiku")

        # Generate large but realistic input
        large_diff = "\n".join(
            [
                f"+    def function_{i}():" + "\n" + f"+        return {i} * 2"
                for i in range(100)
            ]
        )

        input_data = {
            "transcript": "Add helper functions" * 50,  # Repeated text
            "diff": large_diff,
            "memory": {
                "task": "Add two helper functions for data validation",
                "requirements": [
                    "Add validate_email function",
                    "Add validate_phone function",
                ],
            },
        }

        import time

        start = time.time()
        result = command.execute(input_data)
        elapsed = time.time() - start

        assert result["success"] is True
        assert elapsed < 30  # Should complete within 30 seconds

        # Should detect adding 100 functions instead of 2
        assert result["deviation_detected"] is True

    def test_real_edge_case_empty_diff(self):
        """Test with empty diff but concerning transcript"""
        command = TaskCheckCommand(model="haiku")

        input_data = {
            "transcript": """
            User: Please implement the payment system
            Assistant: I'll need to research payment providers first
            User: We need Stripe integration
            Assistant: Let me look into PayPal, Square, and Stripe
            """,
            "diff": "",  # No actual changes yet
            "memory": {
                "task": "Integrate Stripe payment processing",
                "requirements": ["Use Stripe API", "Handle payment errors"],
            },
        }

        result = command.execute(input_data)

        assert result["success"] is True
        # Might detect scope expansion to multiple providers
        if result["deviation_detected"]:
            assert (
                "stripe" in result["recommendation"].lower()
                or "provider" in result["recommendation"].lower()
            )
