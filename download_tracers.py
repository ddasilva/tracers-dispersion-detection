"""
python download_tracers.py 12/01/2025 12/31/2025 myrun --satellite TS2`
"""

import argparse
from datetime import date
from dateutil.relativedelta import relativedelta
import requests
import os
import re
from tqdm import tqdm

TRACERS_PORTAL_BASE_URL = "https://tracers-portal.physics.uiowa.edu/teams/flight/"


def main():
    args = get_parser().parse_args()
    start_date = parse_date(args.start_date)
    end_date = parse_date(args.end_date)

    print("Start date:", start_date)
    print("End date:", end_date)

    # Download ACI data
    aci_urls = get_aci_urls(args, start_date, end_date)
    download_data(aci_urls, f"./data/{args.run_name}/aci/", "ACI data", args)

    # Download ACE data
    ace_urls = get_ace_urls(args, start_date, end_date)
    download_data(ace_urls, f"./data/{args.run_name}/ace", "ACE data", args)

    # Download EAD data
    ead_urls = get_ead_urls(args, start_date, end_date)
    download_data(ead_urls, f"./data/{args.run_name}/ead/", "EAD data", args)


def download_file(url, out_dir, args):
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, os.path.basename(url))
    response = requests.get(url, auth=(args.username, args.password))

    with open(out_path, "wb") as fh:
        fh.write(response.content)


def download_data(urls, out_dir, desc, args):
    """Download a list of ``urls`` into ``out_dir`` with a progress bar.

    ``desc`` is the text displayed in the tqdm bar.
    """
    os.makedirs(out_dir, exist_ok=True)
    for url in tqdm(urls, desc=f"Downloading {desc}"):
        download_file(url, out_dir, args)
    print(f"Downloaded {len(urls)} files")


def get_ead_urls(args, start_date, end_date):
    print("Crawling EAD directory list...")

    ead_dirlist_url = os.path.join(TRACERS_PORTAL_BASE_URL, "SOC/TS2/ead/def/")
    response = requests.get(ead_dirlist_url, auth=(args.username, args.password))

    pattern = "ts2_def_ead_(\d{4})(\d{2})(\d{2})_v(\d+)\.(\d+)\.(\d+)\.cdf"
    pattern_matches = re.findall(pattern, response.text)
    ead_urls = []

    # This directory doesn't have multiple versions
    for yyyy, mm, dd, ver_maj, ver_min, ver_rev in pattern_matches:
        cur_date = date(int(yyyy), int(mm), int(dd))

        if cur_date >= start_date and cur_date <= end_date:
            filename = f"ts2_def_ead_{yyyy}{mm}{dd}_v{ver_maj}.{ver_min}.{ver_rev}.cdf"
            url = os.path.join(ead_dirlist_url, filename)
            ead_urls.append(url)

    ead_urls = list(set(ead_urls))

    # Collect list of final urls
    return ead_urls


def crawl_latest_files(args, dirlist_url, pattern, start_date, end_date):
    """Return list of urls under ``dirlist_url`` matching ``pattern``.

    Only the latest version for each date in the ``start_date``–``end_date``
    interval is retained.  ``args`` is only used to provide authentication
    for the requests call.
    """
    print(f"Crawling {dirlist_url}...")
    response = requests.get(dirlist_url, auth=(args.username, args.password))
    pattern_matches = re.findall(pattern, response.text)

    latest_files_per_date: dict[date, str] = {}
    latest_vers_per_date: dict[date, tuple[int, int, int]] = {}

    for yyyy, mm, dd, ver_maj, ver_min, ver_rev in pattern_matches:
        cur_date = date(int(yyyy), int(mm), int(dd))
        cur_vers = (int(ver_maj), int(ver_min), int(ver_rev))

        # filename must match the directory being crawled – caller constructs it
        filename = os.path.basename(
            dirlist_url.rstrip("/")
        )  # placeholder, will be overridden below
        # however, we just build the string again using the pieces
        if "aci" in dirlist_url.lower():
            filename = (
                f"ts2_l2_aci_ipd_{yyyy}{mm}{dd}_v{ver_maj}.{ver_min}.{ver_rev}.cdf"
            )
        elif "ace" in dirlist_url.lower():
            filename = (
                f"ts2_l2_ace_def_{yyyy}{mm}{dd}_v{ver_maj}.{ver_min}.{ver_rev}.cdf"
            )
        else:
            raise RuntimeError("Unknown directory type in crawl_latest_files")

        if cur_date not in latest_files_per_date:
            latest_files_per_date[cur_date] = filename
            latest_vers_per_date[cur_date] = cur_vers
        elif cur_vers > latest_vers_per_date[cur_date]:
            latest_files_per_date[cur_date] = filename
            latest_vers_per_date[cur_date] = cur_vers

    file_urls: list[str] = []
    for cur_date, filename in latest_files_per_date.items():
        if start_date <= cur_date <= end_date:
            file_urls.append(os.path.join(dirlist_url, filename))
    return file_urls


def get_aci_urls(args, start_date, end_date):
    dirlist_url = os.path.join(TRACERS_PORTAL_BASE_URL, "ACI/ts2/l2/aci/ipd/")
    pattern = r"ts2_l2_aci_ipd_(\d{4})(\d{2})(\d{2})_v(\d+)\.(\d+)\.(\d+)\.cdf"
    return crawl_latest_files(args, dirlist_url, pattern, start_date, end_date)


def get_ace_urls(args, start_date, end_date):
    """Walk through the monthly ACE directories and collect urls.

    The underlying logic is identical to the ACI helper, so we just call the
    generic crawler for each month between ``start_date`` and ``end_date``.
    """
    ace_urls: list[str] = []
    crawl_month = start_date
    while crawl_month < end_date:
        dirlist_url = os.path.join(
            TRACERS_PORTAL_BASE_URL,
            f"ACE/ts2/l2/{crawl_month.year}/{crawl_month.month:02d}/",
        )
        pattern = r"ts2_l2_ace_def_(\d{4})(\d{2})(\d{2})_v(\d+)\.(\d+)\.(\d+)\.cdf"
        ace_urls.extend(
            crawl_latest_files(args, dirlist_url, pattern, start_date, end_date)
        )
        crawl_month += relativedelta(months=1)
    return ace_urls


def parse_date(date_str):
    toks = date_str.split("/")
    return date(int(toks[2]), int(toks[0]), int(toks[1]))


def get_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument("start_date")
    parser.add_argument("end_date")
    parser.add_argument("run_name")
    parser.add_argument("--satellite", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)

    return parser


if __name__ == "__main__":
    main()
