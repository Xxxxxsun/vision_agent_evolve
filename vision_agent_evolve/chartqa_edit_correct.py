from PIL import Image, ImageDraw

# Create image
img = Image.new('RGBA', (800, 600), 'white')
draw = ImageDraw.Draw(img)

# Draw bars for net worth
net_worths = {'Nikolaj Coster-Waldau': 16, 'Peter Dinklage': 16}
y_positions = {'Nikolaj Coster-Waldau': 100, 'Peter Dinklage': 200}

# Draw highlighted bars
for name, value in net_worths.items():
    y = y_positions[name]
    draw.rectangle([100, y, 100 + 20 * value, y + 50], fill='blue')
    draw.text((10, y + 10), name, fill='black')

# Save the image
img.save('artifacts/edited_chartqa_correct.png')
print('Image saved as artifacts/edited_chartqa_correct.png')
