import re
import matplotlib.pyplot as plt
import numpy as np
import os # Added for path operations
from datetime import datetime # Added for unique filenames

LOG_FILE_TLS = "/home/nikba/DrivenDroneMQTT/logs/mqtt_timing_2025-05-30_with_tls_1.log"
LOG_FILE_NO_TLS = "/home/nikba/DrivenDroneMQTT/logs/mqtt_timing_2025-05-30_no_tls_1.log"
ASSETS_DIR = "/home/nikba/DrivenDroneMQTT/assets/"

def parse_log_file(filepath):
    """
    Parses a log file to extract message latencies.
    Returns two lists:
      - latencies: normal message latencies (no GS-SEND)
      - gs_send_latencies: tuples (index, latency) for GS-SEND messages
    """
    send_events = {}  # Stores {msg_id: timestamp}
    latencies = []
    gs_send_latencies = []  # Store (index, latency) for GS-SEND events
    gs_send_ids = set()  # Store UUIDs of GS-SEND events

    # Regex to capture:
    # Group 1: Event type (e.g., DRONE-SEND, GS-RECV)
    # Group 2: Message ID
    # Group 3: Timestamp
    log_pattern = re.compile(
        r"^\S+\s+\S+\s+-\s+(DRONE-SEND|GS-SEND|DRONE-RECV|GS-RECV):\s+"
        r"Message ID ([\w-]+)\s+type\s+\w+\s+(?:sent|received) at ([\d.]+)"
    )

    lines_processed = 0
    lines_matched_regex = 0
    send_events_recorded = 0
    recv_events_found_pair = 0
    recv_events_no_pair = 0

    print(f"\nStarting to parse: {filepath}")
    try:
        with open(filepath, 'r') as f:
            for line in f:
                lines_processed += 1
                match = log_pattern.search(line)
                if match:
                    lines_matched_regex += 1
                    event_type, msg_id, timestamp_str = match.groups()
                    timestamp = float(timestamp_str)

                    if event_type == "GS-SEND":
                        gs_send_ids.add(msg_id)
                        continue  # Don't store GS-SEND as a send event

                    if event_type.endswith("-SEND"):
                        send_events[msg_id] = timestamp
                        send_events_recorded += 1
                    elif event_type.endswith("-RECV"):
                        if msg_id in send_events:
                            send_time = send_events[msg_id]
                            latency_ms = (timestamp - send_time) * 1000  # Convert to milliseconds
                            if msg_id in gs_send_ids:
                                gs_send_latencies.append((len(latencies) + len(gs_send_latencies), latency_ms))
                            else:
                                latencies.append(latency_ms)
                            recv_events_found_pair += 1
                            del send_events[msg_id]
                        else:
                            recv_events_no_pair += 1
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return [], []
    except Exception as e:
        print(f"An error occurred while parsing {filepath}: {e}")
        return [], []
    
    print(f"Finished parsing {filepath}:")
    print(f"  Lines processed: {lines_processed}")
    print(f"  Lines matched by regex: {lines_matched_regex}")
    print(f"  SEND events recorded: {send_events_recorded}")
    print(f"  RECV events that found a pair: {recv_events_found_pair}")
    print(f"  RECV events without a matching SEND: {recv_events_no_pair}")
    print(f"  Calculated latencies: {len(latencies)}")
    if send_events:
        print(f"  Unmatched SEND events remaining: {len(send_events)}")

    print(f"  GS-SEND message IDs to be shown in green: {len(gs_send_latencies)}")
    return latencies, gs_send_latencies

def calculate_stats(latencies):
    """Calculates statistics for a list of latencies."""
    if not latencies:
        return None  # Return None if no latencies to calculate stats for
    
    np_latencies = np.array(latencies)
    return {
        'mean': np.mean(np_latencies),
        'std': np.std(np_latencies),
        'min': np.min(np_latencies),
        'max': np.max(np_latencies),
        'count': len(np_latencies)
    }

