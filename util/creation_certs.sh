#!/usr/bin/env bash
set -euo pipefail

# Directory destinazione
CA_DIR="/etc/mosquitto/ca_certificates"
CERTS_DIR="/etc/mosquitto/certs"
TMPDIR="$(mktemp -d)"

echo "✔ Creazione cartelle se non esistono"
sudo mkdir -p "$CA_DIR" "$CERTS_DIR"
sudo chown root:mosquitto "$CA_DIR" "$CERTS_DIR"
sudo chmod 750 "$CA_DIR" "$CERTS_DIR"

echo "✔ Lavoro in: $TMPDIR"
cd "$TMPDIR"

# 1) CA
echo "1) Generazione CA"
openssl genpkey -algorithm RSA -out ca.key
openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 -out ca.crt \
  -subj "/C=IT/ST=Italy/L=Rome/O=MyMQTT/CN=MyCA"

echo "→ Installazione CA in $CA_DIR"
sudo install -o root -g mosquitto -m 640 ca.crt  "$CA_DIR/ca.crt"
sudo install -o root -g mosquitto -m 640 ca.key  "$CA_DIR/ca.key"

# 2) Broker
echo "2) Generazione broker cert (con SAN)"
cat > broker.cnf <<EOF
[req]
default_bits       = 2048
prompt             = no
default_md         = sha256
distinguished_name = dn
req_extensions     = req_ext

[dn]
C  = IT
ST = Italy
L  = Rome
O  = MyMQTT
CN = 127.0.0.1

[req_ext]
subjectAltName = @alt_names

[alt_names]
IP.1  = 127.0.0.1
DNS.1 = localhost
EOF

openssl genpkey -algorithm RSA -out broker.key
openssl req -new -key broker.key -out broker.csr -config broker.cnf
openssl x509 -req -in broker.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out broker.crt -days 1095 -sha256 -extensions req_ext -extfile broker.cnf

echo "→ Installazione Broker cert in $CERTS_DIR"
sudo install -o root -g mosquitto -m 640 broker.crt  "$CERTS_DIR/broker.crt"
sudo install -o root -g mosquitto -m 640 broker.key  "$CERTS_DIR/broker.key"

# 3) Client
echo "3) Generazione client cert"
openssl genpkey -algorithm RSA -out client.key
openssl req -new -key client.key -out client.csr \
  -subj "/C=IT/ST=Italy/L=Rome/O=MyMQTT/CN=client"
openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out client.crt -days 1095 -sha256

echo "→ Installazione Client cert in $CERTS_DIR"
sudo install -o root -g mosquitto -m 640 client.crt  "$CERTS_DIR/client.crt"
sudo install -o root -g mosquitto -m 640 client.key  "$CERTS_DIR/client.key"

# Pulizia
cd /
rm -rf "$TMPDIR"

echo "✔ Tutti i certificati sono stati generati e piazzati in:"
echo "    CA:     $CA_DIR/ca.crt, ca.key"
echo "    Broker: $CERTS_DIR/broker.crt, broker.key"
echo "    Client: $CERTS_DIR/client.crt, client.key"
echo
echo "Ricordati di configurare mosquitto.conf con:"
echo "  cafile /etc/mosquitto/ca_certificates/ca.crt"
echo "  certfile /etc/mosquitto/certs/broker.crt"
echo "  keyfile  /etc/mosquitto/certs/broker.key"
echo
echo "E, lato client, di usare:"
echo "  cafile=/etc/mosquitto/ca_certificates/ca.crt"
echo "  certfile=/etc/mosquitto/certs/client.crt"
echo "  keyfile=/etc/mosquitto/certs/client.key"
