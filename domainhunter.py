import socket
import json
import sys
import asyncio
import aiohttp
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
import logging
import string

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def is_ascii(s):
    return all(ord(c) < 128 for c in s)

def get_words(length):
    try:
        with open('/usr/share/dict/words', 'r', encoding='utf-8') as f:
            return [word.strip().lower() for word in f 
                    if len(word.strip()) == length 
                    and word.strip().isalpha() 
                    and is_ascii(word.strip())]
    except FileNotFoundError:
        logging.error("Word list not found. Please ensure you have a words file at /usr/share/dict/words")
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

async def check_domain_availability(session, domain, max_retries=3):
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
    
    for attempt in range(max_retries):
        try:
            async with session.post(url, params=params, headers=headers, json=data, timeout=10) as response:
                if response.status == 200:
                    result = await response.json()
                    is_available = result.get('available', False)
                    logging.debug(f"Domain {domain}: Available={is_available}")
                    return domain, is_available
                elif response.status == 429:  # Too Many Requests
                    wait_time = 2 ** attempt + random.random()
                    logging.warning(f"Rate limited. Waiting {wait_time:.2f} seconds before retrying {domain}")
                    await asyncio.sleep(wait_time)
                else:
                    logging.warning(f"Unexpected status code {response.status} for {domain}")
                    return domain, None
        except asyncio.TimeoutError:
            wait_time = 2 ** attempt + random.random()
            logging.warning(f"Timeout for {domain}. Waiting {wait_time:.2f} seconds before retrying")
            await asyncio.sleep(wait_time)
        except Exception as e:
            logging.error(f"Error checking {domain}: {str(e)}")
            return domain, None
    
    logging.error(f"Failed to check {domain} after {max_retries} attempts")
    return domain, None

async def check_domains_availability(domains):
    available_domains = []
    uncertain_domains = []
    async with aiohttp.ClientSession() as session:
        for domain in tqdm(domains, desc="Checking availability", unit="domain"):
            domain, is_available = await check_domain_availability(session, domain)
            if is_available:
                available_domains.append(domain)
            elif is_available is None:
                uncertain_domains.append(domain)
            await asyncio.sleep(0.1)  # Add a small delay between requests
    
    # Second pass for uncertain domains
    if uncertain_domains:
        logging.info(f"Rechecking {len(uncertain_domains)} uncertain domains")
        for domain in tqdm(uncertain_domains, desc="Rechecking uncertain domains", unit="domain"):
            domain, is_available = await check_domain_availability(session, domain)
            if is_available:
                available_domains.append(domain)
            await asyncio.sleep(0.1)
    
    return available_domains

async def main(word_length):
    words = get_words(word_length)
    if words:
        logging.info(f"Checking {len(words)} {word_length}-letter words...")
        domains = [f"{word}.com" for word in words]
        unresolved_domains = check_domains_dns(domains)
        
        logging.info(f"\nFound {len(unresolved_domains)} potentially available domains.")
        logging.info("Validating potentially available domains...")
        
        available_domains = await check_domains_availability(unresolved_domains)
        
        if available_domains:
            logging.info(f"\nFound {len(available_domains)} available domain(s):")
            for domain in available_domains:
                print(domain)
        else:
            logging.info("\nNo available domains found.")
    else:
        logging.warning(f"No {word_length}-letter words found. Please check your word list file.")

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
        logging.error("Please provide a valid positive integer for word length.")
        sys.exit(1)
    
    asyncio.run(main(word_length))
