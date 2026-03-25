from PIL import Image, ImageDraw
import sys

src, dst = sys.argv[1], sys.argv[2]
img = Image.open(src).convert("RGBA")
draw = ImageDraw.Draw(img, "RGBA")

# Mask future data
for x in range(400, img.width):
    draw.rectangle([x, 0, x + 1, img.height], fill=(255, 255, 255, 180))

img.save(dst)
print(f"edited image saved to {dst}")
