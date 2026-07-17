"""GPU-agnostic display switching via the Windows CCD API.

The original NSE shelled out to ``DisplaySwitch.exe /internal`` to drop down to
a single display. That command applies the ``SDC_TOPOLOGY_INTERNAL`` topology,
which keeps whichever display path Windows happens to enumerate first. On a
desktop there is no true "internal" panel, so the surviving monitor depends on
GPU/driver enumeration and which physical port each monitor is plugged into --
change the GPU and the "kept" monitor can change with it.

This module instead targets the *primary* monitor by identity: the source whose
desktop position is (0, 0). It queries the active display configuration, keeps
only the primary path active, and applies the result with ``SetDisplayConfig``.
The choice is therefore independent of GPU, driver, and cabling.
"""

import ctypes
from ctypes import wintypes

# ── CCD constants ─────────────────────────────────────────────────────────────
QDC_ONLY_ACTIVE_PATHS = 0x00000002

SDC_APPLY = 0x00000080
SDC_USE_SUPPLIED_DISPLAY_CONFIG = 0x00000020
SDC_ALLOW_CHANGES = 0x00000400
SDC_SAVE_TO_DATABASE = 0x00000200

DISPLAYCONFIG_PATH_ACTIVE = 0x00000001
DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE = 1
DISPLAYCONFIG_PATH_MODE_IDX_INVALID = 0xFFFFFFFF

ERROR_SUCCESS = 0


# ── Structures (see wingdi.h / winuser.h) ─────────────────────────────────────
class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class DISPLAYCONFIG_PATH_SOURCE_INFO(ctypes.Structure):
    _fields_ = [
        ("adapterId", LUID),
        ("id", wintypes.UINT),
        ("modeInfoIdx", wintypes.UINT),
        ("statusFlags", wintypes.UINT),
    ]


class DISPLAYCONFIG_RATIONAL(ctypes.Structure):
    _fields_ = [("Numerator", wintypes.UINT), ("Denominator", wintypes.UINT)]


class DISPLAYCONFIG_PATH_TARGET_INFO(ctypes.Structure):
    _fields_ = [
        ("adapterId", LUID),
        ("id", wintypes.UINT),
        ("modeInfoIdx", wintypes.UINT),
        ("outputTechnology", wintypes.UINT),
        ("rotation", wintypes.UINT),
        ("scaling", wintypes.UINT),
        ("refreshRate", DISPLAYCONFIG_RATIONAL),
        ("scanLineOrdering", wintypes.UINT),
        ("targetAvailable", wintypes.BOOL),
        ("statusFlags", wintypes.UINT),
    ]


class DISPLAYCONFIG_PATH_INFO(ctypes.Structure):
    _fields_ = [
        ("sourceInfo", DISPLAYCONFIG_PATH_SOURCE_INFO),
        ("targetInfo", DISPLAYCONFIG_PATH_TARGET_INFO),
        ("flags", wintypes.UINT),
    ]


class DISPLAYCONFIG_2DREGION(ctypes.Structure):
    _fields_ = [("cx", wintypes.UINT), ("cy", wintypes.UINT)]


class DISPLAYCONFIG_VIDEO_SIGNAL_INFO(ctypes.Structure):
    _fields_ = [
        ("pixelRate", ctypes.c_uint64),
        ("hSyncFreq", DISPLAYCONFIG_RATIONAL),
        ("vSyncFreq", DISPLAYCONFIG_RATIONAL),
        ("activeSize", DISPLAYCONFIG_2DREGION),
        ("totalSize", DISPLAYCONFIG_2DREGION),
        ("videoStandard", wintypes.UINT),
        ("scanLineOrdering", wintypes.UINT),
    ]


class DISPLAYCONFIG_TARGET_MODE(ctypes.Structure):
    _fields_ = [("targetVideoSignalInfo", DISPLAYCONFIG_VIDEO_SIGNAL_INFO)]


