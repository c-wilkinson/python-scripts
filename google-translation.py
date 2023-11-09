import requests
from bs4 import BeautifulSoup

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

    # Make the request to Google Translate
    response = requests.get(url, params=payload)

    # Parse the response with BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the div with the 'swap-container' class
    swap_container = soup.find('div', class_='result-container')

    # Extract the text or other desired parts from the swap_container
    if swap_container:
        translated_text = swap_container.get_text()  # or any other method depending on what you need
    else:
        translated_text = "The result-container div was not found."

    return translated_text

# Example usage:
translated = scrape_google_translate("Hello, world!", "en", "fr")
print(translated)
