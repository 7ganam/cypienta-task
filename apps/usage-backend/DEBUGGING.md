# Kubernetes backend crash loop caused by a short Django secret

## Symptom

After restarting `deployment/usage-backend` in the Docker Desktop cluster, the
rollout stalled at `1 out of 2 new replicas have been updated`. In the
Kubernetes dashboard, the backend containers started and then stopped. The
backend Pods were in `CrashLoopBackOff` and none were Ready.

## Investigation

Checked the backend Pods with `kubectl get pods`, then inspected the Deployment
and Pod events with `kubectl describe`. The events showed startup probe failures,
but those were a consequence of the application exiting. Reading the previous
container logs with `kubectl logs <pod> --previous` exposed the startup exception:

```text
django.core.exceptions.ImproperlyConfigured:
DJANGO_SECRET_KEY must contain at least 50 characters
```

This narrowed the issue to the Secret's configuration rather than the image,
network, or Kubernetes probes.

## Root Cause

The `usage-backend-secrets` Secret contained a `DJANGO_SECRET_KEY` shorter than
the 50-character minimum enforced by the production Django settings. Django
could not initialize, so Gunicorn workers exited and Kubernetes repeatedly
restarted the container.

## Fix

Generate a sufficiently long key with `openssl rand -base64 48` (64 characters),
put it in `DJANGO_SECRET_KEY` in the local secrets env file, update the
Kubernetes Secret from that file, and restart the Deployment. The Docker Desktop
setup guides now include this generation command. The cluster rollout must be
rerun after applying the updated Secret; its success was not verified as part
of this investigation.

## Prevention

- Generate the Django key rather than typing a placeholder or short value.
- Keep the 50-character minimum beside the secret setup instructions.
- Before investigating probes, inspect previous container logs when a Pod
  repeatedly restarts; probe failures can be symptoms of an application crash.
- Add a deployment preflight check for required Secret keys and configuration
  constraints so invalid credentials fail before rollout.
