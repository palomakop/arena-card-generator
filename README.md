# are.na card generator

have you ever wanted to take all of the blocks in your are.na channels and bring them into meatspace by printing them all out as little cards?

well, probably not, since that is an oddly specific wish. but i did! i enjoy using are.na to organize my thoughts and ideas. but sometimes i need to think away from a screen. i wanted to be able to carry my ideas with me, and interact with them in a tactile way.

now i'm sharing the code i used to generate my cards, in case you want to try it too. i'll do my best to document the instructions below!

this isn't really fully baked because i stopped working on it as soon as i got it to output cards for my specific are.na content. it's not generalized to work for long text blocks, or other content i didn't happen to have in my own channels. there are a few improvements i want to make for my own use cases, but i hope it can be helpful to someone else too, even in its half baked state.

## example output

here are some images of example pages of my PDF output.

### image blocks:
![](/examples/images.jpg)

### link blocks or images with source url:
![](/examples/links.jpg)

### text blocks with markdown formatting:
![](/examples/markdown_text.jpg)

## dependencies

1. **python 3** (already installed on many systems)
2. **typst** - see [installation instructions](https://github.com/typst/typst?tab=readme-ov-file#installation)
3. **python library for generating QR codes**:
   ```bash
   pip3 install "qrcode[pil]"
   ```
4. **are.na personal access token**
   - sign into https://dev.are.na
   - create a new application or use an existing one
   - copy your personal access token

*note: if this was a "real" application i'd give you a way to authorize it by logging in, but i haven't done that, so you need to make a "dummy" application to get your personal access token.*

## setup

1. duplicate the `config_EXAMPLE.json` file and rename it to be called `config.json`
   ```
   cp config_EXAMPLE.json config.json
   ```

2. update `config.json` with your are.na credentials:
   ```json
   {
     "arena_user_slug": "your-arena-username",
     "arena_personal_token": "your-personal-access-token-here",
     ...
   }
   ```

*note: if you're not sure of your are.na username, go to your profile on are.na and look at the url. it will look something like: `https://www.are.na/your-name/channels`. in this example `your-name` would be the user slug.*

### optional: filter by date

if you want to only generate cards for blocks that are new or recently updated (useful if you've already printed cards before and want to print only new ones), you can set a minimum date in `config.json`:

```json
{
  ...
  "min_updated_date": "2025-12-20T00:00:00.000Z"
}
```

this will only include blocks where either the `updated_at` or `connected_at` date (whichever is more recent) is after the date you specify. blocks older than this date will be excluded from the cards generated.

to disable filtering and include all blocks, set it to `null`:

```json
{
  ...
  "min_updated_date": null
}
```

the date format is ISO 8601 (the same format are.na uses). you can find recent block dates by looking in `output/arena_data.json` after running the script once.

## run it

in your command line, `cd` to the folder where you downloaded this code and run the script like this:
### 
```bash
./generate_cards.sh
```

this will:
- download a payload from are.na of all your channels
- organize all of the blocks and their important data into a new JSON file
   *note: blocks that appear in more than one channel are only included once*
- download all the original quality images of the blocks into a folder
- generate a typst layout file (`.typ`)
- if the QR code library is installed, it will make little QR codes that link to the blocks on are.na so you can jump back into the digital realm if you need to (useful for video and link blocks that lead to more material that we can't include in the card)
- use typst to compile the layout into an actual PDF that you can print out

you should get a file called `cards.pdf` that will be the actual printable file. if you want each card to be separate, make sure to print them single-sided!

### step by step

if you want to run steps individually:

1. download and process are.na data
```bash
python3 process_arena_data.py
```

2. generate typst layout
```bash
python3 generate_typst.py
```

3. compile to PDF
```
typst compile output/cards.typ output/cards.pdf
```

## output

all files are created in the `output/` directory:

- `arena_data.json` - raw API response from are.na
- `processed_blocks.json` - cleaned and deduplicated blocks
- `images/` - all downloaded images (named by block ID)
- `cards.typ` - typst source file
- `cards.pdf` - printable PDF file

## card layout

each card contains:
- **title** (if exists - cards with the title "Untitled" are treated as having no title)
- **content area** - square space with either:
  - image (fit to contain)
  - text content (rendered as markdown)
- **source URL** (if exists)
- **footer** - channel names and QR code

cards are designed to print 4 per page on 8.5x11" paper with 0.5" margins.

### ⚠️ big caveats here about the layout not being generalized!

i made these to work with **my specific are.na content**, which is mostly images and very short text snippets. if you have longer texts inside text blocks, it will probably overflow and mess things up, so you'd have to decide how to handle that (truncate? make text smaller or cards bigger? or something else??) some customization options are below but not exhaustive.

## customization

### card dimensions
edit in `generate_typst.py`:
```python
#let card-width = 3.5in
#let card-height = 4.5in
#let card-gap = 0.25in
```

### fonts and styling
edit the typst template section in `generate_typst.py` to change:
- font family
- font sizes
- colors
- spacing


## notes

- even though the API response to GET a channel from are.na contains block data, i am still doing a GET for each block individually, because i found that those requests contained fresher data (such as recently updated text block contents)
- markdown -> typst is not fully implemented, just some codes (headings, lists)... could be improved but i probably will just do as needed


## ideas

- i would like to add the ability to exclude specific channels from the output
   - maybe this could be part of an interactive prompt that shows a numbered list of channels and lets you type the ones to exclude