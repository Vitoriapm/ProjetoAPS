#!/bin/sh
set -eu
umask 077
task_cookie_file="${HOME:?HOME do contêiner não definido}/.erlang.cookie"
printf '%s' "$RABBITMQ_ERLANG_COOKIE" > "$task_cookie_file"
chmod 600 "$task_cookie_file"
rabbitmqctl -n rabbit@rabbit1 await_startup --timeout 120
rabbitmqctl -n rabbit@rabbit1 await_online_nodes "${RABBIT_EXPECTED_NODES:-1}" --timeout 120
rabbitmqctl -n rabbit@rabbit1 import_definitions /init/definitions.json
echo 'RabbitMQ: políticas de retry/DLQ importadas após formação dos nós.'
