#!/usr/bin/env python3
"""
generate typst cards layout from processed are.na blocks.
"""

import json
import sys
from pathlib import Path

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False
    print("warning: couldn't see qrcode[pil] installed. qr codes will be skipped.")


# load configuration
def load_config():
    """load configuration from config.json file."""
    config_path = Path(__file__).parent / 'config.json'
    if not config_path.exists():
        print("error: config.json not found. copy config_EXAMPLE.json to config.json and update it.")
        sys.exit(1)
    with open(config_path, 'r') as f:
        return json.load(f)

CONFIG = load_config()

def generate_qr_code(block_id, output_dir):
    """generate a qr code for the are.na block url."""
    if not HAS_QRCODE:
        return None

    url = f"https://www.are.na/block/{block_id}"

    # create qr code
    qr = qrcode.QRCode(
        version=1,  # small size
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=2,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # generate image
    img = qr.make_image(fill_color="black", back_color="white")

    # save to qrcodes directory
    qr_dir = Path(output_dir) / "qrcodes"
    qr_dir.mkdir(exist_ok=True)

    qr_path = qr_dir / f"{block_id}.png"
    img.save(qr_path)

    return f"qrcodes/{block_id}.png"

def escape_typst_string(text):
    """escape special characters for typst strings."""
    if not text:
        return ""
    # escape backslashes first
    text = text.replace('\\', '\\\\')
    # escape quotes
    text = text.replace('"', '\\"')
    # escape hash (for typst markup)
    text = text.replace('#', '\\#')
    return text

def format_content_as_typst(content):
    """convert markdown content to typst markup."""
    if not content:
        return ""

    lines = content.split('\n')
    formatted_lines = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        # convert markdown headings to typst text formatting
        if stripped.startswith('# '):
            # remove the # and make it bold/larger (13pt)
            text = stripped[2:]  # remove "# "
            # note: we escape text here even though it goes inside [...] because
            # special chars like # still need escaping in typst content blocks
            formatted_lines.append(f'      #text(weight: "bold", size: 13pt)[{escape_typst_string(text)}]')
        elif stripped.startswith('## '):
            # 12pt
            text = stripped[3:]  # remove "## "
            formatted_lines.append(f'      #text(weight: "bold", size: 12pt)[{escape_typst_string(text)}]')
        elif stripped.startswith('### '):
            # 11pt
            text = stripped[4:]  # remove "### "
            formatted_lines.append(f'      #text(weight: "bold", size: 11pt)[{escape_typst_string(text)}]')
        elif stripped == '':
            # preserve empty lines as paragraph breaks
            formatted_lines.append('')
        elif stripped.startswith('- ') or stripped.startswith('* '):
            # list items - don't add linebreak after (typst handles list spacing)
            formatted_lines.append('      ' + escape_typst_string(line))
        else:
            # regular text - add linebreak after each line to preserve newlines
            formatted_lines.append('      ' + escape_typst_string(line))
            # don't add linebreak if next line is a list item or empty
            if i + 1 < len(lines):
                next_stripped = lines[i + 1].strip()
                if not next_stripped.startswith('-') and not next_stripped.startswith('*') and next_stripped != '':
                    formatted_lines.append('      #linebreak()')

    # remove trailing linebreak if present
    if formatted_lines and formatted_lines[-1] == '      #linebreak()':
        formatted_lines.pop()

    return '\n'.join(formatted_lines)

def generate_card(block, images_dir, output_dir):
    """generate typst code for a single card."""
    card_parts = []

    block_id = block.get('id')

    # title
    title = block.get('title')
    if title:
        card_parts.append(f'    title: "{escape_typst_string(title)}",')

    # image or content
    image_file = block.get('image_file')
    content = block.get('content')

    if image_file:
        # use relative path from typst file to images
        # images_dir is a Path object, get just the directory name
        images_subdir = Path(images_dir).name
        image_path = f"{images_subdir}/{image_file}"
        card_parts.append(f'    img-path: "{image_path}",')
    elif content:
        # format content as typst markup
        typst_content = format_content_as_typst(content)
        # use raw strings for content blocks
        card_parts.append(f'    content: [\n{typst_content}\n    ],')

    # source url
    source_url = block.get('source_url')
    if source_url:
        # truncate long urls for display
        max_url_length = 80
        if len(source_url) > max_url_length:
            display_url = source_url[:max_url_length] + '...'
        else:
            display_url = source_url

        card_parts.append(f'    source-url: "{escape_typst_string(source_url)}",')
        card_parts.append(f'    source-url-display: "{escape_typst_string(display_url)}",')

    # channels (always present)
    channels = block.get('channels', [])
    channels_str = ', '.join([f'"{escape_typst_string(c)}"' for c in channels])
    # add trailing comma for single element to ensure it's a tuple in typst
    if len(channels) == 1:
        card_parts.append(f'    channels: ({channels_str},),')
    else:
        card_parts.append(f'    channels: ({channels_str}),')

    # generate qr code
    if HAS_QRCODE and block_id:
        qr_path = generate_qr_code(block_id, output_dir)
        if qr_path:
            card_parts.append(f'    qr-code: "{qr_path}",')

    # build the card
    card_code = "  card(\n" + '\n'.join(card_parts) + "\n  )"
    return card_code

def generate_typst_file(blocks_file, images_dir, output_file):
    """generate complete typst file from blocks data."""

    # load blocks
    with open(blocks_file, 'r') as f:
        blocks = json.load(f)

    print(f"generating typst layout for {len(blocks)} blocks...")

    # generate typst header
    typst_code = '''// generated cards from are.na data

#set page(
  width: 8.5in,
  height: 11in,
  margin: 0.5in,
)

#set text(
  font: "Arial",
  size: 11pt,
)

// card dimensions - 4 per page (2x2 grid)
#let card-width = 3.5in
#let card-height = 4.5in
#let card-gap = 0.25in

// card component
#let card(
  title: none,
  img-path: none,
  content: none,
  source-url: none,
  source-url-display: none,
  channels: (),
  qr-code: none,
) = {
  // calculate image height based on whether source url exists
  let img-height = if source-url != none { 2in } else { 2.5in }

  box(
    width: card-width,
    height: card-height,
    stroke: 0.5pt + luma(225),
    inset: 0.3in,
  )[
    #v(0pt)

    // title at top (if exists)
    #if title != none [
      #text(weight: "bold", size: 12pt)[#title]
      #v(0.1in)
    ]

    // content area - image or text
    #if img-path != none [
      // image with contain fit - full width, conditional height
      #box(
        width: 100%,
        height: img-height,
      )[
        #align(center + horizon)[
          #image(img-path, fit: "contain", width: 100%, height: 100%)
        ]
      ]
    ] else if content != none [
      // rich text content
      #align(left + top)[
        #content
      ]
    ]

    #v(1fr) // push everything below to bottom

    // source url (if exists)
    #if source-url != none [
      #v(0.1in)
      #text(size: 9pt, fill: blue)[
        #link(source-url)[#if source-url-display != none [#source-url-display] else [#source-url]]
      ]
    ]

    #v(0.1in)

    // footer with channels and qr code
    #line(length: 100%, stroke: 0.5pt + luma(200))
    #v(0.05in)
    #grid(
      columns: (1fr, auto),
      align: (left + top, right),
      text(size: 9pt, fill: gray)[
        #channels.map(ch => [● #ch]).join(linebreak())
      ],
      if qr-code != none [
        #image(qr-code, width: 0.4in, height: 0.4in, scaling: "pixelated")
      ]
    )
  ]
}

// generate cards
'''

    # prepare output path
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # generate cards in groups of 4 (2x2 grid per page)
    cards_per_page = 4
    for i in range(0, len(blocks), cards_per_page):
        page_blocks = blocks[i:i + cards_per_page]

        # generate grid for this page
        typst_code += "\n#grid(\n"
        typst_code += "  columns: 2,\n"
        typst_code += "  rows: 2,\n"
        typst_code += "  column-gutter: card-gap,\n"
        typst_code += "  row-gutter: card-gap,\n"
        typst_code += "  \n"

        # generate each card
        card_codes = [generate_card(block, images_dir, output_path.parent) for block in page_blocks]
        typst_code += ",\n".join(card_codes)

        typst_code += "\n)\n"

        # add page break if not last page
        if i + cards_per_page < len(blocks):
            typst_code += "\n#pagebreak()\n"

    # write to file
    with open(output_path, 'w') as f:
        f.write(typst_code)

    print(f"generated typst file: {output_path}")
    print(f"  total cards: {len(blocks)}")
    print(f"  pages: {(len(blocks) + cards_per_page - 1) // cards_per_page}")

    return output_path

if __name__ == "__main__":
    output_dir = Path(CONFIG['output_dir'])
    blocks_file = output_dir / CONFIG['processed_data_filename']
    images_dir = output_dir / CONFIG['images_dir']
    output_file = output_dir / CONFIG['output_typst_file']

    if not blocks_file.exists():
        print(f"error: {blocks_file} not found. run process_arena_data.py first.")
        sys.exit(1)

    generate_typst_file(str(blocks_file), str(images_dir), str(output_file))