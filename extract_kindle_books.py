import os
import csv
import xml.etree.ElementTree as ET

# Path to the XML file
xml_path = r'C:\Users\cawil\AppData\Local\Amazon\Kindle\Cache\KindleSyncMetadataCache.xml'

# Output CSV path (same directory as the script)
output_csv = os.path.join(os.path.dirname(__file__), 'kindle_books.csv')

# Parse the XML
tree = ET.parse(xml_path)
root = tree.getroot()

# Find all book metadata entries
books = root.findall('.//meta_data')

# Extract title and author(s) for each book
book_list = []
for book in books:
    title_elem = book.find('title')
    authors_elem = book.find('authors')
    if title_elem is not None and authors_elem is not None:
        title = title_elem.text.strip()
        authors = [a.text.strip() for a in authors_elem.findall('author') if a.text]
        author_str = ', '.join(authors)
        book_list.append((title, author_str))

# Write to CSV (with .csv extension but comma-separated)
with open(output_csv, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Title', 'Author'])
    writer.writerows(book_list)

print(f"Saved {len(book_list)} books to {output_csv}")
