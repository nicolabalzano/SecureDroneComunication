import re
import matplotlib.pyplot as plt
import numpy as np
import os # Added for path operations
from datetime import datetime # Added for unique filenames

LOG_FILE_TLS = "/home/nikba/DrivenDroneMQTT/logs/mqtt_timing_2025-06-01_with_tls_025.log"
LOG_FILE_NO_TLS = "/home/nikba/DrivenDroneMQTT/logs/mqtt_timing_2025-06-01_no_tls_025.log"
ASSETS_DIR = "/home/nikba/DrivenDroneMQTT/assets/"

# Battery metrics - modify these values manually before running
# TLS test battery metrics
BATTERY_PERCENTAGE_TLS = 72.0  # Battery remaining percentage (0-100%) during TLS test

# No-TLS test battery metrics
BATTERY_PERCENTAGE_NO_TLS = 72.0  # Battery remaining percentage (0-100%) during No-TLS test

def parse_log_file(filepath):
    """
    Parses a log file to extract message latencies.
    Returns:
        latencies: list of (latency_ms, msg_id, is_gs_send)
        gs_send_ids: set of UUIDs che hanno GS-SEND
    """
    send_events = {}  # Stores {msg_id: timestamp}
    latencies = []    # List of (latency_ms, msg_id, is_gs_send)
    gs_send_ids = set()  # Store UUIDs of GS-SEND events
    first_timestamp = None  # Timestamp del primo sample
    last_timestamp = None   # Timestamp dell'ultimo sample

    log_pattern = re.compile(
        r"^\S+\s+\S+\s+-\s+(DRONE-SEND|GS-SEND|DRONE-RECV|GS-RECV):\s+"
        r"Message ID ([\w-]+)\s+type\s+\w+\s+(?:sent|received) at ([\d.]+)"
    )

    lines_processed = 0
    lines_matched_regex = 0
    send_events_recorded = 0
    recv_events_found_pair = 0
    recv_events_no_pair = 0
    max_samples = 5000  # Limite massimo di sample

    print(f"\nStarting to parse: {filepath}")
    try:
        with open(filepath, 'r') as f:
            for line in f:
                # Controlla se abbiamo raggiunto il limite di sample
                if len(latencies) >= max_samples:
                    print(f"  Reached maximum sample limit of {max_samples}, stopping parsing.")
                    break
                lines_processed += 1
                match = log_pattern.search(line)
                if match:
                    lines_matched_regex += 1
                    event_type, msg_id, timestamp_str = match.groups()
                    timestamp = float(timestamp_str)
                    
                    # Traccia il primo timestamp
                    if first_timestamp is None:
                        first_timestamp = timestamp
                    
                    if event_type == "GS-SEND":
                        gs_send_ids.add(msg_id)
                        print(f"Found GS-SEND message ID (will also be treated as a send event): {msg_id}")
                        # RIMOSSO: continue  # Don't store GS-SEND as a send event

                    if event_type.endswith("-SEND"): # Ora GS-SEND corrisponderà anche a questo
                        send_events[msg_id] = timestamp
                        send_events_recorded += 1
                    elif event_type.endswith("-RECV"):
                        if msg_id in send_events:
                            is_gs_send = msg_id in gs_send_ids # Questo determina il colore
                            send_time = send_events[msg_id]
                            latency_ms = (timestamp - send_time) * 1000  # Convert to milliseconds
                            latencies.append((latency_ms, msg_id, is_gs_send))
                            # Aggiorna l'ultimo timestamp quando aggiungiamo una latenza
                            last_timestamp = timestamp
                            if is_gs_send:
                                print(f"  Appended latency for GS-involved message {msg_id}: {latency_ms:.2f}ms, is_gs_send={is_gs_send}, index={len(latencies)-1}")
                            recv_events_found_pair += 1
                            del send_events[msg_id]
                        else:
                            recv_events_no_pair += 1
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return [], set()
    except Exception as e:
        print(f"An error occurred while parsing {filepath}: {e}")
        return [], set()
    
    print(f"Finished parsing {filepath}:")
    print(f"  Lines processed: {lines_processed}")
    print(f"  Lines matched by regex: {lines_matched_regex}")
    print(f"  SEND events recorded: {send_events_recorded}")
    print(f"  RECV events that found a pair: {recv_events_found_pair}")
    print(f"  RECV events without a matching SEND: {recv_events_no_pair}")
    print(f"  Calculated latencies: {len(latencies)}")
    if send_events:
        print(f"  Unmatched SEND events remaining: {len(send_events)}")

    print(f"  Found {len(gs_send_ids)} GS-SEND message IDs.")
    num_gs_true_in_latencies = sum(1 for _, _, is_gs in latencies if is_gs)
    print(f"  Total latencies marked as is_gs_send=True in the returned list: {num_gs_true_in_latencies}")
    print(f"  Total samples collected: {len(latencies)} (max allowed: {max_samples})")
    
    # Calcola e stampa il tempo totale tra primo e ultimo sample
    time_span_info = None
    if first_timestamp is not None and last_timestamp is not None and len(latencies) > 0:
        total_time_seconds = last_timestamp - first_timestamp
        total_time_minutes = total_time_seconds / 60.0
        time_span_info = {
            'seconds': total_time_seconds,
            'minutes': total_time_minutes,
            'first_timestamp': first_timestamp,
            'last_timestamp': last_timestamp
        }
        print(f"  Time span from first to last sample: {total_time_seconds:.2f} seconds ({total_time_minutes:.2f} minutes)")
    else:
        print(f"  No valid time span calculated (insufficient data)")
    
    return latencies, gs_send_ids, time_span_info

