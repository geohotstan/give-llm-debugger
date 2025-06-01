import subprocess
import sys
import logging
import time
import json
import select
import os # Already present, but good to ensure for OPENROUTER_API_KEY
from openrouter import OpenRouter # For LLM interaction

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global variable for OpenRouter API Key
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    logging.warning("OPENROUTER_API_KEY environment variable not set. LLM functionality will be disabled.")

# Placeholder for the actual model to use.
DEFAULT_LLM_MODEL = "openai/gpt-3.5-turbo"

def get_llm_command(prompt: str, model_name: str = None) -> str:
    """
    Gets a debugging command from an LLM via OpenRouter.

    Args:
        prompt: The prompt to send to the LLM, containing the PDB state.
        model_name: The specific model to use on OpenRouter. Defaults to DEFAULT_LLM_MODEL.

    Returns:
        The command suggested by the LLM, or an error message string starting with "error:".
    """
    if model_name is None:
        model_name = DEFAULT_LLM_MODEL

    if not OPENROUTER_API_KEY:
        logging.error("OpenRouter API key is not set. Cannot get LLM command.")
        return "error: OPENROUTER_API_KEY not set"

    try:
        client = OpenRouter(api_key=OPENROUTER_API_KEY)
        logging.info(f"Sending prompt to OpenRouter model {model_name}...")
        # Consider logging the prompt only at DEBUG level or if explicitly enabled,
        # as it can be verbose and might contain sensitive info depending on context.
        # logging.debug(f"Prompt for LLM: {prompt}")

        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
            # Add other parameters like temperature, max_tokens if needed
        )

        if response.choices and response.choices[0].message and response.choices[0].message.content:
            llm_response_content = response.choices[0].message.content
            command = llm_response_content.strip()
            logging.info(f"LLM suggested command: '{command}'")
            # Placeholder for more sophisticated command extraction if needed:
            # e.g., if LLM wraps command in ```pdb ... ```
            return command
        else:
            logging.error("LLM response was empty or malformed.")
            # Log the actual response structure if it's unexpected
            # logging.debug(f"Malformed LLM response: {response}")
            return "error: LLM response empty or malformed"

    except Exception as e:
        # Log the type of exception and message
        logging.error(f"Error calling OpenRouter API (model: {model_name}): {type(e).__name__} - {e}")
        # For debugging, one might want to log traceback:
        # import traceback
        # logging.error(traceback.format_exc())
        return f"error: API call failed ({type(e).__name__})"


