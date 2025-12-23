"""
Semantic Router using DeepSeek LLM for intelligent query routing and decomposition.
"""

import json
import re
from typing import Dict, List, Optional
from utils.deepseek_client import DeepSeekClient


ROUTER_SYSTEM_PROMPT = """You are an expert Query Router and Planner for an IPO analysis system.
Determine the best retrieval strategy for the user's question.

AVAILABLE SOURCES:
1. "kg": Knowledge Graph - Use for structure, entities, relationships, ownership, specific stats (e.g. "Who is CEO", "Subsidiaries", "Promoters").
2. "vector": Vector Search - Use for textual descriptions, policies, risk factors, definitions, clauses.
3. "hybrid": Combined - Use when the question needs BOTH entity data AND textual context (e.g. "Profile the CEO including his background").

OUTPUT RULES:
- Return ONLY a valid JSON object. No markdown, no explanations outside the JSON.
- Use this exact schema:

{
  "reasoning": "Brief explanation of your choice",
  "plan_type": "single" | "multi_step",
  "queries": [
    {
      "question": "The sub-question to ask",
      "source": "kg" | "vector" | "hybrid"
    }
  ]
}

EXAMPLES:

User: "Who is the CEO of PB Fintech?"
{
  "reasoning": "Simple entity lookup for a specific role.",
  "plan_type": "single",
  "queries": [{"question": "Who is the CEO of PB Fintech?", "source": "kg"}]
}

User: "What are the risk factors?"
{
  "reasoning": "Request for descriptive text content.",
  "plan_type": "single",
  "queries": [{"question": "What are the risk factors?", "source": "vector"}]
}

User: "Tell me about Yashish Dahiya."
{
  "reasoning": "Need both his role (KG) and biography/background (Vector).",
  "plan_type": "single",
  "queries": [{"question": "Tell me about Yashish Dahiya", "source": "hybrid"}]
}

User: "Compare the revenue growth with the inflation risks mentioned."
{
  "reasoning": "Requires comparing a statistic with descriptive text. Decompose.",
  "plan_type": "multi_step",
  "queries": [
    {"question": "What is the revenue growth?", "source": "kg"},
    {"question": "What are the inflation risks mentioned?", "source": "vector"}
  ]
}

User: "Who is the CEO and what are the main risks?"
{
  "reasoning": "Two distinct questions: entity lookup and text search.",
  "plan_type": "multi_step",
  "queries": [
    {"question": "Who is the CEO?", "source": "kg"},
    {"question": "What are the main risks?", "source": "vector"}
  ]
}

Now analyze the following question and return ONLY JSON:
"""


class SemanticRouter:
    """
    LLM-powered query router that classifies questions and optionally decomposes them.
    """

    def __init__(self):
        self.client = DeepSeekClient()

    def get_routing_plan(self, question: str) -> Dict:
        """
        Use LLM to analyze the question and return a routing plan.
        
        Returns:
            {
                "reasoning": str,
                "plan_type": "single" | "multi_step",
                "queries": [{"question": str, "source": "kg"|"vector"|"hybrid"}]
            }
        """
        user_prompt = f'User: "{question}"'
        
        try:
            # Call DeepSeek with strict output limits
            response = self.client.query(
                user_prompt,
                system_prompt=ROUTER_SYSTEM_PROMPT,
                max_tokens=300  # Keep response short
            )
            
            # Parse JSON from response
            plan = self._parse_json_response(response)
            
            if plan:
                print(f"🧠 SemanticRouter: Plan generated -> {plan['plan_type']} with {len(plan['queries'])} query(ies)")
                return plan
            else:
                # Fallback if parsing fails
                return self._fallback_plan(question)
                
        except Exception as e:
            print(f"⚠️ SemanticRouter Error: {e}")
            return self._fallback_plan(question)

    def _parse_json_response(self, response: str) -> Optional[Dict]:
        """Extract and parse JSON from LLM response."""
        try:
            # Try direct parse
            return json.loads(response.strip())
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON block in response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        return None

    def _fallback_plan(self, question: str) -> Dict:
        """Return a safe fallback plan (hybrid single query)."""
        print("⚠️ SemanticRouter: Using fallback (hybrid) plan")
        return {
            "reasoning": "Fallback: Could not parse LLM response",
            "plan_type": "single",
            "queries": [{"question": question, "source": "hybrid"}]
        }


# Simple test
if __name__ == "__main__":
    router = SemanticRouter()
    
    test_questions = [
        "Who is the CEO?",
        "What are the risk factors?",
        "Compare the revenue with the risks mentioned.",
    ]
    
    for q in test_questions:
        print(f"\n📝 Question: {q}")
        plan = router.get_routing_plan(q)
        print(f"   Plan: {json.dumps(plan, indent=2)}")
