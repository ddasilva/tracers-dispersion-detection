#!/usr/bin/env python

import argparse
import json
import os

from matplotlib import pyplot as plt
import pandas as pd
from termcolor import cprint

import lib_dasilva2026
import lib_plotting


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Run the model")
    parser.add_argument(
        "-i", metavar="CASE_FILE", required=True, help="Path to case file"
    )
    parser.add_argument(
        "--threshold", type=float, default=-1, help="Detection threshold"
    )
    parser.add_argument(
        "--no-plot", action="store_true", help="Set to disable plotting"
    )
    args = parser.parse_args()

    # Load case  ------------------------------------------------------------
    with open(args.i, "r") as fh:
        case_file = json.load(fh)

    # Loop through ACI files ------------------------------------------------

    # Create detection settings object
    detection_settings = lib_dasilva2026.DetectionSettings(
        score_threshold=args.threshold,
        reverse_effect=case_file["REVERSE_EFFECT"],
        plot_output_path=case_file["PLOT_OUTPUT"],
        bz_north_only=case_file["BZ_NORTH_ONLY"],
        bz_south_only=case_file["BZ_SOUTH_ONLY"],
        min_mlt=case_file["MIN_MLT"],
        max_mlt=case_file["MAX_MLT"],
        debug_plot=case_file["DEBUG_PLOT"],
    )
    omni_data = lib_dasilva2026.load_omni(case_file["OMNIWEB_FILES"])
    df_match_accum = []

    for aci_file in case_file["ACI_FILES"]:
        cprint(f"Processing {aci_file}...", "cyan")

        # Find matching EAD file
        ead_file = find_matching_file(aci_file, case_file["EAD_FILES"], "EAD")
        if ead_file is None:
            continue

        # Find matching ACE file
        ace_file = find_matching_file(aci_file, case_file["ACE_FILES"], "ACE")

        # Load TRACERS data from disk
        tracers_data = lib_dasilva2026.load_tracers_data(
            aci_file=aci_file, ead_file=ead_file, ace_file=ace_file
        )

        # Walk in time
        df_match = lib_dasilva2026.walk_in_time(
            tracers_data, omni_data, detection_settings
        )
        df_match_accum.append(df_match)

        if not df_match.empty:
            print(df_match.to_string())

        # Make plots
        if args.no_plot:
            continue

        # Do a second pass on good events only (combined from overlapping)
        for _, row in df_match.iterrows():
            detection_result = lib_dasilva2026.test_detection(
                tracers_data,
                row.start_time,
                row.end_time,
                omni_data,
                detection_settings,
            )

            lib_plotting.write_plot(
                detection_result,
                tracers_data,
                case_file["SATELLITE"],
                case_file["PLOT_OUTPUT"],
            )
            plt.close()

    df_match_final = pd.concat(df_match_accum, ignore_index=True)
    df_match_final.to_csv(case_file["EVENT_OUTPUT"], index=False)
    cprint(f'Wrote to {case_file["EVENT_OUTPUT"]}', "green")


def find_matching_file(aci_file, other_files, file_type):
    """Find the EAD file that matches the given ACI file based on the date token
    in the filename.
    """
    toks = os.path.basename(aci_file).split("_")
    date_tok = toks[4]
    other_files = [f for f in other_files if date_tok in f]

    if len(other_files) == 0:
        cprint(f"No matching {file_type} file found for {aci_file}, skipping", "red")
        return None
    elif len(other_files) != 1:
        cprint(
            f"Multiple matching {file_type} files found for {aci_file}, skipping", "red"
        )
        return None

    return other_files[0]


if __name__ == "__main__":
    main()
