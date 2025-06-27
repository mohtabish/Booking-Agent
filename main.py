from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
from datetime import datetime, timedelta
import json
from dateutil import parser
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
import requests
from dotenv import load_dotenv

app = FastAPI()

# CORS setup (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Google Calendar configuration
SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.pickle'

class GoogleCalendarService:
    def __init__(self):
        self.service = None
        self.setup_calendar_service()
    
    def setup_calendar_service(self):
        """Initialize Google Calendar service"""
        creds = None
        
        # Load existing token
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if os.path.exists(CREDENTIALS_FILE):
                    flow = Flow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
                    
                    auth_url, _ = flow.authorization_url(prompt='consent')
                    print(f"Please visit this URL to authorize the application: {auth_url}")
                    
                    code = input('Enter the authorization code: ')
                    flow.fetch_token(code=code)
                    creds = flow.credentials
                else:
                    # For demo purposes, use mock data if no credentials
                    print("No Google credentials found. Using mock calendar data.")
                    self.service = None
                    return
            
            # Save credentials
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('calendar', 'v3', credentials=creds)
    
    def get_events(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """Get calendar events in time range"""
        if not self.service:
            # Return mock data for demo
            return self._get_mock_events(start_time, end_time)
        
        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=start_time.isoformat() + 'Z',
                timeMax=end_time.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            return [self._format_event(event) for event in events]
        except Exception as e:
            print(f"Error fetching events: {e}")
            return self._get_mock_events(start_time, end_time)
    
    def create_event(self, title: str, start_time: datetime, end_time: datetime, description: str = "") -> Dict:
        """Create a new calendar event"""
        if not self.service:
            # Return mock response for demo
            return {
                'id': f'mock_event_{int(start_time.timestamp())}',
                'title': title,
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'status': 'confirmed'
            }
        
        event = {
            'summary': title,
            'description': description,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'UTC',
            },
        }
        
        try:
            created_event = self.service.events().insert(calendarId='primary', body=event).execute()
            return self._format_event(created_event)
        except Exception as e:
            print(f"Error creating event: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create event: {str(e)}")
    
    def _format_event(self, event: Dict) -> Dict:
        """Format Google Calendar event for our use"""
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        
        return {
            'id': event['id'],
            'title': event.get('summary', 'No Title'),
            'start': start,
            'end': end,
            'status': event.get('status', 'confirmed')
        }
    
    def _get_mock_events(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """Generate mock events for demo purposes"""
        mock_events = []
        current = start_time.replace(hour=9, minute=0, second=0, microsecond=0)
        
        # Add some mock meetings
        if current.weekday() < 5:  # Weekday
            # Morning meeting
            if current.hour <= 10:
                mock_events.append({
                    'id': f'mock_1_{current.strftime("%Y%m%d")}',
                    'title': 'Team Standup',
                    'start': current.replace(hour=10).isoformat(),
                    'end': current.replace(hour=10, minute=30).isoformat(),
                    'status': 'confirmed'
                })
            
            # Afternoon meeting
            if current.hour <= 15:
                mock_events.append({
                    'id': f'mock_2_{current.strftime("%Y%m%d")}',
                    'title': 'Client Review',
                    'start': current.replace(hour=15).isoformat(),
                    'end': current.replace(hour=16).isoformat(),
                    'status': 'confirmed'
                })
        
        return mock_events

# Initialize calendar service
calendar_service = GoogleCalendarService()

# ===== LANGGRAPH AGENT =====
from langgraph.graph import StateGraph, END
from langchain.tools import tool
from langchain.schema import HumanMessage, AIMessage
from typing import TypedDict, Annotated, Sequence
import operator

class AgentState(TypedDict):
    messages: Annotated[Sequence[HumanMessage | AIMessage], operator.add]
    user_intent: str
    extracted_datetime: Optional[str]
    suggested_slots: Optional[List[Dict]]
    booking_details: Optional[Dict]
    step: str

@tool
def check_calendar_availability(date_range: str) -> str:
    """Check calendar availability for a given date range"""
    try:
        # Parse date range (simplified for demo)
        if "tomorrow" in date_range.lower():
            start_date = datetime.now() + timedelta(days=1)
        elif "today" in date_range.lower():
            start_date = datetime.now()
        elif "friday" in date_range.lower():
            # Find next Friday
            days_ahead = 4 - datetime.now().weekday()  # Friday is 4
            if days_ahead <= 0:
                days_ahead += 7
            start_date = datetime.now() + timedelta(days=days_ahead)
        else:
            start_date = datetime.now() + timedelta(days=1)
        
        end_date = start_date + timedelta(hours=12)  # Check 12 hours
        
        events = calendar_service.get_events(start_date, end_date)
        
        if not events:
            return f"No existing events found for {start_date.strftime('%A, %B %d')}. You have full availability!"
        
        event_list = []
        for event in events:
            start_time = parser.parse(event['start']).strftime('%I:%M %p')
            end_time = parser.parse(event['end']).strftime('%I:%M %p')
            event_list.append(f"- {event['title']}: {start_time} - {end_time}")
        
        return f"Existing events for {start_date.strftime('%A, %B %d')}:\n" + "\n".join(event_list)
        
    except Exception as e:
        return f"Error checking calendar: {str(e)}"

@tool
def suggest_time_slots(preferences: str) -> str:
    """Suggest available time slots based on user preferences"""
    try:
        # Simple logic for demo
        base_date = datetime.now() + timedelta(days=1)
        
        if "afternoon" in preferences.lower():
            slots = [
                base_date.replace(hour=14, minute=0),
                base_date.replace(hour=15, minute=0),
                base_date.replace(hour=16, minute=0)
            ]
        elif "morning" in preferences.lower():
            slots = [
                base_date.replace(hour=9, minute=0),
                base_date.replace(hour=10, minute=0),
                base_date.replace(hour=11, minute=0)
            ]
        else:
            slots = [
                base_date.replace(hour=11, minute=0),
                base_date.replace(hour=14, minute=0),
                base_date.replace(hour=16, minute=0)
            ]
        
        slot_strings = []
        for i, slot in enumerate(slots, 1):
            slot_strings.append(f"{i}. {slot.strftime('%A, %B %d at %I:%M %p')}")
        
        return "Here are some available time slots:\n" + "\n".join(slot_strings)
        
    except Exception as e:
        return f"Error suggesting slots: {str(e)}"

@tool
def book_appointment(details: str) -> str:
    """Book an appointment with given details"""
    try:
        # Parse booking details (simplified)
        import re
        
        # Extract time info
        tomorrow = datetime.now() + timedelta(days=1)
        start_time = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)  # Default 2 PM
        end_time = start_time + timedelta(hours=1)  # 1 hour meeting
        
        # Create the event
        event = calendar_service.create_event(
            title="Scheduled Meeting",
            start_time=start_time,
            end_time=end_time,
            description="Meeting booked through TailorTalk agent"
        )
        
        return f"✅ Appointment booked successfully!\nTitle: {event['title']}\nTime: {start_time.strftime('%A, %B %d at %I:%M %p')} - {end_time.strftime('%I:%M %p')}\nEvent ID: {event['id']}"
        
    except Exception as e:
        return f"Error booking appointment: {str(e)}"

