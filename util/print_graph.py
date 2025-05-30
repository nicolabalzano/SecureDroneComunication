import re
from datetime import datetime
import matplotlib.pyplot as plt
from collections import deque
import os
import numpy as np # Per calcoli statistici (media, mediana, std, min, max)

# Regex (invariate)
send_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (DRONE|GS)-SEND: Message ID (.*?) type \w+ sent at (\d+\.\d+)")
recv_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (DRONE|GS)-RECV: Message ID (.*?) type \w+ received at (\d+\.\d+)")

def process_log_content(log_content_str, filename=""):
    sent_messages = {}
    transit_data_pairs = []

    for line in log_content_str.strip().split('\n'):
        send_match = send_pattern.match(line)
        recv_match = recv_pattern.match(line)

        if send_match:
            _, source_prefix, msg_id_str, send_time_epoch_str = send_match.groups()
            send_time_epoch = float(send_time_epoch_str)
            msg_id_str = msg_id_str.strip()
            expected_receiver_prefix = 'GS' if source_prefix == 'DRONE' else 'DRONE'
            key = (msg_id_str, expected_receiver_prefix)
            if key not in sent_messages:
                sent_messages[key] = deque()
            sent_messages[key].append(send_time_epoch)
        elif recv_match:
            _, receiver_prefix, msg_id_str, recv_time_epoch_str = recv_match.groups()
            recv_time_epoch = float(recv_time_epoch_str)
            msg_id_str = msg_id_str.strip()
            key = (msg_id_str, receiver_prefix)
            if key in sent_messages and sent_messages[key]:
                send_time_epoch = sent_messages[key].popleft()
                transit_seconds = recv_time_epoch - send_time_epoch
                transit_ms = transit_seconds * 1000
                send_datetime = datetime.fromtimestamp(send_time_epoch)
                transit_data_pairs.append((send_datetime, transit_ms))
    
    transit_data_pairs.sort(key=lambda x: x[0])
    ordered_transit_times_ms = [data[1] for data in transit_data_pairs]
    
    unmatched_count = 0
    for queue in sent_messages.values():
        unmatched_count += len(queue)
    if unmatched_count > 0:
        file_info = f"nel file {filename} " if filename else ""
        print(f"  Avviso: Trovati {unmatched_count} messaggi inviati senza corrispondente ricezione {file_info.strip()}.")
        
    return ordered_transit_times_ms

def calculate_metrics(data_list, label_prefix=""):
    """Calcola e formatta le metriche statistiche per una lista di dati."""
    if not data_list: # Se la lista è vuota dopo il troncamento/filtraggio
        metrics_str = f"{label_prefix}: N/D (Nessun dato)"
        legend_label = f"{label_prefix} (N=0)"
        return metrics_str, legend_label
    
    count = len(data_list)
    mean = np.mean(data_list)
    median = np.median(data_list)
    std_dev = np.std(data_list)
    min_val = np.min(data_list)
    max_val = np.max(data_list)
    
    metrics_str = (
        f"{label_prefix} (N={count}):\n"
        f"  Media: {mean:.2f} ms\n"
        f"  Mediana: {median:.2f} ms\n" 
        f"  Std Dev: {std_dev:.2f} ms\n"
        f"  Min: {min_val:.2f} ms, Max: {max_val:.2f} ms"
    )
    
    legend_label = (
        f"{label_prefix} (N={count}, Media: {mean:.2f} ms, StdDev: {std_dev:.2f} ms, Min: {min_val:.2f} ms, Max: {max_val:.2f} ms)"
    )
    return metrics_str, legend_label

