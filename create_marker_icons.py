#!/usr/bin/env python3
"""Generate Leaflet marker icon PNG files."""

from PIL import Image, ImageDraw
import os

# Create images directory if it doesn't exist
os.makedirs('static/images', exist_ok=True)

# Create marker-icon.png (blue teardrop marker, 25x41)
marker_img = Image.new('RGBA', (25, 41), (0, 0, 0, 0))
draw = ImageDraw.Draw(marker_img)

# Draw blue marker shape (simplified teardrop)
draw.polygon([(12, 0), (25, 15), (12.5, 41), (0, 15)], fill=(52, 144, 220, 255), outline=(0, 0, 255, 255))
draw.ellipse([(5, 5), (20, 20)], fill=(255, 255, 255, 200))

marker_img.save('static/images/marker-icon.png')
print("✅ Created marker-icon.png")

# Create marker-shadow.png (shadow, 41x41)
shadow_img = Image.new('RGBA', (41, 41), (0, 0, 0, 0))
draw = ImageDraw.Draw(shadow_img)

# Draw shadow as ellipse
draw.ellipse([(5, 20), (36, 41)], fill=(0, 0, 0, 100))

shadow_img.save('static/images/marker-shadow.png')
print("✅ Created marker-shadow.png")

# Create marker-icon-2x.png (retina version, 50x82)
marker_2x = marker_img.resize((50, 82), Image.Resampling.LANCZOS)
marker_2x.save('static/images/marker-icon-2x.png')
print("✅ Created marker-icon-2x.png")

print("\n✅ All marker files created successfully!")
