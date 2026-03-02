import os
import warnings

from matplotlib import MatplotlibDeprecationWarning
from matplotlib import pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.dates import num2date
from mpl_toolkits.axes_grid1 import make_axes_locatable
import numpy as np
from termcolor import cprint

import lib_dasilva2026


def write_plot(
    detection_result,
    tracers_data,
    sat,
    plot_out_dir,
):
    """Visualizes detection and writes plot to disk.

    Args
      TODO
    """
    start_time = detection_result.start_time
    end_time = detection_result.end_time
    Eic = detection_result.scoring_result.Eic
    D = detection_result.scoring_result.D
    Bx = detection_result.Bx
    By = detection_result.By
    Bz = detection_result.Bz

    fig, axes = plt.subplots(3, 1, figsize=(6, 6), sharex=True)

    fig.suptitle(
        f"TRACERS {sat} Dispersion Event\n"
        f"{start_time.strftime('%Y-%m-%d')},  "
        f"{start_time.strftime('%H:%M:%S')} - {end_time.strftime('%H:%M:%S')} UT"
        f"\nIMF = <{Bx:.1f}, {By:.1f}, {Bz:.1f}> nT"
    )

    padding = 0.2 * (end_time - start_time)
    subset_with_padding = tracers_data.subset(start_time - padding, end_time + padding)
    subset_no_padding = tracers_data.subset(start_time, end_time)

    # Plot ACI Curve -------------------------------
    ax = axes[0]
    im = ax.pcolor(
        subset_with_padding.aci_time,
        subset_with_padding.aci_energies[lib_dasilva2026.CHAN_CUTOFF :],
        subset_with_padding.aci_spect.T[lib_dasilva2026.CHAN_CUTOFF :],
        norm=LogNorm(vmin=1e3, vmax=1e9),
        cmap="jet",
    )
    ax.set_yscale("log")
    ax.set_ylabel("Ion Energy (eV)")
    add_colorbar(fig, ax, im)

    # Plot Eic
    axes[0].plot(
        subset_no_padding.aci_time[D != 0],
        Eic[D != 0],
        "b*-",
        linewidth=2,
    )
    # Plot line for max sheath energy
    axes[0].axhline(
        lib_dasilva2026.MAX_SHEATH_ENERGY,
        color="k",
        linestyle="dashed",
        # label='Max Energy\nSheath Origin',
    )
    axes[0].set_title("Ion Spectrogram from ACI")

    # Plot ACE Curve -------------------------------
    ax = axes[1]
    im = ax.pcolor(
        subset_with_padding.ace_time,
        subset_with_padding.ace_energies,
        subset_with_padding.ace_spect.T,
        norm=LogNorm(vmin=1e5, vmax=1e11),
        cmap="jet",
    )
    ax.set_yscale("log")
    ax.set_ylabel("Electron Energy (eV)")
    add_colorbar(fig, ax, im)

    # Plot Decision Function ----------------------------------
    ax = axes[2]
    label = r"D(T) : Scoring Function | "
    label += f"Total Score: {detection_result.score:.2f}"
    ax.fill_between(
        subset_no_padding.aci_time,
        0,
        detection_result.scoring_result.D,
        label=label,
    )
    axes[2].set_ylabel("D(t)")
    axes[2].legend(loc="upper right")
    axes[2].axhline(0, color="black", linestyle="dashed")
    axes[2].set_ylim(-1, 1)

    add_colorbar(fig, axes[2], im)

    # Fancy MLAT/MLT Xticks -----------------------------------
    add_multirow_xticks(ax, tracers_data)

    # Save Plot -----------------------------------------------
    fname = f"TracersDispersionEvent_{sat}_{start_time.isoformat()}_{end_time.isoformat()}.png"
    os.makedirs(plot_out_dir, exist_ok=True)
    out_path = os.path.join(plot_out_dir, fname)

    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    cprint(f"Wrote plot {out_path}", "green")


def add_colorbar(fig, ax, im):
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.05)
    cb = fig.colorbar(im, cax=cax, orientation="vertical")
    cb.set_label(r"Summed Omni Flux")


def add_multirow_xticks(ax, tracers_data):
    """Add multirow tickmarks to the bottom axis as is common in the
    magnetospheres community.

    Args
      TODO
    """
    xticks = ax.get_xticks()
    new_labels = []

    for time_float in xticks:
        time = num2date(time_float).replace(tzinfo=None)
        i = tracers_data.aci_time.searchsorted(time)
        if i == tracers_data.aci_time.size:
            continue
        mlat = tracers_data.mlat[i]
        mlt = tracers_data.mlt[i]

        new_label = "%s\n%.1f\n%.1f" % (time.strftime("%H:%M:%S"), mlat, mlt)
        new_labels.append(new_label)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        ax.set_xticklabels(new_labels)
        ax.text(-0.09, -0.18, "Time", transform=ax.transAxes)
        ax.text(-0.09, -0.32, "MLAT", transform=ax.transAxes)
        ax.text(-0.09, -0.46, "MLT", transform=ax.transAxes)
