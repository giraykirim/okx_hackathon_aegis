# Public ERC-8004 metadata

AEGIS is registered on Avalanche Fuji as **Agent #273**. The operator approved registration through MetaMask; independent readback matched the Registered event, transaction sender/input, ownerOf(273) and tokenURI(273).

- Agent URI: https://gist.githubusercontent.com/giraykirim/367b45ff5fce169bf1e7a1447eb88d91/raw/agent-registration.json
- Gist: https://gist.github.com/giraykirim/367b45ff5fce169bf1e7a1447eb88d91
- Registry: `0x8004A818BFB912233c491871b3d84c89A494BD9e`
- Registration transaction: `0x7b61d86a11c815b301d44d6062c938bd7c8995c9d81332f9bb476c0bc436f08b`
- Owner: `0x3754131A55d043fC49eB93cEBfB381953cA41bB8`
- Public descriptor source: `web3/public/agent-registration.json`
- Publication evidence: `web3/metadata-publication.json`
- Chain verification evidence: `web3/registration-proof.json`

After confirmation, the same Gist was updated with the actual registration: `agentId=273`, `agentRegistry=eip155:43113:0x8004A818BFB912233c491871b3d84c89A494BD9e`. An unauthenticated HTTPS GET returned HTTP 200 with bytes matching the reviewed local JSON, SHA-256 `756b81b47bd00b65d7c9799ba1ed93e7aee0d46611288a007d5feb68ba133751`. The raw response is JSON served as `text/plain; charset=utf-8`.

`active=false`, `services=[]`, `supportedTrust=[]` remain deliberate: the backend runs locally and has no deployed public service URL. The private repository remains private. Do not set `AEGIS_PUBLIC_ORIGIN` to the Gist URL; it is a metadata file, not a service origin. No credentials, private balances or local control endpoints are published.

The ignored mode-0600 `web3/.env` contains a different unused disposable wallet. Do not run key-based registration expecting it to sign from the funded MetaMask account. Use the read-only verification command in `web3/README.md`; do not mint another agent to recover a read timeout.

Publication commands executed: initial `gh gist create --public --desc 'AEGIS ERC-8004 Fuji testnet metadata - public descriptor only' web3/public/agent-registration.json`; update `gh api --method PATCH gists/367b45ff5fce169bf1e7a1447eb88d91 --input /tmp/aegis-gist-update.json --jq '{id,public,updated_at}'`. The update body contains only the reviewed descriptor. The stable URI omits a revision hash; re-fetch and verify bytes after every edit.
