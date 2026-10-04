#!/bin/sh
set -eu

node_count="${REDIS_NODE_COUNT:-3}"
replicas="${REDIS_REPLICAS:-0}"
nodes=""
for number in $(seq 1 "$node_count"); do
    nodes="$nodes redis$number:6379"
done

all_ready() {
    for number in $(seq 1 "$node_count"); do
        info=$(redis-cli --no-auth-warning -h "redis$number" cluster info 2>/dev/null | tr -d '\r') || return 1
        echo "$info" | grep -q '^cluster_state:ok$' || return 1
        echo "$info" | grep -q '^cluster_slots_assigned:16384$' || return 1
        echo "$info" | grep -q "^cluster_known_nodes:$node_count$" || return 1
    done
}

if all_ready; then
    echo 'Redis Cluster existente saudável; nenhum dado modificado.'
    exit 0
fi

pristine=true
for number in $(seq 1 "$node_count"); do
    info=$(redis-cli --no-auth-warning -h "redis$number" cluster info | tr -d '\r')
    echo "$info" | grep -q '^cluster_slots_assigned:0$' || pristine=false
    echo "$info" | grep -q '^cluster_known_nodes:1$' || pristine=false
done

if [ "$pristine" = true ]; then
    echo "Criando Redis Cluster: $node_count nós, $replicas réplica(s) por primário."
    # Splitting this generated host list is intentional; it contains no user data.
    # shellcheck disable=SC2086
    redis-cli --no-auth-warning --cluster create $nodes --cluster-replicas "$replicas" --cluster-yes
else
    echo 'Cluster já contém estado; aguardando recuperação sem reset ou remoção de dados.'
fi

for attempt in $(seq 1 90); do
    if all_ready; then
        echo 'Redis Cluster pronto com 16384 slots.'
        exit 0
    fi
    sleep 1
done
echo 'Cluster não convergiu. Inspecione os nós/volumes; nenhum dado foi removido.' >&2
exit 1
