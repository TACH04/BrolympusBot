import os
from PIL import Image, ImageDraw, ImageFont
import datetime

# Fallback to default if Arial is not found (which it should be on macOS)
# Prefer Avenir for a premium look, fallback to Helvetica or Arial
FONT_PATH = next((p for p in [
    "/System/Library/Fonts/Avenir.ttc",
    "/System/Library/Fonts/Helvetica.ttc", 
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf"
] if os.path.exists(p)), "/System/Library/Fonts/Supplemental/Arial.ttf")

def render_event_dashboard(events, output_path):
    """
    Renders a high-fidelity image dashboard of upcoming events.
    events: list of dicts with 'schedule', 'title', 'attendees' (int), 'attendees_data' (list)
    """
    width = 850
    base_row_height = 60
    header_height = 100
    padding = 30
    line_spacing = 35
    
    # Pre-load fonts for measurement
    try:
        font_title = ImageFont.truetype(FONT_PATH, 36)
        font_header = ImageFont.truetype(FONT_PATH, 20)
        font_main = ImageFont.truetype(FONT_PATH, 24)
    except IOError:
        font_title = ImageFont.load_default(size=36) if hasattr(ImageFont, 'load_default') else ImageFont.load_default()
        font_header = ImageFont.load_default(size=20) if hasattr(ImageFont, 'load_default') else ImageFont.load_default()
        font_main = ImageFont.load_default(size=24) if hasattr(ImageFont, 'load_default') else ImageFont.load_default()

    # Column constraints
    cols = [padding, padding + 220, width - 340]
    
    # Calculate heights and layouts for each event
    # We use a dummy draw object for measurements
    dummy_img = Image.new("RGB", (1, 1))
    draw_measure = ImageDraw.Draw(dummy_img)
    
    event_layouts = []
    total_events_height = 0
    
    if not events:
        total_events_height = base_row_height + 20
    else:
        for ev in events:
            att_count = ev.get('attendees', 0)
            attendees_data = ev.get('attendees_data', [])
            
            layout = {
                'event': ev,
                'rows': [], # List of lists of {initials, color, x, y_offset}
                'height': base_row_height,
                'base_text': f"{att_count} Going" if att_count > 0 else "- None -"
            }
            
            if att_count > 0:
                # Fixed indentation for all initials rows
                start_x = cols[2] + 120
                current_x = start_x
                current_row = []
                row_y_offset = 0
                
                for person in attendees_data:
                    initials = person.get('initials', '?')
                    ibbox = draw_measure.textbbox((0, 0), initials, font=font_main)
                    iw = ibbox[2] - ibbox[0]
                    
                    if current_x + iw > width - padding:
                        # Wrap to next line
                        layout['rows'].append(current_row)
                        current_row = []
                        current_x = start_x # Keep consistent indentation
                        row_y_offset += line_spacing
                        
                    current_row.append({
                        'initials': initials,
                        'color': person.get('color', '#ffffff'),
                        'x': current_x,
                        'y_offset': row_y_offset
                    })
                    current_x += iw + 12
                
                if current_row:
                    layout['rows'].append(current_row)
                
                layout['height'] = max(base_row_height, row_y_offset + line_spacing + 10)
            
            event_layouts.append(layout)
            total_events_height += layout['height']

    height = header_height + total_events_height + padding * 2
    
    # Dark mode charcoal background
    img = Image.new("RGB", (width, height), color="#1e1e24")
    draw = ImageDraw.Draw(img)
    
    # Draw Header Title
    draw.text((padding, padding), "Brolympus Schedule", font=font_title, fill="#ffd700")  # Gold accent
    
    # Last updated timestamp
    now_str = datetime.datetime.now().strftime("%I:%M %p")
    draw.text((width - padding - 200, padding + 15), f"Updated: {now_str}", font=font_header, fill="#888888")

    col_names = ["SCHEDULE", "EVENT", "GOING"]
    y = header_height
    for x, name in zip(cols, col_names):
        draw.text((x, y), name, font=font_header, fill="#aaaaaa")
        
    y += 35
    # Header separator
    draw.line([(padding, y), (width-padding, y)], fill="#555555", width=2)
    y += 20
    
    if not events:
        draw.text((padding, y + 20), "No upcoming events scheduled.", font=font_main, fill="#ffffff")
    else:
        for layout in event_layouts:
            ev = layout['event']
            # Draw fields
            schedule_text = ev.get('schedule', f"{ev.get('date', '')} {ev.get('time', '')}")
            draw.text((cols[0], y), schedule_text, font=font_main, fill="#ffffff")
            
            # Truncate long titles
            title = ev['title']
            if len(title) > 23:
                title = title[:20] + "..."
            draw.text((cols[1], y), title, font=font_main, fill="#ffffff")
            
            # Attendee base text (e.g. "X Going")
            att_color = "#4CAF50" if ev['attendees'] > 0 else "#888888"
            draw.text((cols[2], y), layout['base_text'], font=font_main, fill=att_color)
            
            # Draw all wrapped initials
            for row in layout['rows']:
                for item in row:
                    draw.text((item['x'], y + item['y_offset']), item['initials'], font=font_main, fill=item['color'])
            
            y += layout['height']
            # Subtle row separator
            draw.line([(padding, y - 5), (width - padding, y - 5)], fill="#333333", width=1)
            
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path)
    return output_path
