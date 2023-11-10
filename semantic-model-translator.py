import os
import sys
import requests
from bs4 import BeautifulSoup
from xml.etree import ElementTree as ET
import time
from tqdm import tqdm

# Function to remove namespace in the passed document in place.
def remove_namespace(doc):
    for elem in doc.iter():
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]  # Removes namespace

# Function to scrape the Google translate mobile website
def scrape_google_translate(text, source_language, target_language):
    # Google Translate URL
    url = "https://translate.google.com/m"

    # Prepare the payload with the query parameters
    payload = {
        'hl': target_language,
        'q': text,
        'sl': source_language,
        'tl': target_language,
    }

    # Make the request to Google Translate with rate limiting
    while True:
        response = requests.get(url, params=payload)
        if response.status_code == 200:
            break
        elif response.status_code == 429:
            print("Rate limit exceeded. Waiting for 5 seconds...")
            time.sleep(5)
        else:
            response.raise_for_status()

    # Parse the response with BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the div with the 'result-container' class
    swap_container = soup.find('div', class_='result-container')

    # Extract the text or other desired parts from the swap_container
    if swap_container:
        translated_text = swap_container.get_text()  # or any other method depending on what you need
    else:
        translated_text = "The result-container div was not found."

    return translated_text

# Function to process an individual file
def process_file(file_path, file_progress_bar):
    # Parse the XML file
    tree = ET.parse(file_path)
    root = tree.getroot()
    remove_namespace(root)  # Call the function to remove namespaces

    # Count the total number of Localization elements in the file
    total_elements = sum(1 for _ in root.iter('Localization'))

    # Loop through each Localization element
    for i, localization in enumerate(root.iter('Localization')):
        culture = localization.get('Culture')
        if culture not in ['en-GB', 'en-US']:  # Skip default English localizations
            source_lang = 'en'  # Assuming the source language is English
            target_lang = culture[:2]  # Assuming the target language is the first two letters of the culture code
            try:
                # Attempt to translate the text using the new scrape function
                translated_text = scrape_google_translate(localization.text, source_lang, target_lang)
                localization.text = translated_text
            except AttributeError as e:  # Catching attribute errors specifically
                print(f"Translation service error for {culture}: {e}")
            except Exception as e:  # Catching all other exceptions
                print(f"General error translating {culture}: {e}")

            # Update element-level progress bar
            file_progress_bar.update(1)

    # Write back to file
    ET.register_namespace('', '')  # Register an empty namespace
    tree.write(file_path, encoding='utf-8', xml_declaration=True)

# Main function to process files within a directory
def main(root_directory):
    for subdir, dirs, files in os.walk(root_directory):
        for file in files:
            if file.endswith(".sm"):
                file_path = os.path.join(subdir, file)

                # Initialize file-level progress bar
                file_progress_bar = tqdm(desc=f"Processing {file}", unit=" element", total=0)

                process_file(file_path, file_progress_bar)

                # Close the file-level progress bar
                file_progress_bar.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <root_directory>")
        sys.exit(1)
    main(sys.argv[1])