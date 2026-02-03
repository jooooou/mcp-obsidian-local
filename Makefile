# Makefile

# Instala tudo garantindo suporte a GPU para o llama.cpp
install:
	@echo "Installing dependencies with CUDA support..."
	uv sync
	CMAKE_ARGS="-DGGML_CUDA=on" uv pip install llama-cpp-python --no-binary llama-cpp-python --force-reinstall

# Atalho para rodar o agente
agent:
	uv run python agent.py