def run_debugger_chain(
    target_script: str,
    task_description: str,
    max_steps: int = 10,
    llm_model: str = None
):
    if llm_model is None:
        llm_model = DEFAULT_LLM_MODEL

    final_summary = None # Initialize final_summary
    history = []

    pdb_interface = PDBInterface(target_script_path=target_script)
    pdb_interface.start_pdb() # This also consumes the initial PDB output/prompt

    if not pdb_interface.process:
        logging.error("Failed to start PDB. Aborting debugger chain.")
        return {"history": history, "final_summary": "Error: Failed to start PDB."}

    # Define the command to get context (used for 'dump' alias and initial context)
    # Using print() ensures the JSON is sent to stdout for capture.
    context_command = "import dump_pdb_context; print(dump_pdb_context.pdb_get_context_json())"

    # Log initial state after PDB start (already captured by start_pdb)
    logging.info("Initial PDB state after start:")
    logging.info(f"STDOUT: {pdb_interface.initial_output['stdout']}")
    logging.info(f"STDERR: {pdb_interface.initial_output['stderr']}")
    history.append({"step": 0, "pdb_command": "initial state (after start_pdb)", "stdout": pdb_interface.initial_output['stdout'], "stderr": pdb_interface.initial_output['stderr'], "llm_prompt": "N/A"})

    # It's often useful to get a full context dump right at the beginning
    # PDB usually stops at the first executable line of the script.
    logging.info("Attempting to get initial full context dump...")
    initial_dump_output = pdb_interface.send_command(context_command, timeout=15.0)
    current_pdb_output_stdout = initial_dump_output['stdout']
    current_pdb_output_stderr = initial_dump_output['stderr']
    history.append({"step": 0, "pdb_command": context_command, "llm_suggested_command": "initial dump", "stdout": current_pdb_output_stdout, "stderr": current_pdb_output_stderr, "llm_prompt": "N/A"})


    for i in range(1, max_steps + 1):
        logging.info(f"\n--- Debugger Chain Step {i}/{max_steps} ---")

        prompt_parts = [
            f"You are an AI assistant controlling a Python debugger (pdb) to solve the following task: '{task_description}'.",
            f"You are debugging the script: '{target_script}'.",
            "The PDB session is live. Below is the most recent output from PDB, including stdout and stderr.",
            "Your goal is to issue PDB commands to gather information and ultimately answer the task.",
            "Standard PDB commands are available (e.g., next, step, continue, print <var>, where, list, args, locals, up, down, until, return, quit).",
            "You can also use the special command 'dump'. This will execute: `import dump_pdb_context; print(dump_pdb_context.pdb_get_context_json())` to get a JSON dump of the current frame, locals, and globals.",
            "Based on the PDB output and the task, decide the *single* next PDB command to execute.",
            "If you believe you have enough information to answer the task, your command must be 'task_complete'.",
            "If you encounter an unrecoverable error, or determine you cannot proceed or solve the task with PDB, your command must be 'task_error'.",
            "IMPORTANT: Return ONLY the PDB command itself (e.g., 'next', 'print my_variable', 'dump', 'task_complete', 'task_error'). Do not include any explanations, conversational text, or markdown.",
            "\n--- PDB Output ---",
            "STDOUT:",
            "\n".join(current_pdb_output_stdout), # Use the latest stdout
            "STDERR:",
            "\n".join(current_pdb_output_stderr), # Use the latest stderr
            "\n--- End PDB Output ---",
            "\nTask: " + task_description,
            "\nWhat is the next PDB command? Return only the command:"
        ]
        current_prompt = "\n".join(prompt_parts)

        llm_command_suggestion = get_llm_command(current_prompt, model_name=llm_model)
        logging.info(f"LLM suggested PDB command: '{llm_command_suggestion}'")

        if llm_command_suggestion.startswith("error:"):
            logging.error(f"LLM failed to provide a command: {llm_command_suggestion}. Stopping.")
            final_summary = llm_command_suggestion # Store LLM error as summary
            history.append({"step": i, "type": "error", "content": final_summary, "llm_prompt": current_prompt})
            break

        actual_pdb_command = llm_command_suggestion.strip() # Use the stripped version

        if actual_pdb_command.lower() == "task_complete":
            logging.info("LLM indicates task complete. Requesting final summary...")
            summary_prompt_parts = [
                f"You have been operating a Python debugger (pdb) on the script '{target_script}' to work on the task: '{task_description}'.",
                "You have just issued the 'task_complete' command, indicating you have sufficient information to answer the task.",
                "Please provide a concise summary of your findings and the direct answer to the initial task.",
                "Focus on answering the original task based on your step-by-step analysis during the debugging session.",
                "Do not output any PDB commands or debugging instructions. Provide only the summary and answer."
            ]
            summary_prompt = "\n".join(summary_prompt_parts)

            final_summary = get_llm_command(summary_prompt, model_name=llm_model)
            logging.info(f"LLM Final Summary:\n{final_summary}")
            # Store the prompt for the summary as well for debugging
            history.append({"step": i, "type": "summary_request", "llm_suggested_command": actual_pdb_command, "llm_prompt": summary_prompt, "summary_result": final_summary})
            break
        elif actual_pdb_command.lower() == "task_error":
            logging.error("LLM indicates it cannot proceed or an error in its reasoning. Stopping.")
            final_summary = f"LLM indicated task_error. Last command suggested: '{actual_pdb_command}'"
            history.append({"step": i, "type": "error_signal", "llm_suggested_command": actual_pdb_command, "content": final_summary, "llm_prompt": current_prompt})
            break

        # Process the command (e.g., 'dump' alias)
        if actual_pdb_command.lower() == "dump":
            command_to_execute = context_command
            logging.info("Executing 'dump' alias as full context dump command.")
        else:
            command_to_execute = actual_pdb_command

        pdb_output = pdb_interface.send_command(command_to_execute)
        current_pdb_output_stdout = pdb_output['stdout']
        current_pdb_output_stderr = pdb_output['stderr']

        logging.info(f"PDB Output after '{command_to_execute}':\nSTDOUT:\n{current_pdb_output_stdout}\nSTDERR:\n{current_pdb_output_stderr}")
        history.append({
            "step": i,
            "pdb_command_executed": command_to_execute,
            "llm_suggested_command": llm_command_suggestion, # record what LLM originally said
            "stdout": current_pdb_output_stdout,
            "stderr": current_pdb_output_stderr,
            "llm_prompt": current_prompt # Save the prompt that led to this command
        })

        if pdb_interface.process is None or pdb_interface.process.poll() is not None:
            logging.warning("PDB process appears to have terminated unexpectedly during command execution. Stopping chain.")
            if not final_summary: # Only set if not already set by task_complete/error
                 final_summary = "Error: PDB process terminated unexpectedly."
            break

    pdb_interface.stop_pdb()
    logging.info("Debugger chain finished.")
    return {"history": history, "final_summary": final_summary}


