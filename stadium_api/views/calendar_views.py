from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from django.conf import settings
import json
import os

def get_calendar_service():
    """Helper function to create Google Calendar service."""
    try:
        print("\n=== Starting Calendar Service Initialization ===")
        # Get credentials from environment variable
        creds_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_CREDENTIALS')
        if not creds_json:
            print("ERROR: Google service account credentials not found in environment")
            raise ValueError("Google service account credentials not found in environment")
        
        # Parse credentials from JSON string
        try:
            creds_info = json.loads(creds_json)
            print("Successfully parsed service account credentials")
            print(f"Service account email: {creds_info.get('client_email')}")
        except json.JSONDecodeError as e:
            print(f"ERROR: Failed to parse service account credentials: {str(e)}")
            raise ValueError("Invalid service account credentials format")
        
        try:
            credentials = service_account.Credentials.from_service_account_info(
                creds_info,
                scopes=['https://www.googleapis.com/auth/calendar']
            )
            print("Successfully created service account credentials")
        except Exception as e:
            print(f"ERROR: Failed to create service account credentials: {str(e)}")
            raise ValueError("Failed to create service account credentials")
        
        try:
            service = build('calendar', 'v3', credentials=credentials)
            print("Successfully created calendar service")
            
            # Test calendar access
            calendars = service.calendarList().list().execute()
            print(f"\nFound {len(calendars.get('items', []))} calendars:")
            for cal in calendars.get('items', []):
                print(f"- {cal.get('summary', 'Unnamed')} ({cal.get('id')})")
                print(f"  Access Role: {cal.get('accessRole', 'unknown')}")
            
            print("\n=== Calendar Service Initialization Complete ===")
            return service
        except Exception as e:
            print(f"ERROR: Failed to build calendar service or test access: {str(e)}")
            raise ValueError("Failed to create or verify calendar service")
            
    except Exception as e:
        print(f"ERROR: Calendar service initialization failed: {str(e)}")
        raise ValueError(f"Calendar service initialization failed: {str(e)}")

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def available_slots(request):
    """Get available time slots for a specific date and calendar."""
    date_str = request.GET.get('date')
    calendar_id = request.GET.get('calendar_id')
    
    if not date_str or not calendar_id:
        return Response(
            {'error': 'Date and calendar_id are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Parse the date
        date = datetime.strptime(date_str, '%Y-%m-%d')
        start_time = date.replace(hour=0, minute=0, second=0).isoformat() + 'Z'
        end_time = date.replace(hour=23, minute=59, second=59).isoformat() + 'Z'
        
        print(f"Fetching slots for calendar: {calendar_id}")
        print(f"Time range: {start_time} to {end_time}")
        
        # Get calendar service
        service = get_calendar_service()
        
        # Get events for the day
        try:
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=start_time,
                timeMax=end_time,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            print(f"Successfully fetched {len(events_result.get('items', []))} events")
        except Exception as e:
            print(f"Error fetching events: {str(e)}")
            raise ValueError(f"Failed to fetch events: {str(e)}")
        
        events = events_result.get('items', [])
        
        # Process events into available slots
        available_slots = []
        for event in events:
            # Only include events that have 'match' in their description
            description = event.get('description', '').lower()
            if 'match' not in description:
                continue
                
            # Skip if already booked
            if event.get('extendedProperties', {}).get('private', {}).get('user_id'):
                print(f"Skipping booked slot by user {event['extendedProperties']['private']['user_id']}")
                continue
                
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            # Convert to datetime objects
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            
            # Add available slot
            available_slots.append({
                'start': start_dt.strftime('%H:%M'),
                'end': end_dt.strftime('%H:%M'),
                'event_id': event['id']
            })
        
        print(f"Returning {len(available_slots)} available slots")
        return Response({'slots': available_slots})
    
    except Exception as e:
        print(f"Error in available_slots: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def book_slot(request):
    """Book a time slot."""
    try:
        data = request.data
        calendar_id = data.get('calendar_id')
        event_id = data.get('event_id')
        
        if not calendar_id or not event_id:
            return Response(
                {'error': 'calendar_id and event_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get calendar service
        service = get_calendar_service()
        
        # Get the event
        event = service.events().get(
            calendarId=calendar_id,
            eventId=event_id
        ).execute()
        
        # Check if already booked
        if event.get('extendedProperties', {}).get('private', {}).get('user_id'):
            return Response(
                {'error': 'This slot is already booked'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create user profile
        from django.db import transaction
        from ..models import UserProfile
        
        with transaction.atomic():
            user_profile, created = UserProfile.objects.get_or_create(
                user=request.user,
                defaults={'phone': "No phone"}  # Only used if a new profile is created
            )
            if created:
                print(f"Created new profile for user {request.user.id}")
            else:
                print(f"Using existing profile for user {request.user.id}")
        
        # Get user details
        user_name = f"{request.user.first_name} {request.user.last_name}".strip() or "Anonymous"
        user_phone = user_profile.phone if hasattr(user_profile, 'phone') else "No phone"
        
        # Update event with booking information
        event['extendedProperties'] = event.get('extendedProperties', {})
        event['extendedProperties']['private'] = {
            'user_id': str(request.user.id),
            'booking_time': datetime.utcnow().isoformat() + 'Z',
            'user_name': user_name,
            'user_phone': user_phone
        }
        
        # Update event details to show it's booked
        booking_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        event.update({
            'summary': '🏟️ BOOKED MATCH',
            'description': (
                f"📋 BOOKING DETAILS\n"
                f"───────────────\n"
                f"👤 Name: {user_name}\n"
                f"📱 Phone: {user_phone}\n"
                f"🆔 User ID: {request.user.id}\n"
                f"⏰ Booked on: {booking_time}"
            ),
            'colorId': '2',  # Green color for booked events
            'transparency': 'opaque'  # Show as busy
        })
        
        # Update the event
        updated_event = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event
        ).execute()
        
        print(f"Successfully booked slot for user {request.user.id} ({user_name})")
        return Response({
            'message': 'Slot booked successfully',
            'event': updated_event
        })
    
    except Exception as e:
        print(f"Error in book_slot: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_booking(request):
    """Cancel a booking."""
    try:
        data = request.data
        calendar_id = data.get('calendar_id')
        event_id = data.get('event_id')
        
        if not calendar_id or not event_id:
            return Response(
                {'error': 'calendar_id and event_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get calendar service
        service = get_calendar_service()
        
        # Get the event
        event = service.events().get(
            calendarId=calendar_id,
            eventId=event_id
        ).execute()
        
        # Check if booked by this user
        if event.get('extendedProperties', {}).get('private', {}).get('user_id') != str(request.user.id):
            return Response(
                {'error': 'You can only cancel your own bookings'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Reset event to default state
        event.update({
            'summary': 'match',
            'description': 'match',
            'transparency': 'transparent'  # Show as free
        })
        
        # Clear booking information
        event['extendedProperties'] = event.get('extendedProperties', {})
        event['extendedProperties']['private'] = {}
        
        # Update the event
        updated_event = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event
        ).execute()
        
        print(f"Successfully cancelled booking for user {request.user.id}")
        return Response({
            'message': 'Booking cancelled successfully',
            'event': updated_event
        })
    
    except Exception as e:
        print(f"Error in cancel_booking: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_bookings(request):
    """Get all bookings for the current user."""
    try:
        print("\n=== Starting my_bookings ===")
        print(f"User ID: {request.user.id}")
        print(f"User Email: {request.user.email}")
        
        # Get calendar service
        try:
            service = get_calendar_service()
            print("Successfully got calendar service")
        except Exception as e:
            print(f"ERROR: Failed to get calendar service: {str(e)}")
            return Response(
                {'error': 'Failed to access calendar service'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Get all calendars
        try:
            print("\nFetching calendar list...")
            calendars_result = service.calendarList().list().execute()
            calendars = calendars_result.get('items', [])
            print(f"Found {len(calendars)} calendars")
            
            if not calendars:
                print("WARNING: No calendars found. Check service account permissions.")
                return Response({'bookings': []})
        except Exception as e:
            print(f"ERROR: Failed to get calendars: {str(e)}")
            return Response(
                {'error': 'Failed to retrieve calendars'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        all_bookings = []
        user_id_str = str(request.user.id)
        
        for calendar in calendars:
            calendar_id = calendar['id']
            print(f"\nProcessing calendar: {calendar['summary']} ({calendar_id})")
            
            # Get events from now onwards
            now = datetime.utcnow().isoformat() + 'Z'
            try:
                print(f"Fetching events from {now} onwards...")
                events_result = service.events().list(
                    calendarId=calendar_id,
                    timeMin=now,
                    maxResults=100,
                    singleEvents=True,
                    orderBy='startTime',
                    showDeleted=False
                ).execute()
                
                events = events_result.get('items', [])
                print(f"Found {len(events)} events in calendar")
                
                if not events:
                    print("No events found in this calendar")
                    continue
                
                # Filter events booked by the current user
                for event in events:
                    print(f"\nChecking event: {event.get('id')}")
                    print(f"Event summary: {event.get('summary')}")
                    
                    # Check extended properties first
                    extended_props = event.get('extendedProperties', {}).get('private', {})
                    stored_user_id = extended_props.get('user_id')
                    print(f"Extended properties user_id: {stored_user_id}")
                    
                    # Check description as fallback
                    description = event.get('description', '')
                    description_user_id = None
                    user_id_pattern = f"🆔 User ID: {user_id_str}"
                    if user_id_pattern in description:
                        description_user_id = user_id_str
                        print(f"Found user ID in description with pattern: {user_id_pattern}")
                    print(f"Description user_id: {description_user_id}")
                    
                    # Match if user ID is found in either place
                    if stored_user_id == user_id_str or description_user_id == user_id_str:
                        print("Match found! Adding to bookings")
                        print(f"Full event description: {description}")
                        print(f"Extended properties: {extended_props}")
                        
                        start = event['start'].get('dateTime', event['start'].get('date'))
                        end = event['end'].get('dateTime', event['end'].get('date'))
                        
                        # Convert to datetime objects for formatting
                        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                        
                        booking = {
                            'calendar_id': calendar_id,
                            'event_id': event['id'],
                            'stadium_name': calendar['summary'],
                            'start_time': start_dt.isoformat() + 'Z',
                            'end_time': end_dt.isoformat() + 'Z',
                            'description': description,
                            'summary': event.get('summary', '')
                        }
                        all_bookings.append(booking)
                        print(f"Added booking: {booking}")
                    else:
                        print("No match, skipping event")
                        
            except Exception as e:
                print(f"ERROR: Failed to process calendar {calendar_id}: {str(e)}")
                print(f"Error details: {type(e).__name__}: {str(e)}")
                continue
        
        # Sort bookings by start time
        all_bookings.sort(key=lambda x: x['start_time'])
        
        print(f"\n=== Completed my_bookings ===")
        print(f"Total bookings found: {len(all_bookings)}")
        return Response({'bookings': all_bookings})
    
    except Exception as e:
        print(f"ERROR: Failed in my_bookings: {str(e)}")
        print(f"Error details: {type(e).__name__}: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )