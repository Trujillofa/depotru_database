#!/bin/bash
# scripts/install-agents.sh
# Install multi-agent CLI tools

echo "🤖 Installing AI Agent Tools..."

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ npm not found. Please install Node.js first:"
    echo "   https://nodejs.org/"
    exit 1
fi

# Install Claude Code (Anthropic)
echo "📦 Installing Claude Code..."
npm install -g @anthropic-ai/claude-code

# Install Gemini CLI (Google)
echo "📦 Installing Gemini CLI..."
npm install -g @google/gemini-cli

# Optional: Install Aider (pair programming)
echo "📦 Installing Aider (optional)..."
pip install aider-chat

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "1. Authenticate Claude Code: claude login"
echo "2. Authenticate Gemini CLI: gemini login"
echo "3. Configure agents: cp .agents/config.template.yml .agents/config.yml"
echo "4. Read the guide: cat docs/MULTI_AGENT_SETUP.md"
