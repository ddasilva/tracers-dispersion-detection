#!/usr/bin/env python
"""Writes a case file for use with analyzing a storm.

See also: run_model.py
"""
import argparse
import glob
import json
import os
from termcolor import cprint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run_name')
    parser.add_argument('satellite', help="TS1 or TS2")
    parser.add_argument('--reverse-effect', action='store_true')
    parser.add_argument('--inverse-effect', action='store_true')
    args = parser.parse_args()

    if args.satellite.upper() not in ('TS1', 'TS2'):
        print('Satellite argument must be either TS1 or TS2')
        return
    
    # Edit here
    reverse_effect = args.reverse_effect
    inverse_effect = args.inverse_effect
    
    plot_output = f'output/{args.run_name}_F{args.satellite.upper()}/plots'
    event_output = f'output/{args.run_name}_F{args.satellite.upper()}/{args.run_name}_{args.satellite.upper()}.csv'

    # Get OMNIweb files
    omniweb_glob = 'data/' + args.run_name + '/**/omni*.cdf'
    omniweb_files = []
    omniweb_files.extend(glob.glob(omniweb_glob, recursive=True))

    # Get DMSP files
    aci_glob = f'./data/{args.run_name}/aci/{args.satellite.lower()}_l2_aci_ipd_*.cdf'
    aci_files = []
    aci_files.extend(glob.glob(aci_glob, recursive=True))
    aci_files.sort()
    
    ead_glob = f'./data/{args.run_name}/ead/{args.satellite.lower()}_def_ead_*.cdf'
    ead_files = []
    ead_files.extend(glob.glob(ead_glob, recursive=True))
    ead_files.sort()

    # Make plot output dir if does not exist
    os.makedirs(plot_output, exist_ok=True)
    
    # Write case fiel
    case_file = {
        'STORM_NAME': args.run_name,
        'SATELLITE': args.satellite.upper(),
        'ACI_FILES': aci_files,
        'EAD_FILES': ead_files,
        'OMNIWEB_FILES': omniweb_files,
        'PLOT_OUTPUT': plot_output,
        'EVENT_OUTPUT': event_output,
        'REVERSE_EFFECT': reverse_effect,
        'INVERSE_EFFECT': inverse_effect,
    }

    case_filename = f'case_files/{args.run_name}_{args.satellite.upper()}.json'
    fh = open(case_filename, 'w')
    json.dump(case_file, fh, indent=4)
    fh.write('\n')
    fh.close()
    
    cprint(f'Wrote case file to path {case_filename}', 'green')
    cprint(f"Plots will be written to {plot_output}", "yellow")
    cprint(f"CSV output will be written to {event_output}", "yellow")


if __name__ == '__main__':
    main()