def plot_latencies(latencies_tls, label_tls, stats_tls,
                   latencies_no_tls, label_no_tls, stats_no_tls,
                   gs_send_tls=None, gs_send_no_tls=None):
    """Plots the latencies and displays statistics. Optionally highlights GS-SEND points in green."""
    plt.figure(figsize=(14, 8))
    
    ax = plt.gca() # Get current axes

    if latencies_tls and stats_tls:
        x_tls = range(stats_tls['count'])
        plt.plot(x_tls, latencies_tls, label=f"{label_tls} (N={stats_tls['count']})", alpha=0.7, marker='o', linestyle='-', markersize=4)
        # Plot GS-SEND points in green
        if gs_send_tls:
            for idx, latency in gs_send_tls:
                plt.scatter(idx, latency, color='green', s=60, marker='o', label='GS-SEND (TLS)' if idx == gs_send_tls[0][0] else "")

    if latencies_no_tls and stats_no_tls:
        x_no_tls = range(stats_no_tls['count'])
        plt.plot(x_no_tls, latencies_no_tls, label=f"{label_no_tls} (N={stats_no_tls['count']})", alpha=0.7, marker='x', linestyle='--', markersize=4)
        # Plot GS-SEND points in green
        if gs_send_no_tls:
            for idx, latency in gs_send_no_tls:
                plt.scatter(idx, latency, color='green', s=60, marker='o', label='GS-SEND (No TLS)' if idx == gs_send_no_tls[0][0] else "")

    plt.xlabel("Message Sequence Index (Comandi)")
    plt.ylabel("Latency (ms)")
    plt.title("MQTT Message Latency Comparison: TLS vs. No TLS")
    plt.legend(loc='upper left')
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)

    # Prepare text for statistics
    text_y_current = 0.95  # Start Y position for text (relative to axes)
    text_x_pos = 1.02    # X position for text (to the right of the plot area)
    line_height = 0.04   # Approximate height for one line of text
    box_padding = 0.03   # Padding around text group

    if stats_tls:
        stats_text_tls = (f"{label_tls} Stats:\n"
                          f"Avg: {stats_tls['mean']:.2f} ms\n"
                          f"Std: {stats_tls['std']:.2f} ms\n"
                          f"Min: {stats_tls['min']:.2f} ms\n"
                          f"Max: {stats_tls['max']:.2f} ms")
        plt.text(text_x_pos, text_y_current, stats_text_tls,
                 transform=ax.transAxes, fontsize=9, va='top', ha='left',
                 bbox=dict(boxstyle='round,pad=0.5', fc='skyblue', alpha=0.5))
        text_y_current -= (stats_text_tls.count('\n') + 1) * line_height + box_padding


    if stats_no_tls:
        stats_text_no_tls = (f"{label_no_tls} Stats:\n"
                             f"Avg: {stats_no_tls['mean']:.2f} ms\n"
                             f"Std: {stats_no_tls['std']:.2f} ms\n"
                             f"Min: {stats_no_tls['min']:.2f} ms\n"
                             f"Max: {stats_no_tls['max']:.2f} ms")
        plt.text(text_x_pos, text_y_current, stats_text_no_tls,
                 transform=ax.transAxes, fontsize=9, va='top', ha='left',
                 bbox=dict(boxstyle='round,pad=0.5', fc='lightcoral', alpha=0.5))

    if not (latencies_tls or latencies_no_tls):
        plt.text(0.5, 0.5, "No latency data to display.",
                 horizontalalignment='center', verticalalignment='center',
                 transform=ax.transAxes, fontsize=12)

    # Adjust layout to make space for the text boxes next to the plot
    plt.subplots_adjust(right=0.75) 
    
    # Ensure the assets directory exists
    try:
        os.makedirs(ASSETS_DIR, exist_ok=True)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"latency_comparison_{timestamp_str}.png"
        filepath = os.path.join(ASSETS_DIR, filename)
        plt.savefig(filepath, bbox_inches='tight') # bbox_inches='tight' helps to include labels
        print(f"\nGraph saved to: {filepath}")
    except Exception as e:
        print(f"Error saving graph: {e}")
    
    plt.show()

if __name__ == "__main__":
    print(f"Parsing TLS log file: {LOG_FILE_TLS}")
    latencies_tls, gs_send_tls = parse_log_file(LOG_FILE_TLS)
    print(f"Found {len(latencies_tls)} latencies with TLS.")

    print(f"Parsing No-TLS log file: {LOG_FILE_NO_TLS}")
    latencies_no_tls, gs_send_no_tls = parse_log_file(LOG_FILE_NO_TLS)
    print(f"Found {len(latencies_no_tls)} latencies without TLS.")

    if latencies_tls and latencies_no_tls:
        min_len = min(len(latencies_tls), len(latencies_no_tls))
        if len(latencies_tls) != len(latencies_no_tls):
            print(f"\nAdjusting datasets to the same number of samples: {min_len}")
            latencies_tls = latencies_tls[:min_len]
            latencies_no_tls = latencies_no_tls[:min_len]
            # Also adjust GS-SEND indices
            gs_send_tls = [(idx, lat) for idx, lat in gs_send_tls if idx < min_len]
            gs_send_no_tls = [(idx, lat) for idx, lat in gs_send_no_tls if idx < min_len]
            print(f"  New count for TLS latencies: {len(latencies_tls)}")
            print(f"  New count for No-TLS latencies: {len(latencies_no_tls)}")
        else:
            print(f"\nBoth datasets have the same number of samples: {len(latencies_tls)}")

    if not latencies_tls and not latencies_no_tls:
        print("No latency data could be extracted from the log files.")
        plot_latencies([], "With TLS", None, [], "Without TLS", None, [], [])
    else:
        stats_tls_data = calculate_stats(latencies_tls)
        stats_no_tls_data = calculate_stats(latencies_no_tls)
        plot_latencies(
            latencies_tls, "With TLS", stats_tls_data,
            latencies_no_tls, "Without TLS", stats_no_tls_data,
            gs_send_tls, gs_send_no_tls
        )