class PDBInterface:
    PDB_PROMPT = "(Pdb) "
    # A short timeout for individual read operations to prevent indefinite blocking
    # if PDB doesn't send a prompt or if there's no more output.
    # The overall timeout for a command is handled by the calling methods.
    READ_POLL_TIMEOUT = 0.1


    def __init__(self, target_script_path: str):
        """
        Initializes the PDBInterface.

        Args:
            target_script_path: The path to the Python script to be debugged.
        """
        self.target_script_path = target_script_path
        self.process = None
        self.initial_output = {"stdout": [], "stderr": []}
        logging.info(f"PDBInterface initialized for target: {target_script_path}")

    def start_pdb(self, initial_timeout=5.0):
        """
        Starts PDB as a subprocess, controlling the target script.
        Consumes the initial PDB prompt.
        """
        if self.process is not None:
            logging.warning("PDB process is already running.")
            return

        command = [sys.executable, "-m", "pdb", self.target_script_path]
        try:
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1, # Line buffered
                # Set environment variable to use the custom .pdbrc for the 'dump' alias
                # Also add current directory to PYTHONPATH so PDB can find dump_pdb_context.py
                env={**os.environ, "PYTHONPATH": "." + os.pathsep + os.environ.get("PYTHONPATH", ""), "PYTHONBREAKPOINT": "pdb.set_trace"} if sys.version_info >= (3,7) else {**os.environ, "PYTHONPATH": "."}
            )
            logging.info(f"PDB started for {self.target_script_path} with PID: {self.process.pid}")
            # Consume initial output (welcome message, initial prompt)
            time.sleep(0.2) # Give PDB a moment to start and print the prompt
            self.initial_output = self.read_output(timeout=initial_timeout)
            logging.info(f"Initial PDB output consumed. stdout: {self.initial_output['stdout']}, stderr: {self.initial_output['stderr']}")

        except FileNotFoundError:
            logging.error(f"Error: The Python interpreter '{sys.executable}' or PDB module could not be found.")
            self.process = None
        except Exception as e:
            logging.error(f"Failed to start PDB: {e}")
            self.process = None

    def read_output(self, timeout=1.0):
        """
        Reads lines from stdout and stderr until the PDB prompt is encountered in stdout
        or a timeout occurs. Uses select for non-blocking reads.

        Args:
            timeout: Total time to wait for the PDB prompt.

        Returns:
            A dictionary {"stdout": list_of_stdout_lines, "stderr": list_of_stderr_lines}.
        """
        if not self.process or not self.process.stdout or not self.process.stderr:
            logging.warning("PDB process not available for reading output.")
            return {"stdout": [], "stderr": []}

        stdout_lines = []
        stderr_lines = []

        # Store the full lines, including the prompt if it's part of a line,
        # then filter the prompt out at the end.
        full_stdout_buffer = ""

        end_time = time.monotonic() + timeout

        while time.monotonic() < end_time:
            # Check if streams are ready for reading
            ready_to_read, _, _ = select.select(
                [self.process.stdout, self.process.stderr], [], [], self.READ_POLL_TIMEOUT
            )

            if not ready_to_read: # select timed out for this poll
                if self.PDB_PROMPT in full_stdout_buffer: # Check if prompt already received
                    break
                continue # continue to check overall timeout

            for stream in ready_to_read:
                try:
                    # Attempt to read a line. This might still block if a full line ending in \n
                    # isn't available, but select said it's readable.
                    # We are in text mode, so readline() should work.
                    line = stream.readline()
                    if not line: # EOF or stream closed
                        # This could indicate PDB crashed or exited.
                        logging.warning(f"Stream {stream.name} closed or returned EOF.")
                        # We should probably break or handle this more gracefully.
                        # For now, let's assume if stdout closes, PDB is done.
                        if stream is self.process.stdout:
                             # If we have some output ending with prompt, process it.
                            if self.PDB_PROMPT in full_stdout_buffer:
                                lines = full_stdout_buffer.splitlines()
                                if lines and lines[-1].strip() == self.PDB_PROMPT.strip():
                                    stdout_lines.extend(lines[:-1]) # Exclude prompt line
                                    full_stdout_buffer = "" # Clear buffer
                                elif lines: # prompt might be part of the last line
                                    last_line_idx = -1
                                    for i, l_ in enumerate(lines):
                                        if self.PDB_PROMPT in l_:
                                            last_line_idx = i
                                            break
                                    if last_line_idx != -1:
                                        processed_line = lines[last_line_idx].replace(self.PDB_PROMPT, "").strip()
                                        if processed_line: # if there was content before prompt
                                            stdout_lines.extend(lines[:last_line_idx])
                                            stdout_lines.append(processed_line)
                                        else: # prompt was alone or only whitespace around it
                                            stdout_lines.extend(lines[:last_line_idx])
                                        full_stdout_buffer = "" # Clear buffer
                            elif full_stdout_buffer: # process remaining buffer if any
                                stdout_lines.extend(full_stdout_buffer.splitlines())
                                full_stdout_buffer = ""

                            return {"stdout": stdout_lines, "stderr": stderr_lines} # PDB exited
                        continue # continue reading from other streams if any

                    if stream is self.process.stdout:
                        full_stdout_buffer += line
                        # Check if the prompt is now in the buffer
                        if self.PDB_PROMPT in full_stdout_buffer:
                            # Process the buffer up to and including the prompt
                            lines_before_prompt, prompt_part, rest_of_buffer = full_stdout_buffer.partition(self.PDB_PROMPT)

                            # Add lines before the prompt (if any)
                            if lines_before_prompt:
                                stdout_lines.extend(lines_before_prompt.splitlines())

                            # The prompt itself is consumed. If there's anything after the prompt in the buffer
                            # (unlikely for PDB but possible), it remains in full_stdout_buffer.
                            full_stdout_buffer = rest_of_buffer

                            # Prompt found, so we can return
                            return {"stdout": stdout_lines, "stderr": stderr_lines}
                    elif stream is self.process.stderr:
                        stderr_lines.append(line.strip())
                except Exception as e:
                    logging.error(f"Error reading from PDB stream: {e}")
                    # This might indicate a more serious issue.
                    # For now, we'll try to continue until the overall timeout.
                    if stream is self.process.stdout and self.PDB_PROMPT in full_stdout_buffer: # check buffer before bailing
                        pass # will be handled by outer loop or next iteration
                    else: # if not in buffer, and error, might be stuck
                        break # break inner loop
            else: # if inner loop completed (no break from error)
                if self.PDB_PROMPT in full_stdout_buffer: # Check if prompt was received in the meantime
                    break # break outer while loop
                continue # continue outer while loop
            break # if inner loop broke due to error reading stream

        # Timeout occurred or read error forced an exit from loop
        # Process any remaining stdout buffer content
        if full_stdout_buffer:
            # Check if the prompt is the last part of the buffer
            # This logic ensures that if the prompt is detected, it's stripped correctly.
            temp_lines = full_stdout_buffer.splitlines()
            processed_lines = []
            prompt_found_at_end = False
            for i, line_ in enumerate(temp_lines):
                if self.PDB_PROMPT in line_:
                    # This is the line containing the prompt.
                    # Take content before the prompt on this line.
                    content_before_prompt = line_.split(self.PDB_PROMPT, 1)[0].strip()
                    if content_before_prompt:
                        processed_lines.append(content_before_prompt)
                    prompt_found_at_end = True # Mark that we found and handled the prompt
                    # Any content after this line (if buffer contained more) is ignored as it's after prompt.
                    break
                else:
                    processed_lines.append(line_)
            stdout_lines.extend(processed_lines)
            if not prompt_found_at_end:
                 logging.warning(f"read_output timed out or exited. PDB prompt '{self.PDB_PROMPT}' not definitively detected in final stdout buffer: '{full_stdout_buffer[:100]}...'")


        return {"stdout": stdout_lines, "stderr": stderr_lines}


    def send_command(self, command: str, timeout=5.0):
        """
        Sends a command to PDB and reads its output.

        Args:
            command: The command string to send to PDB (without newline).
            timeout: Time to wait for PDB to process and respond.

        Returns:
            A dictionary {"stdout": list_of_stdout_lines, "stderr": list_of_stderr_lines}.
        Raises:
            RuntimeError: If PDB process is not running or stdin is closed.
        """
        if not self.process or not self.process.stdin or self.process.stdin.closed:
            logging.error("PDB process is not running or stdin is closed.")
            raise RuntimeError("PDB process is not running or stdin is closed.")

        try:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()
            logging.info(f"Sent command to PDB: {command}")
        except BrokenPipeError:
            logging.error("Failed to send command to PDB: stdin pipe is broken. PDB might have crashed.")
            # Attempt to re-check process status or clean up
            if self.process.poll() is not None: # Process has terminated
                logging.error(f"PDB process terminated with code: {self.process.returncode}")
                self.stop_pdb() # Clean up
            raise RuntimeError("PDB stdin pipe is broken. PDB might have crashed.") from None
        except Exception as e:
            logging.error(f"Error writing to PDB stdin: {e}")
            raise RuntimeError(f"Error writing to PDB stdin: {e}") from e

        # Give PDB a moment to process, especially for commands that change state
        # or produce output quickly. For very fast systems or simple commands,
        # this might not be strictly necessary, but it can help with reliability.
        time.sleep(0.1)

        return self.read_output(timeout=timeout)

    def get_context(self, dump_command: str = "dump", timeout=10.0):
        """
        Executes a command to dump PDB context (expected to be JSON) and parses it.

        Args:
            dump_command: The PDB command that outputs context as JSON.
                          Defaults to "dump", assuming an alias in .pdbrc.
            timeout: Timeout for sending the command and receiving output.

        Returns:
            A Python object parsed from JSON, or None if parsing fails or an error occurs.
        """
        logging.info(f"Requesting PDB context with command: '{dump_command}'")
        output = self.send_command(dump_command, timeout=timeout)

        if output["stderr"]:
            logging.warning(f"Stderr received while getting context: {output['stderr']}")

        if not output["stdout"]:
            logging.warning("No stdout received for context dump command.")
            return None

        # Join lines, as JSON output might be multi-line, though dump_pdb_context aims for single line.
        # However, PDB might break up long lines.
        json_string = "".join(output["stdout"]).strip()

        # It's possible the actual JSON is preceded by other output from PDB or the program.
        # We need to find the start of the JSON. A common pattern is it starts with '{'.
        # This is a heuristic. A more robust way would be for dump_pdb_context to use delimiters.
        first_brace = json_string.find('{')
        last_brace = json_string.rfind('}')

        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_string = json_string[first_brace : last_brace+1]
        else:
            logging.warning(f"Could not reliably find JSON object in output: {json_string[:200]}...")
            return None

        try:
            context = json.loads(json_string)
            logging.info("Successfully parsed PDB context.")
            return context
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON from PDB context dump: {e}")
            logging.error(f"Problematic JSON string (approx first 200 chars): '{json_string[:200]}'")
            if output['stderr']:
                 logging.error(f"Associated stderr: {output['stderr']}")
            return None
        except Exception as e: # Catch any other unexpected errors during parsing
            logging.error(f"An unexpected error occurred during JSON parsing of PDB context: {e}")
            logging.error(f"Problematic JSON string (approx first 200 chars): '{json_string[:200]}'")
            return None


    def stop_pdb(self, timeout=5.0):
        """
        Stops the PDB subprocess if it is running.
        """
        if self.process is None:
            # logging.info("PDB process is not running or already stopped.")
            return

        logging.info("Attempting to stop PDB...")

        # Check if process is still alive
        if self.process.poll() is not None:
            logging.info(f"PDB process already terminated with code {self.process.returncode}.")
        else:
            try:
                if self.process.stdin and not self.process.stdin.closed:
                    self.process.stdin.write("quit\n")
                    self.process.stdin.flush()
                    logging.info("Sent 'quit' command to PDB.")

                self.process.wait(timeout=timeout)
                logging.info(f"PDB process terminated gracefully with code {self.process.returncode}.")

            except subprocess.TimeoutExpired:
                logging.warning(f"PDB process did not terminate after 'quit' (timeout={timeout}s). Killing.")
                self.process.kill()
                try:
                    self.process.wait(timeout=5) # Wait for kill
                    logging.info("PDB process killed.")
                except subprocess.TimeoutExpired:
                    logging.error("PDB process failed to be killed.")
            except BrokenPipeError:
                logging.warning("PDB stdin pipe was already closed when trying to send 'quit'. Process might have terminated unexpectedly.")
            except Exception as e:
                logging.error(f"An error occurred while stopping PDB: {e}")

        # Close pipes and reset process
        try:
            if self.process.stdin: self.process.stdin.close()
        except Exception as e: logging.debug(f"Error closing stdin: {e}")
        try:
            if self.process.stdout: self.process.stdout.close()
        except Exception as e: logging.debug(f"Error closing stdout: {e}")
        try:
            if self.process.stderr: self.process.stderr.close()
        except Exception as e: logging.debug(f"Error closing stderr: {e}")

        self.process = None
        logging.info("PDB resources cleaned up.")


