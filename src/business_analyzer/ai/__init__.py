"""
AI package for Business Analyzer.

Multi-provider AI support for natural language to SQL conversion.
Supports: Grok (xAI), OpenAI, Anthropic Claude, Ollama (local)

Usage:
    from business_analyzer.ai import AIVanna, create_vanna_instance

    # Create instance with default provider (from AI_PROVIDER env var)
    vn = create_vanna_instance()

    # Or specify provider explicitly
    vn = create_vanna_instance(provider="openai")

Environment Variables:
    AI_PROVIDER: Provider selection (grok, openai, anthropic, ollama)
    GROK_API_KEY: xAI Grok API key
    OPENAI_API_KEY: OpenAI API key
    ANTHROPIC_API_KEY: Anthropic API key
    OLLAMA_HOST: Ollama server URL (default: http://localhost:11434)
    OLLAMA_MODEL: Ollama model name (default: mistral)
"""

# Base classes and configuration
from .base import (
    AIVanna,
    Config,
    SUPPORTED_PROVIDERS,
    DEFAULT_PROVIDER,
    require_env,
    get_env_or_test_default,
    retry_on_failure,
    create_ai_client,
)

# Formatting utilities
from .formatting import (
    format_number,
    format_dataframe,
    format_currency,
    format_percentage,
    format_integer,
    CURRENCY_COLUMNS,
    PERCENTAGE_COLUMNS,
)

# Training utilities
from .training import (
    train_on_schema,
    train_with_examples,
    get_default_training_examples,
    generate_training_data,
    full_training,
)

# Insights generation
from .insights import generate_insights

# Provider modules
from .providers import (
    GrokProvider,
    OpenAIProvider,
    AnthropicProvider,
    OllamaProvider,
)

__version__ = "2.0.1"

__all__ = [
    # Base
    "AIVanna",
    "Config",
    "SUPPORTED_PROVIDERS",
    "DEFAULT_PROVIDER",
    "require_env",
    "get_env_or_test_default",
    "retry_on_failure",
    "create_ai_client",
    # Formatting
    "format_number",
    "format_dataframe",
    "format_currency",
    "format_percentage",
    "format_integer",
    "CURRENCY_COLUMNS",
    "PERCENTAGE_COLUMNS",
    # Training
    "train_on_schema",
    "train_with_examples",
    "get_default_training_examples",
    "generate_training_data",
    "full_training",
    # Insights
    "generate_insights",
    # Providers
    "GrokProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    # Factory
    "create_vanna_instance",
]


def create_vanna_instance(provider: str = None) -> AIVanna:
    """
    Factory function to create a Vanna AI instance.

    Args:
        provider: AI provider name (grok, openai, anthropic, ollama).
                If None, uses AI_PROVIDER environment variable.

    Returns:
        Configured AIVanna instance

    Raises:
        ValueError: If provider is not supported
        SystemExit: If required environment variables are missing

    Example:
        >>> vn = create_vanna_instance()  # Uses AI_PROVIDER env var
        >>> vn = create_vanna_instance("openai")  # Explicit provider
    """
    if provider:
        import os

        os.environ["AI_PROVIDER"] = provider

    return AIVanna()
