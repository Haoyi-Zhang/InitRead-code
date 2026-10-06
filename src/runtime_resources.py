"""Resource telemetry only; never supplies a scientific decision or fake RSS."""
import sys
try:
    import resource as _resource
except ImportError:
    _resource = None


def self_peak_rss_kib():
    # Linux ru_maxrss has KiB units. No conversion or substitute is claimed for
    # other platforms; in particular Python's resource module is absent on Windows.
    if _resource is None or not sys.platform.startswith('linux'):
        return None
    return _resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss
