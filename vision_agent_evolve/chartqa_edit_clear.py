from PIL import Image, ImageDraw

# Create a simulated image based on the original chart
img = Image.new('RGBA', (800, 150), 'white')
draw = ImageDraw.Draw(img)

# Draw the bars for net worth
positions = {'Nikolaj Coster-Waldau': 15, 'Peter Dinklage': 75}
net_worths = {'Nikolaj Coster-Waldau': 16, 'Peter Dinklage': 16}

for name, y in positions.items():
    value = net_worths[name]
    draw.rectangle([100, y, 100 + value * 20, y + 30], fill='blue')
    draw.text((10, y), name, fill='black')

# Save the image
img.save('artifacts/edited_chartqa_clear.png')
print('Image saved as artifacts/edited_chartqa_clear.png')
