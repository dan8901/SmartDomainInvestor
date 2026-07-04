import subprocess
import csv
import re
import concurrent.futures
import threading
import time

# Thread-safe counter for progress
lock = threading.Lock()
checked = 0
total = 0

def to_domain(name):
    """Convert artist name to domain-friendly format. Returns None if invalid."""
    cleaned = name.strip()
    # Remove special characters that can't be in domains
    cleaned = re.sub(r"['\".,!?;:@&+#%*=(){}\[\]<>\\|`~^$]", "", cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if not cleaned or not re.match(r'^[a-zA-Z0-9]', cleaned):
        return None
    domain = cleaned.lower().replace(' ', '')
    domain = re.sub(r'[^a-z0-9-]', '', domain)
    domain = domain.strip('-')
    if not domain:
        return None
    return domain

def check_domain(domain):
    """
    Check if domain is taken. Conservative approach:
    Only mark as AVAILABLE if ALL signals confirm it's free.
    """
    full = f"{domain}.com"

    # 1. DNS: Check A, AAAA, and NS records
    # If ANY DNS record exists, domain is taken
    has_a = False
    has_ns = False
    has_mx = False

    try:
        r = subprocess.run(["dig", "+short", "A", full], capture_output=True, text=True, timeout=5)
        has_a = bool(r.stdout.strip())
    except:
        pass

    if not has_a:
        try:
            r = subprocess.run(["dig", "+short", "AAAA", full], capture_output=True, text=True, timeout=5)
            # AAAA without A is rare but still means taken
        except:
            pass

    try:
        r = subprocess.run(["dig", "+short", "NS", full], capture_output=True, text=True, timeout=5)
        output = r.stdout.strip()
        has_ns = bool(output)
    except:
        pass

    try:
        r = subprocess.run(["dig", "+short", "MX", full], capture_output=True, text=True, timeout=5)
        has_mx = bool(r.stdout.strip())
    except:
        pass

    if has_a or has_ns or has_mx:
        record_type = "NS" if has_ns else ("MX" if has_mx else "A")
        return f"TAKEN (DNS {record_type})"

    # 2. WHOIS: Check Verisign directly
    # For .com, verisign-grs.com is the authoritative registry
    try:
        r = subprocess.run(
            ["whois", "-h", "whois.verisign-grs.com", full],
            capture_output=True, text=True, timeout=10
        )
        output = r.stdout.lower()
    except:
        return "UNKNOWN"

    # If "Domain Name:" appears in the response, it's registered
    has_domain_name = "domain name:" in output

    # Check for explicit no-match signals
    no_match = any(x in output for x in [
        "no match for",
        "no match",
        "not found",
        "no data found",
        "no entries found",
        "the queried object does not exist",
    ])

    # Check for registrar/creation data (means registered)
    has_registrar = "registrar:" in output and "iana" not in output.split("registrar:")[1].split("\n")[0].lower()
    has_creation = "creation date:" in output
    has_updated = "updated date:" in output
    has_expiry = "registry expiry date:" in output

    # Count signals
    taken_signals = sum([has_domain_name, has_registrar, has_creation, has_updated, has_expiry])
    free_signals = 1 if no_match else 0

    if no_match and taken_signals == 0:
        return "AVAILABLE"
    elif taken_signals > 0:
        return "TAKEN (WHOIS)"
    else:
        # Inconclusive - default to TAKEN to avoid false positives
        return "TAKEN (WHOIS inconclusive)"

def process_row(row):
    """Process a single row from the CSV."""
    global checked
    name = row['name']
    domain = to_domain(name)

    if domain is None:
        return None, name  # Signal skip

    status = check_domain(domain)

    with lock:
        checked += 1
        if checked % 50 == 0:
            pct = checked*100//total
            # \r returns to start of line, spaces pad to clear leftover chars
            print(f"\rProgress: {checked}/{total} ({pct}%){' '*20}", end='', flush=True)

    return {
        'name': name,
        'domain': f"{domain}.com",
        'status': status,
        'genre': row.get('Genre', ''),
        'country': row.get('Country', ''),
        'monthly_listeners_m': row.get('Monthly Listeners (Millions)', '')
    }, None

# Read input CSV
rows = []
with open('/Users/allonnissim/Documents/SmartDomainInvestor/spotify_singers_vocalists_1m_plus.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

total = len(rows)
print(f"Processing {total} domains with parallel execution...\n")

start_time = time.time()

# Process in parallel using ThreadPoolExecutor
results = []
skipped = []

with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
    # Submit all tasks
    future_to_row = {executor.submit(process_row, row): row for row in rows}

    for future in concurrent.futures.as_completed(future_to_row):
        result, skip_name = future.result()
        if result:
            results.append(result)
        if skip_name:
            skipped.append(skip_name)

elapsed = time.time() - start_time
print()  # newline after progress bar

# Sort results by monthly listeners (descending)
results.sort(key=lambda x: float(x['monthly_listeners_m']) if x['monthly_listeners_m'] else 0, reverse=True)

print(f"\n{'='*50}")
print(f"Completed in {elapsed:.0f}s ({elapsed/60:.1f} minutes)")
print(f"Checked: {len(results)}")
print(f"Skipped (special chars): {len(skipped)}")
if skipped:
    print(f"Skipped names: {skipped}")

available = [r for r in results if 'AVAILABLE' in r['status']]
taken = [r for r in results if 'TAKEN' in r['status']]
unknown = [r for r in results if 'UNKNOWN' in r['status']]
print(f"\nSUMMARY: {len(taken)} TAKEN, {len(available)} AVAILABLE, {len(unknown)} UNKNOWN")

if available:
    print(f"\nAVAILABLE domains (sorted by listeners):")
    for r in available:
        print(f"  {r['domain']} - {r['name']} ({r['genre']}, {r['country']}, {r['monthly_listeners_m']}M listeners)")

# Write results CSV
with open('/Users/allonnissim/Documents/SmartDomainInvestor/spotify_singers_domain_check.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['name', 'domain', 'status', 'genre', 'country', 'monthly_listeners_m'])
    writer.writeheader()
    writer.writerows(results)

print(f"\nResults saved to spotify_singers_domain_check.csv")
