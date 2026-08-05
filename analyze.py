from PIL import Image, ImageOps
import numpy as np

img = Image.open(r'C:\Users\user\Desktop\New folder\New folder\error.png')
arr = np.array(img)
gray = arr[:,:,:3].mean(axis=2)

# Find rows with high brightness (text/UI elements)
print("Row brightness analysis (looking for content rows):")
row_means = gray.mean(axis=1)
for y in range(0, len(row_means), 10):
    bar = '#' * int(row_means[y] / 2)
    print(f"Row {y:4d}: mean={row_means[y]:5.1f} {bar}")

# Find vertical sections of content
print("\n\nLooking for the top bright bar:")
# Find where brightness drops below 30
bright = row_means > 40
in_bright = False
sections = []
start = 0
for y, b in enumerate(bright):
    if b and not in_bright:
        start = y
        in_bright = True
    elif not b and in_bright:
        sections.append((start, y-1))
        in_bright = False
if in_bright:
    sections.append((start, len(bright)-1))
print(f"Bright vertical sections: {sections[:10]}")

# Crop the top bar
top = img.crop((0, 0, 1600, 250))
top.save(r'C:\Users\user\Desktop\New folder\New folder\top.png')

# Crop middle area
mid = img.crop((0, 250, 1600, 500))
mid.save(r'C:\Users\user\Desktop\New folder\New folder\mid.png')

# Crop bottom
bot = img.crop((0, 500, 1600, 776))
bot.save(r'C:\Users\user\Desktop\New folder\New folder\bot.png')

# Also make a 2x upscaled contrast-enhanced version of top
top_arr = np.array(top)
# Invert if it's dark
enhanced = Image.fromarray(top_arr)
enhanced.save(r'C:\Users\user\Desktop\New folder\New folder\top_enhanced.png')

print("\nSaved crops: top.png, mid.png, bot.png")
