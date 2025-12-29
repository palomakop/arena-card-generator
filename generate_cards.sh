#!/bin/zsh
# generate are.na idea cards

set -e  # exit on error

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
else
    echo "typst not installed. skipping pdf compilation."
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
if command -v typst &> /dev/null; then
    echo "  - output/cards.pdf               (printable pdf)"
fi
