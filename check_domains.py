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
whois_counter = 0
whois_lock = threading.Lock()

def to_domain(name):
    """Convert name to domain-friendly format. Returns None if invalid."""
    cleaned = name.strip()
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
    Only mark as AVAILABLE if WHOIS explicitly confirms no match.
    Empty/short WHOIS responses = TAKEN (rate limit protection).
    """
    full = f"{domain}.com"

    # 1. DNS: Check NS records first (most reliable indicator of registration)
    has_ns = False
    has_a = False
    has_mx = False

    try:
        r = subprocess.run(["dig", "+short", "NS", full], capture_output=True, text=True, timeout=5)
        has_ns = bool(r.stdout.strip())
    except:
        pass

    if not has_ns:
        try:
            r = subprocess.run(["dig", "+short", "A", full], capture_output=True, text=True, timeout=5)
            has_a = bool(r.stdout.strip())
        except:
            pass

    if not has_ns and not has_a:
        try:
            r = subprocess.run(["dig", "+short", "MX", full], capture_output=True, text=True, timeout=5)
            has_mx = bool(r.stdout.strip())
        except:
            pass

    if has_ns or has_a or has_mx:
        record_type = "NS" if has_ns else ("MX" if has_mx else "A")
        return f"TAKEN (DNS {record_type})"

    # 2. WHOIS: Check Verisign directly with rate limit protection
    global whois_counter
    with whois_lock:
        whois_counter += 1
        local_count = whois_counter

    # Stagger WHOIS requests to avoid rate limiting
    time.sleep(0.15 * (local_count % 10))

    try:
        r = subprocess.run(
            ["whois", "-h", "whois.verisign-grs.com", full],
            capture_output=True, text=True, timeout=15
        )
        output = r.stdout.lower().strip()
    except:
        return "TAKEN (WHOIS error)"

    # Rate limit protection: if response is too short, treat as taken
    if len(output) < 50:
        return "TAKEN (WHOIS rate limited)"

    # Explicit no-match signals
    no_match = any(x in output for x in [
        "no match for",
        "not found",
        "no data found",
        "no entries found",
        "the queried object does not exist",
    ])

    # Taken signals
    has_domain_name = "domain name:" in output
    has_creation = "creation date:" in output
    has_updated = "updated date:" in output
    has_expiry = "registry expiry date:" in output

    taken_signals = sum([has_domain_name, has_creation, has_updated, has_expiry])

    # Only mark available if explicit no-match AND zero taken signals
    if no_match and taken_signals == 0:
        return "AVAILABLE"
    elif taken_signals > 0:
        return "TAKEN (WHOIS)"
    else:
        # No clear signals either way - conservative = TAKEN
        return "TAKEN (WHOIS inconclusive)"

def process_row(row):
    """Process a single row from the CSV."""
    global checked
    name = row.get('name', row.get('channel_name', ''))
    domain = to_domain(name)

    if domain is None:
        return None, name

    status = check_domain(domain)

    with lock:
        checked += 1
        if checked % 50 == 0:
            pct = checked*100//total
            print(f"\rProgress: {checked}/{total} ({pct}%){' '*20}", end='', flush=True)

    result = {
        'name': name,
        'domain': f"{domain}.com",
        'status': status,
    }
    # Add any extra columns from the input
    for key in row:
        if key not in result:
            result[key] = row[key]

    return result, None

# --- Config ---
INPUT_CSV = '/Users/allonnissim/Documents/SmartDomainInvestor/5_words.csv'
OUTPUT_CSV = '/Users/allonnissim/Documents/SmartDomainInvestor/domain_check_results.csv'
MAX_WORKERS = 15

# Read input CSV
rows = []
with open(INPUT_CSV, 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

total = len(rows)
print(f"Processing {total} domains with {MAX_WORKERS} parallel workers...\n")

start_time = time.time()

results = []
skipped = []

with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    future_to_row = {executor.submit(process_row, row): row for row in rows}
    for future in concurrent.futures.as_completed(future_to_row):
        result, skip_name = future.result()
        if result:
            results.append(result)
        if skip_name:
            skipped.append(skip_name)

elapsed = time.time() - start_time
print()  # newline after progress bar

# Sort by name
results.sort(key=lambda x: x.get('name', ''))

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
    print(f"\nAVAILABLE domains:")
    for r in available:
        extra = ', '.join(f"{k}={v}" for k, v in r.items() if k not in ('name', 'domain', 'status') and v)
        print(f"  {r['domain']} - {r['name']}" + (f" ({extra})" if extra else ""))
else:
    print("\nNo available domains found.")

# Write results CSV
fieldnames = ['name', 'domain', 'status']
# Add any extra fields from results
if results:
    for key in results[0]:
        if key not in fieldnames:
            fieldnames.append(key)

with open(OUTPUT_CSV, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(results)

print(f"\nResults saved to {OUTPUT_CSV}")
