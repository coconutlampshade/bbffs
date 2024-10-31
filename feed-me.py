import requests
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import pytz
import re
from bs4 import BeautifulSoup
from html import unescape
import os

def save_webpage_to_file(url, filename):
    print(f"Attempting to download from {url}")
    try:
        unique_url = f"{url}&t={int(time.time())}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache'
        }
        response = requests.get(unique_url, headers=headers)
        response.raise_for_status()

        with open(filename, 'w', encoding='utf-8') as file:
            file.write(response.text)
        print(f"Successfully saved content to {filename}")
    except requests.RequestException as e:
        print(f"Error downloading webpage: {e}")
        raise

def parse_rss_date(date_str):
    try:
        return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
    except ValueError as e:
        print(f"Error parsing date {date_str}: {e}")
        raise

def is_within_time_range(post_date):
    pacific = pytz.timezone('US/Pacific')
    pt_now = datetime.now(pacific)
    yesterday_12 = (pt_now - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    today_12 = pt_now.replace(hour=12, minute=0, second=0, microsecond=0)
    post_date_pt = post_date.astimezone(pacific)
    return yesterday_12 <= post_date_pt <= today_12

def remove_unwanted_text(content):
    if not content:
        return ""
    content = re.sub(r'<p>The post .+? appeared first on .+?\.?</p>', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'The post .+? appeared first on .+?\.?', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'<p>This entry was posted in .+? and tagged .+?\.?</p>', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'This entry was posted in .+? and tagged .+?\.?', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'Boing Boing is published under a Creative Commons license except where otherwise noted\.?', '', content, flags=re.IGNORECASE)
    return content.strip()

def process_feed(filename):
    print(f"Processing feed from {filename}")
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            content = file.read()

        content = remove_unwanted_text(content)
        root = ET.fromstring(content)
        channel = root.find('channel')
        
        if channel is None:
            print("Error: Could not find channel element in RSS feed")
            return

        initial_item_count = len(channel.findall('item'))
        print(f"Found {initial_item_count} initial items")

        items_to_remove = []
        for item in channel.findall('item'):
            pub_date = item.find('pubDate')
            if pub_date is None or not pub_date.text:
                items_to_remove.append(item)
                continue
                
            try:
                post_date = parse_rss_date(pub_date.text)
                if not is_within_time_range(post_date):
                    items_to_remove.append(item)
            except ValueError:
                items_to_remove.append(item)

        for item in items_to_remove:
            channel.remove(item)

        print(f"Removed {len(items_to_remove)} posts outside time range")

        shop_posts = []
        for item in channel.findall('item'):
            creator = item.find('{http://purl.org/dc/elements/1.1/}creator')
            if creator is not None and creator.text == "Boing Boing's Shop":
                shop_posts.append(item)
        
        for item in shop_posts:
            channel.remove(item)

        print(f"Removed {len(shop_posts)} shop posts")

        for item in channel.findall('item'):
            content = item.find('{http://purl.org/rss/1.0/modules/content/}encoded')
            if content is not None:
                content.text = remove_unwanted_text(content.text)
            description = item.find('description')
            if description is not None:
                description.text = remove_unwanted_text(description.text)

        tree = ET.ElementTree(root)
        tree.write(filename, encoding='UTF-8', xml_declaration=True)
        print(f"Successfully processed feed. Final item count: {len(channel.findall('item'))}")

    except Exception as e:
        print(f"Error processing feed: {e}")
        raise

def format_date(date_str):
    try:
        dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
        pacific = pytz.timezone('US/Pacific')
        dt_pacific = dt.astimezone(pacific)
        return dt_pacific.strftime("%-I:%M %p PT %a %b %-d, %Y").replace("AM", "am").replace("PM", "pm")
    except ValueError as e:
        print(f"Error formatting date {date_str}: {e}")
        return date_str

def xml_to_webpage(xml_file, html_file):
    print(f"Converting {xml_file} to HTML")
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Boing Boing Feed</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; padding: 20px; max-width: 800px; margin: 0 auto; }
        h2 { color: #333; margin-top: 40px; }
        h6 { color: #666; font-weight: normal; margin-bottom: 10px; }
        .meta { font-size: 0.9em; color: #666; }
        article { border-bottom: 1px solid #eee; padding-bottom: 30px; margin-bottom: 30px; }
        img { max-width: 100%; height: auto; display: block; margin: auto; }
        figure { margin: 1em 0; padding: 0; }
        figcaption { color: #666; font-style: italic; text-align: center; margin-top: 0.5em; font-size: 0.9em; }
        .divider { border-top: 2px solid #ccc; margin: 40px 0; }
        .article-content { margin-top: 20px; }
        a { word-break: break-all; }
    </style>
</head>
<body>
"""

        current_time = datetime.now(pytz.UTC)
        html_content += f"<p>Generated on: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}</p>"

        namespaces = {
            'content': 'http://purl.org/rss/1.0/modules/content/',
            'dc': 'http://purl.org/dc/elements/1.1/'
        }

        items = root.findall('.//item')
        print(f"Processing {len(items)} items")

        for index, item in enumerate(items):
            html_content += "<article>"

            title = item.find('title')
            if title is not None:
                html_content += f"<h2>{title.text}</h2>"

            author = item.find('dc:creator', namespaces)
            if author is None:
                author = item.find('author')
            pub_date = item.find('pubDate')

            if author is not None and author.text and pub_date is not None:
                formatted_date = format_date(pub_date.text)
                html_content += f"<h6>{author.text} / {formatted_date}</h6>"

            content = item.find('content:encoded', namespaces)
            if content is not None:
                content_text = unescape(content.text)
            else:
                description = item.find('description')
                content_text = unescape(description.text) if description is not None else ""

            content_text = remove_unwanted_text(content_text)
            soup = BeautifulSoup(content_text, 'html.parser')

            # Remove unwanted paragraphs
            for p in soup.find_all('p'):
                if any(phrase in p.text.lower() for phrase in ['the post', 'appeared first on', 'this entry was posted', 'boing boing is published']):
                    p.decompose()

            # Clean up nested figures
            for figure in soup.find_all('figure'):
                if figure.find('figure'):
                    img = figure.find('img')
                    if img:
                        figure.replace_with(img)

            # Process YouTube embeds
            for iframe in soup.find_all('iframe', class_='youtube-player'):
                src = iframe.get('src', '')
                video_id = re.search(r'embed/([^?]+)', src)
                if video_id:
                    video_id = video_id.group(1)
                    # Find the parent figure element and replace it
                    figure = iframe.find_parent('figure')
                    if figure:
                        youtube_url = f'https://youtu.be/{video_id}\n'
                        figure.replace_with(youtube_url)
                    else:
                        # If no parent figure, replace just the iframe
                        iframe.replace_with(f'https://youtu.be/{video_id}\n')

            # Process all images
            for img in soup.find_all('img'):
                # Remove resize parameters from src URLs
                src = img.get('src', '')
                src = re.sub(r'\?resize=\d+%2C\d+', '', src)
                src = re.sub(r'&ssl=1', '', src)
                
                # Collect all possible caption sources
                caption_sources = []
                if img.get('alt'):
                    caption_sources.append(img['alt'])
                if img.get('title'):
                    caption_sources.append(img['title'])
                
                # Check for existing figcaption
                existing_figcaption = None
                if img.parent.name == 'figure':
                    existing_figcaption = img.parent.find('figcaption')
                    if existing_figcaption:
                        caption_sources.append(existing_figcaption.get_text())

                # Remove duplicate captions and empty strings
                captions = list(filter(None, caption_sources))
                captions = list(dict.fromkeys(captions))  # Remove duplicates while preserving order
                
                # Create new figure with caption if we have any caption text
                if captions:
                    figure = soup.new_tag('figure')
                    new_img = soup.new_tag('img', src=src)
                    figure.append(new_img)
                    
                    figcaption = soup.new_tag('figcaption')
                    figcaption.string = ' | '.join(captions)  # Join multiple captions with separator
                    figure.append(figcaption)
                    
                    # Replace the appropriate element
                    if img.parent.name == 'figure':
                        img.parent.replace_with(figure)
                    elif img.parent.name == 'a':
                        img.parent.replace_with(figure)
                    else:
                        img.replace_with(figure)
                else:
                    # If no caption, just clean up the img tag
                    new_img = soup.new_tag('img', src=src)
                    img.replace_with(new_img)

            html_content += str(soup)
            html_content += "</article>"

            if index < len(items) - 1:
                html_content += '<p> </p>'

        html_content += """
</body>
</html>
"""

        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"Successfully created HTML file: {html_file}")

    except Exception as e:
        print(f"Error converting to HTML: {e}")
        raise

if __name__ == "__main__":
    try:
        print("Starting RSS feed parser...")
        
        desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        xml_file = os.path.join(desktop, 'feed.txt')
        html_file = os.path.join(desktop, 'rss_webpage.html')
        
        print(f"Will save files to:")
        print(f"XML: {xml_file}")
        print(f"HTML: {html_file}")
        
        url = "https://boingboing.net/feed?_show_full_content=yes"
        
        print("Downloading RSS feed...")
        save_webpage_to_file(url, xml_file)
        
        print("Processing feed...")
        process_feed(xml_file)
        
        print("Converting to HTML...")
        xml_to_webpage(xml_file, html_file)
        
        print("Done!")
        
    except Exception as e:
        print(f"Fatal error: {e}")