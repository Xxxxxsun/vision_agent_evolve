from PIL import Image

# Load the images
img_a = Image.open('panel_a.png').convert('L')
img_b = Image.open('panel_b.png').convert('L')
img_c = Image.open('panel_c.png').convert('L')
img_d = Image.open('panel_d.png').convert('L')

def get_pixels(img):
    pixels = set()
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            # The shapes are darker than the background
            if img.getpixel((x, y)) < 200:
                pixels.add((x, y))
    return pixels

masks = {
    'A': get_pixels(img_a),
    'B': get_pixels(img_b),
    'C': get_pixels(img_c),
    'D': get_pixels(img_d)
}

combinations = ['AB', 'AC', 'AD', 'BC', 'BD', 'CD']
max_overlap = -1
best_comb = ''

for comb in combinations:
    m1 = masks[comb[0]]
    m2 = masks[comb[1]]
    overlap = m1.intersection(m2)
    area = len(overlap)
    print(f'{comb}: {area}')
    if area > max_overlap:
        max_overlap = area
        best_comb = comb

print(f'Best: {best_comb}')
