import streamlit as st
import requests
import json

# --- Configuration & Constants ---
API_BASE_URL_TEMPLATE = "https://bot.insightstream.ru/agent/{assistant_id}/v1/chat/completions"

# --- Helper Function to Call API ---
def get_assistant_response(api_token: str, assistant_id: str, messages_history: list):
    """
    Calls the RAG LLM bot API.
    """
    if not api_token or not assistant_id:
        return None, None, "API Token or Assistant ID is missing."

    url = API_BASE_URL_TEMPLATE.format(assistant_id=assistant_id)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token}"
    }
    # The API expects a list of messages with "role" and "content"
    # We need to ensure our stored messages (which might include 'sources')
    # are formatted correctly for the API.
    api_payload_messages = []
    for msg in messages_history:
        api_payload_messages.append({"role": msg["role"], "content": msg["content"]})

    payload = {
        "messages": api_payload_messages,
        "stream": False # As per your example
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=120) # Added timeout
        response.raise_for_status() # Will raise an HTTPError for bad responses (4XX or 5XX)
        
        data = response.json()
        
        assistant_content = data.get("choices", [{}])[0].get("message", {}).get("content")
        sources = data.get("sources")
        
        if not assistant_content:
            return None, None, "Received an empty response from the assistant."
            
        return assistant_content, sources, None

    except requests.exceptions.HTTPError as http_err:
        error_detail = f"HTTP error occurred: {http_err}. Response: {response.text}"
        st.error(f"API Error: {error_detail}") # Show detailed error in UI
        return None, None, error_detail
    except requests.exceptions.RequestException as req_err:
        st.error(f"Request error occurred: {req_err}")
        return None, None, f"Request error: {req_err}"
    except json.JSONDecodeError:
        st.error(f"Failed to decode JSON response: {response.text}")
        return None, None, f"JSON decode error. Response: {response.text}"
    except (IndexError, KeyError) as e:
        st.error(f"Unexpected API response structure: {e}. Response: {data if 'data' in locals() else 'N/A'}")
        return None, None, f"Unexpected API response structure: {e}"


# --- Streamlit App ---
st.set_page_config(page_title="RAG LLM Chat", layout="wide", initial_sidebar_state="expanded")
st.title("💬 Minimalistic RAG LLM Chatbot")

# Initialize session state variables
if "messages" not in st.session_state:
    st.session_state.messages = [] # Stores chat history: [{"role": "user/assistant", "content": "...", "sources": [...]}]
if "api_token" not in st.session_state:
    st.session_state.api_token = ""
if "assistant_id" not in st.session_state:
    st.session_state.assistant_id = ""
if "config_error" not in st.session_state:
    st.session_state.config_error = ""


# --- Sidebar for Configuration ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Use previously entered values from session_state or empty strings
    api_token_input = st.text_input(
        "API Token", 
        value=st.session_state.api_token, 
        type="password",
        key="api_token_input_key" # Unique key for input widget
    )
    assistant_id_input = st.text_input(
        "Assistant Name", 
        value=st.session_state.assistant_id,
        key="assistant_id_input_key" # Unique key for input widget
    )

    # Update session state when inputs change
    if api_token_input != st.session_state.api_token:
        st.session_state.api_token = api_token_input
        st.session_state.config_error = "" # Clear error if user is typing
        
    if assistant_id_input != st.session_state.assistant_id:
        st.session_state.assistant_id = assistant_id_input
        st.session_state.config_error = "" # Clear error if user is typing

    if st.button("🔄 Refresh All & Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.api_token = ""
        st.session_state.assistant_id = ""
        st.session_state.config_error = ""
        # To make text_input fields update, we need to clear their specific keys or rerun
        st.session_state.api_token_input_key = "" 
        st.session_state.assistant_id_input_key = ""
        st.rerun()

    if st.session_state.config_error:
        st.error(st.session_state.config_error)

    st.markdown("---")
    st.markdown("Enter your API token and the specific assistant name you want to chat with.")
    st.markdown("The chat history will be cleared if you refresh.")

# --- Display Chat Messages ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "sources" in message and message["sources"]:
            with st.expander("📚 Sources", expanded=False):
                for i, source in enumerate(message["sources"]):
                    doc_name = source.get("source_document_name", "Unknown Document")
                    doc_loc = source.get("source_location", "#")
                    st.markdown(f"{i+1}. [{doc_name}]({doc_loc})")

# --- Chat Input Field ---
if prompt := st.chat_input("Ask your question..."):
    # Check for API token and assistant ID before proceeding
    if not st.session_state.api_token or not st.session_state.assistant_id:
        st.session_state.config_error = "⚠️ Please enter your API Token and Assistant Name in the sidebar first!"
        st.rerun() # Rerun to display the error message immediately
    else:
        st.session_state.config_error = "" # Clear any previous config error

        # Add user message to chat history and display it
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get assistant's response
        with st.chat_message("assistant"):
            with st.spinner("🧠 Thinking..."):
                assistant_content, sources, error_message = get_assistant_response(
                    st.session_state.api_token,
                    st.session_state.assistant_id,
                    st.session_state.messages # Send the whole history
                )
            
            if error_message:
                st.error(f"Assistant Error: {error_message}")
                # Optionally remove the last user message if the API call failed catastrophically
                # or add an error message from assistant. For now, just show error.
                # To prevent a broken state, let's add an error message to the chat
                error_chat_entry = {"role": "assistant", "content": f"Sorry, I encountered an error: {error_message}"}
                st.session_state.messages.append(error_chat_entry)
                st.markdown(error_chat_entry["content"])

            elif assistant_content:
                st.markdown(assistant_content)
                assistant_chat_entry = {"role": "assistant", "content": assistant_content}
                if sources:
                    assistant_chat_entry["sources"] = sources
                    with st.expander("📚 Sources", expanded=True): # Expand for new sources by default
                        for i, source in enumerate(sources):
                            doc_name = source.get("source_document_name", "Unknown Document")
                            doc_loc = source.get("source_location", "#")
                            st.markdown(f"{i+1}. [{doc_name}]({doc_loc})")
                st.session_state.messages.append(assistant_chat_entry)
            else:
                # This case should ideally be caught by error_message in get_assistant_response
                st.error("Received no content from assistant.")
                fallback_message = "Sorry, I couldn't generate a response."
                st.session_state.messages.append({"role": "assistant", "content": fallback_message})
                st.markdown(fallback_message)

# Add a small welcome message if chat is empty and config is set
if not st.session_state.messages and st.session_state.api_token and st.session_state.assistant_id:
    st.info(f"Ready to chat with '{st.session_state.assistant_id}'! Type your first message below.")
elif not st.session_state.messages and (not st.session_state.api_token or not st.session_state.assistant_id):
     st.info("Please configure your API Token and Assistant Name in the sidebar to begin.")
