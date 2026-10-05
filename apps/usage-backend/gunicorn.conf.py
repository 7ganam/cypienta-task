import os

bind = "0.0.0.0:8000"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
worker_class = "gthread"
threads = 4
timeout = 30
graceful_timeout = 30
keepalive = 5
worker_tmp_dir = "/tmp"
control_socket = "/tmp/gunicorn.ctl"
# Django emits request logs as JSON. Avoid logging raw URLs and query strings twice.
accesslog = None
errorlog = "-"
capture_output = True
