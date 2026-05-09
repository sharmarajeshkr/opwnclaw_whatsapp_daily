"""
app/agents/ollama/
------------------
NEW FOLDER — Ollama-specific agent wrappers.

Each class in here subclasses the original agent and overrides ONLY the
generate_response call to use OllamaProvider instead of LLMProvider.

Original agent files are NOT modified.

Recommended model assignments based on task type:
  - InterviewAgent / DeepDiveAgent  →  OllamaInterviewAgent / OllamaDeepDiveAgent  (llama3.1:8b)
  - CodingAgent                     →  OllamaCodingAgent    (qwen2.5-coder:7b or codellama)
  - CuratorAgent                    →  OllamaCuratorAgent   (phi3:mini or llama3.1:8b)
  - ScoringAgent                    →  keep as-is (cloud) for accuracy, or use OllamaScoringAgent
"""
