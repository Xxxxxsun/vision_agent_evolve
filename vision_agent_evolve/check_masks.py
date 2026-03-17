from PIL import Image

# Check the masks
for name in ['A', 'B', 'C', 'D']:
    img = Image.open(f'panel_{name.lower()}.png').convert('L')
    # Count pixels darker than 200
    count = 0
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            if img.getpixel((x, y)) < 200:
                count += 1
    print(f'{name}: {count}')
