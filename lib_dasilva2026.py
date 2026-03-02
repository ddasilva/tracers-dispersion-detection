from dataclasses import dataclass
from datetime import datetime, timedelta
import os
from typing import Optional

import pandas as pd
import intervaltree
from matplotlib import pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.dates import date2num
import numpy as np
from spacepy import pycdf
from mpl_toolkits.axes_grid1 import make_axes_locatable
from cdasws import CdasWs
import cdasws
from termcolor import cprint
from tqdm import tqdm

EIC_FRAC = 0.1
CHAN_CUTOFF = 10

SPECT_ACI_VMIN = 1e3
SPECT_VMAX = 1e9

MAX_SHEATH_ENERGY = 3.1e3
MIN_ION_VALID_ENERGY = 50
MIN_AVG_IFLUX_SHEATH = 10**6
MIN_IFLUX_AT_EIC = 10**6
MIN_MLT = 6
MAX_MLT = 18


@dataclass
class TRACERSData:
    aci_time: np.ndarray
    aci_energies: np.ndarray
    aci_flux: np.ndarray
    aci_spect: np.ndarray

    ace_time: np.ndarray
    ace_energies: np.ndarray
    ace_flux: np.ndarray
    ace_spect: np.ndarray

    mlat: np.ndarray  # interpolated to ACI time axis
    mlt: np.ndarray

    def subset(self, stime, etime):
        i = np.searchsorted(self.aci_time, stime)
        j = np.searchsorted(self.aci_time, etime)

        ii = np.searchsorted(self.ace_time, stime)
        jj = np.searchsorted(self.ace_time, etime)

        return TRACERSData(
            aci_time=self.aci_time[i:j],
            aci_energies=self.aci_energies,
            aci_flux=self.aci_flux[i:j],
            aci_spect=self.aci_spect[i:j],
            ace_time=self.ace_time[ii:jj],
            ace_energies=self.ace_energies,
            ace_flux=self.ace_flux[ii:jj],
            ace_spect=self.ace_spect[ii:jj],
            mlat=self.mlat[i:j],
            mlt=self.mlt[i:j],
        )


@dataclass
class ScoringResults:
    data_subset: TRACERSData
    iflux_avg_sheath: np.ndarray
    iflux_at_Eic: np.ndarray
    Eic: np.ndarray
    D: np.ndarray
    Bx: float
    By: float
    Bz: float


@dataclass
class DetectionSettings:
    """Configuration settings for dispersion event detection."""

    # Energy thresholds
    min_ion_valid_energy: float = MIN_ION_VALID_ENERGY
    max_sheath_energy: float = MAX_SHEATH_ENERGY

    # Flux thresholds
    min_avg_iflux_sheath: float = MIN_AVG_IFLUX_SHEATH
    min_iflux_at_eic: float = MIN_IFLUX_AT_EIC

    # Eic calculation parameters
    Eic_frac: float = EIC_FRAC
    Eic_window_size: int = 11

    # Spectrogram display parameters
    chan_cutoff: int = CHAN_CUTOFF
    spect_vmin: float = SPECT_ACI_VMIN
    spect_vmax: float = SPECT_VMAX

    # Scoring function parameters
    score_threshold: float = 0.1
    reverse_effect: bool = False

    # IMF (Interplanetary Magnetic Field) constraints
    bz_south_only: bool = False
    bz_north_only: bool = False

    # MLT (Magnetic Local Time) constraints
    min_mlt: float = MIN_MLT  # 6 AM MLT
    max_mlt: float = MAX_MLT  # 6 PM MLT

    # Plotting options
    debug_plot: bool = False
    plot_output_path: str = "plots/default"

    scoring_result: Optional[ScoringResults] = None


@dataclass
class DetectionResult:
    detection: bool
    score: float
    scoring_result: ScoringResults
    start_time: datetime
    end_time: datetime
    Bx: float
    By: float
    Bz: float


def plot_spect(tracers_data, fig=None, ax=None, cmap=None, cbar=False):
    if ax is None:
        fig = plt.figure(figsize=(12, 4))
        ax = plt.gca()

    im = ax.pcolor(
        tracers_data.aci_time,
        tracers_data.aci_energies[CHAN_CUTOFF:],
        tracers_data.aci_spect.T[CHAN_CUTOFF:],
        norm=LogNorm(vmin=SPECT_ACI_VMIN, vmax=SPECT_VMAX),
        cmap=cmap,
    )

    ax.set_yscale("log")
    ax.set_ylabel("Energy (eV)")

    if cbar:
        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", size="5%", pad=0.05)
        cb = fig.colorbar(im, cax=cax, orientation="vertical")
        cb.set_label(r"Summed Omni Flux")

    return ax, im


