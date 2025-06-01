import os
import requests
import logging
import json

# Basic logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Read API key from environment variable
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    logging.error("OPENROUTER_API_KEY environment variable not set.")
    # It's good practice to raise an error or handle this case appropriately
    # For now, we'll let it proceed, but API calls will fail.
    # raise ValueError("OPENROUTER_API_KEY environment variable not set.")

# Updated HTTP Referer and X-Title for reasoning_chain.py
# Replace 'your-repo' with the actual repository name or a generic placeholder
HTTP_REFERER = "https://github.com/your-repo/reasoning-chain-experiment"
X_TITLE = "Reasoning Chain Experiment"

def query_openrouter_llm(prompt: str, model_name: str, system_prompt: str = None) -> str:
    """
    Queries an LLM using the OpenRouter API.

    Args:
        prompt: The user's prompt.
        model_name: The name of the model to use (e.g., "openai/gpt-3.5-turbo").
        system_prompt: An optional system prompt to guide the LLM's behavior.

    Returns:
        The LLM's response content as a string, or an error message string.
    """
    if not OPENROUTER_API_KEY:
        logging.error("API key not configured. Cannot make API call.")
        return "error: API key not configured."

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "Referer": HTTP_REFERER, # Using Referer, not HTTP-Referer as per OpenRouter docs
        "X-Title": X_TITLE,
    }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model_name,
        "messages": messages,
    }

    logging.info(f"Sending request to OpenRouter: model={model_name}, prompt (first 50 chars)='{prompt[:50]}...'")

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60  # Adding a timeout for the request
        )
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)

        response_json = response.json()
        logging.info("Successfully received response from OpenRouter.")

        if response_json.get("choices") and \
           isinstance(response_json["choices"], list) and \
           len(response_json["choices"]) > 0 and \
           response_json["choices"][0].get("message") and \
           isinstance(response_json["choices"][0]["message"], dict) and \
           response_json["choices"][0]["message"].get("content"):
            content = response_json["choices"][0]["message"]["content"]
            return str(content)
        else:
            logging.error(f"Unexpected response structure: {response_json}")
            return "error: Unexpected response structure from API."

    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error occurred: {e} - Response: {e.response.text if e.response else 'No response text'}")
        return f"error: API call failed with HTTP status {e.response.status_code if e.response else 'Unknown'}."
    except requests.exceptions.Timeout:
        logging.error("Request timed out.")
        return "error: API call timed out."
    except requests.exceptions.RequestException as e:
        logging.error(f"An error occurred during the API request: {e}")
        return f"error: API call failed due to a network or request issue: {e}"
    except json.JSONDecodeError:
        logging.error("Failed to decode JSON response.")
        return "error: Failed to decode JSON response from API."
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return f"error: An unexpected error occurred: {e}"

def ask_reasoning_model(question: str, reasoning_model_name: str) -> str:
    """
    Asks the reasoning model a question and extracts its reasoning steps.

    Args:
        question: The user's question.
        reasoning_model_name: The name of the reasoning LLM to use.

    Returns:
        The extracted reasoning string, or an error message.
    """
    system_prompt = (
        "You are a helpful AI assistant. Your task is to answer the user's question. "
        "Please provide your reasoning steps clearly enclosed within <reasoning> and </reasoning> tags, "
        "followed by the final answer. For example: "
        "<reasoning>First, I considered X. Then, I analyzed Y. This led me to conclude Z.</reasoning>"
        "Final Answer: Z."
    )

    logging.info(f"Asking reasoning model '{reasoning_model_name}' the question: '{question[:50]}...'")
    response = query_openrouter_llm(
        prompt=question,
        model_name=reasoning_model_name,
        system_prompt=system_prompt
    )

    if response.startswith("error:"):
        logging.error(f"Error from query_openrouter_llm: {response}")
        return response

    try:
        start_tag = "<reasoning>"
        end_tag = "</reasoning>"
        start_index = response.find(start_tag)
        end_index = response.find(end_tag)

        if start_index != -1 and end_index != -1 and start_index < end_index:
            reasoning_text = response[start_index + len(start_tag):end_index].strip()
            if reasoning_text:
                logging.info(f"Extracted reasoning: '{reasoning_text[:100]}...'")
                return reasoning_text
            else:
                logging.warning(f"Reasoning tags found, but content is empty. Response: {response}")
                return "error: reasoning tags found but content is empty"
        else:
            logging.warning(f"Reasoning tags not found in response: {response}")
            return "error: reasoning tags not found or malformed in response"
    except Exception as e:
        logging.error(f"Error parsing reasoning from response: {e}. Response was: {response}")
        return f"error: failed to parse reasoning from response: {e}"

