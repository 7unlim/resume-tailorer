#!/usr/bin/env python3
"""
Generate simple icons for the Chrome extension
Run: python scripts/generate_icons.py
"""

import os
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Installing Pillow...")
    os.system("pip install Pillow")
    from PIL import Image, ImageDraw

def create_icon(size):
    """Create a simple gradient icon with a document symbol"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Background circle with gradient effect
    padding = size // 8
    
    # Coral to teal gradient simulation
    for i in range(size - 2 * padding):
        ratio = i / (size - 2 * padding)
        r = int(255 * (1 - ratio * 0.7))
        g = int(107 + (205 - 107) * ratio)
        b = int(107 + (196 - 107) * ratio)
        
        y = padding + i
        draw.line([(padding, y), (size - padding, y)], fill=(r, g, b, 255))
    
    # Create rounded rectangle mask
    mask = Image.new('L', (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    radius = size // 4
    mask_draw.rounded_rectangle(
        [padding, padding, size - padding, size - padding],
        radius=radius,
        fill=255
    )
    
    # Apply mask
    img.putalpha(mask)
    
    # Draw document icon
    doc_padding = size // 4
    doc_width = size // 2
    doc_height = int(size * 0.6)
    doc_x = (size - doc_width) // 2
    doc_y = (size - doc_height) // 2
    
    # Document outline
    draw = ImageDraw.Draw(img)
    fold_size = size // 6
    
    # Document shape points
    points = [
        (doc_x, doc_y),
        (doc_x + doc_width - fold_size, doc_y),
        (doc_x + doc_width, doc_y + fold_size),
        (doc_x + doc_width, doc_y + doc_height),
        (doc_x, doc_y + doc_height),
    ]
    
    # Draw document
    draw.polygon(points, fill=(13, 15, 20, 230))
    
    # Draw fold
    fold_points = [
        (doc_x + doc_width - fold_size, doc_y),
        (doc_x + doc_width - fold_size, doc_y + fold_size),
        (doc_x + doc_width, doc_y + fold_size),
    ]
    draw.polygon(fold_points, fill=(30, 35, 45, 230))
    
    # Draw lines on document
    line_y = doc_y + fold_size + size // 10
    line_spacing = size // 12
    line_x_start = doc_x + size // 12
    line_x_end = doc_x + doc_width - size // 12
    
    for i in range(3):
        y = line_y + i * line_spacing
        if y < doc_y + doc_height - size // 12:
            draw.line(
                [(line_x_start, y), (line_x_end - (i * size // 8), y)],
                fill=(100, 110, 130, 200),
                width=max(1, size // 32)
            )
    
    return img


def main():
    # Get project root
    script_dir = Path(__file__).parent
    icons_dir = script_dir.parent / 'extension' / 'icons'
    icons_dir.mkdir(parents=True, exist_ok=True)
    
    sizes = [16, 32, 48, 128]
    
    for size in sizes:
        icon = create_icon(size)
        icon_path = icons_dir / f'icon{size}.png'
        icon.save(icon_path, 'PNG')
        print(f'Created: {icon_path}')
    
    print('\nIcons generated successfully!')


if __name__ == '__main__':
    main()

