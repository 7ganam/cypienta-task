# Run usage-backend on Docker Desktop Kubernetes

This deploys only the backend into the `usage-backend-only` namespace. The full
demo uses `default`, so both deployments can run in the same cluster without
sharing Kubernetes resources. Run commands from the repository root.

## 1. Start Kubernetes

Start Kubernetes in Docker Desktop, then confirm the local cluster is ready:

```sh
kubectl config use-context docker-desktop
kubectl --context docker-desktop get nodes
```

Wait for the node status to show `Ready`.

## 2. Build the backend image

```sh
docker build -t usage-backend:local apps/usage-backend
```

## 3. Create the namespace and Secret

The Secret uses the same private file as the full demo. Create or edit it:

```sh
mkdir -p "$HOME/.config/cypienta-demo"
chmod 700 "$HOME/.config/cypienta-demo"
openssl rand -base64 48
nano "$HOME/.config/cypienta-demo/real-upstream-secrets.env"
```

Copy the generated value into `DJANGO_SECRET_KEY` and enter your real API key,
replacing both placeholders:

```dotenv
API_KEY=<your real upstream API key>
DJANGO_SECRET_KEY=<paste the generated value here>
```

Save and close the editor, then restrict access to the file:

```sh
chmod 600 "$HOME/.config/cypienta-demo/real-upstream-secrets.env"
```

Create the namespace and copy the credentials into it:

```sh
kubectl --context docker-desktop create namespace usage-backend-only --dry-run=client -o yaml | kubectl --context docker-desktop apply -f -
kubectl --context docker-desktop -n usage-backend-only create secret generic usage-backend-secrets \
  --from-env-file="$HOME/.config/cypienta-demo/real-upstream-secrets.env" \
  --dry-run=client -o yaml | kubectl --context docker-desktop -n usage-backend-only apply --server-side -f -
```

## 4. Deploy and check

```sh
kubectl --context docker-desktop -n usage-backend-only apply -k apps/usage-backend/k8s
kubectl --context docker-desktop -n usage-backend-only rollout status deployment/usage-backend --timeout=180s
kubectl --context docker-desktop -n usage-backend-only get pods -l app=usage-backend
```

Expect two Pods, both `1/1` Ready. The backend calls the real upstream API;
readiness fails if the credentials are invalid or the upstream is unreachable.

## 5. Open the backend locally

Run this and leave it running:

```sh
kubectl --context docker-desktop -n usage-backend-only port-forward service/usage-backend 8000:8000
```

In another terminal, check the health endpoints:

```sh
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

The backend is available at `http://localhost:8000`. Stop port forwarding with
Ctrl+C.

## Update or remove

After rebuilding the image or updating the Secret, restart the backend Pods:

```sh
kubectl --context docker-desktop -n usage-backend-only rollout restart deployment/usage-backend
```

Remove the backend-only deployment and its Secret by deleting its namespace:

```sh
kubectl --context docker-desktop delete namespace usage-backend-only
```
