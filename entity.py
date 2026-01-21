from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any


class DSTForensics:
    def __init__(self, timezone_str: str = "Europe/London"):
        self.tz = ZoneInfo(timezone_str)

    def _get_offset(self, dt: datetime) -> float:
        offset = dt.astimezone(self.tz).utcoffset()
        return offset.total_seconds() if offset is not None else 0.0

    def get_dst_info(self, base_dt: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Calculates the next DST transition and determines if it is
        a 'Spring Forward' or 'Fall Back' event.
        """
        # 1. Reuse your precision search to find the exact moment
        transition_moment = self._find_exact_moment(base_dt)

        # 2. Check the offset change
        # One second before the transition
        before_moment = transition_moment - timedelta(seconds=1)

        offset_before = self._get_offset(before_moment)
        offset_after = self._get_offset(transition_moment)

        # 3. Determine Direction
        if offset_after > offset_before:
            direction = "move_forward"
            message = "move_forward_message"
        else:
            direction = "move_back"
            message = "move_back_message"

        # 4. Format for Home Assistant
        return {
            "moment": transition_moment,
            "direction": direction,
            "message": message,
            "days_to_event": (
                transition_moment.date() - datetime.now(self.tz).date()
            ).days,
            "date": transition_moment.date().isoformat(),
            "iso": transition_moment.isoformat(),
        }

    def get_current_period_key(self, base_dt: Optional[datetime] = None) -> str:
        """
        Returns 'Summer Time' or 'Winter Time' based on the 
        current DST status of the timezone.
        """
        ref_dt = base_dt or datetime.now(self.tz)
        if ref_dt.tzinfo is None:
            ref_dt = ref_dt.replace(tzinfo=self.tz)

        # .dst() returns a timedelta of the DST offset. 
        # Non-zero means Summer/Daylight Saving Time is active.
        is_dst = ref_dt.dst() != timedelta(0)
        
        return "summer_time" if is_dst else "winter_time"       

    def _find_exact_moment(self, base_dt: Optional[datetime] = None) -> datetime:
        """The precision binary search we built earlier."""
        ref_dt = base_dt or datetime.now(self.tz)
        if ref_dt.tzinfo is None:
            ref_dt = ref_dt.replace(tzinfo=self.tz)

        start_offset = self._get_offset(ref_dt)

        # Probe in 7-day jumps
        days_ahead = 0
        while days_ahead <= 366:
            days_ahead += 7
            if self._get_offset(ref_dt + timedelta(days=days_ahead)) != start_offset:
                break

        # Binary Search: Day
        low_day, high_day = days_ahead - 7, days_ahead
        while low_day < high_day:
            mid_day = (low_day + high_day) // 2
            if self._get_offset(ref_dt + timedelta(days=mid_day)) != start_offset:
                high_day = mid_day
            else:
                low_day = mid_day + 1

        # Binary Search: Second (Searching 48 hours around the target day)
        day_start = (ref_dt + timedelta(days=low_day - 1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        low_sec, high_sec = 0, 86400 * 2
        while low_sec < high_sec:
            mid_sec = (low_sec + high_sec) // 2
            if self._get_offset(day_start + timedelta(seconds=mid_sec)) != start_offset:
                high_sec = mid_sec
            else:
                low_sec = mid_sec + 1

        return (day_start + timedelta(seconds=low_sec)).astimezone(self.tz)


# --- Test ---
if __name__ == "__main__":
    finder = DSTForensics("Europe/London")

    # Test Spring (March)
    info_spring = finder.get_dst_info(datetime(2026, 3, 20))
    print(f"Spring Check: {info_spring['direction']} on {info_spring['iso']}")

    # Test Autumn (October)
    info_autumn = finder.get_dst_info(datetime(2026, 10, 15))
    print(f"Autumn Check: {info_autumn['direction']} on {info_autumn['iso']}")
