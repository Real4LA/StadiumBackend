from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from django.conf import settings
import json

def get_calendar_service():
    """Helper function to create Google Calendar service."""
    credentials = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_SERVICE_ACCOUNT_FILE,
        scopes=['https://www.googleapis.com/auth/calendar']
    )
    return build('calendar', 'v3', credentials=credentials)

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
        
        # Get calendar service
        service = get_calendar_service()
        
        # Get events for the day
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_time,
            timeMax=end_time,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        # Process events into available slots
        slots = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            # Convert to datetime objects
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            
            # Add slot if it's available
            slots.append({
                'start': start_dt.strftime('%H:%M'),
                'end': end_dt.strftime('%H:%M'),
                'event_id': event['id'],
                'booked': event.get('extendedProperties', {}).get('private', {}).get('booked', 'false') == 'true'
            })
        
        return Response({'slots': slots})
    
    except Exception as e:
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
        if event.get('extendedProperties', {}).get('private', {}).get('booked') == 'true':
            return Response(
                {'error': 'This slot is already booked'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update event with booking information
        event['extendedProperties'] = event.get('extendedProperties', {})
        event['extendedProperties']['private'] = {
            'booked': 'true',
            'user_id': str(request.user.id),
            'booking_time': datetime.utcnow().isoformat() + 'Z'
        }
        
        # Update the event
        updated_event = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event
        ).execute()
        
        return Response({
            'message': 'Slot booked successfully',
            'event': updated_event
        })
    
    except Exception as e:
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
        
        # Update event to remove booking information
        event['extendedProperties'] = event.get('extendedProperties', {})
        event['extendedProperties']['private'] = {
            'booked': 'false'
        }
        
        # Update the event
        updated_event = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event
        ).execute()
        
        return Response({
            'message': 'Booking cancelled successfully',
            'event': updated_event
        })
    
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )