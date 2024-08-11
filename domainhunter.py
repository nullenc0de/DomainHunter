import subprocess
import requests
import json
import time
from tqdm import tqdm

def get_five_letter_words():
    try:
        with open('/usr/share/dict/words', 'r') as f:
            return [word.strip().lower() for word in f if len(word.strip()) == 5 and word.strip().isalpha()]
    except FileNotFoundError:
        print("Word list not found. Please ensure you have a words file at /usr/share/dict/words")
        return []

def check_domains_dns(words):
    domains = [f"{word}.com" for word in words]
    command = f"echo {' '.join(domains)} | dnsx -silent -resp-only"
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    resolved = set(result.stdout.strip().split('\n'))
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

def main():
    words = get_five_letter_words()
    if words:
        print(f"Checking {len(words)} five-letter words...")
        potentially_available = check_domains_dns(words)
        
        print("Validating potentially available domains...")
        available_domains = []
        
        with tqdm(total=len(potentially_available), desc="Checking domains", unit="domain") as pbar:
            for domain in potentially_available:
                is_registered = check_domain_availability(domain)
                if is_registered is False:
                    available_domains.append(domain)
                pbar.update(1)
                time.sleep(1)  # Add a 1-second delay between requests
        
        if available_domains:
            print(f"\nFound {len(available_domains)} available domain(s):")
            for domain in available_domains:
                print(domain)
        else:
            print("\nNo available domains found.")
    else:
        print("No words found. Please check your word list file.")

if __name__ == "__main__":
    main()
