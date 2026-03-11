TRACERS Dispersion Event Identification Software
---------------------------------------------
This repository holds code and notebooks associated with the automated dispersion event search for use with data from the [TRACERS](https://tracers.physics.uiowa.edu/) satellites. It currently supports searches for normal (non-double or overlapping) dispersion.

Note: currently, this pulls data from the TRACERS Portal which is restricted to team members and requires a username and password for access. As more data is made public, the plan is to transition to using public data.



Code in this repository was adapted in part from [a predecessor tool for use with DMSP satellites](https://github.com/ddasilva/dmsp-dispersion-detection).

* `download_tracers.py` - Download data from the [TRACERS Portal at UIowa](https://tracers-portal.physics.uiowa.edu/L2/). Run with `--help` to see options.
* `download_omniweb.py` - Download data from the OMNIWeb HTTP Server. Run with `--help` to see options.
* `run_model.py` - Search downloaded data and optionally plot discovered events. Pass it a case file created with `make_case_file.py`.
* `make_case_file.py` - Generate a case file containing the inputs for `run_model.py`.

Literature
* da Silva, D., et al. "Statistical Analysis of Overlapping Double Ion Energy Dispersion Events in the Northern Cusp." Frontiers in Astronomy and Space Sciences 10: 1228475. [https://doi.org/10.3389/fspas.2023.1228475](https://doi.org/10.3389/fspas.2023.1228475)
* da Silva, D., et al. "Automatic Identification and New Observations of Ion Energy Dispersion Events in the Cusp Ionosphere." Journal of Geophysical Research: Space Physics 127.4 (2022): e2021JA029637. [https://doi.org/10.1029/2021JA029637](https://doi.org/10.1029/2021JA029637)

Requirements
* [Python 3 with Miniconda/Anaconda](https://docs.conda.io/en/latest/miniconda.html) - programming language, see `environment.yml` for module dependencies.

This code was developed by Daniel da Silva at NASA Goddard Spaceflight Center, who may be contacted at [mail@danieldasilva.org](mailto:mail@danieldasilva.org), [daniel.e.dasilva@nasa.gov](mailto:daniel.e.dasilva@nasa.gov), or [ddasilva@umbc.edu](mailto:ddasilva@umbc.edu).

## Instructions

Create and activate the conda environment:

`$ micromamba env create -f environment.yml`

`$ micromamba activate tracers-dispersion`

Now, pick a name for your run. Here, we call it `myrun`. This example downloads data between December 1, 2025 and December 31, 2025 for the `TS2` satellite.

Next, use these commands to download TRACERS and OMNIWeb data:

`$ python download_tracers.py 12/01/2025 12/31/2025 myrun --satellite TS2 --username myusername --password mypassword`

`$ python download_omniweb.py 12/01/2025 12/31/2025 myrun`

Now, create a case file. This is the input file consumed by the model run.

`$ python make_case_file.py myrun TS2`

This writes `case_files/myrun.json` and points plots and CSV output into `output/myrun/`.

To run the code in single-dispersion mode with a threshold of `0.8`, use the following command. A higher threshold is less sensitive and usually produces fewer false positives, but it will also miss more real events (see da Silva JGR 2022 for discussion).

`$ python run_model.py -i case_files/myrun.json --threshold 0.8`

Add `--no-plot` if you only want the event CSV and do not want plots generated.

Check the `output/` folder for plots and a CSV of detected events!
