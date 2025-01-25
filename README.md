# Tottenham Stadium Backend

A Django REST API backend for the Tottenham Stadium booking application.

## Features

- User Authentication with JWT
- Email Verification System
- Password Reset Functionality
- Stadium Booking Management
- Google Calendar Integration
- Profile Management

## Tech Stack

- Python 3.11.7
- Django 5.0
- Django REST Framework
- PostgreSQL (Production) / SQLite (Development)
- JWT Authentication
- Google Calendar API
- SMTP Email Service

## Prerequisites

- Python 3.11.7
- pip (Python package manager)
- Virtual environment (recommended)
- Gmail account (for email notifications)
- Google Cloud Platform account (for Calendar API)

## Local Development Setup

1. Clone the repository:

```bash
git clone <repository-url>
cd backend-stadium
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

5. Generate a Django secret key:

```bash
python generate_key.py
```

6. Update the `.env` file with your configurations:

```env
DEBUG=True
SECRET_KEY=your-generated-key
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:3000
DATABASE_URL=sqlite:///db.sqlite3
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL="Your Name <your-email@gmail.com>"
```

7. Run migrations:

```bash
python manage.py migrate
```

8. Create a superuser:

```bash
python manage.py createsuperuser
```

9. Run the development server:

```bash
python manage.py runserver
```

## API Endpoints

### Authentication

- `POST /auth/register/` - Register a new user
- `POST /auth/login/` - Login user
- `POST /auth/verify-code/` - Verify email
- `POST /auth/resend-code/` - Resend verification code
- `POST /auth/password-reset/` - Request password reset
- `POST /auth/password-reset/confirm/` - Reset password
- `POST /auth/token/refresh/` - Refresh JWT token

### Calendar

- `GET /calendar/available_slots/` - Get available booking slots
- `POST /calendar/book_slot/` - Book a slot
- `POST /calendar/cancel_booking/` - Cancel a booking
- `GET /calendar/my_bookings/` - Get user's bookings

## Deployment Guide

### Deploying on Oracle Cloud

1. Create an Oracle Cloud account and set up a Compute instance:

   - Choose Oracle Linux or Ubuntu
   - Configure networking and security rules
   - Set up SSH access

2. Connect to your instance:

```bash
ssh -i <private-key> <username>@<instance-ip>
```

3. Install required packages:

```bash
sudo yum update -y  # For Oracle Linux
sudo yum install python3.11 python3.11-devel nginx git
```

4. Clone and set up the application:

```bash
git clone <repository-url>
cd backend-stadium
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

5. Set up Gunicorn and Nginx:

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

Add the following:

```ini
[Unit]
Description=gunicorn daemon
After=network.target

[Service]
User=<your-user>
Group=<your-group>
WorkingDirectory=/path/to/backend-stadium
ExecStart=/path/to/backend-stadium/venv/bin/gunicorn --workers 3 --bind unix:/path/to/backend-stadium/app.sock backend.wsgi:application

[Install]
WantedBy=multi-user.target
```

6. Configure Nginx:

```bash
sudo nano /etc/nginx/sites-available/stadium
```

Add:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        root /path/to/backend-stadium;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/path/to/backend-stadium/app.sock;
    }
}
```

7. Enable and start services:

```bash
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
sudo systemctl restart nginx
```

### Deploying on Render

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Configure the service:
   - Build Command: `./build.sh`
   - Start Command: `gunicorn backend.wsgi:application --bind 0.0.0.0:$PORT`
4. Add environment variables from your `.env` file
5. Deploy

### Deploying on Heroku

1. Install Heroku CLI and login:

```bash
heroku login
```

2. Create a new Heroku app:

```bash
heroku create your-app-name
```

3. Add PostgreSQL addon:

```bash
heroku addons:create heroku-postgresql:hobby-dev
```

4. Configure environment variables:

```bash
heroku config:set SECRET_KEY=your-secret-key
heroku config:set DEBUG=False
heroku config:set ALLOWED_HOSTS=.herokuapp.com
# Add other necessary environment variables
```

5. Deploy:

```bash
git push heroku main
```

6. Run migrations:

```bash
heroku run python manage.py migrate
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request
