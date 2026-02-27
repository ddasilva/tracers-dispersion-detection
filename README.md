TRACERS Dispersion Event Identification Software
---------------------------------------------
This repository holds code and notebooks asosciated with the automated dispersion event search for use with data from the [TRACERS](https://tracers.physics.uiowa.edu/) satellites. It currently supports searches for normal (non-double or overlapping) dispersion.

Note: currently, this pulls data from the TRACERS Portal which is restricted to team members and requires a username and password for access. As more data is made public, the plan is to transition to using public data.



Code in this repository was adapted in part from [a predecessor tool for use with DMSP satellites](https://github.com/ddasilva/dmsp-dispersion-detection).

* `download_tracers.py` - Download data from the [TRACERS Portal at UIowa](https://tracers-portal.physics.uiowa.edu/L2/). Run with `--help` to see options.
* `download_omniweb.py` - Downoad data from OMNIWeb HTTP Server. Run with `--help` to see options.
* `run_model.py` - Script to search data and plot discovered events-- you pass it a case file created with `make_case_file.py`.
* `make_case_file.py` - Generate a case file which holds all the inputs for `run_model.py`. Edit the variables at the top of the code and re-run the script to get it to write a file.

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

Now, pick a name for your run. Here, we call it `myrun`. It is going to be between December 1, 2015, and December 31, 2015, using the TS2 satellite. 

Next, use these commands to download TRACERS and OMNIWeb data:

`$ python download_tracers.py 12/01/2025 12/31/2025 myrun --satellite TS2`--username myusername --password mypassword

`$ python download_omniweb.py 12/01/2025 12/31/2025 myrun`

Now, we will make a case file. This is an input file for the model to run. 

`$ python make_case_file.py myrun 16`

To run the code in single dispersion mode with the threshold of 0.8, use the following command. Higher threshold means less sensitive and less false positives, but you miss more real events (See da Silva JGR2022 for discussion).

`$ python run_model.py -i case_files/myrun_F16.json --threshold 0.8`

Check the `output/` folder for plots and a CSV of detected events!
