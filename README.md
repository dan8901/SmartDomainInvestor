# Bulk Domain Availability Checker

A Python script that checks domain availability from a CSV list of names and outputs results to CSV.

## Requirements

Python 3.x

```
pip install colorama
```

## Usage

Run the script with an input CSV file and specify an output CSV file:

```bash
python bulk-checker.py -f names.csv -o results.csv
```

### Arguments

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `-f` / `--file` | Yes | — | Path to input CSV file |
| `-o` / `--output` | Yes | — | Path to output CSV file |
| `-t` / `--tld` | No | `com` | TLD to check (e.g. `org`, `net`, `io`) |
| `--column` | No | `name` | CSV column name containing domain names |

### Examples

Check `.com` availability:
```bash
python bulk-checker.py -f names.csv -o results.csv
```

Check `.org` availability:
```bash
python bulk-checker.py -f names.csv -t org -o results.csv
```

Use a custom column name:
```bash
python bulk-checker.py -f names.csv --column brand_name -o results.csv
```

### Input CSV Format

```csv
name
mybrand
coolstartup
smartdomain
```

### Output CSV Format

```csv
name,domain,status
mybrand,mybrand.com,available
coolstartup,coolstartup.com,taken
```

## How It Works

The script checks DNS resolution for each domain. If a domain resolves via DNS, it is considered **taken**. If DNS resolution fails, it is considered **available**.
