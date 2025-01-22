from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils import timezone
from ..models import CalendarSettings, UserProfile
import json
import logging
import os

logger = logging.getLogger('stadium_api')

SCOPES = ['https://www.googleapis.com/auth/calendar']

class CalendarAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """
        Override to allow unauthenticated access to available slots
        but require authentication for booking
        """
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_calendar_service(self):
        try:
            SERVICE_ACCOUNT_FILE = settings.GOOGLE_SERVICE_ACCOUNT_FILE
            logger.info(f"Service account file path: {SERVICE_ACCOUNT_FILE}")
            
            if not os.path.exists(SERVICE_ACCOUNT_FILE):
                logger.error("Service account file does not exist")
                raise FileNotFoundError(f"Google Calendar service account file not found at {SERVICE_ACCOUNT_FILE}")
            
            credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE,
                scopes=['https://www.googleapis.com/auth/calendar']
            )
            logger.info(f"Successfully loaded credentials for: {credentials.service_account_email}")
            
            service = build('calendar', 'v3', credentials=credentials)
            logger.info("Successfully built calendar service")
            return service
        except Exception as e:
            logger.error(f"Error creating calendar service: {str(e)}", exc_info=True)
            raise

    def get(self, request, format=None):
        # Get calendar settings
        try:
            calendar_settings = CalendarSettings.objects.first()
            if not calendar_settings:
                return Response(
                    {"error": "Calendar settings not configured"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Check if this is a request for available slots
            if 'available_slots' in request.path:
                return self.get_available_slots(request, calendar_settings)
            
            # Check if this is a request for user's bookings
            if 'my-bookings' in request.path:
                return self.get_user_bookings(request, calendar_settings)
            
            # Default calendar endpoint - return calendar info
            service = self.get_calendar_service()
            calendar = service.calendars().get(calendarId=calendar_settings.calendar_id).execute()
            
            return Response({
                "calendar_id": calendar_settings.calendar_id,
                "calendar_name": calendar.get('summary'),
                "timezone": calendar.get('timeZone'),
                "description": calendar.get('description', '')
            })

        except Exception as e:
            logger.error(f"Error in calendar view: {str(e)}", exc_info=True)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get_available_slots(self, request, calendar_settings):
        try:
            date_str = request.query_params.get('date')
            calendar_id = request.query_params.get('calendar_id')
            
            if not date_str:
                return Response({"error": "Date parameter is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            if not calendar_id:
                return Response({"error": "calendar_id parameter is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)
            
            service = self.get_calendar_service()
            
            local_tz = timezone.get_current_timezone()
            start_time = timezone.make_aware(datetime.combine(date, datetime.min.time()), local_tz)
            end_time = timezone.make_aware(datetime.combine(date, datetime.max.time()), local_tz)
            
            logger.info(f"Fetching events for date: {date} from calendar: {calendar_id}")
            logger.info(f"Time range: {start_time.isoformat()} to {end_time.isoformat()}")

            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=start_time.isoformat(),
                timeMax=end_time.isoformat(),
                singleEvents=True,
                maxResults=100,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            logger.info(f"Found {len(events)} events")
            
            available_slots = []
            for event in events:
                logger.info(f"Processing event: {json.dumps(event, indent=2)}")
                description = event.get('description', '').lower()
                summary = event.get('summary', '').lower()
                
                if 'match' in description or 'match' in summary:
                    start = event['start'].get('dateTime')
                    if start:
                        event_time = timezone.datetime.fromisoformat(start.replace('Z', '+00:00'))
                        local_time = timezone.localtime(event_time)
                        end = event['end'].get('dateTime')
                        end_time = timezone.datetime.fromisoformat(end.replace('Z', '+00:00'))
                        local_end_time = timezone.localtime(end_time)
                        
                        # Check if the slot is already booked
                        is_booked = 'booked by' in description.lower()
                        
                        slot = {
                            'start': local_time.strftime('%H:%M'),
                            'end': local_end_time.strftime('%H:%M'),
                            'event_id': event['id'],
                            'summary': event.get('summary', 'Available Slot'),
                            'booked': is_booked
                        }
                        available_slots.append(slot)
                        logger.info(f"Added slot: {slot}")
            
            return Response({
                "slots": available_slots,
                "timezone": str(local_tz),
                "date": date_str,
                "total_events": len(events)
            })
            
        except Exception as e:
            logger.error(f"Error getting available slots: {str(e)}", exc_info=True)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get_user_bookings(self, request, calendar_settings):
        try:
            logger.info(f"Fetching bookings for user: {request.user.username}")
            
            service = self.get_calendar_service()
            logger.info("Successfully got calendar service")
            
            # Get current time in UTC
            now = timezone.now()
            end_time = now + timedelta(days=30)
            
            logger.info(f"Fetching events from {now.isoformat()} to {end_time.isoformat()}")
            
            # Define all calendar IDs
            calendar_ids = [
                "433adde78c577df19c67e7d18b2e932c8aa5b60b05098687a13a227712510f5d@group.calendar.google.com",
                "c0981f9f07e185a73808a13deb4e2648915ff7f9a28cfe35bb212ff87115a435@group.calendar.google.com",
                "a233987f0f4b9c95f17c3abf7055ab3287b7765b2c24c02968360fe68a3f2071@group.calendar.google.com"
            ]
            
            user_bookings = []
            user_id = str(request.user.id)  # Convert user ID to string for comparison
            logger.info(f"Filtering events for user ID: {user_id}")
            
            # Fetch events from each calendar
            for calendar_id in calendar_ids:
                try:
                    logger.info(f"Fetching events from calendar: {calendar_id}")
                    events_result = service.events().list(
                        calendarId=calendar_id,
                        timeMin=now.isoformat(),
                        timeMax=end_time.isoformat(),
                        singleEvents=True,
                        orderBy='startTime'
                    ).execute()
                    
                    events = events_result.get('items', [])
                    logger.info(f"Found {len(events)} events in calendar {calendar_id}")
                    
                    # Filter events booked by the current user using user ID
                    for event in events:
                        description = event.get('description', '')
                        # Look for the user ID in the description
                        if f"User ID: {user_id}" in description:
                            start = event['start'].get('dateTime')
                            end = event['end'].get('dateTime')
                            
                            if start and end:  # Only add if we have valid datetime values
                                # Extract stadium name from the event summary
                                summary = event.get('summary', '')
                                stadium_name = summary.split(' - ')[1] if ' - ' in summary else 'Unknown Stadium'
                                
                                booking = {
                                    'start_time': start,
                                    'end_time': end,
                                    'summary': event.get('summary', 'Stadium Booking'),
                                    'event_id': event['id'],
                                    'description': description,
                                    'stadium_name': stadium_name,
                                    'calendar_id': calendar_id
                                }
                                user_bookings.append(booking)
                                logger.info(f"Added booking: {booking}")
                except Exception as e:
                    logger.error(f"Error fetching events from calendar {calendar_id}: {str(e)}")
                    continue
            
            # Sort bookings by start time
            user_bookings.sort(key=lambda x: x['start_time'])
            logger.info(f"Returning {len(user_bookings)} total bookings for user")
            
            return Response({
                "bookings": user_bookings,
                "total_bookings": len(user_bookings)
            })
            
        except Exception as e:
            logger.error(f"Error getting user bookings: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Failed to fetch bookings: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        try:
            calendar_id = request.data.get('calendar_id')
            logger.info(f"Received booking request with calendar_id: {calendar_id}")
            
            # Check if user is in cooldown period
            user_profile = request.user.profile
            if hasattr(user_profile, 'last_cancellation') and user_profile.last_cancellation:
                cooldown_end = user_profile.last_cancellation + timedelta(hours=1)
                if timezone.now() < cooldown_end:
                    minutes_remaining = int((cooldown_end - timezone.now()).total_seconds() / 60)
                    return Response(
                        {
                            "error": f"You cannot make new bookings for {minutes_remaining} minutes due to a recent cancellation"
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            if not calendar_id:
                return Response(
                    {"error": "calendar_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            start_time = request.data.get('start_time')
            end_time = request.data.get('end_time')
            event_id = request.data.get('event_id')
            confirmation = request.data.get('confirmation')
            stadium_name = request.data.get('stadium_name', 'Unknown Stadium')
            
            logger.info(f"Booking details - Stadium: {stadium_name}, Start: {start_time}, End: {end_time}, Event ID: {event_id}")
            
            if not all([start_time, end_time, event_id]):
                return Response(
                    {"error": "start_time, end_time, and event_id are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not confirmation or confirmation != "I CONFIRM":
                return Response(
                    {"error": "Please type 'I CONFIRM' to proceed with the booking"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            service = self.get_calendar_service()
            logger.info(f"Attempting to get event {event_id} from calendar {calendar_id}")
            
            # Get the existing event
            try:
                event = service.events().get(
                    calendarId=calendar_id,
                    eventId=event_id
                ).execute()
                logger.info(f"Successfully retrieved event: {json.dumps(event, indent=2)}")
            except Exception as e:
                logger.error(f"Error getting event: {str(e)}")
                return Response(
                    {"error": "Event not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Check if the event is already booked
            if 'booked by' in event.get('description', '').lower():
                return Response(
                    {"error": "This slot is already booked"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get user details
            user = request.user
            user_details = f"""Booked by:
- Name: {user.get_full_name() or user.username}
- Email: {user.email}
- Phone: {getattr(user.profile, 'phone', 'Not provided')}
- User ID: {user.id}
- Stadium: {stadium_name}
"""
            
            # Update the event
            event['description'] = user_details
            event['summary'] = f'Stadium Booking - {stadium_name} - {user.get_full_name() or user.username}'
            event['colorId'] = '2'  # Light green color
            
            logger.info(f"Updating event in calendar {calendar_id} with data: {json.dumps(event, indent=2)}")
            
            try:
                updated_event = service.events().update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=event
                ).execute()
                logger.info(f"Successfully updated event: {json.dumps(updated_event, indent=2)}")
            except Exception as e:
                logger.error(f"Error updating event: {str(e)}")
                return Response(
                    {"error": f"Failed to update event: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            return Response({
                "event": updated_event,
                "message": "Booking created successfully"
            })
            
        except Exception as e:
            logger.error(f"Error in create booking: {str(e)}", exc_info=True)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request):
        try:
            calendar_id = request.data.get('calendar_id')
            event_id = request.data.get('event_id')
            confirmation = request.data.get('confirmation')
            
            if not calendar_id or not event_id:
                return Response(
                    {"error": "calendar_id and event_id are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not confirmation or confirmation != "I AGREE":
                return Response(
                    {"error": "Please type 'I AGREE' to cancel the booking"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get the user's profile
            user_profile = request.user.profile
            
            service = self.get_calendar_service()
            
            # Get the event to verify ownership
            try:
                event = service.events().get(
                    calendarId=calendar_id,
                    eventId=event_id
                ).execute()
            except Exception as e:
                logger.error(f"Error getting event: {str(e)}")
                return Response(
                    {"error": "Event not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Verify that this booking belongs to the user
            user_id = str(request.user.id)
            if f"User ID: {user_id}" not in event.get('description', ''):
                return Response(
                    {"error": "You can only cancel your own bookings"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Check if the event is in the past
            start_time = event['start'].get('dateTime')
            event_start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            if event_start < timezone.now():
                return Response(
                    {"error": "Cannot cancel past bookings"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Reset the event to available
            event['description'] = "match"  # Reset description
            event['summary'] = "match"  # Set summary to "Match"
            event['colorId'] = '0'  # Reset color
            
            try:
                updated_event = service.events().update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=event
                ).execute()
                
                # Update user's last cancellation time
                user_profile.last_cancellation = timezone.now()
                user_profile.save()
                
                logger.info(f"Successfully cancelled booking for user {user_id}")
                
                return Response({
                    "message": "Booking cancelled successfully. You cannot make a new booking for 1 hour.",
                    "cooldown_end": (timezone.now() + timedelta(hours=1)).isoformat()
                })
                
            except Exception as e:
                logger.error(f"Error updating event: {str(e)}")
                return Response(
                    {"error": f"Failed to cancel booking: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Exception as e:
            logger.error(f"Error in cancel booking: {str(e)}", exc_info=True)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) 