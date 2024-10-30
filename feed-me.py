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
    try:
        unique_url = f"{url}&t={int(time.time())}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache'
        }
        response = requests.get(unique_url, headers=headers)

        if response.status_code == 200:
            with open(filename, 'w', encoding='utf-8') as file:
                file.write(response.text)
            print(f"Content saved to {filename}")
        else:
            print(f"Failed to retrieve the webpage: Status code {response.status_code}")
    except requests.RequestException as e:
        print(f"An error occurred: {e}")

def parse_rss_date(date_str):
    return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")

def is_within_time_range(post_date):
    pacific = pytz.timezone('US/Pacific')
    pt_now = datetime.now(pacific)
    yesterday_12 = (pt_now - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    today_12 = pt_now.replace(hour=12, minute=0, second=0, microsecond=0)
    post_date_pt = post_date.astimezone(pacific)
    return yesterday_12 <= post_date_pt <= today_12

def remove_unwanted_text(content):
    content = re.sub(r'<p>The post .+? appeared first on .+?\.?</p>', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'The post .+? appeared first on .+?\.?', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'<p>This entry was posted in .+? and tagged .+?\.?</p>', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'This entry was posted in .+? and tagged .+?\.?', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'Boing Boing is published under a Creative Commons license except where otherwise noted\.?', '', content, flags=re.IGNORECASE)
    return content.strip()

def process_feed(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        content = file.read()

    content = remove_unwanted_text(content)

    root = ET.fromstring(content)
    channel = root.find('channel')

    for item in channel.findall('item'):
        pub_date = item.find('pubDate').text
        post_date = parse_rss_date(pub_date)
        if not is_within_time_range(post_date):
            channel.remove(item)

    items_to_remove = []
    for item in channel.findall('item'):
        creator = item.find('{http://purl.org/dc/elements/1.1/}creator')
        if creator is not None and creator.text == "Boing Boing's Shop":
            items_to_remove.append(item)
    for item in items_to_remove:
        channel.remove(item)

    print(f"Removed {len(items_to_remove)} posts authored by Boing Boing's Shop.")

    for item in channel.findall('item'):
        content = item.find('{http://purl.org/rss/1.0/modules/content/}encoded')
        if content is not None:
            content.text = remove_unwanted_text(content.text)
        description = item.find('description')
        if description is not None:
            description.text = remove_unwanted_text(description.text)

    tree = ET.ElementTree(root)
    tree.write(filename, encoding='UTF-8', xml_declaration=True)

def format_date(date_str):
    dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
    pacific = pytz.timezone('US/Pacific')
    dt_pacific = dt.astimezone(pacific)
    return dt_pacific.strftime("%-I:%M %p PT %a %b %-d, %Y").replace("AM", "am").replace("PM", "pm")

def xml_to_webpage(xml_file, html_file):
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

        for p in soup.find_all('p'):
            if any(phrase in p.text.lower() for phrase in ['the post', 'appeared first on', 'this entry was posted', 'boing boing is published']):
                p.decompose()

        for img in soup.find_all('img'):
            caption = img.get('alt', '')
            src = img.get('src', '')

            # Create figure element
            figure = soup.new_tag('figure')
            
            # Create img tag
            new_img = soup.new_tag('img', src=src)
            figure.append(new_img)

            # Add figcaption if there's a caption
            if caption:
                figcaption = soup.new_tag('figcaption')
                figcaption.string = caption
                figure.append(figcaption)

            # Replace old structure with new figure
            if img.parent.name == 'a':
                img.parent.replace_with(figure)
            else:
                img.replace_with(figure)

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

    print(f"Conversion complete. Web page saved as {html_file}")

# Get the path to the desktop
desktop = os.path.join(os.path.expanduser('~'), 'Desktop')

# Define file paths
xml_file = os.path.join(desktop, 'feed.txt')
html_file = os.path.join(desktop, 'rss_webpage.html')

# Main execution
url = "https://boingboing.net/feed?_show_full_content=yes"

save_webpage_to_file(url, xml_file)
process_feed(xml_file)
xml_to_webpage(xml_file, html_file)

# Print the locations where files are saved
print(f"XML file saved to: {xml_file}")
print(f"HTML file saved to: {html_file}")