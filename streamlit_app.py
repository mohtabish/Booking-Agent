import streamlit as st
import requests
import uuid
import json
from datetime import datetime

# Streamlit configuration
st.set_page_config(
    page_title="TailorTalk - AI Calendar Assistant",
    page_icon="📅",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        max-width: 80%;
    }
    .user-message {
        background-color: #007bff;
        color: white;
        margin-left: auto;
    }
    .bot-message {
        background-color: #f8f9fa;
        color: #333;
        border: 1px solid #dee2e6;
    }
    .title-container {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "api_url" not in st.session_state:
    st.session_state.api_url = "http://localhost:8000"  # Change this to your deployed API URL

# Title
st.markdown("""
<div class="title-container">
    <h1>📅 TailorTalk</h1>
    <p>Your AI-powered calendar assistant for seamless appointment booking</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("🛠 Configuration")
    api_url = st.text_input("API URL", value=st.session_state.api_url)
    st.session_state.api_url = api_url
    
    st.header("📖 How to Use")
    st.markdown("""
    **Try these sample queries:**
    - "I want to schedule a call for tomorrow afternoon"
    - "Do you have any free time this Friday?"
    - "Book a meeting between 3-5 PM next week"
    - "Check my availability for tomorrow"
    """)
    
    if st.button("🔄 Reset Conversation"):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

# Main chat interface
st.header("💬 Chat with your AI Assistant")

# Display chat messages
chat_container = st.container()
with chat_container:
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(f"""
            <div class="chat-message user-message">
                <strong>You:</strong> {message["content"]}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="chat-message bot-message">
                <strong>🤖 TailorTalk:</strong> {message["content"]}
            </div>
            """, unsafe_allow_html=True)

# Chat input
with st.form(key="chat_form", clear_on_submit=True):
    col1, col2 = st.columns([6, 1])
    with col1:
        user_input = st.text_input("Type your message here...", key="user_input", label_visibility="collapsed")
    with col2:
        submit_button = st.form_submit_button("Send", use_container_width=True)

# Process user input
if submit_button and user_input:
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    try:
        # Call the API
        with st.spinner("🤔 Thinking..."):
            response = requests.post(
                f"{st.session_state.api_url}/chat",
                json={
                    "message": user_input,
                    "session_id": st.session_state.session_id
                },
                timeout=30
            )
        
        if response.status_code == 200:
            result = response.json()
            bot_response = result["response"]
            
            # Add bot response to chat
            st.session_state.messages.append({"role": "bot", "content": bot_response})
            
            # Show booking confirmation if applicable
            if result.get("booking_confirmed"):
                st.success("🎉 Appointment booked successfully!")
                st.balloons()
            
        else:
            st.error(f"API Error: {response.status_code}")
            st.session_state.messages.append({
                "role": "bot", 
                "content": "Sorry, I encountered an error. Please try again."
            })
    
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to the API. Please check if the backend is running.")
        st.session_state.messages.append({
            "role": "bot", 
            "content": "I'm having trouble connecting to my backend. Please make sure the API server is running on the configured URL."
        })
    except Exception as e:
        st.error(f"Error: {str(e)}")
        st.session_state.messages.append({
            "role": "bot", 
            "content": f"Sorry, I encountered an unexpected error: {str(e)}"
        })
    
    # Rerun to show new messages
    st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 1rem;">
    <p>🚀 Built with FastAPI, LangGraph, and Streamlit | 
    <a href="https://github.com" target="_blank">View Source Code</a></p>
</div>
""", unsafe_allow_html=True)
