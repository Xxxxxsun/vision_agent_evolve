from PIL import Image, ImageDraw
import sys

src, dst = sys.argv[1], sys.argv[2]
img = Image.open(src).convert("RGBA")
draw = ImageDraw.Draw(img, "RGBA")

# Crop to highlight Peter Dinklage and Nikolaj Coster-Waldau
img = img.crop((0, 0, 800, 120))

img.save(dst)
print(f"Refined edited image saved to {dst}")
