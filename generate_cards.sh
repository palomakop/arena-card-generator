#!/bin/zsh
# generate are.na idea cards

set -e  # exit on error

#!/bin/bash

echo "setting up python environment"
echo "================================"
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    
    # Install dependencies if requirements.txt exists
    if [ -f "requirements.txt" ]; then
        echo "Installing dependencies..."
        pip install -r requirements.txt
    fi
else
    source venv/bin/activate
fi

echo "generating are.na idea cards"
echo "================================"
echo ""

# step 1: download and process are.na data
echo "step 1: downloading and processing are.na data..."
python3 process_arena_data.py

echo ""

# step 2: generate typst layout
echo "step 2: generating typst layout..."
python3 generate_typst.py

echo ""

# step 3: compile to pdf (if typst is installed)
if command -v typst &> /dev/null; then
    echo "step 3: compiling pdf with typst..."
    typst compile output/cards.typ output/cards.pdf
    echo "pdf generated: output/cards.pdf"

    echo ""
    echo "step 4: generating card images (150dpi)..."
    mkdir -p output/card_images

    # compile single-card layout to PNG images
    typst compile output/cards_single.typ output/card_images/card_{n}.png --ppi 150

    # convert PNGs to JPEGs with multiply blend for paper color
    python3 -c "
from pathlib import Path
from PIL import Image, ImageChops

card_dir = Path('output/card_images')
png_files = sorted(card_dir.glob('*.png'))
print(f'  converting {len(png_files)} images to JPEG...')

for png_file in png_files:
    img = Image.open(png_file).convert('RGB')
    # multiply blend with paper color #f9f9f0
    paper = Image.new('RGB', img.size, (0xf9, 0xf9, 0xf0))
    result = ImageChops.multiply(img, paper)
    result.save(png_file.with_suffix('.jpg'), 'JPEG', quality=90)
    png_file.unlink()

print(f'  saved to output/card_images/')
"
else
    echo "typst not installed. skipping pdf and image compilation."
    echo "   install typst from: https://github.com/typst/typst"
    echo "   or compile manually: typst compile output/cards.typ output/cards.pdf"
fi

echo ""
echo "done!"
echo ""
echo "output files:"
echo "  - output/arena_data.json         (raw are.na data)"
echo "  - output/processed_blocks.json   (cleaned data)"
echo "  - output/images/                 (downloaded images)"
echo "  - output/cards.typ               (typst layout)"
echo "  - output/cards_single.typ        (single-card typst layout)"
if command -v typst &> /dev/null; then
    echo "  - output/cards.pdf               (printable pdf)"
    echo "  - output/card_images/            (individual card JPEGs + card_index.json)"
fi
