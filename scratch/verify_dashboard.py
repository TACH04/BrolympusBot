import os
import sys
import datetime

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from bot.image_generator import render_event_dashboard

# Mock events data
events = [
    {
        'schedule': 'Apr 19  8:00 PM',
        'title': 'FakeMink Concert',
        'attendees': 0,
        'attendees_data': []
    },
    {
        'schedule': 'Apr 25  9:00 PM',
        'title': 'Sonorans Party',
        'attendees': 2,
        'attendees_data': [
            {'initials': 'TH', 'color': '#ffaaaa'},
            {'initials': 'AR', 'color': '#aaaaff'}
        ]
    }
]

output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scratch', 'dashboard_verify.png'))
render_event_dashboard(events, output_path)
print(f"Generated verification image at: {output_path}")
