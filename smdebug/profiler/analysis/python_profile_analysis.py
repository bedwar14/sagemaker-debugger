# Standard Library
import json
import pstats

# First Party
from smdebug.core.logger import get_logger
from smdebug.profiler.analysis.python_stats_reader import (
    LocalPythonStatsReader,
    S3PythonStatsReader,
)
from smdebug.profiler.analysis.utils.python_profile_analysis_utils import (
    StepPythonProfileStats,
    cProfileStats,
)
from smdebug.profiler.profiler_constants import CONVERT_TO_MICROSECS
from smdebug.profiler.python_profiler import PyinstrumentPythonProfiler, cProfilePythonProfiler


class PythonProfileAnalysis:
    def __init__(self, local_profile_dir="/tmp/python_stats", s3_path=None):
        """Analysis class that takes in path to the profile directory, and sets up the python stats reader, which
        fetches metadata of the python profiling done for each step. Also provides functions for analysis on this
        profiling, such as fetching stats by a specific step or time interval.

        If s3_path is provided, the S3PythonStatsReader is used and local_profile_dir will represent the local
        directory path that the reader will create the stats directory and then download the stats to.
        Otherwise, LocalPythonStatsReader is used and local_profile_dir represents the path to the stats directory,
        which already holds the stats.

        ...

        Attributes
        ----------
        python_stats_reader: PythonStatsReader
            The reader to use for loading the python stats.
        python_profile_stats: list of StepPythonProfileStats
            List of stats for each step profiled.
        """
        self.python_stats_reader = (
            S3PythonStatsReader(local_profile_dir, s3_path)
            if s3_path
            else LocalPythonStatsReader(local_profile_dir)
        )
        self._refresh_python_profile_stats()

    def _refresh_python_profile_stats(self):
        """Helper function to load in the most recent python stats via the python stats reader.
        """
        get_logger("smdebug-profiler").info("Refreshing python profile stats.")
        self.python_profile_stats = self.python_stats_reader.load_python_profile_stats()

    def fetch_profile_stats_by_time(
        self, start_time_since_epoch_in_secs, end_time_since_epoch_in_secs
    ):
        """API function to fetch stats based on time interval.
        """
        self._refresh_python_profile_stats()
        start_time_since_epoch_in_micros = start_time_since_epoch_in_secs * CONVERT_TO_MICROSECS
        end_time_since_epoch_in_micros = end_time_since_epoch_in_secs * CONVERT_TO_MICROSECS
        return [
            step_stats
            for step_stats in self.python_profile_stats
            if step_stats.in_time_interval(
                start_time_since_epoch_in_micros, end_time_since_epoch_in_micros
            )
        ]

    def fetch_profile_stats_by_step(self, start_step, end_step):
        """API function to fetch stats based on step interval.
        """
        self._refresh_python_profile_stats()
        return [
            step_stats
            for step_stats in self.python_profile_stats
            if step_stats.in_step_interval(start_step, end_step)
        ]

    def fetch_pre_step_zero_profile_stats(self):
        """API function that fetches stats from profiling until step 0.
        """
        return self.fetch_profile_stats_by_step(-1, 0)

    def list_profile_stats(self):
        """API function that the list of python profile stats, which holds the metadata for each instance of profiling
        (one per step).
        """
        self._refresh_python_profile_stats()
        return self.python_profile_stats


class cProfileAnalysis(PythonProfileAnalysis):
    """Analysis class used specifically for python profiling with cProfile
    """

    def _refresh_python_profile_stats(self):
        """Helper function to load in the most recent python stats via the python stats reader.
        Filters out any stats not generated by cProfile.
        """
        super()._refresh_python_profile_stats()
        self.python_profile_stats = list(
            filter(
                lambda x: x.profiler_name == cProfilePythonProfiler.name, self.python_profile_stats
            )
        )

    def fetch_profile_stats_by_step(self, start_step, end_step):
        """API function to fetch aggregated stats based on time interval.
        """
        requested_stats = super().fetch_profile_stats_by_step(start_step, end_step)
        return self._aggregate_python_profile_stats(requested_stats)

    def fetch_profile_stats_by_time(
        self, start_time_since_epoch_in_secs, end_time_since_epoch_in_secs
    ):
        """API function to fetch aggregated stats based on time interval.
        """
        requested_stats = super().fetch_profile_stats_by_time(
            start_time_since_epoch_in_secs, end_time_since_epoch_in_secs
        )
        return self._aggregate_python_profile_stats(requested_stats)

    def _aggregate_python_profile_stats(self, stats):
        """Aggregate the stats files into one pStats.Stats object corresponding to the requested interval.
        Then returns a `cProfileStats` object (which holds the pStats.Stats object and parsed stats for each called
        function in these steps).
        """
        ps = pstats.Stats()
        for step_stats in stats:
            ps.add(step_stats.stats_path)
        return cProfileStats(ps)


class PyinstrumentAnalysis(PythonProfileAnalysis):
    """Analysis class used specifically for python profiling with pyinstrument.
    """

    def _refresh_python_profile_stats(self):
        """Helper function to load in the most recent python stats via the python stats reader.
        Filters out any stats not generated by pyinstrument.
        """
        super()._refresh_python_profile_stats()
        self.python_profile_stats = list(
            filter(
                lambda x: x.profiler_name == PyinstrumentPythonProfiler.name,
                self.python_profile_stats,
            )
        )

    def fetch_profile_stats_by_step(self, start_step, end_step):
        """API function to fetch stats based on time interval as list of dictionaries.
        """
        requested_stats = super().fetch_profile_stats_by_step(start_step, end_step)
        return self._load_json_stats(requested_stats)

    def fetch_profile_stats_by_time(
        self, start_time_since_epoch_in_secs, end_time_since_epoch_in_secs
    ):
        """API function to fetch stats based on time interval as list of dictionaries.
        """
        requested_stats = super().fetch_profile_stats_by_time(
            start_time_since_epoch_in_secs, end_time_since_epoch_in_secs
        )
        return self._load_json_stats(requested_stats)

    def _load_json_stats(self, stats):
        """Load and return a list of dictionaries corresponding to each step's stats file.
        """
        json_stats = []
        for step_stats in stats:
            with open(step_stats.stats_path, "r") as stats:
                json_stats.append(json.load(stats))
        return json_stats