def main():
    log_file_tls_path = "/home/nikba/DrivenDroneMQTT/logs/mqtt_timing_2025-05-30_no_tls.log"
    log_file_no_tls_path = "/home/nikba/DrivenDroneMQTT/logs/mqtt_timing_2025-05-30_with_tls.log" 
    
    raw_transit_times_tls = []
    raw_transit_times_no_tls = []

    # Elabora il file CON TLS
    if os.path.exists(log_file_tls_path):
        with open(log_file_tls_path, 'r') as f:
            content_tls = f.read()
        print(f"\nElaborazione file CON TLS: {log_file_tls_path}")
        raw_transit_times_tls = process_log_content(content_tls, log_file_tls_path)
        if not raw_transit_times_tls:
            print(f"  Nessun dato di transito completo (coppie SEND-RECV) trovato nel file {log_file_tls_path}.")
    else:
        print(f"File non trovato: {log_file_tls_path}")

    # Elabora il file SENZA TLS
    if os.path.exists(log_file_no_tls_path):
        with open(log_file_no_tls_path, 'r') as f:
            content_no_tls = f.read()
        print(f"\nElaborazione file SENZA TLS: {log_file_no_tls_path}")
        raw_transit_times_no_tls = process_log_content(content_no_tls, log_file_no_tls_path)
        if not raw_transit_times_no_tls:
            print(f"  Nessun dato di transito completo (coppie SEND-RECV) trovato nel file {log_file_no_tls_path}.")
    else:
        print(f"File non trovato: {log_file_no_tls_path}")

    # Determina il numero di campioni da utilizzare per il confronto
    min_samples = 0
    valid_tls = bool(raw_transit_times_tls)
    valid_no_tls = bool(raw_transit_times_no_tls)

    if valid_tls and valid_no_tls:
        min_samples = min(len(raw_transit_times_tls), len(raw_transit_times_no_tls))
        print(f"\nConfronto basato sui primi {min_samples} campioni comuni da ciascun file.")
    elif valid_tls:
        min_samples = len(raw_transit_times_tls)
        print(f"\nMostrando solo dati da '{log_file_tls_path}' ({min_samples} campioni). L'altro file non ha dati validi o non è stato trovato.")
    elif valid_no_tls:
        min_samples = len(raw_transit_times_no_tls)
        print(f"\nMostrando solo dati da '{log_file_no_tls_path}' ({min_samples} campioni). L'altro file non ha dati validi o non è stato trovato.")
    else:
        print("\nNessun dato di transito valido da elaborare da nessuno dei due file.")
        return

    if min_samples == 0: # Può accadere se uno dei file è valido ma ha 0 campioni, o entrambi sono vuoti
        print("Nessun campione comune o nessun dato valido trovato per il confronto o il plot.")
        return

    # Tronca le liste al numero minimo di campioni
    # Se una lista originale era vuota, la sua versione troncata rimarrà vuota
    common_transit_times_tls = raw_transit_times_tls[:min_samples] if valid_tls else []
    common_transit_times_no_tls = raw_transit_times_no_tls[:min_samples] if valid_no_tls else []
    
    # Ricalcola le metriche sui dati troncati/comuni
    # (solo se la rispettiva lista comune non è vuota, che dipende da min_samples e dalla validità originale)
    print("\n--- Metriche calcolate sui campioni utilizzati per il plot ---")
    metrics_str_tls, legend_label_tls = calculate_metrics(common_transit_times_tls, f"Con TLS (Primi {len(common_transit_times_tls)})")
    if common_transit_times_tls: print(metrics_str_tls)
    else: print(f"Con TLS: Nessun dato utilizzato per il plot (min_samples={min_samples}).")


    metrics_str_no_tls, legend_label_no_tls = calculate_metrics(common_transit_times_no_tls, f"Senza TLS (Primi {len(common_transit_times_no_tls)})")
    if common_transit_times_no_tls: print(metrics_str_no_tls)
    else: print(f"Senza TLS: Nessun dato utilizzato per il plot (min_samples={min_samples}).")
        
    # Prepara i dati per il plot
    plt.figure(figsize=(14, 8))
    
    plotted_something = False
    if common_transit_times_tls:
        x_axis_values = list(range(len(common_transit_times_tls)))
        plt.plot(x_axis_values, common_transit_times_tls, marker='o', linestyle='-', label=legend_label_tls)
        plotted_something = True

    if common_transit_times_no_tls:
        x_axis_values = list(range(len(common_transit_times_no_tls)))
        plt.plot(x_axis_values, common_transit_times_no_tls, marker='x', linestyle='--', label=legend_label_no_tls)
        plotted_something = True
        
    if not plotted_something:
        print("\nNessun dato da plottare.")
        return

    # L'etichetta dell'asse X dovrebbe riflettere il numero di punti effettivamente plottati
    # che è la lunghezza della lista più lunga tra common_transit_times_tls e common_transit_times_no_tls
    # (che sarà min_samples se entrambi avevano dati, o la lunghezza dell'unico set di dati se solo uno ne aveva)
    actual_plot_length = 0
    if common_transit_times_tls: actual_plot_length = max(actual_plot_length, len(common_transit_times_tls))
    if common_transit_times_no_tls: actual_plot_length = max(actual_plot_length, len(common_transit_times_no_tls))

    plt.xlabel(f"Indice Comando (Primi {actual_plot_length} campioni elaborati per file)")
    plt.ylabel("Tempo di Transito (ms)")
    plt.title("Confronto Tempi di Transito Comandi (Invio -> Ricezione)")
    
    plt.legend(fontsize='small', loc='best') # loc='best' per posizionare automaticamente la legenda
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.show()

if __name__ == "__main__":
    main()