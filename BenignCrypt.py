#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# =====================================================================
# benign_crypt.py  --  CONTROL BENIGNO emparejado con CryptSky
#
# Proposito metodologico: aislar "comportamiento de ransomware" de
# "comportamiento de cifrado". Este script comparte con CryptSky TODO
# lo que no es malicioso:
#
#     factor                CryptSky           este control
#     -------------------   ----------------   ----------------
#     lenguaje              Python 2.7         Python 2.7        <- igual
#     libreria              PyCryptodome       PyCryptodome      <- igual
#     algoritmo             AES modo CTR       AES modo CTR      <- igual
#     contador              Counter.new(128)   Counter.new(128)  <- igual
#     patron de escritura   in-place           in-place          <- igual
#     recorrido             recursivo en $TD   recursivo en $TD  <- igual
#     -------------------   ----------------   ----------------
#     intencion             destructiva        REVERSIBLE        <- DIFERENCIA
#     nota de rescate       (si en RW real)    ninguna           <- DIFERENCIA
#
# Si los criterios de deteccion marcan IGUAL a este control que a
# CryptSky, entonces esos criterios miden "cifrado", no "ransomware":
# ese es el resultado cientifico que este control existe para revelar.
#
# AES-CTR es simetrico e involutivo respecto a la operacion de keystream:
# cifrar dos veces con la misma clave+contador devuelve el texto original.
# Por eso este control es REVERSIBLE (corre con --decrypt para restaurar),
# a diferencia del ransomware.
#
# Uso:
#   python2 benign_crypt.py            # cifra $TD (in-place, reversible)
#   python2 benign_crypt.py --decrypt  # revierte
#
# Mide con PCM igual que a CryptSky:
#   sudo $PCM/pcm 0.5 -csv=$OUT/benign_py_crypt_$(date +%Y%m%d_%H%M%S).csv -- \
#     /home/student/.pyenv/versions/2.7.18/bin/python benign_crypt.py
# =====================================================================

import os
import sys
import hashlib
from Crypto.Cipher import AES
from Crypto.Util import Counter

# Mismo directorio objetivo que CryptSky (startdirs)
STARTDIRS = ['/home/student/Desktop/Prueba']

# Clave fija derivada de una passphrase de prueba (control, no seguridad).
# CryptSky usa su propia clave; aqui lo importante es que la operacion
# criptografica sea la MISMA, no que la clave coincida.
KEY = hashlib.sha256(b'benign-control-passphrase').digest()  # 32 bytes -> AES-256

# Bloque de lectura. CryptSky con modify_file_inplace lee el archivo
# completo o por bloques; usamos un bloque grande para reescribir in-place.
CHUNK = 64 * 1024


def make_cipher():
    # Replica exacta de las lineas 59-60 de CryptSky:
    #   ctr = Counter.new(128)
    #   crypt = AES.new(key, AES.MODE_CTR, counter=ctr)
    ctr = Counter.new(128)
    return AES.new(KEY, AES.MODE_CTR, counter=ctr)


def process_file(path):
    """Cifra (o descifra: en CTR es la misma operacion) un archivo in-place,
    igual que modify_file_inplace de CryptSky."""
    try:
        cipher = make_cipher()
        # Leer todo, transformar, reescribir el MISMO archivo (in-place).
        with open(path, 'rb') as f:
            data = f.read()
        out = cipher.encrypt(data)
        with open(path, 'wb') as f:
            f.write(out)
        return True
    except (IOError, OSError) as e:
        sys.stderr.write('saltado %s: %s\n' % (path, e))
        return False


def walk_and_process():
    count = 0
    for startdir in STARTDIRS:
        for root, dirs, files in os.walk(startdir):
            for name in files:
                path = os.path.join(root, name)
                if os.path.isfile(path):
                    if process_file(path):
                        count += 1
    return count


if __name__ == '__main__':
    mode = 'descifrar' if '--decrypt' in sys.argv else 'cifrar'
    # En AES-CTR cifrar y descifrar son la MISMA operacion (XOR con
    # keystream identico), asi que no cambia el codigo, solo la etiqueta.
    print('Control benigno: %s in-place sobre %s' % (mode, STARTDIRS))
    n = walk_and_process()
    print('Procesados %d archivos.' % n)
    print('(Reversible: vuelve a correr para restaurar el contenido original.)')
