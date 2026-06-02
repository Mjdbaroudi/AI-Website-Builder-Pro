from openai import OpenAI
from config import OPENAI_API_KEY

class AICodeAssistant:

    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def modify_code(self, user_request, current_code, file_type, model_name):

        prompt = f"""
You are a senior frontend engineer.

User request:
{user_request}

Current {file_type} code:
{current_code}

INSTRUCTIONS:
- Do NOT return full file.
- Return ONLY changes using this exact format:

---FIND---
<exact text to find>

---REPLACE---
<new replacement text>

Rules:
- FIND text must exist exactly in the provided code.
- Keep formatting precise.
- Only include the parts that must change.
- No explanations.
"""

        response = self.client.responses.create(
            model=model_name,
            input=prompt
        )

        return response.output_text.strip()