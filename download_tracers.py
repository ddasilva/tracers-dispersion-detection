"""
python download_tracers.py 12/01/2025 12/31/2025 myrun --satellite TS2`
"""

import argparse
from datetime import date
import requests
import os
import re
from tqdm import tqdm

TRACERS_PORTAL_BASE_URL = 'https://tracers-portal.physics.uiowa.edu/teams/flight/'


def main():
    args = get_parser().parse_args()
    start_date = parse_date(args.start_date)
    end_date = parse_date(args.end_date)

    print(args)
    print('Start date:', start_date)
    print('End date:', end_date)

    # Download ACI data
    aci_urls = get_aci_or_ace_urls(args, 'aci', start_date, end_date)    
    out_dir = f'./data/{args.run_name}/aci/'
    
    for aci_url in tqdm(aci_urls, desc='Downloading ACI data'):
        download_file(aci_url, out_dir)

    print(f'Downloaded {len(aci_urls)} files')

    # Download EAD data
    ead_urls = get_ead_urls(args, start_date, end_date)
    out_dir = f'./data/{args.run_name}/ead/'
    
    for ead_url in tqdm(ead_urls, desc='Downloading EAD data'):
        download_file(ead_url, out_dir)

    print(f'Downloaded {len(ead_urls)} files')    


def download_file(url, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, os.path.basename(url))
    response = requests.get(url)
    
    with open(out_path, 'wb') as fh:
        fh.write(response.content)

        
def get_ead_urls(args, start_date, end_date):
    print(f"Crawling EAD directory list...")    

    ead_dirlist_url = os.path.join(TRACERS_PORTAL_BASE_URL, 'SOC/TS2/ead/def/')
    response = requests.get(ead_dirlist_url, auth=(args.username, args.password))

    pattern = 'ts2_def_ead_(\d{4})(\d{2})(\d{2})_v(\d+)\.(\d+)\.(\d+)\.cdf'
    pattern_matches = re.findall(pattern, response.text)    
    ead_urls = []
    
    # This directory doesn't have multiple versions
    for (yyyy, mm, dd, ver_maj, ver_min, ver_rev) in pattern_matches:
        cur_date = date(int(yyyy), int(mm), int(dd))

        if cur_date >= start_date and cur_date <= end_date:
            filename = f'ts2_def_ead_{yyyy}{mm}{dd}_v{ver_maj}.{ver_min}.{ver_rev}.cdf'
            url = os.path.join(ead_dirlist_url, filename)
            ead_urls.append(url)
            
    # Collect list of final urls
    return ead_urls
    
        
def get_aci_or_ace_urls(args, inst, start_date, end_date):
    assert inst in ('ace', 'aci')

    print(f"Crawling {inst.upper()} directory list...")
    
    aci_dirlist_url = os.path.join(TRACERS_PORTAL_BASE_URL, f'ACI/ts2/l2/{inst}/ipd/')
    response = requests.get(aci_dirlist_url, auth=(args.username, args.password))

    pattern = 'ts2_l2_' + inst + '_ipd_(\d{4})(\d{2})(\d{2})_v(\d+)\.(\d+)\.(\d+)\.cdf'
    pattern_matches = re.findall(pattern, response.text)

    # Loop through files keeping track of the latest version encountered
    latest_files_per_date = {}
    latest_vers_per_date = {}
    
    for (yyyy, mm, dd, ver_maj, ver_min, ver_rev) in pattern_matches:
        cur_date = date(int(yyyy), int(mm), int(dd))
        cur_vers = (int(ver_maj), int(ver_min), int(ver_rev))
        filename = f'ts2_l2_aci_ipd_{yyyy}{mm}{dd}_v{ver_maj}.{ver_min}.{ver_rev}.cdf'

        if cur_date not in latest_files_per_date:
            latest_files_per_date[cur_date] = filename
            latest_vers_per_date[cur_date] = cur_vers
        elif cur_vers > latest_vers_per_date[cur_date]:
            latest_files_per_date[cur_date] = filename
            latest_vers_per_date[cur_date] = cur_vers
        else:
            #old file!
            pass

    # Build final list of urls
    file_urls = []
        
    for cur_date, filename in latest_files_per_date.items():
        if cur_date >= start_date and cur_date <= end_date:
            file_url = os.path.join(aci_dirlist_url, filename)
            file_urls.append(file_url)
        
    return file_urls

    
def parse_date(date_str):
    toks = date_str.split('/')
    return date(int(toks[2]), int(toks[0]), int(toks[1]))
    
    
    
def get_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument('start_date')
    parser.add_argument('end_date')
    parser.add_argument('run_name')
    parser.add_argument('--satelite', required=True)
    parser.add_argument('--username', required=True)
    parser.add_argument('--password', required=True)

    return parser


if __name__ == '__main__':
    main()
