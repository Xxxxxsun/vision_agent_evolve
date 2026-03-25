from PIL import Image, ImageDraw

src = "/path/to/your/image.png"  # Replace with the actual image path
dst = "$PWD/artifacts/edited_chartqa.png"

img = Image.open(src).convert("RGBA")
draw = ImageDraw.Draw(img, "RGBA")

# Dimming non-React Native bars
mask = Image.new("RGBA", img.size, (255, 255, 255, 150))
draw.rectangle(((95, 0), (600, img.height)), fill=(255, 255, 255, 150))

img.paste(mask, mask=mask)
draw = ImageDraw.Draw(img, "RGBA")
draw.rectangle(((85, 0), (150, img.height)), fill=(0, 0, 0, 0))  # Keeping React Native visible

img.save(dst)
print(f"edited image saved to {dst}")
