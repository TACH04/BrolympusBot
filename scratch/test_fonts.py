from PIL import Image, ImageDraw, ImageFont
import os

def test_font(font_path, text, output_name):
    img = Image.new("RGB", (800, 100), color="#1e1e24")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(font_path, 40)
        draw.text((10, 10), text, font=font, fill="#ffffff")
        img.save(output_name)
        print(f"Saved {output_name} with font {font_path}")
    except Exception as e:
        print(f"Failed {output_name} with font {font_path}: {e}")

text = "🏔️ Apr 19 • 8:00 PM ✅ 2 Going"
test_font("/System/Library/Fonts/Supplemental/Arial.ttf", text, "test_arial.png")
test_font("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", text, "test_arial_unicode.png")
test_font("/System/Library/Fonts/Apple Symbols.ttf", text, "test_apple_symbols.png")
test_font("/System/Library/Fonts/Menlo.ttc", text, "test_menlo.png")
