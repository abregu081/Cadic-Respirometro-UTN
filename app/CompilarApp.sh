#!/bin/bash

echo "------------------------"
echo "Compilando la aplicacion"
echo "------------------------"

cd "/home/abregu/Escritorio/CADIC - Respirometro/Andrea - Software"

source .venv/bin/activate

cd "/home/abregu/Escritorio/CADIC - Respirometro/Andrea - Software/app"
python setup.py build

echo "----------------------------"
echo "Se termino la compilacion :D"
echo "----------------------------"
