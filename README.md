# DST Transition Sensor for Home Assistant

A precision, "set-and-forget" custom integration that calculates the exact moment of the next Daylight Saving Time (DST) transition for your Home Assistant instance.

Unlike simple template sensors that check day-by-day, this integration uses a high-efficiency **Binary Search Algorithm** to identify the exact second the clocks shift, providing you with the transition timestamp, direction (Spring Forward/Fall Back), and an accurate countdown.

## Key Features

- **Zero Configuration:** Automatically detects the timezone from your Home Assistant system settings. No manual input required.
- **High Precision:** Identifies the exact second of the transition.
- **Directional Awareness:** Specifically identifies if the event is a "Spring Forward" (Summer Time) or "Fall Back" (Standard Time) transition.
- **Resource Efficient:** Performs calculations exactly once per day at `00:01 AM` (or upon restart), using virtually 0% CPU for the remainder of the day.
- **Local First:** Operates entirely on your local hardware without any external API calls or internet reliance.

## Installation

### Manual Installation
1. Download the `dstsensor` folder from this repository.
2. Copy the folder into your Home Assistant `custom_components/` directory.
3. Restart Home Assistant.
4. Go to **Settings > Devices & Services > Add Integration**.
5. Search for **DST Transition Sensor** and click to install.

---

## Sensors & Attributes

Once installed, the integration creates a single entity: `sensor.next_dst_change`.

### State
The main state of the sensor is the **Date** of the next transition (ISO format: `YYYY-MM-DD`).

### Attributes
| Attribute | Description | Example |
| :--- | :--- | :--- |
| `moment` | The exact timestamp of the shift | `2026-03-29T01:00:00+00:00` |
| `direction` | Whether clocks go forward or back | `Move Forward` |
| `days_to_event` | Days remaining until the transition (default state) | `71` |
| `timezone` | The timezone being monitored | `Europe/London` |
| `message` | Formatted message | `Clocks go forward (lose 1 hour)` |

---

## How it works (The Binary Search)

To ensure maximum efficiency and precision, the integration employs a multi-tier search strategy rather than a standard linear loop:

1. **Probe:** The logic jumps in 7-day increments to find the specific week where the UTC offset changes.
2. **Day Search:** Uses a binary search within that week to identify the specific 24-hour window of the change.
3. **Second Search:** Performs a final binary search across the 86,400 seconds of that day to pinpoint the exact moment the offset shifts.

This mathematical approach allows the sensor to find a single specific second out of the millions of seconds in a year in approximately **30-40 checks**, making it significantly faster and lighter than traditional Jinja2 templates.

## Dashboard Example

You can use the attributes to create a highly informative dashboard card:

```yaml
type: entity
entity: sensor.next_dst_change
name: "Next Clock Change"
state_color: true
attribute: direction