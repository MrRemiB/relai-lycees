"""One process only: durable jobs and IGN global admission are process-local."""
bind='127.0.0.1:8137'
workers=1
worker_class='gthread'
threads=8
timeout=120
graceful_timeout=40
keepalive=2
limit_request_line=4094
limit_request_fields=40
limit_request_field_size=4096
preload_app=False
accesslog=None
errorlog='-'
capture_output=True
forwarded_allow_ips='127.0.0.1'
umask=0o077