if __name__ == '__main__':
    # Ensure target_program.py exists or create a dummy one for testing
    # For this subtask, we assume target_program.py from the repo is used.
    # Make sure .pdbrc is in the same directory as target_program.py or in the home dir
    # and contains the 'dump' alias:
    # import dump_pdb_context
    # alias dump import dump_pdb_context; dump_pdb_context.pdb_dump_context()

    # For local testing, you might need to ensure .pdbrc is correctly set up,
    # dump_pdb_context.py is available, and OPENROUTER_API_KEY is set.

    target_script = "target_program.py"

    # Check if target_program.py exists, create a simple one if not, for robustness.
    try:
        with open(target_script, "r") as f:
            pass
        logging.info(f"Using existing '{target_script}' for testing.")
    except FileNotFoundError:
        logging.info(f"'{target_script}' not found. Creating a dummy version for testing.")
        with open(target_script, "w") as f:
            f.write("print('Dummy target program starting.')\n")
            f.write("name = 'TestDummy'\n")
            f.write("value = 42\n")
            f.write("# Set a breakpoint here for PDB to stop\n")
            f.write("breakpoint() # Requires Python 3.7+\n")
            f.write("print('Dummy target program finished.')\n")
            # Note: PDB will stop at breakpoint(). If not, it runs to completion quickly.
            # The .pdbrc needs `alias dump import dump_pdb_context; dump_pdb_context.pdb_dump_context(pdb)`
            # or the full command needs to be passed to get_context.

    pdb_interface = PDBInterface(target_script_path=target_script)

    logging.info("--- Test: Starting PDB ---")
    pdb_interface.start_pdb()

    if pdb_interface.process:
        logging.info("--- Test: PDB Process Started ---")
        logging.info(f"Initial PDB stdout: {pdb_interface.initial_output['stdout']}")
        logging.info(f"Initial PDB stderr: {pdb_interface.initial_output['stderr']}")

        # Example: Send 'next' command a few times if target_program has multiple lines
        # This depends on target_program.py having a breakpoint() or starting pdb in a way
        # that it stops at the first line.
        # Assuming .pdbrc has `alias dump ...` correctly defined
        # The default dump command in .pdbrc is `dump_pdb_context.pdb_dump_context(pdb)`
        # which requires pdb instance. Let's use the simpler one for direct call.
        # The .pdbrc alias should be:
        # alias dump import dump_pdb_context; print(dump_pdb_context.pdb_get_context_json())
        # Or we call the full command if .pdbrc isn't reliably sourced by Popen.

        # Let's assume target_program.py has a breakpoint() call.
        # PDB will stop there. We can then try to get context.

        # First, let's try to get context right after start (at the first breakpoint/stop)
        logging.info("--- Test: Getting Initial Context (at first stop) ---")
        # Try the full command if 'dump' alias might not be set up via .pdbrc in Popen
        # This requires dump_pdb_context.py to be in the PYTHONPATH or current dir.
        context_command = "import dump_pdb_context; print(dump_pdb_context.pdb_get_context_json())"

        context = pdb_interface.get_context(dump_command=context_command, timeout=15.0)
        if context:
            logging.info(f"Retrieved context (initial): {json.dumps(context, indent=2)}")
        else:
            logging.warning("Failed to retrieve initial context or context was empty.")

        # Example: Send a 'next' command
        logging.info("--- Test: Sending 'next' command ---")
        output_next = pdb_interface.send_command("next", timeout=5.0)
        logging.info(f"Output from 'next': stdout={output_next['stdout']}, stderr={output_next['stderr']}")

        # Get context again after 'next'
        logging.info("--- Test: Getting Context After 'next' ---")
        context_after_next = pdb_interface.get_context(dump_command=context_command, timeout=15.0)
        if context_after_next:
            logging.info(f"Retrieved context (after next): {json.dumps(context_after_next, indent=2)}")
        else:
            logging.warning("Failed to retrieve context after 'next' or context was empty.")


        # Example: Send 'continue' command to let the script finish (if it's not already done)
        logging.info("--- Test: Sending 'continue' command ---")
        output_continue = pdb_interface.send_command("c", timeout=10.0) # 'c' is alias for 'continue'
        logging.info(f"Output from 'continue': stdout={output_continue['stdout']}, stderr={output_continue['stderr']}")
        # After 'continue', PDB might exit or wait for another breakpoint.
        # If it exits, subsequent commands will fail. read_output might return empty if PDB already exited.

        logging.info("--- Test: Stopping PDB ---")
        pdb_interface.stop_pdb()
    else:
        logging.error("PDB process failed to start. Cannot run tests.")

    logging.info("--- Test: Stopping PDB again (should be no-op) ---")
    pdb_interface.stop_pdb()

    logging.info("Example usage finished.")

    # Cleanup the dummy script if it was created by this test run
    # (Be careful if target_script was pre-existing)
    # if target_script == "target_program.py" and "Dummy target program starting" in open(target_script).read(100): # Basic check
    #     import os
    #     try:
    #         os.remove(target_script)
    #         logging.info(f"Cleaned up dummy '{target_script}'.")
    #     except OSError as e:
    #         logging.warning(f"Could not clean up dummy script {target_script}: {e}")


    # --- Test LLM Command Functionality & Debugger Chain (Conditional) ---
    if OPENROUTER_API_KEY:
        logging.info("--- Test: LLM Command Functionality (single call) ---")
        test_prompt = (
            "You are an expert Python debugger using PDB. "
            "Your task is to suggest the single next PDB command to execute based on the provided PDB state. "
            "Return ONLY the PDB command and nothing else. For example, if you decide to step to the next line, return only 'next'. "
            "If you want to print the value of a variable named 'x', return 'p x'.\n\n"
            "Current PDB State:\n"
            "> /app/target_program.py(5)<module>()\n"
            "-> value = 'initial_value'\n"
            "(Pdb) \n" # Note: The (Pdb) prompt is part of the context given to LLM.
            "What is the next PDB command to type to inspect the current value of the variable 'value'?"
        )

        # Using DEFAULT_LLM_MODEL. You can override with a specific model for testing.
        # e.g., model_name="mistralai/mistral-7b-instruct" (if available and free)
        llm_cmd = get_llm_command(test_prompt)
        logging.info(f"LLM suggested command from test: '{llm_cmd}'")

        # You could add another test with a different prompt or model if desired.
        # test_prompt_2 = "..."
        # llm_cmd_2 = get_llm_command(test_prompt_2, model_name="google/gemma-7b-it") # Example
        # logging.info(f"LLM (other model) suggested command: '{llm_cmd_2}'")

        logging.info("\n--- Test: Full Debugger Chain ---")
        # Example task for the debugger chain
        task_for_llm = "The script initializes a variable 'value'. What is its value just before the script finishes? Also, identify the type of the variable 'name'."

        # Adjust task if using the dummy script created by the test setup
        # This check should be robust enough.
        is_dummy_script = False
        try:
            with open(target_script, "r") as f:
                if "Dummy target program starting" in f.read(100):
                    is_dummy_script = True
        except Exception: #FileNotFound or other issues
            pass # is_dummy_script remains False

        if is_dummy_script:
            task_for_llm = "The script initializes 'name' and 'value'. What are their final types and values right before the `breakpoint()` call? Explain how they are set."
            logging.info(f"Adjusted task for dummy script: {task_for_llm}")
        else:
            logging.info(f"Using standard task for '{target_script}': {task_for_llm}")


        chain_result = run_debugger_chain(
            target_script=target_script,
            task_description=task_for_llm,
            max_steps=10,
            llm_model=DEFAULT_LLM_MODEL
        )

        if chain_result:
            print("\n--- Chain Execution Result ---")
            if chain_result.get("final_summary"):
                summary_to_print = chain_result['final_summary']
                # Check if the summary itself is an error message from get_llm_command
                if summary_to_print.startswith("error:"):
                    print(f"LLM failed to generate a final summary: {summary_to_print}")
                else:
                    print(f"Final Summary from LLM:\n{summary_to_print}")
            else:
                print("No final summary was generated by the LLM (e.g., max_steps reached or error before summary).")

            # Optional: print full history (can be very verbose)
            # print("\nFull execution history:")
            # for entry_idx, entry in enumerate(chain_result.get("history", [])):
            #     print(f"  History Entry {entry_idx}: {entry.get('type', entry.get('pdb_command_executed', 'N/A'))}")
            #     # print(f"    LLM Prompt: {entry.get('llm_prompt', 'N/A')[:150]}...")
            #     # print(f"    STDOUT: {entry.get('stdout')}")
            #     # print(f"    STDERR: {entry.get('stderr')}")
            # if not chain_result.get("history"):
            #     print("  No history recorded.")
        else:
            print("Debugger chain did not return a result.")

    else:
        logging.warning("OPENROUTER_API_KEY not set in environment. Skipping LLM command functionality and debugger chain tests.")

    logging.info("--- Main execution block finished. ---")
