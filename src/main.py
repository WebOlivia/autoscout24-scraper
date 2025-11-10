import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from extractors.listing_extractor import ListingExtractor
from extractors.dealer_extractor import DealerExtractor
from utils.proxy_manager import ProxyManager
from utils.data_cleaner import ensure_directory

DEFAULT_MAX_RECORDS = 300
DEFAULT_OUTPUT_FORMAT = "json"

def setup_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

def load_json_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file does not exist: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def resolve_paths() -> Dict[str, Path]:
    src_dir = Path(__file__).resolve().parent
    project_root = src_dir.parent
    data_dir = project_root / "data"
    config_dir = src_dir / "config"
    return {
        "src_dir": src_dir,
        "project_root": project_root,
        "data_dir": data_dir,
        "config_dir": config_dir,
    }

def merge_settings(
    base: Dict[str, Any],
    override: Dict[str, Any],
) -> Dict[str, Any]:
    merged = dict(base or {})
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_settings(merged[key], value)
        elif value is not None:
            merged[key] = value
    return merged

def read_start_urls(input_cfg: Dict[str, Any], data_dir: Path) -> List[str]:
    urls: List[str] = []

    # Preferred: explicit list in config
    start_urls = input_cfg.get("startUrls") or input_cfg.get("urls")
    if isinstance(start_urls, list):
        urls.extend(str(u).strip() for u in start_urls if str(u).strip())

    # Fallback: test_urls.txt
    if not urls:
        txt_file = data_dir / "test_urls.txt"
        if txt_file.exists():
            with txt_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        urls.append(line)

    if not urls:
        raise ValueError(
            "No start URLs provided. "
            "Provide them via sample_input.json (startUrls) or data/test_urls.txt."
        )

    return urls

