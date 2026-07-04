#!/usr/bin/env python3
"""
Scrape trending entrepreneur/founder names from public sources.
Outputs a CSV with columns: name,city
"""

import csv
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser


def fetch_url(url, timeout=15):
    """Fetch a URL and return decoded text."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


class YCFounderParser(HTMLParser):
    """Extract founder/company names from YC company pages."""

    def __init__(self):
        super().__init__()
        self.founders = []
        self.in_name = False
        self.in_founder = False
        self.current_name = ""
        self.current_founder = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")
        if "company-name" in cls or "title" in cls:
            self.in_name = True
            self.current_name = ""
        if "founder" in cls.lower() or "team" in cls.lower():
            self.in_founder = True
            self.current_founder = ""

    def handle_data(self, data):
        if self.in_name:
            self.current_name += data
        if self.in_founder:
            self.current_founder += data

    def handle_endtag(self, tag):
        if self.in_name and tag == "a":
            self.in_name = False
        if self.in_founder and tag in ("a", "div", "span"):
            self.in_founder = False
            name = self.current_founder.strip()
            if name and len(name.split()) >= 2:
                self.founders.append(name)


def scrape_yc_top_companies():
    """Scrape Y Combinator top companies page for founder names."""
    print("  Fetching YC top companies...")
    founders = []
    try:
        # YC companies JSON API
        url = "https://yc-oss.github.io/api/companies.json"
        data = fetch_url(url)
        companies = json.loads(data)
        for company in companies.get("all", companies) if isinstance(companies, dict) else companies:
            if isinstance(company, dict):
                founders_list = company.get("founders", company.get("team", []))
                for f in founders_list:
                    if isinstance(f, str) and len(f.split()) >= 2:
                        founders.append((f.strip(), "San Francisco"))
        print(f"    Found {len(founders)} founders from YC")
    except Exception as e:
        print(f"    YC scrape failed: {e}")
    return founders


def scrape_forbes_30u30():
    """Scrape Forbes 30 Under 30 tech list for names."""
    print("  Fetching Forbes 30 Under 30...")
    founders = []
    try:
        # Use a known Forbes 30u30 page
        html = fetch_url("https://www.forbes.com/lists/30-under-30-technology/")
        # Extract names from the page - look for name patterns
        name_pattern = re.compile(
            r'"name"\s*:\s*"([^"]+?)"', re.IGNORECASE
        )
        for match in name_pattern.finditer(html):
            name = match.group(1).strip()
            # Filter for likely full names (2+ words, no special chars)
            parts = name.split()
            if (
                len(parts) >= 2
                and len(name) < 40
                and not any(c in name for c in ["@", "#", "$", "%"])
                and name[0].isupper()
            ):
                founders.append((name, "New York"))
        print(f"    Found {len(founders)} names from Forbes")
    except Exception as e:
        print(f"    Forbes scrape failed: {e}")
    return founders


def scrape_techcrunch():
    """Scrape TechCrunch startup section for founder names."""
    print("  Fetching TechCrunch startup coverage...")
    founders = []
    try:
        html = fetch_url("https://techcrunch.com/category/startups/")
        # Look for author/byline names
        author_pattern = re.compile(
            r'by\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            re.IGNORECASE
        )
        for match in author_pattern.finditer(html):
            name = match.group(1).strip()
            parts = name.split()
            if len(parts) == 2:
                founders.append((name, "San Francisco"))

        # Also try structured data
        json_ld_pattern = re.compile(
            r'"author":\s*\{[^}]*"name":\s*"([^"]+)"',
            re.IGNORECASE
        )
        for match in json_ld_pattern.finditer(html):
            name = match.group(1).strip()
            parts = name.split()
            if len(parts) >= 2 and len(name) < 50:
                founders.append((name, "San Francisco"))

        print(f"    Found {len(founders)} names from TechCrunch")
    except Exception as e:
        print(f"    TechCrunch scrape failed: {e}")
    return founders


def scrape_crunchbase_trending():
    """Scrape Crunchbase trending companies for founder info."""
    print("  Fetching Crunchbase trending...")
    founders = []
    try:
        html = fetch_url("https://www.crunchbase.com/search/organizations/field/organization.company_type:for_profit")
        # Try to extract organization and founder names
        org_pattern = re.compile(
            r'"name"\s*:\s*"([^"]+?)(?:\s+Inc\.|\s+Corp\.|\s+LLC|\s+Ltd\.)?"',
            re.IGNORECASE
        )
        # This is a rough extraction - Crunchbase is heavily JS-rendered
        seen = set()
        for match in org_pattern.finditer(html):
            name = match.group(1).strip()
            if name not in seen and len(name.split()) == 2:
                seen.add(name)
                founders.append((name, "San Francisco"))
        print(f"    Found {len(founders)} names from Crunchbase")
    except Exception as e:
        print(f"    Crunchbase scrape failed: {e}")
    return founders


def main():
    print("Scraping entrepreneur data from public sources...")
    print()

    all_founders = []

    # Run all scrapers
    all_founders.extend(scrape_yc_top_companies())
    all_founders.extend(scrape_forbes_30u30())
    all_founders.extend(scrape_techcrunch())
    all_founders.extend(scrape_crunchbase_trending())

    # Deduplicate
    seen = set()
    unique = []
    for name, city in all_founders:
        key = name.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append((name, city))

    print(f"\nTotal unique scraped founders: {len(unique)}")

    # Write output
    output_file = "scraped-entrepreneurs.csv"
    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "city"])
        for name, city in unique:
            writer.writerow([name, city])

    print(f"Results saved to {output_file}")


if __name__ == "__main__":
    main()
