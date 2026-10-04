#!/bin/bash
set -eu
export PGDATA="${PGDATA:-/var/lib/postgresql/data}"
if [ "$(id -u)" = 0 ]; then
    mkdir -p "$PGDATA"
    chown postgres:postgres "$PGDATA"
    chmod 700 "$PGDATA"
    exec gosu postgres bash "$0"
fi

if [ ! -f "$PGDATA/PG_VERSION" ]; then
    # Never overwrite a partially initialized or unknown directory.
    if [ -n "$(find "$PGDATA" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
        echo 'Volume da réplica contém dados incompletos; bootstrap interrompido, sem apagar arquivos.' >&2
        exit 1
    fi
    case "$REPLICATION_PASSWORD" in
        *[!a-zA-Z0-9_.-]*) echo 'Use REPLICATION_PASSWORD URL-safe gerada pelo script.' >&2; exit 1 ;;
    esac
    export PGPASSWORD="$REPLICATION_PASSWORD"
    echo 'Criando réplica física inicial por pg_basebackup.'
    pg_basebackup -h db -p 5432 -U ecopulse_repl -D "$PGDATA" -Fp -X stream -R -S ecopulse_replica
    # Password remains in a private volume, never stdout or application logs.
    umask 077
    printf "\nprimary_conninfo = 'host=db port=5432 user=ecopulse_repl password=%s application_name=ecopulse_replica'\nprimary_slot_name = 'ecopulse_replica'\n" "$REPLICATION_PASSWORD" >> "$PGDATA/postgresql.auto.conf"
    unset PGPASSWORD
fi

# After controlled promotion standby.signal disappears. Existing PG_VERSION
# means startup preserves that state; it never recreates standby.signal.
exec postgres -c hot_standby=on -c wal_level=replica -c max_wal_senders=10 -c max_replication_slots=10
