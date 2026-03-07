#!/usr/bin/env python3
"""
download and process are.na data: deduplicate blocks, download images, create json list of all blocks
"""

import json
import os
import ssl
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
import urllib.request
import html
from datetime import datetime

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
API_DELAY = CONFIG['api_delay_seconds']
MAX_RETRIES = CONFIG['max_retries']

def api_request(url, token):
    """make an API request with retries for transient errors."""
    req = urllib.request.Request(url)
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('User-Agent', 'ArenaCardGenerator/1.0')

    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                # rate limited - don't retry, just fail
                raise
            elif attempt < MAX_RETRIES - 1:
                print(f"    retry {attempt + 1}/{MAX_RETRIES} after HTTP {e.code}")
                time.sleep(API_DELAY)
            else:
                raise
        except (urllib.error.URLError, ssl.SSLError, ConnectionResetError, TimeoutError) as e:
            if attempt < MAX_RETRIES - 1:
                print(f"    retry {attempt + 1}/{MAX_RETRIES} after connection error: {e}")
                time.sleep(API_DELAY)
            else:
                raise

    return None

def download_arena_data(user_slug, token, output_path):
    """download user's channels data from are.na api."""

    # first, get the list of channels
    channels_url = f"https://api.are.na/v3/users/{user_slug}/contents?type=Channel&per=100"
    print(f"downloading channel list for user: {user_slug}")

    try:
        channels_data = api_request(channels_url, token)
        time.sleep(API_DELAY)
    except Exception as e:
        print(f"error downloading channel list: {e}")
        sys.exit(1)

    # fetch each channel to get block IDs and build block->channels mapping
    # v3 API uses 'data' key for results
    channels_list = channels_data.get('data', [])
    print(f"fetching block IDs from {len(channels_list)} channels...")
    block_to_channels = {}  # maps block_id -> list of channel titles

    for i, channel in enumerate(channels_list, 1):
        channel_slug = channel.get('slug')
        channel_title = channel.get('title', 'Untitled')

        if not channel_slug:
            continue

        print(f"  [{i}/{len(channels_list)}] {channel_title}")

        # fetch channel contents to get block IDs
        # use per=100 to get up to 100 blocks per page (API default is 20)
        channel_url = f"https://api.are.na/v3/channels/{channel_slug}/contents?per=100"

        try:
            channel_data = api_request(channel_url, token)
        except Exception as e:
            print(f"    warning: failed to download {channel_title}: {e}")
            time.sleep(API_DELAY)
            continue

        time.sleep(API_DELAY)

        # v3 returns contents in 'data' key with pagination info in 'meta'
        contents = channel_data.get('data', [])
        meta = channel_data.get('meta', {})
        has_more_pages = meta.get('has_more_pages', False)
        blocks_received = len(contents)

        # collect block IDs from first page
        for block in contents:
            block_id = block.get('id')
            if block_id:
                if block_id not in block_to_channels:
                    block_to_channels[block_id] = []
                if channel_title not in block_to_channels[block_id]:
                    block_to_channels[block_id].append(channel_title)

        # fetch remaining pages if needed
        page = 2
        while has_more_pages:
            print(f"    fetching page {page}...")
            page_url = f"https://api.are.na/v3/channels/{channel_slug}/contents?per=100&page={page}"

            try:
                page_data = api_request(page_url, token)
            except Exception as e:
                print(f"    warning: failed to fetch page {page}: {e}")
                time.sleep(API_DELAY)
                break

            time.sleep(API_DELAY)

            page_contents = page_data.get('data', [])
            meta = page_data.get('meta', {})
            has_more_pages = meta.get('has_more_pages', False)

            if not page_contents:
                break

            # collect block IDs from this page
            for block in page_contents:
                block_id = block.get('id')
                if block_id:
                    if block_id not in block_to_channels:
                        block_to_channels[block_id] = []
                    if channel_title not in block_to_channels[block_id]:
                        block_to_channels[block_id].append(channel_title)

            blocks_received += len(page_contents)
            print(f"    page {page}: +{len(page_contents)} blocks ({blocks_received} total)")
            page += 1

    # now fetch each unique block individually
    unique_block_ids = list(block_to_channels.keys())
    print(f"\nfetching {len(unique_block_ids)} unique blocks from blocks API...")

    blocks = []
    for i, block_id in enumerate(unique_block_ids, 1):
        if i % 10 == 0 or i == len(unique_block_ids):
            print(f"  [{i}/{len(unique_block_ids)}] fetching block {block_id}")

        block_url = f"https://api.are.na/v3/blocks/{block_id}"

        try:
            block_data = api_request(block_url, token)
            # add channel membership to block data
            block_data['channel_titles'] = block_to_channels[block_id]
            blocks.append(block_data)
        except Exception as e:
            print(f"    warning: failed to fetch block {block_id}: {e}")

        time.sleep(API_DELAY)

    # save raw data in new format
    data = {'blocks': blocks}
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"downloaded data saved to: {output_path}")
    return data

