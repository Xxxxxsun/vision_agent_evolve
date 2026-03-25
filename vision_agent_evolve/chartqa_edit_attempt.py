from PIL import Image, ImageDraw
import os

# Assuming that "image_input.png" is the image path
src, dst = 'image_input.png', '$PWD/artifacts/edited_chartqa.png'

try:
    img = Image.open(src).convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")

    width, height = img.size

    # Dim all rows except Brett Kavanaugh's
    draw.rectangle(((0, height * 0), (width, height * 0.1)), fill=(255, 255, 255, 150))  # Neil Gorsuch
    draw.rectangle(((0, height * 0.2), (width, height * 0.3)), fill=(255, 255, 255, 150))  # Elena Kagan
    draw.rectangle(((0, height * 0.3), (width, height * 0.4)), fill=(255, 255, 255, 150))  # Sonia Sotomayor
    draw.rectangle(((0, height * 0.4), (width, height * 0.5)), fill=(255, 255, 255, 150))  # Samuel Alito
    draw.rectangle(((0, height * 0.5), (width, height * 0.6)), fill=(255, 255, 255, 150))  # John Roberts
    draw.rectangle(((0, height * 0.6), (width, height * 0.7)), fill=(255, 255, 255, 150))  # Stephen Breyer
    draw.rectangle(((0, height * 0.7), (width, height * 0.8)), fill=(255, 255, 255, 150))  # Ruth Bader Ginsburg
    draw.rectangle(((0, height * 0.8), (width, height * 0.9)), fill=(255, 255, 255, 150))  # Clarence Thomas

    img.save(dst)
    print(f"edited image saved to {dst}")
except FileNotFoundError:
    print("Image file not found.")
