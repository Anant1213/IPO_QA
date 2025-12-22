"""
DeepSeek API Client for Knowledge Graph Extraction
Supports DeepSeek R1 reasoning model with fallback to local models
"""

import requests
import json
from typing import Dict, List, Optional
from utils.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    DEEPSEEK_TEMPERATURE,
    OLLAMA_BASE_URL,
    USE_LOCAL_DEEPSEEK
)


class DeepSeekClient:
    """Client for DeepSeek API with local model support"""
    
    def __init__(self, use_local_fallback=True):
        self.api_key = DEEPSEEK_API_KEY
        self.base_url = DEEPSEEK_BASE_URL
        self.model = DEEPSEEK_MODEL
        self.temperature = DEEPSEEK_TEMPERATURE
        self.use_local = USE_LOCAL_DEEPSEEK or use_local_fallback
        
    def extract_with_reasoning(
        self, 
        prompt: str, 
        system_prompt: str = None,
        max_tokens: int = 4096
    ) -> Dict:
        """
        Call DeepSeek model (local or API) with reasoning mode enabled
        
        Args:
            prompt: User prompt for extraction
            system_prompt: System instructions
            max_tokens: Maximum tokens to generate
            
        Returns:
            Dict with 'reasoning' and 'output' keys
        """
        # Use local model if configured
        if self.use_local:
            return self._call_local_model(prompt, system_prompt, max_tokens)
        
        try:
            return self._call_deepseek(prompt, system_prompt, max_tokens)
        except Exception as e:
            print(f"DeepSeek API failed: {e}. Falling back to local model...")
            return self._call_local_model(prompt, system_prompt, max_tokens, json_mode=True)

    def query(
        self, 
        prompt: str, 
        system_prompt: str = None,
        max_tokens: int = 4096
    ) -> str:
        """
        General query method for text generation (non-JSON)
        """
        if self.use_local:
            result = self._call_local_model(prompt, system_prompt, max_tokens, json_mode=False)
            return result.get('output', '')
        
        # Fallback to API if implemented, or just use local
        return self._call_deepseek(prompt, system_prompt, max_tokens, json_mode=False).get('output', '')
    
    def _call_deepseek(self, prompt: str, system_prompt: str, max_tokens: int, json_mode: bool = True) -> Dict:
        """Call DeepSeek API"""
        url = f"{self.base_url}/v1/chat/completions"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens
        }
        
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        # Parse JSON response
        try:
            if json_mode:
                parsed = json.loads(content)
                return {
                    'reasoning': parsed.get('reasoning', ''),
                    'output': parsed.get('output', parsed)
                }
            else:
                return {'output': content}
        except json.JSONDecodeError:
            # If not JSON, return raw content
            return {
                'reasoning': '',
                'output': content
            }
    
    def _call_local_model(self, prompt: str, system_prompt: str, max_tokens: int, json_mode: bool = True) -> Dict:
        """Call local DeepSeek model via Ollama"""
        url = f"{self.base_url}/api/generate"
        
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        
        payload = {
            "model": self.model,  # Use configured DeepSeek model
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": max_tokens
            }
        }
        
        if json_mode:
             payload["format"] = "json"
        
        print(f"Using local model: {self.model}")
        
        try:
            response = requests.post(url, json=payload, timeout=300)  # 5 minutes timeout for R1
            response.raise_for_status()
        except requests.exceptions.Timeout:
            print("⚠️  Model timeout - DeepSeek R1 is thinking too long. Trying simpler extraction...")
            # Try again with lower max_tokens
            payload['options']['num_predict'] = 2048
            response = requests.post(url, json=payload, timeout=180)
            response.raise_for_status()
        
        result = response.json()
        content = result.get('response', '')
        
        # Extract reasoning from <think> tags if present
        reasoning = ''
        if '<think>' in content and '</think>' in content:
            think_start = content.find('<think>')
            think_end = content.find('</think>')
            reasoning = content[think_start+7:think_end].strip()
            # Remove thinking section from content
            content = content[:think_start] + content[think_end+8:]
        
        # Extract JSON from code blocks if present
        if '```json' in content:
            json_start = content.find('```json') + 7
            json_end = content.find('```', json_start)
            content = content[json_start:json_end].strip()
        elif '```' in content:
            # Handle generic code blocks
            code_start = content.find('```') + 3
            code_end = content.find('```', code_start)
            content = content[code_start:code_end].strip()
        
        content = content.strip()
        
        # Try to parse JSON
        try:
            if json_mode:
                parsed = json.loads(content)
                return {
                    'reasoning': reasoning or 'Local DeepSeek model - reasoning integrated',
                    'output': parsed
                }
            else:
                 return {
                    'reasoning': reasoning,
                    'output': content
                }
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {e}")
            print(f"Content: {content[:500]}...")
            return {
                'reasoning': reasoning or 'Local DeepSeek model - reasoning integrated',
                'output': content
            }
    
    def batch_extract(
        self,
        prompts: List[str],
        system_prompt: str = None,
        max_concurrent: int = 3
    ) -> List[Dict]:
        """
        Process multiple extraction prompts in batches
        
        Args:
            prompts: List of extraction prompts
            system_prompt: Shared system prompt
            max_concurrent: Maximum concurrent requests
            
        Returns:
            List of extraction results
        """
        results = []
        
        # Simple sequential processing for now
        # Can add concurrent.futures for parallelization later
        for i, prompt in enumerate(prompts):
            print(f"Processing chunk {i+1}/{len(prompts)}...")
            result = self.extract_with_reasoning(prompt, system_prompt)
            results.append(result)
        
        return results

    def get_embedding(self, text: str) -> List[float]:
        """
        Get vector embedding for text using Ollama
        """
        url = f"{self.base_url}/api/embeddings"
        
        payload = {
            "model": "nomic-embed-text",  # Use a good embedding model if available, or fallback
            "prompt": text
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 404:
                # Fallback to llama3 if nomic-embed-text not found
                payload["model"] = self.model
                response = requests.post(url, json=payload, timeout=30)
                
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            print(f"Embedding failed: {e}")
            return []