class POINTL(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class DISPLAYCONFIG_SOURCE_MODE(ctypes.Structure):
    _fields_ = [
        ("width", wintypes.UINT),
        ("height", wintypes.UINT),
        ("pixelFormat", wintypes.UINT),
        ("position", POINTL),
    ]


class RECTL(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class DISPLAYCONFIG_DESKTOP_IMAGE_INFO(ctypes.Structure):
    _fields_ = [
        ("PathSourceSize", POINTL),
        ("DesktopImageRegion", RECTL),
        ("DesktopImageClip", RECTL),
    ]


class DISPLAYCONFIG_MODE_INFO_UNION(ctypes.Union):
    _fields_ = [
        ("targetMode", DISPLAYCONFIG_TARGET_MODE),
        ("sourceMode", DISPLAYCONFIG_SOURCE_MODE),
        ("desktopImageInfo", DISPLAYCONFIG_DESKTOP_IMAGE_INFO),
    ]


class DISPLAYCONFIG_MODE_INFO(ctypes.Structure):
    _fields_ = [
        ("infoType", wintypes.UINT),
        ("id", wintypes.UINT),
        ("adapterId", LUID),
        ("u", DISPLAYCONFIG_MODE_INFO_UNION),
    ]


def _user32():
    return ctypes.windll.user32


def engage_primary_only():
    """Keep only the Windows primary monitor active.

    Returns ``(True, None)`` on success or ``(False, message)`` on failure.
    """
    user32 = _user32()

    num_paths = wintypes.UINT()
    num_modes = wintypes.UINT()
    rc = user32.GetDisplayConfigBufferSizes(
        QDC_ONLY_ACTIVE_PATHS, ctypes.byref(num_paths), ctypes.byref(num_modes)
    )
    if rc != ERROR_SUCCESS:
        return False, f"GetDisplayConfigBufferSizes failed (error {rc})."

    paths = (DISPLAYCONFIG_PATH_INFO * num_paths.value)()
    modes = (DISPLAYCONFIG_MODE_INFO * num_modes.value)()
    rc = user32.QueryDisplayConfig(
        QDC_ONLY_ACTIVE_PATHS,
        ctypes.byref(num_paths),
        paths,
        ctypes.byref(num_modes),
        modes,
        None,
    )
    if rc != ERROR_SUCCESS:
        return False, f"QueryDisplayConfig failed (error {rc})."

    # Locate the primary path: its source mode sits at desktop position (0, 0).
    primary_idx = None
    for i in range(num_paths.value):
        path = paths[i]
        if not (path.flags & DISPLAYCONFIG_PATH_ACTIVE):
            continue
        mode_idx = path.sourceInfo.modeInfoIdx
        if mode_idx == DISPLAYCONFIG_PATH_MODE_IDX_INVALID or mode_idx >= num_modes.value:
            continue
        mode = modes[mode_idx]
        if mode.infoType != DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE:
            continue
        pos = mode.u.sourceMode.position
        if pos.x == 0 and pos.y == 0:
            primary_idx = i
            break

    if primary_idx is None:
        return False, "Could not identify the primary monitor."

    # Deactivate every other path; leave the primary untouched.
    for i in range(num_paths.value):
        if i == primary_idx:
            continue
        paths[i].flags &= ~DISPLAYCONFIG_PATH_ACTIVE
        paths[i].sourceInfo.modeInfoIdx = DISPLAYCONFIG_PATH_MODE_IDX_INVALID
        paths[i].targetInfo.modeInfoIdx = DISPLAYCONFIG_PATH_MODE_IDX_INVALID

    flags = (
        SDC_APPLY
        | SDC_USE_SUPPLIED_DISPLAY_CONFIG
        | SDC_ALLOW_CHANGES
        | SDC_SAVE_TO_DATABASE
    )
    rc = user32.SetDisplayConfig(num_paths.value, paths, num_modes.value, modes, flags)
    if rc != ERROR_SUCCESS:
        return False, f"SetDisplayConfig failed (error {rc})."

    return True, None
