# Chain of Stepping Through a Debugger

if llm can execute code during `<think>...</think>`, then maybe it should execute a debugger on the code and have it step through the debugger while returning the context each step.

idk humans do this to understand the codebase. I love my vscode debugger. It helped me learn tinygrad.

Beauty of tinygrad is it's all python, so debugger can step/trace through EVERYTHIGN!!!!

Why doesn't this exist?

it's been months since I've had this idea. I'm definitely not alone.

If llm reasoning is using compute to flesh out intermediate steps/states, then such states can be directly retrieved from the debugger.

To run:

```bash
python -m pdb target_program.py
```

Inside the Pdb debugger, execute:

```python
import dump_pdb_context
dump_pdb_context.pdb_dump()
```