def find_Eic(
    tracers_data, smooth=True, Eic_frac=EIC_FRAC, window_size=5, chan_cutoff=CHAN_CUTOFF
):
    Eic = np.zeros(tracers_data.aci_time.size)
    Eic[:] = np.nan

    for i in range(Eic.size):
        idx_peak_energy = (
            np.argmax(tracers_data.aci_spect[i, chan_cutoff:]) + chan_cutoff
        )
        j = idx_peak_energy

        while j > chan_cutoff:
            if (
                tracers_data.aci_spect[i, j]
                < Eic_frac * tracers_data.aci_spect[i, idx_peak_energy]
            ):
                Eic[i] = tracers_data.aci_energies[j]
                break
            j -= 1

    if smooth:
        Eic = smooth_Eic(Eic, window_size)

    return Eic


def smooth_Eic(Eic, window_size=5):
    """Smooth Eic with a mask of points to include in moving average.

    Args
      Eic: array
      window_size: integer, must be odd
    Returns
      Smoothed Eic array
    """
    assert (window_size is None) or (window_size % 2 == 1), "Window size must be odd"

    Eic_clean = Eic.copy()

    for i in range(Eic.size):
        total = 0.0
        count = 0

        for di in range(-window_size // 2, window_size // 2 + 1):
            if i + di > 0 and i + di < Eic.size:
                total += Eic[i + di]
                count += 1

        if count > 0:  # else left as nan
            Eic_clean[i] = total / count

    return Eic_clean


def load_tracers_data(aci_file, ace_file, ead_file):
    if "ts1" in aci_file:
        key = "ts1"
    else:
        key = "ts2"

    # Load data from ACI file
    cdf = pycdf.CDF(aci_file)
    aci_flux = cdf[f"{key}_l2_aci_tscs_def"][:]
    aci_spect = aci_flux.sum(axis=-1)
    aci_energies = cdf[f"{key}_l2_aci_energy"][:]
    aci_time = cdf["Epoch"][:]
    cdf.close()

    # Load data from ACE file
    cdf = pycdf.CDF(ace_file)
    ace_flux = cdf[f"{key}_l2_ace_def"][:]
    ace_spect = ace_flux.sum(axis=-1)
    ace_energies = cdf[f"{key}_l2_ace_energy"][:]
    ace_time = cdf["Epoch"][:]
    cdf.close()

    # Load MLat from ACI file and interpolate to same times as ACI
    cdf = pycdf.CDF(ead_file)
    ead_time = cdf["Epoch"][:]
    ead_mlat = cdf[f"{key}_ead_mlat"][:]
    ead_mlt = cdf[f"{key}_ead_mlt"][:]
    cdf.close()

    mlat = np.interp(x=date2num(aci_time), xp=date2num(ead_time), fp=ead_mlat)
    mlt = np.interp(x=date2num(aci_time), xp=date2num(ead_time), fp=ead_mlt)

    # Return TRACERSData instance
    return TRACERSData(
        aci_time=aci_time,
        aci_energies=aci_energies,
        aci_flux=aci_flux,
        aci_spect=aci_spect,
        mlat=mlat,
        mlt=mlt,
        ace_time=ace_time,
        ace_energies=ace_energies,
        ace_flux=ace_flux,
        ace_spect=ace_spect,
    )


def get_iflux_at_Eic(data, Eic):
    iflux_at_Eic = np.zeros_like(Eic)

    for i in range(data.aci_spect.shape[0]):
        if np.isnan(Eic[i]):
            iflux_at_Eic[i] = np.nan
        else:
            iflux_at_Eic[i] = data.aci_spect[
                i, np.searchsorted(data.aci_energies, Eic[i])
            ]

    return iflux_at_Eic


def get_scoring_function(
    tracers_data, omni_data, detection_settings, start_time, end_time
):
    # Subset data at provided times
    data_subset = tracers_data.subset(start_time, end_time)

    # Calculate terms and variables that go into the scoring function
    Eic = find_Eic(
        data_subset,
        smooth=True,
        window_size=detection_settings.Eic_window_size,
        Eic_frac=detection_settings.Eic_frac,
        chan_cutoff=detection_settings.chan_cutoff,
    )

    # Calculate variables that go into the scoring function
    ch_i = tracers_data.aci_energies.searchsorted(
        detection_settings.min_ion_valid_energy
    )
    ch_j = tracers_data.aci_energies.searchsorted(detection_settings.max_sheath_energy)
    iflux_avg_sheath = np.mean(data_subset.aci_spect.T[ch_i:ch_j, :], axis=0)
    iflux_at_Eic = get_iflux_at_Eic(data_subset, Eic)

    # Lookup magnetic field at this current time
    time_curr = start_time + (end_time - start_time) / 2
    time_curr_d2n = date2num(time_curr)
    Bx = np.interp(time_curr_d2n, omni_data["time_d2n"], omni_data["Bx"])
    By = np.interp(time_curr_d2n, omni_data["time_d2n"], omni_data["By"])
    Bz = np.interp(time_curr_d2n, omni_data["time_d2n"], omni_data["Bz"])

    # Build masks that zero out scoring function
    iflux_avg_sheath_mask = iflux_avg_sheath > detection_settings.min_avg_iflux_sheath
    iflux_at_Eic_mask = iflux_at_Eic > detection_settings.min_iflux_at_eic
    Eic_in_sheath_mask = Eic < detection_settings.max_sheath_energy
    mask = iflux_avg_sheath_mask & iflux_at_Eic_mask & Eic_in_sheath_mask

    if detection_settings.bz_south_only:
        mask &= Bz < 0
    elif detection_settings.bz_north_only:
        mask &= Bz > 0
    mask &= data_subset.mlt > detection_settings.min_mlt  # dayside only
    mask &= data_subset.mlt < detection_settings.max_mlt

    # Calculate Scoring Function
    delta_t = np.array([dt.total_seconds() for dt in np.diff(data_subset.aci_time)])

    D = np.diff(np.log10(Eic)) / delta_t
    D *= -np.sign(np.diff(np.abs(data_subset.mlat)))
    D[~mask[:-1]] = 0
    D[Eic[:-1] > detection_settings.max_sheath_energy] = 0

    if detection_settings.reverse_effect:
        D *= -1

    D[np.isnan(D)] = 0
    D = np.array(D.tolist() + [0])

    return ScoringResults(
        data_subset=data_subset,
        iflux_avg_sheath=iflux_avg_sheath,
        iflux_at_Eic=iflux_at_Eic,
        Eic=Eic,
        D=D,
        Bx=Bx,
        By=By,
        Bz=Bz,
    )


def test_detection(
    tracers_data, start_time, end_time, omni_data, detection_settings, plot_force=False
):
    subset_time = tracers_data.subset(start_time, end_time).aci_time
    if subset_time.size < 10:  # not enough data points to test
        return None

    scoring_result = get_scoring_function(
        tracers_data, omni_data, detection_settings, start_time, end_time
    )

    # Calculate total score and check for detection
    delta_t = [dt.total_seconds() for dt in np.diff(subset_time)]
    delta_t.append(delta_t[-1])  # assume last interval same as previous for simplicity
    total_score = np.sum(scoring_result.D * delta_t)

    detection = total_score > detection_settings.score_threshold

    if (detection and detection_settings.debug_plot) or plot_force:
        do_detection_plot(
            tracers_data,
            scoring_result.data_subset,
            start_time,
            end_time,
            scoring_result.iflux_avg_sheath,
            scoring_result.iflux_at_Eic,
            scoring_result.Eic,
            scoring_result.D,
            delta_t,
            scoring_result.Bx,
            scoring_result.By,
            scoring_result.Bz,
            total_score,
            detection_settings,
        )

    if not detection:
        return None

    return DetectionResult(
        detection=True,
        start_time=start_time,
        end_time=end_time,
        scoring_result=scoring_result,
        score=total_score,
        Bx=scoring_result.Bx,
        By=scoring_result.By,
        Bz=scoring_result.Bz,
    )


def do_detection_plot(
    tracers_data,
    data_subset,
    start_time,
    end_time,
    iflux_avg_sheath,
    iflux_at_Eic,
    Eic,
    D,
    delta_t,
    Bx,
    By,
    Bz,
    total_score,
    detection_settings,
):
    fig, axes = plt.subplots(4, 1, figsize=(8, 8), sharex=True)

    fig.suptitle(
        f"Dispersion Event: {start_time.strftime('%Y-%m-%d')},  "
        f"{start_time.strftime('%H:%M:%S')} - {end_time.strftime('%H:%M:%S')} UT"
        f"\nIMF = <{Bx:.1f}, {By:.1f}, {Bz:.1f}> nT"
    )

    padding = timedelta(seconds=10)
    subset_with_padding = tracers_data.subset(start_time - padding, end_time + padding)

    _, im = plot_spect(subset_with_padding, fig=fig, ax=axes[0])
    axes[0].plot(
        data_subset.aci_time[D != 0],
        Eic[D != 0],
        "b-",
    )
    axes[0].axhline(
        detection_settings.max_sheath_energy,
        color="k",
        linestyle="dashed",
        # label='Max Energy\nSheath Origin',
    )
    axes[0].set_title("Ion Spectrogram from ACI")

    axes[1].plot(data_subset.aci_time, iflux_avg_sheath, color="C2")
    axes[1].set_title("Average Ion Flux in Energy Range for Magnetosheath Origin")
    axes[1].set_ylabel("Averaged Omni Flux")
    axes[1].axhline(
        detection_settings.min_avg_iflux_sheath,
        color="k",
        linestyle="dashed",
        label="Threshold",
    )

    axes[2].plot(data_subset.aci_time, iflux_at_Eic, color="C3")
    axes[2].set_title("Ion Flux at $E_{ic}$")
    axes[2].set_ylabel("Omni Flux")
    axes[2].axhline(
        detection_settings.min_iflux_at_eic,
        color="k",
        linestyle="dashed",
        label="Threshold",
    )

    label = r"D(T) : Scoring Function | "
    label += f"Total Score: {total_score:.2f}"
    axes[3].fill_between(data_subset.aci_time, 0, D, label=label)
    axes[3].set_ylabel("D(t)")

    for i, ax in enumerate(axes):
        if i > 0:
            ax.legend(loc="upper right", facecolor="white", framealpha=1)
            plt.grid(color="#ccc", linestyle="dashed", alpha=0.5)
        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", size="5%", pad=0.05)
        cb = fig.colorbar(im, cax=cax, orientation="vertical")
        cb.set_label(r"Summed Omni Flux")
        ax.set_xlim(start_time - padding, end_time + padding)

    fname = (
        f"TracersDispersionEvent_{start_time.isoformat()}_{end_time.isoformat()}.png"
    )

    os.makedirs(detection_settings.plot_output_path, exist_ok=True)
    out_path = os.path.join(
        detection_settings.plot_output_path,
        fname,
    )
    fig.savefig(out_path, dpi=300)
    cprint(f"Wrote plot {out_path}", "green")


def walk_in_time(tracers_data, omni_data, detection_settings):
    # Loop over time in ingrements of `step`
    matching_intervals = intervaltree.IntervalTree()
    start_time = tracers_data.aci_time.min().replace(microsecond=0)
    end_time = tracers_data.aci_time.max()
    interval_duration = timedelta(seconds=30)
    current_time = start_time

    # Calculate number of intervals
    step = timedelta(seconds=1)
    num_intervals = int((end_time - start_time).total_seconds() / step.total_seconds())

    for _ in tqdm(range(num_intervals), desc="Testing detections"):
        interval_end = current_time + interval_duration

        result = test_detection(
            tracers_data, current_time, interval_end, omni_data, detection_settings
        )

        if result:  # if detection found
            matching_intervals[current_time:interval_end] = {
                "score": result.score,
                "Bx": result.Bx,
                "By": result.By,
                "Bz": result.Bz,
            }

        current_time = current_time + step

    # Merge overlapping intervals into common intervals. Retain the
    # metadata attached to each.
    def reducer(current, new_data):
        for key in new_data:
            if key not in current:
                current[key] = set()
            current[key].add(new_data[key])

        return current

    matching_intervals.merge_overlaps(data_reducer=reducer, data_initializer={})

    # Convert to pandas dataframe for easy output to terminal of matching
    # intervals and associated metadata.
    df_match_rows = []

    for interval in sorted(matching_intervals):
        df_match_rows.append(
            [
                interval.begin,
                interval.end,
                np.mean(list(interval.data["Bx"])),
                np.mean(list(interval.data["By"])),
                np.mean(list(interval.data["Bz"])),
                np.mean(list(interval.data["score"])),
            ]
        )

    df_match = pd.DataFrame(
        df_match_rows, columns=["start_time", "end_time", "Bx", "By", "Bz", "score"]
    )

    return df_match


def load_omni(omniweb_files, silent=False):
    """Read OMNIWeb files into a single dictionary.

    Args
      omniweb_files: string path to cdf files
    Returns
      dictionary mapping parameters to file
    """
    # Read OMNIWeb Data
    # ------------------------------------------------------------------------------------
    time_items = []
    Bx_items = []
    By_items = []
    Bz_items = []
    n_items = []

    for omniweb_file in sorted(omniweb_files):
        # Open file
        if not silent:
            print(f"Loading {omniweb_file}")
        omniweb_cdf = pycdf.CDF(omniweb_file)
        epochs = omniweb_cdf["Epoch"][:]

        # Read the data
        time_items.append(np.array([time.replace(tzinfo=None) for time in epochs]))

        Bx_items.append(omniweb_cdf["BX_GSE"][:])
        By_items.append(omniweb_cdf["BY_GSM"][:])
        Bz_items.append(omniweb_cdf["BZ_GSM"][:])
        n_items.append(omniweb_cdf["proton_density"][:])

    # Merge arrays list of items
    omniweb_fh = {}
    omniweb_fh["time"] = np.concatenate(time_items)
    omniweb_fh["time_d2n"] = date2num(omniweb_fh["time"])
    omniweb_fh["Bx"] = np.concatenate(Bx_items)
    omniweb_fh["By"] = np.concatenate(By_items)
    omniweb_fh["Bz"] = np.concatenate(Bz_items)
    omniweb_fh["n"] = np.concatenate(n_items)

    return omniweb_fh
