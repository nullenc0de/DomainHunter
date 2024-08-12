import socket
import requests
import json
import time
import sys
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_words(length):
    try:
        with open('/usr/share/dict/words', 'r') as f:
            return [word.strip().lower() for word in f if len(word.strip()) == length and word.strip().isalpha()]
    except FileNotFoundError:
        print("Word list not found. Please ensure you have a words file at /usr/share/dict/words")
        return []

def check_domain_dns(domain):
    try:
        socket.gethostbyname(domain)
        return False  # Domain resolves, likely registered
    except socket.gaierror:
        return True  # Domain doesn't resolve, potentially available

def check_domains_dns(domains):
    unresolved_domains = []
    with ThreadPoolExecutor(max_workers=50) as executor:
        future_to_domain = {executor.submit(check_domain_dns, domain): domain for domain in domains}
        for future in tqdm(as_completed(future_to_domain), total=len(domains), desc="DNS Check", unit="domain"):
            domain = future_to_domain[future]
            if future.result():
                unresolved_domains.append(domain)
    return unresolved_domains

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
        return result.get('available', False)  # If 'available' is True, the domain is available
    except requests.RequestException:
        pass
    except json.JSONDecodeError:
        pass
    
    return None

def main(word_length):
    words = get_words(word_length)
    if words:
        print(f"Checking {len(words)} {word_length}-letter words...")
        domains = [f"{word}.com" for word in words]
        unresolved_domains = check_domains_dns(domains)
        
        print(f"\nFound {len(unresolved_domains)} potentially available domains.")
        print("Validating potentially available domains...")
        available_domains = []
        
        with tqdm(total=len(unresolved_domains), desc="Checking availability", unit="domain") as pbar:
            for domain in unresolved_domains:
                is_available = check_domain_availability(domain)
                if is_available:
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
