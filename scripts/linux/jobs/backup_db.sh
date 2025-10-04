#!/bin/bash
set -e
SRC="/volume2/homes/Hyungsoo/krx/krx_alertor_modular/data/krx_alertor.db"
DST="/volume2/homes/Hyungsoo/krx/krx_alertor_modular/backups/krx_alertor_$(date +%F).db"
[ -f "$SRC" ] && cp -p "$SRC" "$DST"
find /volume2/homes/Hyungsoo/krx/krx_alertor_modular/backups -type f -mtime +30 -delete
