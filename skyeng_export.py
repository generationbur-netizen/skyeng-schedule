#!/usr/bin/env python3
"""
Skyeng Schedule Export to iCalendar
Exports Skyeng teacher schedule to .ics with timezone conversion
Usage: python3 skyeng_export.py
"""

import os
import sys
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from pytz import timezone as pytz_tz

# Configuration
SKYENG_EMAIL = os.environ.get('SKYENG_EMAIL', '').strip()
SKYENG_PASSWORD = os.environ.get('SKYENG_PASSWORD', '').strip()

if not SKYENG_EMAIL or not SKYENG_PASSWORD:
    print("❌ Error: SKYENG_EMAIL and SKYENG_PASSWORD must be set")
    sys.exit(1)

SCHEDULE_URL = 'https://teacher.skyeng.ru/schedule'
MOSCOW_TZ = pytz_tz('Europe/Moscow')      # UTC+3
DANANG_TZ = pytz_tz('Asia/Bangkok')        # UTC+7
TIME_OFFSET = 4  # hours difference

class SkyengExporter:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.events = []

    def login(self):
        """Authenticate with Skyeng"""
        print("🔐 Logging in to Skyeng...")

        login_url = 'https://auth.skyeng.ru/login'

        # First get the login page to extract any CSRF tokens
        response = self.session.get(login_url)

        # Login attempt
        login_data = {
            'email': self.email,
            'password': self.password,
            'remember': 'on'
        }

        response = self.session.post(login_url, data=login_data)

        if 'error' in response.text.lower() or response.status_code >= 400:
            raise Exception(f"Login failed with status {response.status_code}")

        print("✅ Logged in successfully")

    def fetch_schedule(self):
        """Fetch the schedule page"""
        print("📅 Fetching schedule...")

        response = self.session.get(SCHEDULE_URL)
        response.raise_for_status()

        return response.text

    def parse_html_schedule(self, html):
        """Parse schedule from HTML"""
        print("📝 Parsing schedule...")

        soup = BeautifulSoup(html, 'html.parser')

        # Find all lesson links in the schedule
        # Looking for pattern: student name + time
        self.events = []

        # Method 1: Look for student links with time nearby
        links = soup.find_all('a', href=re.compile(r'multi-classroom/personal'))

        for link in links:
            try:
                student_name = link.text.strip()

                # Find time info near the link
                parent = link.parent
                while parent and parent.name != 'div':
                    parent = parent.parent

                if parent:
                    time_match = re.search(r'(\d{1,2}):(\d{2})', parent.text)
                    if time_match:
                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2))

                        # Extract date from calendar context
                        # This is simplified - you may need to enhance
                        date = datetime.now().date()

                        self.events.append({
                            'student': student_name,
                            'hour': hour,
                            'minute': minute,
                            'date': date
                        })
            except Exception as e:
                # Skip events that fail to parse
                pass

        print(f"   ✅ Found {len(self.events)} lessons")
        return len(self.events) > 0

    def create_calendar(self):
        """Create iCalendar from events"""
        print("🗓️  Creating iCalendar...")

        cal = Calendar()
        cal.add('prodid', '-//Skyeng Teacher Calendar//EN')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')
        cal.add('x-wr-calname', 'Skyeng Schedule')
        cal.add('x-wr-timezone', 'Asia/Bangkok')

        for event_data in self.events:
            try:
                # Create datetime in Moscow timezone
                dt_moscow = MOSCOW_TZ.localize(
                    datetime.combine(
                        event_data['date'],
                        datetime.min.time().replace(
                            hour=event_data['hour'],
                            minute=event_data['minute']
                        )
                    )
                )

                # Convert to Danang timezone (add 4 hours)
                dt_danang = dt_moscow.astimezone(DANANG_TZ)

                # Create event
                event = Event()
                event.add('summary', f"Lesson: {event_data['student']}")
                event.add('dtstart', dt_danang)
                event.add('dtend', dt_danang + timedelta(minutes=50))
                event.add('description', f"Skyeng English lesson with {event_data['student']}")
                event.add('location', 'Skyeng')
                event.add('categories', 'Work')

                cal.add_component(event)
            except Exception as e:
                print(f"   ⚠️  Skipped event for {event_data['student']}: {e}")

        print(f"   ✅ Calendar created with {len(cal.subcomponents)} events")
        return cal

    def save_calendar(self, cal, filename='skyeng_schedule.ics'):
        """Save calendar to file"""
        print(f"💾 Saving to {filename}...")

        with open(filename, 'wb') as f:
            f.write(cal.to_ical())

        print(f"   ✅ Saved successfully")
        return filename

def main():
    """Main execution"""
    try:
        print("🚀 Skyeng Calendar Exporter\n")

        exporter = SkyengExporter(SKYENG_EMAIL, SKYENG_PASSWORD)

        # Login
        exporter.login()

        # Fetch schedule
        html = exporter.fetch_schedule()

        # Parse
        if exporter.parse_html_schedule(html):
            # Create calendar
            cal = exporter.create_calendar()

            # Save
            filename = exporter.save_calendar(cal)

            print(f"\n✅ Success! Calendar exported to {filename}")
            print(f"   Times converted: Moscow (UTC+3) → Danang (UTC+7)")

            return 0
        else:
            print("⚠️  No events found in schedule")
            return 1

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