def download_image(url, output_dir, block_id, filename):
    """download an image from url to output directory."""
    # create safe filename using block_id and original filename
    ext = Path(filename).suffix
    safe_filename = f"{block_id}{ext}"
    output_path = output_dir / safe_filename

    # skip if already downloaded and file has content
    if output_path.exists() and output_path.stat().st_size > 0:
        print(f"  already exists: {safe_filename} ({output_path.stat().st_size} bytes)")
        return safe_filename

    try:
        print(f"  downloading: {safe_filename} from {url}")

        # use urlopen for better control and error handling
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')  # some servers require this

        with urllib.request.urlopen(req, timeout=30) as response:
            # read the data
            data = response.read()

            # check if we got data
            if not data:
                print(f"  warning: no data received for {safe_filename}")
                return None

            # detect actual file type from magic bytes and correct extension if needed
            actual_ext = None
            if data.startswith(b'\x89PNG\r\n\x1a\n'):
                actual_ext = '.png'
            elif data.startswith(b'\xff\xd8\xff'):
                actual_ext = '.jpg'
            elif data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
                actual_ext = '.gif'
            elif data.startswith(b'RIFF') and b'WEBP' in data[:20]:
                actual_ext = '.webp'

            # if detected type differs from filename extension, use correct one
            if actual_ext and actual_ext.lower() != ext.lower():
                print(f"    note: file is actually {actual_ext}, not {ext}")
                safe_filename = f"{block_id}{actual_ext}"
                output_path = output_dir / safe_filename

            # write to file
            with open(output_path, 'wb') as f:
                f.write(data)

            file_size = output_path.stat().st_size
            print(f"  downloaded {safe_filename} ({file_size} bytes)")
            return safe_filename

    except urllib.error.HTTPError as e:
        print(f"  http error {e.code} downloading {safe_filename}: {e.reason}")
        # clean up empty file if it was created
        if output_path.exists() and output_path.stat().st_size == 0:
            output_path.unlink()
        return None
    except urllib.error.URLError as e:
        print(f"  url error downloading {safe_filename}: {e.reason}")
        if output_path.exists() and output_path.stat().st_size == 0:
            output_path.unlink()
        return None
    except Exception as e:
        print(f"  error downloading {safe_filename}: {e}")
        if output_path.exists() and output_path.stat().st_size == 0:
            output_path.unlink()
        return None

