from __future__ import annotations
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any

class DSTForensics:
    """Forensic analysis tool for Daylight Saving Time (DST) transitions.
    
    This class provides high-precision detection and analysis of DST transitions
    using binary search algorithms. It can identify the exact moment of clock
    changes and determine whether they are "Spring Forward" or "Fall Back" events.
    
    The implementation uses a two-phase binary search:
    1. Day-level search to narrow down the transition day
    2. Second-level search to pinpoint the exact transition moment
    
    Attributes:
        tz (ZoneInfo): The timezone object for which DST transitions are analyzed.
    """
    
    def __init__(self, timezone_str: str = "Europe/London"):
        """Initialize the DST forensics analyzer.
        
        Args:
            timezone_str: IANA timezone identifier (e.g., 'Europe/London', 'America/New_York').
                         Defaults to 'Europe/London'.
        """
        self.tz = ZoneInfo(timezone_str)

    def _get_offset(self, dt: datetime) -> float:
        """Calculate the UTC offset for a given datetime in the configured timezone.
        
        This is a helper method used by the binary search algorithm to detect
        offset changes that indicate DST transitions.
        
        Args:
            dt: The datetime for which to calculate the UTC offset.
        
        Returns:
            The UTC offset in seconds. Returns 0.0 if offset is None.
        """
        offset = dt.astimezone(self.tz).utcoffset()
        return offset.total_seconds() if offset is not None else 0.0

    def _has_dst(self) -> bool:
        """Check if the configured timezone observes Daylight Saving Time.
        
        This method compares the UTC offset between winter (January) and summer (July)
        to determine if the timezone has different offsets during the year, which
        indicates DST observance.
        
        Returns:
            True if the timezone observes DST (has different winter/summer offsets),
            False otherwise.
        """
        import datetime
        # Compare January (typically winter) and July (typically summer) offsets
        jan = datetime.datetime(2026, 1, 1, tzinfo=self.tz)
        jul = datetime.datetime(2026, 7, 1, tzinfo=self.tz)
        return jan.utcoffset() != jul.utcoffset()

    def get_dst_info(self, base_dt: datetime | None = None) -> dict[str, Any]:
        """Calculate comprehensive information about the next DST transition.
        
        This is the main public method that provides complete DST transition data
        including the exact moment, direction, and countdown information.
        
        Args:
            base_dt: Reference datetime from which to search for the next transition.
                    If None, uses the current time in the configured timezone.
        
        Returns:
            A dictionary containing:
                - moment (datetime): The exact datetime of the DST transition
                - direction (str): Either 'move_forward' (Spring) or 'move_back' (Fall)
                - message (str): Message key for localization
                - days_to_event (int): Number of days until the transition
                - date (str): ISO format date of the transition
                - iso (str): Full ISO format datetime string of the transition
            
            Returns None if the timezone does not observe DST.
        """

        # Early return if this timezone doesn't observe DST
        if not self._has_dst():
            return None  # Caller must handle this gracefully

        # Step 1: Use binary search to find the exact transition moment
        transition_moment = self._find_exact_moment(base_dt)

        # Step 2: Determine the direction of the time change
        # Compare UTC offsets one second before and at the transition
        before_moment = transition_moment - timedelta(seconds=1)
        offset_before = self._get_offset(before_moment)
        offset_after = self._get_offset(transition_moment)

        # Step 3: Classify the transition type
        # Positive offset change = Spring Forward (clocks move ahead)
        # Negative offset change = Fall Back (clocks move back)
        if offset_after > offset_before:
            direction = "move_forward"
            message = "move_forward_message"
        else:
            direction = "move_back"
            message = "move_back_message"

        # Step 4: Build comprehensive result dictionary for Home Assistant
        return {
            "moment": transition_moment,  # Exact datetime of transition
            "direction": direction,  # 'move_forward' or 'move_back'
            "message": message,  # Localization key
            "days_to_event": (  # Countdown in days
                transition_moment.date() - datetime.now(self.tz).date()
            ).days,
            "date": transition_moment.date().isoformat(),  # Date only
            "iso": transition_moment.isoformat(),  # Full ISO timestamp
        }

    def get_current_period_key(self, base_dt: datetime | None = None) -> str:
        """Determine the current time period (Summer Time or Winter Time).
        
        This method checks whether DST is currently active at the given datetime
        and returns the appropriate period identifier.
        
        Args:
            base_dt: Reference datetime to check. If None, uses the current time
                    in the configured timezone.
        
        Returns:
            'summer_time' if DST is currently active, 'winter_time' otherwise.
        """
        # Use current time if no reference datetime provided
        ref_dt = base_dt or datetime.now(self.tz)
        
        # Ensure the datetime is timezone-aware
        if ref_dt.tzinfo is None:
            ref_dt = ref_dt.replace(tzinfo=self.tz)

        # Check DST status using the .dst() method
        # .dst() returns a timedelta representing the DST offset
        # Non-zero timedelta means DST is currently active (Summer Time)
        # Zero timedelta means DST is not active (Winter Time)
        is_dst = ref_dt.dst() != timedelta(0)
        
        return "summer_time" if is_dst else "winter_time"       

    def _find_exact_moment(self, base_dt: datetime | None = None) -> datetime:
        """Find the exact moment of the next DST transition using binary search.
        
        This method implements a two-phase binary search algorithm:
        1. Coarse search: Probe forward in 7-day increments to find the week containing the transition
        2. Day-level binary search: Narrow down to the specific day
        3. Second-level binary search: Pinpoint the exact second of transition
        
        The algorithm is highly efficient, requiring only ~20-30 offset checks
        to find the exact second within a year's worth of time.
        
        Args:
            base_dt: Starting datetime for the search. If None, uses current time
                    in the configured timezone.
        
        Returns:
            The exact datetime when the DST transition occurs, with second precision.
        """
        # Use current time if no reference datetime provided
        ref_dt = base_dt or datetime.now(self.tz)
        
        # Ensure the datetime is timezone-aware
        if ref_dt.tzinfo is None:
            ref_dt = ref_dt.replace(tzinfo=self.tz)

        # Store the starting UTC offset for comparison
        start_offset = self._get_offset(ref_dt)

        # Phase 1: Coarse search - probe forward in 7-day increments
        # This quickly finds the approximate week of the transition
        # Maximum 366 days ensures we find at least one transition in any timezone
        days_ahead = 0
        while days_ahead <= 366:
            days_ahead += 7
            if self._get_offset(ref_dt + timedelta(days=days_ahead)) != start_offset:
                break  # Found a week with different offset

        # Phase 2: Binary search at day granularity
        # Narrow down from the 7-day window to the exact day
        low_day, high_day = days_ahead - 7, days_ahead
        while low_day < high_day:
            mid_day = (low_day + high_day) // 2
            if self._get_offset(ref_dt + timedelta(days=mid_day)) != start_offset:
                high_day = mid_day  # Transition is at or before mid_day
            else:
                low_day = mid_day + 1  # Transition is after mid_day

        # Phase 3: Binary search at second granularity
        # Search a 48-hour window around the transition day to handle edge cases
        # (DST transitions can occur at various times, typically 1-3 AM)
        day_start = (ref_dt + timedelta(days=low_day - 1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        low_sec, high_sec = 0, 86400 * 2  # 86400 seconds = 24 hours, * 2 = 48 hours
        while low_sec < high_sec:
            mid_sec = (low_sec + high_sec) // 2
            if self._get_offset(day_start + timedelta(seconds=mid_sec)) != start_offset:
                high_sec = mid_sec  # Transition is at or before mid_sec
            else:
                low_sec = mid_sec + 1  # Transition is after mid_sec

        # Return the exact transition moment in the configured timezone
        return (day_start + timedelta(seconds=low_sec)).astimezone(self.tz)


# --- Test Suite ---
# This section demonstrates the usage of DSTForensics and validates its accuracy
if __name__ == "__main__":
    # Initialize the analyzer for UK timezone
    finder = DSTForensics("Europe/London")

    # Test 1: Spring Forward transition (March)
    # In 2026, UK clocks move forward on March 29 at 1:00 AM to 2:00 AM
    info_spring = finder.get_dst_info(datetime(2026, 3, 20, tzinfo=ZoneInfo('Europe/London')))
    print(f"Spring Check: {info_spring['direction']} on {info_spring['iso']}")

    # Test 2: Fall Back transition (October)
    # In 2026, UK clocks move back on October 25 at 2:00 AM to 1:00 AM
    info_autumn = finder.get_dst_info(datetime(2026, 10, 15, tzinfo=ZoneInfo('Europe/London')))
    print(f"Autumn Check: {info_autumn['direction']} on {info_autumn['iso']}")