def should_continue(state):
    """Determine if we should continue processing"""
    messages = state['messages']
    last_message = messages[-1]
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "continue"
    else:
        return "end"

def call_model(state):
    """Main agent logic"""
    messages = state['messages']
    last_message = messages[-1].content if messages else ""
    
    # Simple intent detection
    intent = "unknown"
    if any(word in last_message.lower() for word in ["schedule", "book", "appointment", "meeting"]):
        intent = "booking"
    elif any(word in last_message.lower() for word in ["available", "free", "check"]):
        intent = "availability"
    elif any(word in last_message.lower() for word in ["confirm", "yes", "okay"]):
        intent = "confirmation"
    
    # Generate appropriate response
    if intent == "booking":
        if "tomorrow afternoon" in last_message.lower():
            response = "I'd be happy to help you schedule a call for tomorrow afternoon! Let me check what times are available."
            # This would trigger calendar check
        elif "friday" in last_message.lower():
            response = "Let me check your availability for this Friday."
        else:
            response = "I'll help you schedule that meeting. Could you tell me your preferred date and time?"
    
    elif intent == "availability":
        response = "Let me check your calendar availability."
    
    elif intent == "confirmation":
        response = "Great! Let me book that appointment for you."
    
    else:
        response = "Hello! I'm here to help you schedule appointments. What would you like to book?"
    
    return {**state, "messages": [AIMessage(content=response)], "user_intent": intent}

def call_tool(state):
    """Execute tools based on intent"""
    intent = state.get("user_intent", "")
    last_message = state['messages'][-2].content if len(state['messages']) > 1 else ""

    if intent == "availability":
        result = check_calendar_availability(last_message)
    elif intent == "booking" and "suggest" not in state.get("step", ""):
        result = suggest_time_slots(last_message)
        state["step"] = "suggested"
    elif intent == "confirmation":
        result = book_appointment(last_message)
    else:
        result = "I'm ready to help with your scheduling needs!"

    return {**state, "messages": [AIMessage(content=str(result))]}

# Build the graph
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("action", call_tool)

workflow.set_entry_point("agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "continue": "action",
        "end": END
    }
)
workflow.add_edge('action', 'agent')

# Compile the graph
app_graph = workflow.compile()

# Session storage (in production, use Redis or database)
sessions = {}

# Pydantic models
class ChatMessage(BaseModel):
    message: str
    session_id: str

class ChatResponse(BaseModel):
    response: str
    booking_confirmed: bool = False

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(chat_message: ChatMessage):
    """Main chat endpoint"""
    session_id = chat_message.session_id
    message = chat_message.message

    # Use LangGraph agent for scheduling/booking/availability
    keywords = ["schedule", "book", "appointment", "meeting", "available", "free", "check", "confirm", "yes", "okay"]
    if any(word in message.lower() for word in keywords):
        # Use LangGraph agent
        state = {"messages": [HumanMessage(content=message)]}
        result = app_graph.invoke(state)
        ai_message = result["messages"][-1].content if "messages" in result and result["messages"] else "Sorry, I couldn't process your request."
        booking_confirmed = result.get("user_intent") == "confirmation"
        return ChatResponse(
            response=ai_message,
            booking_confirmed=booking_confirmed
        )
    else:
        # Fallback to GROQ LLM for general questions
        ai_response = call_groq_ai(message)
        return ChatResponse(
            response=ai_response,
            booking_confirmed=False
        )

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

load_dotenv()  # Load .env file

def call_groq_ai(prompt: str) -> str:
    """Call the GROQ LLM API and return the response."""
    import os
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "GROQ API key not found. Please set GROQ_API_KEY in your .env file."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "system", "content": "You are an AI assistant for calendar and general questions."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 512,
        "temperature": 0.7
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        print("GROQ API response:", result)  # Debug print
        # Defensive: check for keys
        if "choices" in result and result["choices"]:
            return result["choices"][0]["message"]["content"].strip()
        else:
            return "Sorry, I couldn't understand the response from the AI model."
    except Exception as e:
        print(f"GROQ API error: {e}")
        return "Sorry, I couldn't get a response from the AI model. Please try again later."

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

