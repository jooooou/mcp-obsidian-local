import os
import sys
from dotenv import load_dotenv

# Add current dir to path
sys.path.append(os.getcwd())

from agent_v2 import AgentEngine, MODEL_PATH, N_CTX

def run_test():
    print("🧪 Starting Integration Test: Multi-Agent System")
    
    if not os.path.exists(MODEL_PATH):
        print("❌ Model not found. Skipping test.")
        return

    engine = AgentEngine(model_path=MODEL_PATH, n_ctx=N_CTX)
    
    # Test 1: Brain listing agents
    print("\n--- TEST 1: Brain Self-Reflection ---")
    response1 = engine.run_agent("brain", initial_task="Liste os agentes disponíveis e me diga quem é o especialista em criar arquivos.")
    print(f"\n✅ Result 1:\n{response1}")

    # Test 2: Delegation
    print("\n--- TEST 2: Brain -> Executor Delegation ---")
    task = "Use o executor para listar os arquivos no diretório atual (ls -la) e me mostre o resultado."
    response2 = engine.run_agent("brain", initial_task=task)
    print(f"\n✅ Result 2:\n{response2}")

if __name__ == "__main__":
    run_test()

