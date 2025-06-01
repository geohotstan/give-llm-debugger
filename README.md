# LLM-Powered Python Debugger Chain

## Overview

This project explores the concept of using a Large Language Model (LLM) to automate Python debugging sessions. The core idea is to have an LLM interact with the Python Debugger (`pdb`) by programmatically sending commands and analyzing the output, aiming to solve a given debugging task or understand a piece of code.

The system, primarily driven by `debugger_chain.py`, allows an LLM to:
1.  Start a `pdb` session on a target Python script (`target_program.py` by default).
2.  Receive context from `pdb` (including stdout, stderr, and a JSON dump of variables using `dump_pdb_context.py`).
3.  Decide the next `pdb` command to execute based on the current context and a predefined task.
4.  Iteratively step through the code, analyze its state, and work towards completing the task.
5.  Provide a final summary of its findings when the task is deemed complete or an error occurs.

This project builds upon the initial idea of leveraging `pdb` to provide rich state information for LLM reasoning, evolving from manual context dumping to an automated debugging chain.

## Prerequisites

*   **Python**: Version 3.8 or higher is recommended.
*   **Dependencies**: The project's dependencies are listed in `pyproject.toml`. Key libraries required for `debugger_chain.py` include:
    *   `requests`: Used for making direct HTTP calls to the OpenRouter API.
    *   `python-dotenv`: (Currently listed in `pyproject.toml`. `debugger_chain.py` reads the API key directly from the environment via `os.environ.get`, so `python-dotenv` is not strictly required by the script itself unless used by other parts of a larger project structure to load `.env` files).
    *   All primary dependencies are listed in `pyproject.toml`. You can typically install necessary packages using a Python package manager that reads this file (e.g., `pip install .` from the project root if the project is structured as an installable package). For running `debugger_chain.py` directly, ensure at least `requests` is installed (`pip install requests`).

## Configuration

**Crucially, you must set the `OPENROUTER_API_KEY` environment variable.**

```bash
export OPENROUTER_API_KEY="your_openrouter_api_key_here"
```

The `debugger_chain.py` script will read this environment variable to authenticate with the OpenRouter API. If it's not set, the LLM interaction will fail.

You can also change the default LLM model used by modifying `DEFAULT_LLM_MODEL` in `debugger_chain.py`.

## How to Run

1.  Ensure all prerequisites are met and the `OPENROUTER_API_KEY` is set.
2.  Make sure `target_program.py` (or your desired target script) and `dump_pdb_context.py` are in the same directory.
3.  Execute the main script:

    ```bash
    python debugger_chain.py
    ```

## Expected Output/Behavior

When you run `debugger_chain.py`:
1.  It will initialize the `PDBInterface` and start `pdb` on `target_program.py`.
2.  It will then enter a loop, where in each step:
    *   The current PDB state (including a context dump) is formatted into a prompt for the LLM.
    *   The LLM suggests the next PDB command.
    *   The command is executed in `pdb`.
    *   The output is captured and fed back to the LLM in the next step.
3.  This process continues until a maximum number of steps is reached, the LLM issues a `task_complete` command, or an error occurs.
4.  If `task_complete` is issued, the script will prompt the LLM for a final summary of its findings related to the initial task.
5.  Logging messages will be printed to the console, showing the PDB commands, LLM suggestions, PDB output, and any summaries.

The default task in `debugger_chain.py`'s `if __name__ == '__main__':` block is to determine the value and type of variables in `target_program.py`.

## Components

*   **`debugger_chain.py`**:
    *   The main orchestrator of the debugging process.
    *   Contains the `run_debugger_chain` function that manages the interaction loop between PDB and the LLM.
    *   Includes `get_llm_command` to communicate with the OpenRouter API.
    *   Uses `PDBInterface` to manage the PDB subprocess.
*   **`PDBInterface` (class in `debugger_chain.py`)**:
    *   A wrapper around the `pdb` subprocess.
    *   Handles starting, stopping, sending commands to, and reading output (stdout/stderr) from `pdb`.
*   **`dump_pdb_context.py`**:
    *   A utility script designed to be imported and run within a `pdb` session.
    *   Its `pdb_get_context_json()` function (or older `pdb_dump_context(pdb_instance)`) collects information about the current frame, local variables, and global variables, then prints it as a JSON string to stdout. This JSON is captured by `PDBInterface` and fed to the LLM.
*   **LLM (Large Language Model)**:
    *   Accessed via the OpenRouter API.
    *   Receives prompts containing the debugging task and current PDB state.
    *   Suggests the next PDB command to execute.
    *   Provides a final summary upon task completion.
*   **`target_program.py`**:
    *   The Python script that is being debugged by `pdb` under the control of the LLM. This is the program you want the LLM to analyze or debug.

## Manual Context Dumping (Original Proof of Concept)

The `dump_pdb_context.py` script can also be used manually, which was the initial method for exploring this idea:

1.  Start `pdb` on your target script:
    ```bash
    python -m pdb your_script_to_debug.py
    ```
2.  Inside the Pdb debugger, execute the following to print the context as JSON:
    ```python
    import dump_pdb_context; print(dump_pdb_context.pdb_get_context_json())
    ```
    Or, if you have the `pdb` instance available (e.g. in `.pdbrc` aliases):
    ```python
    # In .pdbrc:
    # import dump_pdb_context
    # alias dump import dump_pdb_context; dump_pdb_context.pdb_dump_context(pdb)
    # Then in PDB:
    # (Pdb) dump
    ```
This manual method is still useful for understanding the kind of context provided to the LLM or for quick local debugging checks.
