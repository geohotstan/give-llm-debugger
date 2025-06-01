# Chain of Stepping Through a Debugger

if llm can execute code during `<think>...</think>`, then maybe it should execute a debugger on the code and have it step through the debugger while returning the context each step.

idk humans do this to understand the codebase. I love my vscode debugger. It helped me learn tinygrad.

Beauty of tinygrad is it's all python, so debugger can step/trace through EVERYTHIGN!!!!

Why doesn't this exist?

it's been months since I've had this idea. I'm definitely not alone.

If llm reasoning is using compute to flesh out intermediate steps/states, then such states can be directly retrieved from the debugger.

## Automated LLM Debugging

`debugger_chain.py` automates Python debugging by using an LLM to interact with `pdb`, analyze output, and iteratively work on a debugging task for `target_program.py`. It leverages `dump_pdb_context.py` to provide rich context to the LLM.

### Prerequisites

Python 3.8+ and the `requests` library are essential. For a complete list of dependencies, please refer to `pyproject.toml`.

### Configuration

Set the `OPENROUTER_API_KEY` environment variable to your OpenRouter API key:
`export OPENROUTER_API_KEY="your_key_here"`

### How to Run

Execute the script:
`python debugger_chain.py`

This will debug `target_program.py` by default. The script logs its operations, LLM interactions, and PDB outputs to the console. It aims to complete a predefined task and will output a final summary from the LLM.

### Manual Context Dumping

The `dump_pdb_context.py` script can also be used manually within a PDB session to print context:
`import dump_pdb_context; print(dump_pdb_context.pdb_get_context_json())`
