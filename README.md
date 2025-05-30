can someone please test-time RL a debugger into the LLM, pretty please?

it's been months since I've had this idea. I'm definitely not alone.

if llm can execute code during `<think>...</think>`, then maybe it should execute a debugger on the code and have it step through the debugger while returning the context each step.

idk humans do this to understand the codebase. I love my vscode debugger. It helped me learn tinygrad.

Beauty of tinygrad is it's all python, so debugger can step/trace through EVERYTHIGN!!!!

Why doesn't this exist?

To run:

```bash
python -m pdb target_program.py
```

Inside the Pdb debugger, execute:

```python
import dump_pdb_context
dump_pdb_context.pdb_dump()
```
