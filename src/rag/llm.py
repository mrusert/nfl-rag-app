"""
Ollama LLM Client for NFL RAG.

Provides an interface to Ollama for local LLM inference.
Supports streaming and non-streaming responses.
"""

import json
import requests
from typing import Optional, Generator, Any
from dataclasses import dataclass

from src.config import OLLAMA_HOST, OLLAMA_MODEL, DEBUG


@dataclass
class LLMResponse:
    """Response from the LLM."""
    content: str
    model: str
    total_duration_ms: Optional[float] = None
    prompt_eval_count: Optional[int] = None
    eval_count: Optional[int] = None
    
    @property
    def tokens_per_second(self) -> Optional[float]:
        """Calculate tokens per second if metrics available."""
        if self.eval_count and self.total_duration_ms:
            return self.eval_count / (self.total_duration_ms / 1000)
        return None


class OllamaLLM:
    """
    Client for Ollama local LLM.
    
    Ollama must be running locally (or accessible via network).
    Install: https://ollama.ai
    
    Default model: llama3.1 (good balance of quality and speed)
    
    Other recommended models:
    - llama3.1:8b - Fastest, good for testing
    - llama3.1:70b - Best quality, requires more RAM
    - mistral - Fast alternative
    - mixtral - Good quality, moderate speed
    """
    
    def __init__(
        self,
        host: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 120,
    ):
        """
        Initialize the Ollama client.
        
        Args:
            host: Ollama server URL (default: http://localhost:11434)
            model: Model name (default: llama3.1)
            timeout: Request timeout in seconds
        """
        self.host = (host or OLLAMA_HOST).rstrip("/")
        self.model = model or OLLAMA_MODEL
        self.timeout = timeout
        
        if DEBUG:
            print(f"Ollama LLM initialized")
            print(f"  Host: {self.host}")
            print(f"  Model: {self.model}")
    
    def _api_url(self, endpoint: str) -> str:
        """Build API URL."""
        return f"{self.host}/api/{endpoint}"
    
    def is_available(self) -> bool:
        """Check if Ollama server is available."""
        try:
            response = requests.get(
                f"{self.host}/api/tags",
                timeout=5,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def list_models(self) -> list[str]:
        """List available models."""
        try:
            response = requests.get(
                self._api_url("tags"),
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except requests.RequestException as e:
            if DEBUG:
                print(f"Error listing models: {e}")
            return []
    
    def model_exists(self, model_name: Optional[str] = None) -> bool:
        """Check if a specific model is available."""
        model = model_name or self.model
        models = self.list_models()
        # Check for exact match or base name match
        return any(
            m == model or m.startswith(f"{model}:")
            for m in models
        )
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[list[str]] = None,
    ) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt for context
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            stop: Stop sequences
            
        Returns:
            LLMResponse with generated content
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        
        if stop:
            payload["options"]["stop"] = stop
        
        try:
            response = requests.post(
                self._api_url("generate"),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            
            return LLMResponse(
                content=data.get("response", ""),
                model=data.get("model", self.model),
                total_duration_ms=data.get("total_duration", 0) / 1_000_000,  # ns to ms
                prompt_eval_count=data.get("prompt_eval_count"),
                eval_count=data.get("eval_count"),
            )
            
        except requests.RequestException as e:
            raise RuntimeError(f"Ollama request failed: {e}")
    
    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """
        Generate a streaming response from the LLM.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Yields:
            Chunks of generated text
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
            },
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        
        try:
            response = requests.post(
                self._api_url("generate"),
                json=payload,
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    if "response" in data:
                        yield data["response"]
                    if data.get("done", False):
                        break
                        
        except requests.RequestException as e:
            raise RuntimeError(f"Ollama streaming request failed: {e}")
    
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        Chat completion with message history.
        
        Args:
            messages: List of {"role": "user"|"assistant"|"system", "content": "..."}
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            LLMResponse with generated content
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        
        try:
            response = requests.post(
                self._api_url("chat"),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            
            return LLMResponse(
                content=data.get("message", {}).get("content", ""),
                model=data.get("model", self.model),
                total_duration_ms=data.get("total_duration", 0) / 1_000_000,
                prompt_eval_count=data.get("prompt_eval_count"),
                eval_count=data.get("eval_count"),
            )
            
        except requests.RequestException as e:
            raise RuntimeError(f"Ollama chat request failed: {e}")


# CLI for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Ollama LLM")
    parser.add_argument("--check", action="store_true", help="Check Ollama availability")
    parser.add_argument("--list", action="store_true", help="List available models")
    parser.add_argument("--prompt", type=str, help="Test prompt")
    parser.add_argument("--model", type=str, help="Model to use")
    parser.add_argument("--stream", action="store_true", help="Use streaming")
    
    args = parser.parse_args()
    
    llm = OllamaLLM(model=args.model) if args.model else OllamaLLM()
    
    if args.check:
        print("Checking Ollama availability...")
        if llm.is_available():
            print(f"✓ Ollama is running at {llm.host}")
            if llm.model_exists():
                print(f"✓ Model '{llm.model}' is available")
            else:
                print(f"✗ Model '{llm.model}' not found")
                print(f"  Run: ollama pull {llm.model}")
        else:
            print(f"✗ Ollama is not available at {llm.host}")
            print("  Make sure Ollama is running: ollama serve")
    
    elif args.list:
        print("Available models:")
        models = llm.list_models()
        if models:
            for m in models:
                print(f"  - {m}")
        else:
            print("  No models found (is Ollama running?)")
    
    elif args.prompt:
        print(f"Model: {llm.model}")
        print(f"Prompt: {args.prompt}")
        print("-" * 40)
        
        if args.stream:
            print("Response: ", end="", flush=True)
            for chunk in llm.generate_stream(args.prompt):
                print(chunk, end="", flush=True)
            print()
        else:
            response = llm.generate(args.prompt)
            print(f"Response: {response.content}")
            if response.tokens_per_second:
                print(f"\n[{response.eval_count} tokens, {response.tokens_per_second:.1f} tok/s]")
    
    else:
        parser.print_help()