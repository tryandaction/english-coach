"""
Build-time defaults for the commercial Cloud activation flow.

The source tree keeps these values empty by default.
`build_cloud.py` can temporarily inject public activation settings into this
module before packaging the cloud executable, then restore the file.

Important:
- `WORKER_URL` is public.
- `CLIENT_TOKEN` is the buyer-side activation token for `/activate` and `/verify`.
- It must NOT be the same as the seller/admin token used by key generation.
"""

WORKER_URL = ""
CLIENT_TOKEN = ""
