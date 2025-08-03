import anthropic

client = anthropic.Anthropic(
    # defaults to os.environ.get("ANTHROPIC_API_KEY")
    api_key="my_api_key",
)

# Replace placeholders like {{USER_PROMPT}} with real values,
# because the SDK does not support variables.
message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=20000,
    temperature=1,
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "You are an AI assistant tasked with analyzing a prompt submitted by a user. This prompt is intended for Claude to implement some code change. Your goal is to evaluate the prompt and, if possible, suggest improvements by asking clarifying questions.\n\nHere's the user's prompt:\n\n<user_prompt>\n{{USER_PROMPT}}\n</user_prompt>\n\nAnalyze the prompt carefully, considering the following aspects:\n1. Clarity: Is the prompt clear and specific about what needs to be done?\n2. Context: Does the prompt provide enough context about the existing code or system?\n3. Requirements: Are the requirements for the code change well-defined?\n4. Edge cases: Does the prompt address potential edge cases or error handling?\n5. Testing: Does the prompt mention any testing requirements or criteria for success?\n6. Performance: Are there any performance considerations mentioned?\n7. Compatibility: Does the prompt specify any compatibility requirements?\n\nBased on your analysis, if you identify areas where the prompt could be improved, formulate clarifying questions to ask the user. These questions should aim to:\n- Fill in missing information\n- Clarify ambiguous points\n- Encourage the user to consider important aspects they might have overlooked\n\nYour output should be structured as follows:\n1. A brief analysis of the prompt's strengths and weaknesses\n2. A list of clarifying questions, if any are needed\n3. Suggestions for improving the prompt based on your analysis\n\nHere's an example of how your output might look:\n\n<example>\nAnalysis:\nThe prompt clearly states the desired functionality but lacks context about the existing system. It doesn't mention error handling or testing requirements.\n\nClarifying Questions:\n1. What programming language and framework is the existing code written in?\n2. Are there any specific error cases we should handle?\n3. How should we validate the input data?\n4. Are there any performance requirements for this code change?\n5. How would you like the success of this implementation to be tested?\n\nSuggestions for Improvement:\n- Provide more context about the existing system and codebase\n- Specify any error handling requirements\n- Include criteria for testing and validating the code change\n- Consider mentioning any performance or compatibility requirements\n</example>\n\nRemember, your goal is to help the user create a more comprehensive and effective prompt for Claude to implement the code change. If the prompt is already well-structured and complete, you can acknowledge that and suggest minor improvements if applicable.\n\nYour final output should only include the analysis, clarifying questions (if any), and suggestions for improvement. Do not include any other text or explanations outside of these sections."
                }
            ]
        }
    ]
)
print(message.content)