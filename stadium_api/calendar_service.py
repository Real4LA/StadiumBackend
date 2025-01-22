from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle
from datetime import datetime, timedelta
from django.conf import settings

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    creds = None
    token_path = os.path.join(settings.BASE_DIR, 'token.pickle')
    credentials_path = os.path.join(settings.BASE_DIR, 'credentials.json')

    # Load existing credentials if they exist
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    # If credentials are invalid or don't exist, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    return build('calendar', 'v3', credentials=creds)

def get_available_slots(stadium_id, date):
    """Get available time slots for a specific stadium on a given date."""
    service = get_calendar_service()
    calendar_id = f'stadium_{stadium_id}@group.calendar.google.com'  # You'll need to create this calendar

    # Get the start and end of the requested date
    start_time = datetime.combine(date, datetime.min.time())
    end_time = start_time + timedelta(days=1)

    # Get existing events
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_time.isoformat() + 'Z',
        timeMax=end_time.isoformat() + 'Z',
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])

    # Define all possible time slots (9 AM to 9 PM)
    all_slots = []
    slot_time = start_time.replace(hour=9, minute=0)
    while slot_time.hour < 21:
        all_slots.append({
            'start': slot_time,
            'end': slot_time + timedelta(hours=1)
        })
        slot_time += timedelta(hours=1)

    # Remove booked slots
    available_slots = []
    for slot in all_slots:
        is_available = True
        for event in events:
            event_start = datetime.fromisoformat(event['start'].get('dateTime', event['start'].get('date')))
            event_end = datetime.fromisoformat(event['end'].get('dateTime', event['end'].get('date')))
            
            if (slot['start'] >= event_start and slot['start'] < event_end) or \
               (slot['end'] > event_start and slot['end'] <= event_end):
                is_available = False
                break
        
        if is_available:
            available_slots.append(slot)

    return available_slots

def create_booking(stadium_id, start_time, end_time, user_email):
    """Create a calendar event for a booking."""
    service = get_calendar_service()
    calendar_id = f'stadium_{stadium_id}@group.calendar.google.com'

    event = {
        'summary': 'Stadium Booking',
        'description': f'match\nBooked by {user_email}',  # Include 'match' to show in available slots
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'UTC',
        },
        'attendees': [
            {'email': user_email},
        ],
        'transparency': 'opaque',  # Show as busy
        'visibility': 'private',   # Only show free/busy information
    }

    event = service.events().insert(calendarId=calendar_id, body=event).execute()
    return event 