def process_arena_data(data, output_dir, images_subdir, min_updated_date=None):
    """process are.na json data and download images."""

    # parse min_updated_date if provided
    min_datetime = None
    if min_updated_date:
        try:
            min_datetime = datetime.fromisoformat(min_updated_date.replace('Z', '+00:00'))
            print(f"filtering blocks updated after: {min_updated_date}")
        except ValueError as e:
            print(f"warning: invalid min_updated_date format '{min_updated_date}': {e}")
            print("expected format: 2025-12-20T00:00:00.000Z")

    # create output directory for images
    images_dir = Path(output_dir) / images_subdir
    images_dir.mkdir(parents=True, exist_ok=True)

    # list to store processed blocks
    blocks_list = []
    filtered_count = 0

    print(f"\nprocessing {len(data.get('blocks', []))} blocks...")

    # process each block
    for block in data.get('blocks', []):
        block_id = block.get('id')

        # skip if no id
        if not block_id:
            continue

        # get channel titles from the block data
        channel_titles = block.get('channel_titles', [])

        # filter by date if min_datetime is set
        # check both updated_at and connected_at, use whichever is more recent
        if min_datetime:
            block_date = None

            # check updated_at
            updated_at_str = block.get('updated_at')
            if updated_at_str:
                try:
                    updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
                    block_date = updated_at
                except ValueError:
                    pass

            # check connected_at
            connected_at_str = block.get('connected_at')
            if connected_at_str:
                try:
                    connected_at = datetime.fromisoformat(connected_at_str.replace('Z', '+00:00'))
                    # use the more recent of the two dates
                    if block_date is None or connected_at > block_date:
                        block_date = connected_at
                except ValueError:
                    pass

            # filter if block_date exists and is older than min_datetime
            if block_date and block_date < min_datetime:
                filtered_count += 1
                continue

        # get title - treat "Untitled" as no title (since that is the default generated title in are.na)
        title = block.get('title', '') or block.get('generated_title', '')
        if title == 'Untitled':
            title = None
        elif title:
            # decode html entities in title
            title = html.unescape(title)

        # get author info
        user = block.get('user', {})
        author_slug = user.get('slug', '')

        # get source url
        source = block.get('source')
        source_url = source.get('url') if isinstance(source, dict) else None

        # create new block entry
        block_data = {
            'id': block_id,
            'channels': channel_titles,
            'author': author_slug
        }

        # add optional fields
        if title:
            block_data['title'] = title
        if source_url:
            block_data['source_url'] = source_url

        # handle image if present (for image, media, link, attachment types)
        image = block.get('image')
        if image and isinstance(image, dict):
            # v3 uses 'src' directly, v2 used 'original.url'
            image_url = image.get('src') or image.get('original', {}).get('url')
            filename = image.get('filename', 'image')

            if image_url:
                block_data['image_url'] = image_url
                downloaded_filename = download_image(
                    image_url,
                    images_dir,
                    block_id,
                    filename
                )
                if downloaded_filename:
                    block_data['image_file'] = downloaded_filename

        # handle text content (for text blocks)
        content = block.get('content')
        if content:
            # v3 API returns content as dict with markdown/html/plain keys
            if isinstance(content, dict):
                content = content.get('markdown') or content.get('plain') or ''
            if content:
                # decode html entities (e.g., &gt; -> >, &lt; -> <, &amp; -> &)
                block_data['content'] = html.unescape(content)

        blocks_list.append(block_data)

    # save processed data
    output_file = Path(output_dir) / CONFIG['processed_data_filename']
    with open(output_file, 'w') as f:
        json.dump(blocks_list, f, indent=2)

    print(f"\nprocessed {len(blocks_list)} unique blocks")
    if filtered_count > 0:
        print(f"filtered out {filtered_count} blocks (older than {min_updated_date})")
    print(f"saved to: {output_file}")

    return blocks_list

if __name__ == "__main__":
    # get personal access token from config
    token = CONFIG.get('arena_access_token')
    if not token:
        print("error: arena_access_token not set in config.json")
        print("create a personal access token at https://are.na/settings/tokens")
        sys.exit(1)

    # setup paths
    output_dir = Path(CONFIG['output_dir'])
    output_dir.mkdir(exist_ok=True)

    raw_data_path = output_dir / CONFIG['raw_data_filename']

    # download data from are.na api
    data = download_arena_data(CONFIG['arena_user_slug'], token, raw_data_path)

    # process data and download images
    min_updated_date = CONFIG.get('min_updated_date')
    process_arena_data(data, output_dir, CONFIG['images_dir'], min_updated_date)
