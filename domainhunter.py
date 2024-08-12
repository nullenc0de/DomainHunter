import subprocess
import requests
import json
import time
import sys

def get_words(length):
    try:
        with open('/usr/share/dict/words', 'r') as f:
            return [word.strip().lower() for word in f if len(word.strip()) == length and word.strip().isalpha()]
    except FileNotFoundError:
        print("Word list not found. Please ensure you have a words file at /usr/share/dict/words")
        return []

def check_domains_dns(words, batch_size=100):
    domains = [f"{word}.com" for word in words]
    resolved = set()
    
    for i in range(0, len(domains), batch_size):
        batch = domains[i:i+batch_size]
        command = f"echo {' '.join(batch)} | dnsx -silent -resp-only"
        result = subprocess.run(command, shell=True, text=True, capture_output=True)
        resolved.update(result.stdout.strip().split('\n'))
    
    return [domain for domain in domains if domain not in resolved]

def check_domain_availability(domain):
    url = 'https://partners.vpsvc.com/api/anonymous/v1/domain/search'
    params = {
        'locale': 'en-US',
        'source': 'domains-search-suggestions',
        'requestor': 'domains-pdp'
    }
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/json',
        'origin': 'https://www.vistaprint.com',
        'referer': 'https://www.vistaprint.com/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
    }
    data = {
        "domain": domain
    }
    
    try:
        response = requests.post(url, params=params, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        return not result.get('available', True)  # If 'available' is False, the domain is registered
    except requests.RequestException:
        pass
    except json.JSONDecodeError:
        pass
    
    return None

def main(word_length):
    words = get_words(word_length)
    if words:
        print(f"Checking {len(words)} {word_length}-letter words...")
        potentially_available = check_domains_dns(words)
        
        print(f"Found {len(potentially_available)} potentially available domains.")
        print("Validating potentially available domains...")
        print("Available domains:")
        
        available_count = 0
        for index, domain in enumerate(potentially_available, 1):
            is_registered = check_domain_availability(domain)
            if is_registered is False:
                print(f"{domain}")
                available_count += 1
            
            if index % 100 == 0:
                print(f"Checked {index}/{len(potentially_available)} domains. Found {available_count} so far.")
            
            time.sleep(1)  # Add a 1-second delay between requests
        
        print(f"\nSearch completed. Total available domains found: {available_count}")
    else:
        print(f"No {word_length}-letter words found. Please check your word list file.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 script_name.py <word_length>")
        print("Example: python3 script_name.py 7")
        sys.exit(1)
    
    try:
        word_length = int(sys.argv[1])
        if word_length < 1:
            raise ValueError
    except ValueError:
        print("Please provide a valid positive integer for word length.")
        sys.exit(1)
    
    main(word_length)