def calculate_stats(latencies):
    """Calculates statistics for a list of latencies (list of tuples)."""
    if not latencies:
        return None
    np_latencies = np.array([l[0] for l in latencies])
    return {
        'mean': np.mean(np_latencies),
        'std': np.std(np_latencies),
        'min': np.min(np_latencies),
        'max': np.max(np_latencies),
        'count': len(np_latencies)
    }

def calculate_time_span(latencies, gs_send_ids):
    """Calcola il tempo totale tra il primo e l'ultimo sample dalle latenze."""
    if not latencies or len(latencies) < 2:
        return None
    
    # Per calcolare il time span corretto, dovremmo avere accesso ai timestamp originali
    # Per ora restituiamo None, ma questa funzione può essere espansa se necessario
    return None

def plot_latencies(latencies_tls, label_tls, stats_tls, time_span_tls,
                   latencies_no_tls, label_no_tls, stats_no_tls, time_span_no_tls):
    """Plots the latencies and displays statistics. GS-SEND points in verde."""
    plt.figure(figsize=(14, 8))
    ax = plt.gca()

    # Separate normal and GS-SEND points
    def split_latencies(latencies_list_param): # Changed parameter name
        all_x_coords = []
        all_y_coords = []
        gs_x_coords = []
        gs_y_coords = []
        for idx, (lat, _msg_id, is_gs) in enumerate(latencies_list_param): # _msg_id to show it's not used here
            all_x_coords.append(idx)
            all_y_coords.append(lat)
            if is_gs:
                gs_x_coords.append(idx)
                gs_y_coords.append(lat)
        return (all_x_coords, all_y_coords), (gs_x_coords, gs_y_coords)

    if latencies_tls and stats_tls:
        (all_x_tls, all_y_tls), (x_tls_gs, y_tls_gs) = split_latencies(latencies_tls)
        # Plot the main line with all points, using its original marker 'o'
        plt.plot(all_x_tls, all_y_tls, label=f"{label_tls} (N={stats_tls['count']})", alpha=0.7, marker='o', linestyle='-', markersize=4)
        # Overlay GS-SEND points with green color and 'o' marker
        if x_tls_gs:
            plt.scatter(x_tls_gs, y_tls_gs, color='green', label=f"GS-SEND (TLS)", marker='o', s=60, edgecolors='darkgreen', zorder=10)

    if latencies_no_tls and stats_no_tls:
        (all_x_no_tls, all_y_no_tls), (x_no_tls_gs, y_no_tls_gs) = split_latencies(latencies_no_tls)
        # Plot the main line with all points, using its original marker 'x'
        plt.plot(all_x_no_tls, all_y_no_tls, label=f"{label_no_tls} (N={stats_no_tls['count']})", alpha=0.7, marker='x', linestyle='--', markersize=4)
        # Overlay GS-SEND points with green color and 'x' marker
        if x_no_tls_gs:
            # Using a slightly different green ('limegreen') for No-TLS GS-SEND for potential distinction, or could be 'green'
            plt.scatter(x_no_tls_gs, y_no_tls_gs, color='limegreen', label=f"GS-SEND (No TLS)", marker='x', s=60, edgecolors='darkgreen', zorder=10)

    plt.xlabel("Message Sequence Index (Comandi)")
    plt.ylabel("Latency (ms)")
    plt.title("MQTT Message Latency Comparison: TLS vs. No TLS (GS-SEND in verde)")
    plt.legend(loc='upper left')
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)

    # Prepare text for statistics
    text_y_current = 0.95  # Start Y position for text (relative to axes)
    text_x_pos = 1.02    # X position for text (to the right of the plot area)
    line_height = 0.04   # Approximate height for one line of text
    box_padding = 0.03   # Padding around text group

    # Combined TLS metrics (latencies + battery)
    if stats_tls:
        tls_combined_text = (f"{label_tls} Stats:\n"
                            f"Avg: {stats_tls['mean']:.2f} ms\n"
                            f"Std: {stats_tls['std']:.2f} ms\n"
                            f"Min: {stats_tls['min']:.2f} ms\n"
                            f"Max: {stats_tls['max']:.2f} ms\n"
                            f"Samples: {stats_tls['count']}")
        #if time_span_tls:
        #    tls_combined_text += f"\nTime span: {time_span_tls['seconds']:.1f}s ({time_span_tls['minutes']:.1f}m)"
        tls_combined_text += f"\nBattery: {BATTERY_PERCENTAGE_TLS:.1f}%"
        
        plt.text(text_x_pos, text_y_current, tls_combined_text,
                 transform=ax.transAxes, fontsize=9, va='top', ha='left',
                 bbox=dict(boxstyle='round,pad=0.5', fc='skyblue', alpha=0.5))
        text_y_current -= (tls_combined_text.count('\n') + 1) * line_height + box_padding

    # Combined No-TLS metrics (latencies + battery)
    if stats_no_tls:
        no_tls_combined_text = (f"{label_no_tls} Stats:\n"
                               f"Avg: {stats_no_tls['mean']:.2f} ms\n"
                               f"Std: {stats_no_tls['std']:.2f} ms\n"
                               f"Min: {stats_no_tls['min']:.2f} ms\n"
                               f"Max: {stats_no_tls['max']:.2f} ms\n"
                               f"Samples: {stats_no_tls['count']}")
        #if time_span_no_tls:
        #    no_tls_combined_text += f"\nTime span: {time_span_no_tls['seconds']:.1f}s ({time_span_no_tls['minutes']:.1f}m)"
        no_tls_combined_text += f"\nBattery: {BATTERY_PERCENTAGE_NO_TLS:.1f}%"
        
        plt.text(text_x_pos, text_y_current, no_tls_combined_text,
                 transform=ax.transAxes, fontsize=9, va='top', ha='left',
                 bbox=dict(boxstyle='round,pad=0.5', fc='lightcoral', alpha=0.5))
        text_y_current -= (no_tls_combined_text.count('\n') + 1) * line_height + box_padding

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
    latencies_tls, gs_send_ids_tls, time_span_tls = parse_log_file(LOG_FILE_TLS)
    print(f"Found {len(latencies_tls)} latencies with TLS.")

    print(f"Parsing No-TLS log file: {LOG_FILE_NO_TLS}")
    latencies_no_tls, gs_send_ids_no_tls, time_span_no_tls = parse_log_file(LOG_FILE_NO_TLS)
    print(f"Found {len(latencies_no_tls)} latencies without TLS.")

    if latencies_tls and latencies_no_tls:
        min_len = min(len(latencies_tls), len(latencies_no_tls))
        if len(latencies_tls) != len(latencies_no_tls):
            print(f"\nAdjusting datasets to the same number of samples: {min_len}")
            latencies_tls = latencies_tls[:min_len]
            latencies_no_tls = latencies_no_tls[:min_len]
            print(f"  New count for TLS latencies: {len(latencies_tls)}")
            print(f"  New count for No-TLS latencies: {len(latencies_no_tls)}")
        else:
            print(f"\nBoth datasets have the same number of samples: {len(latencies_tls)}")


    if not latencies_tls and not latencies_no_tls:
        print("No latency data could be extracted from the log files.")
        # Call plot_latencies to show an empty graph with a message
        plot_latencies([], "With TLS", None, None, [], "Without TLS", None, None)
    else:
        stats_tls_data = calculate_stats(latencies_tls)
        stats_no_tls_data = calculate_stats(latencies_no_tls)
        
        plot_latencies(
            latencies_tls, "With TLS", stats_tls_data, time_span_tls,
            latencies_no_tls, "Without TLS", stats_no_tls_data, time_span_no_tls
        )
