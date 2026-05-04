"""
Create a simple icon for PDF2ZH-Next application
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_app_icon():
    """Create a simple application icon"""
    
    # Create a 256x256 image with transparent background
    size = 256
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw a rounded rectangle background
    margin = 20
    corner_radius = 30
    
    # Background gradient effect (simplified as solid color)
    bg_color = (67, 126, 235, 255)  # Blue color
    
    # Draw rounded rectangle
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=corner_radius,
        fill=bg_color
    )
    
    # Add text "PDF" and "2ZH"
    try:
        # Try to use a system font
        font_size = 48
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        # Fallback to default font
        font = ImageFont.load_default()
    
    # Draw "PDF" text
    text1 = "PDF"
    text1_bbox = draw.textbbox((0, 0), text1, font=font)
    text1_width = text1_bbox[2] - text1_bbox[0]
    text1_height = text1_bbox[3] - text1_bbox[1]
    
    text1_x = (size - text1_width) // 2
    text1_y = size // 2 - text1_height - 10
    
    draw.text((text1_x, text1_y), text1, fill=(255, 255, 255, 255), font=font)
    
    # Draw "2ZH" text
    text2 = "2ZH"
    text2_bbox = draw.textbbox((0, 0), text2, font=font)
    text2_width = text2_bbox[2] - text2_bbox[0]
    text2_height = text2_bbox[3] - text2_bbox[1]
    
    text2_x = (size - text2_width) // 2
    text2_y = size // 2 + 10
    
    draw.text((text2_x, text2_y), text2, fill=(255, 255, 255, 255), font=font)
    
    # Add a small document icon
    doc_size = 30
    doc_x = size - margin - doc_size - 10
    doc_y = margin + 10
    
    # Draw document shape
    draw.rectangle([doc_x, doc_y, doc_x + doc_size, doc_y + doc_size], 
                  fill=(255, 255, 255, 200))
    draw.rectangle([doc_x + 5, doc_y + 5, doc_x + doc_size - 5, doc_y + 8], 
                  fill=(67, 126, 235, 255))
    draw.rectangle([doc_x + 5, doc_y + 12, doc_x + doc_size - 5, doc_y + 15], 
                  fill=(67, 126, 235, 255))
    draw.rectangle([doc_x + 5, doc_y + 19, doc_x + doc_size - 10, doc_y + 22], 
                  fill=(67, 126, 235, 255))
    
    return img

def main():
    """Create icons in different sizes"""
    
    # Create the base icon
    base_icon = create_app_icon()
    
    # Save as PNG
    base_icon.save('app-icon.png', 'PNG')
    print("Created app-icon.png")
    
    # Create ICO file with multiple sizes
    icon_sizes = [16, 32, 48, 64, 128, 256]
    icons = []
    
    for size in icon_sizes:
        resized = base_icon.resize((size, size), Image.Resampling.LANCZOS)
        icons.append(resized)
    
    # Save as ICO
    base_icon.save('app-icon.ico', format='ICO', sizes=[(s, s) for s in icon_sizes])
    print("Created app-icon.ico")
    
    print("Icon creation completed!")

if __name__ == "__main__":
    main()
