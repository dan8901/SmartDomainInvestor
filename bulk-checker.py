import csv
import argparse
import sys
import logging
import whois
from whois.exceptions import WhoisDomainNotFoundError
from colorama import init, Fore, Style

init(autoreset=True)

# Suppress python-whois socket warnings
logging.getLogger("whois").setLevel(logging.CRITICAL)


def check_domain_availability(domain):
    try:
        # Suppress stderr warnings from python-whois
        old_stderr = sys.stderr
        sys.stderr = open('/dev/null', 'w')
        try:
            w = whois.whois(domain)
        finally:
            sys.stderr.close()
            sys.stderr = old_stderr
        if w.domain_name:
            return False  # Domain is registered
        return True  # No WHOIS data = available
    except WhoisDomainNotFoundError:
        return True  # WHOIS says not found = available
    except Exception:
        return True  # Fall back to available on error


def count_rows(csvfile, column, min_net_worth):
    """Count how many rows will be processed."""
    csvfile.seek(0)
    reader = csv.DictReader(csvfile)
    count = 0
    for row in reader:
        name = row.get(column, "").strip()
        if not name:
            continue
        if min_net_worth > 0:
            try:
                net_worth = int(row.get("net_worth", 0))
            except ValueError:
                net_worth = 0
            if net_worth < min_net_worth:
                continue
        count += 1
    csvfile.seek(0)
    return count


def print_progress(current, total, domain, status, bar_width=40):
    """Print a progress bar with current domain info."""
    pct = current / total if total > 0 else 0
    filled = int(bar_width * pct)
    bar = "=" * filled + "-" * (bar_width - filled)
    color = Fore.GREEN if status == "available" else Fore.RED
    status_label = f" {color}{status.upper()}{Style.RESET_ALL}"
    print(f"\r[{bar}] {current}/{total} ({pct:.0%}) | {domain} ->{status_label}    ", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Bulk domain availability checker from CSV.")
    parser.add_argument("-f", "--file", required=True, help="Path to input CSV file.")
    parser.add_argument("-t", "--tld", default="com", help="TLD to check (default: com).")
    parser.add_argument("-o", "--output", required=True, help="Path to output CSV file.")
    parser.add_argument("--column", default="name", help="CSV column name for domain names (default: name).")
    parser.add_argument("--min-net-worth", type=int, default=0, help="Minimum net worth to include (in dollars).")
    args = parser.parse_args()

    results = []
    total = 0
    available_count = 0

    with open(args.file, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        if args.column not in reader.fieldnames:
            print(Fore.RED + f"Error: column '{args.column}' not found in CSV. Available columns: {reader.fieldnames}")
            return

        total = count_rows(csvfile, args.column, args.min_net_worth)

        if total == 0:
            print(Fore.YELLOW + "No domains to check.")
            return

        # Re-create reader after seeking back in count_rows
        reader = csv.DictReader(csvfile)
        extra_cols = [c for c in reader.fieldnames if c != args.column]
        output_fields = ["name", "domain", "status"] + extra_cols

        print(Fore.CYAN + f"Checking {total} domains against .{args.tld}\n")

        checked = 0
        for row in reader:
            name = row[args.column].strip()
            if not name:
                continue
            if args.min_net_worth > 0:
                try:
                    net_worth = int(row.get("net_worth", 0))
                except ValueError:
                    net_worth = 0
                if net_worth < args.min_net_worth:
                    continue
            domain_slug = name.lower().replace(" ", "").replace(".", "").replace("-", "").replace("'", "")
            domain = f"{domain_slug}.{args.tld}"
            is_available = check_domain_availability(domain)
            status = "available" if is_available else "taken"
            result = {"name": name, "domain": domain, "status": status}
            for col in extra_cols:
                result[col] = row.get(col, "")
            results.append(result)
            checked += 1
            if is_available:
                available_count += 1
            print_progress(checked, total, domain, status)

    with open(args.output, "w", newline="") as outcsv:
        writer = csv.DictWriter(outcsv, fieldnames=output_fields)
        writer.writeheader()
        writer.writerows(results)

    print(Fore.CYAN + f"\nChecked {total} domains against .{args.tld}")
    print(Fore.GREEN + f"Available: {available_count}")
    print(Fore.RED + f"Taken: {total - available_count}")
    print(Fore.CYAN + f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