def export_data(records: List[Dict[str, Any]], output_path: Path, fmt: str) -> None:
    fmt = (fmt or DEFAULT_OUTPUT_FORMAT).lower()
    ensure_directory(output_path.parent)

    if fmt == "json":
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        return

    if fmt == "csv":
        import csv

        fieldnames = sorted({k for r in records for k in r.keys()})
        with output_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in records:
                writer.writerow({k: r.get(k, "") for k in fieldnames})
        return

    if fmt == "xml":
        from xml.etree.ElementTree import Element, SubElement, ElementTree

        root = Element("listings")
        for rec in records:
            item_el = SubElement(root, "listing")
            for k, v in rec.items():
                field_el = SubElement(item_el, k)
                field_el.text = "" if v is None else str(v)
        tree = ElementTree(root)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        return

    if fmt == "rss":
        from xml.etree.ElementTree import Element, SubElement, ElementTree

        rss = Element("rss", version="2.0")
        channel = SubElement(rss, "channel")
        title = SubElement(channel, "title")
        title.text = "Autoscout24 Scraper Feed"
        link = SubElement(channel, "link")
        link.text = "https://www.autoscout24.com"
        description = SubElement(channel, "description")
        description.text = "Scraped Autoscout24 car listings"

        for rec in records:
            item = SubElement(channel, "item")
            it_title = SubElement(item, "title")
            it_title.text = str(rec.get("title") or "Car listing")
            it_link = SubElement(item, "link")
            it_link.text = str(rec.get("url") or "")
            it_desc = SubElement(item, "description")
            it_desc.text = str(rec.get("dealerName") or "")

        tree = ElementTree(rss)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        return

    if fmt == "html":
        headers = sorted({k for r in records for k in r.keys()})
        rows = []
        for rec in records:
            row_cells = "".join(
                f"<td>{(rec.get(h) if rec.get(h) is not None else '')}</td>"
                for h in headers
            )
            rows.append(f"<tr>{row_cells}</tr>")
        head_cells = "".join(f"<th>{h}</th>" for h in headers)
        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Autoscout24 Scraper Output</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{ font-family: Arial, sans-serif; margin: 1.5rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem; font-size: 0.9rem; }}
    th {{ background: #f5f5f5; text-align: left; }}
    tr:nth-child(even) {{ background: #fafafa; }}
  </style>
</head>
<body>
  <h1>Autoscout24 Scraper Output</h1>
  <table>
    <thead><tr>{head_cells}</tr></thead>
    <tbody>
      {"".join(rows)}
    </tbody>
  </table>
</body>
</html>
"""
        with output_path.open("w", encoding="utf-8") as f:
            f.write(html)
        return

    raise ValueError(f"Unsupported output format: {fmt}")

def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Autoscout24 Scraper - scrape car listings into structured data."
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to settings JSON (defaults to src/config/settings.example.json).",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        help="Optional input JSON with startUrls and overrides (e.g. data/sample_input.json).",
    )
    parser.add_argument(
        "--max-records",
        "-m",
        type=int,
        help="Maximum number of records to scrape (overrides config).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output file path (overrides config).",
    )
    parser.add_argument(
        "--format",
        "-f",
        type=str,
        choices=["json", "csv", "xml", "rss", "html"],
        help="Output format (overrides config).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (use -vv for debug).",
    )
    return parser.parse_args(argv)

def main(argv: List[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])
    setup_logging(args.verbose)
    log = logging.getLogger("autoscout.main")

    paths = resolve_paths()
    config_dir = paths["config_dir"]
    data_dir = paths["data_dir"]

    # Load base settings from example
    config_path = Path(args.config) if args.config else (config_dir / "settings.example.json")
    try:
        base_settings = load_json_file(config_path)
    except FileNotFoundError:
        log.warning("Config file %s not found. Using minimal defaults.", config_path)
        base_settings = {}
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Config file is not valid JSON: {exc}") from exc

    # Load optional input overrides (includes startUrls)
    input_settings: Dict[str, Any] = {}
    if args.input:
        try:
            input_settings = load_json_file(Path(args.input))
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(f"Failed to load input file {args.input}: {exc}") from exc

    settings = merge_settings(base_settings, input_settings)

    # CLI overrides
    if args.max_records is not None:
        settings["maxRecords"] = args.max_records
    if args.output is not None:
        settings["outputFile"] = args.output
    if args.format is not None:
        settings["outputFormat"] = args.format

    max_records = int(settings.get("maxRecords") or DEFAULT_MAX_RECORDS)
    output_format = settings.get("outputFormat") or DEFAULT_OUTPUT_FORMAT
    output_file = settings.get("outputFile") or f"{data_dir}/output.{output_format}"

    try:
        start_urls = read_start_urls(settings, data_dir)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(str(exc)) from exc

    proxy_cfg = settings.get("proxies") or settings.get("proxyList") or []
    if isinstance(proxy_cfg, str):
        proxies = [p.strip() for p in proxy_cfg.split(",") if p.strip()]
    elif isinstance(proxy_cfg, list):
        proxies = [str(p).strip() for p in proxy_cfg if str(p).strip()]
    else:
        proxies = []

    proxy_manager = ProxyManager(proxies=proxies)
    parallel_requests = int(settings.get("parallelRequests") or 8)
    timeout = float(settings.get("timeoutSeconds") or 15.0)
    user_agent = settings.get("userAgent") or settings.get("user_agent")

    extractor = ListingExtractor(
        max_records=max_records,
        proxy_manager=proxy_manager,
        timeout=timeout,
        parallel_requests=parallel_requests,
        user_agent=user_agent,
    )

    log.info(
        "Starting scrape: %d max records, %d start URLs, format=%s",
        max_records,
        len(start_urls),
        output_format,
    )

    records = extractor.scrape(start_urls)
    log.info("Scraping finished. Collected %d listings.", len(records))

    export_path = Path(output_file)
    try:
        export_data(records, export_path, output_format)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Failed to export data: {exc}") from exc

    # Optional dealer summary (not exported, but logged when verbose)
    dealer_summary = DealerExtractor.build_summary(records)
    log.debug("Dealer summary for %d dealers built.", len(dealer_summary))

    print(f"Scraped {len(records)} listings into {export_path} ({output_format}).")

if __name__ == "__main__":
    main()