def ask_non_reasoning_model(original_question: str, extracted_reasoning: str, non_reasoning_model_name: str) -> str:
    """
    Asks a non-reasoning model to answer a question based on provided reasoning.

    Args:
        original_question: The original question posed to the reasoning model.
        extracted_reasoning: The reasoning steps extracted from the reasoning model's response.
        non_reasoning_model_name: The name of the non-reasoning LLM to use.

    Returns:
        The non-reasoning model's answer, or an error message.
    """
    prompt = (
        f"Based *only* on the following reasoning, please answer the original question.\n"
        f"Original Question: '{original_question}'\n"
        f"Provided Reasoning:\n"
        f"---\n"
        f"{extracted_reasoning}\n"
        f"---\n"
        f"Your Answer:"
    )

    logging.info(f"Asking non-reasoning model '{non_reasoning_model_name}' based on extracted reasoning. Question: '{original_question[:50]}...'")
    response = query_openrouter_llm(
        prompt=prompt,
        model_name=non_reasoning_model_name
        # No specific system prompt here, main instruction is in the user prompt.
    )

    if response.startswith("error:"):
        logging.error(f"Error from query_openrouter_llm for non-reasoning model: {response}")
        return response

    logging.info(f"Received answer from non-reasoning model: '{response[:100]}...'")
    return response

if __name__ == '__main__':
    # The basicConfig for logging is already at the top level of the script.
    # No need to reconfigure it here unless for specific __main__ level adjustments.

    if not OPENROUTER_API_KEY:
        logging.error("OPENROUTER_API_KEY environment variable not set. This script requires it to run.")
        print("Error: OPENROUTER_API_KEY not set. Please set it as an environment variable to run the examples.")
        print("Example: export OPENROUTER_API_KEY=\"your_actual_api_key_here\"")
        # import sys # Consider adding sys.exit(1) if this script is meant to be a CLI tool primarily
        # sys.exit(1)
    else:
        logging.info("OPENROUTER_API_KEY found. Proceeding with example execution.")

        # --- Configuration for Models ---
        # These are placeholder model names. You might need to change them based on availability
        # on OpenRouter, your account's access, or your specific needs.
        # For reasoning, a model good at instruction following and step-by-step thinking is ideal.
        reasoning_model_name = "mistralai/mistral-7b-instruct-v0.2"  # Or "openai/gpt-3.5-turbo", "anthropic/claude-3-haiku"
        # For the non-reasoning step (answering based on provided text),
        # a variety of models can work, potentially even smaller/faster ones.
        non_reasoning_model_name = "google/gemma-7b-it" # Or "mistralai/mistral-7b-instruct-v0.2", "openai/gpt-3.5-turbo"

        # --- Example Question ---
        # A question that benefits from explicit reasoning steps.
        original_question = (
            "A customer has been with our company for 5 years and has a GOLD loyalty status. "
            "According to company policy Document X, customers with GOLD status get a 15% discount. "
            "However, if they have GOLD status AND have been with the company for more than 3 years, "
            "they are eligible for a 20% discount. "
            "Which discount percentage should this customer receive?"
        )
        # original_question = "If a train leaves City A at 10:00 AM traveling at 60 mph, and City B is 180 miles away, what time will it arrive in City B?"

        print("======================================================================")
        print("Starting Reasoning Chain Example")
        print("======================================================================")
        print(f"Original Question:\n{original_question}\n")

        # 1. Get reasoning from the reasoning model
        print(f"Asking reasoning model ({reasoning_model_name}) for reasoning steps...")
        logging.info(f"Requesting reasoning for: \"{original_question[:100]}...\" from {reasoning_model_name}")
        extracted_reasoning = ask_reasoning_model(original_question, reasoning_model_name)

        if extracted_reasoning.startswith("error:"):
            print(f"--- Error getting reasoning from {reasoning_model_name} ---")
            print(extracted_reasoning)
            print("--- End of Error ---")
            logging.error(f"Failed to get reasoning: {extracted_reasoning}")
        else:
            print(f"--- Extracted Reasoning from {reasoning_model_name} ---")
            print(extracted_reasoning)
            print("--- End of Reasoning ---\n")
            logging.info(f"Successfully extracted reasoning: \"{extracted_reasoning[:200]}...\"")

            # 2. Get final answer from the non-reasoning model based on the extracted reasoning
            print(f"Asking non-reasoning model ({non_reasoning_model_name}) for an answer based on the reasoning...")
            logging.info(f"Requesting final answer from {non_reasoning_model_name} using the extracted reasoning.")
            final_answer = ask_non_reasoning_model(
                original_question,
                extracted_reasoning,
                non_reasoning_model_name
            )

            if final_answer.startswith("error:"):
                print(f"--- Error getting final answer from {non_reasoning_model_name} ---")
                print(final_answer)
                print("--- End of Error ---")
                logging.error(f"Failed to get final answer: {final_answer}")
            else:
                print(f"--- Final Answer from {non_reasoning_model_name} (based *only* on provided reasoning) ---")
                print(final_answer)
                print("--- End of Final Answer ---")
                logging.info(f"Successfully obtained final answer: \"{final_answer[:200]}...\"")

        print("\n======================================================================")
        print("Reasoning Chain Example Complete")
        print("======================================================================")

    print("\nreasoning_chain.py execution finished.")
