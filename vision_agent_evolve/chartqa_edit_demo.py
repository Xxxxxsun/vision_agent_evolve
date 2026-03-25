from PIL import Image, ImageDraw

# Create a chart based on the original information for demonstration purposes
img = Image.new('RGBA', (800, 140), 'white')
draw = ImageDraw.Draw(img)

# Add bars for net worth
net_worths = {'Nikolaj Coster-Waldau': 16, 'Peter Dinklage': 16}
y_positions = {'Nikolaj Coster-Waldau': 20, 'Peter Dinklage': 80}

# Draw highlighted bars
for name, value in net_worths.items():
    y = y_positions[name]
    draw.rectangle([50, y, 50 + 20 * value, y + 40], fill='blue')
    draw.text((10, y), name, fill='black')

# Save the image
img.save('artifacts/edited_chartqa_demo_v2.png')
print('Edited image saved to artifacts/edited_chartqa_demo_v2.png')
