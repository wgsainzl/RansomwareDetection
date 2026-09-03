#!/bin/bash
# ==============================================================================
# run_benign_workloads.sh
# Ejecuta una serie de programas benignos mientras captura contadores de
# rendimiento de hardware (PMCs) con `perf stat`, generando un CSV por
# ejecución con el formato: timestamp,EVENT1,EVENT2,...
#
# Uso:
#   ./run_benign_workloads.sh <directorio_salida> <directorio_test_data>
#
# Requiere: perf, p7zip-full, gnupg, openssl, stress-ng, sysbench, rsync
# ==============================================================================

set -euo pipefail

OUT_DIR="${1:-./dataset/raw/benign}"
TEST_DATA_DIR="${2:-./test_data}"
SAMPLE_INTERVAL_MS=10   # igual que el paper (10ms)
DURATION_S=30            # duración de cada workload

# Eventos de hardware seleccionados por los autores (ajusta según tu CPU)
EVENTS="branches,instructions,cache-references,mem-loads,mem-stores,LLC-misses"

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
# WORKLOADS BENIGNOS
# ==============================================================================

prepare_test_data

# 1. Compresión benigna (7zip)
run_with_perf "7zip_compress" \
    7z a -mx=5 "${TEST_DATA_DIR}/output.7z" "${TEST_DATA_DIR}/many_files/"

# 2. Encriptación benigna con GPG (simétrica, passphrase de prueba)
run_with_perf "gpg_encrypt" \
    bash -c "gpg --batch --yes --passphrase testpass123 -c ${TEST_DATA_DIR}/sample_100mb.bin"

# 3. Encriptación benigna con OpenSSL AES-256
run_with_perf "openssl_encrypt" \
    openssl enc -aes-256-cbc -salt -in "${TEST_DATA_DIR}/sample_100mb.bin" \
        -out "${TEST_DATA_DIR}/sample_100mb.enc" -pass pass:testpass123

# 4. Copia/movimiento de archivos (I/O intensivo)
run_with_perf "rsync_copy" \
    rsync -a "${TEST_DATA_DIR}/many_files/" "${TEST_DATA_DIR}/many_files_copy/"

# 5. Lectura/escritura masiva de archivos
run_with_perf "file_readwrite" \
    bash -c "for f in ${TEST_DATA_DIR}/many_files/*; do cat \"\$f\" > /dev/null; done"

# 6. Compilación de código (usa un repo clonado previamente, ej. jq)
if [ -d "${TEST_DATA_DIR}/repo_to_build" ]; then
    run_with_perf "compile_code" \
        bash -c "cd ${TEST_DATA_DIR}/repo_to_build && make -j$(nproc)"
fi

# 7. Stress test (CPU + memoria + I/O combinados)
run_with_perf "stress_cpu_mem" \
    stress-ng --cpu 4 --vm 2 --vm-bytes 256M --io 2 --timeout "${DURATION_S}s"

# 8. Benchmark de CPU/memoria con sysbench
run_with_perf "sysbench_cpu" \
    sysbench cpu --cpu-max-prime=20000 --time="$DURATION_S" run

echo ""
echo "=== Todos los workloads benignos completados ==="
echo "CSVs disponibles en: $OUT_DIR"
