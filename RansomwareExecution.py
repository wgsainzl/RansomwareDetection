esto es correcto?

#!/bin/bash
# ==============================================================================
# run_ransomware_workloads.sh
# Ejecuta una serie de programas ransomware mientras captura contadores de
# rendimiento de hardware (PMCs) con `perf stat`, generando un CSV por
# ejecución con el formato: timestamp,EVENT1,EVENT2,...
#
# Uso:
#   ./run_ransomware_workloads.sh <directorio_salida> <directorio_test_data>
#
# Requiere: perf, p7zip-full, gnupg, openssl, stress-ng, sysbench, rsync
# ==============================================================================
set -euo pipefail
OUT_DIR="${1:-./dataset/raw/ransomware}"
TEST_DATA_DIR="${2:-./test_data}"
SAMPLE_INTERVAL_MS=10   # igual que el paper (10ms)
DURATION_S=30            # duración de cada workload
# Eventos de hardware seleccionados por los autores (ajusta según tu CPU)
EVENTS="task-clock,context-switches,page-faults,cpu-migrations"
mkdir -p "$OUT_DIR"
mkdir -p "$TEST_DATA_DIR"
# ------------------------------------------------------------------
# Función auxiliar: ejecuta un comando bajo perf y convierte la salida
# a CSV con columna de timestamp
# ------------------------------------------------------------------
run_with_perf () {
    local name="$1"
    shift
    local cmd=("$@")
    local run_id
    run_id=$(date +%Y%m%d_%H%M%S)
    local raw_file="${OUT_DIR}/${name}_${run_id}.perf.txt"
    local csv_file="${OUT_DIR}/${name}_${run_id}.csv"
    echo ">>> Ejecutando: $name"
    echo "    Comando: ${cmd[*]}"
    # perf stat con muestreo por intervalos (-I) en ms, salida a archivo
    perf stat -I "$SAMPLE_INTERVAL_MS" -e "$EVENTS" -x, -o "$raw_file" \
        timeout "$DURATION_S" "${cmd[@]}" > /dev/null 2>&1 || true
    # Convertir la salida de perf (formato CSV nativo con -x,) a nuestro esquema
    python3 - "$raw_file" "$csv_file" "$EVENTS" << 'PYEOF'
import sys, csv
from collections import defaultdict
raw_path, csv_path, events_str = sys.argv[1], sys.argv[2], sys.argv[3]
events = events_str.split(",")
rows = defaultdict(dict)
with open(raw_path) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",")
        # formato perf -x,: timestamp,value,unit,event,...
        try:
            ts = float(parts[0])
            value = parts[1]
            event = parts[3]
        except (ValueError, IndexError):
            continue
        value = value if value not in ("<not", "counted>") else "0"
        try:
            value = float(value)
        except ValueError:
            value = 0.0
        rows[ts][event] = value
with open(csv_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp"] + events)
    for ts in sorted(rows.keys()):
        row = [ts] + [rows[ts].get(ev, 0) for ev in events]
        writer.writerow(row)
print(f"CSV generado: {csv_path} ({len(rows)} muestras)")
PYEOF
    rm -f "$raw_file"
}
# ------------------------------------------------------------------
# Preparar datos de prueba (archivos dummy para compresión/cifrado/copia)
# ------------------------------------------------------------------
prepare_test_data () {
    if [ ! -f "${TEST_DATA_DIR}/sample_100mb.bin" ]; then
        echo ">>> Generando archivos de prueba en $TEST_DATA_DIR"
        dd if=/dev/urandom of="${TEST_DATA_DIR}/sample_100mb.bin" bs=1M count=100 status=none
        mkdir -p "${TEST_DATA_DIR}/many_files"
        for i in $(seq 1 200); do
            dd if=/dev/urandom of="${TEST_DATA_DIR}/many_files/file_${i}.dat" bs=1K count=50 status=none
        done
    fi
}
# ==============================================================================
# WORKLOADS RANSOMWARE
# ==============================================================================
prepare_test_data
# 1. CryptSky
run_with_perf "CryptSky" \
    bash -c "cd ~/Desktop/'Ransomware Scripts'/CryptSky && python3 main.py '${TEST_DATA_DIR}'"
echo ""
echo "=== Todos los workloads ransomware completados ==="
echo "CSVs disponibles en: $OUT_DIR"
