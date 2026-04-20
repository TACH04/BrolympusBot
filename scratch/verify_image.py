import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from bot.image_generator import render_event_dashboard

def test_image_generation():
    # Mock data with many attendees
    events = [
        {
            'schedule': 'Apr 25  07:00 PM',
            'title': 'Huge Brolympus Party',
            'attendees': 15,
            'attendees_data': [
                {'initials': 'TH', 'color': '#ff9999'},
                {'initials': 'JD', 'color': '#99ff99'},
                {'initials': 'AM', 'color': '#9999ff'},
                {'initials': 'KB', 'color': '#ffff99'},
                {'initials': 'SC', 'color': '#ff99ff'},
                {'initials': 'MJ', 'color': '#99ffff'},
                {'initials': 'LB', 'color': '#ffffff'},
                {'initials': 'DR', 'color': '#cccccc'},
                {'initials': 'BK', 'color': '#ffaa00'},
                {'initials': 'TW', 'color': '#00ffaa'},
                {'initials': 'RS', 'color': '#aa00ff'},
                {'initials': 'PP', 'color': '#ff00aa'},
                {'initials': 'QQ', 'color': '#00aaff'},
                {'initials': 'RR', 'color': '#aaff00'},
                {'initials': 'SS', 'color': '#555555'}
            ]
        },
        {
            'schedule': 'Apr 26  10:00 AM',
            'title': 'Morning Run',
            'attendees': 2,
            'attendees_data': [
                {'initials': 'TH', 'color': '#ff9999'},
                {'initials': 'JD', 'color': '#99ff99'}
            ]
        },
        {
            'schedule': 'Apr 27  06:00 PM',
            'title': 'Empty Event',
            'attendees': 0,
            'attendees_data': []
        }
    ]
    
    output_path = os.path.join(os.path.dirname(__file__), 'test_dashboard.png')
    render_event_dashboard(events, output_path)
    print(f"Test image generated at: {output_path}")

if __name__ == "__main__":
    test_image_generation()
